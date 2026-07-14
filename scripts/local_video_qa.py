#!/usr/bin/env python3
"""Local final-video QA for video-production runs."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def find_manifest_video(manifest: dict) -> str:
    artifacts = manifest.get("artifacts") or []
    for item in artifacts:
        if isinstance(item, dict) and item.get("category") == "final_video" and item.get("path"):
            return str(item["path"])
    return ""


def probe_audio_loudness(path: Path) -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"ok": False, "error": "ffmpeg not found"}
    proc = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    text = (proc.stderr or "") + "\n" + (proc.stdout or "")
    if proc.returncode != 0:
        return {"ok": False, "error": text.strip()}

    values: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if "mean_volume:" in line:
            try:
                values["mean_volume_db"] = float(line.rsplit("mean_volume:", 1)[1].strip().split(" ", 1)[0])
            except (IndexError, ValueError):
                pass
        if "max_volume:" in line:
            try:
                values["max_volume_db"] = float(line.rsplit("max_volume:", 1)[1].strip().split(" ", 1)[0])
            except (IndexError, ValueError):
                pass
    if "max_volume_db" not in values:
        return {"ok": False, "error": "volumedetect max_volume not found"}
    return {"ok": True, **values}


def probe_video(path: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"ok": False, "error": "ffprobe not found"}
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip() or proc.stdout.strip()}
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"invalid ffprobe JSON: {exc}"}
    streams = data.get("streams") or []
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio_streams = [item for item in streams if item.get("codec_type") == "audio"]
    if not video_stream:
        return {"ok": False, "error": "no video stream"}

    def as_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    duration = as_float((data.get("format") or {}).get("duration")) or as_float(video_stream.get("duration")) or 0.0
    return {
        "ok": True,
        "duration": duration,
        "width": int(video_stream.get("width") or 0),
        "height": int(video_stream.get("height") or 0),
        "has_audio": bool(audio_streams),
        "audio_loudness": probe_audio_loudness(path) if audio_streams else {"ok": False, "error": "no audio stream"},
        "format": data.get("format") or {},
    }


def expected_ratio_value(aspect_ratio: str | None) -> float | None:
    if not aspect_ratio or ":" not in str(aspect_ratio):
        return None
    try:
        width, height = str(aspect_ratio).split(":", 1)
        width_num = float(width)
        height_num = float(height)
    except ValueError:
        return None
    if height_num <= 0:
        return None
    return width_num / height_num


def add_check(checks: list[dict], ok: bool, check_id: str, message: str, severity: str = "error", **extra: Any) -> None:
    checks.append({"id": check_id, "ok": ok, "severity": severity, "message": message, **extra})


def resolve_manifest_path(path_value: str, run_dir: Path | None) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute() and run_dir is not None:
        path = run_dir / path
    return path.resolve()


def run_qa(args: argparse.Namespace) -> dict:
    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else None
    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else None
    if manifest_path is None and run_dir is not None:
        manifest_path = run_dir / "artifact_manifest.json"
    manifest = read_json(manifest_path) if manifest_path else {}

    video_path = args.final_video or find_manifest_video(manifest)
    if not video_path and run_dir is not None:
        for sub in ("release", "final"):
            candidates = sorted((run_dir / sub).glob("*.mp4"))
            if candidates:
                video_path = str(candidates[0])
                break
    video = Path(video_path).expanduser().resolve() if video_path else None

    checks: list[dict] = []
    add_check(checks, bool(manifest), "manifest_exists", "artifact_manifest.json exists")
    if manifest:
        artifacts = [item for item in manifest.get("artifacts", []) if isinstance(item, dict)]
        categories = {item.get("category") for item in artifacts}
        add_check(checks, "final_video" in categories, "manifest_final_video", "manifest includes final_video")
        add_check(checks, "copywriting" in categories, "manifest_copywriting", "manifest includes copywriting", severity="warning")
        if args.require_prompts:
            prompt_artifacts = [item for item in artifacts if item.get("category") == "storyboard_prompt"]
            prompt_index_paths = [
                resolve_manifest_path(str(item["path"]), run_dir)
                for item in prompt_artifacts
                if str(item.get("path") or "").endswith("prompt_index.json")
            ]
            missing_prompt_paths = [
                str(resolve_manifest_path(str(item.get("path")), run_dir))
                for item in prompt_artifacts
                if item.get("path") and not resolve_manifest_path(str(item["path"]), run_dir).exists()
            ]
            add_check(
                checks,
                bool(prompt_artifacts),
                "manifest_prompt_artifacts",
                "manifest includes prompt snapshots",
                count=len(prompt_artifacts),
            )
            add_check(
                checks,
                any(path.exists() for path in prompt_index_paths),
                "prompt_index_exists",
                "prompts/prompt_index.json exists and is listed in manifest",
                paths=[str(path) for path in prompt_index_paths],
            )
            add_check(
                checks,
                not missing_prompt_paths,
                "manifest_prompt_paths_exist",
                "all manifest prompt snapshot paths exist",
                missing=missing_prompt_paths,
            )
    elif args.require_prompts:
        add_check(checks, False, "manifest_prompt_artifacts", "manifest includes prompt snapshots", count=0)
        add_check(checks, False, "prompt_index_exists", "prompts/prompt_index.json exists and is listed in manifest", paths=[])

    add_check(checks, bool(video and video.exists()), "final_video_exists", "final video exists", path=str(video) if video else "")
    probe = probe_video(video) if video and video.exists() else {"ok": False, "error": "missing final video"}
    add_check(checks, bool(probe.get("ok")), "ffprobe", "ffprobe can parse final video", detail=probe.get("error", ""))
    if probe.get("ok"):
        duration = float(probe.get("duration") or 0)
        width = int(probe.get("width") or 0)
        height = int(probe.get("height") or 0)
        add_check(checks, duration >= args.min_duration, "duration_min", "duration meets minimum", actual=duration, expected=args.min_duration)
        if args.expect_audio:
            add_check(checks, bool(probe.get("has_audio")), "audio_expected", "audio stream exists")
            if probe.get("has_audio"):
                loudness = probe.get("audio_loudness") if isinstance(probe.get("audio_loudness"), dict) else {}
                max_volume = loudness.get("max_volume_db")
                if isinstance(max_volume, (int, float)):
                    silence_threshold = float(getattr(args, "audio_silence_max_volume_db", -60.0))
                    add_check(
                        checks,
                        float(max_volume) > silence_threshold,
                        "audio_not_silent",
                        "audio is above the silence threshold",
                        actual_max_volume_db=float(max_volume),
                        expected_above_db=silence_threshold,
                    )
                else:
                    add_check(
                        checks,
                        False,
                        "audio_loudness_measured",
                        "audio loudness can be measured",
                        severity="warning",
                        detail=loudness.get("error", ""),
                    )
        expected_ratio = expected_ratio_value(args.aspect_ratio)
        if expected_ratio and width and height:
            actual_ratio = width / height
            ok = abs(actual_ratio - expected_ratio) <= args.aspect_tolerance
            add_check(
                checks,
                ok,
                "aspect_ratio",
                "aspect ratio matches expected",
                actual=round(actual_ratio, 4),
                expected=args.aspect_ratio,
                width=width,
                height=height,
            )

    errors = [item for item in checks if not item["ok"] and item.get("severity") == "error"]
    return {
        "ok": not errors,
        "scope": "local_video_qa",
        "run_dir": str(run_dir) if run_dir else "",
        "manifest_path": str(manifest_path) if manifest_path else "",
        "final_video": str(video) if video else "",
        "probe": probe,
        "checks": checks,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--manifest", default="")
    parser.add_argument("--final-video", default="")
    parser.add_argument("--aspect-ratio", default="")
    parser.add_argument("--min-duration", type=float, default=6.0)
    parser.add_argument("--aspect-tolerance", type=float, default=0.08)
    parser.add_argument("--expect-audio", action="store_true")
    parser.add_argument("--audio-silence-max-volume-db", type=float, default=-60.0)
    parser.add_argument("--require-prompts", action="store_true", help="Require prompt snapshots and prompt_index.json in artifact_manifest.json")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = run_qa(args)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    if args.json or args.output:
        print(text)
    else:
        print("local_video_qa:", "ok" if report["ok"] else "failed")
        for item in report["checks"]:
            status = "ok" if item["ok"] else item.get("severity", "error")
            print(f"- {status}: {item['id']} - {item['message']}")
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
