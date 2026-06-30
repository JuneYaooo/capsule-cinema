#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


FPS = 30
SUPPORTED_ASPECTS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "3:4": (1080, 1440),
}
DEFAULT_SERIES_TITLE = "每天一个模拟人生"
DEFAULT_SUBTITLE = "摇出今天的人生"
DEFAULT_DRAW_LABEL = "今天抽到"
DEFAULT_CANDIDATES = ["夜班英雄", "省钱大师", "小镇传说", "反转人生", "好运错觉"]
DEFAULT_FONT_BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"
DEFAULT_FONT_REGULAR = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def ffprobe_duration(path: Path) -> float:
    raw = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    ).strip()
    return float(raw)


def parse_candidates(raw: str) -> list[str]:
    if not raw:
        return DEFAULT_CANDIDATES
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            terms = [str(item).strip() for item in value if str(item).strip()]
            return terms or DEFAULT_CANDIDATES
    except json.JSONDecodeError:
        pass
    terms = [item.strip() for item in raw.replace("，", ",").split(",") if item.strip()]
    return terms or DEFAULT_CANDIDATES


def candidate_terms_for_display(candidate_terms: list[str]) -> list[str]:
    if not candidate_terms:
        return list(DEFAULT_CANDIDATES)
    return list(candidate_terms[:6])


def split_topic(topic: str, result_title: str, result_tail: str) -> tuple[str, str]:
    if result_title:
        return result_title, result_tail
    clean = topic.strip()
    if clean.endswith("的一生"):
        return clean[:-3], "的一生"
    return clean, result_tail


class Renderer:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.size = SUPPORTED_ASPECTS[args.aspect_ratio]
        self.is_vertical = args.aspect_ratio != "16:9"
        self.accent = tuple(args.accent)
        self.accent2 = tuple(args.accent2)
        self.font_bold_path = args.font_bold
        self.font_regular_path = args.font_regular

    def font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        path = self.font_bold_path if bold else self.font_regular_path
        return ImageFont.truetype(path, size=size)

    @staticmethod
    def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
        box = draw.textbbox((0, 0), text, font=font, stroke_width=0)
        return box[2] - box[0], box[3] - box[1]

    @staticmethod
    def alpha(layer: Image.Image, amount: float) -> Image.Image:
        amount = max(0.0, min(1.0, amount))
        if amount >= 0.999:
            return layer
        out = layer.copy()
        out.putalpha(out.getchannel("A").point(lambda p: int(p * amount)))
        return out

    def add_text(
        self,
        layer: Image.Image,
        xy: tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont,
        *,
        fill=(255, 255, 255, 255),
        anchor: str | None = None,
        stroke: int = 3,
        stroke_fill=(0, 0, 0, 185),
    ) -> None:
        draw = ImageDraw.Draw(layer)
        draw.text(xy, text, font=font, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=stroke_fill)

    def rounded_panel(
        self,
        draw: ImageDraw.ImageDraw,
        xy: tuple[int, int, int, int],
        radius: int,
        fill,
        outline=None,
        width: int = 1,
    ) -> None:
        draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)

    def make_cover(self) -> Image.Image:
        w, h = self.size
        bg = Image.open(self.args.background).convert("RGB")
        scale = max(w / bg.width, h / bg.height) * 1.13
        resized = bg.resize((math.ceil(bg.width * scale), math.ceil(bg.height * scale)), Image.Resampling.LANCZOS)
        return resized.convert("RGBA")

    def crop_motion(self, cover: Image.Image, t: float, duration: float) -> Image.Image:
        w, h = self.size
        zoom = 1.0 + 0.032 * (t / duration)
        crop_w = int(w / zoom)
        crop_h = int(h / zoom)
        if 0.55 <= t <= 2.10:
            sx = math.sin(t * 83.0) * 13 + math.sin(t * 37.0) * 6
            sy = math.cos(t * 79.0) * 10 + math.sin(t * 45.0) * 4
        else:
            sx = math.sin(t * 1.7) * 7
            sy = math.cos(t * 1.35) * 5
        cx = cover.width / 2 + sx
        cy = cover.height / 2 + sy
        left = int(max(0, min(cover.width - crop_w, cx - crop_w / 2)))
        top = int(max(0, min(cover.height - crop_h, cy - crop_h / 2)))
        return cover.crop((left, top, left + crop_w, top + crop_h)).resize((w, h), Image.Resampling.LANCZOS)

    def make_title_layer(self) -> Image.Image:
        w, h = self.size
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        top_h = int(h * (0.205 if self.is_vertical else 0.18))
        for y in range(top_h):
            draw.line([(0, y), (w, y)], fill=(0, 0, 0, int(150 * (1 - y / top_h))))

        title_font = self.font(78 if self.is_vertical else 82, bold=True)
        subtitle_font = self.font(36 if self.is_vertical else 36)
        badge_font = self.font(31 if self.is_vertical else 31, bold=True)
        title_x = w // 2 if self.is_vertical else int(w * 0.32)
        title_y = 110 if self.is_vertical else 78
        _, title_h = self.text_size(draw, self.args.series_title, title_font)

        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        gdraw.text(
            (title_x, title_y),
            self.args.series_title,
            font=title_font,
            anchor="mm",
            fill=(*self.accent, 160),
            stroke_width=8,
            stroke_fill=(*self.accent2, 120),
        )
        layer.alpha_composite(glow.filter(ImageFilter.GaussianBlur(7)))
        self.add_text(layer, (title_x, title_y), self.args.series_title, title_font, anchor="mm", stroke=4)
        self.add_text(
            layer,
            (title_x, title_y + int(title_h * 0.85)),
            self.args.subtitle,
            subtitle_font,
            anchor="mm",
            fill=(*self.accent, 255),
            stroke=2,
        )

        badge = self.args.badge_text
        badge_w, badge_h = self.text_size(draw, badge, badge_font)
        badge_x = int(w * (0.075 if self.is_vertical else 0.055))
        badge_y = int(h * (0.045 if self.is_vertical else 0.055))
        self.rounded_panel(
            draw,
            (badge_x, badge_y, badge_x + badge_w + 38, badge_y + badge_h + 22),
            10,
            (0, 0, 0, 126),
            (*self.accent, 215),
            2,
        )
        self.add_text(layer, (badge_x + 19, badge_y + 10), badge, badge_font, fill=(255, 255, 255, 235), stroke=1)
        return layer

    def make_chips_layer(self, t: float) -> Image.Image:
        w, h = self.size
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        chip_font = self.font(34 if self.is_vertical else 38, bold=True)
        base_positions = (
            [(90, 285), (560, 245), (105, 440), (555, 420), (160, h - 380), (590, h - 410)]
            if self.is_vertical
            else [(940, 130), (1240, 235), (940, 815), (1260, 710), (1490, 420), (950, 545)]
        )
        terms = candidate_terms_for_display(self.args.candidate_terms)
        for index, chip in enumerate(terms):
            x, y = base_positions[index]
            x += int(math.sin(t * 7.5 + index * 1.7) * (22 if self.is_vertical else 28))
            y += int(math.cos(t * 6.5 + index * 1.1) * 14)
            text_w, text_h = self.text_size(draw, chip, chip_font)
            pad_x, pad_y = 24, 13
            outline = (*self.accent2, 185) if index % 2 else (*self.accent, 185)
            self.rounded_panel(
                draw,
                (x, y, x + text_w + pad_x * 2 + 15, y + text_h + pad_y * 2),
                18,
                (0, 0, 0, 125),
                outline,
                2,
            )
            draw.ellipse((x + 9, y + 11, x + 28, y + 30), fill=outline)
            self.add_text(layer, (x + pad_x + 15, y + pad_y - 2), chip, chip_font, fill=(255, 255, 255, 238), stroke=2)
        return layer

    def draw_vignette(self, frame: Image.Image) -> None:
        w, h = self.size
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        band = max(80, int(h * 0.11))
        for y in range(band):
            draw.line([(0, y), (w, y)], fill=(0, 0, 0, int(95 * (1 - y / band))))
            draw.line([(0, h - 1 - y), (w, h - 1 - y)], fill=(0, 0, 0, int(85 * (1 - y / band))))
        side = max(80, int(w * 0.08))
        for x in range(side):
            a = int(65 * (1 - x / side))
            draw.line([(x, 0), (x, h)], fill=(0, 0, 0, a))
            draw.line([(w - 1 - x, 0), (w - 1 - x, h)], fill=(0, 0, 0, a))
        frame.alpha_composite(overlay)

    def draw_speed_lines(self, frame: Image.Image, t: float) -> None:
        if not 0.55 <= t <= 2.1:
            return
        w, h = self.size
        draw = ImageDraw.Draw(frame)
        pulse = 0.55 + 0.45 * abs(math.sin(t * 18))
        for index in range(10):
            offset = (t * 900 + index * 191) % (w + h)
            x1 = int(offset - h * 0.42)
            y1 = int(index * h / 10 + math.sin(t * 9 + index) * 36)
            x2 = x1 + int(w * 0.18)
            y2 = y1 - int(h * 0.035)
            color = self.accent if index % 2 == 0 else self.accent2
            draw.line([(x1, y1), (x2, y2)], fill=(*color, int(145 * pulse)), width=4)

    def draw_flash(self, frame: Image.Image, t: float) -> None:
        if 2.10 <= t <= 2.28:
            phase = max(0, min(1, 1 - abs((t - 2.19) / 0.09)))
            frame.alpha_composite(Image.new("RGBA", self.size, (255, 255, 255, int(115 * phase))))
        if 2.28 <= t <= 2.38:
            phase = 1 - (t - 2.28) / 0.10
            frame.alpha_composite(Image.new("RGBA", self.size, (*self.accent, int(50 * phase))))

    def draw_result_card(self, frame: Image.Image, t: float) -> None:
        if t < 2.08:
            return
        w, h = self.size
        card_w = 900 if self.is_vertical else 980
        card_h = 408 if self.is_vertical else 390
        final_x = (w - card_w) // 2 if self.is_vertical else int(w * 0.455)
        final_y = int(h * 0.642) if self.is_vertical else int(h * 0.535)
        start_x = final_x if self.is_vertical else int(w * 0.22)
        start_y = int(h * 0.91) if self.is_vertical else final_y + 12
        if t < 2.50:
            k = max(0, min(1, (t - 2.08) / 0.42))
            ease = 1 - (1 - k) ** 3
            x = int(start_x + (final_x - start_x) * ease)
            y = int(start_y + (final_y - start_y) * ease)
        else:
            bounce = math.sin((t - 2.50) * 17) * math.exp(-(t - 2.50) * 5.2)
            x = int(final_x + (0 if self.is_vertical else 12 * bounce))
            y = int(final_y + 16 * bounce)

        opacity = 1.0 if t >= 2.28 else (t - 2.08) / 0.20
        card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(card)
        glow = Image.new("RGBA", (card_w + 80, card_h + 80), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        gdraw.rounded_rectangle((40, 40, card_w + 40, card_h + 40), radius=34, fill=(*self.accent, 95))
        frame.alpha_composite(self.alpha(glow.filter(ImageFilter.GaussianBlur(22)), opacity), (x - 40, y - 40))

        self.rounded_panel(draw, (0, 0, card_w, card_h), 28, (8, 12, 25, 218), (*self.accent, 245), 4)
        self.rounded_panel(draw, (18, 18, card_w - 18, card_h - 18), 22, (255, 255, 255, 18), (*self.accent2, 135), 2)
        draw.line((38, 92, card_w - 38, 92), fill=(*self.accent, 180), width=2)

        label_font = self.font(38 if self.is_vertical else 36, bold=True)
        result_font = self.font(78 if self.is_vertical else 82, bold=True)
        tail_font = self.font(52 if self.is_vertical else 54, bold=True)
        self.add_text(card, (card_w // 2, 60 if self.is_vertical else 64), self.args.draw_label, label_font, fill=(*self.accent, 255), anchor="mm", stroke=2)
        self.add_text(card, (card_w // 2, 194 if self.is_vertical else 188), self.args.result_title, result_font, anchor="mm", stroke=5)
        if self.args.result_tail:
            self.add_text(card, (card_w // 2, 306 if self.is_vertical else 292), self.args.result_tail, tail_font, fill=(255, 238, 180, 255), anchor="mm", stroke=4)

        capsule_r = 19
        draw.ellipse((card_w - 78, 34, card_w - 40, 72), fill=(*self.accent2, 220), outline=(255, 255, 255, 180), width=2)
        draw.ellipse((38, card_h - 74, 38 + capsule_r * 2, card_h - 74 + capsule_r * 2), fill=(*self.accent, 220), outline=(255, 255, 255, 180), width=2)
        frame.alpha_composite(self.alpha(card, opacity), (x, y))

    def render_frames(self, frame_dir: Path, duration: float) -> None:
        cover = self.make_cover()
        title_layer = self.make_title_layer()
        frame_count = math.ceil(duration * FPS)
        for index in range(frame_count):
            t = index / FPS
            frame = self.crop_motion(cover, t, duration)
            self.draw_vignette(frame)
            self.draw_speed_lines(frame, t)
            if t >= 0.10:
                frame.alpha_composite(self.alpha(title_layer, min(1.0, (t - 0.10) / 0.24)))
            if 0.42 <= t <= 2.10:
                in_alpha = min(1.0, (t - 0.42) / 0.22)
                out_alpha = min(1.0, (2.10 - t) / 0.22)
                frame.alpha_composite(self.alpha(self.make_chips_layer(t), max(0.0, min(in_alpha, out_alpha, 0.88))))
            self.draw_flash(frame, t)
            self.draw_result_card(frame, t)
            frame.convert("RGB").save(frame_dir / f"{index:04d}.jpg", quality=93, subsampling=1)


def build_audio(args: argparse.Namespace, duration: float, temp_dir: Path) -> Path:
    tts_audio = Path(args.tts_audio).expanduser() if args.tts_audio else None
    sfx_audio = Path(args.sfx).expanduser() if args.sfx else None
    out = temp_dir / "opening_audio.wav"

    inputs: list[str] = []
    filters: list[str] = []
    mix_inputs: list[str] = []
    if tts_audio and tts_audio.is_file():
        inputs.extend(["-i", str(tts_audio)])
        delay = int(args.tts_start * 1000)
        filters.append(f"[0:a]adelay={delay}|{delay},volume={args.tts_volume}[tts]")
        mix_inputs.append("[tts]")
    if sfx_audio and sfx_audio.is_file():
        sfx_index = 1 if mix_inputs else 0
        fade_start = max(0.2, duration - 0.35)
        filters.append(f"[{sfx_index}:a]atrim=0:{duration},volume={args.sfx_volume},afade=t=out:st={fade_start}:d=0.30[sfx]")
        inputs.extend(["-i", str(sfx_audio)])
        mix_inputs.append("[sfx]")

    if not mix_inputs:
        run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=48000:cl=stereo",
                "-t",
                f"{duration}",
                str(out),
            ]
        )
        return out

    filters.append("".join(mix_inputs) + f"amix=inputs={len(mix_inputs)}:duration=longest:normalize=0,atrim=0:{duration},alimiter=limit=0.95[a]")
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            *inputs,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[a]",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(out),
        ]
    )
    return out


def render(args: argparse.Namespace) -> None:
    args.background = Path(args.background).expanduser()
    args.output = Path(args.output).expanduser()
    if not args.background.is_file():
        raise SystemExit(f"background not found: {args.background}")

    args.result_title, args.result_tail = split_topic(args.topic, args.result_title, args.result_tail)
    args.candidate_terms = parse_candidates(args.candidate_terms)
    duration = args.duration
    if args.tts_audio:
        duration = max(duration, ffprobe_duration(Path(args.tts_audio).expanduser()) + args.tts_start)
    duration = round(duration, 3)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="life_shaker_opening_") as raw_temp:
        temp_dir = Path(raw_temp)
        frame_dir = temp_dir / "frames"
        frame_dir.mkdir()
        Renderer(args).render_frames(frame_dir, duration)
        audio_path = build_audio(args, duration, temp_dir)
        run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-framerate",
                str(FPS),
                "-i",
                str(frame_dir / "%04d.jpg"),
                "-i",
                str(audio_path),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(FPS),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                "-shortest",
                str(args.output),
            ]
        )
        if args.keep_frames:
            keep_dir = args.output.parent / f"{args.output.stem}_frames"
            if keep_dir.exists():
                shutil.rmtree(keep_dir)
            shutil.copytree(frame_dir, keep_dir)

    if args.manifest:
        manifest_path = Path(args.manifest).expanduser()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "renderer": "life_shaker_opening_renderer",
                    "output": str(args.output),
                    "background": str(args.background),
                    "aspect_ratio": args.aspect_ratio,
                    "duration": duration,
                    "series_title": args.series_title,
                    "draw_label": args.draw_label,
                    "result_title": args.result_title,
                    "result_tail": args.result_tail,
                    "candidate_terms": args.candidate_terms,
                    "tts_audio": args.tts_audio,
                    "sfx": args.sfx,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def parse_rgb(raw: str) -> tuple[int, int, int]:
    parts = [int(item) for item in raw.split(",")]
    if len(parts) != 3 or any(item < 0 or item > 255 for item in parts):
        raise argparse.ArgumentTypeError("expected R,G,B values from 0 to 255")
    return tuple(parts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render the reusable life_sim life-object shaker opening.")
    parser.add_argument("--background", required=True, help="Shaker-machine background image for the selected aspect ratio.")
    parser.add_argument("--output", required=True, help="Output MP4 path.")
    parser.add_argument("--aspect-ratio", choices=sorted(SUPPORTED_ASPECTS), default="9:16")
    parser.add_argument("--topic", default="", help="Full topic phrase. Used only when --result-title is omitted.")
    parser.add_argument("--series-title", default=DEFAULT_SERIES_TITLE)
    parser.add_argument("--subtitle", default=DEFAULT_SUBTITLE)
    parser.add_argument("--badge-text", default="人生摇摇机")
    parser.add_argument("--draw-label", default=DEFAULT_DRAW_LABEL)
    parser.add_argument("--result-title", default="", help="Adapted identity/result text for this episode.")
    parser.add_argument("--result-tail", default="", help="Optional second result line, for example 的一生.")
    parser.add_argument("--candidate-terms", default="", help="JSON list or comma-separated visible candidate terms.")
    parser.add_argument("--tts-audio", default="", help="Optional opening TTS audio from the same voice system as the full story.")
    parser.add_argument("--tts-start", type=float, default=0.0)
    parser.add_argument("--tts-volume", type=float, default=1.28)
    parser.add_argument("--sfx", default="", help="Optional shaker-machine SFX audio.")
    parser.add_argument("--sfx-volume", type=float, default=0.35)
    parser.add_argument("--duration", type=float, default=3.75)
    parser.add_argument("--accent", type=parse_rgb, default=(255, 184, 83))
    parser.add_argument("--accent2", type=parse_rgb, default=(75, 170, 255))
    parser.add_argument("--font-bold", default=DEFAULT_FONT_BOLD)
    parser.add_argument("--font-regular", default=DEFAULT_FONT_REGULAR)
    parser.add_argument("--manifest", default="")
    parser.add_argument("--keep-frames", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.result_title and not args.topic:
        raise SystemExit("provide --result-title or --topic")
    render(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
