#!/usr/bin/env python3
"""Convert QA failures into a non-destructive repair plan."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LIB_DIR = SKILL_DIR / "lib"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(LIB_DIR))

from output_guard import require_under_output, require_workspace_under_output  # noqa: E402


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def default_score_path(workspace: Path) -> Path:
    return workspace / "qa" / "video_quality_score.json"


def action_for_check(workspace: Path, issue: dict[str, Any], index: int) -> dict[str, Any]:
    check_id = str(issue.get("id") or "unknown")
    severity = str(issue.get("severity") or "warning")
    description = issue.get("description") or issue.get("detail") or issue.get("message") or ""
    base = {
        "id": f"repair_{index:02d}_{check_id}",
        "check_id": check_id,
        "severity": severity,
        "description": description,
        "workspace": str(workspace),
    }

    if check_id in {
        "manifest_present",
        "manifest_exists",
        "manifest_final_video",
        "manifest_prompt_artifacts",
        "prompt_index_exists",
        "manifest_prompt_paths_exist",
        "copywriting_present",
        "manifest_copywriting",
        "review_artifacts_present",
    }:
        return {
            **base,
            "type": "refresh_release_package",
            "command_hint": f"PYTHONPATH=lib python3.12 scripts/release_checkpoint.py --workspace {workspace}",
        }
    if check_id in {
        "edit_plan_exists",
        "edit_plan_validated",
        "edit_plan_schema",
        "timeline_duration_positive",
        "scene_map_present",
        "scene_map_covers_timeline",
        "clip_source_exists",
        "clip_start_monotonic",
        "clip_duration_positive",
        "scene_start_contiguous",
        "scene_duration_positive",
        "no_missing_scene_video_warnings",
    }:
        return {
            **base,
            "type": "rebuild_edit_plan_or_reassemble",
            "command_hint": (
                f"PYTHONPATH=lib python3.12 scripts/build_edit_plan.py --workspace {workspace} && "
                f"PYTHONPATH=lib python3.12 scripts/validate_edit_plan.py --workspace {workspace}"
            ),
        }
    if check_id in {
        "final_video_exists",
        "ffprobe",
        "ffprobe_ok",
        "duration_min",
        "duration_ok",
        "aspect_ratio",
        "aspect_ratio_ok",
        "resolution_ok",
    }:
        return {
            **base,
            "type": "reassemble_or_rerender",
            "command_hint": f"PYTHONPATH=lib python3.12 scripts/run_concat.py --workspace_dir {workspace}",
        }
    if check_id in {"expected_audio_present", "audio_expected", "audio_not_unexpected", "bgm_balance_reviewed", "audio_route_matches_capsule"}:
        return {
            **base,
            "type": "remix_audio",
            "command_hint": "Check storyboard audio paths, voice/BGM volume, then rerun concat or BGM mix.",
        }
    if check_id in {"subtitle_policy_ok", "subtitle_text_layout"}:
        return {
            **base,
            "type": "rerender_subtitles",
            "command_hint": "Adjust subtitle text/style/safe-area, then rerun subtitle rendering and concat.",
        }
    if check_id in {
        "no_black_frames",
        "no_freeze_events",
        "visual_scan_required",
        "main_subject_not_deformed",
        "talking_head_motion_continuity",
        "style_continuity",
        "no_generated_text_artifacts",
        "speech_visual_sync_reviewed",
        "voice_character_match",
    }:
        return {
            **base,
            "type": "regenerate_or_replace_scene",
            "requires_scene_target": True,
            "command_hint": f"PYTHONPATH=lib python3.12 scripts/run_scene.py --workspace_dir {workspace} --scene_id <scene_id> --video_prompt '<revised prompt>'",
        }
    if check_id in {"route_truthful", "capsule_contract_loaded", "structure_matches_capsule", "style_matches_capsule", "quality_rules_reviewed"}:
        return {
            **base,
            "type": "replan_route",
            "command_hint": "Inspect capsule contract and route policy before regenerating; do not patch this as a cosmetic edit.",
        }
    if check_id == "no_remote_or_secret_paths":
        return {
            **base,
            "type": "block_secret_or_remote_path",
            "command_hint": "Remove secret-looking values or remote/cloud URLs from manifests and rerun package checks.",
        }
    return {
        **base,
        "type": "manual_review",
        "command_hint": "Inspect the QA evidence and decide whether to rerun a scene, reassemble, or block delivery.",
    }


def dedupe_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        key = str(issue.get("id") or issue.get("check_id") or issue)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


def build_repair_plan(workspace: str | Path, *, score_path: str | Path | None = None) -> dict[str, Any]:
    workspace_path = require_workspace_under_output(workspace)
    score_file = require_under_output(score_path, "--score") if score_path else default_score_path(workspace_path)
    score = read_json(score_file, {})
    source_status = score.get("status", "")
    blockers = score.get("blockers") if isinstance(score.get("blockers"), list) else []
    manual_review = score.get("manual_review_required") if isinstance(score.get("manual_review_required"), list) else []
    warnings = score.get("warnings") if isinstance(score.get("warnings"), list) else []

    if not score:
        local_qa_file = workspace_path / "qa" / "local_video_qa.json"
        local_qa = read_json(local_qa_file, {})
        checks = local_qa.get("checks") if isinstance(local_qa.get("checks"), list) else []
        blockers = [
            {
                "id": item.get("id"),
                "severity": item.get("severity", "error"),
                "description": item.get("message") or item.get("detail") or item.get("id", ""),
            }
            for item in checks
            if isinstance(item, dict) and not item.get("ok") and item.get("severity", "error") != "warning"
        ]
        warnings = [
            {
                "id": item.get("id"),
                "severity": item.get("severity", "warning"),
                "description": item.get("message") or item.get("detail") or item.get("id", ""),
            }
            for item in checks
            if isinstance(item, dict) and not item.get("ok") and item.get("severity") == "warning"
        ]
        source_status = "local_qa_failed" if blockers else ("local_qa_pass" if local_qa else "")
        score_file = local_qa_file if local_qa else score_file

    edit_plan_validation_file = workspace_path / "qa" / "edit_plan_validation.json"
    edit_plan_validation = read_json(edit_plan_validation_file, {})
    if edit_plan_validation and not edit_plan_validation.get("ok"):
        source_status = source_status or edit_plan_validation.get("status", "")
        edit_plan_blockers = edit_plan_validation.get("blockers")
        edit_plan_warnings = edit_plan_validation.get("warnings")
        if isinstance(edit_plan_blockers, list):
            blockers.extend(edit_plan_blockers)
        if isinstance(edit_plan_warnings, list):
            warnings.extend(edit_plan_warnings)

    repair_candidates = dedupe_issues([*blockers, *manual_review])
    actions = [action_for_check(workspace_path, issue, index) for index, issue in enumerate(repair_candidates, start=1)]

    return {
        "schema": "capsule_cinema.repair_plan.v1",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "workspace": str(workspace_path),
        "source_score": str(score_file),
        "source_status": source_status,
        "blocking": bool(actions),
        "status": "needs_repair" if actions else "no_blocking_repairs",
        "actions": actions,
        "warning_count": len(warnings),
        "warnings_deferred": warnings if actions else [],
    }


def write_repair_plan(
    workspace: str | Path,
    *,
    score_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> Path:
    workspace_path = require_workspace_under_output(workspace)
    output = require_under_output(output_path, "--output") if output_path else workspace_path / "qa" / "repair_plan.json"
    plan = build_repair_plan(workspace_path, score_path=score_path)
    write_json(output, plan)
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", "--run-dir", dest="workspace", required=True, help="Workspace under output/")
    parser.add_argument("--score", default="", help="Optional video_quality_score.json path")
    parser.add_argument("--output", default="", help="Output repair_plan.json path under output/")
    parser.add_argument("--json", action="store_true", help="Print repair plan JSON")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        workspace = require_workspace_under_output(args.workspace)
        output = write_repair_plan(
            workspace,
            score_path=args.score or None,
            output_path=args.output or None,
        )
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from exc
    if args.json:
        print(json.dumps(read_json(output, {}), ensure_ascii=False, indent=2))
    else:
        print(output)


if __name__ == "__main__":
    main()
