#!/usr/bin/env python3
"""Canonical dispatcher for active local-script capsule packages."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
LIB_DIR = ROOT / "lib"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(LIB_DIR))

from capsule_runtime import load_capsule  # noqa: E402
from src.capsule_gate_runner import load_gate_bindings, run_capsule_gates  # noqa: E402


def read_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    target = Path(path).expanduser()
    if not target.exists():
        raise SystemExit(f"params not found: {target}")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"params must be valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("params must be a JSON object")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merged_params(user_params: dict[str, Any], capsule: dict[str, Any]) -> dict[str, Any]:
    config = capsule.get("config") if isinstance(capsule.get("config"), dict) else {}
    user_config = user_params.get("config") if isinstance(user_params.get("config"), dict) else {}
    merged = dict(user_params)
    merged["config"] = {**config, **user_config}
    for key in ("aspect_ratio", "target_duration", "opening_style"):
        if key not in merged and key in merged["config"]:
            merged[key] = merged["config"][key]
    merged.setdefault("capsule_name", capsule.get("name") or "")
    merged.setdefault("capsule_execution_mode", capsule.get("execution_mode") or "")
    return merged


def augment_manifest(output_dir: Path, capsule: dict[str, Any], local_script: Path) -> None:
    manifest_path = output_dir / "artifact_manifest.json"
    if not manifest_path.exists():
        return
    manifest = read_json(manifest_path)
    manifest["capsule"] = capsule.get("name") or ""
    manifest["capsule_name"] = capsule.get("name") or ""
    manifest["capsule_execution_mode"] = "local_script"
    manifest["execution_mode"] = "local_script"
    manifest["execution_script"] = str(local_script)
    manifest["capsule_local_script_path"] = str(local_script)
    manifest["capsule_dispatcher"] = str((SCRIPT_DIR / "run_capsule.py").resolve())
    toolchain = manifest.get("toolchain") if isinstance(manifest.get("toolchain"), dict) else {}
    toolchain["execution_script"] = str(local_script)
    toolchain["capsule_dispatcher"] = str((SCRIPT_DIR / "run_capsule.py").resolve())
    manifest["toolchain"] = toolchain
    write_json(manifest_path, manifest)


def _has_release_gate_bindings(capsule: dict[str, Any]) -> bool:
    capsule_dir = str(capsule.get("capsule_dir") or "").strip()
    if not capsule_dir:
        return False
    return any(str(gate.get("phase") or "") == "release" for gate in load_gate_bindings(capsule_dir))


def _append_manifest_artifact(manifest: dict[str, Any], *, category: str, path: Path, title: str) -> None:
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), list) else []
    artifact_path = str(path.resolve())
    artifacts = [
        item
        for item in artifacts
        if not (isinstance(item, dict) and item.get("category") == category and item.get("path") == artifact_path)
    ]
    artifacts.append({"category": category, "path": artifact_path, "title": title})
    manifest["artifacts"] = artifacts


def write_release_gate_report(output_dir: Path, capsule: dict[str, Any]) -> dict[str, Any] | None:
    if not _has_release_gate_bindings(capsule):
        return None
    manifest_path = output_dir / "artifact_manifest.json"
    manifest = read_json(manifest_path)
    report = run_capsule_gates(
        capsule.get("capsule_dir") or "",
        "release",
        manifest=manifest,
        release=manifest,
    )
    report_path = output_dir / "qa" / "capsule_gate_report.json"
    write_json(report_path, report)
    _append_manifest_artifact(
        manifest,
        category="capsule_gate_report",
        path=report_path,
        title="Capsule gate report",
    )
    write_json(manifest_path, manifest)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capsule", required=True, help="Active capsule package name or path.")
    parser.add_argument("--topic", required=True, help="Run topic passed to the capsule local script.")
    parser.add_argument("--params", default="", help="User params JSON; merged copy is written under output-dir.")
    parser.add_argument("--output-dir", required=True, help="Run output directory.")
    parser.add_argument("--dry-run", action="store_true", help="Forward --dry-run to the capsule local script.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    capsule = load_capsule(args.capsule)
    if capsule.get("execution_mode") != "local_script":
        raise SystemExit(
            f"Capsule '{capsule.get('name')}' is execution_mode={capsule.get('execution_mode')}; "
            "use scripts/run_video.py for preset capsules."
        )

    local_script_text = str(capsule.get("local_script_path") or "").strip()
    if not local_script_text:
        raise SystemExit(f"Capsule '{capsule.get('name')}' is missing entrypoints.local_script")
    local_script = Path(local_script_text).expanduser().resolve()
    if not local_script.is_file():
        raise SystemExit(f"Capsule local script not found: {local_script}")

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    params = merged_params(read_json(args.params), capsule)
    merged_params_path = output_dir / "inputs" / "params.merged.json"
    write_json(merged_params_path, params)

    command = [
        sys.executable,
        str(local_script),
        "--topic",
        args.topic,
        "--params",
        str(merged_params_path),
        "--output-dir",
        str(output_dir),
    ]
    if args.dry_run:
        command.append("--dry-run")

    result = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    dispatch = {
        "schema": "capsule_cinema.local_script_dispatch.v1",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ok": result.returncode == 0,
        "capsule": capsule.get("name") or "",
        "execution_mode": "local_script",
        "local_script_path": str(local_script),
        "dispatcher": str((SCRIPT_DIR / "run_capsule.py").resolve()),
        "topic": args.topic,
        "params_path": str(merged_params_path),
        "output_dir": str(output_dir),
        "return_code": result.returncode,
    }
    write_json(output_dir / "reports" / "capsule_dispatch.json", dispatch)

    if result.returncode != 0:
        return result.returncode

    manifest_path = output_dir / "artifact_manifest.json"
    if not manifest_path.exists():
        dispatch["ok"] = False
        dispatch["error"] = "artifact_manifest_missing"
        write_json(output_dir / "reports" / "capsule_dispatch.json", dispatch)
        return 4

    augment_manifest(output_dir, capsule, local_script)
    gate_report = write_release_gate_report(output_dir, capsule)
    if gate_report is not None and not gate_report.get("ok"):
        dispatch["ok"] = False
        dispatch["error"] = "capsule_release_gates_blocked"
        dispatch["gate_report_path"] = str((output_dir / "qa" / "capsule_gate_report.json").resolve())
        dispatch["blocked_gates"] = gate_report.get("blockers", [])
        write_json(output_dir / "reports" / "capsule_dispatch.json", dispatch)
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
