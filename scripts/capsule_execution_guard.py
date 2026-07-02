#!/usr/bin/env python3
"""Execution-path checks for capsule release artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
LIB_DIR = ROOT / "lib"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(LIB_DIR))

from capsule_runtime import load_capsule  # noqa: E402


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def manifest_capsule_name(manifest: dict[str, Any], fallback: str = "") -> str:
    return _first_text(
        manifest.get("capsule_name"),
        manifest.get("capsule"),
        (manifest.get("capsule_info") or {}).get("name") if isinstance(manifest.get("capsule_info"), dict) else "",
        fallback,
    )


def manifest_execution_script(manifest: dict[str, Any]) -> str:
    toolchain = manifest.get("toolchain") if isinstance(manifest.get("toolchain"), dict) else {}
    return _first_text(
        manifest.get("execution_script"),
        manifest.get("local_script_path"),
        manifest.get("capsule_local_script_path"),
        toolchain.get("execution_script"),
        toolchain.get("local_script_path"),
    )


def _resolved(path_value: str) -> Path:
    return Path(path_value).expanduser().resolve(strict=False)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _script_allowed(script_path: Path, capsule: dict[str, Any], manifest: dict[str, Any]) -> bool:
    local_script = _resolved(str(capsule.get("local_script_path") or ""))
    dispatcher = (SCRIPT_DIR / "run_capsule.py").resolve(strict=False)
    if script_path == local_script:
        return True
    if script_path == dispatcher:
        recorded_local = _first_text(
            manifest.get("capsule_local_script_path"),
            (manifest.get("toolchain") or {}).get("execution_script")
            if isinstance(manifest.get("toolchain"), dict)
            else "",
        )
        return bool(recorded_local and _resolved(recorded_local) == local_script)
    capsule_scripts = _resolved(str(capsule.get("capsule_dir") or "")) / "scripts"
    return _is_relative_to(script_path, capsule_scripts)


def local_script_bypass_issue(
    manifest: dict[str, Any],
    *,
    capsule_name: str = "",
    capsule: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    name = manifest_capsule_name(manifest, capsule_name)
    if not name:
        return None
    try:
        capsule = capsule or load_capsule(name)
    except SystemExit:
        return None
    if capsule.get("execution_mode") != "local_script":
        return None
    script_text = manifest_execution_script(manifest)
    if not script_text:
        return {
            "id": "local_script_capsule_bypassed",
            "category": "capsule_execution",
            "ok": False,
            "severity": "blocker",
            "description": "Local-script capsule release does not record the capsule execution script.",
            "detail": f"capsule={name}; expected {capsule.get('local_script_path')}",
        }
    script_path = _resolved(script_text)
    if _script_allowed(script_path, capsule, manifest):
        return None
    return {
        "id": "local_script_capsule_bypassed",
        "category": "capsule_execution",
        "ok": False,
        "severity": "blocker",
        "description": "Local-script capsule release was produced by an unregistered script.",
        "detail": f"capsule={name}; script={script_path}; expected={capsule.get('local_script_path')}",
    }


def issue_to_quality_check(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": issue["id"],
        "category": issue.get("category", "capsule_execution"),
        "label": "胶囊执行路径",
        "ok": False,
        "points": 0,
        "earned": 0,
        "severity": issue.get("severity", "blocker"),
        "common_issue": issue["id"],
        "description": issue.get("description", ""),
        "detail": issue.get("detail", ""),
    }


def issue_to_release_check(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": issue["id"],
        "ok": False,
        "severity": issue.get("severity", "blocker"),
        "detail": issue.get("detail", ""),
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: capsule_execution_guard.py <artifact_manifest.json>")
    manifest_path = Path(sys.argv[1]).expanduser()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    issue = local_script_bypass_issue(manifest)
    print(json.dumps(issue or {"ok": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
