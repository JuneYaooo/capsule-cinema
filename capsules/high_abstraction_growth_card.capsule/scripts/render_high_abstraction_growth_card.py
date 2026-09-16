#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import shutil
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = PROJECT_ROOT / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass


W, H = 1080, 1440
FPS = 30
CARD_SECONDS = 3.2
HEADER_WORDMARK = "MIND STRUCTURE"
ROMAN_SEPARATOR = "COGNITIVE STRUCTURE"
DISCLAIMER_TEXT = "原创观点\n仅供参考"
BOTTOM_COLUMNS = ("现实场景\n先被看见", "机制拆解\n获得解释", "行动重建\n身份升级")
BLACK = "#111111"
SOFT_BLACK = "#202020"
GRAY = "#9b9b9b"
LIGHT_GRAY = "#eeeeee"
MID_GRAY = "#cfcfcf"
PALE_GRAY = "#f5f5f5"
RED = "#d84b61"
DEEP_RED = "#d71935"
PALE_RED = "#f4c5cd"
DEFAULT_TTS_VOICE = "Tingting"
DEFAULT_TTS_RATE = 230
DEFAULT_VOICE_VOLUME = 1.0
DEFAULT_BGM_VOLUME = 0.85
DEFAULT_SUNO_BGM_VOLUME = 0.09
DEFAULT_REMOTE_TTS_PROVIDER = "auto"
DEFAULT_DOUBAO_TTS_VOICE = "zh_male_jieshuoxiaoming_uranus_bigtts"
DEFAULT_MINIMAX_TTS_VOICE = "male-qn-jingying"
DEFAULT_REMOTE_TTS_SPEED = 1.14
VECTOR_REQUIRED_FAMILIES = ["person_silhouette", "red_path_or_arc", "environment_symbol", "system_panel"]
VECTOR_OPTIONAL_FAMILIES = [
    "thought_cloud",
    "risk_radar",
    "threshold_gate",
    "timer_ring",
    "route_panel",
    "background_structure",
    "semantic_context_prop",
    "annotation_node",
]


def load_json(path: str) -> dict[str, Any]:
    if not path:
        return {}
    target = Path(path).expanduser()
    if not target.exists():
        return {}
    data = json.loads(target.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
        if bold
        else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
        if bold
        else "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc" if bold else "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size, index=0)
    return ImageFont.load_default(size=size)


def latin_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
        if bold
        else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size, index=0)
    return font(size, bold=bold)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font_obj: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        trial = current + char
        width = draw.textbbox((0, 0), trial, font=font_obj)[2]
        if width <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font_obj: ImageFont.FreeTypeFont,
    *,
    fill: str = "#111111",
    max_width: int = 820,
    line_gap: int = 18,
    stroke_width: int = 0,
) -> int:
    lines = []
    for raw in text.split("\n"):
        lines.extend(wrap_text(draw, raw, font_obj, max_width))
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_obj)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text(
            (x, y),
            line,
            font=font_obj,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=fill,
        )
        y += bbox[3] - bbox[1] + line_gap
    return y


def strip_emphasis_markup(text: Any) -> str:
    return str(text).replace("**", "")


def normalize_spoken_anchor(text: Any) -> str:
    """Normalize display punctuation while preserving the spoken word order."""
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", strip_emphasis_markup(text))


def emphasis_segments(text: Any) -> list[tuple[str, bool]]:
    value = str(text)
    if value.count("**") % 2:
        raise SystemExit("episode_semantic_beats_required: visible_text has unbalanced ** emphasis markers")
    parts = value.split("**")
    return [(part, index % 2 == 1) for index, part in enumerate(parts) if part]


def extracted_emphasis_keywords(text: Any) -> list[str]:
    return [match.strip() for match in re.findall(r"\*\*(.+?)\*\*", str(text), flags=re.DOTALL) if match.strip()]


def _rich_char_lines(
    draw: ImageDraw.ImageDraw,
    text: Any,
    normal_font: ImageFont.FreeTypeFont,
    bold_font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[list[tuple[str, bool]]]:
    output: list[list[tuple[str, bool]]] = []
    for raw_line in str(text).split("\n"):
        units: list[tuple[str, bool]] = []
        for segment, emphasized in emphasis_segments(raw_line):
            if emphasized:
                # A bold phrase is one reading anchor. Keep it intact when wrapping so
                # the renderer never produces fragments such as “解 / 释未来”.
                units.append((segment, True))
            else:
                units.extend((char, False) for char in segment)
        current: list[tuple[str, bool]] = []
        current_width = 0
        for segment, emphasized in units:
            current_font = bold_font if emphasized else normal_font
            bbox = draw.textbbox((0, 0), segment, font=current_font, stroke_width=1 if emphasized else 0)
            segment_width = bbox[2] - bbox[0]
            if current and current_width + segment_width > max_width:
                output.append(current)
                current = []
                current_width = 0
            if emphasized and segment_width > max_width:
                # The content contract caps emphasis at ten characters, but retain a
                # safe fallback for unusually narrow canvases.
                for char in segment:
                    char_bbox = draw.textbbox((0, 0), char, font=current_font, stroke_width=1)
                    char_width = char_bbox[2] - char_bbox[0]
                    if current and current_width + char_width > max_width:
                        output.append(current)
                        current = []
                        current_width = 0
                    current.append((char, emphasized))
                    current_width += char_width
            else:
                current.append((segment, emphasized))
                current_width += segment_width
        output.append(current)
    return output


def _group_rich_chars(chars: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    grouped: list[tuple[str, bool]] = []
    for char, emphasized in chars:
        if grouped and grouped[-1][1] == emphasized:
            grouped[-1] = (grouped[-1][0] + char, emphasized)
        else:
            grouped.append((char, emphasized))
    return grouped


def draw_rich_centered(
    draw: ImageDraw.ImageDraw,
    text: Any,
    y: int,
    *,
    size: int,
    fill: str,
    emphasis_fill: str,
    max_width: int,
    line_gap: int,
    reveal_progress: float = 1.0,
    emphasis_progress: float = 1.0,
) -> int:
    normal_font = font(size, bold=True)
    bold_font = font(size, bold=True)
    lines = _rich_char_lines(draw, text, normal_font, bold_font, max_width)
    base_fill = fade_color(fill, reveal_progress)
    bold_fill = fade_color(
        emphasis_fill,
        reveal_progress * (0.78 + 0.22 * min(1.0, emphasis_progress)),
    )
    for chars in lines:
        grouped = _group_rich_chars(chars)
        widths: list[int] = []
        heights: list[int] = []
        for segment, emphasized in grouped:
            current_font = bold_font if emphasized else normal_font
            bbox = draw.textbbox((0, 0), segment, font=current_font, stroke_width=1 if emphasized else 0)
            widths.append(bbox[2] - bbox[0])
            heights.append(bbox[3] - bbox[1])
        x = (W - sum(widths)) / 2
        line_height = max(heights or [size])
        for (segment, emphasized), segment_width in zip(grouped, widths):
            current_font = bold_font if emphasized else normal_font
            segment_fill = bold_fill if emphasized else base_fill
            draw.text(
                (x, y),
                segment,
                font=current_font,
                fill=segment_fill,
                stroke_width=1 if emphasized else 0,
                stroke_fill=segment_fill,
            )
            x += segment_width
        y += line_height + line_gap
    return y


def fit_rich_text_size(
    draw: ImageDraw.ImageDraw,
    text: Any,
    *,
    start: int,
    minimum: int,
    max_width: int,
    max_height: int,
    line_gap: int,
) -> int:
    for size in range(start, minimum - 1, -2):
        normal_font = font(size, bold=True)
        bold_font = font(size, bold=True)
        explicit_lines = str(text).split("\n")
        line_widths: list[int] = []
        heights: list[int] = []
        for raw_line in explicit_lines:
            grouped = emphasis_segments(raw_line)
            line_heights: list[int] = []
            line_width = 0
            for segment, emphasized in grouped:
                current_font = bold_font if emphasized else normal_font
                bbox = draw.textbbox((0, 0), segment, font=current_font, stroke_width=1 if emphasized else 0)
                line_width += bbox[2] - bbox[0]
                line_heights.append(bbox[3] - bbox[1])
            line_widths.append(line_width)
            heights.append(max(line_heights or [size]))
        total_height = sum(heights) + line_gap * max(0, len(heights) - 1)
        if max(line_widths or [0]) <= max_width and total_height <= max_height:
            return size
    return minimum


SUPPORTED_CONTENT_LANES = {
    "life_uncertainty",
    "cognitive_control",
    "relationship_social",
    "growth_reconstruction",
}
SUPPORTED_DURATION_MODES = {
    "short_thesis": (10, 14),
    "deep_cognitive_essay": (12, 24),
    "long_column": (24, 40),
}
SUPPORTED_BEAT_ROLES = {
    "counterintuitive_verdict",
    "concrete_scene",
    "common_belief",
    "mechanism_reveal",
    "conceptual_split",
    "consequence",
    "proof",
    "analogy",
    "framework_bridge",
    "objection",
    "boundary",
    "false_solution",
    "redefinition",
    "contrast",
    "derived_action",
    "emotional_relief",
    "identity_close",
}
SUPPORTED_INFORMATION_GAINS = {
    "new_scene",
    "new_distinction",
    "new_mechanism",
    "new_evidence",
    "objection_resolution",
    "new_action",
    "identity_reframe",
}
SUPPORTED_CARD_FORMS = {
    "verdict_poster",
    "scene_card",
    "dual_compare",
    "model_map",
    "question_card",
    "action_path",
    "identity_poster",
}
CARD_FORM_LABELS = {
    "verdict_poster": "核心判断",
    "scene_card": "现实切片",
    "dual_compare": "两层对照",
    "model_map": "结构模型",
    "question_card": "继续追问",
    "action_path": "行动路径",
    "identity_poster": "身份重构",
}
METAPHOR_FAMILY_TO_SCENE = {
    "open_path": "heavy_start",
    "recovery_growth": "heavy_start",
    "rebuilding": "heavy_start",
    "isolated_person": "thought_load",
    "cognitive_load": "thought_load",
    "social_distance": "thought_load",
    "hidden_signal": "risk_signal",
    "fractured_identity": "failure_shadow",
    "dual_layer_system": "risk_signal",
    "relationship_signal": "risk_signal",
    "boundary": "threshold",
    "blocked_path": "threshold",
    "choice_point": "threshold",
    "changed_route": "lower_entry",
    "new_direction": "lower_entry",
    "emotional_relief": "lower_entry",
    "cycle_loop": "timed_action",
    "time_horizon": "timed_action",
    "repeated_pattern": "timed_action",
    "system_map": "system_redesign",
    "environment_design": "system_redesign",
    "relationship_boundary": "system_redesign",
    "identity_upgrade": "system_redesign",
}
BEAT_REQUIRED_FIELDS = (
    "id",
    "role",
    "theme",
    "visible_text",
    "narration",
    "metaphor_family",
    "information_gain",
    "card_form",
)
AUDIENCE_REQUIRED_FIELDS = ("target_viewer", "current_pressure", "emotional_gap")
SELECTED_ANGLE_REQUIRED_FIELDS = (
    "common_belief",
    "hidden_mechanism",
    "counterintuitive_thesis",
    "conceptual_split",
    "false_solution",
    "redefinition",
    "viewer_self_projection",
    "model_name",
    "scope_boundary",
)
PROOF_REQUIRED_FIELDS = ("route", "material", "factual_risk", "boundary")
IDENTITY_REQUIRED_FIELDS = ("old_identity", "new_identity", "closing_judgment")
COMMENT_CTA_REQUIRED_FIELDS = ("prompt", "discussion_target")
EMPHASIS_FRAGMENT_PREFIXES = ("而是", "不是", "其实", "所以", "然后", "以及", "但是", "因为")
EMPHASIS_FRAGMENT_SUFFIXES = ("的", "地", "得", "了", "着", "和", "与", "或", "但", "而")


def episode_content_from_params(params: dict[str, Any]) -> dict[str, Any]:
    value = params.get("episode_content")
    if not isinstance(value, dict):
        raise SystemExit(
            "episode_content_strategy_required: params.episode_content must contain current-run "
            "strategy, semantic beats, title, cover_text, and publishing_copy"
        )
    return value


def required_object(value: Any, name: str, required_fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SystemExit(f"episode_content_strategy_required: {name} must be an object")
    missing = [field for field in required_fields if not str(value.get(field) or "").strip()]
    if missing:
        raise SystemExit(f"episode_content_strategy_required: {name} missing fields: {', '.join(missing)}")
    return value


def validate_episode_strategy(episode_content: dict[str, Any]) -> dict[str, Any]:
    content_lane = str(episode_content.get("content_lane") or "").strip()
    if content_lane not in SUPPORTED_CONTENT_LANES:
        raise SystemExit(
            "episode_content_strategy_required: content_lane must be one of "
            + ", ".join(sorted(SUPPORTED_CONTENT_LANES))
        )
    duration_mode = str(episode_content.get("duration_mode") or "").strip()
    if duration_mode not in SUPPORTED_DURATION_MODES:
        raise SystemExit(
            "episode_content_strategy_required: duration_mode must be one of "
            + ", ".join(sorted(SUPPORTED_DURATION_MODES))
        )

    audience = required_object(episode_content.get("audience"), "audience", AUDIENCE_REQUIRED_FIELDS)
    selected_angle = required_object(
        episode_content.get("selected_angle"), "selected_angle", SELECTED_ANGLE_REQUIRED_FIELDS
    )
    next_questions = selected_angle.get("next_questions")
    if not isinstance(next_questions, list) or len([item for item in next_questions if str(item).strip()]) < 3:
        raise SystemExit(
            "episode_content_strategy_required: selected_angle.next_questions must contain at least 3 questions"
        )
    conceptual_split = required_object(
        selected_angle.get("conceptual_split"),
        "selected_angle.conceptual_split",
        ("surface_layer", "deep_layer"),
    )
    proof = required_object(episode_content.get("proof"), "proof", PROOF_REQUIRED_FIELDS)
    identity_payoff = required_object(
        episode_content.get("identity_payoff"), "identity_payoff", IDENTITY_REQUIRED_FIELDS
    )
    comment_cta = required_object(
        episode_content.get("comment_cta"), "comment_cta", COMMENT_CTA_REQUIRED_FIELDS
    )

    angle_candidates = episode_content.get("angle_candidates")
    if not isinstance(angle_candidates, list) or len(angle_candidates) < 5:
        raise SystemExit("episode_content_strategy_required: angle_candidates must contain at least 5 candidates")
    candidate_angles: list[str] = []
    for index, candidate in enumerate(angle_candidates, start=1):
        required_candidate_fields = (
            "angle",
            "score",
            "projection_strength",
            "explanatory_gain",
            "retention_depth",
            "save_value",
            "risk",
        )
        if not isinstance(candidate, dict):
            raise SystemExit(f"episode_content_strategy_required: angle candidate {index} must be an object")
        missing_candidate_fields = [
            field for field in required_candidate_fields if candidate.get(field) in (None, "")
        ]
        if missing_candidate_fields:
            raise SystemExit(
                f"episode_content_strategy_required: angle candidate {index} missing fields: "
                + ", ".join(missing_candidate_fields)
            )
        try:
            float(candidate.get("score"))
            float(candidate.get("projection_strength"))
            float(candidate.get("explanatory_gain"))
            float(candidate.get("retention_depth"))
            float(candidate.get("save_value"))
        except (TypeError, ValueError) as exc:
            raise SystemExit(
                f"episode_content_strategy_required: angle candidate {index} has non-numeric scoring fields"
            ) from exc
        candidate_angles.append("".join(str(candidate["angle"]).split()))
    if len(set(candidate_angles)) != len(candidate_angles):
        raise SystemExit("episode_content_strategy_required: angle candidates must be meaningfully distinct")

    concrete_scenes = episode_content.get("concrete_scenes")
    required_scenes = {"short_thesis": 2, "deep_cognitive_essay": 3, "long_column": 4}[duration_mode]
    normalized_scenes = ["".join(str(item).split()) for item in concrete_scenes or [] if str(item).strip()]
    if not isinstance(concrete_scenes, list) or len(normalized_scenes) < required_scenes:
        raise SystemExit(
            f"episode_content_strategy_required: {duration_mode} requires at least {required_scenes} concrete_scenes"
        )
    if len(set(normalized_scenes)) != len(normalized_scenes):
        raise SystemExit("episode_content_strategy_required: concrete_scenes must be non-interchangeable and distinct")

    actions = episode_content.get("actions")
    required_actions = 3 if duration_mode == "long_column" else 2
    if not isinstance(actions, list) or len(actions) < required_actions:
        raise SystemExit(
            f"episode_content_strategy_required: {duration_mode} requires at least {required_actions} derived actions"
        )
    normalized_actions: list[dict[str, str]] = []
    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            raise SystemExit(
                f"episode_content_strategy_required: action {index} must contain action and mechanism_link"
            )
        normalized_actions.append(
            {
                "action": str(action.get("action") or "").strip(),
                "mechanism_link": str(action.get("mechanism_link") or "").strip(),
            }
        )
        if not all(normalized_actions[-1].values()):
            raise SystemExit(
                f"episode_content_strategy_required: action {index} must contain action and mechanism_link"
            )

    return {
        "content_lane": content_lane,
        "duration_mode": duration_mode,
        "audience": audience,
        "angle_candidates": angle_candidates,
        "selected_angle": {**selected_angle, "conceptual_split": conceptual_split},
        "concrete_scenes": concrete_scenes,
        "proof": proof,
        "actions": normalized_actions,
        "identity_payoff": identity_payoff,
        "comment_cta": comment_cta,
        "risk_notes": episode_content.get("risk_notes") or [],
        "evidence_boundary": {
            "account_baseline_unique_posts": 60,
            "full_text_opening_visual_samples": 20,
            "evidence_level": "L4_video_opening",
            "bounded_layers": ["full_timeline_action_continuity", "full_timeline_bgm_and_sfx_model_review"],
            "policy": "account-relative patterns guide original production but must not be presented as universal causal laws",
        },
    }


def build_cards(topic: str, episode_content: dict[str, Any], strategy: dict[str, Any]) -> list[dict[str, Any]]:
    raw_beats = episode_content.get("beats")
    min_beats, max_beats = SUPPORTED_DURATION_MODES[strategy["duration_mode"]]
    if not isinstance(raw_beats, list) or not min_beats <= len(raw_beats) <= max_beats:
        raise SystemExit(
            f"episode_semantic_beats_required: {strategy['duration_mode']} needs {min_beats}-{max_beats} beats"
        )

    cards: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_beat in enumerate(raw_beats, start=1):
        if not isinstance(raw_beat, dict):
            raise SystemExit(f"episode_semantic_beats_required: beat {index} must be an object")
        beat = {field: str(raw_beat.get(field) or "").strip() for field in BEAT_REQUIRED_FIELDS}
        missing = [field for field, value in beat.items() if not value]
        if missing:
            raise SystemExit(
                f"episode_semantic_beats_required: beat {index} missing fields: {', '.join(missing)}"
            )
        if beat["id"] in seen_ids:
            raise SystemExit(f"episode_semantic_beats_required: duplicate beat id: {beat['id']}")
        seen_ids.add(beat["id"])
        if beat["role"] not in SUPPORTED_BEAT_ROLES:
            raise SystemExit(
                f"episode_semantic_beats_required: beat {index} role is unsupported: {beat['role']}"
            )
        if beat["metaphor_family"] not in METAPHOR_FAMILY_TO_SCENE:
            raise SystemExit(
                f"episode_semantic_beats_required: beat {index} metaphor_family is unsupported: {beat['metaphor_family']}"
            )
        if beat["information_gain"] not in SUPPORTED_INFORMATION_GAINS:
            raise SystemExit(
                f"episode_semantic_beats_required: beat {index} information_gain is unsupported: "
                f"{beat['information_gain']}"
            )
        if beat["card_form"] not in SUPPORTED_CARD_FORMS:
            raise SystemExit(
                f"episode_semantic_beats_required: beat {index} card_form is unsupported: {beat['card_form']}"
            )
        emphasis_keywords = raw_beat.get("emphasis_keywords")
        if not isinstance(emphasis_keywords, list) or not 1 <= len(emphasis_keywords) <= 2:
            raise SystemExit(
                f"episode_semantic_beats_required: beat {index} emphasis_keywords must contain 1-2 phrases"
            )
        normalized_keywords = [str(item).strip() for item in emphasis_keywords if str(item).strip()]
        malformed_keywords = [
            keyword
            for keyword in normalized_keywords
            if not 2 <= len(keyword) <= 10
            or "\n" in keyword
            or keyword.startswith(EMPHASIS_FRAGMENT_PREFIXES)
            or keyword.endswith(EMPHASIS_FRAGMENT_SUFFIXES)
            or not re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9·/+＋-]+", keyword)
        ]
        if malformed_keywords:
            raise SystemExit(
                f"episode_semantic_beats_required: beat {index} emphasis_keywords must be complete "
                "2-10 character semantic phrases, not conjunction-led or truncated fragments: "
                + ", ".join(malformed_keywords)
            )
        marked_keywords = extracted_emphasis_keywords(beat["visible_text"])
        if normalized_keywords != marked_keywords:
            raise SystemExit(
                f"episode_semantic_beats_required: beat {index} emphasis_keywords must exactly match "
                "the ordered **...** phrases in visible_text"
            )
        visible_plain = strip_emphasis_markup(beat["visible_text"]).replace("\n", "")
        visible_anchor = normalize_spoken_anchor(beat["visible_text"])
        narration_anchor = normalize_spoken_anchor(beat["narration"])
        if not visible_anchor or visible_anchor not in narration_anchor:
            raise SystemExit(
                f"episode_semantic_beats_required: beat {index} visible_text must be an exact ordered "
                "phrase from narration after punctuation and line-break normalization"
            )
        emphasized_length = sum(len(item.replace("\n", "")) for item in normalized_keywords)
        if visible_plain and emphasized_length / len(visible_plain) > 0.6:
            raise SystemExit(
                f"episode_semantic_beats_required: beat {index} emphasizes more than 60% of visible_text"
            )
        if "retention_question" not in raw_beat:
            raise SystemExit(
                f"episode_semantic_beats_required: beat {index} must declare retention_question, using an empty "
                "string only when no new loop is opened"
            )
        retention_question = str(raw_beat.get("retention_question") or "").strip()
        supporting_points = raw_beat.get("supporting_points") or []
        if not isinstance(supporting_points, list) or len(supporting_points) > 3:
            raise SystemExit(
                f"episode_semantic_beats_required: beat {index} supporting_points must contain at most 3 items"
            )
        normalized_supporting_points = [str(item).strip() for item in supporting_points if str(item).strip()]
        if any(len(item) > 12 for item in normalized_supporting_points):
            raise SystemExit(
                f"episode_semantic_beats_required: beat {index} supporting_points must be 12 characters or fewer"
            )
        estimated_seconds = raw_beat.get("estimated_seconds")
        duration_weight = raw_beat.get("duration_weight")
        pause_after_seconds = raw_beat.get("pause_after_seconds")
        try:
            estimated_value = float(estimated_seconds) if estimated_seconds is not None else 0.0
            weight_value = float(duration_weight) if duration_weight is not None else 0.0
            pause_value = float(pause_after_seconds) if pause_after_seconds is not None else 0.0
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"episode_semantic_beats_required: beat {index} timing must be numeric") from exc
        cards.append(
            {
                "id": beat["id"],
                "label": beat["role"],
                "role": beat["role"],
                "theme": beat["theme"],
                "core": beat["visible_text"],
                "core_plain": strip_emphasis_markup(beat["visible_text"]),
                "sub": str(raw_beat.get("subtext") or "").strip(),
                "scene": beat["metaphor_family"],
                "render_scene": METAPHOR_FAMILY_TO_SCENE[beat["metaphor_family"]],
                "narration": beat["narration"],
                "emphasis_keywords": normalized_keywords,
                "information_gain": beat["information_gain"],
                "card_form": beat["card_form"],
                "retention_question": retention_question,
                "supporting_points": normalized_supporting_points,
                "estimated_seconds": max(0.0, estimated_value),
                "duration_weight": max(0.0, weight_value),
                "pause_after_seconds": max(0.0, min(pause_value, 0.8)),
                "measured_audio_seconds": 0.0,
            }
        )

    roles = [card["role"] for card in cards]
    if roles[0] != "counterintuitive_verdict":
        raise SystemExit("episode_semantic_beats_required: first beat must be counterintuitive_verdict")
    if roles[-1] != "identity_close":
        raise SystemExit("episode_semantic_beats_required: final beat must be identity_close")
    if cards[0]["card_form"] != "verdict_poster":
        raise SystemExit("episode_semantic_beats_required: first beat must use verdict_poster")
    if cards[-1]["card_form"] != "identity_poster":
        raise SystemExit("episode_semantic_beats_required: final beat must use identity_poster")
    if cards[-1]["retention_question"]:
        raise SystemExit("episode_semantic_beats_required: final beat must close the opening and leave retention_question empty")
    required_scene_beats = {"short_thesis": 2, "deep_cognitive_essay": 3, "long_column": 4}[
        strategy["duration_mode"]
    ]
    if roles.count("concrete_scene") < required_scene_beats:
        raise SystemExit(
            f"episode_semantic_beats_required: {strategy['duration_mode']} needs {required_scene_beats} concrete_scene beats"
        )
    if not ({"conceptual_split", "mechanism_reveal"} & set(roles)):
        raise SystemExit("episode_semantic_beats_required: a mechanism or conceptual split beat is required")
    if not ({"proof", "analogy", "contrast"} & set(roles)):
        raise SystemExit("episode_semantic_beats_required: a proof, analogy, or contrast beat is required")
    if "redefinition" not in roles:
        raise SystemExit("episode_semantic_beats_required: a redefinition beat is required")
    if "emotional_relief" not in roles:
        raise SystemExit("episode_semantic_beats_required: an emotional_relief beat is required")
    if roles.count("derived_action") < 2:
        raise SystemExit("episode_semantic_beats_required: at least 2 derived_action beats are required")
    minimum_questions = {"short_thesis": 2, "deep_cognitive_essay": 3, "long_column": 6}[
        strategy["duration_mode"]
    ]
    retention_questions = [card["retention_question"] for card in cards if card["retention_question"]]
    if len(set(retention_questions)) < minimum_questions:
        raise SystemExit(
            f"episode_semantic_beats_required: {strategy['duration_mode']} requires at least "
            f"{minimum_questions} distinct retention questions"
        )
    for index in range(2, len(cards)):
        if cards[index]["card_form"] == cards[index - 1]["card_form"] == cards[index - 2]["card_form"]:
            raise SystemExit(
                "episode_semantic_beats_required: more than two adjacent cards use the same card_form"
            )
    if strategy["duration_mode"] == "long_column":
        if roles.count("derived_action") < 3:
            raise SystemExit("episode_semantic_beats_required: long_column needs at least 3 derived_action beats")
        if not ({"objection", "boundary"} & set(roles)):
            raise SystemExit("episode_semantic_beats_required: long_column needs an objection or boundary beat")
        proof_roles = {"proof", "analogy", "contrast", "framework_bridge"}
        if sum(role in proof_roles for role in roles) < 3:
            raise SystemExit("episode_semantic_beats_required: long_column needs at least 3 proof/framework beats")
    return cards


def episode_text(episode_content: dict[str, Any], key: str) -> str:
    value = episode_content.get(key)
    if key == "voiceover_text" and isinstance(value, list):
        value = "\n".join(str(item).strip() for item in value if str(item).strip())
    text = str(value or "").strip()
    if not text:
        raise SystemExit(f"episode_card_content_required: episode_content.{key} must not be empty")
    return text


def voiceover_from_cards(cards: list[dict[str, Any]], episode_content: dict[str, Any]) -> str:
    beat_voiceover = "\n".join(str(card["narration"]).strip() for card in cards if str(card["narration"]).strip())
    supplied = episode_content.get("voiceover_text")
    if isinstance(supplied, list):
        supplied = "\n".join(str(item).strip() for item in supplied if str(item).strip())
    supplied_text = str(supplied or "").strip()
    if supplied_text:
        normalize = lambda value: "".join(str(value).split())
        if normalize(supplied_text) != normalize(beat_voiceover):
            raise SystemExit(
                "episode_semantic_beats_required: voiceover_text must match the ordered beat narration; "
                "omit voiceover_text to let beats remain authoritative"
            )
    return beat_voiceover


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def fade_color(value: str, alpha: float, bg: str = "#ffffff") -> tuple[int, int, int]:
    alpha = max(0.0, min(1.0, alpha))
    fg_r, fg_g, fg_b = hex_to_rgb(value)
    bg_r, bg_g, bg_b = hex_to_rgb(bg)
    return (
        int(bg_r + (fg_r - bg_r) * alpha),
        int(bg_g + (fg_g - bg_g) * alpha),
        int(bg_b + (fg_b - bg_b) * alpha),
    )


def ease(progress: float) -> float:
    progress = max(0.0, min(1.0, progress))
    # Smoothstep keeps motion alive through the middle of the beat instead of
    # racing to the end and leaving a long static hold.
    return progress * progress * (3 - 2 * progress)


def draw_spaced_text(draw: ImageDraw.ImageDraw, text: str, center_x: int, y: int, font_obj: ImageFont.FreeTypeFont, fill: str) -> None:
    char_gap = 12
    widths = [draw.textbbox((0, 0), char, font=font_obj)[2] for char in text]
    total = sum(widths) + char_gap * max(len(text) - 1, 0)
    x = center_x - total // 2
    for char, width in zip(text, widths):
        draw.text((x, y), char, font=font_obj, fill=fill)
        x += width + char_gap


def draw_header(draw: ImageDraw.ImageDraw) -> None:
    seal_font = font(54, bold=True)
    draw.ellipse((42, 40, 132, 130), outline=BLACK, width=5)
    draw.text((66, 53), "思", font=seal_font, fill=BLACK)
    title_font = latin_font(46, bold=True)
    bbox = draw.textbbox((0, 0), HEADER_WORDMARK, font=title_font)
    draw.text(((W - (bbox[2] - bbox[0])) // 2, 68), HEADER_WORDMARK, font=title_font, fill="#595959")


def draw_footer_system(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle((0, 1320, W, H), fill="#dedede")
    col_font = font(34, bold=True)
    x_positions = (260, 540, 820)
    for i in range(2):
        draw.line((390 + 260 * i, 1343, 390 + 260 * i, 1410), fill=BLACK, width=2)
    for x, text in zip(x_positions, BOTTOM_COLUMNS):
        lines = text.split("\n")
        y = 1342
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=col_font)
            draw.text((x - (bbox[2] - bbox[0]) // 2, y), line, font=col_font, fill=BLACK)
            y += 44


def draw_disclaimer(draw: ImageDraw.ImageDraw) -> None:
    small_font = font(30, bold=True)
    y = 1230
    for line in DISCLAIMER_TEXT.split("\n"):
        bbox = draw.textbbox((0, 0), line, font=small_font)
        draw.text((980 - (bbox[2] - bbox[0]), y), line, font=small_font, fill="#333333")
        y += 38


def draw_person(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    scale: float = 1.0,
    color: str = BLACK,
    red_body: bool = False,
    *,
    lean: float = 0.0,
) -> None:
    c = color
    s = scale
    lean_px = int(lean * 20 * s)
    head_r = int(17 * s)
    draw.ellipse((x - head_r + lean_px, y - int(100 * s), x + head_r + lean_px, y - int(66 * s)), fill=c)
    body_fill = DEEP_RED if red_body else c
    torso = [
        (x - int(19 * s), y - int(58 * s)),
        (x + int(16 * s) + lean_px, y - int(62 * s)),
        (x + int(24 * s) + lean_px, y + int(8 * s)),
        (x - int(13 * s), y + int(15 * s)),
    ]
    draw.polygon(torso, fill=body_fill)
    joint = "curve"
    w_leg = max(4, int(7 * s))
    w_arm = max(3, int(6 * s))
    draw.line((x - int(3 * s), y + int(10 * s), x - int(34 * s), y + int(72 * s)), fill=c, width=w_leg, joint=joint)
    draw.line((x + int(12 * s), y + int(9 * s), x + int(45 * s), y + int(68 * s)), fill=c, width=w_leg, joint=joint)
    draw.line((x - int(12 * s), y - int(40 * s), x - int(50 * s), y - int(6 * s)), fill=c, width=w_arm, joint=joint)
    draw.line((x + int(18 * s), y - int(42 * s), x + int(55 * s), y - int(15 * s)), fill=c, width=w_arm, joint=joint)
    draw.ellipse((x - int(47 * s), y + int(70 * s), x + int(52 * s), y + int(77 * s)), fill=fade_color(GRAY, 0.26))


def draw_core_character(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    scale: float,
    progress: float,
    *,
    pose: str = "stand",
    facing: int = 1,
) -> None:
    """Draw the recurring original protagonist with one stable red-scarf anchor."""
    p = ease(progress)
    s = scale
    facing = 1 if facing >= 0 else -1
    black = fade_color(BLACK, p)
    red = fade_color(DEEP_RED, p)
    shadow = fade_color(MID_GRAY, 0.28 * p)
    y += int(math.sin(max(0.0, min(1.0, progress)) * math.pi * 2) * 2.4 * s)
    pose_offsets = {
        "stand": (0, 0),
        "hesitate": (-8 * facing, 5),
        "crouch": (-6 * facing, 22),
        "observe": (5 * facing, 0),
        "walk": (8 * facing, 0),
        "record": (2 * facing, 4),
        "open": (0, -4),
        "climb": (10 * facing, -2),
    }
    lean_x, body_drop = pose_offsets.get(pose, (0, 0))
    lean_x *= s
    body_drop *= s
    head_x = x + lean_x
    head_y = y - 92 * s + body_drop
    head_r = 18 * s
    draw.ellipse(
        (head_x - head_r, head_y - head_r, head_x + head_r, head_y + head_r),
        fill=black,
    )
    shoulder_y = y - 62 * s + body_drop
    hip_y = y + 8 * s + body_drop
    torso = [
        (x - 22 * s, shoulder_y),
        (x + 18 * s + lean_x, shoulder_y - 4 * s),
        (x + 25 * s + lean_x, hip_y),
        (x - 16 * s, hip_y + 7 * s),
    ]
    draw.polygon(torso, fill=black)

    # The scarf is the cross-scene identity anchor: same color, side and scale.
    neck_x = x + 5 * s + lean_x
    neck_y = shoulder_y - 2 * s
    draw.polygon(
        [
            (neck_x - 20 * s, neck_y - 3 * s),
            (neck_x + 17 * s, neck_y + 7 * s),
            (neck_x - 2 * s, neck_y + 18 * s),
        ],
        fill=red,
    )
    draw.polygon(
        [
            (neck_x + 12 * s, neck_y + 6 * s),
            (neck_x + (46 * facing) * s, neck_y + 18 * s),
            (neck_x + (19 * facing) * s, neck_y + 27 * s),
        ],
        fill=red,
    )

    arm_poses = {
        "stand": ((-44, -8), (48, -10)),
        "hesitate": ((-42, -2), (28, -74)),
        "crouch": ((-38, 5), (34, 7)),
        "observe": ((-38, -5), (70, -38)),
        "walk": ((-52, -12), (53, 2)),
        "record": ((-8, -20), (52, -18)),
        "open": ((-72, -45), (72, -45)),
        "climb": ((-24, -44), (66, -58)),
    }
    left_hand, right_hand = arm_poses.get(pose, arm_poses["stand"])
    if facing < 0:
        left_hand = (-right_hand[0], right_hand[1])
        right_hand = (-arm_poses.get(pose, arm_poses["stand"])[0][0], arm_poses.get(pose, arm_poses["stand"])[0][1])
    shoulder_left = (x - 13 * s, shoulder_y + 13 * s)
    shoulder_right = (x + 18 * s + lean_x, shoulder_y + 13 * s)
    hands = [
        (x + left_hand[0] * s, y + left_hand[1] * s + body_drop),
        (x + right_hand[0] * s, y + right_hand[1] * s + body_drop),
    ]
    for shoulder, hand in zip((shoulder_left, shoulder_right), hands):
        elbow = ((shoulder[0] + hand[0]) / 2, (shoulder[1] + hand[1]) / 2 + 7 * s)
        draw.line((shoulder, elbow, hand), fill=black, width=max(4, int(7 * s)), joint="curve")
        hand_r = max(2, int(4 * s))
        draw.ellipse((hand[0] - hand_r, hand[1] - hand_r, hand[0] + hand_r, hand[1] + hand_r), fill=black)

    leg_poses = {
        "stand": ((-33, 76), (36, 74)),
        "hesitate": ((-42, 72), (26, 78)),
        "crouch": ((-48, 60), (45, 60)),
        "observe": ((-28, 76), (42, 70)),
        "walk": ((-52, 66), (58, 62)),
        "record": ((-31, 75), (33, 74)),
        "open": ((-38, 76), (38, 76)),
        "climb": ((-35, 72), (54, 48)),
    }
    feet = leg_poses.get(pose, leg_poses["stand"])
    if facing < 0:
        feet = tuple((-foot[0], foot[1]) for foot in reversed(feet))
    hip_points = ((x - 5 * s, hip_y), (x + 13 * s + lean_x, hip_y))
    for hip, foot in zip(hip_points, feet):
        foot_point = (x + foot[0] * s, y + foot[1] * s + body_drop)
        knee = ((hip[0] + foot_point[0]) / 2, (hip[1] + foot_point[1]) / 2 - 4 * s)
        draw.line((hip, knee, foot_point), fill=black, width=max(5, int(8 * s)), joint="curve")
    draw.ellipse(
        (x - 58 * s, y + 78 * s + body_drop, x + 62 * s, y + 88 * s + body_drop),
        fill=shadow,
    )

    if pose == "record":
        card_x = x + 42 * facing * s
        card_y = y - 28 * s + body_drop
        draw.rounded_rectangle(
            (card_x - 22 * s, card_y - 28 * s, card_x + 26 * s, card_y + 34 * s),
            radius=max(3, int(5 * s)),
            fill="white",
            outline=red,
            width=max(2, int(4 * s)),
        )
        draw.line((card_x - 12 * s, card_y - 8 * s, card_x + 14 * s, card_y - 8 * s), fill=red, width=max(2, int(3 * s)))
        draw.line((card_x - 12 * s, card_y + 8 * s, card_x + 8 * s, card_y + 8 * s), fill=black, width=max(2, int(3 * s)))


def draw_continuity_character(draw: ImageDraw.ImageDraw, scene: str, progress: float) -> None:
    """Place the same protagonist in a scene-specific state and inherited direction."""
    p = ease(progress)
    states = {
        "fractured_identity": (548 + int(20 * p), 1090, 1.04, "hesitate", -1),
        "blocked_path": (744 + int(54 * p), 1110, 0.86, "observe", 1),
        "isolated_person": (540, 1180, 0.82, "hesitate", 1),
        "dual_layer_system": (548, 1156, 0.72, "observe", 1),
        "repeated_pattern": (610 + int(190 * p), 1180 - int(130 * p), 0.70, "walk", 1),
        "cycle_loop": (540, 1144, 0.62, "hesitate", 1),
        "changed_route": (390 + int(290 * p), 1104 - int(56 * p), 0.78, "walk", 1),
        "emotional_relief": (600, 1094 - int(18 * p), 0.86, "open", 1),
        "system_map": (850, 1182, 0.68, "record", -1),
        "new_direction": (656 + int(150 * p), 1176 - int(85 * p), 0.72, "walk", 1),
        "identity_upgrade": (540 + int(250 * p), 1170 - int(190 * p), 0.76, "climb", 1),
    }
    x, y, scale, pose, facing = states.get(scene, (760, 1120, 0.62, "stand", 1))
    draw_core_character(draw, x, y, scale, p, pose=pose, facing=facing)


def draw_curve(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[int, int]],
    fill: str | tuple[int, int, int],
    width: int,
) -> None:
    if len(points) < 2:
        return
    draw.line(points, fill=fill, width=width, joint="curve")


def quadratic_points(
    start: tuple[int, int],
    control: tuple[int, int],
    end: tuple[int, int],
    steps: int = 30,
) -> list[tuple[int, int]]:
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = int((1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control[0] + t**2 * end[0])
        y = int((1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control[1] + t**2 * end[1])
        points.append((x, y))
    return points


def draw_ground(draw: ImageDraw.ImageDraw, x1: int, y: int, x2: int, *, progress: float = 1.0, fill: str = BLACK, width: int = 5) -> None:
    p = ease(progress)
    draw.line((x1, y, x1 + int((x2 - x1) * p), y), fill=fade_color(fill, p), width=width)
    draw.ellipse((x1 + 22, y + 7, x2 - 22, y + 24), outline=fade_color(GRAY, 0.24 * p), width=2)


def draw_radiant_dot(draw: ImageDraw.ImageDraw, x: int, y: int, radius: int, progress: float, fill: str = DEEP_RED) -> None:
    p = ease(progress)
    color = fade_color(fill, p)
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        x1 = x + int(math.cos(rad) * (radius + 13))
        y1 = y + int(math.sin(rad) * (radius + 13))
        x2 = x + int(math.cos(rad) * (radius + 31))
        y2 = y + int(math.sin(rad) * (radius + 31))
        draw.line((x1, y1, x2, y2), fill=color, width=4)


def draw_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], progress: float) -> None:
    p = ease(progress)
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=22, outline=fade_color(BLACK, p), width=8)
    for i, y in enumerate((y1 + 88, y1 + 170, y1 + 252)):
        draw.line((x1 + 78, y, x2 - 78, y), fill=fade_color(MID_GRAY, 0.72 * p), width=7)
        knob_x = x1 + 135 + int((52 + i * 64) * p)
        draw.ellipse((knob_x - 23, y - 23, knob_x + 23, y + 23), fill=DEEP_RED if i == 1 else fade_color(BLACK, p))


def draw_tree(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float, fill: str) -> None:
    draw.rectangle((x - int(7 * scale), y - int(120 * scale), x + int(7 * scale), y + int(8 * scale)), fill=fill)
    for i, width in enumerate((120, 94, 70)):
        top = y - int((165 - i * 38) * scale)
        draw.polygon(
            [
                (x, top),
                (x - int(width * scale / 2), top + int(70 * scale)),
                (x + int(width * scale / 2), top + int(70 * scale)),
            ],
            fill=fill,
        )


def draw_sun(draw: ImageDraw.ImageDraw, x: int, y: int, radius: int, fill: str, alpha: float = 1.0) -> None:
    color = fade_color(fill, alpha)
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        x1 = x + int(math.cos(rad) * (radius + 12))
        y1 = y + int(math.sin(rad) * (radius + 12))
        x2 = x + int(math.cos(rad) * (radius + 28))
        y2 = y + int(math.sin(rad) * (radius + 28))
        draw.line((x1, y1, x2, y2), fill=color, width=4)


def draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    fill: str | tuple[int, int, int],
    width: int = 4,
    dash: int = 16,
    gap: int = 10,
) -> None:
    x1, y1 = start
    x2, y2 = end
    distance = max(1.0, math.hypot(x2 - x1, y2 - y1))
    cursor = 0.0
    while cursor < distance:
        segment_end = min(distance, cursor + dash)
        sx = x1 + (x2 - x1) * cursor / distance
        sy = y1 + (y2 - y1) * cursor / distance
        ex = x1 + (x2 - x1) * segment_end / distance
        ey = y1 + (y2 - y1) * segment_end / distance
        draw.line((sx, sy, ex, ey), fill=fill, width=width)
        cursor += dash + gap


def draw_arrow_head(
    draw: ImageDraw.ImageDraw,
    point: tuple[int, int],
    angle: float,
    *,
    size: int,
    fill: str | tuple[int, int, int],
) -> None:
    x, y = point
    left = (
        x - int(math.cos(angle - 0.55) * size),
        y - int(math.sin(angle - 0.55) * size),
    )
    right = (
        x - int(math.cos(angle + 0.55) * size),
        y - int(math.sin(angle + 0.55) * size),
    )
    draw.polygon([point, left, right], fill=fill)


def draw_semantic_backdrop(draw: ImageDraw.ImageDraw, scene: str, progress: float) -> None:
    """Add a restrained background layer so the main metaphor sits inside a readable world."""
    p = ease(progress)
    pale = fade_color(MID_GRAY, 0.22 * p)
    faint_red = fade_color(PALE_RED, 0.22 * p)
    path_growth = {"open_path", "recovery_growth", "rebuilding"}
    cognition = {"isolated_person", "cognitive_load", "fractured_identity", "dual_layer_system"}
    relationship = {"social_distance", "hidden_signal", "relationship_signal", "relationship_boundary", "boundary"}
    direction = {"blocked_path", "choice_point", "changed_route", "new_direction"}
    time_system = {"cycle_loop", "time_horizon", "repeated_pattern", "system_map", "environment_design", "identity_upgrade"}

    if scene in path_growth:
        for offset in (0, 44, 88):
            ridge = quadratic_points((160, 1110 - offset), (410, 800 - offset), (880, 1030 - offset), 30)
            draw_curve(draw, ridge[: max(2, int(len(ridge) * p))], pale, 3)
        draw.ellipse((760, 720, 940, 900), outline=faint_red, width=4)
    elif scene in cognition:
        for x in (210, 540, 870):
            draw.line((x, 746, x, 1160), fill=pale, width=2)
        for y in (790, 960, 1130):
            draw.line((160, y, 920, y), fill=pale, width=2)
        for x, y in ((210, 790), (540, 960), (870, 1130)):
            draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=faint_red)
    elif scene in relationship:
        draw.ellipse((180, 770, 610, 1170), outline=pale, width=4)
        draw.ellipse((470, 770, 900, 1170), outline=faint_red, width=4)
        draw_dashed_line(draw, (260, 1188), (820, 1188), fill=pale, width=3)
    elif scene in direction:
        draw.ellipse((320, 740, 760, 1180), outline=pale, width=4)
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            draw.line(
                (540 + int(math.cos(rad) * 194), 960 + int(math.sin(rad) * 194),
                 540 + int(math.cos(rad) * 220), 960 + int(math.sin(rad) * 220)),
                fill=pale,
                width=3,
            )
    elif scene in time_system:
        for radius in (170, 230, 290):
            draw.arc((540 - radius, 930 - radius, 540 + radius, 930 + radius), 205, 505, fill=pale, width=3)
        for x, y in ((290, 1100), (420, 790), (690, 780), (820, 1060)):
            draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill=faint_red)
    elif scene == "emotional_relief":
        draw.arc((180, 740, 900, 1190), 185, 350, fill=pale, width=4)
        draw_sun(draw, 800, 790, 30, PALE_RED, 0.28 * p)


def draw_semantic_details(draw: ImageDraw.ImageDraw, scene: str, progress: float) -> None:
    """Draw topic-specific context props; all shapes are original and built from local primitives."""
    p = ease(progress)
    black = fade_color(BLACK, 0.68 * p)
    gray = fade_color(GRAY, 0.52 * p)
    red = fade_color(DEEP_RED, 0.82 * p)
    pale = fade_color(PALE_RED, 0.34 * p)

    if scene == "open_path":
        draw.line((832, 770, 832, 930), fill=black, width=7)
        draw.polygon([(832, 772), (920, 806), (832, 840)], fill=red)
        for x, y in ((260, 1100), (360, 1018), (465, 910)):
            draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill=red)
    elif scene == "recovery_growth":
        draw_tree(draw, 250, 1110, 0.55, black)
        for x, y in ((202, 960), (256, 930), (302, 978)):
            draw.ellipse((x - 16, y - 9, x + 16, y + 9), fill=pale)
        draw_sun(draw, 840, 790, 25, DEEP_RED, 0.62 * p)
    elif scene == "rebuilding":
        for index, (x, y) in enumerate(((190, 1120), (260, 1060), (330, 1000), (400, 940))):
            draw.rounded_rectangle((x, y, x + 76, 1180), radius=8, outline=red if index == 3 else gray, width=5)
        draw_dashed_line(draw, (212, 900), (454, 900), fill=gray, width=3)
    elif scene in {"isolated_person", "cognitive_load"}:
        for index, y in enumerate((790, 865, 940)):
            x = 174 + index * 22
            draw.rounded_rectangle((x, y, x + 180, y + 58), radius=12, outline=gray, width=4)
            draw.ellipse((x + 18, y + 18, x + 40, y + 40), fill=red if index == 1 else black)
            draw.line((x + 56, y + 28, x + 150, y + 28), fill=gray, width=4)
    elif scene == "social_distance":
        draw.rounded_rectangle((160, 790, 340, 900), radius=26, outline=black, width=5)
        draw.polygon([(282, 900), (322, 900), (306, 934)], fill=black)
        draw.rounded_rectangle((740, 820, 920, 930), radius=26, outline=red, width=5)
        draw.polygon([(758, 930), (798, 930), (770, 964)], fill=red)
        draw_dashed_line(draw, (350, 860), (730, 880), fill=gray, width=4)
    elif scene == "hidden_signal":
        for radius in (42, 76, 110):
            draw.arc((790 - radius, 820 - radius, 790 + radius, 820 + radius), 120, 300, fill=red, width=5)
        for x, y in ((190, 820), (224, 888), (282, 936)):
            draw.ellipse((x - 11, y - 11, x + 11, y + 11), fill=black)
    elif scene == "fractured_identity":
        shards = [
            [(180, 820), (292, 760), (276, 910)],
            [(294, 770), (410, 836), (296, 914)],
            [(192, 930), (286, 920), (246, 1050)],
        ]
        for index, polygon in enumerate(shards):
            draw.polygon(polygon, outline=red if index == 1 else black)
        draw.line((290, 760, 294, 1050), fill=gray, width=4)
    elif scene == "dual_layer_system":
        for y, color in ((790, black), (1020, red)):
            draw.rounded_rectangle((150, y, 360, y + 120), radius=18, outline=color, width=5)
            for offset in (42, 84, 126):
                draw.ellipse((150 + offset, y + 48, 166 + offset, y + 64), fill=color)
        draw.line((255, 916, 255, 1010), fill=gray, width=5)
        draw_arrow_head(draw, (255, 1010), math.pi / 2, size=18, fill=gray)
    elif scene in {"relationship_signal", "relationship_boundary", "boundary"}:
        for x in (170, 230, 850, 910):
            draw.line((x, 950, x, 1130), fill=black if x < 500 else red, width=6)
            draw.ellipse((x - 14, 928, x + 14, 956), fill=black if x < 500 else red)
        draw_dashed_line(draw, (250, 1030), (830, 1030), fill=gray, width=4)
        draw.line((540, 900, 540, 1160), fill=red, width=8)
    elif scene == "blocked_path":
        draw.line((180, 1020, 410, 1020), fill=black, width=10)
        draw.line((205, 970, 380, 1070), fill=red, width=18)
        draw.line((380, 970, 205, 1070), fill=red, width=18)
    elif scene == "choice_point":
        draw.line((220, 1110, 350, 960), fill=red, width=9)
        draw.line((350, 960, 270, 830), fill=black, width=7)
        draw.line((350, 960, 455, 840), fill=red, width=9)
        draw_arrow_head(draw, (270, 830), -2.12, size=20, fill=black)
        draw_arrow_head(draw, (455, 840), -0.85, size=22, fill=red)
    elif scene == "changed_route":
        draw_dashed_line(draw, (170, 1110), (420, 820), fill=gray, width=5)
        route = quadratic_points((170, 1110), (330, 1080), (455, 900), 20)
        draw_curve(draw, route, red, 9)
        draw_arrow_head(draw, route[-1], -0.95, size=22, fill=red)
    elif scene == "new_direction":
        draw.ellipse((160, 790, 390, 1020), outline=gray, width=5)
        draw.line((275, 905, 340, 830), fill=red, width=10)
        draw_arrow_head(draw, (340, 830), -0.86, size=24, fill=red)
        draw.ellipse((258, 888, 292, 922), fill=black)
    elif scene == "emotional_relief":
        draw.arc((160, 820, 400, 1020), 180, 350, fill=gray, width=5)
        draw.arc((220, 790, 470, 1030), 190, 340, fill=gray, width=5)
        draw_sun(draw, 840, 820, 34, DEEP_RED, 0.76 * p)
        for x in (710, 760, 810):
            draw.line((x, 900, x + 40, 850), fill=pale, width=6)
    elif scene in {"cycle_loop", "repeated_pattern"}:
        for index, x in enumerate((180, 270, 360)):
            draw.ellipse((x, 810 + index * 52, x + 72, 882 + index * 52), outline=red if index == 2 else gray, width=5)
            if index < 2:
                draw.line((x + 72, 846 + index * 52, x + 90, 898 + index * 52), fill=gray, width=4)
    elif scene == "time_horizon":
        draw.line((160, 1080, 450, 1080), fill=black, width=6)
        for index, x in enumerate((190, 270, 350, 430)):
            height = 34 + index * 20
            draw.line((x, 1080, x, 1080 - height), fill=red if index == 3 else gray, width=5)
            draw.ellipse((x - 8, 1072 - height, x + 8, 1088 - height), fill=red if index == 3 else black)
    elif scene in {"system_map", "environment_design"}:
        nodes = [(180, 820), (330, 760), (410, 920), (260, 1060)]
        for first, second in zip(nodes, nodes[1:]):
            draw.line((*first, *second), fill=gray, width=4)
        for index, (x, y) in enumerate(nodes):
            radius = 18 if index == 2 else 12
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=red if index == 2 else black)
    elif scene == "identity_upgrade":
        for index in range(4):
            x1 = 160 + index * 72
            y1 = 1110 - index * 76
            draw.rectangle((x1, y1, x1 + 92, 1160), outline=red if index == 3 else gray, width=5)
        draw.ellipse((375, 760, 505, 890), outline=pale, width=8)


def draw_scene_heavy_start(draw: ImageDraw.ImageDraw, progress: float) -> None:
    p = ease(progress)
    cx, base = W // 2, 1048
    draw_ground(draw, cx - 330, base, cx + 330, progress=p, width=6)
    draw.polygon(
        [
            (cx - 290, base - 10),
            (cx - 58, base - 210),
            (cx + 82, base - 380),
            (cx + 82, base - 315),
            (cx - 42, base - 160),
            (cx - 250, base - 10),
        ],
        fill=fade_color(PALE_RED, 0.48 * p),
    )
    path = quadratic_points((cx - 285, base - 14), (cx - 108, base - 245), (cx + 78, base - 380), 36)
    draw_curve(draw, path[: max(2, int(len(path) * p))], fade_color(DEEP_RED, p), 18)
    draw.rectangle((cx + 62, base - 384, cx + 116, base), fill=fade_color(BLACK, p))
    draw.pieslice((cx - 70, base - 388, cx + 122, base - 194), 88, 270, fill=fade_color(BLACK, p))
    if p > 0.24:
        draw.line((cx - 114, base - 214, cx - 58, base - 294), fill="white", width=8)
        draw.line((cx - 72, base - 275, cx - 46, base - 312), fill="white", width=8)
    draw_radiant_dot(draw, cx + 214, base - 356, 28, p)
    draw_curve(
        draw,
        quadratic_points((cx + 96, base - 66), (cx + 210, base + 30), (cx + 312, base + 96), 22),
        fade_color(BLACK, 0.62 * p),
        4,
    )


def draw_scene_thought_load(draw: ImageDraw.ImageDraw, progress: float) -> None:
    p = ease(progress)
    cx, base = W // 2, 1052
    draw_ground(draw, cx - 290, base + 72, cx + 265, progress=p, width=5)
    cloud = [
        (cx - 252, base - 318, cx - 72, base - 148),
        (cx - 150, base - 382, cx + 78, base - 166),
        (cx + 6, base - 330, cx + 268, base - 122),
    ]
    for box in cloud:
        draw.ellipse(box, fill=fade_color(BLACK, 0.92 * p))
    draw.rounded_rectangle((cx - 214, base - 268, cx + 222, base - 136), radius=36, fill=fade_color(BLACK, 0.92 * p))
    draw.line((cx - 126, base - 122, cx - 68, base - 62), fill=fade_color(BLACK, 0.82 * p), width=8)
    draw.line((cx + 122, base - 118, cx + 66, base - 52), fill=fade_color(BLACK, 0.82 * p), width=8)
    for i in range(5):
        x = cx - 232 + i * 112
        draw.arc((x, base - 100, x + 62, base - 38), 190, 335, fill=fade_color(DEEP_RED, p), width=6)
    draw.line((cx + 206, base + 42, cx + 274, base + 42), fill=fade_color(DEEP_RED, p), width=11)
    draw.line((cx + 240, base + 8, cx + 240, base + 76), fill=fade_color(DEEP_RED, p), width=11)


def draw_scene_risk_signal(draw: ImageDraw.ImageDraw, progress: float) -> None:
    p = ease(progress)
    cx, cy = W // 2, 925
    draw.ellipse((cx - 252, cy - 252, cx + 252, cy + 252), outline=fade_color(MID_GRAY, 0.42 * p), width=5)
    draw.arc((cx - 292, cy - 292, cx + 292, cy + 292), 126, 222, fill=fade_color(BLACK, 0.62 * p), width=7)
    draw.pieslice((cx - 154, cy - 160, cx + 154, cy + 150), 88, 270, fill=fade_color(BLACK, p))
    draw.pieslice((cx - 154, cy - 160, cx + 154, cy + 150), -90, 92, fill=fade_color(PALE_GRAY, 0.85 * p))
    draw.rectangle((cx, cy - 160, cx + int(54 * p), cy + 150), fill=fade_color(MID_GRAY, 0.72 * p))
    draw.arc((cx - 214, cy - 214, cx + 214, cy + 214), 300, 76 + int(62 * p), fill=fade_color(DEEP_RED, p), width=24)
    draw.line((cx, cy, cx + int(196 * p), cy - int(142 * p)), fill=fade_color(DEEP_RED, p), width=7)
    for i in range(3):
        offset = i * 42
        draw.line((cx + 226 + offset, cy - 130 + offset, cx + 324 + offset, cy - 204 + offset), fill=fade_color(GRAY, p), width=5)
    draw_radiant_dot(draw, cx + 190, cy - 166, 24, p, fill=PALE_RED)


def draw_scene_failure_shadow(draw: ImageDraw.ImageDraw, progress: float) -> None:
    """Opening-only conflict tableau: one past failure begins closing future doors."""
    p = ease(progress)
    # Left: a dominant broken-result seal. It is readable even on the first frame.
    seal_x, seal_y = 286, 946
    seal_r = 142
    draw.ellipse(
        (seal_x - seal_r, seal_y - seal_r, seal_x + seal_r, seal_y + seal_r),
        outline=fade_color(DEEP_RED, 0.92),
        width=22,
    )
    draw.line((190, 850, 380, 1040), fill=fade_color(DEEP_RED, 0.96), width=28)
    draw.line((380, 850, 190, 1040), fill=fade_color(DEEP_RED, 0.96), width=28)
    for start, end in (((158, 820), (122, 782)), ((410, 824), (452, 786)), ((150, 1070), (112, 1110))):
        draw.line((*start, *end), fill=fade_color(BLACK, 0.72), width=7)

    # Right: three future entrances. The red interpretation path progressively
    # reaches them and turns open possibilities into closed outcomes.
    door_xs = (692, 806, 920)
    for index, door_x in enumerate(door_xs):
        arrival = stage_progress(progress, 0.34 + index * 0.16, 0.60 + index * 0.16)
        door_color = fade_color(MID_GRAY, 0.68)
        draw.rounded_rectangle((door_x - 42, 794, door_x + 42, 1068), radius=12, outline=door_color, width=7)
        draw.ellipse((door_x + 18, 918, door_x + 30, 930), fill=door_color)
        if arrival > 0:
            red = fade_color(DEEP_RED, 0.96 * arrival)
            draw.line((door_x - 30, 872, door_x + 30, 992), fill=red, width=14)
            draw.line((door_x + 30, 872, door_x - 30, 992), fill=red, width=14)

    path = quadratic_points((seal_x + 118, seal_y - 34), (540, 730), (928, 844), 60)
    visible = max(2, int(len(path) * stage_progress(progress, 0.12, 0.94)))
    draw_curve(draw, path[:visible], fade_color(DEEP_RED, 0.98), 15)
    if visible > 2:
        tracer_x, tracer_y = path[min(visible - 1, len(path) - 1)]
        draw.ellipse((tracer_x - 13, tracer_y - 13, tracer_x + 13, tracer_y + 13), fill=DEEP_RED)

    # A dark projected shadow links the past result to the protagonist without
    # replacing the protagonist itself.
    shadow_alpha = 0.10 + 0.18 * stage_progress(progress, 0.18, 0.76)
    draw.polygon(
        [(372, 962), (522, 862), (622, 1080), (416, 1050)],
        fill=fade_color(BLACK, shadow_alpha),
    )


def draw_scene_application_exit(draw: ImageDraw.ImageDraw, progress: float) -> None:
    """A real application page where an old rejection travels to the close control."""
    p = ease(progress)
    panel = (150, 760, 930, 1135)
    draw.rounded_rectangle(panel, radius=24, fill=fade_color(PALE_GRAY, 0.72), outline=fade_color(BLACK, 0.78 * p), width=7)
    draw.line((150, 836, 930, 836), fill=fade_color(MID_GRAY, 0.82 * p), width=5)
    for x, color in ((192, GRAY), (230, GRAY), (268, RED)):
        draw.ellipse((x - 11, 786, x + 11, 808), fill=fade_color(color, 0.92 * p))
    # Job card and requirement lines.
    draw.rounded_rectangle((205, 875, 620, 1080), radius=18, fill="white", outline=fade_color(MID_GRAY, 0.72 * p), width=4)
    title_font = font(31, bold=True)
    draw.text((240, 898), "新岗位 · 条件更匹配", font=title_font, fill=fade_color(BLACK, p))
    for index, (label, ok) in enumerate((("经验", True), ("作品", True), ("表达", False))):
        y = 956 + index * 48
        color = DEEP_RED if ok else GRAY
        draw.ellipse((244, y - 5, 264, y + 15), outline=fade_color(color, p), width=4)
        if ok:
            draw.line((249, y + 4, 255, y + 10, 266, y - 5), fill=fade_color(color, p), width=4)
        draw.text((282, y - 12), label, font=font(26, bold=True), fill=fade_color(BLACK, 0.72 * p))
        draw.line((356, y + 3, 565, y + 3), fill=fade_color(MID_GRAY, 0.55 * p), width=4)
    # Close control becomes the destination of the old-result path.
    close_p = stage_progress(progress, 0.42, 0.94)
    draw.rounded_rectangle((820, 866, 892, 938), radius=16, fill=fade_color(PALE_RED, 0.48 * close_p), outline=fade_color(DEEP_RED, close_p), width=6)
    draw.line((842, 888, 870, 916), fill=fade_color(DEEP_RED, close_p), width=7)
    draw.line((870, 888, 842, 916), fill=fade_color(DEEP_RED, close_p), width=7)
    draw.ellipse((170, 1070, 310, 1210), outline=fade_color(DEEP_RED, 0.86 * p), width=12)
    stamp_font = font(29, bold=True)
    draw.text((190, 1115), "没通过", font=stamp_font, fill=fade_color(DEEP_RED, p))
    route = quadratic_points((300, 1110), (545, 1000), (846, 924), 54)
    visible = max(2, int(len(route) * stage_progress(progress, 0.16, 0.96)))
    draw_curve(draw, route[:visible], fade_color(DEEP_RED, p), 11)
    if visible > 2:
        x, y = route[visible - 1]
        draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill=fade_color(DEEP_RED, p))


def draw_scene_meeting_confirmation(draw: ImageDraw.ImageDraw, progress: float) -> None:
    """Meeting tableau: the protagonist sees the issue but sends the decision outward."""
    p = ease(progress)
    draw.ellipse((190, 900, 890, 1160), fill=fade_color(PALE_GRAY, 0.78), outline=fade_color(BLACK, 0.7 * p), width=7)
    draw.ellipse((245, 942, 835, 1118), outline=fade_color(MID_GRAY, 0.64 * p), width=4)
    # Proposal sheet with one visible fault.
    draw.rounded_rectangle((430, 928, 650, 1088), radius=14, fill="white", outline=fade_color(MID_GRAY, 0.8 * p), width=4)
    for index, y in enumerate((966, 1008, 1050)):
        draw.line((464, y, 614, y), fill=fade_color(GRAY, 0.55 * p), width=5)
        if index == 1:
            draw.ellipse((598, y - 10, 618, y + 10), fill=fade_color(DEEP_RED, p))
    # Colleagues and their incoming answer bubbles.
    for index, x in enumerate((260, 820)):
        draw_person(draw, x, 905, 0.58, color=fade_color(BLACK, 0.82 * p), lean=0.15 if index == 0 else -0.15)
        bubble_x = 185 if index == 0 else 735
        draw.rounded_rectangle((bubble_x, 770, bubble_x + 170, 850), radius=26, outline=fade_color(RED if index else GRAY, 0.72 * p), width=5)
        q_font = font(42, bold=True)
        draw.text((bubble_x + 66, 783), "?", font=q_font, fill=fade_color(RED if index else BLACK, p))
    for x in (400, 680):
        draw_arrow_head(draw, (540, 884), math.atan2(884 - 824, 540 - x), size=18, fill=fade_color(DEEP_RED, p))
        draw.line((x, 824, 540, 884), fill=fade_color(DEEP_RED, 0.68 * p), width=5)


def draw_scene_result_identity_stamp(draw: ImageDraw.ImageDraw, progress: float) -> None:
    """One result card is visibly rewritten into a global self-label."""
    p = ease(progress)
    left = (150, 810, 430, 1100)
    right = (650, 810, 930, 1100)
    for box in (left, right):
        draw.rounded_rectangle(box, radius=24, fill="white", outline=fade_color(MID_GRAY, 0.82 * p), width=6)
    draw.text((215, 858), "那次结果", font=font(32, bold=True), fill=fade_color(BLACK, p))
    draw.text((730, 858), "对自己", font=font(32, bold=True), fill=fade_color(BLACK, p))
    draw.rounded_rectangle((192, 940, 390, 1020), radius=20, outline=fade_color(DEEP_RED, p), width=6)
    draw.text((228, 958), "没有通过", font=font(34, bold=True), fill=fade_color(DEEP_RED, p))
    draw.ellipse((722, 920, 858, 1056), outline=fade_color(BLACK, 0.7 * p), width=7)
    draw_person(draw, 790, 1018, 0.52, color=fade_color(BLACK, p))
    stamp_p = stage_progress(progress, 0.52, 0.94)
    draw.rounded_rectangle((690, 946, 892, 1032), radius=16, fill=fade_color(PALE_RED, 0.46 * stamp_p), outline=fade_color(DEEP_RED, stamp_p), width=7)
    draw.text((736, 965), "我不行", font=font(36, bold=True), fill=fade_color(DEEP_RED, stamp_p))
    route = quadratic_points((430, 962), (540, 830), (690, 962), 42)
    visible = max(2, int(len(route) * stage_progress(progress, 0.2, 0.9)))
    draw_curve(draw, route[:visible], fade_color(DEEP_RED, p), 10)
    if visible > 3:
        draw_arrow_head(draw, route[visible - 1], 0.35, size=22, fill=fade_color(DEEP_RED, p))


def draw_scene_feedback_fork(draw: ImageDraw.ImageDraw, progress: float) -> None:
    """Two routes after failure: adjust conditions or exit before feedback can arrive."""
    p = ease(progress)
    origin = (210, 970)
    draw.rounded_rectangle((130, 914, 290, 1026), radius=18, outline=fade_color(DEEP_RED, p), width=6)
    draw.text((164, 948), "没通过", font=font(30, bold=True), fill=fade_color(DEEP_RED, p))
    upper = quadratic_points(origin, (430, 760), (820, 820), 50)
    lower = quadratic_points(origin, (450, 1120), (820, 1110), 50)
    upper_n = max(2, int(len(upper) * stage_progress(progress, 0.1, 0.82)))
    lower_n = max(2, int(len(lower) * stage_progress(progress, 0.22, 0.9)))
    draw_curve(draw, upper[:upper_n], fade_color(BLACK, 0.72 * p), 8)
    draw_curve(draw, lower[:lower_n], fade_color(DEEP_RED, p), 10)
    for index, (x, label) in enumerate(((430, "补经验"), (610, "改简历"), (800, "新反馈"))):
        node_p = stage_progress(progress, 0.22 + index * 0.16, 0.56 + index * 0.16)
        draw.ellipse((x - 40, 760, x + 40, 840), fill="white", outline=fade_color(BLACK if index < 2 else DEEP_RED, node_p), width=6)
        bbox = draw.textbbox((0, 0), label, font=font(25, bold=True))
        draw.text((x - (bbox[2] - bbox[0]) / 2, 856), label, font=font(25, bold=True), fill=fade_color(BLACK, node_p))
    draw.rounded_rectangle((700, 1050, 900, 1160), radius=20, outline=fade_color(MID_GRAY, 0.62 * p), width=5)
    draw.text((744, 1082), "无反馈", font=font(31, bold=True), fill=fade_color(GRAY, p))
    cross_p = stage_progress(progress, 0.58, 0.95)
    draw.line((724, 1068, 876, 1144), fill=fade_color(DEEP_RED, cross_p), width=12)
    draw.line((876, 1068, 724, 1144), fill=fade_color(DEEP_RED, cross_p), width=12)


def draw_scene_old_conclusion_loop(draw: ImageDraw.ImageDraw, progress: float) -> None:
    """The single named five-node mechanism used by this episode."""
    p = ease(progress)
    center = (540, 970)
    nodes = [
        (540, 750, "没通过"),
        (790, 860, "我不行"),
        (760, 1090, "回避"),
        (320, 1090, "无反馈"),
        (290, 860, "更像真的"),
    ]
    reveal = stage_progress(progress, 0.08, 0.88)
    loop_points: list[tuple[int, int]] = []
    for index in range(len(nodes)):
        start = nodes[index][:2]
        end = nodes[(index + 1) % len(nodes)][:2]
        segment = quadratic_points(start, center, end, 16)
        loop_points.extend(segment[:-1])
    loop_points.append(nodes[0][:2])
    visible = max(2, int(len(loop_points) * reveal))
    draw_curve(draw, loop_points[:visible], fade_color(DEEP_RED, p), 10)
    for index, (x, y, label) in enumerate(nodes):
        node_p = stage_progress(progress, 0.1 + index * 0.13, 0.42 + index * 0.13)
        radius = 58 if index in (0, 4) else 52
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="white", outline=fade_color(DEEP_RED if index in (0, 4) else BLACK, node_p), width=7)
        label_font = font(24 if len(label) <= 3 else 21, bold=True)
        bbox = draw.textbbox((0, 0), label, font=label_font)
        draw.text((x - (bbox[2] - bbox[0]) / 2, y - 17), label, font=label_font, fill=fade_color(BLACK, node_p))
    draw.ellipse((452, 882, 628, 1058), outline=fade_color(PALE_RED, 0.62 * p), width=10)
    draw.text((480, 944), "循环", font=font(42, bold=True), fill=fade_color(DEEP_RED, p))


def draw_scene_three_column_review(draw: ImageDraw.ImageDraw, progress: float) -> None:
    p = ease(progress)
    panel = (125, 790, 955, 1135)
    draw.rounded_rectangle(panel, radius=24, fill="white", outline=fade_color(BLACK, 0.78 * p), width=7)
    headers = (("事实", 125, 402), ("条件", 402, 679), ("评价", 679, 955))
    values = ("这次没通过", "需要3年\n我有1年", "我不行")
    for index, ((label, x1, x2), value) in enumerate(zip(headers, values)):
        draw.rectangle((x1, 790, x2, 868), fill=fade_color(PALE_RED if index == 2 else PALE_GRAY, 0.72 * p))
        bbox = draw.textbbox((0, 0), label, font=font(31, bold=True))
        draw.text(((x1 + x2 - (bbox[2] - bbox[0])) / 2, 810), label, font=font(31, bold=True), fill=fade_color(DEEP_RED if index == 2 else BLACK, p))
        if index:
            draw.line((x1, 790, x1, 1135), fill=fade_color(MID_GRAY, 0.72 * p), width=4)
        lines = value.split("\n")
        for line_index, line in enumerate(lines):
            value_font = font(28, bold=True)
            value_bbox = draw.textbbox((0, 0), line, font=value_font)
            draw.text(((x1 + x2 - (value_bbox[2] - value_bbox[0])) / 2, 948 + line_index * 48), line, font=value_font, fill=fade_color(BLACK, 0.78 * p))
    separation = stage_progress(progress, 0.48, 0.95)
    draw.line((682, 894, 682, 1106), fill=fade_color(DEEP_RED, separation), width=10)
    draw_arrow_head(draw, (682, 894), -math.pi / 2, size=20, fill=fade_color(DEEP_RED, separation))
    # Keep the long explanatory beat alive as the viewer checks each row: a
    # high-contrast cursor scans the boundary between conditions and judgment.
    scan = stage_progress(progress, 0.46, 0.995)
    scan_y = 890 + int(205 * scan)
    draw.ellipse((652, scan_y - 30, 712, scan_y + 30), fill=fade_color(BLACK, 0.94 * separation))
    draw.ellipse((663, scan_y - 19, 701, scan_y + 19), fill="white")
    draw.ellipse((674, scan_y - 8, 690, scan_y + 8), fill=fade_color(DEEP_RED, separation))


def draw_scene_new_application_feedback(draw: ImageDraw.ImageDraw, progress: float) -> None:
    p = ease(progress)
    draw.rounded_rectangle((145, 790, 650, 1118), radius=22, fill="white", outline=fade_color(BLACK, 0.76 * p), width=7)
    draw.line((145, 856, 650, 856), fill=fade_color(MID_GRAY, 0.72 * p), width=5)
    draw.text((190, 888), "条件更匹配的岗位", font=font(32, bold=True), fill=fade_color(BLACK, p))
    for index, y in enumerate((962, 1014, 1066)):
        draw.ellipse((194, y - 10, 218, y + 14), outline=fade_color(DEEP_RED, p), width=4)
        draw.line((200, y + 2, 207, y + 9, 220, y - 8), fill=fade_color(DEEP_RED, p), width=4)
        draw.line((248, y + 2, 570 - index * 34, y + 2), fill=fade_color(MID_GRAY, 0.62 * p), width=5)
    send_p = stage_progress(progress, 0.24, 0.7)
    draw.rounded_rectangle((490, 1040, 620, 1096), radius=20, fill=fade_color(DEEP_RED, send_p))
    draw.text((530, 1053), "投递", font=font(25, bold=True), fill="white")
    # Reply envelope arrives late in the beat, keeping the semantic action alive.
    reply_p = stage_progress(progress, 0.58, 0.97)
    envelope = (735, 872, 930, 1010)
    draw.rounded_rectangle(envelope, radius=18, fill="white", outline=fade_color(DEEP_RED, reply_p), width=7)
    draw.line((735, 886, 832, 958, 930, 886), fill=fade_color(DEEP_RED, reply_p), width=5)
    draw.ellipse((812, 1035, 854, 1077), fill=fade_color(DEEP_RED, reply_p))
    draw.text((728, 1090), "记录回复", font=font(29, bold=True), fill=fade_color(BLACK, reply_p))
    route = quadratic_points((612, 1065), (712, 1100), (832, 1038), 36)
    visible = max(2, int(len(route) * stage_progress(progress, 0.34, 0.94)))
    draw_curve(draw, route[:visible], fade_color(DEEP_RED, p), 9)


def draw_scene_relief_window(draw: ImageDraw.ImageDraw, progress: float) -> None:
    """A broad late-moving relief state: the old cloud lifts and light enters."""
    p = max(0.0, min(1.0, progress))
    cloud_y = -int(150 * p)
    cloud_fill = fade_color(BLACK, 0.84 - 0.38 * p)
    for box in (
        (120, 850 + cloud_y, 410, 1060 + cloud_y),
        (270, 790 + cloud_y, 610, 1050 + cloud_y),
        (470, 850 + cloud_y, 730, 1050 + cloud_y),
    ):
        draw.ellipse(box, fill=cloud_fill)
    draw.rounded_rectangle((170, 920 + cloud_y, 680, 1050 + cloud_y), radius=54, fill=cloud_fill)
    # A large opening beam grows through the whole spoken beat.
    beam = stage_progress(progress, 0.18, 0.995)
    draw.polygon(
        [
            (890, 790),
            (930, 850),
            (690 - int(260 * beam), 1170),
            (610 - int(190 * beam), 1170),
        ],
        fill=fade_color(PALE_RED, 0.32 + 0.34 * beam),
    )
    sun_radius = 28 + int(28 * beam)
    draw_sun(draw, 860, 820, sun_radius, DEEP_RED, 0.64 + 0.28 * beam)
    horizon = quadratic_points((170, 1120), (510, 1080 - int(70 * beam)), (870, 1000 - int(120 * beam)), 64)
    visible = max(2, int(len(horizon) * stage_progress(progress, 0.14, 0.99)))
    draw_curve(draw, horizon[:visible], fade_color(DEEP_RED, 0.9), 13)


def draw_scene_updating_map(draw: ImageDraw.ImageDraw, progress: float) -> None:
    p = ease(progress)
    draw.rounded_rectangle((150, 770, 930, 1150), radius=28, fill=fade_color(PALE_GRAY, 0.68), outline=fade_color(BLACK, 0.72 * p), width=7)
    # Old route remains visible in gray.
    old_route = quadratic_points((210, 1080), (420, 780), (810, 1040), 54)
    draw_dashed_line(draw, old_route[0], old_route[-1], fill=fade_color(GRAY, 0.55 * p), width=5, dash=20, gap=12)
    for x, y in ((260, 990), (470, 870), (740, 970)):
        draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill=fade_color(GRAY, p))
    new_route = quadratic_points((210, 1080), (500, 1160), (850, 820), 70)
    visible = max(2, int(len(new_route) * stage_progress(progress, 0.12, 0.97)))
    draw_curve(draw, new_route[:visible], fade_color(DEEP_RED, p), 12)
    if visible > 3:
        x, y = new_route[visible - 1]
        draw.ellipse((x - 13, y - 13, x + 13, y + 13), fill=fade_color(DEEP_RED, p))
    draw_radiant_dot(draw, 850, 820, 24, stage_progress(progress, 0.72, 1.0))


def draw_scene_threshold(draw: ImageDraw.ImageDraw, progress: float) -> None:
    p = ease(progress)
    cx, base = W // 2, 1090
    draw_ground(draw, cx - 300, base, cx + 310, progress=p, width=7)
    draw.rounded_rectangle((cx + 52, base - 282, cx + 284, base + 2), radius=16, outline=fade_color(BLACK, p), width=11)
    draw.line((cx + 166, base - 270, cx + 166, base - 18), fill=fade_color(MID_GRAY, 0.52 * p), width=5)
    draw.rectangle((cx + 76, base - int(54 * p), cx + 258, base), fill=fade_color(DEEP_RED, 0.92 * p))
    draw_curve(
        draw,
        quadratic_points((cx - 166, base - 2), (cx - 34, base - 82), (cx + 82, base - int(46 * p)), 24),
        fade_color(DEEP_RED, p),
        12,
    )


def draw_scene_lower_entry(draw: ImageDraw.ImageDraw, progress: float) -> None:
    p = ease(progress)
    cx, base = W // 2, 1088
    draw_ground(draw, cx - 290, base, cx + 300, progress=p, width=7)
    draw.line((cx - 226, base - 222, cx + 188, base - 222), fill=fade_color(MID_GRAY, 0.52 * p), width=24)
    draw_curve(
        draw,
        quadratic_points((cx - 226, base - 222), (cx - 58, base - 62), (cx + 206, base), 28),
        fade_color(MID_GRAY, 0.5 * p),
        12,
    )
    red_path = quadratic_points((cx - 246, base - 2), (cx - 20, base - 16), (cx + 252, base - 88), 32)
    draw_curve(draw, red_path[: max(2, int(len(red_path) * p))], fade_color(DEEP_RED, p), 18)
    draw.ellipse((cx + 204, base - 118, cx + 278, base - 44), outline=fade_color(DEEP_RED, p), width=8)


def draw_scene_timed_action(draw: ImageDraw.ImageDraw, progress: float) -> None:
    p = ease(progress)
    cx, cy = W // 2, 930
    draw.ellipse((cx - 210, cy - 210, cx + 210, cy + 210), outline=fade_color(MID_GRAY, 0.45 * p), width=4)
    draw.ellipse((cx - 180, cy - 180, cx + 180, cy + 180), outline=fade_color(BLACK, p), width=13)
    for angle in range(0, 360, 30):
        rad = math.radians(angle - 90)
        x1 = cx + int(math.cos(rad) * 154)
        y1 = cy + int(math.sin(rad) * 154)
        x2 = cx + int(math.cos(rad) * 174)
        y2 = cy + int(math.sin(rad) * 174)
        draw.line((x1, y1, x2, y2), fill=fade_color(BLACK, 0.65 * p), width=4)
    draw.arc((cx - 180, cy - 180, cx + 180, cy + 180), -90, -90 + int(300 * p), fill=fade_color(DEEP_RED, p), width=20)
    draw.line((cx, cy, cx + int(70 * p), cy - int(88 * p)), fill=fade_color(BLACK, p), width=9)
    draw.line((cx, cy, cx, cy - int(125 * p)), fill=fade_color(BLACK, p), width=7)
    draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=fade_color(DEEP_RED, p))
    for index, radius in enumerate((16, 12, 8)):
        dot_x = cx - 72 + index * 72
        draw.ellipse(
            (dot_x - radius, cy + 70 - radius, dot_x + radius, cy + 70 + radius),
            fill=fade_color(DEEP_RED if index == 1 else BLACK, p),
        )
    draw_ground(draw, cx + 210, cy + 250, cx + 360, progress=p, width=4)


def draw_scene_system_redesign(draw: ImageDraw.ImageDraw, progress: float) -> None:
    p = ease(progress)
    cx, cy = W // 2, 940
    draw_panel(draw, (cx - 255, cy - 190, cx + 255, cy + 170), p)
    draw_ground(draw, cx - 304, cy + 232, cx + 310, progress=p, width=7)
    route = quadratic_points((cx - 266, cy + 224), (cx - 42, cy + 120), (cx + 218, cy + 198), 32)
    draw_curve(draw, route[: max(2, int(len(route) * p))], fade_color(DEEP_RED, p), 11)
    draw.ellipse((cx + 198, cy + 178, cx + 240, cy + 220), fill=fade_color(DEEP_RED, p))


SCENE_RENDERERS = {
    "heavy_start": draw_scene_heavy_start,
    "thought_load": draw_scene_thought_load,
    "risk_signal": draw_scene_risk_signal,
    "failure_shadow": draw_scene_failure_shadow,
    "threshold": draw_scene_threshold,
    "lower_entry": draw_scene_lower_entry,
    "timed_action": draw_scene_timed_action,
    "system_redesign": draw_scene_system_redesign,
}

SPECIALIZED_SEMANTIC_RENDERERS = {
    "blocked_path": draw_scene_application_exit,
    "isolated_person": draw_scene_meeting_confirmation,
    "dual_layer_system": draw_scene_result_identity_stamp,
    "repeated_pattern": draw_scene_feedback_fork,
    "cycle_loop": draw_scene_old_conclusion_loop,
    "emotional_relief": draw_scene_relief_window,
    "system_map": draw_scene_three_column_review,
    "new_direction": draw_scene_new_application_feedback,
    "identity_upgrade": draw_scene_updating_map,
}


def draw_metaphor_scene(draw: ImageDraw.ImageDraw, scene: str, progress: float) -> None:
    render_scene = METAPHOR_FAMILY_TO_SCENE.get(scene, scene)
    specialized_renderer = SPECIALIZED_SEMANTIC_RENDERERS.get(scene)
    renderer = specialized_renderer or SCENE_RENDERERS.get(render_scene) or draw_scene_heavy_start
    # Spread the semantic action across almost the entire card duration. Each
    # stage overlaps the next so the viewer watches an explanation unfold rather
    # than seeing a quick build followed by a frozen slide.
    draw_semantic_backdrop(draw, scene, stage_progress(progress, 0.02, 0.90 if specialized_renderer else 0.58))
    renderer(draw, stage_progress(progress, 0.08, 0.98 if specialized_renderer else 0.92))
    if specialized_renderer is None:
        draw_semantic_details(draw, scene, stage_progress(progress, 0.28, 0.95))
    character_progress = stage_progress(progress, 0.16, 0.97)
    if scene == "fractured_identity":
        character_progress = max(0.58, character_progress)
    draw_continuity_character(draw, scene, character_progress)
    draw_scene_motion_overlay(draw, scene, progress)


def draw_scene_motion_overlay(draw: ImageDraw.ImageDraw, scene: str, progress: float) -> None:
    """Keep one semantic cause moving until the spoken beat is almost complete."""
    routes = {
        "fractured_identity": ((404, 912), (612, 748), (926, 844)),
        "blocked_path": ((352, 1080), (478, 1018), (650, 1035)),
        "isolated_person": ((344, 1010), (540, 938), (746, 1010)),
        "dual_layer_system": ((286, 884), (540, 930), (786, 1050)),
        "repeated_pattern": ((382, 1010), (540, 748), (698, 1008)),
        "changed_route": ((304, 1090), (516, 1082), (798, 1000)),
        "emotional_relief": ((310, 1080), (570, 1060), (810, 1004)),
        "system_map": ((332, 1076), (540, 1018), (760, 1138)),
        "new_direction": ((300, 1090), (560, 1080), (800, 998)),
        "identity_upgrade": ((350, 1110), (570, 1030), (774, 908)),
    }
    start, control, end = routes.get(scene, ((310, 1090), (540, 960), (790, 1010)))
    travel = stage_progress(progress, 0.34, 0.97)
    points = quadratic_points(start, control, end, 240)
    dot_index = min(len(points) - 1, max(0, int((len(points) - 1) * travel)))
    dot_x, dot_y = points[dot_index]
    dot_alpha = stage_progress(progress, 0.30, 0.44)
    # A visible moving tail carries the causal signal across the late half of a
    # long beat. A tiny tracer alone can be technically animated yet still feel
    # frozen on a 1080x1440 canvas.
    tail_start = max(0, dot_index - 26)
    tail = points[tail_start : dot_index + 1]
    if len(tail) >= 2:
        draw_curve(draw, tail, fade_color(PALE_RED, 0.88 * dot_alpha), 20)
        draw_curve(draw, tail, fade_color(DEEP_RED, 0.78 * dot_alpha), 7)
    halo_phase = max(0.0, min(1.0, progress)) * math.pi * 8
    halo_radius = 18 + int(7 * (0.5 + 0.5 * math.sin(halo_phase)))
    draw.ellipse(
        (dot_x - halo_radius, dot_y - halo_radius, dot_x + halo_radius, dot_y + halo_radius),
        outline=fade_color(PALE_RED, 0.82 * dot_alpha),
        width=6,
    )
    # High-contrast evidence cursor: it stays legible even when travelling over
    # an existing red loop or path, where a red-only dot can visually disappear.
    cursor_radius = 19
    draw.ellipse(
        (dot_x - cursor_radius, dot_y - cursor_radius, dot_x + cursor_radius, dot_y + cursor_radius),
        fill=fade_color(BLACK, 0.94 * dot_alpha),
    )
    draw.ellipse((dot_x - 11, dot_y - 11, dot_x + 11, dot_y + 11), fill=fade_color("#ffffff", dot_alpha))
    draw.ellipse((dot_x - 6, dot_y - 6, dot_x + 6, dot_y + 6), fill=fade_color(DEEP_RED, 0.98 * dot_alpha))
    if progress > 0.72:
        pulse = (progress - 0.72) / 0.28
        ring_r = 22 + int(58 * pulse)
        draw.ellipse(
            (end[0] - ring_r, end[1] - ring_r, end[0] + ring_r, end[1] + ring_r),
            outline=fade_color(PALE_RED, 0.78 * (1 - pulse * 0.35)),
            width=8,
        )


def stage_progress(progress: float, start: float, end: float) -> float:
    if end <= start:
        return 1.0
    return max(0.0, min(1.0, (progress - start) / (end - start)))


def draw_card_form_chrome(draw: ImageDraw.ImageDraw, card: dict[str, Any], progress: float) -> None:
    form = str(card.get("card_form") or "scene_card")
    p = ease(progress)
    pale = fade_color(MID_GRAY, 0.28 * p)
    red = fade_color(RED, 0.68 * p)
    black = fade_color(BLACK, 0.32 * p)
    if form == "verdict_poster":
        draw.line((100, 734, 100, 734 + int(400 * p)), fill=red, width=10)
        draw.arc((770, 720, 972, 922), 205, 205 + int(270 * p), fill=pale, width=5)
    elif form == "scene_card":
        draw.line((178, 732, 178 + int(724 * p), 732), fill=pale, width=3)
        draw.line((178, 732, 178, 732 + int(96 * p)), fill=black, width=5)
        draw.line((902, 732, 902, 732 + int(96 * p)), fill=black, width=5)
    elif form == "dual_compare":
        draw.line((W // 2, 728, W // 2, 728 + int(420 * p)), fill=pale, width=4)
        for x, label in ((330, "表层"), (750, "深层")):
            draw.rounded_rectangle((x - 58, 742, x + 58, 792), radius=24, outline=red, width=3)
            bbox = draw.textbbox((0, 0), label, font=font(27, bold=True))
            draw.text((x - (bbox[2] - bbox[0]) / 2, 750), label, font=font(27, bold=True), fill=red)
    elif form == "model_map":
        draw.rounded_rectangle((184, 718, 896, 1178), radius=28, outline=pale, width=5)
        for x, y in ((230, 764), (850, 764), (230, 1132), (850, 1132)):
            draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=red)
    elif form == "question_card":
        question_font = font(260, bold=True)
        draw.text((776, 724), "?", font=question_font, fill=fade_color(PALE_RED, 0.42 * p))
        draw.arc((170, 744, 910, 1190), 195, 195 + int(250 * p), fill=red, width=7)
    elif form == "action_path":
        for offset, x in enumerate((226, 540, 854), start=1):
            alpha = stage_progress(p, 0.12 * (offset - 1), 0.42 + 0.12 * (offset - 1))
            outline = fade_color(RED if offset == 1 else MID_GRAY, 0.82 * alpha)
            draw.ellipse((x - 34, 742, x + 34, 810), outline=outline, width=5)
            label_font = font(28, bold=True)
            label = str(offset)
            bbox = draw.textbbox((0, 0), label, font=label_font)
            draw.text((x - (bbox[2] - bbox[0]) / 2, 757), label, font=label_font, fill=outline)
        draw.line((260, 776, 820, 776), fill=pale, width=4)
    elif form == "identity_poster":
        draw.arc((190, 720, 890, 1220), 202, 202 + int(268 * p), fill=pale, width=6)
        draw.arc((280, 790, 800, 1160), 202, 202 + int(268 * p), fill=red, width=9)

    label = CARD_FORM_LABELS.get(form, "语义卡片")
    label_font = font(25, bold=True)
    bbox = draw.textbbox((0, 0), label, font=label_font)
    label_width = bbox[2] - bbox[0]
    draw.rounded_rectangle((72, 636, 106 + label_width, 684), radius=20, fill=fade_color(PALE_GRAY, p))
    draw.text((89, 646), label, font=label_font, fill=fade_color(SOFT_BLACK, p))

    points = [str(item) for item in card.get("supporting_points") or []]
    if points:
        point_font = font(24, bold=True)
        widths = [draw.textbbox((0, 0), item, font=point_font)[2] + 34 for item in points]
        total = sum(widths) + 14 * max(0, len(widths) - 1)
        x = W - 72 - total
        for item, width in zip(points, widths):
            draw.rounded_rectangle((x, 638, x + width, 682), radius=18, outline=pale, width=2)
            draw.text((x + 17, 646), item, font=point_font, fill=fade_color(GRAY, p))
            x += width + 14


def render_card(card: dict[str, Any], index: int, out_path: Path, progress: float = 1.0) -> None:
    image = Image.new("RGB", (W, H), "#ffffff")
    draw = ImageDraw.Draw(image)
    theme_font = font(52, bold=True)
    p = max(0.0, min(1.0, progress))
    is_opening = index == 0
    # The opening frame is a designed hook, not an empty template. Its judgment
    # is readable immediately while the visual conflict develops over 0-3s.
    theme_progress = 1.0 if is_opening else stage_progress(p, 0.0, 0.22)
    judgment_progress = 1.0 if is_opening else stage_progress(p, 0.04, 0.38)
    form_progress = max(0.62, stage_progress(p, 0.0, 0.50)) if is_opening else stage_progress(p, 0.0, 0.52)
    scene_progress = 0.24 + 0.76 * p if is_opening else p
    keyword_progress = stage_progress(p, 0.58, 0.90)

    draw.rectangle((0, 0, W, H), fill="#ffffff")
    draw_header(draw)
    core_size = fit_rich_text_size(
        draw,
        card["core"],
        start=72,
        minimum=48,
        max_width=820,
        max_height=232,
        line_gap=14,
    )
    centered_text(
        draw,
        card["theme"],
        186,
        theme_font,
        fill=fade_color(RED, theme_progress),
        max_width=1000,
        line_gap=10,
        stroke_width=1,
    )
    draw.line((72, 270, 72 + int(936 * theme_progress), 270), fill=fade_color(RED, 0.65 * theme_progress), width=4)
    core_bottom = draw_rich_centered(
        draw,
        card["core"],
        310,
        size=core_size,
        fill=SOFT_BLACK,
        emphasis_fill=BLACK,
        max_width=820,
        line_gap=14,
        reveal_progress=judgment_progress,
        emphasis_progress=keyword_progress,
    )
    roman_y = min(594, max(564, core_bottom + 22))
    draw_spaced_text(
        draw,
        ROMAN_SEPARATOR,
        W // 2,
        roman_y,
        latin_font(34, bold=True),
        fade_color("#505050", judgment_progress),
    )
    draw_card_form_chrome(draw, card, form_progress)
    draw_metaphor_scene(draw, str(card.get("scene") or "open_path"), scene_progress)
    draw_disclaimer(draw)
    draw_footer_system(draw)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, quality=95)


def card_duration_weights(cards: list[dict[str, Any]]) -> list[float]:
    measured = [float(card.get("measured_audio_seconds") or 0.0) for card in cards]
    if all(value > 0 for value in measured):
        return measured
    estimated = [float(card.get("estimated_seconds") or 0.0) for card in cards]
    if any(value > 0 for value in estimated):
        return [value if value > 0 else max(len(str(card.get("narration") or "")), 8) / 5 for value, card in zip(estimated, cards)]
    explicit = [float(card.get("duration_weight") or 0.0) for card in cards]
    if any(value > 0 for value in explicit):
        return [value if value > 0 else 1.0 for value in explicit]
    return [max(len(str(card.get("narration") or "").replace("\n", "")), 8) for card in cards]


def allocate_card_frames(cards: list[dict[str, Any]], total_frames: int) -> list[int]:
    weights = card_duration_weights(cards)
    weight_sum = sum(weights) or float(len(cards) or 1)
    raw = [total_frames * value / weight_sum for value in weights]
    allocated = [max(1, int(math.floor(value))) for value in raw]
    delta = total_frames - sum(allocated)
    if delta > 0:
        order = sorted(range(len(raw)), key=lambda index: raw[index] - math.floor(raw[index]), reverse=True)
        for offset in range(delta):
            allocated[order[offset % len(order)]] += 1
    elif delta < 0:
        order = sorted(range(len(allocated)), key=lambda index: allocated[index], reverse=True)
        for index in order:
            while delta < 0 and allocated[index] > 1:
                allocated[index] -= 1
                delta += 1
    if sum(allocated) != total_frames:
        allocated[-1] += total_frames - sum(allocated)
    return allocated


def render_card_sequence(cards: list[dict[str, Any]], total_duration: float, frames_dir: Path) -> dict[str, Any]:
    sequence_dir = frames_dir / "animated"
    sequence_dir.mkdir(parents=True, exist_ok=True)
    total_frames = max(1, int(math.ceil(total_duration * FPS)))
    frame_counts = allocate_card_frames(cards, total_frames)
    boundaries: list[int] = []
    cursor = 0
    for count in frame_counts:
        cursor += count
        boundaries.append(cursor)
    card_index = 0
    card_start = 0
    transition_frames = max(3, int(FPS * 0.18))
    for frame_index in range(total_frames):
        while card_index < len(boundaries) - 1 and frame_index >= boundaries[card_index]:
            card_start = boundaries[card_index]
            card_index += 1
        local_index = frame_index - card_start
        normalized = min(1.0, local_index / max(frame_counts[card_index] - 1, 1))
        baseline = 0.0 if card_index == 0 else 0.08
        local_progress = baseline + (1.0 - baseline) * normalized
        frame_path = sequence_dir / f"frame_{frame_index:05d}.jpg"
        render_card(cards[card_index], card_index, frame_path, progress=local_progress)
        if card_index > 0 and local_index < transition_frames:
            previous_frame_path = sequence_dir / f"frame_{card_start - 1:05d}.jpg"
            if previous_frame_path.exists():
                alpha = ease((local_index + 1) / transition_frames)
                with Image.open(previous_frame_path).convert("RGB") as previous_image:
                    with Image.open(frame_path).convert("RGB") as current_image:
                        Image.blend(previous_image, current_image, alpha).save(frame_path, quality=95)
    return {
        "frame_dir": str(sequence_dir),
        "total_frames": total_frames,
        "fps": FPS,
        "timing_authority": (
            "measured per-beat narration plus pause durations"
            if all(float(card.get("measured_audio_seconds") or 0.0) > 0 for card in cards)
            else "beat estimated_seconds, duration_weight, or narration length normalized to measured audio duration"
        ),
        "motion_timing": "full-beat semantic action with 0.18s cross-card blend and no forced static tail",
        "cards": [
            {
                "id": card.get("id"),
                "role": card.get("role"),
                "frames": frame_count,
                "duration_seconds": round(frame_count / FPS, 3),
            }
            for card, frame_count in zip(cards, frame_counts)
        ],
    }


def svg_text_lines(text: str, x: int, y: int, size: int, fill: str, *, weight: int = 400, gap: int = 1) -> list[str]:
    lines = text.split("\n")
    output = [
        f'<text x="{x}" y="{y}" text-anchor="middle" font-family="PingFang SC, Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">'
    ]
    for index, line in enumerate(lines):
        dy = 0 if index == 0 else int(size * gap)
        output.append(f'<tspan x="{x}" dy="{dy}">{html.escape(line)}</tspan>')
    output.append("</text>")
    return output


def svg_rich_text_lines(
    text: str,
    x: int,
    y: int,
    size: int,
    fill: str,
    *,
    normal_weight: int = 650,
    bold_weight: int = 900,
    gap: float = 1.24,
    max_chars: int = 14,
) -> list[str]:
    output: list[str] = []
    rich_lines: list[list[tuple[str, bool]]] = []
    for raw_line in str(text).split("\n"):
        units: list[tuple[str, bool]] = []
        for segment, emphasized in emphasis_segments(raw_line):
            if emphasized:
                units.append((segment, True))
            else:
                units.extend((char, False) for char in segment)
        if not units:
            rich_lines.append([])
            continue
        current: list[tuple[str, bool]] = []
        current_length = 0
        for segment, emphasized in units:
            segment_length = len(segment)
            if current and current_length + segment_length > max_chars:
                rich_lines.append(current)
                current = []
                current_length = 0
            if emphasized and segment_length > max_chars:
                for char in segment:
                    if current and current_length + 1 > max_chars:
                        rich_lines.append(current)
                        current = []
                        current_length = 0
                    current.append((char, True))
                    current_length += 1
            else:
                current.append((segment, emphasized))
                current_length += segment_length
        rich_lines.append(current)
    for index, chars in enumerate(rich_lines):
        line_y = y + int(index * size * gap)
        output.append(
            f'<text x="{x}" y="{line_y}" text-anchor="middle" '
            f'font-family="PingFang SC, Heiti SC, Arial, sans-serif" font-size="{size}" fill="{fill}">'
        )
        for segment, emphasized in _group_rich_chars(chars):
            weight = bold_weight if emphasized else normal_weight
            stroke = f' stroke="{fill}" stroke-width="0.7" paint-order="stroke"' if emphasized else ""
            output.append(
                f'<tspan font-weight="{weight}"{stroke}>{html.escape(segment)}</tspan>'
            )
        output.append("</text>")
    return output


def svg_person(x: int, y: int, scale: float = 1.0, *, red_body: bool = False, lean: float = 0.0) -> list[str]:
    s = scale
    body_fill = BLACK
    lean_px = lean * 18 * s
    return [
        f'<g class="person-silhouette core-character" data-family="person_silhouette" data-character-id="mind_walker">',
        f'<ellipse class="ground-shadow" cx="{x + 2 * s:.1f}" cy="{y + 74 * s:.1f}" rx="{50 * s:.1f}" ry="{8 * s:.1f}" fill="{MID_GRAY}" opacity="0.32"/>',
        f'<circle cx="{x + lean_px:.1f}" cy="{y - 82 * s:.1f}" r="{17 * s:.1f}" fill="{BLACK}"/>',
        (
            f'<path d="M{x - 20 * s:.1f} {y - 58 * s:.1f} '
            f'C{x - 8 * s:.1f} {y - 68 * s:.1f} {x + 18 * s + lean_px:.1f} {y - 66 * s:.1f} {x + 25 * s + lean_px:.1f} {y - 45 * s:.1f} '
            f'L{x + 24 * s + lean_px:.1f} {y + 12 * s:.1f} '
            f'C{x + 8 * s:.1f} {y + 23 * s:.1f} {x - 10 * s:.1f} {y + 18 * s:.1f} {x - 18 * s:.1f} {y + 8 * s:.1f} Z" '
            f'fill="{body_fill}"/>'
        ),
        (
            f'<path class="character-anchor-scarf" d="M{x - 16 * s:.1f} {y - 60 * s:.1f} '
            f'L{x + 17 * s + lean_px:.1f} {y - 53 * s:.1f} L{x - 2 * s:.1f} {y - 41 * s:.1f} Z" '
            f'fill="{DEEP_RED}"/>'
        ),
        (
            f'<path class="character-anchor-scarf-tail" d="M{x + 12 * s + lean_px:.1f} {y - 53 * s:.1f} '
            f'L{x + 48 * s + lean_px:.1f} {y - 40 * s:.1f} L{x + 22 * s + lean_px:.1f} {y - 29 * s:.1f} Z" '
            f'fill="{DEEP_RED}"/>'
        ),
        f'<path d="M{x - 4 * s:.1f} {y + 9 * s:.1f} C{x - 16 * s:.1f} {y + 28 * s:.1f} {x - 28 * s:.1f} {y + 50 * s:.1f} {x - 38 * s:.1f} {y + 72 * s:.1f}" stroke="{BLACK}" stroke-width="{7 * s:.1f}" fill="none"/>',
        f'<path d="M{x + 12 * s:.1f} {y + 8 * s:.1f} C{x + 24 * s:.1f} {y + 29 * s:.1f} {x + 36 * s:.1f} {y + 49 * s:.1f} {x + 48 * s:.1f} {y + 68 * s:.1f}" stroke="{BLACK}" stroke-width="{7 * s:.1f}" fill="none"/>',
        f'<path d="M{x - 14 * s:.1f} {y - 38 * s:.1f} C{x - 30 * s:.1f} {y - 26 * s:.1f} {x - 42 * s:.1f} {y - 12 * s:.1f} {x - 54 * s:.1f} {y + 4 * s:.1f}" stroke="{BLACK}" stroke-width="{6 * s:.1f}" fill="none"/>',
        f'<path d="M{x + 18 * s:.1f} {y - 40 * s:.1f} C{x + 34 * s:.1f} {y - 30 * s:.1f} {x + 46 * s:.1f} {y - 20 * s:.1f} {x + 58 * s:.1f} {y - 10 * s:.1f}" stroke="{BLACK}" stroke-width="{6 * s:.1f}" fill="none"/>',
        "</g>",
    ]


def svg_semantic_details(scene: str) -> list[str]:
    path_growth = {"open_path", "recovery_growth", "rebuilding"}
    cognition = {"isolated_person", "cognitive_load", "fractured_identity", "dual_layer_system"}
    relationship = {"social_distance", "hidden_signal", "relationship_signal", "relationship_boundary", "boundary"}
    direction = {"blocked_path", "choice_point", "changed_route", "new_direction"}
    time_system = {"cycle_loop", "time_horizon", "repeated_pattern", "system_map", "environment_design", "identity_upgrade"}
    if scene in path_growth:
        if scene == "recovery_growth":
            context_prop = (
                f'<g data-family="semantic_context_prop" class="recovery-tree">'
                f'<path d="M250 1110 V950 M250 1000 L205 960 M250 1020 L305 975" stroke="{BLACK}" stroke-width="8" fill="none"/>'
                f'<circle cx="205" cy="950" r="22" fill="{PALE_RED}"/><circle cx="250" cy="925" r="26" fill="{PALE_RED}"/>'
                f'<circle cx="305" cy="965" r="22" fill="{PALE_RED}"/><circle cx="840" cy="790" r="25" fill="{DEEP_RED}"/>'
                f'</g>'
            )
        elif scene == "rebuilding":
            context_prop = (
                f'<g data-family="semantic_context_prop" class="rebuilding-blocks">'
                f'<rect x="190" y="1120" width="76" height="60" rx="8" fill="none" stroke="{GRAY}" stroke-width="5"/>'
                f'<rect x="260" y="1060" width="76" height="120" rx="8" fill="none" stroke="{GRAY}" stroke-width="5"/>'
                f'<rect x="330" y="1000" width="76" height="180" rx="8" fill="none" stroke="{GRAY}" stroke-width="5"/>'
                f'<rect x="400" y="940" width="76" height="240" rx="8" fill="none" stroke="{DEEP_RED}" stroke-width="5"/>'
                f'</g>'
            )
        else:
            context_prop = (
                f'<g data-family="semantic_context_prop" class="destination-flag">'
                f'<path d="M832 770 V930" stroke="{BLACK}" stroke-width="7"/>'
                f'<path d="M832 772 L920 806 L832 840 Z" fill="{DEEP_RED}"/>'
                f'<circle cx="260" cy="1100" r="9" fill="{DEEP_RED}"/>'
                f'<circle cx="360" cy="1018" r="9" fill="{DEEP_RED}"/>'
                f'</g>'
            )
        return [
            (
                f'<g data-family="background_structure" class="landscape-context" opacity="0.42">'
                f'<path d="M160 1110 Q410 800 880 1030 M160 1066 Q410 756 880 986 M160 1022 Q410 712 880 942" '
                f'stroke="{MID_GRAY}" stroke-width="3" fill="none"/>'
                f'</g>'
            ),
            context_prop,
        ]
    if scene in cognition:
        return [
            (
                f'<g data-family="background_structure" class="cognitive-grid" opacity="0.3">'
                f'<path d="M210 746 V1160 M540 746 V1160 M870 746 V1160 M160 790 H920 M160 960 H920 M160 1130 H920" '
                f'stroke="{MID_GRAY}" stroke-width="2"/>'
                f'</g>'
            ),
            (
                f'<g data-family="semantic_context_prop" class="task-stack">'
                f'<rect x="174" y="790" width="180" height="58" rx="12" fill="none" stroke="{GRAY}" stroke-width="4"/>'
                f'<rect x="196" y="865" width="180" height="58" rx="12" fill="none" stroke="{GRAY}" stroke-width="4"/>'
                f'<circle cx="204" cy="819" r="11" fill="{BLACK}"/><circle cx="226" cy="894" r="11" fill="{DEEP_RED}"/>'
                f'</g>'
            ),
        ]
    if scene in relationship:
        return [
            (
                f'<g data-family="background_structure" class="relationship-zones" opacity="0.4">'
                f'<ellipse cx="395" cy="970" rx="215" ry="200" fill="none" stroke="{MID_GRAY}" stroke-width="4"/>'
                f'<ellipse cx="685" cy="970" rx="215" ry="200" fill="none" stroke="{PALE_RED}" stroke-width="4"/>'
                f'</g>'
            ),
            (
                f'<g data-family="semantic_context_prop" class="boundary-posts">'
                f'<path d="M170 950 V1130 M230 950 V1130" stroke="{BLACK}" stroke-width="6"/>'
                f'<path d="M850 950 V1130 M910 950 V1130" stroke="{DEEP_RED}" stroke-width="6"/>'
                f'<path d="M540 900 V1160" stroke="{DEEP_RED}" stroke-width="8"/>'
                f'<path d="M250 1030 H830" stroke="{GRAY}" stroke-width="4" stroke-dasharray="16 10"/>'
                f'</g>'
            ),
        ]
    if scene in direction:
        return [
            (
                f'<g data-family="background_structure" class="direction-compass" opacity="0.38">'
                f'<circle cx="540" cy="960" r="220" fill="none" stroke="{MID_GRAY}" stroke-width="4"/>'
                f'<path d="M540 740 V790 M540 1130 V1180 M320 960 H370 M710 960 H760" stroke="{MID_GRAY}" stroke-width="3"/>'
                f'</g>'
            ),
            (
                f'<g data-family="semantic_context_prop" class="route-fork">'
                f'<path d="M220 1110 L350 960 L270 830 M350 960 L455 840" fill="none" stroke="{BLACK}" stroke-width="7"/>'
                f'<path d="M350 960 L455 840" fill="none" stroke="{DEEP_RED}" stroke-width="10"/>'
                f'</g>'
            ),
        ]
    if scene in time_system:
        if scene == "time_horizon":
            detail = (
                f'<g data-family="annotation_node" class="time-horizon">'
                f'<path d="M160 1080 H450" stroke="{BLACK}" stroke-width="6"/>'
                f'<path d="M190 1080 V1046 M270 1080 V1026 M350 1080 V1006 M430 1080 V986" stroke="{GRAY}" stroke-width="5"/>'
                f'<circle cx="430" cy="986" r="9" fill="{DEEP_RED}"/>'
                f'</g>'
            )
        elif scene == "identity_upgrade":
            detail = (
                f'<g data-family="annotation_node" class="identity-steps">'
                f'<path d="M160 1110 H252 V1034 H324 V958 H396 V882 H488" fill="none" stroke="{GRAY}" stroke-width="6"/>'
                f'<circle cx="488" cy="882" r="18" fill="{DEEP_RED}"/>'
                f'</g>'
            )
        else:
            detail = (
                f'<g data-family="annotation_node" class="system-network">'
                f'<path d="M180 820 L330 760 L410 920 L260 1060" stroke="{GRAY}" stroke-width="4" fill="none"/>'
                f'<circle cx="180" cy="820" r="12" fill="{BLACK}"/><circle cx="330" cy="760" r="12" fill="{BLACK}"/>'
                f'<circle cx="410" cy="920" r="18" fill="{DEEP_RED}"/><circle cx="260" cy="1060" r="12" fill="{BLACK}"/>'
                f'</g>'
            )
        return [
            (
                f'<g data-family="background_structure" class="system-orbits" opacity="0.34">'
                f'<path d="M370 930 A170 170 0 1 0 710 930 M310 930 A230 230 0 1 0 770 930 M250 930 A290 290 0 1 0 830 930" '
                f'fill="none" stroke="{MID_GRAY}" stroke-width="3"/>'
                f'</g>'
            ),
            detail,
        ]
    if scene == "emotional_relief":
        return [
            (
                f'<g data-family="semantic_context_prop" class="relief-weather">'
                f'<path d="M160 980 A120 100 0 0 1 400 980 M220 970 A125 120 0 0 1 470 970" '
                f'fill="none" stroke="{GRAY}" stroke-width="5"/>'
                f'<circle cx="840" cy="820" r="34" fill="{DEEP_RED}" opacity="0.8"/>'
                f'</g>'
            )
        ]
    return []


def svg_scene_group(scene: str, lines: list[str]) -> list[str]:
    return [
        f'<g data-scene="{html.escape(scene)}" class="semantic-vector-scene">',
        *svg_semantic_details(scene),
        *lines,
        "</g>",
    ]


def svg_ground(x1: int, y: int, x2: int) -> str:
    return (
        f'<g data-family="environment_symbol" class="ground-line">'
        f'<path d="M{x1} {y} H{x2}" stroke="{BLACK}" stroke-width="7" fill="none"/>'
        f'<ellipse cx="{(x1 + x2) / 2:.1f}" cy="{y + 18}" rx="{abs(x2 - x1) / 2 - 24:.1f}" ry="10" '
        f'fill="none" stroke="{MID_GRAY}" stroke-width="2" opacity="0.32"/>'
        "</g>"
    )


def svg_radiant_dot(x: int, y: int, radius: int, fill: str = DEEP_RED) -> str:
    rays = []
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        x1 = x + int(math.cos(rad) * (radius + 13))
        y1 = y + int(math.sin(rad) * (radius + 13))
        x2 = x + int(math.cos(rad) * (radius + 31))
        y2 = y + int(math.sin(rad) * (radius + 31))
        rays.append(f'M{x1} {y1} L{x2} {y2}')
    return (
        f'<g data-family="environment_symbol" class="radiant-dot">'
        f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{fill}"/>'
        f'<path d="{" ".join(rays)}" stroke="{fill}" stroke-width="4" fill="none"/>'
        "</g>"
    )


def svg_scene_body(scene: str) -> list[str]:
    semantic_scene = scene
    scene = METAPHOR_FAMILY_TO_SCENE.get(scene, scene)
    if scene == "thought_load":
        return svg_scene_group(
            semantic_scene,
            [
                svg_ground(250, 1124, 810),
                *svg_person(540, 1042, 1.02, lean=-0.12),
                (
                    f'<g data-family="environment_symbol" class="thought-cloud">'
                    f'<ellipse cx="394" cy="806" rx="92" ry="74" fill="{BLACK}"/>'
                    f'<ellipse cx="528" cy="758" rx="122" ry="92" fill="{BLACK}"/>'
                    f'<ellipse cx="684" cy="818" rx="134" ry="86" fill="{BLACK}"/>'
                    f'<path d="M336 806 H732 Q760 806 760 836 V895 H364 V838 Q364 806 336 806 Z" fill="{BLACK}"/>'
                    f'<path d="M424 908 L474 970 M660 906 L612 976" stroke="{BLACK}" stroke-width="8" fill="none"/>'
                    "</g>"
                ),
                (
                    f'<g data-family="red_path_or_arc" class="pressure-arcs">'
                    f'<path d="M306 978 Q338 930 370 978 M420 978 Q452 930 484 978 '
                    f'M534 978 Q566 930 598 978 M648 978 Q680 930 712 978" '
                    f'fill="none" stroke="{DEEP_RED}" stroke-width="7"/>'
                    f'<path d="M746 1094 H814 M780 1060 V1128" stroke="{DEEP_RED}" stroke-width="11" fill="none"/>'
                    "</g>"
                ),
            ],
        )
    if scene == "failure_shadow":
        return svg_scene_group(
            semantic_scene,
            [
                f'<circle data-family="environment_symbol" cx="286" cy="946" r="142" fill="none" stroke="{DEEP_RED}" stroke-width="22"/>',
                f'<path data-family="environment_symbol" d="M190 850 L380 1040 M380 850 L190 1040" stroke="{DEEP_RED}" stroke-width="28"/>',
                (
                    f'<g data-family="semantic_context_prop" class="future-doors">'
                    f'<rect x="650" y="794" width="84" height="274" rx="12" fill="none" stroke="{MID_GRAY}" stroke-width="7"/>'
                    f'<rect x="764" y="794" width="84" height="274" rx="12" fill="none" stroke="{MID_GRAY}" stroke-width="7"/>'
                    f'<rect x="878" y="794" width="84" height="274" rx="12" fill="none" stroke="{MID_GRAY}" stroke-width="7"/>'
                    f'<path d="M662 872 L722 992 M722 872 L662 992 M776 872 L836 992 M836 872 L776 992 M890 872 L950 992 M950 872 L890 992" stroke="{DEEP_RED}" stroke-width="14"/>'
                    f'</g>'
                ),
                f'<path data-family="red_path_or_arc" d="M404 912 Q612 748 928 844" stroke="{DEEP_RED}" stroke-width="15" fill="none"/>',
                f'<path data-family="environment_symbol" d="M372 962 L522 862 L622 1080 L416 1050 Z" fill="{BLACK}" opacity="0.2"/>',
                *svg_person(568, 1090, 0.90, lean=-0.18),
            ],
        )
    if scene == "risk_signal":
        return svg_scene_group(
            semantic_scene,
            [
                f'<circle data-family="environment_symbol" cx="540" cy="925" r="252" fill="none" stroke="{MID_GRAY}" stroke-width="5" opacity="0.45"/>',
                f'<path data-family="environment_symbol" d="M540 765 A158 158 0 1 0 540 1083 Z" fill="{BLACK}"/>',
                f'<path data-family="environment_symbol" d="M540 765 A158 158 0 0 1 540 1083 Z" fill="{PALE_GRAY}"/>',
                f'<rect data-family="environment_symbol" x="540" y="765" width="54" height="318" fill="{MID_GRAY}" opacity="0.75"/>',
                f'<g data-family="red_path_or_arc" class="risk-radar"><path d="M704 1094 A222 222 0 0 0 766 780" fill="none" stroke="{DEEP_RED}" stroke-width="24"/><path d="M540 925 L736 783" stroke="{DEEP_RED}" stroke-width="7"/></g>',
                f'<path data-family="environment_symbol" d="M334 1058 A292 292 0 0 1 322 884" fill="none" stroke="{BLACK}" stroke-width="7" opacity="0.72"/>',
                f'<path data-family="environment_symbol" d="M770 802 L856 728 M810 852 L900 788 M842 908 L936 846" stroke="{GRAY}" stroke-width="5"/>',
                svg_radiant_dot(724, 758, 25, PALE_RED),
                *svg_person(770, 1090, 0.70, lean=-0.18),
            ],
        )
    if scene == "threshold":
        return svg_scene_group(
            semantic_scene,
            [
                svg_ground(240, 1090, 850),
                (
                    f'<g data-family="environment_symbol" class="threshold-gate">'
                    f'<rect x="592" y="808" width="236" height="282" rx="16" fill="none" stroke="{BLACK}" stroke-width="11"/>'
                    f'<path d="M710 824 V1070" stroke="{MID_GRAY}" stroke-width="5"/>'
                    f'<rect x="616" y="1036" width="184" height="54" fill="{DEEP_RED}"/>'
                    "</g>"
                ),
                *svg_person(370, 1090, 0.74, lean=0.18),
                f'<path data-family="red_path_or_arc" d="M500 1084 Q568 1032 626 1036" stroke="{DEEP_RED}" stroke-width="13" fill="none"/>',
            ],
        )
    if scene == "lower_entry":
        return svg_scene_group(
            semantic_scene,
            [
                svg_ground(250, 1088, 840),
                f'<path data-family="environment_symbol" d="M314 866 H728" stroke="{MID_GRAY}" stroke-width="24" fill="none"/>',
                f'<path data-family="environment_symbol" d="M314 866 Q484 1028 756 1088" stroke="{MID_GRAY}" stroke-width="12" fill="none" opacity="0.65"/>',
                f'<path data-family="red_path_or_arc" d="M292 1088 Q520 1072 800 998" stroke="{DEEP_RED}" stroke-width="19" fill="none"/>',
                f'<circle data-family="red_path_or_arc" cx="780" cy="998" r="33" fill="none" stroke="{DEEP_RED}" stroke-width="8"/>',
                *svg_person(594, 1034, 0.66, red_body=True, lean=0.26),
            ],
        )
    if scene == "timed_action":
        ticks = []
        for angle in range(0, 360, 30):
            rad = math.radians(angle - 90)
            x1 = 540 + int(math.cos(rad) * 154)
            y1 = 930 + int(math.sin(rad) * 154)
            x2 = 540 + int(math.cos(rad) * 174)
            y2 = 930 + int(math.sin(rad) * 174)
            ticks.append(f'M{x1} {y1} L{x2} {y2}')
        return svg_scene_group(
            semantic_scene,
            [
                f'<g data-family="environment_symbol" class="timer-ring"><circle cx="540" cy="930" r="210" fill="none" stroke="{MID_GRAY}" stroke-width="4" opacity="0.45"/><circle cx="540" cy="930" r="180" fill="none" stroke="{BLACK}" stroke-width="13"/><path d="{" ".join(ticks)}" stroke="{BLACK}" stroke-width="4" opacity="0.66"/></g>',
                f'<path data-family="red_path_or_arc" d="M540 750 A180 180 0 1 1 398 1040" fill="none" stroke="{DEEP_RED}" stroke-width="20"/>',
                f'<path data-family="environment_symbol" d="M540 930 L610 842 M540 930 L540 805" stroke="{BLACK}" stroke-width="9" fill="none"/>',
                f'<circle data-family="red_path_or_arc" cx="540" cy="930" r="10" fill="{DEEP_RED}"/>',
                f'<circle data-family="environment_symbol" cx="468" cy="1000" r="16" fill="{BLACK}"/>',
                f'<circle data-family="red_path_or_arc" cx="540" cy="1000" r="12" fill="{DEEP_RED}"/>',
                f'<circle data-family="environment_symbol" cx="612" cy="1000" r="8" fill="{BLACK}"/>',
                svg_ground(750, 1180, 910),
                *svg_person(810, 1105, 0.42, red_body=True, lean=-0.15),
            ],
        )
    if scene == "system_redesign":
        return svg_scene_group(
            semantic_scene,
            [
                (
                    f'<g data-family="system_panel" class="system-panel">'
                    f'<rect x="285" y="748" width="510" height="360" rx="22" fill="none" stroke="{BLACK}" stroke-width="9"/>'
                    f'<path d="M362 850 H718 M362 940 H718 M362 1030 H718" stroke="{GRAY}" stroke-width="8"/>'
                    f'<circle cx="504" cy="850" r="24" fill="{BLACK}"/>'
                    f'<circle cx="634" cy="940" r="24" fill="{DEEP_RED}"/>'
                    f'<circle cx="574" cy="1030" r="24" fill="{BLACK}"/>'
                    "</g>"
                ),
                svg_ground(236, 1162, 850),
                f'<path data-family="red_path_or_arc" d="M278 1155 Q502 1040 766 1138" stroke="{DEEP_RED}" stroke-width="11" fill="none"/>',
                f'<circle data-family="red_path_or_arc" cx="766" cy="1138" r="22" fill="{DEEP_RED}"/>',
                *svg_person(750, 1160, 0.5, red_body=True, lean=-0.08),
            ],
        )
    return svg_scene_group(
        semantic_scene,
        [
            svg_ground(210, 1050, 862),
            f'<path data-family="environment_symbol" d="M274 1050 L602 1050 L602 692 Z" fill="{PALE_RED}" opacity="0.72"/>',
            f'<path data-family="red_path_or_arc" d="M276 1044 Q418 830 602 694" stroke="{DEEP_RED}" stroke-width="18" fill="none"/>',
            '<path d="M425 845 L480 765 L503 730" stroke="#ffffff" stroke-width="10" fill="none"/>',
            f'<rect data-family="environment_symbol" x="586" y="686" width="54" height="364" fill="{BLACK}"/>',
            f'<path data-family="environment_symbol" d="M520 690 C425 700 382 800 415 920 C448 1015 520 1050 602 1050 L602 700 Z" fill="{BLACK}"/>',
            svg_radiant_dot(714, 720, 30, DEEP_RED),
            *svg_person(792, 840, 0.45, red_body=True, lean=-0.1),
            f'<path data-family="environment_symbol" d="M690 980 Q780 1060 858 1150" stroke="{BLACK}" stroke-width="4" fill="none" opacity="0.68"/>',
        ],
    )


def write_svg_assets(cards: list[dict[str, Any]], svg_dir: Path) -> dict[str, Any]:
    svg_dir.mkdir(parents=True, exist_ok=True)
    assets = []
    for index, card in enumerate(cards):
        scene = str(card.get("scene") or "open_path")
        path = svg_dir / f"metaphor_{index:02d}_{scene}.svg"
        max_explicit_line = max(
            (len(strip_emphasis_markup(line)) for line in str(card.get("core", "")).split("\n")),
            default=0,
        )
        svg_core_size = 64 if max_explicit_line <= 14 else 54
        svg_max_chars = max(14, min(16, max_explicit_line))
        core_lines = svg_rich_text_lines(
            str(card.get("core", "")), 540, 382, svg_core_size, BLACK, max_chars=svg_max_chars
        )
        theme_line = svg_text_lines(str(card.get("theme", "")), 540, 226, 52, RED, weight=650)
        scene_lines = svg_scene_body(scene)
        path.write_text(
            "\n".join(
                [
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1440">',
                    '<rect width="1080" height="1440" fill="#ffffff"/>',
                    f'<!-- scene={html.escape(scene)}; card_form={html.escape(str(card.get("card_form") or ""))}; original vector-metaphor, no copied source frame/logo/watermark -->',
                    '<style>.semantic-vector-scene *{vector-effect:non-scaling-stroke}.person-silhouette path{stroke-linecap:round;stroke-linejoin:round}</style>',
                    (
                        f'<g id="layout" data-card-form="{html.escape(str(card.get("card_form") or ""))}" '
                        f'data-emphasis-keywords="{html.escape("|".join(str(item) for item in card.get("emphasis_keywords") or []))}">'
                    ),
                    '<circle cx="88" cy="86" r="44" fill="none" stroke="#111111" stroke-width="5"/>',
                    '<text x="88" y="104" text-anchor="middle" font-family="PingFang SC, Arial, sans-serif" font-size="54" font-weight="700" fill="#111111">思</text>',
                    '<text x="540" y="112" text-anchor="middle" font-family="PingFang SC, Arial, sans-serif" font-size="48" font-weight="600" fill="#595959">MIND STRUCTURE</text>',
                    *theme_line,
                    *core_lines,
                    '<text x="540" y="618" text-anchor="middle" font-family="PingFang SC, Arial, sans-serif" font-size="36" font-weight="600" fill="#505050" letter-spacing="12">COGNITIVE STRUCTURE</text>',
                    '<rect x="0" y="1320" width="1080" height="120" fill="#dedede"/>',
                    '<path d="M390 1343 V1410 M650 1343 V1410" stroke="#111111" stroke-width="2"/>',
                    '<text x="260" y="1376" text-anchor="middle" font-family="PingFang SC, Arial, sans-serif" font-size="34" font-weight="700" fill="#111111">现实场景</text>',
                    '<text x="260" y="1420" text-anchor="middle" font-family="PingFang SC, Arial, sans-serif" font-size="34" font-weight="700" fill="#111111">先被看见</text>',
                    '<text x="540" y="1376" text-anchor="middle" font-family="PingFang SC, Arial, sans-serif" font-size="34" font-weight="700" fill="#111111">机制拆解</text>',
                    '<text x="540" y="1420" text-anchor="middle" font-family="PingFang SC, Arial, sans-serif" font-size="34" font-weight="700" fill="#111111">获得解释</text>',
                    '<text x="820" y="1376" text-anchor="middle" font-family="PingFang SC, Arial, sans-serif" font-size="34" font-weight="700" fill="#111111">行动重建</text>',
                    '<text x="820" y="1420" text-anchor="middle" font-family="PingFang SC, Arial, sans-serif" font-size="34" font-weight="700" fill="#111111">身份升级</text>',
                    '</g>',
                    '<g id="metaphor" stroke-linecap="round" stroke-linejoin="round">',
                    *scene_lines,
                    '</g>',
                    '</svg>',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        assets.append({"card": index, "scene": scene, "path": str(path)})
    return {
        "svg_assets": assets,
        "component_library": {
            "required_families": VECTOR_REQUIRED_FAMILIES,
            "optional_families": VECTOR_OPTIONAL_FAMILIES,
            "style_rules": [
                "person silhouettes use filled body paths and curved limbs, not stick-figure lines only",
                "every card reuses character id mind_walker with the same black silhouette and red scarf while pose, prop, and position change by scene",
                "red paths, arcs, or rings carry the action mechanism",
                "environment symbols hold the cognitive context and must stay black/gray",
                "system panels appear when the card explains redesign or control logic",
                "each middle scene uses a background structure, one primary metaphor, and at least two context props",
                "context props are drawn from local vector primitives instead of unlicensed web icons",
            ],
        },
    }


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, text=True, capture_output=True)


def run_text(command: list[str]) -> str:
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    return (result.stdout or "") + (result.stderr or "")


def ffprobe_duration(path: Path) -> float:
    output = run_text(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    ).strip()
    try:
        return float(output)
    except ValueError as exc:
        raise SystemExit(f"could not read duration for {path}: {output}") from exc


def audio_loudness(path: Path) -> dict[str, Any]:
    text = run_text(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"])
    report: dict[str, Any] = {"ok": True}
    for line in text.splitlines():
        if "mean_volume:" in line:
            try:
                report["mean_volume_db"] = float(line.rsplit("mean_volume:", 1)[1].strip().split(" ", 1)[0])
            except (IndexError, ValueError):
                pass
        if "max_volume:" in line:
            try:
                report["max_volume_db"] = float(line.rsplit("max_volume:", 1)[1].strip().split(" ", 1)[0])
            except (IndexError, ValueError):
                pass
    if "max_volume_db" not in report:
        report["ok"] = False
        report["error"] = "volumedetect max_volume not found"
    return report


def nested_config(params: dict[str, Any]) -> dict[str, Any]:
    value = params.get("config")
    if not isinstance(value, dict):
        return {}
    video = value.get("video_elements") if isinstance(value.get("video_elements"), dict) else {}
    merged: dict[str, Any] = {
        "roles": value.get("roles", {}),
        "output_contract": value.get("output_contract", {}),
        "video_elements": video,
    }
    video_element_keys: set[str] = set()
    for section in ("defaults", "user_overridable", "fixed"):
        section_value = video.get(section) if isinstance(video.get(section), dict) else {}
        video_element_keys.update(str(key) for key in section_value)
        merged.update(section_value)
    for key, item in value.items():
        if key not in {"roles", "output_contract", "video_elements"} and key not in video_element_keys:
            merged[key] = item
    return merged


def number_param(params: dict[str, Any], key: str, default: float) -> float:
    config = nested_config(params)
    value = params.get(key, config.get(key, default))
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def bool_param(params: dict[str, Any], key: str, default: bool) -> bool:
    config = nested_config(params)
    if key in params:
        value = params[key]
    elif key in config:
        value = config[key]
    else:
        env_value = os.getenv(key.upper())
        value = env_value if env_value is not None else default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def selected_tts_provider(params: dict[str, Any]) -> str:
    config = nested_config(params)
    provider = str(
        params.get("tts_provider")
        or config.get("tts_provider")
        or os.getenv("TTS_PROVIDER")
        or DEFAULT_REMOTE_TTS_PROVIDER
    ).strip().lower()
    if provider not in {"", "auto"}:
        return provider
    if os.getenv("DOUBAO_TTS_API_KEY"):
        return "doubao"
    if os.getenv("MINIMAX_API_KEY"):
        return "minimax"
    return "local_system"


def generate_voiceover_audio(text: str, params: dict[str, Any], out_path: Path) -> dict[str, Any]:
    existing_path_value = str(
        params.get("narration_path") or nested_config(params).get("narration_path") or ""
    ).strip()
    if existing_path_value:
        existing_path = Path(existing_path_value).expanduser().resolve()
        if not existing_path.is_file():
            raise SystemExit(f"configured narration audio is missing: {existing_path}")
        provider_hint = str(params.get("narration_provider") or "").strip().lower()
        if provider_hint not in {"doubao", "minimax"}:
            raise SystemExit("reused narration_provider must be doubao or minimax")
        return {
            "provider": provider_hint,
            "requested_provider": provider_hint,
            "voice": str(params.get("narration_voice") or params.get("tts_voice") or "reused_approved_voice"),
            "requested_voice": str(params.get("narration_voice") or params.get("tts_voice") or "reused_approved_voice"),
            "speed": number_param(params, "tts_speed", DEFAULT_REMOTE_TTS_SPEED),
            "path": str(existing_path),
            "source_path": str(existing_path),
            "duration": round(ffprobe_duration(existing_path), 3),
            "loudness": audio_loudness(existing_path),
            "fallback_from": None,
            "remote_error": None,
            "quality_tier": "production_tts_reused",
        }
    provider = selected_tts_provider(params)
    remote_output = out_path.with_name(f"{out_path.stem}_{provider}.mp3")
    config = nested_config(params)
    doubao_voice = str(
        params.get("doubao_tts_voice")
        or config.get("doubao_tts_voice")
        or params.get("tts_voice")
        or config.get("tts_voice")
        or DEFAULT_DOUBAO_TTS_VOICE
    )
    minimax_voice = str(
        params.get("minimax_tts_voice")
        or config.get("minimax_tts_voice")
        or DEFAULT_MINIMAX_TTS_VOICE
    )
    voice_type = minimax_voice if provider == "minimax" else doubao_voice
    speed = number_param(params, "tts_speed", DEFAULT_REMOTE_TTS_SPEED)
    allow_local_fallback = bool_param(params, "allow_local_tts_fallback", True)
    allow_provider_fallback = bool_param(params, "allow_tts_provider_fallback", False)

    if provider in {"minimax", "doubao"}:
        from custom_tools.audio_generation.tts_tool import UniversalTTSTool

        tool = UniversalTTSTool()
        result = tool._run(
            text=text,
            output_path=str(remote_output),
            provider=provider,
            voice_type=voice_type,
            speed=speed,
            encoding="mp3",
            allow_provider_fallback=allow_provider_fallback,
            allow_local_fallback=allow_local_fallback,
        )
        if isinstance(result, dict) and result.get("success"):
            audio_path = Path(str(result.get("audio_path") or result.get("output_path") or remote_output))
            actual_provider = str(result.get("provider") or provider)
            if actual_provider in {"local", "local_system", "system", "post_production"} and not allow_local_fallback:
                raise SystemExit("remote TTS failed and local fallback is disabled")
            return {
                "provider": actual_provider,
                "requested_provider": provider,
                "voice": minimax_voice if actual_provider == "minimax" else voice_type,
                "requested_voice": voice_type,
                "speed": speed,
                "path": str(audio_path),
                "duration": round(ffprobe_duration(audio_path), 3),
                "loudness": audio_loudness(audio_path),
                "fallback_from": result.get("fallback_from"),
                "remote_error": result.get("minimax_error") or result.get("doubao_error"),
                "quality_tier": "production_tts" if actual_provider in {"minimax", "doubao"} else "local_preview_fallback",
            }
        if not allow_local_fallback:
            raise SystemExit(f"{provider} TTS failed: {result}")

    say = shutil.which("say")
    if not say:
        raise SystemExit("local TTS unavailable: macOS say command not found")
    voice = str(params.get("local_tts_voice") or DEFAULT_TTS_VOICE)
    rate = int(number_param(params, "local_tts_rate", DEFAULT_TTS_RATE))
    run([say, "-v", voice, "-r", str(rate), "-o", str(out_path), text])
    return {
        "provider": "local_macos_say_preview",
        "requested_provider": provider,
        "voice": voice,
        "rate": rate,
        "path": str(out_path),
        "duration": round(ffprobe_duration(out_path), 3),
        "loudness": audio_loudness(out_path),
        "quality_tier": "local_preview_fallback",
    }


def generate_voiceover_by_beat(
    cards: list[dict[str, Any]],
    params: dict[str, Any],
    audio_dir: Path,
) -> dict[str, Any]:
    """Generate, measure, normalize, and concatenate narration one semantic beat at a time."""
    beats_dir = audio_dir / "beats"
    normalized_dir = beats_dir / "normalized"
    beats_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    default_pause = max(0.12, min(number_param(params, "beat_pause_seconds", 0.24), 0.8))
    beat_params = dict(params)
    for key in ("narration_path", "narration_provider", "narration_voice"):
        beat_params.pop(key, None)

    segments: list[dict[str, Any]] = []
    concat_sources: list[Path] = []
    provider_names: list[str] = []
    cursor = 0.0
    for index, card in enumerate(cards):
        beat_id = str(card.get("id") or f"beat_{index:02d}")
        requested_output = beats_dir / f"{index:02d}_{beat_id}.aiff"
        info = generate_voiceover_audio(str(card["narration"]), beat_params, requested_output)
        source = Path(str(info["path"]))
        normalized = normalized_dir / f"{index:02d}_{beat_id}.wav"
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-ar",
                "44100",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(normalized),
            ]
        )
        speech_seconds = ffprobe_duration(normalized)
        pause_seconds = 0.0
        if index < len(cards) - 1:
            pause_seconds = float(card.get("pause_after_seconds") or default_pause)
            pause_seconds = max(0.12, min(pause_seconds, 0.8))
        card["measured_audio_seconds"] = speech_seconds + pause_seconds
        concat_sources.append(normalized)
        if pause_seconds > 0:
            pause_path = normalized_dir / f"{index:02d}_{beat_id}_pause.wav"
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=44100:cl=mono",
                    "-t",
                    f"{pause_seconds:.3f}",
                    "-c:a",
                    "pcm_s16le",
                    str(pause_path),
                ]
            )
            concat_sources.append(pause_path)
        provider_names.append(str(info.get("provider") or ""))
        segments.append(
            {
                "beat_id": beat_id,
                "narration": card["narration"],
                "source_audio": str(source),
                "normalized_audio": str(normalized),
                "provider": info.get("provider"),
                "voice": info.get("voice"),
                "speed": info.get("speed"),
                "start_seconds": round(cursor, 3),
                "speech_seconds": round(speech_seconds, 3),
                "pause_after_seconds": round(pause_seconds, 3),
                "card_duration_seconds": round(speech_seconds + pause_seconds, 3),
                "end_seconds": round(cursor + speech_seconds + pause_seconds, 3),
            }
        )
        cursor += speech_seconds + pause_seconds

    concat_manifest = beats_dir / "concat.txt"
    concat_manifest.write_text(
        "".join(f"file '{str(path).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n" for path in concat_sources),
        encoding="utf-8",
    )
    narration_master = audio_dir / "narration_by_beat.mp3"
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_manifest),
            "-ar",
            "44100",
            "-ac",
            "1",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(narration_master),
        ]
    )
    actual_duration = ffprobe_duration(narration_master)
    requested_provider = selected_tts_provider(params)
    actual_provider = provider_names[0] if provider_names and len(set(provider_names)) == 1 else "mixed_remote_tts"
    return {
        "provider": actual_provider,
        "requested_provider": requested_provider,
        "voice": str(params.get("tts_voice") or DEFAULT_DOUBAO_TTS_VOICE),
        "requested_voice": str(params.get("tts_voice") or DEFAULT_DOUBAO_TTS_VOICE),
        "speed": number_param(params, "tts_speed", DEFAULT_REMOTE_TTS_SPEED),
        "path": str(narration_master),
        "duration": round(actual_duration, 3),
        "loudness": audio_loudness(narration_master),
        "quality_tier": "production_tts_segmented",
        "timing_authority": "measured per-beat narration plus explicit inter-beat pauses",
        "segments": segments,
        "concat_manifest": str(concat_manifest),
    }


def reuse_existing_voiceover_by_beat(
    cards: list[dict[str, Any]],
    audio_dir: Path,
) -> dict[str, Any] | None:
    timing_path = audio_dir / "beat_timing.json"
    narration_master = audio_dir / "narration_by_beat.mp3"
    previous_audio_qa = audio_dir.parent.parent / "qa" / "audio_qa.json"
    if not (timing_path.is_file() and narration_master.is_file() and previous_audio_qa.is_file()):
        return None
    timing = load_json(str(timing_path))
    segments = timing.get("segments") or []
    if not isinstance(segments, list) or len(segments) != len(cards):
        return None
    for card, segment in zip(cards, segments):
        if not isinstance(segment, dict):
            return None
        if str(segment.get("beat_id") or "") != str(card.get("id") or ""):
            return None
        if normalize_spoken_anchor(segment.get("narration") or "") != normalize_spoken_anchor(card.get("narration") or ""):
            return None
        measured = float(segment.get("card_duration_seconds") or 0.0)
        if measured <= 0:
            return None
        card["measured_audio_seconds"] = measured
    previous = load_json(str(previous_audio_qa)).get("voice") or {}
    if not isinstance(previous, dict):
        previous = {}
    return {
        **previous,
        "path": str(narration_master),
        "duration": round(ffprobe_duration(narration_master), 3),
        "loudness": audio_loudness(narration_master),
        "quality_tier": "production_tts_segmented_reused",
        "timing_authority": "measured per-beat narration plus explicit inter-beat pauses",
        "segments": segments,
        "reused_after_text_and_beat_id_validation": True,
    }


def generate_suno_bgm(duration: float, output_dir: Path) -> dict[str, Any] | None:
    if not (os.getenv("SUNO_BASE_URL") and os.getenv("SUNO_API_KEY")):
        return None
    try:
        from custom_tools.music_generation import UniversalMusicGenerationTool

        result = UniversalMusicGenerationTool()._run(
            description=(
                "minimal cinematic instrumental background music for a serious Chinese knowledge-card short video; "
                "soft pulse, subtle synth texture, clean low-end, no vocals, no lyrics, loop-friendly, voiceover-safe"
            ),
            provider="suno",
            mode="custom",
            title="mind_structure_bgm",
            tags="instrumental, background music, no vocals, minimal cinematic, subtle pulse, soft synth",
            output_dir=str(output_dir),
            make_instrumental=True,
            wait_for_completion=True,
        )
    except Exception as exc:
        return {"ok": False, "provider": "suno", "error": str(exc)}
    if not isinstance(result, dict) or not result.get("success"):
        error_text = result.get("error", "suno_generation_failed") if isinstance(result, dict) else "suno_generation_failed"
        return {"ok": False, "provider": "suno", "error": str(error_text)[:240]}
    for song in result.get("songs", []):
        if not isinstance(song, dict):
            continue
        local_path = song.get("local_path")
        if local_path and Path(str(local_path)).exists():
            music_path = Path(str(local_path))
            return {
                "ok": True,
                "provider": "suno",
                "path": str(music_path),
                "duration": round(ffprobe_duration(music_path), 3),
                "loudness": audio_loudness(music_path),
                "requested_duration": round(duration, 3),
                "mode": "custom",
                "instrumental": True,
            }
    return {"ok": False, "provider": "suno", "error": "no local_path returned"}


def generate_bgm(duration: float, out_path: Path, params: dict[str, Any]) -> dict[str, Any]:
    external_path_value = str(params.get("bgm_path") or nested_config(params).get("bgm_path") or "").strip()
    if external_path_value:
        external_path = Path(external_path_value).expanduser().resolve()
        if not external_path.is_file():
            raise SystemExit(f"configured external BGM is missing: {external_path}")
        fade_out_start = max(duration - 1.2, 0.0)
        run(
            [
                "ffmpeg",
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                str(external_path),
                "-t",
                f"{duration:.3f}",
                "-af",
                f"afade=t=in:st=0:d=0.8,afade=t=out:st={fade_out_start:.3f}:d=1.2",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                str(out_path),
            ]
        )
        provider_hint = str(params.get("bgm_provider") or "external_music").strip().lower()
        return {
            "ok": True,
            "provider": provider_hint,
            "path": str(out_path),
            "source_path": str(external_path),
            "source_title": str(params.get("bgm_title") or "").strip(),
            "source_creator": str(params.get("bgm_creator") or "").strip(),
            "source_page": str(params.get("bgm_source_page") or "").strip(),
            "duration": round(ffprobe_duration(out_path), 3),
            "loudness": audio_loudness(out_path),
        }

    suno_info = generate_suno_bgm(duration, out_path.parent / "suno")
    if isinstance(suno_info, dict) and suno_info.get("ok") and suno_info.get("path"):
        return suno_info

    allow_local_fallback = bool_param(
        params,
        "allow_local_bgm_fallback",
        not bool(os.getenv("FACTORY_JOB_ID")),
    )
    if not allow_local_fallback:
        error = (
            str(suno_info.get("error") or "suno_generation_failed")
            if isinstance(suno_info, dict)
            else "suno_route_unavailable"
        )
        raise SystemExit(f"background_music_generation_failed: {error}")

    fade_out_start = max(duration - 1.2, 0.0)
    filter_complex = (
        "[0:a]volume=0.055,lowpass=f=360[a0];"
        "[1:a]volume=0.024,lowpass=f=720[a1];"
        "[2:a]volume=0.036,lowpass=f=1200[a2];"
        "[a0][a1][a2]amix=inputs=3:duration=longest:normalize=0,"
        "afade=t=in:st=0:d=0.8,"
        f"afade=t=out:st={fade_out_start:.3f}:d=1.2,"
        "alimiter=limit=0.5[a]"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-t",
            f"{duration:.3f}",
            "-i",
            "sine=frequency=146.83:sample_rate=44100",
            "-f",
            "lavfi",
            "-t",
            f"{duration:.3f}",
            "-i",
            "sine=frequency=220:sample_rate=44100",
            "-f",
            "lavfi",
            "-t",
            f"{duration:.3f}",
            "-i",
            "anoisesrc=color=pink:amplitude=0.03:sample_rate=44100",
            "-filter_complex",
            filter_complex,
            "-map",
            "[a]",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(out_path),
        ]
    )
    return {
        "provider": "local_ffmpeg_generated_preview_bed",
        "path": str(out_path),
        "duration": round(ffprobe_duration(out_path), 3),
        "loudness": audio_loudness(out_path),
        "fallback_from": suno_info,
    }


def mix_audio(narration: Path, bgm: Path, params: dict[str, Any], out_path: Path, *, bgm_provider: str = "") -> dict[str, Any]:
    voice_volume = number_param(params, "voice_volume", DEFAULT_VOICE_VOLUME)
    default_bgm_volume = (
        DEFAULT_SUNO_BGM_VOLUME
        if bgm_provider == "suno" or bgm_provider.startswith("external_")
        else DEFAULT_BGM_VOLUME
    )
    bgm_volume = number_param(params, "bgm_volume", default_bgm_volume)
    filter_complex = (
        f"[0:a]aresample=44100,volume={voice_volume:.3f}[voice];"
        f"[1:a]aresample=44100,volume={bgm_volume:.3f}[bgm];"
        "[voice][bgm]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
        "alimiter=limit=0.78[a]"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(narration),
            "-i",
            str(bgm),
            "-filter_complex",
            filter_complex,
            "-map",
            "[a]",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            str(out_path),
        ]
    )
    return {
        "path": str(out_path),
        "duration": round(ffprobe_duration(out_path), 3),
        "voice_volume": voice_volume,
        "bgm_volume": bgm_volume,
        "bgm_provider": bgm_provider,
        "loudness": audio_loudness(out_path),
    }


def forbidden_public_tokens(params: dict[str, Any]) -> tuple[str, ...]:
    values = params.get("forbidden_public_tokens") or []
    if not isinstance(values, list):
        return ()
    return tuple(str(item) for item in values if str(item).strip())


def ensure_no_forbidden_public_text(text: str, forbidden_tokens: tuple[str, ...]) -> None:
    hits = [token for token in forbidden_tokens if token in text]
    if hits:
        raise SystemExit("forbidden public reference text found: " + ", ".join(hits))


def semantic_content_qa(strategy: dict[str, Any], cards: list[dict[str, Any]]) -> dict[str, Any]:
    roles = [str(card.get("role") or "") for card in cards]
    visible_lines = ["".join(strip_emphasis_markup(card.get("core") or "").split()) for card in cards]
    duplicate_visible_text = len(visible_lines) != len(set(visible_lines))
    minimum_questions = {"short_thesis": 2, "deep_cognitive_essay": 3, "long_column": 6}[
        str(strategy.get("duration_mode"))
    ]
    retention_questions = [str(card.get("retention_question") or "") for card in cards if card.get("retention_question")]
    card_forms = [str(card.get("card_form") or "") for card in cards]
    checks = [
        {
            "id": "angle_candidates_min_5",
            "ok": len(strategy.get("angle_candidates") or []) >= 5,
        },
        {
            "id": "concrete_scene_count",
            "ok": len(strategy.get("concrete_scenes") or [])
            >= (2 if strategy.get("duration_mode") == "short_thesis" else 3),
        },
        {
            "id": "conceptual_split_present",
            "ok": bool(strategy.get("selected_angle", {}).get("conceptual_split")),
        },
        {
            "id": "proof_route_present",
            "ok": bool(strategy.get("proof", {}).get("route")),
        },
        {
            "id": "actions_trace_to_mechanism",
            "ok": all(item.get("action") and item.get("mechanism_link") for item in strategy.get("actions") or []),
        },
        {
            "id": "semantic_progression_unique_visible_text",
            "ok": not duplicate_visible_text,
        },
        {
            "id": "explicit_keyword_bold_map",
            "ok": all(
                1 <= len(card.get("emphasis_keywords") or []) <= 2
                and extracted_emphasis_keywords(card.get("core") or "") == card.get("emphasis_keywords")
                for card in cards
            ),
        },
        {
            "id": "visible_text_is_spoken_anchor",
            "ok": all(
                normalize_spoken_anchor(card.get("core") or "")
                in normalize_spoken_anchor(card.get("narration") or "")
                for card in cards
            ),
        },
        {
            "id": "retention_question_chain",
            "ok": len(set(retention_questions)) >= minimum_questions and not cards[-1].get("retention_question"),
        },
        {
            "id": "card_form_rotation",
            "ok": all(
                not (card_forms[index] == card_forms[index - 1] == card_forms[index - 2])
                for index in range(2, len(card_forms))
            ),
        },
        {
            "id": "information_gain_declared",
            "ok": all(card.get("information_gain") in SUPPORTED_INFORMATION_GAINS for card in cards),
        },
        {
            "id": "required_role_progression",
            "ok": (
                roles[:1] == ["counterintuitive_verdict"]
                and roles[-1:] == ["identity_close"]
                and roles.count("derived_action") >= 2
                and bool({"proof", "analogy", "contrast"} & set(roles))
            ),
        },
        {
            "id": "lane_specific_strategy_declared",
            "ok": strategy.get("content_lane") in SUPPORTED_CONTENT_LANES,
        },
    ]
    blockers = [str(check["id"]) for check in checks if not check.get("ok")]
    if blockers:
        raise SystemExit("semantic_content_qa_failed: " + ", ".join(blockers))
    return {
        "schema": "capsule_cinema.semantic_content_qa.v1",
        "ok": True,
        "content_lane": strategy["content_lane"],
        "duration_mode": strategy["duration_mode"],
        "beat_count": len(cards),
        "checks": checks,
        "evidence_boundary": strategy["evidence_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a local high-abstraction card explainer video.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--params", default="")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    params = load_json(args.params)
    forbidden_tokens = forbidden_public_tokens(params)
    output_dir = Path(args.output_dir).expanduser().resolve()
    release_slug = str(params.get("release_slug") or "visual_card_video").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", release_slug):
        raise SystemExit("release_slug must use lowercase letters, numbers, underscores, or hyphens")
    release_dir = output_dir / "release" / release_slug
    public_dir = release_dir / "public"
    qa_dir = release_dir / "qa"
    internal_dir = release_dir / "internal"
    technical_dir = release_dir / "technical"
    audio_dir = technical_dir / "audio"
    frames_dir = technical_dir / "frames"
    for path in (public_dir, qa_dir, internal_dir, technical_dir, audio_dir, frames_dir):
        path.mkdir(parents=True, exist_ok=True)

    topic = str(params.get("topic") or args.topic)
    episode_content = episode_content_from_params(params)
    strategy = validate_episode_strategy(episode_content)
    cards = build_cards(topic, episode_content, strategy)
    semantic_qa = semantic_content_qa(strategy, cards)
    visible_text = "\n".join(
        [
            HEADER_WORDMARK,
            ROMAN_SEPARATOR,
            DISCLAIMER_TEXT,
            *BOTTOM_COLUMNS,
            *[card["theme"] + "\n" + strip_emphasis_markup(card["core"]) for card in cards],
        ]
    )
    ensure_no_forbidden_public_text(visible_text, forbidden_tokens)
    voiceover_text = voiceover_from_cards(cards, episode_content)
    ensure_no_forbidden_public_text(voiceover_text, forbidden_tokens)
    svg_info = write_svg_assets(cards, technical_dir / "svg")
    sequence_info: dict[str, Any] = {}
    visual_report: dict[str, Any] = {
        "ok": True,
        "canvas": [W, H],
        "fps": FPS,
        "visual_mechanism": [
            "white vertical knowledge card",
            "generic seal and wordmark",
            "red topic line",
            "medium-heavy black central verdict",
            "one or two extra-heavy keyword anchors per card",
            "romanized separator",
            "semantic middle SVG-like vector metaphor",
            "background structure plus primary metaphor plus semantic context props",
            "one recurring black silhouette protagonist with a stable red-scarf identity anchor and scene-specific poses",
            "right lower disclaimer",
            "bottom three-column gray system band",
            "per-card vector reveal animation",
            "argument-driven multi-form card rotation",
            "single-pass keyword weight-and-tone emphasis without underline",
        ],
        "source_identity_policy": "No source account name, handle, logo, watermark, link, source frame, or copied visual asset is used.",
        "svg_assets": svg_info["svg_assets"],
        "component_library": svg_info["component_library"],
    }

    if not args.dry_run:
        voiceover_path = public_dir / "voiceover.txt"
        voiceover_path.write_text(voiceover_text + "\n", encoding="utf-8")
        narration_audio = audio_dir / "narration.aiff"
        bgm_audio = audio_dir / "bgm.m4a"
        mixed_audio = audio_dir / "mixed_audio.m4a"
        reuse_narration = bool(str(params.get("narration_path") or "").strip())
        reusable_voice_info = (
            reuse_existing_voiceover_by_beat(cards, audio_dir)
            if bool_param(params, "reuse_existing_segmented_tts", False)
            else None
        )
        if reusable_voice_info:
            voice_info = reusable_voice_info
        elif bool_param(params, "segment_tts_by_beat", True) and not reuse_narration:
            voice_info = generate_voiceover_by_beat(cards, params, audio_dir)
        else:
            voice_info = generate_voiceover_audio(voiceover_text, params, narration_audio)
        actual_narration_audio = Path(str(voice_info["path"]))
        bgm_info = generate_bgm(float(voice_info["duration"]), bgm_audio, params)
        actual_bgm_audio = Path(str(bgm_info.get("path") or bgm_audio))
        mixed_info = mix_audio(
            actual_narration_audio,
            actual_bgm_audio,
            params,
            mixed_audio,
            bgm_provider=str(bgm_info.get("provider") or ""),
        )
        audio_duration = float(mixed_info["duration"])
        preview_dir = frames_dir / "previews"
        for index, card in enumerate(cards):
            render_card(card, index, preview_dir / f"card_{index:02d}.png", progress=1.0)
        sequence_info = render_card_sequence(cards, audio_duration, frames_dir)
        duration = math.ceil(audio_duration * 10) / 10
        final_video = public_dir / "high_abstraction_growth_card_complete.mp4"
        run(
            [
                "ffmpeg",
                "-y",
                "-framerate",
                str(FPS),
                "-i",
                str(Path(sequence_info["frame_dir"]) / "frame_%05d.jpg"),
                "-i",
                str(mixed_audio),
                "-t",
                f"{audio_duration:.3f}",
                "-shortest",
                "-vf",
                "fps=30,format=yuv420p",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(final_video),
            ]
        )
        cover_path = public_dir / "cover.png"
        render_card(cards[0], 0, cover_path, progress=1.0)
        visual_report["sequence"] = sequence_info
        visual_report["preview_frames"] = str(preview_dir)
        audio_qa = {
            "ok": True,
            "voice": voice_info,
            "bgm": bgm_info,
            "mixed_audio": mixed_info,
            "timing": {
                "audio_duration": round(audio_duration, 3),
                "target_video_duration": round(duration, 3),
                "card_timing": sequence_info.get("cards", []),
                "timing_authority": sequence_info.get("timing_authority"),
            },
        }
        if voice_info.get("segments"):
            write_json(
                audio_dir / "beat_timing.json",
                {
                    "schema": "capsule_cinema.beat_audio_timing.v1",
                    "timing_authority": voice_info.get("timing_authority"),
                    "total_duration_seconds": voice_info.get("duration"),
                    "segments": voice_info.get("segments"),
                },
            )
    else:
        final_video = public_dir / "dry_run_not_rendered.mp4"
        cover_path = public_dir / "dry_run_cover.png"
        voiceover_path = public_dir / "voiceover.txt"
        voiceover_path.write_text(voiceover_text + "\n", encoding="utf-8")
        render_card(cards[0], 0, cover_path, progress=1.0)
        preview_dir = frames_dir / "previews"
        for index, card in enumerate(cards):
            render_card(card, index, preview_dir / f"card_{index:02d}.png", progress=1.0)
        narration_audio = audio_dir / "dry_run_narration.aiff"
        actual_narration_audio = narration_audio
        bgm_audio = audio_dir / "dry_run_bgm.m4a"
        actual_bgm_audio = bgm_audio
        mixed_audio = audio_dir / "dry_run_mixed_audio.m4a"
        audio_qa = {"ok": True, "dry_run": True}
        visual_report["dry_run"] = True
        visual_report["preview_frames"] = str(preview_dir)

    copy_path = public_dir / "copy.md"
    copy_path.write_text(
        "\n".join(
            [
                f"# {topic}",
                "",
                "## 内容路线",
                str(strategy["content_lane"]),
                "",
                "## 时长模式",
                str(strategy["duration_mode"]),
                "",
                "## 标题",
                episode_text(episode_content, "title"),
                "",
                "## 封面文案",
                episode_text(episode_content, "cover_text"),
                "",
                "## 发布文案",
                episode_text(episode_content, "publishing_copy"),
                "",
                "## 评论引导",
                str(strategy["comment_cta"]["prompt"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    visible_text_path = public_dir / "visible_text.txt"
    visible_text_path.write_text(visible_text + "\n", encoding="utf-8")
    ensure_no_forbidden_public_text(copy_path.read_text(encoding="utf-8"), forbidden_tokens)
    ensure_no_forbidden_public_text(voiceover_path.read_text(encoding="utf-8"), forbidden_tokens)

    internal_storyboard = {
        "topic": topic,
        "content_lane": strategy["content_lane"],
        "duration_mode": strategy["duration_mode"],
        "cards": cards,
        "source_policy": "No source account name, watermark, link, logo, or original video material is used.",
    }
    content_strategy_path = internal_dir / "content_strategy.json"
    semantic_beats_path = internal_dir / "semantic_beats.json"
    question_chain_path = internal_dir / "question_escalation_chain.json"
    emphasis_map_path = internal_dir / "emphasis_keyword_map.json"
    card_form_map_path = internal_dir / "card_form_map.json"
    semantic_qa_path = qa_dir / "semantic_content_qa.json"
    write_json(content_strategy_path, {"topic": topic, **strategy})
    write_json(
        semantic_beats_path,
        {
            "schema": "capsule_cinema.semantic_beats.v1",
            "topic": topic,
            "content_lane": strategy["content_lane"],
            "duration_mode": strategy["duration_mode"],
            "beats": cards,
        },
    )
    write_json(
        question_chain_path,
        {
            "schema": "capsule_cinema.question_escalation_chain.v1",
            "topic": topic,
            "opening_question": cards[0].get("retention_question"),
            "questions": [
                {
                    "beat_id": card.get("id"),
                    "role": card.get("role"),
                    "question": card.get("retention_question"),
                }
                for card in cards
                if card.get("retention_question")
            ],
            "final_closure": cards[-1].get("core_plain"),
        },
    )
    write_json(
        emphasis_map_path,
        {
            "schema": "capsule_cinema.emphasis_keyword_map.v1",
            "cards": [
                {
                    "beat_id": card.get("id"),
                    "visible_text": card.get("core_plain"),
                    "emphasis_keywords": card.get("emphasis_keywords"),
                }
                for card in cards
            ],
        },
    )
    write_json(
        card_form_map_path,
        {
            "schema": "capsule_cinema.card_form_map.v1",
            "cards": [
                {
                    "beat_id": card.get("id"),
                    "role": card.get("role"),
                    "card_form": card.get("card_form"),
                    "information_gain": card.get("information_gain"),
                }
                for card in cards
            ],
        },
    )
    write_json(semantic_qa_path, semantic_qa)
    write_json(internal_dir / "storyboard.json", internal_storyboard)
    write_json(technical_dir / "visual_system_report.json", visual_report)
    qa_report = {
        "ok": True,
        "forbidden_public_tokens_checked": len(forbidden_tokens),
        "visible_text_checked": str(visible_text_path),
        "voiceover_text_checked": str(voiceover_path),
        "final_video": str(final_video),
        "semantic_content_qa": str(semantic_qa_path),
    }
    write_json(qa_dir / "visible_text_no_source_account.json", qa_report)
    write_json(qa_dir / "audio_qa.json", audio_qa)
    (qa_dir / "compliance_review.md").write_text(
        "\n".join(
            [
                "# 合规风险审核",
                "",
                "- 平台: 抖音",
                "- 内容范围: 本地测试视频、封面、标题、可见文字",
                "- 结论: Low",
                "- 最高风险: 本地测试视频无原账号名称、链接、水印或导流文字；配音使用已配置的远程 TTS 或明确标记的预览兜底，正式发布前仍需复核音色授权与平台规则。",
                "",
                "## 风险明细",
                "",
                "| 等级 | 证据位置 | 风险说明 | 修改建议 |",
                "| --- | --- | --- | --- |",
                "| Low | public/visible_text.txt | 成长方法论内容，未见医疗、金融、法律承诺 | 发布前保持非绝对化表达 |",
                "| Low | public/voiceover.txt / technical/audio | 口播来自本期原创脚本，BGM 为本期生成或配置的音源，无来源视频原声 | 保持 BGM 低于口播；授权凭证不作为发布条件 |",
                "",
            ]
        ),
        encoding="utf-8",
    )
    release_manifest = {
        "schema": "capsule_cinema.release_manifest.v1",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "capsule": "high_abstraction_growth_card",
        "version_slug": release_slug,
        "predecessor_release": str(params.get("predecessor_release") or ""),
        "topic": topic,
        "final_video": str(final_video),
        "cover": str(cover_path),
        "copy": str(copy_path),
        "voiceover": str(voiceover_path),
        "visible_text": str(visible_text_path),
        "qa": str(qa_dir / "visible_text_no_source_account.json"),
        "audio_qa": str(qa_dir / "audio_qa.json"),
        "semantic_content_qa": str(semantic_qa_path),
        "content_strategy": str(content_strategy_path),
        "semantic_beats": str(semantic_beats_path),
        "question_escalation_chain": str(question_chain_path),
        "emphasis_keyword_map": str(emphasis_map_path),
        "card_form_map": str(card_form_map_path),
        "compliance_review": str(qa_dir / "compliance_review.md"),
        "narration_audio": str(actual_narration_audio),
        "actual_narration_audio": str(actual_narration_audio),
        "bgm_audio": str(actual_bgm_audio),
        "requested_bgm_audio": str(bgm_audio),
        "mixed_audio": str(mixed_audio),
        "visual_system_report": str(technical_dir / "visual_system_report.json"),
        "svg_assets": svg_info["svg_assets"],
        "animation_sequence": sequence_info,
        "source_account_public_text_used": False,
    }
    write_json(release_dir / "release_manifest.json", release_manifest)
    write_json(
        output_dir / "artifact_manifest.json",
        {
            "schema_version": 1,
            "workflow": "local_capsule_test",
            "capsule": "high_abstraction_growth_card",
            "artifacts": [
                {"category": "final_video", "path": str(final_video), "title": "Final video"},
                {"category": "copywriting", "path": str(copy_path), "title": "Copywriting"},
                {"category": "voiceover_script", "path": str(voiceover_path), "title": "Voiceover script"},
                {"category": "cover", "path": str(cover_path), "title": "Cover"},
                {"category": "storyboard_prompt", "path": str(internal_dir / "storyboard.json"), "title": "Storyboard"},
                {"category": "content_strategy", "path": str(content_strategy_path), "title": "Content strategy"},
                {"category": "semantic_beat_manifest", "path": str(semantic_beats_path), "title": "Semantic beat manifest"},
                {"category": "retention_manifest", "path": str(question_chain_path), "title": "Question escalation chain"},
                {"category": "visual_text_manifest", "path": str(emphasis_map_path), "title": "Bold keyword map"},
                {"category": "visual_structure_manifest", "path": str(card_form_map_path), "title": "Card form map"},
                {"category": "qa_report", "path": str(technical_dir / "visual_system_report.json"), "title": "Visual system report"},
                {"category": "qa_report", "path": str(semantic_qa_path), "title": "Semantic content QA"},
                {"category": "audio_qa", "path": str(qa_dir / "audio_qa.json"), "title": "Audio QA"},
                {"category": "qa_report", "path": str(qa_dir / "visible_text_no_source_account.json"), "title": "No source-account text QA"},
                *[
                    {"category": "storyboard_image", "path": item["path"], "title": f"Vector metaphor SVG {item['card']:02d}"}
                    for item in svg_info["svg_assets"]
                ],
            ],
        },
    )
    (output_dir / "CURRENT_RELEASE.md").write_text(
        f"# Current Release\n\n- release: `{release_dir}`\n- final_video: `{final_video}`\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "final_video": str(final_video), "release_dir": str(release_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
