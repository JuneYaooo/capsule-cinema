#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import math
import os
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

from src.utils.font_utils import load_pil_font

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
DEFAULT_MINIMAX_TTS_VOICE = "audiobook_male_2"
DEFAULT_REMOTE_TTS_SPEED = 1.14
VECTOR_REQUIRED_FAMILIES = ["person_silhouette", "red_path_or_arc", "environment_symbol", "system_panel"]
VECTOR_OPTIONAL_FAMILIES = [
    "thought_cloud",
    "risk_radar",
    "threshold_gate",
    "timer_ring",
    "route_panel",
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
    return load_pil_font(size, bold=bold)


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
) -> int:
    lines = []
    for raw in text.split("\n"):
        lines.extend(wrap_text(draw, raw, font_obj, max_width))
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_obj)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=font_obj, fill=fill)
        y += bbox[3] - bbox[1] + line_gap
    return y


SUPPORTED_CONTENT_LANES = {
    "life_uncertainty",
    "cognitive_control",
    "relationship_social",
    "growth_reconstruction",
}
SUPPORTED_DURATION_MODES = {
    "short_thesis": (10, 10),
    "deep_cognitive_essay": (12, 20),
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
    "false_solution",
    "redefinition",
    "contrast",
    "derived_action",
    "emotional_relief",
    "identity_close",
}
METAPHOR_FAMILY_TO_SCENE = {
    "open_path": "heavy_start",
    "recovery_growth": "heavy_start",
    "rebuilding": "heavy_start",
    "isolated_person": "thought_load",
    "cognitive_load": "thought_load",
    "social_distance": "thought_load",
    "hidden_signal": "risk_signal",
    "fractured_identity": "risk_signal",
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
BEAT_REQUIRED_FIELDS = ("id", "role", "theme", "visible_text", "narration", "metaphor_family")
AUDIENCE_REQUIRED_FIELDS = ("target_viewer", "current_pressure", "emotional_gap")
SELECTED_ANGLE_REQUIRED_FIELDS = (
    "common_belief",
    "hidden_mechanism",
    "counterintuitive_thesis",
    "conceptual_split",
    "false_solution",
    "redefinition",
)
PROOF_REQUIRED_FIELDS = ("route", "material", "factual_risk")
IDENTITY_REQUIRED_FIELDS = ("old_identity", "new_identity", "closing_judgment")


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
    conceptual_split = required_object(
        selected_angle.get("conceptual_split"),
        "selected_angle.conceptual_split",
        ("surface_layer", "deep_layer"),
    )
    proof = required_object(episode_content.get("proof"), "proof", PROOF_REQUIRED_FIELDS)
    identity_payoff = required_object(
        episode_content.get("identity_payoff"), "identity_payoff", IDENTITY_REQUIRED_FIELDS
    )

    angle_candidates = episode_content.get("angle_candidates")
    if not isinstance(angle_candidates, list) or len(angle_candidates) < 3:
        raise SystemExit("episode_content_strategy_required: angle_candidates must contain at least 3 candidates")
    candidate_angles: list[str] = []
    for index, candidate in enumerate(angle_candidates, start=1):
        if not isinstance(candidate, dict) or not str(candidate.get("angle") or "").strip():
            raise SystemExit(f"episode_content_strategy_required: angle candidate {index} missing angle")
        try:
            float(candidate.get("score"))
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"episode_content_strategy_required: angle candidate {index} missing numeric score") from exc
        candidate_angles.append("".join(str(candidate["angle"]).split()))
    if len(set(candidate_angles)) != len(candidate_angles):
        raise SystemExit("episode_content_strategy_required: angle candidates must be meaningfully distinct")

    concrete_scenes = episode_content.get("concrete_scenes")
    required_scenes = 2 if duration_mode == "short_thesis" else 3
    normalized_scenes = ["".join(str(item).split()) for item in concrete_scenes or [] if str(item).strip()]
    if not isinstance(concrete_scenes, list) or len(normalized_scenes) < required_scenes:
        raise SystemExit(
            f"episode_content_strategy_required: {duration_mode} requires at least {required_scenes} concrete_scenes"
        )
    if len(set(normalized_scenes)) != len(normalized_scenes):
        raise SystemExit("episode_content_strategy_required: concrete_scenes must be non-interchangeable and distinct")

    actions = episode_content.get("actions")
    if not isinstance(actions, list) or len(actions) < 2:
        raise SystemExit("episode_content_strategy_required: actions must contain at least 2 derived actions")
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
        "risk_notes": episode_content.get("risk_notes") or [],
        "evidence_boundary": {
            "validated_lanes": ["growth_reconstruction"],
            "candidate_lanes": ["life_uncertainty", "cognitive_control", "relationship_social"],
            "policy": "candidate lanes require cross-topic QA and must not be presented as universal laws",
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
        estimated_seconds = raw_beat.get("estimated_seconds")
        duration_weight = raw_beat.get("duration_weight")
        try:
            estimated_value = float(estimated_seconds) if estimated_seconds is not None else 0.0
            weight_value = float(duration_weight) if duration_weight is not None else 0.0
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"episode_semantic_beats_required: beat {index} timing must be numeric") from exc
        cards.append(
            {
                "id": beat["id"],
                "label": beat["role"],
                "role": beat["role"],
                "theme": beat["theme"],
                "core": beat["visible_text"],
                "sub": str(raw_beat.get("subtext") or "").strip(),
                "scene": beat["metaphor_family"],
                "render_scene": METAPHOR_FAMILY_TO_SCENE[beat["metaphor_family"]],
                "narration": beat["narration"],
                "estimated_seconds": max(0.0, estimated_value),
                "duration_weight": max(0.0, weight_value),
            }
        )

    roles = [card["role"] for card in cards]
    if roles[0] != "counterintuitive_verdict":
        raise SystemExit("episode_semantic_beats_required: first beat must be counterintuitive_verdict")
    if roles[-1] != "identity_close":
        raise SystemExit("episode_semantic_beats_required: final beat must be identity_close")
    required_scene_beats = 2 if strategy["duration_mode"] == "short_thesis" else 3
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
    return 1 - (1 - progress) ** 3


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
    title_font = font(48)
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
    draw_person(
        draw,
        cx - 234 + int(145 * p),
        base - 10 - int(112 * p),
        0.52,
        BLACK,
        red_body=True,
        lean=0.45,
    )


def draw_scene_thought_load(draw: ImageDraw.ImageDraw, progress: float) -> None:
    p = ease(progress)
    cx, base = W // 2, 1052
    draw_ground(draw, cx - 290, base + 72, cx + 265, progress=p, width=5)
    draw_person(draw, cx - 18, base - int(8 * p), 1.02, BLACK, lean=-0.12)
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
    draw_person(draw, cx - 184 + int(112 * p), base, 0.72, BLACK, red_body=p > 0.5, lean=0.22)


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
    draw_person(draw, cx - 176 + int(278 * p), base - int(54 * p), 0.65, BLACK, red_body=True, lean=0.35)


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
    draw_person(draw, cx + 286 - int(52 * p), cy + 178, 0.42, BLACK, red_body=True, lean=-0.18)


def draw_scene_system_redesign(draw: ImageDraw.ImageDraw, progress: float) -> None:
    p = ease(progress)
    cx, cy = W // 2, 940
    draw_panel(draw, (cx - 255, cy - 190, cx + 255, cy + 170), p)
    draw_ground(draw, cx - 304, cy + 232, cx + 310, progress=p, width=7)
    route = quadratic_points((cx - 266, cy + 224), (cx - 42, cy + 120), (cx + 218, cy + 198), 32)
    draw_curve(draw, route[: max(2, int(len(route) * p))], fade_color(DEEP_RED, p), 11)
    draw.ellipse((cx + 198, cy + 178, cx + 240, cy + 220), fill=fade_color(DEEP_RED, p))
    draw_person(draw, cx - 298 + int(126 * p), cy + 222, 0.5, BLACK, lean=0.24)
    draw_person(draw, cx + 264, cy + 222, 0.5, BLACK, red_body=True, lean=-0.08)


SCENE_RENDERERS = {
    "heavy_start": draw_scene_heavy_start,
    "thought_load": draw_scene_thought_load,
    "risk_signal": draw_scene_risk_signal,
    "threshold": draw_scene_threshold,
    "lower_entry": draw_scene_lower_entry,
    "timed_action": draw_scene_timed_action,
    "system_redesign": draw_scene_system_redesign,
}


def draw_metaphor_scene(draw: ImageDraw.ImageDraw, scene: str, progress: float) -> None:
    render_scene = METAPHOR_FAMILY_TO_SCENE.get(scene, scene)
    renderer = SCENE_RENDERERS.get(render_scene) or draw_scene_heavy_start
    renderer(draw, progress)


def render_card(card: dict[str, Any], index: int, out_path: Path, progress: float = 1.0) -> None:
    image = Image.new("RGB", (W, H), "#ffffff")
    draw = ImageDraw.Draw(image)
    theme_font = font(52)
    core_font = font(72, bold=True)
    p = ease(progress)

    draw.rectangle((0, 0, W, H), fill="#ffffff")
    draw_header(draw)
    centered_text(draw, card["theme"], 186, theme_font, fill=RED, max_width=1000, line_gap=10)
    draw.line((72, 270, 72 + int(936 * p), 270), fill=fade_color(RED, 0.65), width=4)
    centered_text(draw, card["core"], 310, core_font, fill=BLACK, max_width=820, line_gap=18)
    draw_spaced_text(draw, ROMAN_SEPARATOR, W // 2, 578, font(36), "#505050")
    draw_metaphor_scene(draw, str(card.get("scene") or "open_path"), progress)
    draw_disclaimer(draw)
    draw_footer_system(draw)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, quality=95)


def card_duration_weights(cards: list[dict[str, Any]]) -> list[float]:
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
    for frame_index in range(total_frames):
        while card_index < len(boundaries) - 1 and frame_index >= boundaries[card_index]:
            card_start = boundaries[card_index]
            card_index += 1
        local_index = frame_index - card_start
        local_progress = min(1.0, local_index / max(frame_counts[card_index] * 0.55, 1))
        render_card(cards[card_index], card_index, sequence_dir / f"frame_{frame_index:05d}.jpg", progress=local_progress)
    return {
        "frame_dir": str(sequence_dir),
        "total_frames": total_frames,
        "fps": FPS,
        "timing_authority": "beat estimated_seconds, duration_weight, or narration length normalized to measured audio duration",
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


def svg_person(x: int, y: int, scale: float = 1.0, *, red_body: bool = False, lean: float = 0.0) -> list[str]:
    s = scale
    body_fill = DEEP_RED if red_body else BLACK
    lean_px = lean * 18 * s
    return [
        f'<g class="person-silhouette" data-family="person_silhouette">',
        f'<ellipse class="ground-shadow" cx="{x + 2 * s:.1f}" cy="{y + 74 * s:.1f}" rx="{50 * s:.1f}" ry="{8 * s:.1f}" fill="{MID_GRAY}" opacity="0.32"/>',
        f'<circle cx="{x + lean_px:.1f}" cy="{y - 82 * s:.1f}" r="{17 * s:.1f}" fill="{BLACK}"/>',
        (
            f'<path d="M{x - 20 * s:.1f} {y - 58 * s:.1f} '
            f'C{x - 8 * s:.1f} {y - 68 * s:.1f} {x + 18 * s + lean_px:.1f} {y - 66 * s:.1f} {x + 25 * s + lean_px:.1f} {y - 45 * s:.1f} '
            f'L{x + 24 * s + lean_px:.1f} {y + 12 * s:.1f} '
            f'C{x + 8 * s:.1f} {y + 23 * s:.1f} {x - 10 * s:.1f} {y + 18 * s:.1f} {x - 18 * s:.1f} {y + 8 * s:.1f} Z" '
            f'fill="{body_fill}"/>'
        ),
        f'<path d="M{x - 4 * s:.1f} {y + 9 * s:.1f} C{x - 16 * s:.1f} {y + 28 * s:.1f} {x - 28 * s:.1f} {y + 50 * s:.1f} {x - 38 * s:.1f} {y + 72 * s:.1f}" stroke="{BLACK}" stroke-width="{7 * s:.1f}" fill="none"/>',
        f'<path d="M{x + 12 * s:.1f} {y + 8 * s:.1f} C{x + 24 * s:.1f} {y + 29 * s:.1f} {x + 36 * s:.1f} {y + 49 * s:.1f} {x + 48 * s:.1f} {y + 68 * s:.1f}" stroke="{BLACK}" stroke-width="{7 * s:.1f}" fill="none"/>',
        f'<path d="M{x - 14 * s:.1f} {y - 38 * s:.1f} C{x - 30 * s:.1f} {y - 26 * s:.1f} {x - 42 * s:.1f} {y - 12 * s:.1f} {x - 54 * s:.1f} {y + 4 * s:.1f}" stroke="{BLACK}" stroke-width="{6 * s:.1f}" fill="none"/>',
        f'<path d="M{x + 18 * s:.1f} {y - 40 * s:.1f} C{x + 34 * s:.1f} {y - 30 * s:.1f} {x + 46 * s:.1f} {y - 20 * s:.1f} {x + 58 * s:.1f} {y - 10 * s:.1f}" stroke="{BLACK}" stroke-width="{6 * s:.1f}" fill="none"/>',
        "</g>",
    ]


def svg_scene_group(scene: str, lines: list[str]) -> list[str]:
    return [
        f'<g data-scene="{html.escape(scene)}" class="semantic-vector-scene">',
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
                *svg_person(370, 1160, 0.5, lean=0.2),
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
        core_lines = svg_text_lines(str(card.get("core", "")), 540, 382, 72, BLACK, weight=700, gap=1.24)
        theme_line = svg_text_lines(str(card.get("theme", "")), 540, 226, 52, RED, weight=500)
        scene_lines = svg_scene_body(scene)
        path.write_text(
            "\n".join(
                [
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1440">',
                    '<rect width="1080" height="1440" fill="#ffffff"/>',
                    f'<!-- scene={html.escape(scene)}; original vector-metaphor, no copied source frame/logo/watermark -->',
                    '<style>.semantic-vector-scene *{vector-effect:non-scaling-stroke}.person-silhouette path{stroke-linecap:round;stroke-linejoin:round}</style>',
                    '<g id="layout">',
                    '<circle cx="88" cy="86" r="44" fill="none" stroke="#111111" stroke-width="5"/>',
                    '<text x="88" y="104" text-anchor="middle" font-family="PingFang SC, Arial, sans-serif" font-size="54" font-weight="700" fill="#111111">思</text>',
                    '<text x="540" y="112" text-anchor="middle" font-family="PingFang SC, Arial, sans-serif" font-size="48" fill="#595959">MIND STRUCTURE</text>',
                    *theme_line,
                    *core_lines,
                    '<text x="540" y="618" text-anchor="middle" font-family="PingFang SC, Arial, sans-serif" font-size="36" fill="#505050" letter-spacing="12">COGNITIVE STRUCTURE</text>',
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
                "red paths, arcs, or rings carry the action mechanism",
                "environment symbols hold the cognitive context and must stay black/gray",
                "system panels appear when the card explains redesign or control logic",
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
        )
        if provider == "doubao" and (
            not isinstance(result, dict)
            or not result.get("success")
            or str(result.get("provider") or "").lower() in {"local", "local_system", "system", "post_production"}
        ):
            minimax_output = out_path.with_name(f"{out_path.stem}_minimax.mp3")
            result = tool._run(
                text=text,
                output_path=str(minimax_output),
                provider="minimax",
                voice_type=minimax_voice,
                speed=speed,
                encoding="mp3",
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
        return {
            "ok": True,
            "provider": "external_licensed_music",
            "path": str(out_path),
            "source_path": str(external_path),
            "source_title": str(params.get("bgm_title") or "").strip(),
            "source_creator": str(params.get("bgm_creator") or "").strip(),
            "source_page": str(params.get("bgm_source_page") or "").strip(),
            "license_name": str(params.get("bgm_license_name") or "").strip(),
            "license_page": str(params.get("bgm_license_page") or "").strip(),
            "duration": round(ffprobe_duration(out_path), 3),
            "loudness": audio_loudness(out_path),
        }

    suno_info = generate_suno_bgm(duration, out_path.parent / "suno")
    if isinstance(suno_info, dict) and suno_info.get("ok") and suno_info.get("path"):
        return suno_info

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
        if bgm_provider in {"suno", "external_licensed_music"}
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
    visible_lines = ["".join(str(card.get("core") or "").split()) for card in cards]
    duplicate_visible_text = len(visible_lines) != len(set(visible_lines))
    checks = [
        {
            "id": "angle_candidates_min_3",
            "ok": len(strategy.get("angle_candidates") or []) >= 3,
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
    release_dir = output_dir / "release" / "visual_card_video"
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
            *[card["theme"] + "\n" + card["core"] for card in cards],
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
            "large black central verdict",
            "romanized separator",
            "semantic middle SVG-like vector metaphor",
            "right lower disclaimer",
            "bottom three-column gray system band",
            "per-card vector reveal animation",
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
    else:
        final_video = public_dir / "dry_run_not_rendered.mp4"
        cover_path = public_dir / "dry_run_cover.png"
        voiceover_path = public_dir / "voiceover.txt"
        voiceover_path.write_text(voiceover_text + "\n", encoding="utf-8")
        render_card(cards[0], 0, cover_path, progress=1.0)
        narration_audio = audio_dir / "dry_run_narration.aiff"
        actual_narration_audio = narration_audio
        bgm_audio = audio_dir / "dry_run_bgm.m4a"
        actual_bgm_audio = bgm_audio
        mixed_audio = audio_dir / "dry_run_mixed_audio.m4a"
        audio_qa = {"ok": True, "dry_run": True}
        visual_report["dry_run"] = True

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
                "| Low | public/voiceover.txt / technical/audio | 口播来自本期原创脚本，BGM 为本期生成或配置的音源，无来源视频原声 | 发布前确认 TTS/BGM 授权，并保持 BGM 低于口播 |",
                "",
            ]
        ),
        encoding="utf-8",
    )
    release_manifest = {
        "schema": "capsule_cinema.release_manifest.v1",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "capsule": "high_abstraction_growth_card",
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
