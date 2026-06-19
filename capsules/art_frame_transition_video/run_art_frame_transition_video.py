#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(ROOT / "lib"))


def normalize_reference_images(raw: object) -> list[dict[str, Any]]:
    if raw in (None, "", []):
        return []
    if isinstance(raw, (str, Path)):
        return [{"path": str(raw), "role": "", "description": ""}]
    if not isinstance(raw, list):
        raise ValueError("reference_images must be a string path or list")

    normalized: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, (str, Path)):
            normalized.append({"path": str(item), "role": "", "description": ""})
        elif isinstance(item, dict):
            normalized.append(
                {
                    "path": str(item.get("path") or item.get("image") or "").strip(),
                    "role": str(item.get("role") or "").strip().lower(),
                    "description": str(item.get("description") or item.get("note") or "").strip(),
                }
            )
        else:
            raise ValueError("reference_images entries must be strings or objects")
    return [item for item in normalized if item["path"]]


def _score_keywords(text: str, keywords: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword in lowered)


START_WORDS = {
    "empty",
    "initial",
    "before",
    "minimal",
    "dormant",
    "closed",
    "blank",
    "空",
    "初始",
    "开始",
    "之前",
    "未",
    "少",
    "静止",
    "空瓶",
    "素净",
}
END_WORDS = {
    "full",
    "finished",
    "complete",
    "bloom",
    "rich",
    "peak",
    "after",
    "满",
    "完成",
    "盛放",
    "开花",
    "长满",
    "丰富",
    "终态",
    "之后",
}
NOVEL_WORDS = {"surreal", "modern", "installation", "unexpected", "新奇", "吸引", "超现实", "现代", "装置", "几何"}
FAMOUS_WORDS = {"museum", "collection", "artist", "famous", "名画", "馆藏", "收藏", "作者", "博物馆", "艺术史"}
COMFORT_WORDS = {"flower", "landscape", "still life", "quiet", "calm", "花", "风景", "静物", "治愈", "舒适", "安静", "器物"}


def _ref_state_score(ref: dict[str, Any]) -> tuple[int, int]:
    text = " ".join([ref.get("path", ""), ref.get("role", ""), ref.get("description", "")])
    return _score_keywords(text, START_WORDS), _score_keywords(text, END_WORDS)


def choose_motion_route(prompt: str, mood: str = "auto", style_hint: str = "") -> str:
    joined = f"{prompt} {style_hint}".lower()
    if mood == "comfortable":
        return "comfortable_immersive"
    if mood == "novel":
        return "novel_attention"
    if _score_keywords(joined, FAMOUS_WORDS):
        return "famous_art_deconstruction"
    if _score_keywords(joined, NOVEL_WORDS):
        return "novel_attention"
    if _score_keywords(joined, COMFORT_WORDS):
        return "comfortable_immersive"
    return "comfortable_immersive"


def decide_frame_plan(
    prompt: str,
    reference_images: list[dict[str, Any]],
    mood: str = "auto",
    style_hint: str = "",
) -> dict[str, Any]:
    route = choose_motion_route(prompt, mood=mood, style_hint=style_hint)
    plan: dict[str, Any] = {
        "visual_analysis": {
            "prompt_summary": prompt.strip(),
            "style_hint": style_hint,
        },
        "reference_images": reference_images,
        "motion_route": route,
        "anchor_frame": "unknown",
        "start_frame_strategy": "generate_from_text",
        "end_frame_strategy": "generate_from_text",
        "selected_start_image": "",
        "selected_end_image": "",
        "image_processing_actions": ["normalize_aspect_ratio", "compress_veo_inputs", "add_subtle_depth_if_useful"],
        "risk_notes": [],
    }
    if not reference_images:
        return plan

    scored = [(ref, *_ref_state_score(ref)) for ref in reference_images]
    explicit_start = [ref for ref in reference_images if ref.get("role") in {"start", "first", "首帧"}]
    explicit_end = [ref for ref in reference_images if ref.get("role") in {"end", "last", "尾帧"}]
    if explicit_start and explicit_end:
        plan.update(
            {
                "anchor_frame": "both",
                "start_frame_strategy": "select_from_inputs",
                "end_frame_strategy": "select_from_inputs",
                "selected_start_image": explicit_start[0]["path"],
                "selected_end_image": explicit_end[0]["path"],
            }
        )
        return plan

    if len(reference_images) >= 2:
        start_ref = max(scored, key=lambda item: (item[1] - item[2], item[1]))[0]
        end_ref = max(scored, key=lambda item: (item[2] - item[1], item[2]))[0]
        if start_ref["path"] != end_ref["path"]:
            plan.update(
                {
                    "anchor_frame": "both",
                    "start_frame_strategy": "select_from_inputs",
                    "end_frame_strategy": "select_from_inputs",
                    "selected_start_image": start_ref["path"],
                    "selected_end_image": end_ref["path"],
                }
            )
            return plan

    only = reference_images[0]
    start_score, end_score = _ref_state_score(only)
    if start_score > end_score:
        plan.update(
            {
                "anchor_frame": "start",
                "start_frame_strategy": "use_reference",
                "end_frame_strategy": "derive_from_reference",
                "selected_start_image": only["path"],
                "image_processing_actions": plan["image_processing_actions"] + ["derive_consistent_end_frame"],
            }
        )
    else:
        plan.update(
            {
                "anchor_frame": "end",
                "start_frame_strategy": "derive_from_reference",
                "end_frame_strategy": "use_reference",
                "selected_end_image": only["path"],
                "image_processing_actions": plan["image_processing_actions"] + ["derive_consistent_start_frame"],
            }
        )
    return plan


def build_caption_lines(
    prompt: str,
    frame_plan: dict[str, Any],
    artwork_info: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    artwork_info = artwork_info or {}
    verified = bool(artwork_info.get("verified"))
    title = str(artwork_info.get("title") or "").strip()
    artist = str(artwork_info.get("artist") or "").strip()
    collection = str(artwork_info.get("collection") or "").strip()
    route = frame_plan.get("motion_route") or "comfortable_immersive"

    if verified and (title or artist or collection):
        parts = [part for part in [artist, f"《{title}》" if title else "", collection] if part]
        hook = "，".join(parts) + "，先用一个细节把人留下来。"
    elif route == "novel_attention":
        hook = "这幅画最抓人的地方，是静止里忽然有了变化。"
    else:
        hook = "从画面气质看，它最动人的地方，是时间慢了下来。"

    subject = prompt.strip() or "这幅画面"
    context = f"它描绘的不是热闹，而是「{subject[:24]}」里的气息。"
    distinction = "最特别的地方，是光、质感和空间层次一起慢慢展开。"
    if route == "novel_attention":
        distinction = "最特别的地方，是熟悉的画面里出现了一点出人意料的生命感。"
    ending = "愿你也能在流动的日子里，留住一处清明。"

    return [
        {"index": 0, "start": 0.2, "end": 2.0, "text": hook},
        {"index": 1, "start": 2.1, "end": 4.0, "text": context},
        {"index": 2, "start": 4.1, "end": 6.2, "text": distinction},
        {"index": 3, "start": 6.3, "end": 7.8, "text": ending},
    ]


def build_veo_prompt(prompt: str, frame_plan: dict[str, Any], captions: list[dict[str, Any]]) -> str:
    route = frame_plan.get("motion_route") or "comfortable_immersive"
    if route == "novel_attention":
        motion = (
            "Use a restrained surprising transformation: pigment, light, or the main object "
            "seems to gently leave the flat image plane while staying tasteful and artistic."
        )
    elif route == "famous_art_deconstruction":
        motion = (
            "Respect the source artwork. Animate key motifs subtly, like time, light, brush texture, "
            "or symbolic objects awakening without damaging the artwork's dignity."
        )
    else:
        motion = (
            "Use a comfortable immersive transformation: slow light movement, layered depth, "
            "soft parallax, texture breathing, and gentle subject motion."
        )

    visible_caption_context = " / ".join(item["text"] for item in captions[:2])
    return (
        f"{prompt}\n"
        f"{motion}\n"
        "Maintain a refined artistic feeling, subtle 3D depth, gallery-grade lighting, coherent framing, "
        "and no cheap plastic 3D look. Keep the start and end frame composition consistent.\n"
        "Add native scene sound effects that match the object transformation: soft paper movement, pigment bloom, "
        "gallery ambience, delicate light shimmer, ceramic resonance, water ripple, or subject-specific natural sounds. "
        "No background music, no speech, no dialogue, no subtitles rendered by the video model.\n"
        f"Caption intent for mood only, do not render text: {visible_caption_context}"
    )


def build_bgm_selection(prompt: str, frame_plan: dict[str, Any], bgm_query: str = "") -> dict[str, Any]:
    route = frame_plan.get("motion_route") or "comfortable_immersive"
    if bgm_query.strip():
        query = bgm_query.strip()
    elif route == "novel_attention":
        query = "subtle modern art ambient instrumental"
    elif route == "famous_art_deconstruction":
        query = "quiet museum classical ambient instrumental"
    else:
        query = "soft cinematic ambient instrumental calm art gallery"
    return {
        "music_source": "online",
        "music_query": query,
        "reason": f"Subtle BGM for: {prompt[:80]}",
        "needs_bgm": True,
    }
