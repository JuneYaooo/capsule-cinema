#!/usr/bin/env python3
"""Render a source-grounded GitHub/repo showcase profile into a safe 6:7 video.

This is a deterministic local renderer for capsule-driven repo showcase runs.
It expects the agent to do the project-specific judgment first, then pass a
small JSON profile with titles, scene cards, source image paths, and silent card copy.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


W, H = 1080, 1260
SAFE_TOP = 30
SAFE_BOTTOM = 30
CONTENT_BOTTOM = H - SAFE_BOTTOM
TOP_TAG_Y = 25
MIDDLE_PANEL_BOX = (68, 270, 1012, 765)
MIDDLE_TITLE_Y = 286
MIDDLE_TITLE_Y_WITH_VALUE = 280
MIDDLE_CONTENT_START = 329
MIDDLE_CONTENT_START_WITH_VALUE = 303
MIDDLE_CONTENT_BOTTOM = 735
BOTTOM_BOX_DEFAULTS = {
    True: (790, 1215),
    False: (805, 1205),
}
BACKGROUND_COLOR = "#FFFDF8"
SURFACE_COLOR = "#FFFFFF"
CARD_COLOR = "#FFF1E5"
SHADOW_COLOR = "#F2D5C2"
TITLE_COLOR = "#2B1A12"
BODY_COLOR = "#493228"
MUTED_COLOR = "#806252"
DEFAULT_ACCENT = "#F26B2B"
FONT_REG_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]
FONT_BOLD_CANDIDATES = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for candidate in FONT_BOLD_CANDIDATES if bold else FONT_REG_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default(size=size)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def multiline_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    fnt: ImageFont.FreeTypeFont,
    *,
    line_gap: int = 0,
) -> tuple[int, int]:
    lines = str(text).split("\n") or [""]
    widths: list[int] = []
    heights: list[int] = []
    for line in lines:
        tw, th = text_size(draw, line, fnt)
        widths.append(tw)
        heights.append(th)
    return max(widths or [0]), sum(heights) + max(0, len(lines) - 1) * line_gap


def fit_font_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    start: int,
    minimum: int,
    max_w: int,
    max_h: int | None = None,
    bold: bool = False,
    line_gap: int = 0,
) -> ImageFont.ImageFont:
    size = start
    while size > minimum:
        candidate = font(size, bold)
        tw, th = multiline_size(draw, text, candidate, line_gap=line_gap)
        if tw <= max_w and (max_h is None or th <= max_h):
            return candidate
        size -= 2
    return font(minimum, bold)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    for raw in str(text).split("\n"):
        current = ""
        for ch in raw:
            candidate = current + ch
            if text_size(draw, candidate, fnt)[0] <= max_w or not current:
                current = candidate
            else:
                lines.append(current)
                current = ch
        if current:
            lines.append(current)
    return lines


def strip_emphasis_markup(text: Any) -> str:
    return str(text).replace("**", "")


def emphasis_segments(text: Any) -> list[tuple[str, bool]]:
    parts = str(text).split("**")
    return [(part, idx % 2 == 1) for idx, part in enumerate(parts) if part]


def rich_line_size(
    draw: ImageDraw.ImageDraw,
    line: Any,
    size: int,
    *,
    base_bold: bool = False,
) -> tuple[int, int]:
    normal_f = font(size, base_bold)
    bold_f = font(size, True)
    width = 0
    height = 0
    for segment, highlighted in emphasis_segments(line):
        fnt = bold_f if highlighted or base_bold else normal_f
        tw, th = text_size(draw, segment, fnt)
        width += tw
        height = max(height, th)
    return width, height


def fit_rich_font_size(
    draw: ImageDraw.ImageDraw,
    text: Any,
    *,
    start: int,
    minimum: int,
    max_w: int,
    max_h: int | None = None,
    base_bold: bool = False,
    line_gap: int = 0,
) -> int:
    size = start
    lines = str(text).split("\n") or [""]
    while size > minimum:
        widths: list[int] = []
        heights: list[int] = []
        for line in lines:
            tw, th = rich_line_size(draw, line, size, base_bold=base_bold)
            widths.append(tw)
            heights.append(th)
        total_h = sum(heights) + max(0, len(lines) - 1) * line_gap
        if max(widths or [0]) <= max_w and (max_h is None or total_h <= max_h):
            return size
        size -= 2
    return minimum


def rich_line_height(
    draw: ImageDraw.ImageDraw,
    line: Any,
    size: int,
    *,
    base_bold: bool = False,
) -> int:
    _, height = rich_line_size(draw, line, size, base_bold=base_bold)
    return height


def wrap_rich_line_to_width(
    draw: ImageDraw.ImageDraw,
    line: Any,
    *,
    size: int,
    max_w: int,
    base_bold: bool = False,
) -> list[str]:
    text = str(line)
    if rich_line_size(draw, text, size, base_bold=base_bold)[0] <= max_w:
        return [text]

    wrapped: list[str] = []
    current = ""
    for ch in text:
        candidate = current + ch
        if current and rich_line_size(draw, candidate, size, base_bold=base_bold)[0] > max_w:
            wrapped.append(current)
            current = ch
        else:
            current = candidate
    if current:
        wrapped.append(current)
    return wrapped or [text]


def prepare_bottom_lines_for_layout(
    draw: ImageDraw.ImageDraw,
    profile: dict[str, Any],
    scene: dict[str, Any],
    lines: list[Any],
) -> list[str]:
    line_count = len(lines)
    dense = bool(scene.get("dense_bottom")) or line_count >= 4
    typography = bottom_body_typography(profile, scene, line_count=line_count, dense=dense)
    wrap_size = int(scene.get("bottom_wrap_font_size", profile.get("bottom_wrap_font_size", typography["body_size_min"])))
    max_w = int(profile.get("bottom_text_max_w", 870))
    base_bold = bool(scene.get("bottom_bold_lines", False))
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(wrap_rich_line_to_width(draw, line, size=wrap_size, max_w=max_w, base_bold=base_bold))
    return wrapped


def bottom_body_layout(
    draw: ImageDraw.ImageDraw,
    lines: list[Any],
    *,
    start_size: int,
    minimum: int,
    max_w: int,
    body_top: int,
    body_bottom: int,
    line_step_hint: int,
    line_step_max: int,
    base_bold: bool = False,
) -> tuple[int, int, int]:
    if not lines:
        return start_size, line_step_hint, body_top

    available_h = max(1, body_bottom - body_top)
    for size in range(start_size, minimum - 1, -2):
        metrics = [rich_line_size(draw, line, size, base_bold=base_bold) for line in lines]
        if max((width for width, _ in metrics), default=0) > max_w:
            continue
        max_line_h = max((height for _, height in metrics), default=size)
        min_step = max(max_line_h + 8, int(size * 1.05))
        if len(lines) == 1:
            y = body_top + max(0, int((available_h - max_line_h) / 2))
            return size, line_step_hint, y

        fill_step = int((available_h - max_line_h) / max(1, len(lines) - 1))
        if fill_step < min_step:
            continue
        step = min(max(fill_step, line_step_hint, min_step), line_step_max)
        total_h = max_line_h + step * (len(lines) - 1)
        y = body_top + max(0, int((available_h - total_h) / 2))
        return size, step, y

    fallback_size = minimum
    fallback_h = max(rich_line_height(draw, line, fallback_size, base_bold=base_bold) for line in lines)
    fallback_step = max(fallback_h + 6, min(line_step_hint, line_step_max))
    total_h = fallback_h + fallback_step * max(0, len(lines) - 1)
    y = body_top + max(0, int((available_h - total_h) / 2))
    return fallback_size, fallback_step, y


def bottom_body_typography(
    profile: dict[str, Any],
    scene: dict[str, Any],
    *,
    line_count: int,
    dense: bool,
) -> dict[str, int]:
    presets = {
        1: {"body_size": 52, "body_size_min": 38, "line_step": 68, "line_step_max": 104},
        2: {"body_size": 50, "body_size_min": 36, "line_step": 68, "line_step_max": 104},
        3: {"body_size": 46, "body_size_min": 34, "line_step": 64, "line_step_max": 98},
        4: {"body_size": 40, "body_size_min": 32, "line_step": 56, "line_step_max": 76},
        5: {"body_size": 36, "body_size_min": 30, "line_step": 48, "line_step_max": 58},
    }
    default = presets.get(max(1, min(line_count, 5)), presets[5])
    if not dense and line_count <= 3:
        default = {**default, "body_size": max(default["body_size"], 44)}

    return {
        "body_size": int(scene.get("bottom_font_size", profile.get("bottom_font_size", default["body_size"]))),
        "body_size_min": int(scene.get("bottom_font_size_min", profile.get("bottom_font_size_min", default["body_size_min"]))),
        "line_step": int(scene.get("bottom_line_step", profile.get("bottom_line_step", default["line_step"]))),
        "line_step_max": int(scene.get("bottom_line_step_max", profile.get("bottom_line_step_max", default["line_step_max"]))),
    }


def draw_rich_centered(
    draw: ImageDraw.ImageDraw,
    text: Any,
    y: int,
    size: int,
    fill: str,
    highlight_fill: str,
    *,
    base_bold: bool = False,
    line_gap: int = 0,
    canvas_w: int = W,
) -> int:
    yy = y
    for line in str(text).split("\n"):
        tw, th = rich_line_size(draw, line, size, base_bold=base_bold)
        xx = (canvas_w - tw) / 2
        for segment, highlighted in emphasis_segments(line):
            fnt = font(size, highlighted or base_bold)
            segment_fill = highlight_fill if highlighted else fill
            draw.text((xx, yy), segment, font=fnt, fill=segment_fill)
            seg_w, _ = text_size(draw, segment, fnt)
            xx += seg_w
        yy += th + line_gap
    return yy


def draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    fnt: ImageFont.FreeTypeFont,
    fill: str,
    *,
    line_gap: int = 0,
    stroke_width: int = 0,
    stroke_fill: str = "#000000",
    canvas_w: int = W,
) -> int:
    yy = y
    for line in str(text).split("\n"):
        tw, th = text_size(draw, line, fnt)
        draw.text(
            ((canvas_w - tw) / 2, yy),
            line,
            font=fnt,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        yy += th + line_gap
    return yy


def draw_centered_in_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    fnt: ImageFont.FreeTypeFont,
    fill: str,
    *,
    line_gap: int = 0,
) -> int:
    x1, y1, x2, _ = box
    yy = y1
    for line in str(text).split("\n"):
        tw, th = text_size(draw, line, fnt)
        draw.text((x1 + (x2 - x1 - tw) / 2, yy), line, font=fnt, fill=fill)
        yy += th + line_gap
    return yy


def rounded(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: str | tuple[int, int, int, int] | None,
    outline: str | tuple[int, int, int, int] | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


@lru_cache(maxsize=16)
def _make_bg_cached(accent: str, show_safe_bands: bool) -> Image.Image:
    bg = Image.new("RGBA", (W, H), BACKGROUND_COLOR)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    try:
        rgb = tuple(int(accent[i : i + 2], 16) for i in (1, 3, 5))
    except Exception:
        rgb = (242, 107, 43)
    gd.ellipse((120, 20, 960, 600), fill=rgb + (22,))
    gd.ellipse((650, 360, 1280, 920), fill=(255, 170, 92, 18))
    gd.ellipse((-220, 760, 440, 1390), fill=(255, 210, 170, 22))
    bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(90)))
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    # Safe zones constrain meaningful content only. The background treatment is
    # continuous across the full 6:7 canvas so the top and bottom never become
    # visually separate blank bands.
    grid_top = 0
    grid_bottom = H
    for y in range(grid_top, grid_bottom, 64):
        gd.line((0, y, W, y), fill=(242, 107, 43, 54), width=1)
    for x in range(0, W, 86):
        gd.line((x, grid_top, x, grid_bottom), fill=(242, 107, 43, 44), width=1)
    for x in range(-260, W, 110):
        gd.line((x, grid_top, x + 420, grid_bottom), fill=(242, 107, 43, 34), width=1)
    bg.alpha_composite(grid)
    return bg


def make_bg(accent: str, *, show_safe_bands: bool = False) -> Image.Image:
    """Return an isolated frame background while reusing expensive glow/grid work."""
    return _make_bg_cached(accent, show_safe_bands).copy()


def fit_image(src: Image.Image, box: tuple[int, int, int, int], mode: str = "contain") -> Image.Image:
    bw = box[2] - box[0]
    bh = box[3] - box[1]
    im = ImageOps.exif_transpose(src.convert("RGB"))
    if mode == "cover":
        scale = max(bw / im.width, bh / im.height)
    elif mode == "cover_width":
        scale = bw / im.width
        if im.height * scale < bh:
            scale = bh / im.height
    elif mode == "cover_height":
        scale = bh / im.height
        if im.width * scale < bw:
            scale = bw / im.width
    else:
        scale = min(bw / im.width, bh / im.height)
    return im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.Resampling.LANCZOS)


def motion_plan_for_source(
    source_size: tuple[int, int],
    box: tuple[int, int, int, int],
    *,
    requested_direction: str | None = None,
    requested_amount: float | None = None,
    requested_focus: str | None = None,
    content_features: list[str] | None = None,
) -> dict[str, Any]:
    src_w, src_h = max(1, int(source_size[0])), max(1, int(source_size[1]))
    box_w = max(1, box[2] - box[0])
    box_h = max(1, box[3] - box[1])
    source_ratio = src_w / src_h
    box_ratio = box_w / box_h
    aspect_gap = max(source_ratio / box_ratio, box_ratio / source_ratio)

    if aspect_gap >= 1.8:
        if source_ratio < box_ratio:
            return {
                "fit_mode": "scroll_long_axis",
                "scale_mode": "fit_width",
                "scroll_axis": "y",
                "motion_direction": "scroll_down",
                "motion_amount": 0.0,
                "motion_focus": "center",
            }
        return {
            "fit_mode": "scroll_long_axis",
            "scale_mode": "fit_height",
            "scroll_axis": "x",
            "motion_direction": "scroll_right",
            "motion_amount": 0.0,
            "motion_focus": "center",
        }

    has_explicit_direction = bool(requested_direction and requested_direction not in {"auto", "none"})
    direction = requested_direction if has_explicit_direction else "slide_in_right"
    zoom_aliases = {"zoom_in", "zoom_out", "scale_in", "center_zoom", "local_zoom", "focus_zoom"}
    feature_text = " ".join(str(item).lower() for item in (content_features or []))
    detail_terms = [
        "chart",
        "graph",
        "dashboard",
        "ui",
        "table",
        "thumbnail",
        "deck",
        "detail",
        "dense",
        "diagram",
        "flow",
        "图表",
        "数据",
        "看板",
        "面板",
        "界面",
        "缩略",
        "细节",
        "小字",
        "表格",
        "机制",
        "流程",
    ]
    should_zoom_for_detail = any(term in feature_text for term in detail_terms)
    if direction in zoom_aliases or should_zoom_for_detail:
        if direction in {"center_zoom", "local_zoom", "focus_zoom"} or (should_zoom_for_detail and not has_explicit_direction):
            direction = "zoom_in"
        # The 6:7 middle panel is substantially wider than the old 9:16 panel.
        # Fill the width and crop source height when contain would create dark
        # side bars; this keeps the user's requested height-first crop visible.
        fit_mode = "cover_width" if source_ratio < box_ratio * 0.9 else "contain"
        return {
            "fit_mode": fit_mode,
            "scale_mode": "fill_width_crop_height" if fit_mode == "cover_width" else "fit_inside",
            "scroll_axis": "",
            "motion_direction": direction,
            "motion_amount": float(requested_amount if requested_amount is not None else 0.08),
            "motion_focus": requested_focus or "center",
        }
    if direction in {"pan_left", "pan_right", "pan_up", "pan_down"}:
        direction = {
            "pan_left": "slide_in_left",
            "pan_right": "slide_in_right",
            "pan_up": "slide_in_top",
            "pan_down": "slide_in_bottom",
        }[direction]
    return {
        "fit_mode": "contain",
        "scale_mode": "fit_inside",
        "scroll_axis": "",
        "motion_direction": direction,
        "motion_amount": 0.0,
        "motion_focus": requested_focus or "center",
    }


def focus_adjusted_position(
    layer_size: tuple[int, int],
    image_size: tuple[int, int],
    base_x: int,
    base_y: int,
    focus: str | None,
) -> tuple[int, int]:
    focus_value = (focus or "center").lower().replace("-", "_")
    if focus_value in {"", "center", "centre"}:
        return base_x, base_y

    layer_w, layer_h = layer_size
    image_w, image_h = image_size
    extra_x = max(0, image_w - layer_w)
    extra_y = max(0, image_h - layer_h)
    if extra_x:
        if "left" in focus_value:
            base_x = 0
        elif "right" in focus_value:
            base_x = -extra_x
    if extra_y:
        if "top" in focus_value:
            base_y = 0
        elif "bottom" in focus_value:
            base_y = -extra_y
    return base_x, base_y


def paste_fit(
    canvas: Image.Image,
    src_path: Path,
    box: tuple[int, int, int, int],
    *,
    mode: str = "cover",
    bg: str = "#1F2929",
    radius: int = 16,
    outline: str = "#1D2525",
    motion_progress: float = 0.0,
    motion_direction: str = "zoom_in",
    motion_amount: float = 0.0,
    motion_focus: str | None = None,
) -> None:
    x1, y1, x2, y2 = box
    layer = Image.new("RGBA", (x2 - x1, y2 - y1), bg)
    source = ImageOps.exif_transpose(Image.open(src_path).convert("RGB"))
    progress = min(1.0, max(0.0, motion_progress))
    eased = 0.5 - math.cos(progress * math.pi) / 2

    if mode == "scroll_long_axis":
        bw, bh = layer.size
        if motion_direction in {"scroll_down", "scroll_up"}:
            scale = bw / source.width
        else:
            scale = bh / source.height
        im = source.resize(
            (max(1, int(source.width * scale)), max(1, int(source.height * scale))),
            Image.Resampling.LANCZOS,
        ).convert("RGBA")
    else:
        im = fit_image(source, box, mode=mode).convert("RGBA")
        if motion_amount > 0:
            if motion_direction == "scale_in":
                scale = max(0.75, 1.0 - motion_amount) + (motion_amount * 1.18) * eased
            elif motion_direction == "zoom_out":
                scale = 1.0 + motion_amount * (1.0 - eased)
            else:
                scale = 1.0 + motion_amount * eased
            if scale != 1.0:
                im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.Resampling.LANCZOS)

    base_x = (layer.width - im.width) // 2
    base_y = (layer.height - im.height) // 2
    if mode == "scroll_long_axis":
        if motion_direction in {"scroll_down", "scroll_up"}:
            scroll_range = max(0, im.height - layer.height)
            base_y = -int(scroll_range * eased)
            if motion_direction == "scroll_up":
                base_y = -scroll_range + int(scroll_range * eased)
        else:
            scroll_range = max(0, im.width - layer.width)
            base_x = -int(scroll_range * eased)
            if motion_direction == "scroll_left":
                base_x = -scroll_range + int(scroll_range * eased)
    else:
        if motion_direction in {"zoom_in", "zoom_out", "scale_in"}:
            base_x, base_y = focus_adjusted_position(layer.size, im.size, base_x, base_y, motion_focus)
        entry = min(1.0, progress / 0.28)
        entry_eased = 0.5 - math.cos(entry * math.pi) / 2
        if motion_direction == "slide_in_right":
            base_x += int(layer.width * 0.36 * (1.0 - entry_eased))
        elif motion_direction == "slide_in_left":
            base_x -= int(layer.width * 0.36 * (1.0 - entry_eased))
        elif motion_direction == "slide_in_bottom":
            base_y += int(layer.height * 0.36 * (1.0 - entry_eased))
        elif motion_direction == "slide_in_top":
            base_y -= int(layer.height * 0.36 * (1.0 - entry_eased))

    layer.alpha_composite(im, (base_x, base_y))
    mask = Image.new("L", layer.size, 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, layer.width - 1, layer.height - 1), radius=radius, fill=255)
    layer.putalpha(mask)
    canvas.alpha_composite(layer, (x1, y1))
    rounded(ImageDraw.Draw(canvas), box, radius, None, outline=outline, width=2)


def existing_image_paths(scene: dict[str, Any]) -> list[Path]:
    images = [Path(item) for item in scene.get("image_paths", []) if item]
    return [item for item in images if item.exists()]


def top_title_y_for_profile(profile: dict[str, Any]) -> int:
    return int(profile.get("top_title_y", profile.get("top_title_y_preferred", 78)))


def top_title_line_gap_for_profile(profile: dict[str, Any]) -> int:
    return int(profile.get("top_title_line_gap", profile.get("top_title_line_gap_preferred", 16)))


def top_subtitle_min_y_for_profile(profile: dict[str, Any]) -> int:
    return int(profile.get("top_subtitle_min_y", profile.get("top_subtitle_min_y_preferred", 222)))


def top_subtitle_line_gap_for_profile(profile: dict[str, Any]) -> int:
    return int(profile.get("top_subtitle_line_gap", profile.get("top_subtitle_line_gap_preferred", 0)))


def top_subtitle_font_start_for_profile(profile: dict[str, Any]) -> int:
    return int(profile.get("top_subtitle_font_size", profile.get("top_subtitle_font_size_preferred", 34)))


def top_subtitle_font_min_for_profile(profile: dict[str, Any]) -> int:
    return int(profile.get("top_subtitle_font_size_min", profile.get("top_subtitle_font_size_min_preferred", 26)))


def top_subtitle_max_h_for_profile(profile: dict[str, Any]) -> int:
    return int(profile.get("top_subtitle_max_h", profile.get("top_subtitle_max_h_preferred", 44)))


def resolve_top_subtitle(profile: dict[str, Any]) -> str:
    subtitle = str(profile.get("top_subtitle", "") or "").strip()
    suffix = str(profile.get("top_subtitle_suffix", profile.get("top_subtitle_suffix_default", "")) or "").strip()
    if not suffix:
        return subtitle
    if not subtitle:
        return suffix
    if suffix in subtitle:
        return subtitle
    return f"{subtitle} · {suffix}"


def draw_title(draw: ImageDraw.ImageDraw, profile: dict[str, Any], scene: dict[str, Any]) -> None:
    accent = scene.get("accent") or profile.get("accent") or DEFAULT_ACCENT
    show_top_tag = bool(scene.get("show_top_tag", profile.get("show_top_tag", True)))
    if show_top_tag:
        tag = scene.get("tag") or profile.get("tag") or "repo showcase"
        tag_f = font(24, True)
        tw, th = text_size(draw, tag, tag_f)
        rounded(
            draw,
            (int((W - tw) / 2 - 24), TOP_TAG_Y, int((W + tw) / 2 + 24), TOP_TAG_Y + th + 16),
            18,
            CARD_COLOR,
            accent,
            2,
        )
        draw.text(((W - tw) / 2, TOP_TAG_Y + 6), tag, font=tag_f, fill=TITLE_COLOR)
    title_line_gap = top_title_line_gap_for_profile(profile)
    title_f = fit_font_size(
        draw,
        profile["top_title"],
        start=int(profile.get("top_title_font_size", 60)),
        minimum=44,
        max_w=940,
        max_h=int(profile.get("top_title_max_h", 126)),
        bold=True,
        line_gap=title_line_gap,
    )
    title_y = top_title_y_for_profile(profile)
    if show_top_tag and "top_title_y" not in profile:
        title_y = max(title_y, 78)
    title_end = draw_centered(
        draw,
        profile["top_title"],
        title_y,
        title_f,
        TITLE_COLOR,
        line_gap=title_line_gap,
        stroke_width=3,
        stroke_fill=BACKGROUND_COLOR,
    )
    subtitle = resolve_top_subtitle(profile)
    if subtitle:
        subtitle_line_gap = top_subtitle_line_gap_for_profile(profile)
        subtitle_f = fit_font_size(
            draw,
            subtitle,
            start=top_subtitle_font_start_for_profile(profile),
            minimum=top_subtitle_font_min_for_profile(profile),
            max_w=940,
            max_h=top_subtitle_max_h_for_profile(profile),
            bold=True,
            line_gap=subtitle_line_gap,
        )
        draw_centered(
            draw,
            subtitle,
            max(top_subtitle_min_y_for_profile(profile), title_end + 16),
            subtitle_f,
            MUTED_COLOR,
            line_gap=subtitle_line_gap,
        )


def draw_metric_card(draw: ImageDraw.ImageDraw, x: int, y: int, metric: dict[str, Any], accent: str) -> None:
    rounded(draw, (x, y, x + 190, y + 104), 18, SURFACE_COLOR, accent, 2)
    draw.text((x + 20, y + 16), str(metric.get("value", "")), font=font(40, True), fill=BACKGROUND_COLOR)
    draw.text((x + 20, y + 66), str(metric.get("label", "")), font=font(22), fill="#4F5A4D")


def draw_hero_value(draw: ImageDraw.ImageDraw, text: str, y: int, accent: str) -> int:
    fnt = fit_font_size(draw, text, start=52, minimum=34, max_w=760, max_h=74, bold=True, line_gap=2)
    _, block_h = multiline_size(draw, text, fnt, line_gap=2)
    rounded(draw, (132, y - 12, 948, y + block_h + 20), 20, CARD_COLOR, accent, 2)
    draw_centered(draw, text, y, fnt, TITLE_COLOR, line_gap=2)
    return y + block_h + 28


def draw_value_badges(draw: ImageDraw.ImageDraw, badges: list[dict[str, Any]], y: int, accent: str) -> int:
    visible = [item for item in badges if item and (item.get("value") or item.get("text"))][:3]
    if not visible:
        return y

    gap = 18
    if len(visible) == 1:
        card_w = 640
        x0 = int((W - card_w) / 2)
    else:
        card_w = int((820 - gap * (len(visible) - 1)) / len(visible))
        x0 = int((W - (card_w * len(visible) + gap * (len(visible) - 1))) / 2)
    card_h = 118

    for idx, badge in enumerate(visible):
        x = x0 + idx * (card_w + gap)
        local_accent = badge.get("accent") or accent
        rounded(draw, (x, y, x + card_w, y + card_h), 18, CARD_COLOR, local_accent, 2)
        value = str(badge.get("value") or badge.get("text") or "")
        label = str(badge.get("label") or "")
        value_f = fit_font_size(
            draw,
            value,
            start=int(badge.get("font_size", 48)),
            minimum=26,
            max_w=card_w - 34,
            max_h=64,
            bold=True,
            line_gap=0,
        )
        _, value_h = multiline_size(draw, value, value_f)
        value_y = y + 18 if label else y + int((card_h - value_h) / 2) - 2
        draw_centered_in_box(draw, value, (x, value_y, x + card_w, y + card_h), value_f, TITLE_COLOR)
        if label:
            label_f = fit_font_size(draw, label, start=22, minimum=16, max_w=card_w - 34, max_h=28)
            label_w, _ = text_size(draw, label, label_f)
            draw.text((x + (card_w - label_w) / 2, y + 82), label, font=label_f, fill=MUTED_COLOR)
    return y + card_h


def image_boxes_for_content(content_y: int, image_count: int) -> list[tuple[int, int, int, int]]:
    top = min(max(int(content_y), MIDDLE_PANEL_BOX[1] + 18), MIDDLE_CONTENT_BOTTOM - 120)
    if image_count <= 1:
        return [(104, top, 976, MIDDLE_CONTENT_BOTTOM)]
    if image_count <= 2:
        return [(104, top, 524, MIDDLE_CONTENT_BOTTOM), (556, top, 976, MIDDLE_CONTENT_BOTTOM)]
    row_gap = 18
    row_h = max(88, int((MIDDLE_CONTENT_BOTTOM - top - row_gap) / 2))
    return [
        (104, top, 524, top + row_h),
        (556, top, 976, top + row_h),
        (104, top + row_h + row_gap, 524, MIDDLE_CONTENT_BOTTOM),
        (556, top + row_h + row_gap, 976, MIDDLE_CONTENT_BOTTOM),
    ]


def should_show_middle_title(profile: dict[str, Any], scene: dict[str, Any]) -> bool:
    if "show_middle_title" in scene:
        return bool(scene.get("show_middle_title"))
    return bool(profile.get("show_middle_title", False))


def should_show_image_labels(profile: dict[str, Any], scene: dict[str, Any]) -> bool:
    if "show_image_labels" in scene:
        return bool(scene.get("show_image_labels"))
    return bool(profile.get("show_image_labels", False))


def middle_title_font_size(profile: dict[str, Any], scene: dict[str, Any], *, has_value_block: bool) -> int:
    return int(
        scene.get(
            "middle_visual_title_font_size",
            profile.get(
                "middle_visual_title_font_size",
                profile.get("middle_visual_title_font_size_preferred", 28 if has_value_block else 32),
            ),
        )
    )


def middle_content_start_y(profile: dict[str, Any], scene: dict[str, Any], *, has_value_block: bool, show_title: bool) -> int:
    if not show_title:
        return int(
            scene.get(
                "middle_content_start_no_title",
                profile.get("middle_content_start_no_title", MIDDLE_PANEL_BOX[1] + 18),
            )
        )
    return MIDDLE_CONTENT_START_WITH_VALUE if has_value_block else MIDDLE_CONTENT_START


def draw_visual(canvas: Image.Image, profile: dict[str, Any], scene: dict[str, Any], progress: float = 0.0) -> None:
    draw = ImageDraw.Draw(canvas)
    accent = scene.get("accent") or profile.get("accent") or DEFAULT_ACCENT
    x1, y1, x2, y2 = MIDDLE_PANEL_BOX
    rounded(draw, (x1 + 10, y1 + 12, x2 + 10, y2 + 12), 24, SHADOW_COLOR)
    rounded(draw, MIDDLE_PANEL_BOX, 24, SURFACE_COLOR, accent, 3)
    draw.rectangle((x1, y1 + 28, x1 + 10, y2 - 28), fill=accent)
    title = scene.get("visual_title") or scene.get("bottom_title") or profile.get("project_name", "")
    has_value_block = bool(scene.get("hero_value_text") or scene.get("value_badges"))
    show_title = should_show_middle_title(profile, scene)
    if show_title and title:
        draw_centered(
            draw,
            title,
            MIDDLE_TITLE_Y_WITH_VALUE if has_value_block else MIDDLE_TITLE_Y,
            font(middle_title_font_size(profile, scene, has_value_block=has_value_block), True),
            BACKGROUND_COLOR,
        )

    content_y = middle_content_start_y(profile, scene, has_value_block=has_value_block, show_title=show_title)
    if scene.get("hero_value_text"):
        content_y = draw_hero_value(draw, str(scene["hero_value_text"]), content_y, accent) + 8
    if scene.get("value_badges"):
        content_y = draw_value_badges(draw, scene.get("value_badges") or [], content_y, accent) + 8

    images = existing_image_paths(scene)
    if images:
        boxes = image_boxes_for_content(content_y, len(images))
        labels = scene.get("image_labels", []) if should_show_image_labels(profile, scene) else []
        image_mode = scene.get("image_mode") or profile.get("image_mode") or "auto_source"
        animate_image = bool(scene.get("animate_image", profile.get("animate_middle", False)))
        requested_direction = scene.get("motion_direction") or profile.get("motion_direction")
        requested_focus = scene.get("motion_focus") or scene.get("image_focus") or profile.get("motion_focus")
        if not animate_image:
            requested_direction = "none"
        requested_amount = float(scene.get("motion_amount", profile.get("motion_amount", 0.08)))
        for idx, path in enumerate(images[:4]):
            local_mode = image_mode
            motion_direction = "none" if requested_direction == "none" else (requested_direction or "slide_in_right")
            motion_amount = 0.0
            motion_focus = requested_focus or "center"
            if image_mode in {"auto", "auto_source"}:
                with Image.open(path) as src:
                    plan = motion_plan_for_source(
                        src.size,
                        boxes[idx],
                        requested_direction=requested_direction,
                        requested_amount=requested_amount,
                        requested_focus=requested_focus,
                        content_features=list(
                            scene.get("content_features")
                            or scene.get("visual_features")
                            or scene.get("image_features")
                            or labels
                            or []
                        )
                        + [str(title), str(scene.get("bottom_title", ""))],
                    )
                local_mode = plan["fit_mode"]
                motion_direction = "none" if requested_direction == "none" else plan["motion_direction"]
                motion_amount = float(plan["motion_amount"]) if animate_image else 0.0
                motion_focus = str(plan.get("motion_focus") or "center")
            paste_fit(
                canvas,
                path,
                boxes[idx],
                mode=local_mode,
                outline=accent,
                motion_progress=progress,
                motion_direction=motion_direction,
                motion_amount=motion_amount,
                motion_focus=motion_focus,
            )
            if idx < len(labels):
                x1, y1, _, _ = boxes[idx]
                rounded(draw, (x1 + 12, y1 + 12, x1 + 158, y1 + 46), 12, CARD_COLOR, accent, 1)
                draw.text((x1 + 24, y1 + 16), str(labels[idx]), font=font(20, True), fill=TITLE_COLOR)
        return

    metrics = scene.get("metrics") or profile.get("metrics") or []
    for idx, metric in enumerate(metrics[:4]):
        draw_metric_card(
            draw,
            130 + idx * 215,
            max(MIDDLE_PANEL_BOX[1] + 40, content_y + 22),
            metric,
            metric.get("accent") or accent,
        )

    bullets = scene.get("visual_lines") or []
    yy = max(MIDDLE_PANEL_BOX[1] + 250, content_y + 156 if metrics else content_y + 24)
    for line in bullets[:4]:
        if yy > MIDDLE_CONTENT_BOTTOM - 28:
            break
        rounded(draw, (150, yy, 930, yy + 45), 14, CARD_COLOR, accent, 1)
        draw_centered(draw, line, yy + 8, font(24, True), TITLE_COLOR)
        yy += 58


def draw_bottom(canvas: Image.Image, profile: dict[str, Any], scene: dict[str, Any]) -> None:
    draw = ImageDraw.Draw(canvas)
    accent = scene.get("accent") or profile.get("accent") or DEFAULT_ACCENT
    highlight = scene.get("bottom_highlight_color") or scene.get("highlight_color") or accent
    raw_lines = list(scene.get("bottom_lines", []) or [])
    lines = prepare_bottom_lines_for_layout(draw, profile, scene, raw_lines)
    line_count = len(lines)
    dense = bool(scene.get("dense_bottom")) or line_count >= 4
    default_y1, default_y2 = BOTTOM_BOX_DEFAULTS[dense]
    y1 = int(scene.get("bottom_box_y1", profile.get("bottom_box_y1", default_y1)))
    y2 = int(scene.get("bottom_box_y2", profile.get("bottom_box_y2", default_y2)))
    rounded(draw, (86, y1 + 12, 1014, y2 + 12), 22, SHADOW_COLOR)
    rounded(draw, (76, y1, 1004, y2), 22, CARD_COLOR, accent, 3)
    draw.rectangle((430, y1 - 3, 650, y1 + 7), fill=accent)
    typography = bottom_body_typography(profile, scene, line_count=line_count, dense=dense)
    body_size = typography["body_size"]
    body_size_min = typography["body_size_min"]
    line_step = typography["line_step"]
    line_step_max = typography["line_step_max"]
    body_y_offset = int(
        scene.get(
            "bottom_body_y_offset",
            profile.get("bottom_body_y_offset", profile.get("bottom_body_y_offset_no_title", 30 if dense else 42)),
        )
    )

    footer = scene.get("footer", "")
    footer_y = y2 - int(scene.get("footer_y_offset", profile.get("footer_y_offset", 38)))
    footer_h = 0
    foot_f: ImageFont.ImageFont | None = None
    footer_box: tuple[int, int, int, int] | None = None
    if footer:
        footer_start = int(scene.get("footer_font_size", profile.get("footer_font_size", 21)))
        foot_f = fit_font_size(
            draw,
            footer,
            start=footer_start,
            minimum=int(profile.get("footer_font_size_min", 18)),
            max_w=int(profile.get("footer_max_w", 860)),
            max_h=36,
            bold=True,
        )
        tw, th = text_size(draw, footer, foot_f)
        footer_h = max(30, th + 10)
        footer_box = (
            int((W - tw) / 2 - 20),
            footer_y,
            int((W + tw) / 2 + 20),
            footer_y + footer_h,
        )

    body_top = y1 + body_y_offset
    body_bottom = (footer_y - int(profile.get("bottom_body_footer_gap", 26))) if footer else (y2 - 34)
    base_bold = bool(scene.get("bottom_bold_lines", False))
    if bool(scene.get("dynamic_bottom_layout", profile.get("dynamic_bottom_layout", True))):
        body_size, line_step, yy = bottom_body_layout(
            draw,
            lines,
            start_size=body_size,
            minimum=body_size_min,
            max_w=int(profile.get("bottom_text_max_w", 870)),
            body_top=body_top,
            body_bottom=body_bottom,
            line_step_hint=line_step,
            line_step_max=line_step_max,
            base_bold=base_bold,
        )
    else:
        yy = body_top

    for line in lines:
        line_size = fit_rich_font_size(
            draw,
            line,
            start=body_size,
            minimum=body_size_min,
            max_w=int(profile.get("bottom_text_max_w", 870)),
            max_h=line_step + 6,
            base_bold=base_bold,
        )
        draw_rich_centered(
            draw,
            line,
            yy,
            line_size,
            BODY_COLOR,
            highlight,
            base_bold=base_bold,
        )
        yy += line_step

    if footer and foot_f and footer_box:
        rounded(draw, footer_box, 12, SURFACE_COLOR)
        tw, _ = text_size(draw, footer, foot_f)
        draw.text(((W - tw) / 2, footer_y), footer, font=foot_f, fill=accent)


def render_frame(profile: dict[str, Any], scene: dict[str, Any], out: Path, *, progress: float = 0.0) -> None:
    canvas = make_bg(
        scene.get("accent") or profile.get("accent") or DEFAULT_ACCENT,
        show_safe_bands=bool(scene.get("show_safe_bands", profile.get("show_safe_bands", True))),
    )
    draw = ImageDraw.Draw(canvas)
    draw_title(draw, profile, scene)
    draw_visual(canvas, profile, scene, progress=progress)
    draw_bottom(canvas, profile, scene)
    canvas.convert("RGB").save(out, quality=95)


def render_animated_visual(
    profile: dict[str, Any],
    scenes: list[dict[str, Any]],
    durations: list[float],
    frames_dir: Path,
    tmp_dir: Path,
) -> Path:
    fps = int(profile.get("animation_fps", 30))
    clips: list[Path] = []
    for idx, (scene, duration) in enumerate(zip(scenes, durations), start=1):
        scene_dir = frames_dir / f"scene_{idx:02d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        frame_count = max(2, int(round(duration * fps)))
        for frame_idx in range(frame_count):
            progress = frame_idx / max(1, frame_count - 1)
            render_frame(profile, scene, scene_dir / f"frame_{frame_idx:04d}.png", progress=progress)
        clip = tmp_dir / f"scene_{idx:02d}.mp4"
        run([
            "ffmpeg",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(scene_dir / "frame_%04d.png"),
            "-vf",
            "fps=30,format=yuv420p",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(clip),
        ])
        clips.append(clip)

    concat = tmp_dir / "scene_clips.txt"
    with concat.open("w", encoding="utf-8") as handle:
        for clip in clips:
            handle.write(f"file '{clip.resolve()}'\n")
    visual = tmp_dir / "visual.mp4"
    run([
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(visual),
    ])
    return visual


def compute_scene_durations(profile: dict[str, Any], scenes: list[dict[str, Any]], duration: float) -> list[float]:
    if not scenes:
        return []

    explicit: dict[int, float] = {}
    for idx, scene in enumerate(scenes):
        value = scene.get("duration_seconds", scene.get("duration"))
        if isinstance(value, (int, float)) and value > 0:
            explicit[idx] = float(value)

    if explicit:
        durations = [0.0 for _ in scenes]
        fixed_total = sum(explicit.values())
        if fixed_total >= duration:
            scale = duration / fixed_total
            for idx, value in explicit.items():
                durations[idx] = value * scale
            return durations

        remaining_indices = [idx for idx in range(len(scenes)) if idx not in explicit]
        remaining_duration = duration - fixed_total
        has_duration_weights = any(
            isinstance(scenes[idx].get("duration_weight"), (int, float)) and scenes[idx].get("duration_weight") > 0
            for idx in remaining_indices
        )
        remaining_weights = (
            [float(scenes[idx].get("duration_weight", 1)) for idx in remaining_indices]
            if has_duration_weights
            else [1.0 for _ in remaining_indices]
        )
        total_weight = sum(remaining_weights) or len(remaining_indices) or 1
        for idx, value in explicit.items():
            durations[idx] = value
        for idx, weight in zip(remaining_indices, remaining_weights):
            durations[idx] = remaining_duration * weight / total_weight
        return durations

    weights = [max(1, len(str(scene.get("narration", scene.get("bottom_title", ""))))) for scene in scenes]
    raw = [duration * weight / sum(weights) for weight in weights]
    durations = [max(3.5, item) for item in raw]
    scale = duration / sum(durations)
    return [item * scale for item in durations]


def ffprobe_duration(path: Path) -> float:
    proc = run([
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])
    return float(proc.stdout.strip())


def has_audio_stream(path: Path) -> bool:
    proc = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=False,
    )
    return proc.returncode == 0 and bool(proc.stdout.strip())


def packaged_assets_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "assets"


def packaged_bgm_candidates(profile: dict[str, Any]) -> list[Path]:
    assets_dir = packaged_assets_dir()
    if not assets_dir.is_dir():
        return []

    names: list[str] = []
    for value in (
        profile.get("bgm_asset"),
        profile.get("bgm_asset_filename"),
        profile.get("default_bgm_asset"),
    ):
        if value:
            names.append(str(value))

    candidates = [(assets_dir / name) for name in names]
    return candidates


def first_existing_bgm_path(profile: dict[str, Any]) -> Path | None:
    candidates: list[Any] = [
        os.environ.get("CAPSULE_BGM_PATH"),
        os.environ.get("CAPSULE_CINEMA_BGM_PATH"),
        profile.get("bgm_path"),
        profile.get("background_music_path"),
        profile.get("music_path"),
    ]
    music_selection = profile.get("music_selection")
    if isinstance(music_selection, dict):
        candidates.extend(
            [
                music_selection.get("bgm_path"),
                music_selection.get("music_path"),
                music_selection.get("background_music_path"),
            ]
        )

    candidates.extend(packaged_bgm_candidates(profile))
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(str(candidate)).expanduser()
        if path.is_file():
            return path.resolve()
    return None


def mix_background_music(video: Path, music: Path, out: Path, volume: float) -> None:
    if has_audio_stream(video):
        filter_complex = (
            "[0:a]aformat=sample_rates=48000:channel_layouts=stereo[base];"
            f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={volume}[bgm];"
            "[base][bgm]amix=inputs=2:duration=first:dropout_transition=0.2[aout]"
        )
    else:
        filter_complex = f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={volume}[aout]"

    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-stream_loop",
            "-1",
            "-i",
            str(music),
            "-filter_complex",
            filter_complex,
            "-map",
            "0:v",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out),
        ]
    )


def find_project_root() -> Path:
    env_root = os.environ.get("CAPSULE_CINEMA_ROOT") or os.environ.get("VIDEO_AGENT_ROOT")
    candidates: list[Path] = []
    if env_root:
        candidates.append(Path(env_root).expanduser())
    candidates.extend([Path.cwd(), Path(__file__).resolve()])
    for start in candidates:
        current = start if start.is_dir() else start.parent
        for parent in (current, *current.parents):
            if (parent / "scripts" / "env_loader.py").exists() and (parent / "lib").exists():
                return parent.resolve()
    raise SystemExit(
        "Cannot locate Capsule Cinema project root. Run from the repo root or set CAPSULE_CINEMA_ROOT."
    )


SPOKEN_PROFILE_FIELDS = ("voiceover", "narration", "tts_text", "speech_text")
MIN_BOTTOM_LINE_VISIBLE_CHARS = 8
MAX_SOURCE_FILE_SCREENSHOTS_DEFAULT = 1
ALLOWED_SOURCE_ASSET_TYPES = {
    "browser_evidence_screenshot",
    "repository_image",
    "readme_embedded_image",
    "project_discussion_image",
    "external_project_related_image",
    "documentation_screenshot",
    "source_file_screenshot",
    "demo_output_screenshot",
    "video_or_gif_frame",
}
RICH_MIDDLE_VISUAL_ASSET_TYPES = {
    "browser_evidence_screenshot",
    "repository_image",
    "readme_embedded_image",
    "project_discussion_image",
    "external_project_related_image",
    "demo_output_screenshot",
    "video_or_gif_frame",
}
APPROVED_BROWSER_MIDDLE_VISUAL_ASSET_TYPES = {
    "browser_evidence_screenshot",
    "readme_embedded_image",
    "project_discussion_image",
    "external_project_related_image",
}
APPROVED_BROWSER_CAPTURE_METHODS = {
    "actual_browser_github_repository_page_screenshot",
    "actual_browser_github_repo_readme_key_area_screenshot",
    "actual_browser_github_readme_image_element_screenshot",
    "actual_browser_x_search_screenshot",
    "actual_browser_project_page_screenshot",
}
SOURCE_ASSET_TYPE_ALIASES = {
    "repository_image_asset": "repository_image",
    "repo_local_image": "repository_image",
    "readme_embedded_image_asset": "readme_embedded_image",
    "github_repo_readme_key_area": "browser_evidence_screenshot",
    "actual_browser_github_repo_readme_key_area_screenshot": "browser_evidence_screenshot",
    "github_readme_content_screenshot": "documentation_screenshot",
    "github_readme_content": "documentation_screenshot",
    "repository_source_file_preview": "source_file_screenshot",
    "quicklook_source_file_preview": "source_file_screenshot",
}
SIMULATED_SOURCE_CAPTURE_RE = re.compile(
    r"local[_ -]?rendered|markdown[_ -]?(?:render|to[_ -]?html)|"
    r"set[_ -]?content|html[_ -]?generated|pil[_ -]?generated|"
    r"generated[_ -]?text[_ -]?card|self[_ -]?made|retyped|synthetic"
)


def reject_spoken_profile_fields(profile: dict[str, Any]) -> None:
    for key in SPOKEN_PROFILE_FIELDS:
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            raise SystemExit(f"repo_signal_grid is silent-only; remove {key} from the profile")
        if isinstance(value, (list, tuple)) and any(str(item).strip() for item in value):
            raise SystemExit(f"repo_signal_grid is silent-only; remove {key} from the profile")
        if isinstance(value, dict) and any(str(item).strip() for item in value.values()):
            raise SystemExit(f"repo_signal_grid is silent-only; remove {key} from the profile")


def preflight_fail(message: str) -> None:
    raise SystemExit(f"repo_signal_grid preflight failed: {message}")


def canonical_source_asset_type(item: dict[str, Any]) -> str:
    for key in ("asset_type", "source_kind"):
        value = str(item.get(key) or "").strip()
        if value:
            return SOURCE_ASSET_TYPE_ALIASES.get(value, value)
    return ""


def load_source_asset_manifest(profile: dict[str, Any]) -> list[dict[str, Any]]:
    inline_manifest = profile.get("source_asset_manifest")
    if inline_manifest:
        if not isinstance(inline_manifest, list):
            preflight_fail("source_asset_manifest must be a list")
        return [item for item in inline_manifest if isinstance(item, dict)]

    manifest_path_value = profile.get("source_asset_manifest_path")
    if not manifest_path_value:
        preflight_fail("source_asset_manifest is required for approved repo_signal_grid renders")

    manifest_path = Path(str(manifest_path_value)).expanduser()
    if not manifest_path.exists():
        preflight_fail(f"source_asset_manifest_path does not exist: {manifest_path}")

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        preflight_fail(f"source_asset_manifest_path is invalid JSON: {exc}")

    if isinstance(data, dict):
        data = data.get("assets") or data.get("items") or data.get("source_asset_manifest") or []
    if not isinstance(data, list):
        preflight_fail("source_asset_manifest_path must contain a list")
    return [item for item in data if isinstance(item, dict)]


def normalized_asset_path(value: Any) -> str:
    return str(Path(str(value)).expanduser().resolve()) if value else ""


def validate_actual_source_manifest(profile: dict[str, Any], scenes: list[dict[str, Any]]) -> None:
    manifest = load_source_asset_manifest(profile)
    if not manifest:
        preflight_fail("source_asset_manifest must list every middle visual")

    by_asset_id: dict[str, dict[str, Any]] = {}
    by_path: dict[str, dict[str, Any]] = {}
    actual_source_count = 0
    rich_middle_visual_count = 0
    source_file_screenshot_count = 0
    for index, item in enumerate(manifest, start=1):
        asset_id = str(item.get("asset_id") or "").strip()
        path_value = item.get("path")
        if not asset_id:
            preflight_fail(f"source_asset_manifest[{index}] missing asset_id")
        if not path_value:
            preflight_fail(f"source_asset_manifest[{asset_id}] missing path")
        if item.get("actual_source") is not True:
            preflight_fail(f"source_asset_manifest[{asset_id}] must set actual_source=true")
        if item.get("reconstructed_card") is not False:
            preflight_fail(f"source_asset_manifest[{asset_id}] must set reconstructed_card=false")
        asset_type = canonical_source_asset_type(item)
        if asset_type not in ALLOWED_SOURCE_ASSET_TYPES:
            allowed = ", ".join(sorted(ALLOWED_SOURCE_ASSET_TYPES))
            preflight_fail(
                f"source_asset_manifest[{asset_id}] asset_type must be one of: {allowed}"
            )
        if asset_type == "source_file_screenshot":
            source_file_screenshot_count += 1
        if asset_type in RICH_MIDDLE_VISUAL_ASSET_TYPES:
            rich_middle_visual_count += 1
        capture_method = str(item.get("capture_method") or "").strip()
        if not capture_method:
            preflight_fail(f"source_asset_manifest[{asset_id}] missing capture_method")
        source_ref = str(item.get("source_url_or_repo_path") or "").strip()
        if not source_ref:
            preflight_fail(f"source_asset_manifest[{asset_id}] missing source_url_or_repo_path")
        source_kind = str(item.get("source_kind") or "")
        capture_label = f"{asset_type} {source_kind} {capture_method} {source_ref}"
        if SIMULATED_SOURCE_CAPTURE_RE.search(capture_label.lower()):
            preflight_fail(
                f"source_asset_manifest[{asset_id}] uses simulated source capture; "
                "README/docs screenshots must be actual browser content-area screenshots"
            )
        if asset_type in RICH_MIDDLE_VISUAL_ASSET_TYPES and capture_method not in APPROVED_BROWSER_CAPTURE_METHODS:
            allowed_methods = ", ".join(sorted(APPROVED_BROWSER_CAPTURE_METHODS))
            preflight_fail(
                f"source_asset_manifest[{asset_id}] uses non-browser capture_method for an approved profile; "
                f"repo_signal_grid is browser-only and requires one of: {allowed_methods}"
            )

        path = Path(str(path_value)).expanduser()
        if not path.exists():
            preflight_fail(f"source_asset_manifest[{asset_id}] path does not exist: {path}")
        by_asset_id[asset_id] = item
        by_path[normalized_asset_path(path_value)] = item
        actual_source_count += 1

    required_actual_sources = min(4, len(scenes))
    if actual_source_count < required_actual_sources:
        preflight_fail(
            f"source_asset_manifest needs at least {required_actual_sources} actual_source middle visuals"
        )
    if rich_middle_visual_count < required_actual_sources:
        preflight_fail(
            "source_asset_manifest needs at least "
            f"{required_actual_sources} rich middle visual(s); "
            "browser_evidence_screenshot is allowed only when it is an actual browser "
            "GitHub/README key-area capture; documentation_screenshot and "
            "source_file_screenshot are diagnostic-only, not approved middle scenes"
        )
    max_source_file_screenshots = int(
        profile.get("max_source_file_screenshots", MAX_SOURCE_FILE_SCREENSHOTS_DEFAULT)
    )
    if source_file_screenshot_count > max_source_file_screenshots:
        preflight_fail(
            "source_file_screenshot can support at most "
            f"{max_source_file_screenshots} middle visual(s); use README/docs/demo/output screenshots instead"
        )

    for scene_index, scene in enumerate(scenes, start=1):
        image_paths = [item for item in scene.get("image_paths", []) if item]
        if not image_paths:
            preflight_fail(f"scene {scene_index} must use real image_paths; metrics/visual_lines cards are not allowed")

        scene_asset_id = str(scene.get("asset_id") or "").strip()
        if scene_asset_id and scene_asset_id not in by_asset_id:
            preflight_fail(f"scene {scene_index} asset_id is not in source_asset_manifest: {scene_asset_id}")

        for image_path in image_paths:
            path_key = normalized_asset_path(image_path)
            if path_key not in by_path:
                preflight_fail(f"scene {scene_index} image_path is not listed in source_asset_manifest: {image_path}")
            if scene_asset_id and by_asset_id[scene_asset_id] is not by_path[path_key]:
                preflight_fail(f"scene {scene_index} asset_id does not match image_path manifest entry")
            scene_asset_type = canonical_source_asset_type(by_path[path_key])
            if scene_asset_type not in APPROVED_BROWSER_MIDDLE_VISUAL_ASSET_TYPES:
                preflight_fail(
                    f"scene {scene_index} must use a browser-captured rich middle visual; "
                    f"{scene_asset_type} can only be kept in blocked/diagnostic material notes"
                )


def visible_char_count(text: Any) -> int:
    cleaned = strip_emphasis_markup(text)
    return len(re.sub(r"\s+", "", cleaned))


def validate_bottom_fact_chain(scenes: list[dict[str, Any]]) -> None:
    for scene_index, scene in enumerate(scenes, start=1):
        bottom_title = str(scene.get("bottom_title") or "").strip()
        if bottom_title:
            preflight_fail(f"scene {scene_index} bottom_title must be empty; put the judgment in bottom_lines[0]")

        lines = scene.get("bottom_lines")
        if not isinstance(lines, list) or not (4 <= len(lines) <= 5):
            preflight_fail(f"scene {scene_index} bottom_lines must contain 4-5 complete readable lines")

        for line_index, line in enumerate(lines, start=1):
            cleaned = strip_emphasis_markup(line).strip()
            if not re.search(r"[。！？.!?]$", cleaned):
                preflight_fail(
                    f"scene {scene_index} bottom_lines[{line_index}] must be a complete sentence, not a fragment"
                )
            if visible_char_count(cleaned) < MIN_BOTTOM_LINE_VISIBLE_CHARS:
                preflight_fail(
                    f"scene {scene_index} bottom_lines[{line_index}] is too short to read as a complete fact-chain line"
                )
            if cleaned.endswith((",", "，", "、", "/", ":", "：", "-", "->")):
                preflight_fail(
                    f"scene {scene_index} bottom_lines[{line_index}] must be a complete sentence, not a fragment"
                )


def validate_repo_signal_grid_profile(profile: dict[str, Any]) -> None:
    scenes = profile.get("scenes") or []
    if not scenes:
        preflight_fail("profile must include scenes")
    if len(scenes) > 5:
        preflight_fail("short_silent_repo_signal_grid supports at most 5 scenes")
    duration = float(profile.get("target_duration", 15))
    if not math.isclose(duration, 15.0, abs_tol=0.05):
        preflight_fail("target_duration must be fixed at 15 seconds")
    validate_actual_source_manifest(profile, scenes)
    validate_bottom_fact_chain(scenes)


def write_concat(frames: list[Path], durations: list[float], out: Path) -> None:
    with out.open("w", encoding="utf-8") as handle:
        for frame, duration in zip(frames, durations):
            handle.write(f"file '{frame.resolve()}'\n")
            handle.write(f"duration {duration:.3f}\n")
        handle.write(f"file '{frames[-1].resolve()}'\n")
        handle.write("duration 0.033\n")
        handle.write(f"file '{frames[-1].resolve()}'\n")


def write_prompt_snapshots(profile: dict[str, Any], output_dir: Path, params_path: Path, topic: str) -> list[dict[str, Any]]:
    prompts_dir = output_dir / "prompts"
    render_dir = prompts_dir / "render"
    render_dir.mkdir(parents=True, exist_ok=True)

    profile_snapshot = render_dir / "repo_signal_grid_profile_v001.json"
    snapshot = {
        "type": "repo_signal_grid_profile",
        "topic": topic,
        "source_params_path": str(params_path),
        "profile": profile,
    }
    profile_snapshot.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prompt_index = prompts_dir / "prompt_index.json"
    index = {
        "schema": "capsule_cinema.prompt_index.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entries": [
            {
                "id": "repo_signal_grid_profile_v001",
                "category": "render",
                "path": str(profile_snapshot.relative_to(output_dir)),
                "source_params_path": str(params_path),
            }
        ],
    }
    prompt_index.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [
        {"path": str(prompt_index.resolve()), "category": "storyboard_prompt", "title": "Prompt index"},
        {"path": str(profile_snapshot.resolve()), "category": "storyboard_prompt", "title": "Repo showcase profile"},
    ]


def add_visible_text(lines: list[str], value: Any) -> None:
    if value is None:
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            add_visible_text(lines, item)
        return
    for line in str(value).splitlines():
        cleaned = strip_emphasis_markup(line).strip()
        if cleaned:
            lines.append(cleaned)


def collect_visible_text(profile: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()

    for scene in profile.get("scenes") or []:
        if bool(scene.get("show_top_tag", profile.get("show_top_tag", True))):
            add_visible_text(lines, scene.get("tag") or profile.get("tag") or "repo showcase")
        add_visible_text(lines, profile.get("top_title"))
        add_visible_text(lines, resolve_top_subtitle(profile))
        if should_show_middle_title(profile, scene):
            add_visible_text(lines, scene.get("visual_title") or scene.get("bottom_title") or profile.get("project_name"))
        add_visible_text(lines, scene.get("hero_value_text"))
        for badge in scene.get("value_badges") or []:
            add_visible_text(lines, badge.get("value") or badge.get("text"))
            add_visible_text(lines, badge.get("label"))

        images = existing_image_paths(scene)
        if images and should_show_image_labels(profile, scene):
            add_visible_text(lines, list(scene.get("image_labels", []))[: len(images[:4])])
        elif not images:
            for metric in (scene.get("metrics") or profile.get("metrics") or [])[:4]:
                add_visible_text(lines, metric.get("value"))
                add_visible_text(lines, metric.get("label"))
            add_visible_text(lines, list(scene.get("visual_lines") or [])[:4])

        add_visible_text(lines, scene.get("bottom_lines") or [])
        add_visible_text(lines, scene.get("footer"))

    deduped: list[str] = []
    for line in lines:
        if line not in seen:
            deduped.append(line)
            seen.add(line)
    return deduped


CAPSULE_VISIBLE_COPY_FORBIDDEN_TERMS = [
    "商用可用",
    "长图按页面滚动",
    "页面滚动",
    "滚动展示",
    "缩放抖动",
    "MIT",
    "链接",
    "网址",
    "域名",
    "二维码",
    "扫码",
    "URL",
]

CAPSULE_VISIBLE_COPY_FORBIDDEN_REGEX = [
    r"https?://[^\s<>\u3000]+",
    r"\b(?:www\.)?[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)*\.(?:com|cn|net|org|io|ai|dev|app|co|edu|gov|xyz|me|tv|cc)(?:/[^\s<>\u3000]*)?",
]


def capsule_visible_copy_policy_violations(lines: list[str]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    seen_terms: set[str] = set()
    for line in lines:
        present_terms = [term for term in CAPSULE_VISIBLE_COPY_FORBIDDEN_TERMS if term in line]
        for term in CAPSULE_VISIBLE_COPY_FORBIDDEN_TERMS:
            has_more_specific_match = any(term != other and term in other for other in present_terms)
            if term in line and term not in seen_terms and not has_more_specific_match:
                violations.append({"term": term, "line": line})
                seen_terms.add(term)
        for pattern in CAPSULE_VISIBLE_COPY_FORBIDDEN_REGEX:
            key = f"regex:{pattern}"
            if key not in seen_terms and re.search(pattern, line, flags=re.IGNORECASE):
                violations.append({"term": key, "line": line})
                seen_terms.add(key)
    return violations


def write_visible_text_and_lint(profile: dict[str, Any], output_dir: Path, root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    qa_dir = output_dir / "qa"
    visible_text_path = qa_dir / "visible_text_for_lint.txt"
    visible_lines = collect_visible_text(profile)
    visible_text_path.write_text("\n".join(visible_lines) + "\n", encoding="utf-8")

    artifacts = [
        {"path": str(visible_text_path.resolve()), "category": "qa_visible_text", "title": "Visible text for lint"}
    ]
    lint_script = root / "scripts" / "visible_copy_lint.py"
    lint_report = qa_dir / "visible_copy_lint.json"
    capsule_violations = capsule_visible_copy_policy_violations(visible_lines)
    if capsule_violations:
        status = {
            "requested": True,
            "success": False,
            "capsule_policy_violations": capsule_violations,
        }
        lint_report.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        artifacts.append({"path": str(lint_report.resolve()), "category": "qa_report", "title": "Visible copy lint report"})
        raise SystemExit(f"capsule visible copy policy failed; see {lint_report}")

    if not lint_script.exists():
        status = {"requested": False, "success": False, "reason": f"lint script not found: {lint_script}"}
        lint_report.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        artifacts.append({"path": str(lint_report.resolve()), "category": "qa_report", "title": "Visible copy lint report"})
        return artifacts, status

    proc = run([sys.executable, str(lint_script), str(visible_text_path), "--json"], check=False)
    report_text = proc.stdout.strip() or json.dumps(
        {"ok": proc.returncode == 0, "stderr": proc.stderr.strip()},
        ensure_ascii=False,
        indent=2,
    )
    lint_report.write_text(report_text + "\n", encoding="utf-8")
    artifacts.append({"path": str(lint_report.resolve()), "category": "qa_report", "title": "Visible copy lint report"})
    status = {"requested": True, "success": proc.returncode == 0, "report": str(lint_report.resolve())}
    if proc.returncode != 0:
        raise SystemExit(f"visible copy lint failed; see {lint_report}\n{proc.stdout}{proc.stderr}")
    return artifacts, status


def render_video(profile: dict[str, Any], output_dir: Path, root: Path, params_path: Path, topic: str) -> dict[str, Any]:
    release_dir = output_dir / "release"
    work_dir = output_dir / "work"
    frames_dir = work_dir / "frames"
    audio_dir = work_dir / "audio"
    qa_dir = output_dir / "qa"
    tmp_dir = work_dir / "tmp"
    for directory in (release_dir, frames_dir, audio_dir, qa_dir, tmp_dir):
        directory.mkdir(parents=True, exist_ok=True)

    scenes = profile.get("scenes") or []
    if not scenes:
        raise SystemExit("params profile must include scenes")

    reject_spoken_profile_fields(profile)
    validate_repo_signal_grid_profile(profile)
    visible_text_artifacts, visible_lint_status = write_visible_text_and_lint(profile, output_dir, root)
    animate_middle = bool(profile.get("animate_middle") or any(scene.get("animate_image") for scene in scenes))

    frames: list[Path] = []
    for idx, scene in enumerate(scenes, start=1):
        out = frames_dir / f"frame_{idx:02d}.png"
        render_frame(profile, scene, out, progress=0.5 if animate_middle else 0.0)
        frames.append(out)

    duration = float(profile.get("target_duration", 15))
    durations = compute_scene_durations(profile, scenes, duration)

    if animate_middle:
        visual = render_animated_visual(profile, scenes, durations, frames_dir, tmp_dir)
    else:
        concat = tmp_dir / "frames.txt"
        visual = tmp_dir / "visual.mp4"
        write_concat(frames, durations, concat)
        run([
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-vf",
            "fps=30,format=yuv420p",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(visual),
        ])

    base_video = tmp_dir / "base_audio.mp4"
    final_video = release_dir / "video.mp4"
    run(["ffmpeg", "-y", "-i", str(visual), "-c:v", "copy", "-an", "-movflags", "+faststart", str(base_video)])

    bgm_status: dict[str, Any] = {
        "requested": bool(profile.get("add_background_music", False)),
        "success": False,
        "title": profile.get("bgm_title") or profile.get("default_bgm_label") or profile.get("default_bgm_title") or "",
    }
    bgm_path = first_existing_bgm_path(profile) if bgm_status["requested"] else None
    if bgm_path:
        bgm_volume = float(profile.get("bgm_volume", 0.85))
        mix_background_music(base_video, bgm_path, final_video, bgm_volume)
        bgm_status.update({"success": True, "path": str(bgm_path), "volume": bgm_volume})
    else:
        run(["ffmpeg", "-y", "-i", str(base_video), "-c", "copy", "-movflags", "+faststart", str(final_video)])
        if bgm_status["requested"]:
            bgm_status["reason"] = "No local licensed BGM path supplied via bgm_path/background_music_path/CAPSULE_BGM_PATH."

    copy_path = release_dir / "copy.txt"
    copy_path.write_text(profile.get("copy", profile.get("top_title", "")) + "\n", encoding="utf-8")
    prompt_artifacts = write_prompt_snapshots(profile, output_dir, params_path, topic)
    run_notes = {
        "ok": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "audio_route": "optional_user_supplied_bgm",
        "bgm_status": bgm_status,
        "visible_copy_lint": visible_lint_status,
        "frame_count": len(frames),
        "animate_middle": animate_middle,
        "duration": ffprobe_duration(final_video),
    }
    run_notes_path = qa_dir / "run_notes.json"
    run_notes_path.write_text(json.dumps(run_notes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "artifacts": [
            {"path": str(final_video.resolve()), "category": "final_video", "title": "Final video"},
            {"path": str(copy_path.resolve()), "category": "copywriting", "title": "Copywriting"},
            {"path": str(run_notes_path.resolve()), "category": "run_notes", "title": "Run notes"},
            *visible_text_artifacts,
            *prompt_artifacts,
        ]
    }
    (output_dir / "artifact_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return run_notes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", default="")
    parser.add_argument("--params", required=True, help="Path to repo showcase profile JSON.")
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = find_project_root()
    params_path = Path(args.params).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    profile = json.loads(params_path.read_text(encoding="utf-8"))
    if args.topic and "topic" not in profile:
        profile["topic"] = args.topic
    render_video(profile, output_dir, root, params_path, args.topic or profile.get("topic", ""))


if __name__ == "__main__":
    main()
