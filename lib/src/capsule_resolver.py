"""Capability-based tool resolver (L4).

Pure matching logic: given a capsule role, the tool capability library, and the
set of locally available env keys, pick an ordered candidate chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@dataclass
class RoleResolution:
    selected: str | None
    fallback: list[str] = field(default_factory=list)
    status: str = "ok"  # ok | substituted | blocked
    missing: list[str] = field(default_factory=list)


def _provides_flags(tool: dict) -> dict:
    return tool.get("provides", {}).get("flags", {})


def _provides_enums(tool: dict) -> dict:
    return tool.get("provides", {}).get("enums", {})


def _provides_limits(tool: dict) -> dict:
    return tool.get("provides", {}).get("limits", {})


def _env_available(tool: dict, available_env: set[str]) -> bool:
    required_groups: list[list[str]] = []
    if tool.get("requires_env"):
        required_groups.append(list(tool.get("requires_env") or []))
    required_groups.extend(list(group) for group in tool.get("requires_env_any", []) or [])
    if not required_groups:
        return True
    return any(all(key in available_env for key in group) for group in required_groups)


def _satisfies(tool: dict, role: dict) -> bool:
    flags = _provides_flags(tool)
    if not all(flags.get(flag) is True for flag in role.get("requires", [])):
        return False
    enums = _provides_enums(tool)
    if not all(enums.get(key) == val for key, val in role.get("requires_enums", {}).items()):
        return False
    limits = _provides_limits(tool)
    if not all(val in limits.get(key, []) for key, val in role.get("requires_limits", {}).items()):
        return False
    if set(tool.get("tags", [])) & set(role.get("forbids", [])):
        return False
    return True


def _score(tool: dict, role: dict) -> int:
    tags = set(tool.get("tags", []))
    enums = _provides_enums(tool)
    score = sum(1 for tag in role.get("prefers", []) if tag in tags)
    score += sum(1 for key, val in role.get("prefers_enums", {}).items() if enums.get(key) == val)
    return score


_COST_RANK = {"low": 0, "medium": 1, "high": 2}


def _cost_rank(tool: dict) -> int:
    return _COST_RANK.get(tool.get("cost_tier"), 1)


def _missing_requirements(role: dict, pool: list[dict]) -> list[str]:
    missing: list[str] = []
    for flag in role.get("requires", []):
        if not any(_provides_flags(t).get(flag) is True for t in pool):
            missing.append(flag)
    for key, val in role.get("requires_enums", {}).items():
        if not any(_provides_enums(t).get(key) == val for t in pool):
            missing.append(key)
    for key, val in role.get("requires_limits", {}).items():
        if not any(val in _provides_limits(t).get(key, []) for t in pool):
            missing.append(key)
    return missing


def resolve_role(role: dict, tools: dict, available_env: set[str]) -> RoleResolution:
    modality = role.get("modality")
    pool = [
        tool
        for tool in tools.values()
        if tool.get("modality") == modality and _env_available(tool, available_env)
    ]
    candidates = [
        name
        for name, tool in tools.items()
        if tool.get("modality") == modality
        and _env_available(tool, available_env)
        and _satisfies(tool, role)
    ]

    if not candidates:
        return RoleResolution(
            selected=None,
            status="blocked",
            missing=_missing_requirements(role, pool),
        )

    validated_with = role.get("validated_with")
    ordered = sorted(
        candidates,
        key=lambda name: (
            -_score(tools[name], role),
            0 if name == validated_with else 1,
            _cost_rank(tools[name]),
        ),
    )

    selected = ordered[0]
    status = "substituted" if validated_with and selected != validated_with else "ok"

    return RoleResolution(selected=selected, fallback=ordered[1:], status=status)


def load_tool_capabilities(path: str | Path | None = None) -> dict:
    """Load the L2 tool capability library, returning the ``tools`` mapping."""
    if path is None:
        from src.config_registry import load_tool_capabilities as load_merged_capabilities

        return load_merged_capabilities()
    target = Path(path) if path else _CONFIG_DIR / "tool_capabilities.yaml"
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return data.get("tools", {})


def load_voice_catalog(path: str | Path | None = None) -> dict:
    """Load the voice catalog (each voice is a modality=voice tool entry)."""
    target = Path(path) if path else _CONFIG_DIR / "voice_catalog.yaml"
    if not target.exists():
        return {}
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return data.get("voices", {})


def load_all_tools() -> dict:
    """Merge L2 tools and the voice catalog into one capability pool."""
    tools = dict(load_tool_capabilities())
    tools.update(load_voice_catalog())
    return tools


# 运行时视频引擎短名 ↔ 工具类名（替代旧 video_engines.yaml 的静态顺序）
_VIDEO_ENGINE_SHORTNAME = {
    "Seedance20VideoGeneratorTool": "seedance2.0",
}


def resolve_video_fallback(
    current_engine: str,
    available_env: set[str],
    tools: dict | None = None,
    required_flags: list[str] | None = None,
) -> list[str]:
    """按本地可用性动态算视频回退链（运行时短名），当前引擎置首。

    取代 video_generation_config.VIDEO_ENGINE_FALLBACK_ORDER 的全局静态顺序。
    """
    tools = tools if tools is not None else load_all_tools()
    res = resolve_role(
        {"modality": "video", "requires": required_flags or ["image_to_video"]},
        tools,
        available_env,
    )

    chain: list[str] = []
    if res.selected:
        for name in [res.selected, *res.fallback]:
            short = _VIDEO_ENGINE_SHORTNAME.get(name)
            if short and short not in chain:
                chain.append(short)

    if current_engine in chain:
        chain.remove(current_engine)
    chain.insert(0, current_engine)
    return chain
