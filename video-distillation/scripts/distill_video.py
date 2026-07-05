#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from build_video_distillation_report import (
    build_beat_timeline,
    build_copy_logic,
    build_production_logic,
    build_recipe_seed,
    write_json,
    write_text,
    write_yaml,
)


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
REPO_ROOT = SKILL_DIR.parent

DEFAULT_OUTPUT_ROOT = Path("output/video_distillation")
DEFAULT_EXTERNAL_VIDEO_WORKFLOW_ROOT = Path("/Users/june2/code/github/video_workflow")
EXTRACTOR_TOOL_RELATIVE_PATH = Path(
    "backend/video_workflow/custom_tools/extract_content/social_media_content_extractor_tool.py"
)
DEFAULT_EXTRACTOR_TOOL_PATH = DEFAULT_EXTERNAL_VIDEO_WORKFLOW_ROOT / EXTRACTOR_TOOL_RELATIVE_PATH
EXTRACTOR_MODULE = "custom_tools.extract_content.social_media_content_extractor_tool"

RUN_SUBDIRS = [
    "00_source",
    "01_media",
    "02_transcript",
    "03_keyframes/frames",
    "04_gemini",
    "05_copy",
    "06_video_logic",
    "07_production_logic",
    "08_synthesis",
]


def safe_slug(value: str, default: str = "video") -> str:
    text = str(value or "").strip()
    match = re.search(r"v\.douyin\.com/([A-Za-z0-9_-]+)", text)
    if match:
        return match.group(1)
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")
    return slug[:48] or default


def _safe_run_id(run_id: str | None, slug: str) -> str:
    if run_id:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(run_id).strip()).strip("._-")
        return cleaned or safe_slug(slug, "run")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{safe_slug(slug)}"


def _relative_to(path: Path, parent: Path) -> str:
    return path.relative_to(parent).as_posix()


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def _safe_remove_run_dir(run_dir: Path, output_root: Path) -> None:
    resolved_run = run_dir.resolve(strict=False)
    resolved_root = output_root.resolve(strict=False)
    if resolved_run == resolved_root or not _is_under(run_dir, output_root):
        raise ValueError(f"refusing to remove unsafe run directory: {run_dir}")
    shutil.rmtree(run_dir)


def make_run_dir(output_root: Path, run_id: str | None, slug: str, force: bool = False) -> Path:
    output_root = Path(output_root)
    final_run_id = _safe_run_id(run_id, slug)
    run_dir = output_root / final_run_id
    if not _is_under(run_dir, output_root):
        raise ValueError(f"run directory escapes output root: {run_dir}")
    if run_dir.exists() and force:
        _safe_remove_run_dir(run_dir, output_root)
    run_dir.mkdir(parents=True, exist_ok=True)
    for subdir in RUN_SUBDIRS:
        (run_dir / subdir).mkdir(parents=True, exist_ok=True)
    return run_dir


def run_cmd(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_value(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _aspect_ratio(width: int, height: int) -> str:
    if not width or not height:
        return "unknown"
    ratio = width / height
    if ratio < 0.8:
        return "9:16"
    if ratio > 1.2:
        return "16:9"
    return "1:1"


def ffprobe_media(video: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {
            "ok": False,
            "reason": "ffprobe_missing",
            "tool": "ffprobe",
        }

    proc = run_cmd(
        [
            ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(video),
        ],
        timeout=60,
    )
    if proc.returncode != 0:
        return {
            "ok": False,
            "reason": "ffprobe_failed",
            "returncode": proc.returncode,
            "stderr": (proc.stderr or "").strip()[:2000],
        }

    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "reason": "ffprobe_json_failed",
            "error": str(exc),
        }

    streams = data.get("streams") if isinstance(data.get("streams"), list) else []
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio_streams = [item for item in streams if item.get("codec_type") == "audio"]
    format_info = data.get("format") if isinstance(data.get("format"), dict) else {}
    width = _int_value(video_stream.get("width"))
    height = _int_value(video_stream.get("height"))
    duration = _float_value(format_info.get("duration") or video_stream.get("duration"))

    return {
        "ok": True,
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "aspect_ratio": _aspect_ratio(width, height),
        "has_audio": bool(audio_streams),
        "video_codec": str(video_stream.get("codec_name") or ""),
        "audio_stream_count": len(audio_streams),
        "format_name": str(format_info.get("format_name") or ""),
    }


def _candidate_keyframe_timestamps(duration_seconds: float) -> list[float]:
    duration = max(float(duration_seconds or 0), 0.0)
    candidates = [0.0]
    if duration >= 0.75:
        candidates.append(min(1.0, duration * 0.5))
    if duration >= 2.0:
        candidates.append(min(3.0, duration * 0.5))
    if duration > 0:
        candidates.append(max(duration - 0.25, 0.0))

    unique: list[float] = []
    for item in candidates:
        rounded = round(max(item, 0.0), 2)
        if rounded not in unique:
            unique.append(rounded)
    return unique


def extract_keyframes(video: Path, run_dir: Path, duration_seconds: float) -> list[dict[str, Any]]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return []

    frames: list[dict[str, Any]] = []
    for index, timestamp in enumerate(_candidate_keyframe_timestamps(duration_seconds)):
        frame_path = run_dir / "03_keyframes" / "frames" / f"frame_{index:04d}_{timestamp:.2f}.jpg"
        proc = run_cmd(
            [
                ffmpeg,
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(frame_path),
            ],
            timeout=60,
        )
        if proc.returncode == 0 and frame_path.is_file():
            frames.append(
                {
                    "path": _relative_to(frame_path, run_dir),
                    "timestamp": timestamp,
                    "label": "first_frame" if index == 0 else f"frame_{index}",
                }
            )
    return frames


def _artifact_entries(run_dir: Path) -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        rel_path = _relative_to(path, run_dir)
        if rel_path.startswith("../") or Path(rel_path).is_absolute():
            continue
        entries[rel_path] = {
            "path": rel_path,
            "status": "present",
            "size_bytes": path.stat().st_size,
        }

    manifest_path = "artifact_manifest.json"
    if manifest_path not in entries:
        entries[manifest_path] = {
            "path": manifest_path,
            "status": "present",
            "size_bytes": 0,
        }
    return [entries[key] for key in sorted(entries)]


def write_evidence_map(
    run_dir: Path,
    evidence_level: str,
    success: bool,
    failed_stage: str = "",
) -> Path:
    stage_status = "present" if success else "partial"
    return write_json(
        run_dir / "evidence_map.json",
        {
            "schema_version": "capsule_cinema.video_distillation_evidence_map.v1",
            "run_id": run_dir.name,
            "success": success,
            "failed_stage": failed_stage,
            "evidence_level": evidence_level,
            "stages": [
                {
                    "id": "V0_source_recorded",
                    "status": "present",
                    "artifact_paths": ["00_source/source_input.txt", "00_source/source_status.md"],
                },
                {
                    "id": "V1_media_acquired",
                    "status": stage_status if (run_dir / "01_media" / "video.mp4").exists() else "missing",
                    "artifact_paths": ["01_media/video.mp4", "00_source/media_info.json"],
                },
                {
                    "id": "V2_transcript_ready",
                    "status": stage_status if (run_dir / "02_transcript" / "transcript.txt").exists() else "missing",
                    "artifact_paths": [
                        "02_transcript/transcript.txt",
                        "02_transcript/transcript_analysis.md",
                    ],
                },
                {
                    "id": "V3_keyframes_ready",
                    "status": stage_status if (run_dir / "03_keyframes" / "keyframe_index.json").exists() else "missing",
                    "artifact_paths": ["03_keyframes/keyframe_index.json"],
                },
                {
                    "id": "V4_copy_and_timeline_ready",
                    "status": stage_status if (run_dir / "05_copy" / "copy_logic.yaml").exists() else "missing",
                    "artifact_paths": ["05_copy/copy_logic.yaml", "06_video_logic/beat_timeline.json"],
                },
                {
                    "id": "V5_production_logic_distilled",
                    "status": stage_status
                    if (run_dir / "07_production_logic" / "production_logic.yaml").exists()
                    else "missing",
                    "artifact_paths": ["07_production_logic/production_logic.yaml"],
                },
                {
                    "id": "V6_recipe_seed_ready",
                    "status": "present" if success else "missing",
                    "artifact_paths": ["08_synthesis/recipe_seed.yaml"],
                },
            ],
            "folders": {
                "source": "00_source",
                "media": "01_media",
                "transcript": "02_transcript",
                "keyframes": "03_keyframes",
                "gemini": "04_gemini",
                "copy": "05_copy",
                "video_logic": "06_video_logic",
                "production_logic": "07_production_logic",
                "synthesis": "08_synthesis",
            },
        },
    )


def write_artifact_manifest(
    run_dir: Path,
    success: bool,
    failed_stage: str = "",
) -> Path:
    return write_json(
        run_dir / "artifact_manifest.json",
        {
            "schema_version": "capsule_cinema.video_distillation_manifest.v1",
            "run_id": run_dir.name,
            "success": success,
            "failed_stage": failed_stage,
            "artifacts": _artifact_entries(run_dir),
        },
    )


def write_manifest_bundle(
    run_dir: Path,
    evidence_level: str,
    success: bool,
    failed_stage: str = "",
) -> None:
    write_evidence_map(run_dir, evidence_level, success, failed_stage)
    write_artifact_manifest(run_dir, success, failed_stage)


def _write_source_status(
    run_dir: Path,
    status: str,
    failed_stage: str = "",
    message: str = "",
    extra_lines: list[str] | None = None,
) -> Path:
    lines = ["# Source Status", "", f"- status: {status}"]
    if failed_stage:
        lines.append(f"- failed_stage: {failed_stage}")
    if message:
        lines.append(f"- message: {message}")
    if extra_lines:
        lines.extend(extra_lines)
    return write_text(run_dir / "00_source" / "source_status.md", "\n".join(lines))


def _failure(
    run_dir: Path,
    stage: str,
    message: str,
    evidence_level: str = "V0_metadata_only",
    extra_status_lines: list[str] | None = None,
) -> dict[str, Any]:
    _write_source_status(
        run_dir,
        status="failed",
        failed_stage=stage,
        message=message,
        extra_lines=extra_status_lines,
    )
    write_manifest_bundle(run_dir, evidence_level, False, stage)
    return {
        "success": False,
        "failed_stage": stage,
        "output_dir": str(run_dir),
        "evidence_level": evidence_level,
        "error": message,
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _write_keyframe_analysis(run_dir: Path, keyframes: list[dict[str, Any]]) -> None:
    if keyframes:
        body = "\n".join(
            f"- {item['label']}: `{item['path']}` at {item['timestamp']}s" for item in keyframes
        )
    else:
        body = "- inference: no keyframes were extracted from the local media."
    write_text(run_dir / "03_keyframes" / "keyframe_analysis.md", f"# Keyframe Analysis\n\n{body}")


def _distill_acquired_video(
    source_video: Path,
    run_dir: Path,
    transcript_text: str = "",
    enable_gemini: bool = False,
    source_title: str = "",
    source_caption: str = "",
    ready_status: str = "local_video_ready",
    status_extra_lines: list[str] | None = None,
) -> dict[str, Any]:
    source_video = Path(source_video).expanduser()
    if not source_video.is_file():
        return _failure(
            run_dir,
            "download_failed",
            f"local video not found: {source_video}",
            evidence_level="V0_metadata_only",
            extra_status_lines=status_extra_lines,
        )

    target_video = run_dir / "01_media" / "video.mp4"
    if source_video.resolve(strict=False) != target_video.resolve(strict=False):
        shutil.copy2(source_video, target_video)

    media_info = ffprobe_media(target_video)
    write_json(run_dir / "00_source" / "media_info.json", media_info)
    if not media_info.get("ok"):
        return _failure(
            run_dir,
            "ffprobe_failed",
            str(media_info.get("reason") or "ffprobe failed"),
            evidence_level="V1_media_acquired",
            extra_status_lines=status_extra_lines,
        )

    transcript = transcript_text.strip()
    write_text(run_dir / "02_transcript" / "transcript.txt", transcript)
    write_text(
        run_dir / "02_transcript" / "transcript_analysis.md",
        "# Transcript Analysis\n\n"
        + (
            "Transcript text was supplied by the caller and used as local evidence."
            if transcript
            else "No transcript text was supplied; copy logic uses media and keyframe inference only."
        ),
    )

    keyframes = extract_keyframes(
        target_video,
        run_dir,
        float(media_info.get("duration_seconds") or 0),
    )
    write_json(
        run_dir / "03_keyframes" / "keyframe_index.json",
        {
            "schema_version": "capsule_cinema.video_distillation_keyframes.v1",
            "extraction_status": "present" if keyframes else "empty_or_ffmpeg_unavailable",
            "frames": keyframes,
        },
    )
    _write_keyframe_analysis(run_dir, keyframes)

    gemini_status = (
        "disabled_by_request"
        if not enable_gemini
        else "not_called_in_task_4_local_runner"
    )
    write_text(
        run_dir / "04_gemini" / "gemini_status.md",
        "# Gemini Status\n\n"
        f"- status: {gemini_status}\n"
        "- note: Task 4 local runs do not call live Gemini APIs.",
    )

    beat_timeline = build_beat_timeline(transcript, keyframes, None)
    copy_logic = build_copy_logic(
        source={"title": source_title or source_video.stem, "caption": source_caption},
        transcript=transcript,
        beats=beat_timeline["beats"],
        evidence_level="V2_transcript_ready" if transcript else "V1_media_acquired",
    )
    production_logic = build_production_logic(media_info, keyframes, None, copy_logic)
    recipe_seed = build_recipe_seed(copy_logic, beat_timeline, production_logic)

    write_yaml(run_dir / "05_copy" / "copy_logic.yaml", copy_logic)
    write_text(run_dir / "05_copy" / "copy_analysis.md", "# Copy Analysis\n\nSee `copy_logic.yaml`.")
    write_json(run_dir / "06_video_logic" / "beat_timeline.json", beat_timeline)
    write_text(
        run_dir / "06_video_logic" / "narrative_logic.md",
        "# Narrative Logic\n\nSee `beat_timeline.json`.",
    )
    write_yaml(
        run_dir / "06_video_logic" / "retention_logic.yaml",
        {
            "main_retention_device": beat_timeline["logic_summary"]["main_retention_device"],
            "evidence": beat_timeline["logic_summary"]["evidence"],
        },
    )
    write_yaml(run_dir / "07_production_logic" / "production_logic.yaml", production_logic)
    write_json(
        run_dir / "07_production_logic" / "modality_breakdown.json",
        production_logic["production_route"],
    )
    write_text(
        run_dir / "07_production_logic" / "implementation_playbook.md",
        "# Implementation Playbook\n\n" + production_logic["recommended_route"],
    )
    write_text(
        run_dir / "08_synthesis" / "video_distillation.md",
        "# Video Distillation\n\n"
        "Deep distillation artifacts generated from the local video without network access.",
    )
    write_text(
        run_dir / "08_synthesis" / "reusable_patterns.md",
        "# Reusable Patterns\n\nUse the recipe seed without copying source identity.",
    )
    write_yaml(run_dir / "08_synthesis" / "recipe_seed.yaml", recipe_seed)
    extra_lines = [
        f"- evidence_level: V6_recipe_seed_ready",
        f"- copied_media: 01_media/video.mp4",
    ]
    if status_extra_lines:
        extra_lines.extend(status_extra_lines)
    _write_source_status(
        run_dir,
        status=ready_status,
        extra_lines=extra_lines,
    )
    write_manifest_bundle(run_dir, "V6_recipe_seed_ready", True)
    return {
        "success": True,
        "output_dir": str(run_dir),
        "evidence_level": "V6_recipe_seed_ready",
    }


def run_local_distillation(
    local_video: Path,
    output_root: Path,
    run_id: str,
    transcript_text: str = "",
    enable_gemini: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    local_video = Path(local_video).expanduser()
    run_dir = make_run_dir(Path(output_root).expanduser(), run_id, local_video.stem, force=force)
    write_text(run_dir / "00_source" / "source_input.txt", str(local_video))
    return _distill_acquired_video(
        source_video=local_video,
        run_dir=run_dir,
        transcript_text=transcript_text,
        enable_gemini=enable_gemini,
        source_title=local_video.stem,
        ready_status="local_video_ready",
    )


def _external_extractor_tool_path(external_video_workflow_root: Path) -> Path:
    return Path(external_video_workflow_root).expanduser() / EXTRACTOR_TOOL_RELATIVE_PATH


def _extractor_status_lines(external_video_workflow_root: Path) -> list[str]:
    configured_tool = _external_extractor_tool_path(external_video_workflow_root)
    return [
        "- contract: references/extraction-tool-contract.md",
        f"- default_extractor_tool: {DEFAULT_EXTRACTOR_TOOL_PATH}",
        f"- configured_extractor_tool: {configured_tool}",
    ]


def load_env_file(path: Path) -> None:
    path = Path(path).expanduser()
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            continue
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def extract_with_external_tool(
    url_or_share_text: str,
    run_dir: Path,
    external_video_workflow_root: Path,
    dotenv_path: Path,
) -> dict[str, Any]:
    external_video_workflow_root = Path(external_video_workflow_root).expanduser()
    package_root = external_video_workflow_root / "backend" / "video_workflow"
    configured_tool = _external_extractor_tool_path(external_video_workflow_root)
    extract_result_path = run_dir / "00_source" / "extract_result.json"

    if not package_root.is_dir():
        result = {
            "success": False,
            "failed_stage": "extractor_import_failed",
            "error": "extractor package root not found",
            "configured_extractor_tool": str(configured_tool),
        }
        write_json(extract_result_path, result)
        return result

    load_env_file(dotenv_path)
    package_root_text = str(package_root)
    if package_root_text not in sys.path:
        sys.path.insert(0, package_root_text)
    importlib.invalidate_caches()
    for module_name in (
        EXTRACTOR_MODULE,
        "custom_tools.extract_content",
        "custom_tools",
    ):
        sys.modules.pop(module_name, None)

    try:
        module = importlib.import_module(EXTRACTOR_MODULE)
        extractor_cls = getattr(module, "SocialMediaContentExtractorTool")
    except Exception as exc:
        result = {
            "success": False,
            "failed_stage": "extractor_import_failed",
            "error": type(exc).__name__,
            "configured_extractor_tool": str(configured_tool),
        }
        write_json(extract_result_path, result)
        return result

    try:
        result = extractor_cls()._run(
            url=url_or_share_text,
            enable_transcript=True,
            enable_video_analysis=False,
            output_dir=str(run_dir / "00_source" / "extractor"),
            save_video=True,
        )
    except Exception as exc:
        result = {
            "success": False,
            "failed_stage": "parse_failed",
            "error": type(exc).__name__,
            "configured_extractor_tool": str(configured_tool),
        }
        write_json(extract_result_path, result)
        return result

    if not isinstance(result, dict):
        result = {
            "success": False,
            "failed_stage": "parse_failed",
            "error": f"extractor returned {type(result).__name__}",
            "configured_extractor_tool": str(configured_tool),
        }
    else:
        result = dict(result)
        result.setdefault("configured_extractor_tool", str(configured_tool))

    if not result.get("success"):
        result.setdefault("failed_stage", "parse_failed")
        result.setdefault("error", "external extractor acquisition failed")
    write_json(extract_result_path, _json_safe(result))
    return result


def _extracted_video_path(extracted: dict[str, Any]) -> Path | None:
    for key in ("video_file", "video_local_path", "local_video", "video_path", "downloaded_video"):
        value = extracted.get(key)
        if value:
            return Path(str(value)).expanduser()
    return None


def run_url_distillation(
    url: str,
    output_root: Path,
    run_id: str,
    external_video_workflow_root: Path = DEFAULT_EXTERNAL_VIDEO_WORKFLOW_ROOT,
    dotenv_path: Path = DEFAULT_EXTERNAL_VIDEO_WORKFLOW_ROOT / ".env",
    enable_gemini: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    external_video_workflow_root = Path(external_video_workflow_root).expanduser()
    run_dir = make_run_dir(Path(output_root).expanduser(), run_id, safe_slug(url, "url"), force=force)
    write_text(run_dir / "00_source" / "source_input.txt", url)

    status_lines = _extractor_status_lines(external_video_workflow_root)
    extracted = extract_with_external_tool(
        url_or_share_text=url,
        run_dir=run_dir,
        external_video_workflow_root=external_video_workflow_root,
        dotenv_path=Path(dotenv_path).expanduser(),
    )
    if not extracted.get("success"):
        failed_stage = str(extracted.get("failed_stage") or "parse_failed")
        message = (
            "external extractor import failed"
            if failed_stage == "extractor_import_failed"
            else "external extractor acquisition failed"
        )
        return _failure(
            run_dir,
            failed_stage,
            message,
            evidence_level="V0_metadata_only",
            extra_status_lines=status_lines,
        )

    video_path = _extracted_video_path(extracted)
    if not video_path or not video_path.is_file():
        return _failure(
            run_dir,
            "download_failed",
            "extractor succeeded but no local video path was found",
            evidence_level="V0_metadata_only",
            extra_status_lines=status_lines,
        )

    return _distill_acquired_video(
        source_video=video_path,
        run_dir=run_dir,
        transcript_text=str(extracted.get("transcript") or ""),
        enable_gemini=enable_gemini,
        source_title=str(extracted.get("title") or video_path.stem),
        source_caption=str(extracted.get("caption") or ""),
        ready_status="external_video_ready",
        status_extra_lines=status_lines,
    )


def _result_for_missing_input(output_root: Path, run_id: str, force: bool) -> dict[str, Any]:
    run_dir = make_run_dir(output_root, run_id, "missing_input", force=force)
    write_text(run_dir / "00_source" / "source_input.txt", "")
    return _failure(
        run_dir,
        "parse_failed",
        "provide --local-video for Task 4 local runs or --url for the Task 5 extractor path",
        evidence_level="V0_metadata_only",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deep-distill a social/local video into evidence-backed production logic."
    )
    parser.add_argument("--local-video", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--transcript-text", default="")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--run-id", default="")
    parser.add_argument("--disable-gemini", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--external-video-workflow-root",
        default=str(DEFAULT_EXTERNAL_VIDEO_WORKFLOW_ROOT),
    )
    parser.add_argument(
        "--dotenv-path",
        default=str(DEFAULT_EXTERNAL_VIDEO_WORKFLOW_ROOT / ".env"),
    )
    args = parser.parse_args()

    output_root = Path(args.output_root).expanduser()
    if args.local_video:
        local_video = Path(args.local_video).expanduser()
        result = run_local_distillation(
            local_video=local_video,
            output_root=output_root,
            run_id=args.run_id or _safe_run_id("", local_video.stem),
            transcript_text=args.transcript_text,
            enable_gemini=not args.disable_gemini,
            force=args.force,
        )
    elif args.url:
        result = run_url_distillation(
            url=args.url,
            output_root=output_root,
            run_id=args.run_id or _safe_run_id("", args.url),
            external_video_workflow_root=Path(args.external_video_workflow_root),
            dotenv_path=Path(args.dotenv_path),
            enable_gemini=not args.disable_gemini,
            force=args.force,
        )
    else:
        result = _result_for_missing_input(
            output_root=output_root,
            run_id=args.run_id or _safe_run_id("", "missing_input"),
            force=args.force,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
