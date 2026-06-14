#!/usr/bin/env python3
"""Build a deterministic edit plan for a Capsule Cinema workspace."""

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
from src.contracts import get_storyboard_scenes, scene_display_id, scene_order  # noqa: E402


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


def resolve_workspace_path(workspace: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = workspace / path
    return path.resolve(strict=False)


def first_existing(candidates: list[Path | None]) -> Path | None:
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return None


def sorted_glob(root: Path, pattern: str) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.glob(pattern))


def find_scene_media(workspace: Path, scene: dict[str, Any], display_id: int, kind: str) -> Path | None:
    zero_id = max(display_id - 1, 0)
    if kind == "video":
        explicit = resolve_workspace_path(workspace, scene.get("video_path"))
        candidates: list[Path | None] = [
            explicit,
            *sorted_glob(workspace / "work" / "videos" / "subtitled", f"scene_{zero_id:02d}_*.mp4"),
            *sorted_glob(workspace / "work" / "videos", f"scene_{display_id:02d}_v*.mp4"),
            *sorted_glob(workspace / "work" / "videos", f"scene_{zero_id:02d}*.mp4"),
            *sorted_glob(workspace / "work" / "videos" / "fallback_videos", f"scene_{zero_id:02d}*.mp4"),
        ]
        return first_existing(candidates)
    if kind == "audio":
        explicit = resolve_workspace_path(workspace, scene.get("audio_path"))
        return first_existing(
            [
                explicit,
                workspace / "work" / "audios" / f"scene_{zero_id:02d}.mp3",
                workspace / "work" / "audios" / f"scene_{display_id:02d}.mp3",
                workspace / "work" / "audios" / f"scene_{zero_id:02d}.wav",
                workspace / "work" / "audios" / f"scene_{display_id:02d}.wav",
            ]
        )
    if kind == "image":
        explicit = resolve_workspace_path(workspace, scene.get("image_path"))
        candidates = [
            explicit,
            *sorted_glob(workspace / "work" / "images", f"scene_{display_id:02d}_v*.*"),
            *sorted_glob(workspace / "work" / "images", f"scene_{zero_id:02d}.*"),
            *sorted_glob(workspace / "work" / "images", f"scene_{display_id:02d}.*"),
        ]
        return first_existing(candidates)
    raise ValueError(f"unsupported media kind: {kind}")


def probe_duration(path: Path | None) -> float:
    if not path or not path.exists() or not shutil.which("ffprobe"):
        return 0.0
    proc = subprocess.run(
        [
            "ffprobe",
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


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_edit_plan(workspace: str | Path, *, storyboard_path: str | Path | None = None) -> dict[str, Any]:
    workspace_path = require_workspace_under_output(workspace)
    storyboard = Path(storyboard_path).expanduser() if storyboard_path else workspace_path / "storyboard.json"
    if not storyboard.is_absolute():
        storyboard = workspace_path / storyboard
    storyboard = storyboard.resolve(strict=False)
    data = read_json(storyboard, {})
    scenes = sorted(
        enumerate(get_storyboard_scenes(data), start=1),
        key=lambda item: scene_order(item[1], item[0]),
    )

    video_clips: list[dict[str, Any]] = []
    audio_clips: list[dict[str, Any]] = []
    caption_clips: list[dict[str, Any]] = []
    scene_map: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    cursor = 0.0

    for fallback, scene in scenes:
        if not isinstance(scene, dict):
            continue
        display_id = scene_display_id(scene, fallback)
        planned_duration = as_float(scene.get("duration"), 5.0) or 5.0
        video_path = find_scene_media(workspace_path, scene, display_id, "video")
        audio_path = find_scene_media(workspace_path, scene, display_id, "audio")
        image_path = find_scene_media(workspace_path, scene, display_id, "image")
        video_duration = probe_duration(video_path)
        audio_duration = probe_duration(audio_path)
        duration = max(planned_duration, video_duration, audio_duration)
        clip_id = f"scene_{display_id:02d}"

        scene_entry = {
            "scene_id": display_id,
            "clip_id": clip_id,
            "start": round(cursor, 3),
            "duration": round(duration, 3),
            "planned_duration": round(planned_duration, 3),
            "video_duration": round(video_duration, 3),
            "audio_duration": round(audio_duration, 3),
            "image_path": str(image_path) if image_path else "",
            "video_path": str(video_path) if video_path else "",
            "audio_path": str(audio_path) if audio_path else "",
            "description": scene.get("description") or scene.get("scene_description") or "",
        }
        scene_map.append(scene_entry)

        if video_path:
            video_clips.append(
                {
                    "id": f"{clip_id}_video",
                    "scene_id": display_id,
                    "source_path": str(video_path),
                    "start": round(cursor, 3),
                    "duration": round(duration, 3),
                    "source_duration": round(video_duration, 3),
                    "fit": "trim_or_extend_to_scene_duration",
                }
            )
        else:
            warnings.append({"id": "missing_scene_video", "scene_id": display_id, "message": "scene has no local video"})

        if audio_path:
            audio_clips.append(
                {
                    "id": f"{clip_id}_audio",
                    "scene_id": display_id,
                    "source_path": str(audio_path),
                    "start": round(cursor, 3),
                    "duration": round(audio_duration or duration, 3),
                    "mix_role": "voice",
                }
            )

        caption_text = scene.get("subtitle_text") or scene.get("subtitle") or scene.get("narration") or ""
        if isinstance(caption_text, str) and caption_text.strip():
            caption_clips.append(
                {
                    "id": f"{clip_id}_caption",
                    "scene_id": display_id,
                    "text": caption_text.strip(),
                    "start": round(cursor, 3),
                    "duration": round(duration, 3),
                }
            )

        cursor += duration

    return {
        "schema": "capsule_cinema.edit_plan.v1",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "workspace": str(workspace_path),
        "source_storyboard": str(storyboard),
        "export_preset": {
            "aspect_ratio": data.get("aspect_ratio") or data.get("story", {}).get("aspect_ratio") or "",
            "duration": round(cursor, 3),
        },
        "timeline": {
            "duration": round(cursor, 3),
            "tracks": [
                {"id": "video_main", "type": "video", "clips": video_clips},
                {"id": "voice_main", "type": "audio", "clips": audio_clips},
                {"id": "captions_main", "type": "caption", "clips": caption_clips},
            ],
        },
        "scene_map": scene_map,
        "warnings": warnings,
    }


def write_edit_plan(
    workspace: str | Path,
    *,
    storyboard_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> Path:
    workspace_path = require_workspace_under_output(workspace)
    output = require_under_output(output_path, "--output") if output_path else workspace_path / "work" / "edit_plan.json"
    plan = build_edit_plan(workspace_path, storyboard_path=storyboard_path)
    write_json(output, plan)
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", "--run-dir", dest="workspace", required=True, help="Workspace under output/")
    parser.add_argument("--storyboard", default="", help="Optional storyboard path")
    parser.add_argument("--output", default="", help="Output edit_plan.json path under output/")
    parser.add_argument("--json", action="store_true", help="Print the plan JSON")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        workspace = require_workspace_under_output(args.workspace)
        output = write_edit_plan(
            workspace,
            storyboard_path=args.storyboard or None,
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
