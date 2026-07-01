#!/usr/bin/env python3.12
"""Local-script entrypoint for the life_sim capsule.

The creative story can still be adapted per topic, but this runner owns the
execution contract so recurring format rules are enforced before spending image
or TTS quota.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MICRO_CUT_SECONDS = 2.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute the life_sim local-script capsule.")
    parser.add_argument("--topic", required=True, help="本期人生主题，例如 赌球成瘾者的一生。")
    parser.add_argument("--params", default="", help="Merged capsule/user params JSON.")
    parser.add_argument("--output-dir", required=True, help="Run directory for final/, reports/, and artifact_manifest.json.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the execution contract and write reports without generating paid media.",
    )
    return parser


def read_json(path: str) -> dict[str, Any]:
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


def config_from_params(params: dict[str, Any]) -> dict[str, Any]:
    config = params.get("config") or {}
    if not isinstance(config, dict):
        raise SystemExit("params.config must be an object when provided")
    return config


def target_duration_seconds(params: dict[str, Any], config: dict[str, Any]) -> float:
    for key in ("target_duration_seconds", "target_duration", "duration_seconds"):
        value = params.get(key, config.get(key))
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    policy = config.get("duration_policy") if isinstance(config.get("duration_policy"), dict) else {}
    typical = policy.get("typical_range_seconds")
    if isinstance(typical, list) and typical and isinstance(typical[-1], (int, float)):
        return float(typical[-1])
    return 180.0


def ideal_micro_cut_seconds(config: dict[str, Any]) -> float:
    spec = config.get("micro_cut_seconds") if isinstance(config.get("micro_cut_seconds"), dict) else {}
    ideal = spec.get("ideal")
    if isinstance(ideal, list) and ideal:
        numeric = [float(item) for item in ideal if isinstance(item, (int, float))]
        if numeric:
            return sum(numeric) / len(numeric)
    if isinstance(spec.get("max"), (int, float)):
        return min(DEFAULT_MICRO_CUT_SECONDS, float(spec["max"]))
    return DEFAULT_MICRO_CUT_SECONDS


def estimate_unique_body_images(params: dict[str, Any], config: dict[str, Any]) -> int:
    duration = target_duration_seconds(params, config)
    opening = config.get("opening_template") if isinstance(config.get("opening_template"), dict) else {}
    opening_duration = opening.get("duration_seconds") if isinstance(opening.get("duration_seconds"), dict) else {}
    opening_seconds = float(opening_duration.get("default", 4.0))
    body_seconds = max(0.0, duration - opening_seconds)
    return max(1, math.ceil(body_seconds / ideal_micro_cut_seconds(config)))


def opening_style(params: dict[str, Any], config: dict[str, Any]) -> str:
    value = params.get("opening_style") or config.get("opening_style") or config.get("opening_style_default")
    return str(value or "life_shaker").strip() or "life_shaker"


def validate_contract(topic: str, params: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    output_contract = config.get("output_contract") if isinstance(config.get("output_contract"), dict) else {}
    opening_template = config.get("opening_template") if isinstance(config.get("opening_template"), dict) else {}
    required_lines = opening_template.get("tts_required_lines") or []
    selected_opening_style = opening_style(params, config)
    opening_style_options = config.get("opening_style_options") or ["life_shaker", "title_card", "cold_open", "none"]

    checks.append({
        "id": "opening_style_supported",
        "ok": selected_opening_style in opening_style_options,
        "severity": "blocker",
        "message": "opening_style 必须是 life_shaker/title_card/cold_open/none 之一。",
    })

    checks.append({
        "id": "opening_series_tts_required",
        "ok": selected_opening_style != "life_shaker" or (
            "series_title" in required_lines and "episode_topic" in required_lines
        ),
        "severity": "blocker",
        "message": "life_shaker 默认开场的片头 TTS 必须包含系列标题和本期主题。",
    })
    checks.append({
        "id": "body_subtitles_disabled_by_default",
        "ok": output_contract.get("subtitle") == "none" and config.get("body_subtitles_default") is False,
        "severity": "blocker",
        "message": "正文默认不烧底部对白字幕。",
    })
    checks.append({
        "id": "unique_image2_keyframes",
        "ok": (
            config.get("visual_generation_type") == "unique_image2_keyframes_with_micro_cuts"
            and config.get("micro_cut_visual_source") == "unique_image2_keyframe_per_cut"
            and config.get("distinct_body_image_per_micro_cut_required") is True
        ),
        "severity": "blocker",
        "message": "正文每个 1-3 秒微切默认必须使用独立 Image2 关键帧，不能只复用同一张图裁切。",
    })
    checks.append({
        "id": "unique_image2_content_hashes",
        "ok": config.get("body_image_content_hash_unique_required") is True,
        "severity": "blocker",
        "message": "正文微切图片必须检查内容哈希唯一，不能只检查路径唯一。",
    })
    micro = config.get("micro_cut_seconds") if isinstance(config.get("micro_cut_seconds"), dict) else {}
    checks.append({
        "id": "micro_cut_seconds_range",
        "ok": float(micro.get("min", 0)) >= 1.0 and float(micro.get("max", 99)) <= 3.0,
        "severity": "blocker",
        "message": "正文切图间隔必须在 1-3 秒。",
    })
    checks.append({
        "id": "topic_present",
        "ok": bool(topic.strip()),
        "severity": "blocker",
        "message": "必须提供本期人生主题。",
    })
    return checks


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_run_notes(
    *,
    output_dir: Path,
    topic: str,
    params: dict[str, Any],
    config: dict[str, Any],
    checks: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, Any]:
    image_count = estimate_unique_body_images(params, config)
    ok = all(item["ok"] for item in checks if item.get("severity") == "blocker")
    notes = {
        "ok": ok,
        "dry_run": dry_run,
        "topic": topic,
        "execution_mode": "local_script",
        "opening_style": opening_style(params, config),
        "visual_strategy": "unique_image2_keyframes_with_micro_cuts",
        "micro_cut_visual_source": "unique_image2_keyframe_per_cut",
        "estimated_unique_body_images": image_count,
        "budget_notice": (
            f"按当前时长和 1-3 秒切图策略，正文预计需要约 {image_count} 张独立 Image2 图片；"
            "正式生成前应向用户提示用量。"
        ),
        "checks": checks,
    }
    write_json(output_dir / "reports" / "run_notes.json", notes)
    return notes


def write_dry_run_manifest(output_dir: Path, notes: dict[str, Any]) -> None:
    report = output_dir / "reports" / "run_notes.json"
    manifest = {
        "schema_version": 1,
        "capsule": "life_sim",
        "execution_mode": "local_script",
        "dry_run": True,
        "artifacts": [
            {"path": str(report), "category": "run_notes", "title": "Dry-run contract report"},
        ],
        "estimated_unique_body_images": notes["estimated_unique_body_images"],
    }
    write_json(output_dir / "artifact_manifest.json", manifest)


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    params = read_json(args.params)
    config = config_from_params(params)
    checks = validate_contract(args.topic, params, config)
    notes = write_run_notes(
        output_dir=output_dir,
        topic=args.topic,
        params=params,
        config=config,
        checks=checks,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        write_dry_run_manifest(output_dir, notes)
        return 0 if notes["ok"] else 2

    failed = [item for item in checks if item.get("severity") == "blocker" and not item.get("ok")]
    if failed:
        write_dry_run_manifest(output_dir, notes)
        return 2

    # The rendering backend is intentionally gated until callers pass an
    # adapted storyboard package. This keeps the local_script from silently
    # falling back to one-scene-per-image rendering.
    write_json(
        output_dir / "reports" / "run_notes.json",
        {
            **notes,
            "ok": False,
            "error": "render_backend_requires_storyboard_package",
            "required_input": "params.storyboard or params.storyboard_path with per-micro-cut Image2 prompts",
        },
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
