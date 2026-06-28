"""Preflight 编排：把 L1–L5 在运行时串起来。

生成前先审视本地环境，对胶囊每个 role 撮合工具、绑定 Adapter 指令，
分类 ok / substituted / blocked；任何 blocked 即整体失败并给可执行提示。
产出 preflight_report.json(给人看) + execution_plan.json(给流水线吃)。

详见 docs/capsule-tool-abstraction-design.md §4。
"""

from __future__ import annotations

import json
import os
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from src.capsule_adapter import ExecutionDirective, reconcile
from src.capsule_resolver import load_all_tools, resolve_role


def scan_available_env(environ: dict) -> set[str]:
    """本地"可用"= 有非空值的 env key。"""
    return {key for key, value in environ.items() if value}


@dataclass
class RolePlan:
    role: str
    selected: str | None = None
    status: str = "ok"  # ok | substituted | blocked
    fallback: list[str] = field(default_factory=list)
    validated_with: str | None = None
    requires: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    directive: ExecutionDirective | None = None
    degraded: list[str] = field(default_factory=list)


@dataclass
class Preflight:
    capsule: str
    roles: dict[str, RolePlan] = field(default_factory=dict)
    status: str = "ok"  # ok | needs_confirmation | blocked
    blocked: list[str] = field(default_factory=list)


def _role_order(roles: dict) -> list[str]:
    """按 depends_on 拓扑序（决策六）。"""
    ordered: list[str] = []

    def visit(name: str) -> None:
        if name in ordered:
            return
        for dep in roles.get(name, {}).get("depends_on", []):
            if dep in roles:
                visit(dep)
        ordered.append(name)

    for name in roles:
        visit(name)
    return ordered


def _contract_for_role(output_contract: dict, role_name: str, role: dict) -> dict:
    """Return only the output-contract dimensions relevant to this role."""
    modality = role.get("modality") or role_name
    scoped: dict = {}
    if modality == "video":
        for key in ("clip_audio",):
            if key in output_contract:
                scoped[key] = output_contract[key]
    if modality == "image":
        for key in ("on_frame_text", "on_frame_text_fallback"):
            if key in output_contract:
                scoped[key] = output_contract[key]
    return scoped


def run_preflight(capsule: dict, tools: dict, available_env: set[str]) -> Preflight:
    roles_spec = capsule.get("roles", {})
    output_contract = capsule.get("output_contract", {})
    pf = Preflight(capsule=capsule.get("name", ""))

    for role_name in _role_order(roles_spec):
        role = dict(roles_spec[role_name])
        role.setdefault("modality", role_name)
        res = resolve_role(role, tools, available_env)

        plan = RolePlan(
            role=role_name,
            selected=res.selected,
            status=res.status,
            fallback=res.fallback,
            validated_with=role.get("validated_with"),
            requires=list(role.get("requires", [])),
            missing=res.missing,
        )

        if res.status == "blocked":
            pf.blocked.append(role_name)
        else:
            provides = tools.get(res.selected, {}).get("provides", {})
            directive = reconcile(_contract_for_role(output_contract, role_name, role), provides)
            plan.directive = directive
            plan.degraded = directive.degraded
            if directive.blocked:
                plan.status = "blocked"
                plan.missing = directive.blocked
                pf.blocked.append(role_name)

        pf.roles[role_name] = plan

    if pf.blocked:
        pf.status = "blocked"
    elif any(p.status == "substituted" or p.degraded for p in pf.roles.values()):
        pf.status = "needs_confirmation"
    else:
        pf.status = "ok"

    return pf


def _directive_dict(directive: ExecutionDirective | None) -> dict | None:
    if directive is None:
        return None
    return {
        "prompt_additions": directive.prompt_additions,
        "prompt_negatives": directive.prompt_negatives,
        "post_steps": directive.post_steps,
        "notes": directive.notes,
        "degraded": directive.degraded,
        "blocked": directive.blocked,
    }


def to_report(pf: Preflight) -> dict:
    """给人看的审视结论。"""
    return {
        "capsule": pf.capsule,
        "status": pf.status,
        "blocked": pf.blocked,
        "roles": {
            name: {
                "selected": plan.selected,
                "status": plan.status,
                "validated_with": plan.validated_with,
                "fallback": plan.fallback,
                "missing": plan.missing,
                "degraded": plan.degraded,
                "notes": (plan.directive.notes if plan.directive else []),
            }
            for name, plan in pf.roles.items()
        },
    }


def to_execution_plan(pf: Preflight, capsule: dict) -> dict:
    """给固定流水线吃的规划：绑定每个 role 的选中工具 + Adapter 指令。"""
    return {
        "capsule": pf.capsule,
        "status": pf.status,
        "output_contract": capsule.get("output_contract", {}),
        "roles": {
            name: {
                "selected": plan.selected,
                "status": plan.status,
                "requires": plan.requires,
                "directive": _directive_dict(plan.directive),
            }
            for name, plan in pf.roles.items()
        },
    }


def suggest_tools(role_name: str, missing: list[str], tools: dict) -> list[dict]:
    """列出同 modality、能补上缺失能力的工具及其所需 env。"""
    suggestions = []
    for name, tool in tools.items():
        if tool.get("modality") != role_name:
            continue
        flags = tool.get("provides", {}).get("flags", {})
        if any(flags.get(cap) is True for cap in missing):
            suggestions.append({"tool": name, "requires_env": tool.get("requires_env", [])})
    return suggestions


def raise_if_blocked(pf: Preflight, tools: dict) -> None:
    """任一 role 被 blocked 即抛 ValueError，附可执行的接入提示。"""
    if not pf.blocked:
        return
    lines = [f"胶囊 {pf.capsule!r} 无法运行：本地能力不满足以下角色。"]
    for role_name in pf.blocked:
        plan = pf.roles[role_name]
        lines.append(f"- 角色 '{role_name}' 缺能力: {', '.join(plan.missing) or '(无可用工具)'}")
        for sug in suggest_tools(role_name, plan.missing, tools):
            env = ", ".join(sug["requires_env"]) or "(无需 env)"
            lines.append(f"    请接入: {sug['tool']} ({env})")
    raise ValueError("\n".join(lines))


def write_artifacts(pf: Preflight, capsule: dict, out_dir: str | Path) -> tuple[Path, Path]:
    """落盘 preflight_report.json + execution_plan.json 到 session 目录。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "preflight_report.json"
    plan_path = out / "execution_plan.json"
    report_path.write_text(json.dumps(to_report(pf), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plan_path.write_text(
        json.dumps(to_execution_plan(pf, capsule), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_path, plan_path


def _load_capsule_by_name(name: str) -> dict:
    package_path = Path(__file__).resolve().parents[2] / "capsules" / f"{name}.capsule.zip"
    if not package_path.is_file():
        raise SystemExit(f"capsule package not found: {name}")

    with zipfile.ZipFile(package_path) as package:
        manifest = json.loads(package.read("manifest.json").decode("utf-8"))

    capsule = manifest.get("capsule", {})
    config = capsule.get("config", {})
    return {
        "name": capsule.get("name") or name,
        "roles": config.get("roles", {}),
        "output_contract": config.get("output_contract", {}),
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m src.capsule_preflight <capsule_name> [out_dir]", file=sys.stderr)
        return 2
    capsule = _load_capsule_by_name(argv[1])
    tools = load_all_tools()
    pf = run_preflight(capsule, tools, scan_available_env(dict(os.environ)))
    try:
        raise_if_blocked(pf, tools)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if len(argv) > 2:
        report_path, plan_path = write_artifacts(pf, capsule, argv[2])
        print(f"wrote {report_path}\nwrote {plan_path}")
    print(json.dumps(to_report(pf), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
