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
