#!/usr/bin/env python3
"""Continuity QA for storyboard-level character and style consistency."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_LIB_DIR = _SKILL_DIR / "lib"
sys.path.insert(0, str(_LIB_DIR))
sys.path.insert(0, str(_SCRIPT_DIR))

from env_loader import load_video_agent_env  # noqa: E402

load_video_agent_env(_SKILL_DIR)

from src.contracts import normalize_storyboard_document  # noqa: E402


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def add_check(checks: list[dict], ok: bool, check_id: str, message: str, severity: str = "error", **extra: Any) -> None:
    checks.append({"id": check_id, "ok": ok, "severity": severity, "message": message, **extra})


def run_qa(storyboard_path: Path) -> dict:
    raw = read_json(storyboard_path)
    document = normalize_storyboard_document(raw)
    data = document.model_dump(mode="json")
    scenes = data.get("storyboard") or []
    contract = data.get("consistency_contract") or {}
    checks: list[dict] = []

    character_ids = {
        item.get("character_id")
        for item in contract.get("characters", [])
        if item.get("character_id")
    }
    scene_character_ids = {
        char_id
        for scene in scenes
        for char_id in scene.get("character_ids", [])
    }
    undefined_character_ids = sorted(scene_character_ids - character_ids)

    add_check(checks, bool(contract.get("long_chain_ready")), "long_chain_ready", "long-chain consistency contract is enabled")
    add_check(
        checks,
        not undefined_character_ids,
        "characters_defined",
        "all scene character_ids are defined in consistency_contract.characters",
        undefined_character_ids=undefined_character_ids,
    )

    missing_reference = [
        scene.get("scene_id")
        for scene in scenes
        if scene.get("character_ids") and not scene.get("reference_ids")
    ]
    add_check(
        checks,
        not missing_reference,
        "character_reference_present",
        "all character scenes include reference_ids",
        missing_scene_ids=missing_reference,
    )

    style_anchor_id = contract.get("style_anchor_id") or "main_style"
    style_mismatch = [
        scene.get("scene_id")
        for scene in scenes
        if scene.get("style_anchor", "main_style") != style_anchor_id
    ]
    add_check(
        checks,
        not style_mismatch,
        "style_anchor_uniform",
        "scene style_anchor matches consistency contract",
        severity="warning",
        expected=style_anchor_id,
        mismatch_scene_ids=style_mismatch,
    )

    missing_prompts = [
        scene.get("scene_id")
        for scene in scenes
        if not scene.get("image_prompt_chinese") and not scene.get("image_prompt_english")
    ]
    add_check(
        checks,
        not missing_prompts,
        "image_prompts_present",
        "all scenes include image prompts",
        missing_scene_ids=missing_prompts,
    )

    continuity_groups = contract.get("continuity_groups") or []
    add_check(
        checks,
        bool(continuity_groups),
        "continuity_groups_present",
        "continuity groups are recorded",
    )

    errors = [item for item in checks if not item["ok"] and item.get("severity") == "error"]
    return {
        "ok": not errors,
        "scope": "consistency_qa",
        "storyboard_path": str(storyboard_path),
        "scene_count": len(scenes),
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storyboard", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        report = run_qa(Path(args.storyboard).expanduser().resolve())
    except Exception as exc:
        report = {
            "ok": False,
            "scope": "consistency_qa",
            "storyboard_path": args.storyboard,
            "error": str(exc),
            "checks": [{"id": "qa_exception", "ok": False, "severity": "error", "message": "consistency QA failed to run"}],
        }

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")

    if args.json or args.output:
        print(text)
    else:
        print("consistency_qa:", "ok" if report["ok"] else "failed")
        for item in report.get("checks", []):
            status = "ok" if item["ok"] else item.get("severity", "error")
            print(f"- {status}: {item['id']} - {item['message']}")

    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
