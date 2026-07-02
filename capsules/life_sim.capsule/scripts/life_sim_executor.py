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
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MICRO_CUT_SECONDS = 2.0


def _is_identity_ignored_char(char: str) -> bool:
    return char.isspace() or unicodedata.category(char).startswith("P")


def normalize_for_identity_lock(text: str) -> str:
    """Normalize only for comparing repeated opening identity-lock copy."""
    return "".join(
        char.casefold()
        for char in str(text or "")
        if not _is_identity_ignored_char(char)
    )


def _opening_prefix_end_index(narration_script: str, opening_tts: str) -> int | None:
    target = normalize_for_identity_lock(opening_tts)
    if not target:
        return None

    position = 0
    for index, char in enumerate(str(narration_script or "")):
        if _is_identity_ignored_char(char):
            continue
        if char.casefold() != target[position]:
            return None
        position += 1
        if position == len(target):
            return index + 1
    return None


def strip_opening_tts_from_body_script(narration_script: str, opening_tts: str) -> tuple[str, bool]:
    """Return body TTS text with a duplicated opening identity-lock prefix removed."""
    script = str(narration_script or "")
    opening_end = _opening_prefix_end_index(script, opening_tts)
    if opening_end is None:
        return script, False

    suffix = script[opening_end:]
    if suffix and not _is_identity_ignored_char(suffix[0]):
        return script, False

    while suffix and _is_identity_ignored_char(suffix[0]):
        suffix = suffix[1:]
    return suffix, True


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return ""


def opening_tts_from_params(params: dict[str, Any]) -> str:
    storyboard = _mapping(params.get("storyboard"))
    opening = _mapping(params.get("opening"))
    storyboard_opening = _mapping(storyboard.get("opening"))
    return _first_text(
        params.get("opening_tts"),
        params.get("opening_tts_text"),
        opening.get("tts"),
        opening.get("tts_text"),
        storyboard.get("opening_tts"),
        storyboard.get("opening_tts_text"),
        storyboard_opening.get("tts"),
        storyboard_opening.get("tts_text"),
    )


def body_narration_script_from_params(params: dict[str, Any]) -> str:
    storyboard = _mapping(params.get("storyboard"))
    return _first_text(
        params.get("body_narration_script"),
        storyboard.get("body_narration_script"),
        params.get("narration_script_for_tts"),
        storyboard.get("narration_script_for_tts"),
        params.get("narration_script"),
        storyboard.get("narration_script"),
    )


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


def micro_cut_average_target(config: dict[str, Any]) -> dict[str, float]:
    spec = config.get("micro_cut_seconds") if isinstance(config.get("micro_cut_seconds"), dict) else {}
    target = spec.get("target_average") if isinstance(spec.get("target_average"), dict) else {}
    return {
        "min": float(target.get("min", 0)),
        "max": float(target.get("max", 99)),
    }


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
    opening_tts = opening_tts_from_params(params)
    body_script = body_narration_script_from_params(params)
    _, opening_repeated_in_body = strip_opening_tts_from_body_script(body_script, opening_tts)
    checks.append({
        "id": "opening_tts_not_repeated_in_body",
        "ok": selected_opening_style == "none" or not opening_tts or not body_script or not opening_repeated_in_body,
        "severity": "blocker",
        "message": (
            "片头身份锁定句只能出现在 opening.tts；正文 TTS 必须使用已去重的 body_narration_script，"
            "不能让 narration_script 再从同一句开场开始。"
        ),
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
        "message": "正文每个 1-5 秒微切默认必须使用独立 Image2 关键帧，不能只复用同一张图裁切。",
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
        "ok": float(micro.get("min", 0)) >= 1.0 and float(micro.get("max", 99)) <= 5.0,
        "severity": "blocker",
        "message": "正文切图间隔必须在 1-5 秒。",
    })
    average_target = micro_cut_average_target(config)
    ideal_seconds = ideal_micro_cut_seconds(config)
    checks.append({
        "id": "micro_cut_average_target",
        "ok": (
            2.0 <= average_target["min"] <= average_target["max"] <= 3.0
            and average_target["min"] <= ideal_seconds <= average_target["max"]
        ),
        "severity": "blocker",
        "message": "正文切图平均停留目标必须落在 2-3 秒内；life_sim 默认应靠近 2.6-3.0 秒，且 ideal 均值必须在目标区间内。",
    })
    relation_allowed = config.get("voice_visual_relation_allowed") or []
    checks.append({
        "id": "visual_storyline_continuity_required",
        "ok": (
            config.get("visual_continuity_required") is True
            and config.get("visual_storyline_required") is True
            and config.get("continuity_anchor_required_per_micro_cut") is True
            and config.get("voice_visual_relation_required_per_micro_cut") is True
            and {"direct", "parallel", "foreshadow"}.issubset(set(relation_allowed))
            and config.get("keyword_illustration_storyboard_forbidden") is True
        ),
        "severity": "blocker",
        "message": "正文画面必须有连续 visual_storyline、逐镜 continuity_anchor 和 direct/parallel/foreshadow 关系，禁止关键词插画式配图。",
    })
    mini_sequence_size = config.get("visual_mini_sequence_size") if isinstance(config.get("visual_mini_sequence_size"), dict) else {}
    checks.append({
        "id": "visual_mini_sequence_required",
        "ok": (
            config.get("visual_mini_sequence_required") is True
            and int(mini_sequence_size.get("min", 0)) <= 3
            and int(mini_sequence_size.get("max", 0)) >= 5
        ),
        "severity": "blocker",
        "message": "正文画面必须每 3-5 张图形成一个小连续动作，不能把每张图做成互不相干的关键词插画。",
    })
    sentence_policy = config.get("visual_cut_sentence_policy") if isinstance(config.get("visual_cut_sentence_policy"), dict) else {}
    preferred_sentences = sentence_policy.get("preferred_complete_sentences_per_cut") or []
    checks.append({
        "id": "voice_sentence_boundary_pacing_required",
        "ok": (
            config.get("voice_sentence_boundary_pacing_required") is True
            and int(sentence_policy.get("min_complete_sentences_per_cut", 0)) >= 1
            and 1 in preferred_sentences
            and 2 in preferred_sentences
            and sentence_policy.get("forbid_mid_sentence_cut") is True
            and sentence_policy.get("merge_short_sentences") is True
            and sentence_policy.get("long_sentence_policy") == "allow_multiple_visuals_at_semantic_clause_boundaries"
            and sentence_policy.get("long_sentence_multiple_visuals_allowed") is True
            and sentence_policy.get("require_same_sentence_visual_continuity") is True
        ),
        "severity": "blocker",
        "message": "正文换图必须贴着口播 sentence_boundary：至少完整说完 1 句，优先 1-2 句后切；超长句可在语义分句边界拆多个连续画面。",
    })
    checks.append({
        "id": "image2_budget_notice_before_generation",
        "ok": config.get("image2_budget_notice_required") is True,
        "severity": "blocker",
        "message": "正式生成前必须先估算并告知用户预计需要的独立 Image2 图片张数。",
    })
    motion_policy = config.get("motion_policy") if isinstance(config.get("motion_policy"), dict) else {}
    subtle_range = motion_policy.get("subtle_displacement_scale_range") or []
    checks.append({
        "id": "settled_body_motion_required",
        "ok": (
            motion_policy.get("body_motion_style") == "settled_hold"
            and motion_policy.get("default_body_frame_motion") == "static_hold"
            and motion_policy.get("allow_subtle_displacement") is True
            and isinstance(subtle_range, list)
            and len(subtle_range) == 2
            and 0 < float(subtle_range[0]) <= float(subtle_range[1]) <= 0.02
            and motion_policy.get("continuous_shake_forbidden") is True
            and motion_policy.get("opening_shake_scope") == "opening_only"
            and float(motion_policy.get("punctuation_shake_max_seconds", 9)) <= 0.25
            and motion_policy.get("body_motion_qa_required") is True
        ),
        "severity": "blocker",
        "message": "正片必须默认 settled_hold 稳定持镜：可轻微位移，但不能一直抖动；片头摇动不得延伸到正片。",
    })
    character_lock = config.get("character_lock") if isinstance(config.get("character_lock"), dict) else {}
    checks.append({
        "id": "character_lock_required",
        "ok": (
            character_lock.get("character_bible_required") is True
            and character_lock.get("character_reference_image_required") is True
            and character_lock.get("character_anchor_required_per_prompt") is True
            and character_lock.get("actor_state_required_per_micro_cut") is True
            and character_lock.get("reference_identity_not_pose_lock") is True
            and character_lock.get("contact_sheet_drift_review_required") is True
        ),
        "severity": "blocker",
        "message": "正片生成前必须有角色圣经和角色参考图；每个 Image2 prompt 与微切都要锁定同一角色状态并做漂移复查。",
    })
    visual_consistency = config.get("visual_consistency_contract") if isinstance(config.get("visual_consistency_contract"), dict) else {}
    checks.append({
        "id": "visual_consistency_contract_required",
        "ok": (
            visual_consistency.get("style_consistency_contract_required") is True
            and visual_consistency.get("prompt_compiler_required") is True
            and visual_consistency.get("prompt_style_hash_stable_required") is True
            and visual_consistency.get("strict_reference_lock_required") is True
            and visual_consistency.get("reference_failure_policy") == "fail_closed"
            and visual_consistency.get("soft_consistency_preview_requires_user_ack") is True
            and visual_consistency.get("style_consistency_report_required") is True
        ),
        "severity": "blocker",
        "message": "life_sim 必须使用共享 visual consistency contract：稳定 prompt_style_hash、严格参考图锁定、参考失败 fail-closed，并生成风格一致性报告。",
    })
    script_policy = config.get("script_quality_policy") if isinstance(config.get("script_quality_policy"), dict) else {}
    checks.append({
        "id": "viral_script_review_required",
        "ok": (
            int(script_policy.get("hook_variants_required", 0)) >= 3
            and script_policy.get("content_force_card_required") is True
            and script_policy.get("true_first_line_audit_required") is True
            and script_policy.get("enemy_or_pressure_source_required") is True
            and script_policy.get("ban_generic_advice") is True
            and script_policy.get("reference_style_brief_required_when_reference_path") is True
        ),
        "severity": "blocker",
        "message": "脚本必须先做 3 个 hook、content_force_card 和真实第一句审查；禁止泛泛建议和低压口播。",
    })
    reference_policy = config.get("reference_account_ingestion") if isinstance(config.get("reference_account_ingestion"), dict) else {}
    checks.append({
        "id": "reference_style_ingestion_supported",
        "ok": (
            reference_policy.get("reference_account_analysis_path_supported") is True
            and reference_policy.get("distill_patterns_only") is True
        ),
        "severity": "blocker",
        "message": "胶囊必须支持 reference_account_analysis_path，并只提炼结构、节奏、爽点和视觉模式，不照抄具体桥段。",
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
        "micro_cut_seconds": config.get("micro_cut_seconds", {}),
        "budget_notice": (
            f"按当前时长和 1-5 秒可变切图、平均 2.6-3.0 秒节奏，正文预计需要约 {image_count} 张独立 Image2 图片；"
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
        "budget_notice": notes["budget_notice"],
    }
    write_json(output_dir / "artifact_manifest.json", manifest)


def budget_ack_check(params: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "generation_budget_ack_required",
        "ok": config.get("image2_budget_notice_required") is not True or params.get("generation_budget_ack") is True,
        "severity": "blocker",
        "message": "正式生成前必须先把预计独立 Image2 图片张数告知用户，并设置 generation_budget_ack=true。",
    }


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

    ack_check = budget_ack_check(params, config)
    if not ack_check["ok"]:
        checks_with_ack = [*checks, ack_check]
        write_run_notes(
            output_dir=output_dir,
            topic=args.topic,
            params=params,
            config=config,
            checks=checks_with_ack,
            dry_run=args.dry_run,
        )
        report = json.loads((output_dir / "reports" / "run_notes.json").read_text(encoding="utf-8"))
        write_json(
            output_dir / "reports" / "run_notes.json",
            {
                **report,
                "ok": False,
                "error": "generation_budget_ack_required",
            },
        )
        write_dry_run_manifest(output_dir, {**report, "ok": False})
        return 2

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
