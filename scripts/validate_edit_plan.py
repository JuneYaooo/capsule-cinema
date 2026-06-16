#!/usr/bin/env python3
"""Validate a Capsule Cinema EditPlan as a local timeline contract."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
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


DEFAULT_TOLERANCE_SECONDS = 0.35


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


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def resolve_existing_local_path(workspace: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = workspace / path
    path = path.resolve(strict=False)
    try:
        require_under_output(path, "edit plan source path")
    except ValueError:
        return None
    return path if path.exists() else None


def source_path_error(workspace: Path, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "missing path"
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = workspace / path
    path = path.resolve(strict=False)
    try:
        require_under_output(path, "edit plan source path")
    except ValueError as exc:
        return str(exc)
    if not path.exists():
        return f"path does not exist: {path}"
    return ""


def probe_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not path.exists():
        return 0.0
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return 0.0
    try:
        return max(float(proc.stdout.strip()), 0.0)
    except ValueError:
        return 0.0


def add_check(
    checks: list[dict[str, Any]],
    ok: bool,
    check_id: str,
    message: str,
    *,
    severity: str = "error",
    **extra: Any,
) -> None:
    checks.append({"id": check_id, "ok": ok, "severity": severity, "message": message, **extra})


def sorted_track_clips(plan: dict[str, Any], track_type: str) -> list[dict[str, Any]]:
    timeline = plan.get("timeline") if isinstance(plan.get("timeline"), dict) else {}
    tracks = timeline.get("tracks") if isinstance(timeline.get("tracks"), list) else []
    clips: list[dict[str, Any]] = []
    for track in tracks:
        if not isinstance(track, dict) or track.get("type") != track_type:
            continue
        track_clips = track.get("clips") if isinstance(track.get("clips"), list) else []
        clips.extend(item for item in track_clips if isinstance(item, dict))
    return sorted(clips, key=lambda item: (as_float(item.get("start")), str(item.get("id") or "")))


def validate_clip_paths(workspace: Path, clips: list[dict[str, Any]], checks: list[dict[str, Any]]) -> None:
    for clip in clips:
        clip_id = str(clip.get("id") or "unknown")
        source_path = clip.get("source_path")
        error = source_path_error(workspace, source_path)
        add_check(
            checks,
            not error,
            "clip_source_exists",
            "clip source exists and stays under output/",
            clip_id=clip_id,
            source_path=str(source_path or ""),
            detail=error,
        )


def validate_monotonic_clips(clips: list[dict[str, Any]], checks: list[dict[str, Any]], track_type: str) -> None:
    previous_start = -1.0
    for clip in clips:
        clip_id = str(clip.get("id") or "unknown")
        start = as_float(clip.get("start"), -1.0)
        duration = as_float(clip.get("duration"), -1.0)
        add_check(
            checks,
            start >= previous_start and start >= 0,
            "clip_start_monotonic",
            f"{track_type} clip starts are monotonic",
            clip_id=clip_id,
            start=start,
            previous_start=previous_start,
        )
        add_check(
            checks,
            duration > 0,
            "clip_duration_positive",
            f"{track_type} clip duration is positive",
            clip_id=clip_id,
            duration=duration,
        )
        previous_start = max(previous_start, start)


def validate_probe_durations(
    workspace: Path,
    clips: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    *,
    tolerance_seconds: float,
) -> None:
    if not shutil.which("ffprobe"):
        add_check(checks, False, "ffprobe_available", "ffprobe is available for media duration checks", severity="warning")
        return

    for clip in clips:
        path = resolve_existing_local_path(workspace, clip.get("source_path"))
        if not path:
            continue
        recorded = as_float(clip.get("source_duration"), 0.0)
        actual = probe_duration(path)
        if recorded <= 0 or actual <= 0:
            add_check(
                checks,
                actual > 0,
                "clip_probe_duration_available",
                "clip source duration can be probed",
                clip_id=clip.get("id"),
                source_path=str(path),
                actual_duration=round(actual, 3),
                severity="warning",
            )
            continue
        add_check(
            checks,
            abs(actual - recorded) <= tolerance_seconds,
            "clip_source_duration_matches_probe",
            "recorded source duration matches ffprobe",
            clip_id=clip.get("id"),
            source_path=str(path),
            recorded_duration=round(recorded, 3),
            actual_duration=round(actual, 3),
            tolerance_seconds=tolerance_seconds,
            severity="warning",
        )


def validate_scene_map(plan: dict[str, Any], checks: list[dict[str, Any]], *, tolerance_seconds: float) -> None:
    scene_map = plan.get("scene_map") if isinstance(plan.get("scene_map"), list) else []
    timeline = plan.get("timeline") if isinstance(plan.get("timeline"), dict) else {}
    timeline_duration = as_float(timeline.get("duration"), 0.0)
    add_check(checks, bool(scene_map), "scene_map_present", "edit plan has a scene_map")

    previous_end = 0.0
    for scene in scene_map:
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get("scene_id")
        start = as_float(scene.get("start"), -1.0)
        duration = as_float(scene.get("duration"), -1.0)
        add_check(
            checks,
            start >= previous_end - tolerance_seconds and start >= 0,
            "scene_start_contiguous",
            "scene starts are contiguous and monotonic",
            scene_id=scene_id,
            start=start,
            previous_end=round(previous_end, 3),
            tolerance_seconds=tolerance_seconds,
        )
        add_check(
            checks,
            duration > 0,
            "scene_duration_positive",
            "scene duration is positive",
            scene_id=scene_id,
            duration=duration,
        )
        previous_end = max(previous_end, start + max(duration, 0.0))

    if scene_map:
        add_check(
            checks,
            abs(previous_end - timeline_duration) <= tolerance_seconds,
            "scene_map_covers_timeline",
            "scene_map duration covers the timeline duration",
            scene_end=round(previous_end, 3),
            timeline_duration=round(timeline_duration, 3),
            tolerance_seconds=tolerance_seconds,
        )


def validate_edit_plan(
    workspace: str | Path,
    *,
    edit_plan_path: str | Path | None = None,
    tolerance_seconds: float = DEFAULT_TOLERANCE_SECONDS,
) -> dict[str, Any]:
    workspace_path = require_workspace_under_output(workspace)
    edit_plan_file = Path(edit_plan_path).expanduser() if edit_plan_path else workspace_path / "work" / "edit_plan.json"
    if not edit_plan_file.is_absolute():
        edit_plan_file = workspace_path / edit_plan_file
    edit_plan_file = require_under_output(edit_plan_file, "--edit-plan")

    plan = read_json(edit_plan_file, {})
    checks: list[dict[str, Any]] = []
    add_check(checks, bool(plan), "edit_plan_exists", "edit_plan.json exists and is valid JSON", path=str(edit_plan_file))
    if not plan:
        return {
            "schema": "capsule_cinema.edit_plan_validation.v1",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "workspace": str(workspace_path),
            "edit_plan": str(edit_plan_file),
            "ok": False,
            "status": "blocked",
            "checks": checks,
            "blockers": [item for item in checks if not item["ok"] and item.get("severity") == "error"],
            "warnings": [item for item in checks if not item["ok"] and item.get("severity") == "warning"],
        }

    add_check(
        checks,
        plan.get("schema") == "capsule_cinema.edit_plan.v1",
        "edit_plan_schema",
        "edit plan schema is supported",
        actual=plan.get("schema"),
    )

    timeline = plan.get("timeline") if isinstance(plan.get("timeline"), dict) else {}
    timeline_duration = as_float(timeline.get("duration"), 0.0)
    add_check(checks, timeline_duration > 0, "timeline_duration_positive", "timeline duration is positive", duration=timeline_duration)

    video_clips = sorted_track_clips(plan, "video")
    audio_clips = sorted_track_clips(plan, "audio")
    caption_clips = sorted_track_clips(plan, "caption")

    add_check(checks, bool(video_clips), "video_track_has_clips", "video track has at least one clip")
    validate_clip_paths(workspace_path, video_clips + audio_clips, checks)
    validate_monotonic_clips(video_clips, checks, "video")
    validate_monotonic_clips(audio_clips, checks, "audio")
    validate_monotonic_clips(caption_clips, checks, "caption")
    validate_probe_durations(workspace_path, video_clips + audio_clips, checks, tolerance_seconds=tolerance_seconds)
    validate_scene_map(plan, checks, tolerance_seconds=tolerance_seconds)

    plan_warnings = plan.get("warnings") if isinstance(plan.get("warnings"), list) else []
    missing_video_warnings = [item for item in plan_warnings if isinstance(item, dict) and item.get("id") == "missing_scene_video"]
    add_check(
        checks,
        not missing_video_warnings,
        "no_missing_scene_video_warnings",
        "edit plan has no missing scene video warnings",
        missing_count=len(missing_video_warnings),
    )

    blockers = [item for item in checks if not item["ok"] and item.get("severity") == "error"]
    warnings = [item for item in checks if not item["ok"] and item.get("severity") == "warning"]
    return {
        "schema": "capsule_cinema.edit_plan_validation.v1",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "workspace": str(workspace_path),
        "edit_plan": str(edit_plan_file),
        "ok": not blockers,
        "status": "pass" if not blockers else "blocked",
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }


def write_edit_plan_validation(
    workspace: str | Path,
    *,
    edit_plan_path: str | Path | None = None,
    output_path: str | Path | None = None,
    tolerance_seconds: float = DEFAULT_TOLERANCE_SECONDS,
) -> Path:
    workspace_path = require_workspace_under_output(workspace)
    output = require_under_output(output_path, "--output") if output_path else workspace_path / "qa" / "edit_plan_validation.json"
    report = validate_edit_plan(workspace_path, edit_plan_path=edit_plan_path, tolerance_seconds=tolerance_seconds)
    write_json(output, report)
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", "--run-dir", dest="workspace", required=True, help="Workspace under output/")
    parser.add_argument("--edit-plan", default="", help="Optional edit_plan.json path")
    parser.add_argument("--output", default="", help="Output validation report path under output/")
    parser.add_argument("--tolerance-seconds", type=float, default=DEFAULT_TOLERANCE_SECONDS)
    parser.add_argument("--json", action="store_true", help="Print validation JSON")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        workspace = require_workspace_under_output(args.workspace)
        output = write_edit_plan_validation(
            workspace,
            edit_plan_path=args.edit_plan or None,
            output_path=args.output or None,
            tolerance_seconds=args.tolerance_seconds,
        )
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from exc

    report = read_json(output, {})
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(output)
    raise SystemExit(0 if report.get("ok") else 1)


if __name__ == "__main__":
    main()
