#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from env_loader import load_video_agent_env


_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent


def safe_slug(text: str, default: str = "douyin_account") -> str:
    """Create a safe filesystem segment, preferring the short Douyin URL code."""
    raw = str(text or "").strip()
    url_match = re.search(r"v\.douyin\.com/([A-Za-z0-9_-]+)", raw)
    if url_match:
        return url_match.group(1)

    normalized = raw.replace("账号", "account")
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", normalized).strip("_")
    if not slug:
        return default
    if not re.match(r"^[A-Za-z]", slug):
        slug = f"account_{slug}"
    return slug


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _url_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        urls = value.get("url_list") or value.get("urls") or value.get("url")
        return [str(item) for item in _as_list(urls) if str(item or "").strip()]
    return [str(item) for item in _as_list(value) if str(item or "").strip()]


def _nested_url_list(data: dict[str, Any], *keys: str) -> list[str]:
    current: Any = data
    for key in keys:
        current = _as_dict(current).get(key)
    return _url_list(current)


def extract_video_list(crawl_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract videos from common external crawler response shapes."""
    if not isinstance(crawl_result, dict):
        return []

    candidates: list[Any] = [
        crawl_result.get("video_list"),
        crawl_result.get("list"),
        crawl_result.get("aweme_list"),
    ]

    data = crawl_result.get("data")
    if isinstance(data, dict):
        candidates.extend([data.get("video_list"), data.get("list"), data.get("aweme_list")])
        nested = data.get("data")
        if isinstance(nested, dict):
            candidates.extend([nested.get("video_list"), nested.get("list"), nested.get("aweme_list")])

    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _extract_hashtags(text: str, item: dict[str, Any]) -> list[str]:
    tags = re.findall(r"#([^#\s]+)", text or "")
    text_extra = item.get("text_extra") or item.get("cha_list") or []
    for entry in _as_list(text_extra):
        if not isinstance(entry, dict):
            continue
        tag = entry.get("hashtag_name") or entry.get("cha_name") or entry.get("name")
        if tag:
            tags.append(str(tag))

    result: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        clean = str(tag).strip(" #，,。.!！?？:：;；")
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _author_info(item: dict[str, Any]) -> dict[str, Any]:
    author = _as_dict(item.get("author"))
    return {
        "uid": _as_text(author.get("uid") or author.get("sec_uid") or author.get("id")),
        "nickname": _as_text(author.get("nickname") or item.get("author_name") or item.get("nickname")),
        "signature": _as_text(author.get("signature")),
        "follower_count": _as_int(author.get("follower_count") or author.get("fans_count")),
    }


def _normalize_duration_ms(item: dict[str, Any], video: dict[str, Any]) -> int:
    raw = _as_int(item.get("duration") or video.get("duration"))
    if not raw:
        return 0
    if raw < 1000 and (item.get("video_url") or item.get("share_link")):
        return raw * 1000
    return raw


def normalize_video(item: dict[str, Any], index: int) -> dict[str, Any]:
    video = _as_dict(item.get("video"))
    stats = _as_dict(item.get("statistics") or item.get("stats"))
    description = _as_text(item.get("desc") or item.get("description") or item.get("title"))
    title = _as_text(item.get("title"), description[:60])
    duration_ms = _normalize_duration_ms(item, video)
    normalized_stats = {
        "digg_count": _as_int(stats.get("digg_count") or stats.get("like_count") or item.get("liked_count")),
        "comment_count": _as_int(stats.get("comment_count") or item.get("comment_count")),
        "share_count": _as_int(stats.get("share_count") or item.get("share_count")),
        "collect_count": _as_int(
            stats.get("collect_count") or stats.get("favorite_count") or item.get("collected_count")
        ),
        "play_count": _as_int(stats.get("play_count") or item.get("play_count")),
    }
    engagement_score = (
        normalized_stats["digg_count"]
        + normalized_stats["comment_count"]
        + normalized_stats["share_count"]
        + normalized_stats["collect_count"]
    )

    play_urls: list[str] = []
    cover_urls: list[str] = []
    for urls in (
        _url_list(item.get("video_url")),
        _url_list(item.get("play_url")),
        _url_list(item.get("share_url")),
        _url_list(item.get("share_link")),
        _nested_url_list(item, "play_addr"),
        _nested_url_list(item, "video", "play_addr"),
        _nested_url_list(item, "video", "download_addr"),
    ):
        play_urls.extend(urls)
    for urls in (
        _url_list(item.get("cover")),
        _url_list(item.get("thumbnail")),
        _url_list(item.get("pics")),
        _nested_url_list(item, "cover"),
        _nested_url_list(item, "video", "cover"),
        _nested_url_list(item, "video", "origin_cover"),
        _nested_url_list(item, "video", "dynamic_cover"),
    ):
        cover_urls.extend(urls)

    return {
        "index": index,
        "aweme_id": _as_text(item.get("aweme_id") or item.get("id")),
        "description": description,
        "title": title,
        "hashtags": _extract_hashtags(description, item),
        "create_time": item.get("create_time") or item.get("publish_time"),
        "create_time_iso": _timestamp_to_iso(item.get("create_time")),
        "duration_ms": duration_ms,
        "duration_seconds": round(duration_ms / 1000, 3) if duration_ms else 0,
        "stats": normalized_stats,
        "engagement_score": engagement_score,
        "author": _author_info(item),
        "play_urls": _dedupe(play_urls),
        "cover_urls": _dedupe(cover_urls),
        "raw_keys": sorted(str(key) for key in item.keys()),
    }


def _timestamp_to_iso(value: Any) -> str:
    timestamp = _as_int(value)
    if not timestamp:
        return ""
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return ""


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _top_counter(counter: Counter[str], limit: int = 12, key_name: str = "value") -> list[dict[str, Any]]:
    return [{key_name: value, "count": count} for value, count in counter.most_common(limit)]


def _phrase_candidates(description: str) -> list[str]:
    text = re.sub(r"#\S+", "", description or "")
    parts = re.split(r"[\s，。！？!?、；;：:\n]+", text)
    return [part.strip() for part in parts if 2 <= len(part.strip()) <= 18]


def summarize_videos(videos: list[dict[str, Any]]) -> dict[str, Any]:
    hashtag_counter: Counter[str] = Counter()
    author_counter: Counter[str] = Counter()
    phrase_counter: Counter[str] = Counter()
    missing: Counter[str] = Counter()
    durations = [video["duration_seconds"] for video in videos if video.get("duration_seconds")]

    pattern_counts = {
        "question_hooks": 0,
        "number_hooks": 0,
        "direct_address": 0,
        "contrast_or_negation": 0,
        "has_cover_url": 0,
        "has_play_url": 0,
    }

    for video in videos:
        hashtag_counter.update(video.get("hashtags") or [])
        nickname = _as_text(_as_dict(video.get("author")).get("nickname"))
        if nickname:
            author_counter[nickname] += 1
        else:
            missing["author.nickname"] += 1
        description = _as_text(video.get("description"))
        if not description:
            missing["description"] += 1
        phrase_counter.update(_phrase_candidates(description))
        if "?" in description or "？" in description or "吗" in description:
            pattern_counts["question_hooks"] += 1
        if re.search(r"\d|一|二|三|四|五|六|七|八|九|十", description):
            pattern_counts["number_hooks"] += 1
        if re.search(r"你|普通人|年轻人|女生|男生|老板|打工人", description):
            pattern_counts["direct_address"] += 1
        if re.search(r"别|不是|而是|但是|真正|千万|不要|只要", description):
            pattern_counts["contrast_or_negation"] += 1
        if video.get("cover_urls"):
            pattern_counts["has_cover_url"] += 1
        if video.get("play_urls"):
            pattern_counts["has_play_url"] += 1

    top_videos = sorted(videos, key=lambda item: item.get("engagement_score", 0), reverse=True)[:8]
    return {
        "video_count": len(videos),
        "account_nickname": author_counter.most_common(1)[0][0] if author_counter else "",
        "top_authors": _top_counter(author_counter, key_name="nickname"),
        "top_hashtags": _top_counter(hashtag_counter, key_name="tag"),
        "top_phrases": _top_counter(phrase_counter, key_name="phrase"),
        "top_videos": top_videos,
        "duration": {
            "min_seconds": min(durations) if durations else 0,
            "max_seconds": max(durations) if durations else 0,
            "avg_seconds": round(sum(durations) / len(durations), 2) if durations else 0,
        },
        "engagement": {
            "total_score": sum(video.get("engagement_score", 0) for video in videos),
            "avg_score": round(
                sum(video.get("engagement_score", 0) for video in videos) / len(videos), 2
            )
            if videos
            else 0,
        },
        "pattern_counts": pattern_counts,
        "missing_fields": dict(missing),
        "analysis_limits": [
            "metadata_only: 本次蒸馏主要基于爬虫返回的标题、描述、标签、统计和URL字段。",
            "未默认下载视频，因此镜头节奏、真人表演、口播逐字稿和剪辑细节只能作为有限推断。",
        ],
    }


def _format_duration(seconds: Any) -> str:
    total = int(round(float(seconds or 0)))
    minutes, rest = divmod(total, 60)
    return f"{minutes}:{rest:02d}"


def _duration_profile(summary: dict[str, Any]) -> str:
    duration = summary.get("duration", {})
    avg = duration.get("avg_seconds", 0)
    if avg >= 300:
        return (
            f"长讲解型内容，平均约 {_format_duration(avg)}，"
            f"区间 {_format_duration(duration.get('min_seconds', 0))}-{_format_duration(duration.get('max_seconds', 0))}"
        )
    if avg >= 90:
        return (
            f"中等时长讲解，平均约 {_format_duration(avg)}，"
            f"区间 {_format_duration(duration.get('min_seconds', 0))}-{_format_duration(duration.get('max_seconds', 0))}"
        )
    return (
        f"短视频讲解，平均约 {_format_duration(avg)}，"
        f"区间 {_format_duration(duration.get('min_seconds', 0))}-{_format_duration(duration.get('max_seconds', 0))}"
    )


def _title_formula_examples(summary: dict[str, Any]) -> list[str]:
    top_descriptions = [video.get("description", "") for video in summary.get("top_videos", [])]
    formulas: list[str] = []
    joined = "\n".join(top_descriptions)
    if "本质" in joined or "从来不是" in joined:
        formulas.append("`X 的本质，从来不是 A，而是 B`")
    if "最高" in joined or "顶级" in joined:
        formulas.append("`顶级/最高境界的 X：一句话重定义它`")
    if "一个人" in joined or "所有人" in joined:
        formulas.append("`一个人/所有人这一生，都在解决同一个底层问题`")
    if "为什么" in joined or "如何" in joined:
        formulas.append("`人为什么会 X？如何重建 Y`")
    if "看透" in joined or "识人" in joined:
        formulas.append("`从一个细节，看透关系/人性/时间/命运的底层逻辑`")
    if not formulas:
        formulas.append("`具体处境 + 反常识判断 + 底层逻辑`")
    return formulas


def _script_structure(summary: dict[str, Any]) -> list[str]:
    avg = summary.get("duration", {}).get("avg_seconds", 0)
    if avg >= 300:
        return [
            "0:00-0:20 直接抛出总论断：用“本质/最高境界/顶级法则”把问题抬高。",
            "0:20-1:30 否定普通理解：说明大众为什么把 A 当答案，但 A 只是表层。",
            "1:30-4:00 建立核心概念：创造或命名一个结构词，如“本体性自信”“信息环境设计”“结构型自律”。",
            "4:00-8:00 拆机制：用心理、人性、关系、命运、时间等高抽象框架解释为什么有效。",
            "8:00-12:00 给现实场景：饭局、低谷、关系场、拖延、焦虑、财富、识人等，把抽象概念落回生活。",
            "结尾 30-60 秒 收束成内在主权：告诉观众不是学技巧，而是在重建自己的内在人格系统。",
        ]
    return [
        "0-3 秒 直接点出痛点或误区，不铺背景。",
        "3-8 秒 给出一句反常识判断。",
        "8-20 秒 用一个具体场景证明判断。",
        "20-35 秒 给出 2-3 个动作或认知框架。",
        "结尾 用身份感收束，让观众觉得收藏是在保护自己。",
    ]


def _theme_lanes(summary: dict[str, Any]) -> list[dict[str, str]]:
    tags = [item["tag"] for item in summary.get("top_hashtags", [])]
    lanes = [
        ("个人成长/改变自己", "人格系统、内在主权、自律、自控力、长期主义"),
        ("心理/认知", "信念、自信、信息环境设计、低谷重建、焦虑处理"),
        ("人际交往/人性", "识人、吸引力、关系场、饭局价值、矛盾分析"),
        ("人生/命运/时间", "无常、意义、过去现在未来、低欲望社会"),
    ]
    result = []
    for name, angle in lanes:
        if any(part in tags for part in re.split(r"[/]", name)):
            result.append({"lane": name, "angle": angle})
    if result:
        return result
    return [{"lane": tag, "angle": "从一个具体处境切入，提炼出底层逻辑。"} for tag in tags[:5]]


def _probe_keyframe_paths(probe_report: Any) -> list[str]:
    probes: list[Any]
    if isinstance(probe_report, list):
        probes = probe_report
    elif isinstance(probe_report, dict):
        probes = _as_list(probe_report.get("top_video_probes") or probe_report.get("probes") or probe_report.get("items"))
    else:
        probes = []

    paths: list[str] = []
    for probe in probes:
        if not isinstance(probe, dict):
            continue
        for frame in _as_list(probe.get("frames")):
            if not isinstance(frame, dict):
                continue
            path = _as_text(frame.get("path"))
            if path:
                paths.append(path)
    return _dedupe(paths)


def build_presentation_recipe(
    videos: list[dict[str, Any]],
    summary: dict[str, Any],
    probe_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Infer reusable video presentation rules from metadata and optional probes."""
    keyframe_paths = _probe_keyframe_paths(probe_report)
    has_keyframes = bool(keyframe_paths)
    avg_duration = summary.get("duration", {}).get("avg_seconds", 0)
    long_explainer = avg_duration >= 300
    has_play_urls = summary.get("pattern_counts", {}).get("has_play_url", 0) > 0
    format_type = "minimal_text_card_explainer" if long_explainer or has_play_urls else "minimal_text_card_explainer"

    return {
        "schema_version": "douyin_account_presentation_recipe.v1",
        "format_type": format_type,
        "observed_or_inferred": "observed_from_metadata_and_keyframes" if has_keyframes else "metadata_inferred",
        "canvas": {
            "observed_size": "1080x1440",
            "recommended_output": "1080x1440",
            "douyin_safe_variant": "1080x1920 centered_card",
        },
        "layout": [
            "top_brand_area",
            "red_topic_line",
            "bold_black_core_sentence",
            "english_separator",
            "minimal_symbolic_illustration",
            "semantic_vector_metaphor",
            "small_disclaimer",
            "bottom_column_bar",
        ],
        "frame_grammar": {
            "top_area": "generic seal at upper left plus centered wordmark; never copy source account mark or handle",
            "topic_line": "muted red one-line thesis above the main verdict",
            "core_sentence": "one large black verdict, usually 1-2 lines, centered and readable before the illustration",
            "separator": "spaced Latin/pinyin-style line that acts as a visual divider, not source identity text",
            "middle_scene": "semantic SVG-like metaphor illustration occupying the middle-lower field",
            "bottom_band": "three-column gray system bar with thin vertical separators",
        },
        "palette": {
            "background": "white",
            "primary_text": "black",
            "accent": "muted_red_or_pink",
            "illustration": ["black", "gray", "red"],
            "bottom_bar": "light_gray",
        },
        "typography": {
            "core_sentence": "extra_bold_chinese_sans_large",
            "topic_line": "medium_bold_chinese_sans_red",
            "decorative_separator": "spaced_latin_caps",
            "body_subtitles": "optional_or_absent_when_card_text_is_primary",
        },
        "motion": [
            "mostly_static",
            "key_sentence_replacement",
            "vector_reveal",
            "red_accent_sweep",
            "subtle_fade_or_scale",
            "hard_cut_between_cards",
        ],
        "visual_component_library": {
            "required_families": [
                "person_silhouette",
                "red_path_or_arc",
                "environment_symbol",
                "system_panel",
            ],
            "optional_families": [
                "thought_cloud",
                "risk_radar",
                "threshold_gate",
                "timer_ring",
                "tree_sun_window",
                "desk_or_relationship_scene",
            ],
            "style_rules": [
                "flat black/red/gray vector shapes with stable stroke widths",
                "figures are silhouettes rather than stick figures",
                "silhouette bodies use shaped paths/polygons, not rectangle bodies with stick limbs",
                "red elements carry the mechanism or action path",
                "gray elements carry environment, uncertainty, or background structure",
                "each middle scene must explain the card sentence, not decorate it",
                "SVG assets should expose semantic component-family metadata for QA",
            ],
        },
        "semantic_illustration_map": [
            {
                "abstract_claim_type": "startup_cost_or_threshold",
                "metaphor": "small figure facing a lowered red path, threshold, gate, or heavy black block",
            },
            {
                "abstract_claim_type": "mental_load_or_inner_friction",
                "metaphor": "figure under black thought cloud with small red blocked path or pressure arcs",
            },
            {
                "abstract_claim_type": "uncertainty_or_risk",
                "metaphor": "half-brain, radar ring, warning arc, or signal lines in black/red/gray",
            },
            {
                "abstract_claim_type": "system_redesign",
                "metaphor": "control panel, sliders, reordered route, desk, or modular system frame",
            },
        ],
        "visual_quality_gates": [
            "keyframe_probe_required_for_visual_claims",
            "middle_semantic_svg_scene_required",
            "polished_vector_component_library_required",
            "animated_vector_reveal_required",
            "no_source_identity_visuals",
            "no_generic_icon_only_middle_scene",
            "contact_sheet_visual_review_required",
        ],
        "card_timing": {
            "recommended_seconds_per_card": [8, 18],
            "trial_video_duration_seconds": [90, 150],
            "full_video_duration_seconds": [360, 900],
        },
        "audio": {
            "voice": "mature_calm_chinese_voiceover",
            "bgm": "very_low_volume_minimal_pulse",
            "voice_priority": True,
        },
        "cover_formula": [
            "white_background",
            "red_topic_line",
            "one_bold_black_high_density_claim",
            "one_symbolic_black_gray_red_illustration",
        ],
        "implementation_route": "local_card_rendering_tts_ffmpeg",
        "implementation_steps": [
            "write_voiceover_script",
            "split_script_into_semantic_cards",
            "extract_one_core_sentence_per_card",
            "render_exact_text_cards_locally",
            "draw_semantic_svg_metaphor_illustrations",
            "export_svg_component_assets",
            "animate_red_accents_and_middle_scene_reveal",
            "generate_tts",
            "assemble_cards_to_audio_duration_with_ffmpeg",
            "add_low_bgm_and_package_public_copy",
        ],
        "avoid": [
            "do_not_copy_account_logo_or_name",
            "do_not_use_model_rendered_chinese_text",
            "do_not_turn_into_generic_ai_scene_video",
            "do_not_overanimate_transitions",
        ],
        "evidence": {
            "sample_count": len(videos),
            "keyframe_count": len(keyframe_paths),
            "keyframe_paths": keyframe_paths,
            "duration_profile": _duration_profile(summary),
            "top_video_descriptions": [
                video.get("description", "") for video in summary.get("top_videos", [])[:5]
            ],
        },
    }


def build_presentation_recipe_markdown(recipe: dict[str, Any], account_name: str = "") -> str:
    account = account_name or "目标账号"
    layout = "\n".join(f"- {item}" for item in recipe.get("layout", []))
    motion = "\n".join(f"- {item}" for item in recipe.get("motion", []))
    avoid = "\n".join(f"- {item}" for item in recipe.get("avoid", []))
    steps = "\n".join(
        f"{index}. {item}" for index, item in enumerate(recipe.get("implementation_steps", []), start=1)
    )
    palette = recipe.get("palette", {})
    canvas = recipe.get("canvas", {})
    card_timing = recipe.get("card_timing", {})
    component_library = recipe.get("visual_component_library", {})
    required_components = "\n".join(
        f"- {item}" for item in component_library.get("required_families", [])
    )
    optional_components = "\n".join(
        f"- {item}" for item in component_library.get("optional_families", [])
    )
    component_rules = "\n".join(f"- {item}" for item in component_library.get("style_rules", []))
    semantic_map = "\n".join(
        f"- {item.get('abstract_claim_type', '')}: {item.get('metaphor', '')}"
        for item in recipe.get("semantic_illustration_map", [])
        if isinstance(item, dict)
    )
    visual_quality_gates = "\n".join(f"- {item}" for item in recipe.get("visual_quality_gates", []))
    evidence = recipe.get("evidence", {})
    keyframe_paths = "\n".join(f"- {item}" for item in evidence.get("keyframe_paths", [])[:12])

    return "\n".join(
        [
            f"# {account} 视频呈现方式配方",
            "",
            "## 形式判断",
            "",
            f"- 类型: `{recipe.get('format_type', '')}`",
            f"- 画幅: `{canvas.get('observed_size', '')}`，推荐输出 `{canvas.get('recommended_output', '')}`",
            f"- 抖音安全版: `{canvas.get('douyin_safe_variant', '')}`",
            f"- 实现路线: `{recipe.get('implementation_route', '')}`",
            "",
            "## 版式结构",
            "",
            layout,
            "",
            "## 色彩",
            "",
            f"- 背景: {palette.get('background', '')}",
            f"- 主文字: {palette.get('primary_text', '')}",
            f"- 强调色: {palette.get('accent', '')}",
            f"- 插画色: {', '.join(palette.get('illustration', []))}",
            f"- 底栏: {palette.get('bottom_bar', '')}",
            "",
            "## 动效",
            "",
            motion,
            "",
            "## 中部 SVG 视觉组件库",
            "",
            "必备组件:",
            "",
            required_components,
            "",
            "可选组件:",
            "",
            optional_components,
            "",
            "风格规则:",
            "",
            component_rules,
            "",
            "## 语义插画映射",
            "",
            semantic_map,
            "",
            "## 视觉 QA 门槛",
            "",
            visual_quality_gates,
            "",
            "## 卡片节奏",
            "",
            f"- 单卡建议: {card_timing.get('recommended_seconds_per_card', [])} 秒",
            f"- 试播版时长: {card_timing.get('trial_video_duration_seconds', [])} 秒",
            f"- 完整版时长: {card_timing.get('full_video_duration_seconds', [])} 秒",
            "",
            "## 实现步骤",
            "",
            steps,
            "",
            "## 不能照搬",
            "",
            avoid,
            "",
            "## 关键帧证据",
            "",
            f"- 关键帧数量: {evidence.get('keyframe_count', 0)}",
            keyframe_paths,
            "",
        ]
    )


def build_account_distillation(
    url: str,
    range_str: str,
    videos: list[dict[str, Any]],
    summary: dict[str, Any],
    analysis_mode: str = "metadata_only",
    keyframe_count: int = 0,
) -> str:
    account = summary.get("account_nickname") or "未知账号"
    top_tags = ", ".join(item["tag"] for item in summary.get("top_hashtags", [])[:8]) or "标签不足"
    top_phrases = " / ".join(item["phrase"] for item in summary.get("top_phrases", [])[:8]) or "短语不足"
    pattern_counts = summary.get("pattern_counts", {})
    duration = summary.get("duration", {})
    top_examples = _markdown_video_examples(summary.get("top_videos", []))
    formulas = "\n".join(f"- {formula}" for formula in _title_formula_examples(summary))
    lanes = "\n".join(f"- {item['lane']}: {item['angle']}" for item in _theme_lanes(summary))

    return "\n".join(
        [
            f"# {account} 账号蒸馏",
            "",
            "## 数据范围",
            "",
            f"- 来源链接: `{url}`",
            f"- 抓取范围: `{range_str}`",
            f"- 样本数: {summary.get('video_count', 0)}",
            f"- 分析模式: `{analysis_mode}`",
            f"- 关键帧证据数: {keyframe_count}",
            "",
            "## 账号画像",
            "",
            f"这个账号的可见内容更适合被理解为一个围绕 `{top_tags}` 展开的深度成长/心理讲解账号。它不是轻建议型短视频，而是把普通处境拔高为“本质、顶级法则、最高境界、底层逻辑”的长讲解内容。",
            "",
            "## 内容母题",
            "",
            f"- 高频标签: {top_tags}",
            f"- 高频描述短语: {top_phrases}",
            "- 高互动内容优先复用“抽象大问题 + 关系/心理/命运机制 + 内在重建”的组合。",
            "",
            "## 可复用栏目车道",
            "",
            lanes,
            "",
            "## 钩子与标题模式",
            "",
            f"- 疑问式开头样本数: {pattern_counts.get('question_hooks', 0)}",
            f"- 数字/步骤感样本数: {pattern_counts.get('number_hooks', 0)}",
            f"- 直接点名观众样本数: {pattern_counts.get('direct_address', 0)}",
            f"- 反差/否定式表达样本数: {pattern_counts.get('contrast_or_negation', 0)}",
            "",
            "可复用标题公式:",
            "",
            formulas,
            "",
            "## 视频格式线索",
            "",
            f"- 时长画像: {_duration_profile(summary)}",
            f"- 平均时长: {_format_duration(duration.get('avg_seconds', 0))}",
            f"- 最短/最长: {_format_duration(duration.get('min_seconds', 0))} / {_format_duration(duration.get('max_seconds', 0))}",
            f"- 有封面 URL 的样本数: {pattern_counts.get('has_cover_url', 0)}",
            f"- 有播放 URL 的样本数: {pattern_counts.get('has_play_url', 0)}",
            "",
            "## 高互动样本",
            "",
            top_examples,
            "",
            "## 局限",
            "",
            "- metadata_only 模式只基于标题、描述、标签、统计和 URL 字段，不对完整镜头语言、字幕设计、口播节奏做强断言。",
            "- metadata_plus_visual_probe 模式会读取外部关键帧 probe 报告，用于呈现方式、版式、SVG 隐喻和动效语法蒸馏；它仍然只复用机制，不复制原视频帧或账号身份素材。",
            "- 报告中的账号定位是从公开元数据推断，不等同于账号后台人群数据。",
            "- 后续如果要做更像的成片，应抽取 3-5 条代表视频做逐帧和逐字稿复核。",
            "",
        ]
    )


def build_replication_recipe(
    url: str,
    range_str: str,
    videos: list[dict[str, Any]],
    summary: dict[str, Any],
    presentation_recipe: dict[str, Any] | None = None,
    analysis_mode: str = "metadata_only",
) -> str:
    del videos
    account = summary.get("account_nickname") or "目标账号"
    lane_items = _theme_lanes(summary)
    primary_lane = lane_items[0]["lane"] if lane_items else "个人成长/心理"
    formulas = _title_formula_examples(summary)
    structure = _script_structure(summary)
    presentation = presentation_recipe or build_presentation_recipe([], summary)

    return "\n".join(
        [
            f"# {account} 复刻配方",
            "",
            "## 使用边界",
            "",
            f"- 参考来源: `{url}`",
            f"- 样本范围: `{range_str}`",
            "- 复刻目标: 复用账号的方法论、选题结构、包装节奏，不复制原视频内容。",
            f"- 分析模式: `{analysis_mode}`。metadata_plus_visual_probe 可用于抽取版式、SVG 隐喻、动效和关键帧 QA；metadata_only 只适合作第一版内容结构配方。",
            "",
            "## 账号定位公式",
            "",
            f"`给关注 {primary_lane} 的人 -> 一个高抽象命题 -> 一个重新解释世界/关系/自我的底层框架`",
            "",
            "## 选题池",
            "",
            *[f"- {item['lane']}: {item['angle']}。" for item in lane_items],
            "",
            "## 标题公式",
            "",
            *[f"- {formula}" for formula in formulas],
            "",
            "## 单条视频脚本结构",
            "",
            *[f"{index}. {line}" for index, line in enumerate(structure, start=1)],
            "",
            "## 文案质感",
            "",
            "- 高频词库: 本质、顶级、最高境界、底层逻辑、内在、人格系统、主权、无常、结构、看透。",
            "- 每条都要有一个“命名概念”，让观众觉得不是普通建议，而是一套可收藏的方法论。",
            "- 语言要像深度拆解，不像鸡汤；观点可以锋利，但结论要回到自我建设。",
            "",
            "## 视频呈现方式",
            "",
            f"- 类型: `{presentation.get('format_type', '')}`",
            f"- 实现路线: `{presentation.get('implementation_route', '')}`",
            "- 核心形式: 白底图文知识卡 + 红色主题句 + 超大黑体判断 + 黑灰红隐喻插画。",
            "- 中部图形: 必须是语义 SVG 隐喻图，不是装饰图标；每张卡要把抽象判断转成可看懂的结构画面。",
            "- 组件体系: 人物剪影、红色路径/圆环、环境符号、系统面板是必备组件；思绪云、风险雷达、门槛、计时环、树/太阳/窗口按主题选用。",
            "- 运动方式: 主要靠关键句替换、红色路径/圆环绘制、中部图形揭示和硬切，不靠复杂镜头运动。",
            "- 生产路线: 本地精确渲染文字卡片，再用 TTS 和 ffmpeg 合成。",
            "- 视觉 QA: 生成前必须有关键帧或参考帧证据；成片前必须检查中部 SVG、首 3 秒、contact sheet 和 source identity 泄漏。",
            "",
            "## 封面与包装公式",
            "",
            "- 封面: 只放一个高密度命题，例如“自信的本质不是相信自己”。",
            "- 标题: 用“本质/顶级/最高境界/所有人这一生”制造收藏感。",
            "- 标签: 选择 2-4 个稳定垂类标签，不把每条都塞成泛流量标签。",
            "",
            "## 生产流程",
            "",
            "1. 从选题池挑一个大命题，再找 2-3 个生活场景验证它。",
            "2. 先写标题，再反推口播结构；标题不强，正文先别写。",
            "3. 每条至少准备一个原创概念名和一个反常识对照。",
            "4. 按长讲解节奏写稿，不要压成 60 秒建议流。",
            "5. 发布后重点看收藏、转发、评论长问题，而不只看点赞。",
            "",
            "## 风险控制",
            "",
            "- 避免直接羞辱、绝对化承诺、医疗/法律/金融式硬建议。",
            "- 冲突表达用“误区、没结果、被现实打醒、第一眼没过关”等更稳的措辞。",
            "- 不搬运原账号标题和画面，只复用结构。",
            "",
        ]
    )


def build_recipe_seed(
    url: str,
    range_str: str,
    videos: list[dict[str, Any]],
    summary: dict[str, Any],
    presentation_recipe: dict[str, Any] | None = None,
    analysis_mode: str = "metadata_only",
) -> dict[str, Any]:
    top_tags = [item["tag"] for item in summary.get("top_hashtags", [])[:8]]
    top_phrases = [item["phrase"] for item in summary.get("top_phrases", [])[:8]]
    presentation = presentation_recipe or build_presentation_recipe(videos, summary)
    return {
        "schema_version": "douyin_account_replication_seed.v1",
        "source": {
            "platform": "douyin",
            "url": url,
            "range": range_str,
            "sample_size": len(videos),
            "analysis_mode": analysis_mode,
        },
        "account": {
            "nickname": summary.get("account_nickname", ""),
            "top_authors": summary.get("top_authors", []),
        },
        "signals": {
            "top_hashtags": top_tags,
            "top_phrases": top_phrases,
            "duration": summary.get("duration", {}),
            "engagement": summary.get("engagement", {}),
            "pattern_counts": summary.get("pattern_counts", {}),
        },
        "recipe": {
            "positioning": "高抽象成长/心理命题 + 底层逻辑重解释 + 内在主权收束",
            "duration_profile": _duration_profile(summary),
            "content_lanes": _theme_lanes(summary),
            "hook_patterns": _title_formula_examples(summary),
            "structure": _script_structure(summary),
            "copy_rules": [
                "每条必须命名一个核心概念",
                "标题使用本质、顶级、最高境界、底层逻辑等收藏型词汇",
                "先抽象后落地，避免全程泛泛讲道理",
            ],
            "visual_rules": [
                "优先让画面证明场景和情绪",
                "封面只承载一个冲突句",
                "字幕不遮挡脸和关键动作",
            ],
            "quality_rules": [
                "前 3 秒必须能独立成立",
                "不得照搬原账号标题和口播",
                "缺少逐帧分析时不要强断言镜头风格",
            ],
        },
        "presentation_recipe": presentation,
    }


def _markdown_video_examples(videos: list[dict[str, Any]]) -> str:
    if not videos:
        return "- 样本不足。"
    lines: list[str] = []
    for video in videos[:8]:
        stats = video.get("stats", {})
        desc = video.get("description") or "(无描述)"
        lines.append(
            f"- #{video.get('index')} score={video.get('engagement_score', 0)} "
            f"赞={stats.get('digg_count', 0)} 评={stats.get('comment_count', 0)} 转={stats.get('share_count', 0)}: {desc}"
        )
    return "\n".join(lines)


def _write_json(path: Path, value: Any) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def _write_text(path: Path, value: str) -> Path:
    path.write_text(value.rstrip() + "\n", encoding="utf-8")
    return path


def _write_yaml(path: Path, value: Any) -> Path:
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def _artifact_manifest(output_dir: Path, artifacts: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema_version": "capsule_cinema.account_distillation_manifest.v1",
        "output_dir": str(output_dir),
        "artifacts": artifacts,
    }


def _load_env(dotenv_path: str | Path | None) -> None:
    if dotenv_path:
        os.environ["DOTENV_PATH"] = str(Path(dotenv_path).expanduser())
    load_video_agent_env(_SKILL_DIR)


def _load_probe_report(probe_report: Any) -> Any:
    if isinstance(probe_report, (dict, list)) or probe_report is None:
        return probe_report
    path = Path(str(probe_report)).expanduser()
    if not path.is_file():
        raise SystemExit(f"probe report not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _external_crawler_factory(external_video_workflow_root: str | Path | None) -> Callable[[], Any]:
    if not external_video_workflow_root:
        raise SystemExit("--external-video-workflow-root is required for live crawling")
    root = Path(external_video_workflow_root).expanduser()
    package_root = root / "backend" / "video_workflow"
    if not package_root.is_dir():
        raise SystemExit(f"external video workflow package not found: {package_root}")
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from custom_tools.content_crawler import DouyinBloggerCrawlerTool

    return DouyinBloggerCrawlerTool


def _make_output_dir(output_base_dir: str | Path | None, url: str, timestamp: str | None) -> Path:
    if output_base_dir:
        base = Path(output_base_dir).expanduser()
    else:
        base = Path(os.getenv("OPENCLAW_OUTPUT_DIR") or (_SKILL_DIR / "output")) / "account_distillations"
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = base / f"{safe_slug(url)}_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def _write_error_artifacts(output_dir: Path, crawl_result: dict[str, Any], error: str) -> dict[str, Any]:
    raw_path = _write_json(output_dir / "raw_crawl_response.json", crawl_result)
    error_path = _write_text(
        output_dir / "error_report.md",
        "\n".join(["# Douyin Account Distillation Error", "", error, ""]),
    )
    manifest = _artifact_manifest(
        output_dir,
        [
            {"category": "raw_crawl_response", "path": str(raw_path), "title": "Raw crawl response"},
            {"category": "error_report", "path": str(error_path), "title": "Error report"},
        ],
    )
    manifest_path = _write_json(output_dir / "artifact_manifest.json", manifest)
    return {
        "success": False,
        "analysis_mode": "metadata_only",
        "output_dir": str(output_dir),
        "raw_crawl_response_path": str(raw_path),
        "error_report_path": str(error_path),
        "artifact_manifest_path": str(manifest_path),
        "error": error,
    }


def run_distillation(
    *,
    url: str,
    range_str: str = "0-19",
    output_base_dir: str | Path | None = None,
    external_video_workflow_root: str | Path | None = None,
    dotenv_path: str | Path | None = None,
    crawler_factory: Callable[[], Any] | None = None,
    timestamp: str | None = None,
    probe_report: Any = None,
) -> dict[str, Any]:
    _load_env(dotenv_path)
    loaded_probe_report = _load_probe_report(probe_report)
    analysis_mode = "metadata_plus_visual_probe" if _probe_keyframe_paths(loaded_probe_report) else "metadata_only"
    output_dir = _make_output_dir(output_base_dir, url, timestamp)
    factory = crawler_factory or _external_crawler_factory(external_video_workflow_root)
    crawler = factory()
    crawl_result = crawler._run(url=url, range=range_str)

    raw_path = _write_json(output_dir / "raw_crawl_response.json", crawl_result)
    if not isinstance(crawl_result, dict) or not crawl_result.get("success"):
        error = _as_text(_as_dict(crawl_result).get("error"), "crawler returned an unsuccessful response")
        return _write_error_artifacts(output_dir, _as_dict(crawl_result), error)

    raw_videos = extract_video_list(crawl_result)
    videos = [normalize_video(item, index) for index, item in enumerate(raw_videos, start=1)]
    summary = summarize_videos(videos)
    presentation = build_presentation_recipe(videos, summary, probe_report=loaded_probe_report)

    video_index = {
        "schema_version": "capsule_cinema.douyin_video_index.v1",
        "source": {"platform": "douyin", "url": url, "range": range_str},
        "summary": summary,
        "videos": videos,
    }
    index_path = _write_json(output_dir / "video_index.json", video_index)
    distillation_path = _write_text(
        output_dir / "account_distillation.md",
        build_account_distillation(
            url,
            range_str,
            videos,
            summary,
            analysis_mode=analysis_mode,
            keyframe_count=len(_probe_keyframe_paths(loaded_probe_report)),
        ),
    )
    recipe_path = _write_text(
        output_dir / "replication_recipe.md",
        build_replication_recipe(url, range_str, videos, summary, presentation, analysis_mode=analysis_mode),
    )
    presentation_json_path = _write_json(
        output_dir / "presentation_recipe.json",
        presentation,
    )
    presentation_md_path = _write_text(
        output_dir / "presentation_recipe.md",
        build_presentation_recipe_markdown(presentation, summary.get("account_nickname", "")),
    )
    seed_path = _write_yaml(
        output_dir / "recipe_seed.yaml",
        build_recipe_seed(url, range_str, videos, summary, presentation, analysis_mode=analysis_mode),
    )
    manifest = _artifact_manifest(
        output_dir,
        [
            {"category": "raw_crawl_response", "path": str(raw_path), "title": "Raw crawl response"},
            {"category": "video_index", "path": str(index_path), "title": "Normalized video index"},
            {"category": "account_distillation", "path": str(distillation_path), "title": "Account distillation"},
            {"category": "replication_recipe", "path": str(recipe_path), "title": "Replication recipe"},
            {"category": "presentation_recipe", "path": str(presentation_md_path), "title": "Presentation recipe"},
            {"category": "presentation_recipe_json", "path": str(presentation_json_path), "title": "Presentation recipe JSON"},
            {"category": "recipe_seed", "path": str(seed_path), "title": "Recipe seed"},
        ],
    )
    manifest_path = _write_json(output_dir / "artifact_manifest.json", manifest)

    return {
        "success": True,
        "analysis_mode": analysis_mode,
        "output_dir": str(output_dir),
        "video_count": len(videos),
        "raw_crawl_response_path": str(raw_path),
        "video_index_path": str(index_path),
        "account_distillation_path": str(distillation_path),
        "replication_recipe_path": str(recipe_path),
        "presentation_recipe_path": str(presentation_md_path),
        "presentation_recipe_json_path": str(presentation_json_path),
        "recipe_seed_path": str(seed_path),
        "artifact_manifest_path": str(manifest_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Distill a Douyin account into standalone recipe artifacts.")
    parser.add_argument("--url", required=True, help="Douyin account/profile/share URL")
    parser.add_argument("--range", default="0-19", dest="range_str", help="Video range, for example 0-19")
    parser.add_argument("--output-base-dir", default="", help="Base directory for account distillation outputs")
    parser.add_argument("--external-video-workflow-root", default="", help="Path to /Users/.../video_workflow")
    parser.add_argument("--dotenv-path", default="", help="Optional .env path containing XIAOLVFANG_API_TOKEN")
    parser.add_argument("--probe-report", default="", help="Optional JSON report with sampled keyframe paths")
    args = parser.parse_args()

    result = run_distillation(
        url=args.url,
        range_str=args.range_str,
        output_base_dir=args.output_base_dir or None,
        external_video_workflow_root=args.external_video_workflow_root or None,
        dotenv_path=args.dotenv_path or None,
        probe_report=args.probe_report or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
