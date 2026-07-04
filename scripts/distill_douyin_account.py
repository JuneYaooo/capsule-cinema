#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
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
        formulas.append("`具体对象/处境 + 明确结果/冲突 + 可验证看点`")
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
    return [{"lane": tag, "angle": "围绕该标签设计具体情境、冲突、证据和观众收益。"} for tag in tags[:5]]


def _definition_key_from_presentation(presentation: dict[str, Any]) -> str:
    format_type = str(presentation.get("format_type") or "unknown_or_hybrid")
    if format_type == "minimal_text_card_explainer":
        return "knowledge_card_explainer"
    return format_type if format_type in FORMAT_DEFINITIONS else "unknown_or_hybrid"


def _format_positioning_formula(format_key: str, primary_lane: str) -> str:
    if format_key == "product_showcase":
        return f"`给正在关注 {primary_lane} 的人 -> 一个真实使用场景 -> 一组可视化证据 -> 一个买/不买/怎么选判断`"
    if format_key == "story_drama":
        return f"`给会被 {primary_lane} 场景吸引的人 -> 一个关系冲突 -> 一个反转选择 -> 一个情绪余味`"
    if format_key == "tutorial_screen_recording":
        return f"`给需要解决 {primary_lane} 问题的人 -> 一个结果预览 -> 一条可复现步骤 -> 一个最终成果`"
    if format_key == "shop_or_local_life":
        return f"`给想判断 {primary_lane} 是否值得去的人 -> 到店证据 -> 价格/体验细节 -> 清晰结论`"
    if format_key == "ai_visual_story":
        return f"`给喜欢 {primary_lane} 视觉想象的人 -> 世界观钩子 -> 连续分镜 -> 一个记忆画面`"
    if format_key == "clip_commentary":
        return f"`给关注 {primary_lane} 的人 -> 一个高能片段 -> 一条原创解读 -> 一个可转述观点`"
    if format_key == "asmr_or_sensory":
        return f"`给需要 {primary_lane} 感官体验的人 -> 一个声音/动作钩子 -> 稳定循环 -> 舒适收束`"
    if format_key == "talking_head_explainer":
        return f"`给关注 {primary_lane} 的人 -> 一个强观点 -> 一个解释框架 -> 一个可执行判断`"
    if format_key == "knowledge_card_explainer":
        return f"`给关注 {primary_lane} 的人 -> 一个高抽象命题 -> 一个重新解释问题的结构框架`"
    return f"`给关注 {primary_lane} 的人 -> 一个明确停止理由 -> 一套可复用内容机制 -> 一个可验证输出`"


def _format_script_structure(format_key: str, summary: dict[str, Any]) -> list[str]:
    if format_key == "product_showcase":
        return [
            "0-3 秒 直接亮出产品和最强使用结果/最大槽点，不从品牌背景讲起。",
            "3-8 秒 给出本条判断：适合谁、不适合谁、解决什么具体问题。",
            "8-20 秒 展示真实使用场景或手部演示，让卖点有画面证据。",
            "20-35 秒 做对比、细节特写、优缺点或价格/规格上下文。",
            "结尾 用一句清晰结论收束：值得买、谨慎买、适合某类人，避免绝对承诺。",
        ]
    if format_key == "story_drama":
        return [
            "0-3 秒 抛出人物关系和冲突瞬间，让观众立刻知道谁在为难谁。",
            "3-10 秒 建立误会、试探、压力或利益矛盾。",
            "10-35 秒 用动作和对白推进冲突，不用旁白解释全部背景。",
            "中后段 安排反转证据或身份揭示，让前面的冲突被重新理解。",
            "结尾 留一个情绪判断或关系余味，而不是机械说教。",
        ]
    if format_key == "tutorial_screen_recording":
        return [
            "0-3 秒 先展示最终效果或失败痛点。",
            "3-8 秒 说明适用场景和所需工具。",
            "8-40 秒 按屏幕操作步骤推进，每步只讲一个动作。",
            "关键步骤 用放大、高亮、暂停帧避免用户看丢。",
            "结尾 回到最终结果，并提示最容易出错的一步。",
        ]
    if format_key == "shop_or_local_life":
        return [
            "0-3 秒 给出是否值得去/最特别的到店证据。",
            "3-10 秒 建立地点、排队、人均、环境或招牌产品。",
            "10-35 秒 展示核心体验细节：入口、菜单、制作、口感、服务或避坑点。",
            "中后段 用价格、等待时间、分量、对比对象支撑判断。",
            "结尾 给适合人群和不适合人群，不做无依据夸张承诺。",
        ]
    if format_key == "knowledge_card_explainer":
        return _script_structure(summary)
    return [
        "0-3 秒 直接给出该类型最强停止理由。",
        "3-8 秒 明确本条视频的判断、冲突、结果或承诺边界。",
        "8-35 秒 用该类型的核心证据推进：画面、动作、步骤、对白、产品、声音或场景。",
        "中后段 放大一个可记忆细节，让观众能转述。",
        "结尾 给结论、余味或下一步动作，但不复制原账号话术。",
    ]


def _format_copy_rules(format_key: str) -> list[str]:
    if format_key == "product_showcase":
        return [
            "文案优先说使用结果、适合人群、限制条件和证据，不堆抽象价值观。",
            "每个卖点最好对应一个可见演示、对比、细节特写或真实使用场景。",
            "避免绝对化功效、虚假价格、夸张保证和无法核验的数据。",
        ]
    if format_key == "story_drama":
        return [
            "文案优先制造人物关系、处境压力和反转期待。",
            "对白要推动冲突，少用解释型旁白替代戏剧行动。",
            "避免低俗猎奇、过度羞辱、家庭伦理极端化和误导性封面。",
        ]
    if format_key == "tutorial_screen_recording":
        return [
            "文案优先说结果和步骤，不用空泛形容词。",
            "每一步只交代一个屏幕动作，口播和画面必须同步。",
            "避免伪造软件能力、隐藏前置条件或跳过关键步骤。",
        ]
    if format_key == "knowledge_card_explainer":
        return [
            "每条可以命名一个核心概念，但必须服务本条观点。",
            "标题使用反常识、重定义或结构化判断制造收藏感。",
            "先抽象后落地，避免全程泛泛讲道理。",
        ]
    return [
        "文案必须服务该视频类型的停留理由，而不是套用固定成长话术。",
        "每个核心判断都要对应画面、声音、步骤、对白或数据证据。",
        "不得照搬原账号标题、口播、人物、logo、画面或水印。",
    ]


def _format_visual_lines(presentation: dict[str, Any]) -> list[str]:
    components = ", ".join(presentation.get("visual_component_library", {}).get("required_families", []))
    return [
        f"- 类型: `{presentation.get('format_type', '')}`",
        f"- 实现路线: `{presentation.get('implementation_route', '')}`",
        f"- 核心版式/镜头: {', '.join(presentation.get('layout', []))}",
        f"- 必备视觉组件: {components or '待 probe 确认'}",
        f"- 运动方式: {', '.join(presentation.get('motion', []))}",
        "- 视觉 QA: 按该类型 quality gates 检查首 3 秒、contact sheet、源身份泄漏和证据一致性。",
    ]


def _format_cover_rules(format_key: str) -> list[str]:
    if format_key == "product_showcase":
        return [
            "- 封面: 产品主体 + 一个使用结果/避坑判断 + 关键证据点。",
            "- 标题: `产品/场景 + 实测判断 + 适合/不适合谁`。",
            "- 标签: 产品品类、使用场景、测评/开箱/好物，不乱塞无关热词。",
        ]
    if format_key == "story_drama":
        return [
            "- 封面: 人物关系 + 冲突瞬间 + 反转期待。",
            "- 标题: `关系/处境 + 异常动作 + 结局悬念`。",
            "- 标签: 短剧、剧情垂类、关系场景，不用虚假社会新闻口吻。",
        ]
    if format_key == "tutorial_screen_recording":
        return [
            "- 封面: 最终效果 + 工具/场景 + 明确收益。",
            "- 标题: `用 X 做到 Y / 解决 Z 的步骤`。",
            "- 标签: 工具名、教程、场景，避免标题党。",
        ]
    return [
        "- 封面: 只放一个该类型最强停止理由。",
        "- 标题: 让观众知道冲突、结果、证据或收益。",
        "- 标签: 选择 2-4 个稳定垂类标签，不把每条都塞成泛流量标签。",
    ]


FORMAT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "knowledge_card_explainer": {
        "label": "知识卡/图文讲解",
        "implementation_route": "local_card_rendering_tts_ffmpeg",
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
        "motion": ["mostly_static", "key_sentence_replacement", "vector_reveal", "red_accent_sweep", "hard_cut_between_cards"],
        "required_families": ["person_silhouette", "red_path_or_arc", "environment_symbol", "system_panel"],
        "quality_gates": [
            "keyframe_probe_required_for_visual_claims",
            "middle_semantic_svg_scene_required",
            "polished_vector_component_library_required",
            "animated_vector_reveal_required",
            "no_source_identity_visuals",
            "no_generic_icon_only_middle_scene",
            "contact_sheet_visual_review_required",
        ],
        "capsule_capabilities": ["local_card_rendering", "semantic_vector_metaphor", "animated_card_reveal", "tts", "bgm"],
        "quality_gate_profile": "knowledge_card_release",
    },
    "talking_head_explainer": {
        "label": "真人/半身口播讲解",
        "implementation_route": "talking_head_script_tts_or_original_audio_edit",
        "layout": ["face_or_half_body_anchor", "subtitle_safe_area", "supporting_broll_or_callout", "cover_claim"],
        "motion": ["jump_cut", "punch_in", "caption_emphasis", "broll_insert"],
        "required_families": ["speaker_anchor", "subtitle_system", "broll_insert", "emphasis_caption"],
        "quality_gates": ["speaker_identity_consistency_required", "subtitle_readability_required", "first_three_seconds_hook_required", "audio_intelligibility_required"],
        "capsule_capabilities": ["talking_head_editing", "subtitle_packaging", "broll_planning", "tts_or_original_audio", "bgm"],
        "quality_gate_profile": "talking_head_release",
    },
    "story_drama": {
        "label": "剧情/短剧/反转叙事",
        "implementation_route": "scene_storyboard_character_continuity_video",
        "layout": ["conflict_scene_setup", "character_blocking", "dialogue_or_subtitle_beats", "turning_point_closeup", "reaction_cut"],
        "motion": ["shot_reverse_shot", "reaction_cut", "tension_hold", "reveal_cut"],
        "required_families": ["character_blocking", "conflict_location", "reaction_closeup", "continuity_anchor"],
        "quality_gates": ["scene_continuity_review_required", "character_consistency_required", "conflict_clear_in_first_three_seconds", "reaction_cut_required"],
        "capsule_capabilities": ["storyboard", "character_lock", "scene_continuity", "dialogue_subtitles", "sfx"],
        "quality_gate_profile": "story_drama_release",
    },
    "product_showcase": {
        "label": "产品展示/开箱/测评/种草",
        "implementation_route": "demonstration_evidence_sequence",
        "layout": ["product_closeup", "use_case_demonstration", "before_after_or_comparison", "feature_callout", "trust_or_price_context"],
        "motion": ["hands_on_demo", "macro_detail_cut", "comparison_cut", "benefit_callout"],
        "required_families": ["product_closeup", "hands_or_usage_scene", "feature_callout", "comparison_evidence"],
        "quality_gates": ["product_visible_in_first_three_seconds", "claim_evidence_alignment_required", "price_or_offer_consistency_if_present", "no_unverified_absolute_claims"],
        "capsule_capabilities": ["product_closeup", "demo_sequence", "claim_evidence_mapping", "cover_packaging", "bgm"],
        "quality_gate_profile": "product_showcase_release",
    },
    "tutorial_screen_recording": {
        "label": "教程/录屏/步骤演示",
        "implementation_route": "screen_recording_step_by_step_edit",
        "layout": ["problem_result_preview", "screen_focus_area", "step_caption", "cursor_or_highlight", "final_result"],
        "motion": ["screen_zoom", "cursor_highlight", "step_cut", "result_reveal"],
        "required_families": ["screen_capture", "cursor_highlight", "step_caption", "result_preview"],
        "quality_gates": ["steps_readable_required", "screen_area_not_cropped", "result_preview_required", "no_fake_ui_claims"],
        "capsule_capabilities": ["screen_recording", "step_subtitles", "cursor_highlight", "zoom_pan", "qa_readability"],
        "quality_gate_profile": "tutorial_release",
    },
    "shop_or_local_life": {
        "label": "探店/本地生活",
        "implementation_route": "location_experience_review_sequence",
        "layout": ["storefront_or_arrival", "environment_scan", "product_or_food_closeup", "price_or_queue_context", "verdict"],
        "motion": ["walk_in", "handheld_pan", "macro_detail_cut", "reaction_or_verdict"],
        "required_families": ["location_anchor", "environment_detail", "consumption_proof", "verdict_caption"],
        "quality_gates": ["location_context_clear_required", "price_claim_consistency_if_present", "no_hidden_ad_mislead", "privacy_review_required"],
        "capsule_capabilities": ["location_sequence", "review_copy", "price_context", "privacy_blur", "bgm"],
        "quality_gate_profile": "local_life_release",
    },
    "ai_visual_story": {
        "label": "AI 视觉/分镜故事",
        "implementation_route": "ai_storyboard_image_video_generation",
        "layout": ["world_setting", "character_or_subject_anchor", "scene_progression", "visual_reveal", "ending_image"],
        "motion": ["image_to_video_motion", "camera_push", "scene_transition", "atmosphere_shift"],
        "required_families": ["style_anchor", "character_anchor", "scene_keyframe", "motion_prompt"],
        "quality_gates": ["style_consistency_required", "character_anchor_required", "no_garbled_model_text", "synthetic_media_label_if_needed"],
        "capsule_capabilities": ["image_generation", "image_to_video", "storyboard", "style_reference", "tts", "bgm"],
        "quality_gate_profile": "ai_visual_story_release",
    },
    "clip_commentary": {
        "label": "混剪/解说/评论",
        "implementation_route": "source_clip_commentary_edit",
        "layout": ["source_clip_context", "commentary_caption", "evidence_moment", "reaction_or_takeaway"],
        "motion": ["cold_open_clip", "freeze_frame_callout", "zoom_replay", "commentary_cut"],
        "required_families": ["source_clip_segment", "commentary_track", "callout_caption", "rights_context"],
        "quality_gates": ["source_rights_review_required", "watermark_review_required", "commentary_transformative_required", "audio_ducking_required"],
        "capsule_capabilities": ["clip_selection", "commentary_script", "audio_ducking", "risk_mute", "rights_review"],
        "quality_gate_profile": "clip_commentary_release",
    },
    "asmr_or_sensory": {
        "label": "ASMR/沉浸感/感官驱动",
        "implementation_route": "sensory_audio_visual_loop",
        "layout": ["texture_closeup", "repetitive_action", "audio_sync_focus", "minimal_copy"],
        "motion": ["slow_macro_motion", "loopable_action", "sound_sync_cut"],
        "required_families": ["texture_closeup", "hands_or_tool_action", "clean_audio_focus", "loop_rhythm"],
        "quality_gates": ["audio_clean_required", "loop_rhythm_review_required", "visual_texture_clear_required", "no_harsh_sibilance_or_clipping"],
        "capsule_capabilities": ["macro_visuals", "audio_capture_or_generation", "loop_editing", "minimal_copy", "bgm_optional"],
        "quality_gate_profile": "sensory_release",
    },
    "unknown_or_hybrid": {
        "label": "混合/未知格式",
        "implementation_route": "format_probe_then_adapter_selection",
        "layout": ["format_probe_required", "top_examples_comparison", "candidate_recipe_set"],
        "motion": ["unknown_until_probe"],
        "required_families": ["evidence_index", "candidate_formats", "qa_questions"],
        "quality_gates": ["manual_format_review_required", "keyframe_probe_required_before_production", "do_not_overfit_single_sample"],
        "capsule_capabilities": ["format_probe", "candidate_recipe_generation", "manual_review"],
        "quality_gate_profile": "hybrid_probe_release",
    },
}


FORMAT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "product_showcase": ("开箱", "测评", "好物", "种草", "产品", "实测", "对比", "优缺点", "上手", "使用一周", "价格"),
    "story_drama": ("短剧", "剧情", "反转", "结局", "婆婆", "儿媳", "老板装穷", "全家沉默", "试探", "家庭", "职场短剧"),
    "tutorial_screen_recording": ("教程", "步骤", "录屏", "软件", "操作", "一键", "保姆级", "Excel", "剪映", "怎么做", "如何"),
    "shop_or_local_life": ("探店", "门店", "到店", "排队", "人均", "菜单", "老板", "本地生活", "打卡", "试吃"),
    "ai_visual_story": ("AI", "Midjourney", "图生视频", "分镜", "赛博", "奇幻", "科幻", "生成", "视觉故事"),
    "clip_commentary": ("解说", "混剪", "名场面", "盘点", "高燃", "片段", "原声", "reaction", "二创"),
    "asmr_or_sensory": ("ASMR", "沉浸式", "助眠", "解压", "咀嚼音", "敲击", "清洁", "整理", "手作"),
    "talking_head_explainer": ("口播", "观点", "认知", "心理", "商业", "职场", "普通人", "为什么", "建议"),
    "knowledge_card_explainer": ("本质", "底层逻辑", "最高境界", "顶级", "结构", "看透", "内在", "人格系统", "不是", "而是"),
}
FORMAT_TIE_BREAK_ORDER = [
    "product_showcase",
    "story_drama",
    "tutorial_screen_recording",
    "shop_or_local_life",
    "ai_visual_story",
    "clip_commentary",
    "asmr_or_sensory",
    "knowledge_card_explainer",
    "talking_head_explainer",
]


def _joined_signal_text(videos: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    parts: list[str] = []
    parts.extend(str(video.get("description") or "") for video in videos)
    parts.extend(str(video.get("title") or "") for video in videos)
    parts.extend(str(item.get("tag") or "") for item in summary.get("top_hashtags", []))
    parts.extend(str(item.get("phrase") or "") for item in summary.get("top_phrases", []))
    return "\n".join(parts)


def classify_video_format(videos: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    signal_text = _joined_signal_text(videos, summary)
    scores: dict[str, int] = {}
    matched: dict[str, list[str]] = {}
    for format_name, keywords in FORMAT_KEYWORDS.items():
        hits = [keyword for keyword in keywords if keyword and keyword.lower() in signal_text.lower()]
        if hits:
            scores[format_name] = len(hits)
            matched[format_name] = hits

    if not scores:
        primary = "unknown_or_hybrid"
        confidence = 0.0
    else:
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        top_score = ranked[0][1]
        top_formats = {name for name, score in ranked if score == top_score}
        primary = next((name for name in FORMAT_TIE_BREAK_ORDER if name in top_formats), ranked[0][0])
        total = sum(scores.values())
        confidence = round(top_score / total, 3) if total else 0.0

    return {
        "schema_version": "account_video_format_classifier.v1",
        "primary_format": primary,
        "confidence": confidence,
        "scores": scores,
        "matched_keywords": matched,
        "supported_formats": list(FORMAT_DEFINITIONS.keys()),
    }


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


def _probe_has_multimodal_signals(probe_report: Any) -> bool:
    if not isinstance(probe_report, dict):
        return False
    multimodal_keys = {
        "transcript",
        "transcripts",
        "shot_segments",
        "shots",
        "audio_probe",
        "audio",
        "subtitle_ocr",
        "ocr",
        "rhythm",
    }
    return any(key in probe_report for key in multimodal_keys)


def evidence_level(probe_report: Any) -> str:
    if _probe_has_multimodal_signals(probe_report):
        return "L2_multimodal_probe"
    if _probe_keyframe_paths(probe_report):
        return "L1_metadata_plus_keyframes"
    return "L0_metadata_only"


EVIDENCE_LEVEL_ORDER = {
    "L0_metadata_only": 0,
    "L1_metadata_plus_keyframes": 1,
    "L2_multimodal_probe": 2,
    "L3_production_capsule": 3,
}


def evidence_rank(level: str) -> int:
    return EVIDENCE_LEVEL_ORDER.get(str(level or ""), 0)


def analysis_mode_from_evidence_level(level: str) -> str:
    if evidence_rank(level) >= evidence_rank("L2_multimodal_probe"):
        return "metadata_plus_multimodal_probe"
    if evidence_rank(level) >= evidence_rank("L1_metadata_plus_keyframes"):
        return "metadata_plus_visual_probe"
    return "metadata_only"


def _normalize_probe_report(probe_report: Any) -> dict[str, Any]:
    if probe_report is None:
        return {}
    if isinstance(probe_report, list):
        return {"top_video_probes": probe_report}
    if isinstance(probe_report, dict):
        return dict(probe_report)
    return {}


def merge_probe_reports(*reports: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for report in reports:
        current = _normalize_probe_report(report)
        for key, value in current.items():
            if key in merged and isinstance(merged[key], list) and isinstance(value, list):
                merged[key].extend(value)
            elif key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = {**merged[key], **value}
            elif key not in merged or merged[key] in (None, [], {}):
                merged[key] = value
            else:
                merged[f"additional_{key}"] = value
    return merged


def _probe_available_signals(probe_report: Any) -> list[str]:
    report = _normalize_probe_report(probe_report)
    signals = ["metadata"]
    if _probe_keyframe_paths(report):
        signals.append("keyframes")
    if any(key in report for key in ("subtitle_ocr", "ocr")):
        signals.append("ocr")
    if any(key in report for key in ("transcript", "transcripts")):
        signals.append("transcript")
    if any(key in report for key in ("audio_probe", "audio")):
        signals.append("audio")
    if any(key in report for key in ("rhythm", "shot_segments", "shots")):
        signals.append("rhythm")
    return _dedupe(signals)


def build_evidence_manifest(
    videos: list[dict[str, Any]],
    probe_report: Any = None,
) -> dict[str, Any]:
    report = _normalize_probe_report(probe_report)
    level = evidence_level(report)
    rank = evidence_rank(level)
    allowed_claims = [
        "topic_lanes",
        "title_patterns",
        "description_language_patterns",
        "duration_profile",
        "engagement_ranking",
    ]
    blocked_claims: list[str] = []
    if rank >= evidence_rank("L1_metadata_plus_keyframes"):
        allowed_claims.extend(
            [
                "cover_and_first_screen_layout",
                "visual_density",
                "palette_and_typography_hypotheses",
                "visual_component_families",
            ]
        )
    else:
        blocked_claims.extend(
            [
                "cover_visual_claims",
                "layout_and_svg_claims",
            ]
        )
    if rank >= evidence_rank("L2_multimodal_probe"):
        allowed_claims.extend(
            [
                "true_first_three_seconds_structure",
                "camera_pacing_motion_claims",
                "subtitle_ocr_claims",
                "audio_voice_bgm_claims",
                "cut_rhythm_claims",
            ]
        )
    else:
        blocked_claims.extend(
            [
                "true_first_three_seconds_structure",
                "camera_pacing_motion_claims",
                "audio_voice_bgm_claims",
                "cut_rhythm_claims",
            ]
        )

    return {
        "schema_version": "capsule_cinema.account_evidence_manifest.v1",
        "evidence_level": level,
        "available_signals": _probe_available_signals(report),
        "sample_count": len(videos),
        "representative_video_ids": [video.get("aweme_id") or str(video.get("index")) for video in videos[:8]],
        "allowed_claims": _dedupe(allowed_claims),
        "blocked_claims": _dedupe(blocked_claims),
        "probe_status": report.get("probe_status") or report.get("auto_probe_status") or [],
        "fetch_results": report.get("fetch_results") or [],
        "upgrade_path": [
            "L0 metadata supports content hypotheses only",
            "Add keyframes/contact sheets for cover, layout, and visual component claims",
            "Add OCR/transcript/audio/rhythm probes for pacing, voice, subtitles, and BGM claims",
            "Generate and QA a sample video before marking L3_production_capsule",
        ],
    }


def _representative_videos(videos: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    with_media = [video for video in videos if video.get("play_urls")]
    ranked = sorted(
        with_media,
        key=lambda item: (
            item.get("engagement_score", 0),
            item.get("duration_seconds", 0),
            -int(item.get("index") or 0),
        ),
        reverse=True,
    )
    return ranked[:limit]


def _download_remote_media(url: str, dest: Path) -> dict[str, Any]:
    max_bytes = int(os.getenv("CAPSULE_CINEMA_AUTO_PROBE_MAX_BYTES", str(96 * 1024 * 1024)))
    timeout = float(os.getenv("CAPSULE_CINEMA_AUTO_PROBE_TIMEOUT", "20"))
    request = urllib.request.Request(url, headers={"User-Agent": "capsule-cinema-distiller/1.0"})
    read = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            with dest.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    read += len(chunk)
                    if read > max_bytes:
                        handle.close()
                        dest.unlink(missing_ok=True)
                        return {"ok": False, "reason": "remote_media_too_large", "bytes_read": read}
                    handle.write(chunk)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        dest.unlink(missing_ok=True)
        return {"ok": False, "reason": "remote_download_failed", "error": str(exc)}
    return {"ok": True, "bytes_read": read, "path": str(dest)}


def default_media_fetcher(video: dict[str, Any], media_dir: str | Path) -> dict[str, Any]:
    media_root = Path(media_dir)
    media_root.mkdir(parents=True, exist_ok=True)
    urls = video.get("play_urls") or []
    aweme_id = _as_text(video.get("aweme_id"), str(video.get("index") or "video"))
    if not urls:
        return {"ok": False, "aweme_id": aweme_id, "reason": "no_play_url"}
    source_url = str(urls[0])
    suffix = Path(source_url.split("?", 1)[0]).suffix or ".mp4"
    dest = media_root / f"{safe_slug(aweme_id, 'video')}{suffix}"
    source_path = Path(source_url).expanduser()
    if source_path.is_file():
        shutil.copy2(source_path, dest)
        return {"ok": True, "aweme_id": aweme_id, "source_url": source_url, "path": str(dest)}
    if source_url.startswith(("http://", "https://")):
        result = _download_remote_media(source_url, dest)
        return {"aweme_id": aweme_id, "source_url": source_url, **result}
    return {"ok": False, "aweme_id": aweme_id, "source_url": source_url, "reason": "unsupported_media_url"}


def _ffprobe_json(media_path: str) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"ok": False, "reason": "ffprobe_missing"}
    try:
        proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                media_path,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "reason": "ffprobe_failed", "error": str(exc)}
    if proc.returncode != 0:
        return {"ok": False, "reason": "ffprobe_failed", "error": proc.stderr.strip()}
    try:
        return {"ok": True, "data": json.loads(proc.stdout or "{}")}
    except json.JSONDecodeError as exc:
        return {"ok": False, "reason": "ffprobe_invalid_json", "error": str(exc)}


def _extract_probe_frame(media_path: str, out_path: Path, timestamp: float) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-ss",
                f"{max(timestamp, 0):.3f}",
                "-i",
                media_path,
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(out_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and out_path.is_file()


def default_probe_runner(media_items: list[dict[str, Any]], output_dir: str | Path) -> dict[str, Any]:
    output_root = Path(output_dir)
    probes: list[dict[str, Any]] = []
    status: list[dict[str, Any]] = []
    audio_observations: list[dict[str, Any]] = []
    rhythm_observations: list[dict[str, Any]] = []
    for item in media_items:
        media_path = str(item.get("path") or "")
        aweme_id = _as_text(item.get("aweme_id"), Path(media_path).stem)
        ffprobe = _ffprobe_json(media_path)
        if not ffprobe.get("ok"):
            status.append({"aweme_id": aweme_id, "ok": False, "stage": "ffprobe", "reason": ffprobe.get("reason")})
            continue
        data = ffprobe.get("data") or {}
        streams = data.get("streams") if isinstance(data.get("streams"), list) else []
        try:
            duration = float(_as_text(_as_dict(data.get("format")).get("duration"), "0") or 0)
        except ValueError:
            duration = 0.0
        has_audio = any(stream.get("codec_type") == "audio" for stream in streams if isinstance(stream, dict))
        has_video = any(stream.get("codec_type") == "video" for stream in streams if isinstance(stream, dict))
        frames: list[dict[str, str]] = []
        if has_video:
            timestamps = [0.0]
            if duration > 3:
                timestamps.append(3.0)
            if duration > 6:
                timestamps.append(duration / 2)
            for index, timestamp in enumerate(timestamps):
                frame_path = output_root / "visual_probe" / f"{safe_slug(aweme_id, 'video')}_{index}.jpg"
                if _extract_probe_frame(media_path, frame_path, timestamp):
                    frames.append({"label": f"t_{timestamp:.1f}", "path": str(frame_path), "timestamp": timestamp})
        probes.append({"aweme_id": aweme_id, "frames": frames, "duration_seconds": duration})
        audio_observations.append({"aweme_id": aweme_id, "has_audio": has_audio})
        rhythm_observations.append({"aweme_id": aweme_id, "duration_seconds": duration, "frame_count": len(frames)})
        status.append({"aweme_id": aweme_id, "ok": True, "stage": "probe", "frame_count": len(frames), "has_audio": has_audio})

    report: dict[str, Any] = {
        "top_video_probes": probes,
        "probe_status": status,
    }
    if any(item.get("has_audio") for item in audio_observations):
        report["audio_probe"] = {"items": audio_observations}
    if rhythm_observations:
        report["rhythm"] = {"items": rhythm_observations}
    return report


def maybe_run_auto_probe(
    videos: list[dict[str, Any]],
    output_dir: str | Path,
    enable_auto_probe: bool,
    *,
    media_fetcher: Callable[[dict[str, Any], str | Path], dict[str, Any]] | None = None,
    probe_runner: Callable[[list[dict[str, Any]], str | Path], dict[str, Any]] | None = None,
    sample_limit: int = 5,
) -> dict[str, Any]:
    if not enable_auto_probe:
        return {
            "schema_version": "capsule_cinema.account_auto_probe.v1",
            "auto_probe_status": [{"ok": True, "stage": "auto_probe", "status": "disabled"}],
        }
    media_root = Path(output_dir) / "source_media"
    fetcher = media_fetcher or default_media_fetcher
    runner = probe_runner or default_probe_runner
    fetch_results: list[dict[str, Any]] = []
    media_items: list[dict[str, Any]] = []
    for video in _representative_videos(videos, limit=sample_limit):
        result = fetcher(video, media_root)
        fetch_results.append(result)
        if result.get("ok") and result.get("path"):
            media_items.append(
                {
                    "aweme_id": result.get("aweme_id") or video.get("aweme_id") or str(video.get("index") or ""),
                    "path": result["path"],
                    "source_url": result.get("source_url") or (video.get("play_urls") or [""])[0],
                    "video_index": video.get("index"),
                }
            )
    if not media_items:
        return {
            "schema_version": "capsule_cinema.account_auto_probe.v1",
            "fetch_results": fetch_results,
            "auto_probe_status": [{"ok": False, "stage": "auto_probe", "status": "no_media_fetched"}],
        }
    probe = runner(media_items, output_dir)
    if not isinstance(probe, dict):
        probe = {"probe_status": [{"ok": False, "stage": "probe_runner", "status": "invalid_probe_report"}]}
    return {
        "schema_version": "capsule_cinema.account_auto_probe.v1",
        **probe,
        "fetch_results": fetch_results,
        "auto_probe_status": [{"ok": True, "stage": "auto_probe", "status": "completed", "media_count": len(media_items)}],
    }


def build_presentation_recipe(
    videos: list[dict[str, Any]],
    summary: dict[str, Any],
    probe_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Infer reusable video presentation rules from metadata and optional probes."""
    keyframe_paths = _probe_keyframe_paths(probe_report)
    has_keyframes = bool(keyframe_paths)
    classification = classify_video_format(videos, summary)
    format_type = classification["primary_format"]
    if format_type == "knowledge_card_explainer":
        format_type = "minimal_text_card_explainer"
    definition_key = "knowledge_card_explainer" if format_type == "minimal_text_card_explainer" else format_type
    definition = FORMAT_DEFINITIONS.get(definition_key, FORMAT_DEFINITIONS["unknown_or_hybrid"])
    non_card = definition_key != "knowledge_card_explainer"

    if non_card:
        return {
            "schema_version": "douyin_account_presentation_recipe.v2",
            "format_type": format_type,
            "format_label": definition["label"],
            "observed_or_inferred": "observed_from_metadata_and_keyframes" if has_keyframes else "metadata_inferred",
            "evidence_level": evidence_level(probe_report),
            "format_classifier": classification,
            "canvas": {
                "observed_size": "unknown_without_probe",
                "recommended_output": "1080x1920",
                "douyin_safe_variant": "1080x1920 full_vertical",
            },
            "layout": definition["layout"],
            "frame_grammar": {
                "core_surface": "Extract only reusable visual mechanics for this format; do not copy source identity or source frames.",
                "first_three_seconds": "The first screen must expose the format-specific stop reason: conflict, product proof, result preview, or sensory hook.",
                "evidence_boundary": "Claims about camera, pacing, acting, or UI layout require keyframe, transcript, or shot evidence.",
            },
            "palette": {
                "background": "format_observed_or_topic_appropriate",
                "primary_text": "format_observed",
                "accent": "format_observed",
                "illustration": [],
                "bottom_bar": "optional",
            },
            "typography": {
                "caption": "readable_platform_native_chinese",
                "cover": "one_clear_stop_claim_or_result",
                "body_subtitles": "required_when_speech_or_steps_drive_retention",
            },
            "motion": definition["motion"],
            "visual_component_library": {
                "required_families": definition["required_families"],
                "optional_families": [],
                "style_rules": [
                    "components describe reusable mechanics, not copied source assets",
                    "every required family must be visible in either keyframe evidence or marked as inferred",
                    "source identity, watermark, logo, handle, and original frames are forbidden in generated public outputs",
                ],
            },
            "semantic_illustration_map": [],
            "visual_quality_gates": definition["quality_gates"] + ["no_source_identity_visuals", "contact_sheet_visual_review_required"],
            "card_timing": {},
            "audio": {
                "voice": "format_observed_or_capsule_default",
                "bgm": "format_observed_or_low_volume_safe_default",
                "voice_priority": definition_key not in {"asmr_or_sensory"},
            },
            "cover_formula": ["format_specific_stop_reason", "one_visual_proof_or_conflict", "no_source_identity"],
            "implementation_route": definition["implementation_route"],
            "implementation_steps": [
                "classify_video_format",
                "collect_multimodal_evidence_if_available",
                "extract_format_specific_hook_structure",
                "map_required_visual_component_families",
                "write_capsule_seed_without_source_identity",
                "generate_one_sample_and_run_format_quality_gates",
            ],
            "avoid": [
                "do_not_copy_account_logo_or_name",
                "do_not_reuse_source_frames_without_rights",
                "do_not_force_knowledge_card_layout_on_non_card_formats",
                "do_not_claim_pacing_or_camera_style_without_probe_evidence",
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

    return {
        "schema_version": "douyin_account_presentation_recipe.v2",
        "format_type": format_type,
        "format_label": definition["label"],
        "observed_or_inferred": "observed_from_metadata_and_keyframes" if has_keyframes else "metadata_inferred",
        "evidence_level": evidence_level(probe_report),
        "format_classifier": classification,
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
    classification = classify_video_format(videos, summary)
    definition = FORMAT_DEFINITIONS.get(classification["primary_format"], FORMAT_DEFINITIONS["unknown_or_hybrid"])

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
            f"这个账号的可见内容更适合先归入 `{classification['primary_format']}`（{definition['label']}）。当前判断来自标题、描述、标签、统计字段和可选 probe 证据；复刻时应优先复用内容机制、版式机制、节奏机制和质量门槛，而不是复制原账号素材。",
            "",
            "## 内容母题",
            "",
            f"- 高频标签: {top_tags}",
            f"- 高频描述短语: {top_phrases}",
            "- 高互动内容优先提炼“观众停止理由 + 该类型核心证据 + 可转述结论”的组合。",
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
    presentation = presentation_recipe or build_presentation_recipe([], summary)
    format_key = _definition_key_from_presentation(presentation)
    definition = FORMAT_DEFINITIONS.get(format_key, FORMAT_DEFINITIONS["unknown_or_hybrid"])
    structure = _format_script_structure(format_key, summary)
    copy_rules = _format_copy_rules(format_key)
    visual_lines = _format_visual_lines(presentation)
    cover_rules = _format_cover_rules(format_key)

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
            _format_positioning_formula(format_key, primary_lane),
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
            *[f"- {item}" for item in copy_rules],
            "",
            "## 视频呈现方式",
            "",
            f"- 格式家族: `{format_key}`（{definition['label']}）",
            *visual_lines,
            "",
            "## 封面与包装公式",
            "",
            *cover_rules,
            "",
            "## 生产流程",
            "",
            "1. 先确认 format_family，不要把所有账号都套进同一种视频模板。",
            "2. 从选题池挑一个主题，再找该类型需要的核心证据：产品演示、人物冲突、屏幕步骤、地点体验、视觉分镜或声音动作。",
            "3. 先写首 3 秒停止理由，再写正文；首 3 秒不强，正文先别扩。",
            "4. 按 presentation_recipe 里的组件族和 quality gates 生成样片。",
            "5. 发布后按该类型核心指标复盘：完播、收藏、转发、评论问题、商品点击、到店意向或教程复现反馈。",
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
    definition_key = "knowledge_card_explainer" if presentation.get("format_type") == "minimal_text_card_explainer" else str(
        presentation.get("format_type") or "unknown_or_hybrid"
    )
    definition = FORMAT_DEFINITIONS.get(definition_key, FORMAT_DEFINITIONS["unknown_or_hybrid"])
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
            "positioning": "从账号高频主题、观众压力、形式机制和证据等级生成可复用内容配方",
            "duration_profile": _duration_profile(summary),
            "content_lanes": _theme_lanes(summary),
            "hook_patterns": _title_formula_examples(summary),
            "structure": _script_structure(summary),
            "copy_rules": [
                "标题和开头必须服务该 format_family 的停留理由",
                "不得照搬原账号标题、口播、人物、logo、画面或水印",
                "metadata_only 只产出粗配方；涉及镜头、动效、表演、UI、节奏时必须有 probe 证据",
            ],
            "visual_rules": [
                "按 presentation_recipe.visual_component_library 生成视觉组件",
                "封面只承载一个该类型的停止理由",
                "字幕、UI、产品、人物或场景不得遮挡该类型的核心证据",
            ],
            "quality_rules": [
                "前 3 秒必须能独立成立",
                "不得照搬原账号标题和口播",
                "缺少逐帧/转录/音频分析时不要强断言镜头、表演、剪辑、音色和节奏风格",
            ],
        },
        "capsule_seed": {
            "schema_version": "capsule_cinema.account_capsule_seed.v1",
            "format_family": definition_key,
            "evidence_level": presentation.get("evidence_level", "L0_metadata_only"),
            "production_capabilities": definition["capsule_capabilities"],
            "quality_gate_profile": definition["quality_gate_profile"],
            "recommended_execution_mode": "local_script" if definition_key in {"knowledge_card_explainer", "tutorial_screen_recording"} else "preset_or_local_script",
        },
        "presentation_recipe": presentation,
    }


def build_universal_distillation(
    videos: list[dict[str, Any]],
    summary: dict[str, Any],
    probe_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    presentation = build_presentation_recipe(videos, summary, probe_report=probe_report)
    definition_key = "knowledge_card_explainer" if presentation.get("format_type") == "minimal_text_card_explainer" else str(
        presentation.get("format_type") or "unknown_or_hybrid"
    )
    definition = FORMAT_DEFINITIONS.get(definition_key, FORMAT_DEFINITIONS["unknown_or_hybrid"])
    return {
        "schema_version": "universal_account_distillation.v1",
        "evidence_level": presentation.get("evidence_level", evidence_level(probe_report)),
        "format_classifier": presentation.get("format_classifier") or classify_video_format(videos, summary),
        "account_profile": {
            "nickname": summary.get("account_nickname", ""),
            "sample_size": len(videos),
            "duration_profile": _duration_profile(summary),
            "top_hashtags": summary.get("top_hashtags", []),
            "top_phrases": summary.get("top_phrases", []),
            "engagement": summary.get("engagement", {}),
        },
        "content_recipe": {
            "topic_lanes": _theme_lanes(summary),
            "title_patterns": _title_formula_examples(summary),
            "script_patterns": _script_structure(summary),
            "hook_signal_counts": summary.get("pattern_counts", {}),
            "evidence_boundary": "metadata_only can support topic/title/script hypotheses; camera, pacing, performance, UI, product proof, and audio claims require probe evidence.",
        },
        "presentation_recipe": presentation,
        "capsule_seed": {
            "schema_version": "capsule_cinema.account_capsule_seed.v1",
            "format_family": definition_key,
            "evidence_level": presentation.get("evidence_level", "L0_metadata_only"),
            "production_capabilities": definition["capsule_capabilities"],
            "quality_gate_profile": definition["quality_gate_profile"],
            "read_order_extension": [
                "format_classifier.json",
                "presentation_recipe.json",
                "quality_gates.yaml",
            ],
            "source_identity_policy": "distill mechanisms only; do not embed source account name, logo, watermark, handle, source frames, or copied text.",
        },
        "quality_gates": presentation.get("visual_quality_gates", []),
    }


def build_content_formula(
    videos: list[dict[str, Any]],
    summary: dict[str, Any],
    presentation: dict[str, Any],
    evidence_manifest: dict[str, Any],
) -> dict[str, Any]:
    format_key = _definition_key_from_presentation(presentation)
    return {
        "schema_version": "capsule_cinema.account_content_formula.v1",
        "format_family": format_key,
        "evidence_level": evidence_manifest["evidence_level"],
        "evidence_status": "observed_from_metadata",
        "topic_lanes": _theme_lanes(summary),
        "title_patterns": _title_formula_examples(summary),
        "script_structure": _format_script_structure(format_key, summary),
        "hook_generation_contract": {
            "hook_candidates_min": 12,
            "score_dimensions": [
                "specific_viewer_pressure",
                "visible_result_or_conflict",
                "evidence_density",
                "contrast",
                "save_or_share_value",
                "risk_control",
            ],
            "first_three_seconds_required": True,
            "reject_if_first_three_seconds_only_background": True,
        },
        "source_safety": {
            "copy_source_title_forbidden": True,
            "copy_source_script_forbidden": True,
            "source_identity_forbidden": True,
        },
        "top_examples": [
            {
                "index": video.get("index"),
                "aweme_id": video.get("aweme_id"),
                "description": video.get("description"),
                "engagement_score": video.get("engagement_score", 0),
            }
            for video in videos[:8]
        ],
    }


def build_cover_formula(
    summary: dict[str, Any],
    presentation: dict[str, Any],
    evidence_manifest: dict[str, Any],
) -> dict[str, Any]:
    format_key = _definition_key_from_presentation(presentation)
    status = (
        "observed_from_L1_or_better"
        if evidence_rank(evidence_manifest["evidence_level"]) >= evidence_rank("L1_metadata_plus_keyframes")
        else "metadata_hypothesis_only"
    )
    return {
        "schema_version": "capsule_cinema.account_cover_formula.v1",
        "format_family": format_key,
        "evidence_level": evidence_manifest["evidence_level"],
        "evidence_status": status,
        "formula": _format_cover_rules(format_key),
        "cover_contract": {
            "one_stop_reason_only": True,
            "title_visual_alignment_required": True,
            "first_screen_can_prove_title": True,
            "source_identity_forbidden": True,
        },
        "observed_inputs": {
            "sample_count": summary.get("video_count", 0),
            "has_cover_url_count": summary.get("pattern_counts", {}).get("has_cover_url", 0),
        },
    }


def build_motion_formula(
    presentation: dict[str, Any],
    evidence_manifest: dict[str, Any],
) -> dict[str, Any]:
    level = evidence_manifest["evidence_level"]
    rank = evidence_rank(level)
    if rank >= evidence_rank("L2_multimodal_probe"):
        status = "observed_from_L2_probe"
    elif rank >= evidence_rank("L1_metadata_plus_keyframes"):
        status = "partially_observed_from_keyframes"
    else:
        status = "blocked_without_L2"
    return {
        "schema_version": "capsule_cinema.account_motion_formula.v1",
        "format_family": _definition_key_from_presentation(presentation),
        "evidence_level": level,
        "evidence_status": status,
        "motion_patterns": presentation.get("motion", []),
        "implementation_route": presentation.get("implementation_route", ""),
        "motion_contract": {
            "motion_plan_required": True,
            "first_three_seconds_motion_or_cut_required": True,
            "static_hold_limit_seconds": 3,
            "do_not_claim_pacing_without_L2": rank < evidence_rank("L2_multimodal_probe"),
        },
        "blocked_claims": [
            claim
            for claim in evidence_manifest.get("blocked_claims", [])
            if "motion" in claim or "rhythm" in claim or "pacing" in claim
        ],
    }


def build_audio_formula(
    presentation: dict[str, Any],
    evidence_manifest: dict[str, Any],
) -> dict[str, Any]:
    level = evidence_manifest["evidence_level"]
    rank = evidence_rank(level)
    status = "observed_from_L2_probe" if rank >= evidence_rank("L2_multimodal_probe") else "blocked_without_L2"
    return {
        "schema_version": "capsule_cinema.account_audio_formula.v1",
        "format_family": _definition_key_from_presentation(presentation),
        "evidence_level": level,
        "evidence_status": status,
        "audio": presentation.get("audio", {}),
        "audio_contract": {
            "voice_required_when_voice_drives_format": True,
            "bgm_required_unless_format_declares_optional": True,
            "silent_placeholder_forbidden": True,
            "audio_duration_is_timing_authority": True,
            "do_not_claim_voice_bgm_without_L2": rank < evidence_rank("L2_multimodal_probe"),
        },
        "blocked_claims": [
            claim
            for claim in evidence_manifest.get("blocked_claims", [])
            if "audio" in claim or "voice" in claim or "bgm" in claim
        ],
    }


def build_quality_gates_formula(
    presentation: dict[str, Any],
    evidence_manifest: dict[str, Any],
) -> dict[str, Any]:
    base_gate_ids = [
        "first_three_seconds_gate",
        "source_identity_gate",
        "evidence_boundary_gate",
        "visual_mechanism_gate",
        "modality_completeness_gate",
    ]
    gates = [
        {
            "id": "first_three_seconds_gate",
            "severity": "blocker",
            "type": "copy_visual_review",
            "rule": "The real first 0-3 seconds must expose a concrete stop reason for the detected format family.",
        },
        {
            "id": "source_identity_gate",
            "severity": "blocker",
            "type": "source_safety_review",
            "rule": "Public outputs must not contain source account name, link, watermark, handle, logo, source frames, or copied text.",
        },
        {
            "id": "evidence_boundary_gate",
            "severity": "blocker",
            "type": "planning_review",
            "rule": "Do not claim camera, pacing, motion, subtitle, voice, or BGM style unless L2 evidence is present.",
        },
        {
            "id": "visual_mechanism_gate",
            "severity": "blocker",
            "type": "visual_review",
            "rule": "Generated visuals must expose the format-specific mechanism and component families, not a generic decorative substitute.",
        },
        {
            "id": "modality_completeness_gate",
            "severity": "blocker",
            "type": "artifact_review",
            "rule": "A complete video release must include required voice/BGM/final-video/QA artifacts declared by the capsule production contract.",
        },
    ]
    for gate_id in presentation.get("visual_quality_gates", []):
        if gate_id not in base_gate_ids:
            gates.append(
                {
                    "id": str(gate_id),
                    "severity": "blocker",
                    "type": "format_specific_review",
                    "rule": f"Format-specific gate from presentation recipe: {gate_id}.",
                }
            )
    return {
        "schema_version": "capsule_cinema.account_quality_gates.v1",
        "format_family": _definition_key_from_presentation(presentation),
        "evidence_level": evidence_manifest["evidence_level"],
        "minimum_evidence_for_release": "L2_multimodal_probe",
        "gates": gates,
    }


def build_capsule_seed_artifact(universal: dict[str, Any]) -> dict[str, Any]:
    seed = dict(universal.get("capsule_seed") or {})
    seed.setdefault("schema_version", "capsule_cinema.account_capsule_seed.v1")
    seed.setdefault("minimum_evidence_for_release", "L2_multimodal_probe")
    seed.setdefault(
        "production_contract_hint",
        {
            "required_outputs": {
                "final_video": "required",
                "qa_report": "required",
                "publishing_package": "required",
            },
            "modality_contracts": {
                "copy": {
                    "hook_candidates_min": 12,
                    "first_3_seconds_audit_required": True,
                    "title_cover_opening_alignment_required": True,
                },
                "visual": {
                    "contact_sheet_review_required": True,
                    "source_identity_forbidden": True,
                },
                "audio": {
                    "silent_placeholder_forbidden": True,
                },
            },
        },
    )
    return seed


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
    enable_auto_probe: bool = True,
    media_fetcher: Callable[[dict[str, Any], str | Path], dict[str, Any]] | None = None,
    probe_runner: Callable[[list[dict[str, Any]], str | Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _load_env(dotenv_path)
    loaded_probe_report = _load_probe_report(probe_report)
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
    auto_probe_report = maybe_run_auto_probe(
        videos,
        output_dir,
        enable_auto_probe and evidence_rank(evidence_level(loaded_probe_report)) < evidence_rank("L2_multimodal_probe"),
        media_fetcher=media_fetcher,
        probe_runner=probe_runner,
    )
    combined_probe_report = merge_probe_reports(loaded_probe_report, auto_probe_report)
    evidence_manifest = build_evidence_manifest(videos, combined_probe_report)
    analysis_mode = analysis_mode_from_evidence_level(evidence_manifest["evidence_level"])
    presentation = build_presentation_recipe(videos, summary, probe_report=combined_probe_report)
    universal = build_universal_distillation(videos, summary, probe_report=combined_probe_report)
    content_formula = build_content_formula(videos, summary, presentation, evidence_manifest)
    cover_formula = build_cover_formula(summary, presentation, evidence_manifest)
    motion_formula = build_motion_formula(presentation, evidence_manifest)
    audio_formula = build_audio_formula(presentation, evidence_manifest)
    quality_gates = build_quality_gates_formula(presentation, evidence_manifest)
    capsule_seed = build_capsule_seed_artifact(universal)

    video_index = {
        "schema_version": "capsule_cinema.douyin_video_index.v1",
        "source": {"platform": "douyin", "url": url, "range": range_str},
        "summary": summary,
        "videos": videos,
    }
    index_path = _write_json(output_dir / "video_index.json", video_index)
    evidence_path = _write_json(output_dir / "evidence_manifest.json", evidence_manifest)
    universal_path = _write_json(output_dir / "universal_distillation.json", universal)
    distillation_path = _write_text(
        output_dir / "account_distillation.md",
        build_account_distillation(
            url,
            range_str,
            videos,
            summary,
            analysis_mode=analysis_mode,
            keyframe_count=len(_probe_keyframe_paths(combined_probe_report)),
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
    presentation_formula_path = _write_yaml(output_dir / "presentation_formula.yaml", presentation)
    content_formula_path = _write_yaml(output_dir / "content_formula.yaml", content_formula)
    cover_formula_path = _write_yaml(output_dir / "cover_formula.yaml", cover_formula)
    motion_formula_path = _write_yaml(output_dir / "motion_formula.yaml", motion_formula)
    audio_formula_path = _write_yaml(output_dir / "audio_formula.yaml", audio_formula)
    quality_gates_path = _write_yaml(output_dir / "quality_gates.yaml", quality_gates)
    capsule_seed_path = _write_yaml(output_dir / "capsule_seed.yaml", capsule_seed)
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
            {"category": "evidence_manifest", "path": str(evidence_path), "title": "Evidence manifest"},
            {"category": "universal_distillation", "path": str(universal_path), "title": "Universal distillation"},
            {"category": "account_distillation", "path": str(distillation_path), "title": "Account distillation"},
            {"category": "replication_recipe", "path": str(recipe_path), "title": "Replication recipe"},
            {"category": "presentation_recipe", "path": str(presentation_md_path), "title": "Presentation recipe"},
            {"category": "presentation_recipe_json", "path": str(presentation_json_path), "title": "Presentation recipe JSON"},
            {"category": "presentation_formula", "path": str(presentation_formula_path), "title": "Presentation formula"},
            {"category": "content_formula", "path": str(content_formula_path), "title": "Content formula"},
            {"category": "cover_formula", "path": str(cover_formula_path), "title": "Cover formula"},
            {"category": "motion_formula", "path": str(motion_formula_path), "title": "Motion formula"},
            {"category": "audio_formula", "path": str(audio_formula_path), "title": "Audio formula"},
            {"category": "quality_gates", "path": str(quality_gates_path), "title": "Quality gates"},
            {"category": "capsule_seed", "path": str(capsule_seed_path), "title": "Capsule seed"},
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
        "evidence_manifest_path": str(evidence_path),
        "universal_distillation_path": str(universal_path),
        "account_distillation_path": str(distillation_path),
        "replication_recipe_path": str(recipe_path),
        "presentation_recipe_path": str(presentation_md_path),
        "presentation_recipe_json_path": str(presentation_json_path),
        "presentation_formula_path": str(presentation_formula_path),
        "content_formula_path": str(content_formula_path),
        "cover_formula_path": str(cover_formula_path),
        "motion_formula_path": str(motion_formula_path),
        "audio_formula_path": str(audio_formula_path),
        "quality_gates_path": str(quality_gates_path),
        "capsule_seed_path": str(capsule_seed_path),
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
    parser.add_argument("--disable-auto-probe", action="store_true", help="Skip automatic media/keyframe/audio probing")
    args = parser.parse_args()

    result = run_distillation(
        url=args.url,
        range_str=args.range_str,
        output_base_dir=args.output_base_dir or None,
        external_video_workflow_root=args.external_video_workflow_root or None,
        dotenv_path=args.dotenv_path or None,
        probe_report=args.probe_report or None,
        enable_auto_probe=not args.disable_auto_probe,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
