#!/usr/bin/env python3
"""Validate and optionally normalize a Capsule Cinema storyboard.json."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_LIB_DIR = _SKILL_DIR / "lib"
sys.path.insert(0, str(_LIB_DIR))
sys.path.insert(0, str(_SCRIPT_DIR))

from env_loader import load_video_agent_env  # noqa: E402

load_video_agent_env(_SKILL_DIR)

from src.contracts import normalize_storyboard_document  # noqa: E402


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("storyboard root must be a JSON object")
    return data


def build_report(path: Path, normalized: dict) -> dict:
    scenes = normalized.get("storyboard") or []
    contract = normalized.get("consistency_contract") or {}
    checks = []

    def add(ok: bool, check_id: str, message: str, severity: str = "error", **extra):
        checks.append({"ok": ok, "id": check_id, "message": message, "severity": severity, **extra})

    add(bool(scenes), "scenes_present", "storyboard contains scenes", count=len(scenes))
    add(bool(contract), "contract_present", "consistency_contract exists")
    add(bool(contract.get("long_chain_ready")), "long_chain_ready", "long-chain continuity flag is enabled")
    add(bool(contract.get("style_anchor_id")), "style_anchor", "style anchor exists", severity="warning")

    missing_continuity = [
        scene.get("scene_id")
        for scene in scenes
        if not scene.get("chapter_id") or not scene.get("continuity_group") or not scene.get("style_anchor")
    ]
    add(
        not missing_continuity,
        "scene_continuity_fields",
        "all scenes include chapter_id, continuity_group, and style_anchor",
        missing_scene_ids=missing_continuity,
    )

    reference_mismatch = [
        scene.get("scene_id")
        for scene in scenes
        if scene.get("character_ids") and not scene.get("reference_ids")
    ]
    add(
        not reference_mismatch,
        "character_reference_ids",
        "scenes with character_ids also carry reference_ids",
        missing_scene_ids=reference_mismatch,
    )

    errors = [item for item in checks if not item["ok"] and item.get("severity") == "error"]
    return {
        "ok": not errors,
        "scope": "storyboard_contract",
        "storyboard_path": str(path),
        "scene_count": len(scenes),
        "contract": {
            "style_anchor_id": contract.get("style_anchor_id"),
            "character_count": len(contract.get("characters") or []),
            "chapter_count": len(contract.get("chapters") or []),
            "continuity_group_count": len(contract.get("continuity_groups") or []),
        },
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storyboard", required=True, help="Path to storyboard.json")
    parser.add_argument("--write-normalized", action="store_true", help="Write normalized contract fields back to storyboard.json")
    parser.add_argument("--output", default="", help="Optional report output path")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args()

    path = Path(args.storyboard).expanduser().resolve()
    try:
        data = load_json(path)
        document = normalize_storyboard_document(data)
        normalized = document.model_dump(mode="json")
    except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        report = {
            "ok": False,
            "scope": "storyboard_contract",
            "storyboard_path": str(path),
            "error": str(exc),
            "checks": [{"ok": False, "id": "parse_or_validate", "message": "storyboard could not be parsed or normalized", "severity": "error"}],
        }
    else:
        report = build_report(path, normalized)
        if args.write_normalized:
            path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")

    if args.json or args.output:
        print(text)
    else:
        print("storyboard_contract:", "ok" if report["ok"] else "failed")
        for item in report.get("checks", []):
            status = "ok" if item["ok"] else item.get("severity", "error")
            print(f"- {status}: {item['id']} - {item['message']}")

    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
