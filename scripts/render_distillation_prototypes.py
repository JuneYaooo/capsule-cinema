#!/usr/bin/env python3
"""Render local rhythm prototypes from the account-distillation playbook."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "output" / "account_distillation_video_prototypes"
RELEASE = PROJECT / "release" / "v1_structure_prototypes"
PUBLIC = RELEASE / "public"
INTERNAL = RELEASE / "internal"
QA = RELEASE / "qa"
TECHNICAL = RELEASE / "technical"
WIDTH = 720
HEIGHT = 1280
FPS = 24


FONT_CANDIDATES = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


FONTS = {
    "tiny": font(24),
    "small": font(30),
    "body": font(38),
    "mid": font(48),
    "large": font(64),
    "hero": font(82),
    "num": font(110),
}


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    mode: str
    title: str
    subtitle: str
    bullets: tuple[str, ...] = ()
    badge: str = ""


@dataclass(frozen=True)
class Prototype:
    slug: str
    title: str
    lane: str
    duration: float
    palette: tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]
    segments: tuple[Segment, ...]
    source_pattern: str
    public_caption: str


PROTOTYPES = [
    Prototype(
        slug="tool_list_structure_prototype",
        title="职场人必收的8个免费AI工具",
        lane="tool_list",
        duration=34,
        palette=((12, 18, 24), (30, 132, 109), (240, 197, 76)),
        source_pattern="工具榜单：0s榜单承诺 -> 5s内第一结果 -> 多工具循环 -> 清单承接",
        public_caption="职场工具榜单样片：先给结果，再给工具和限制。适合评论区承接工具清单、模板和提示词。",
        segments=(
            Segment(0, 3, "hero", "2026年", "职场人最该收藏的 8 个 AI 工具", badge="先看第一个效果"),
            Segment(3, 8, "proof", "会议录音", "3秒变成纪要和待办", ("上传录音", "自动摘要", "生成行动项"), "结果先出来"),
            Segment(8, 13, "loop", "工具 01", "会议纪要自动整理", ("痛点：会后没人想补记录", "证明：摘要、责任人、截止时间"), "可收藏"),
            Segment(13, 18, "loop", "工具 02", "PPT 一键重排", ("输入：杂乱大纲", "输出：标题、版式、配色"), "看前后对比"),
            Segment(18, 23, "loop", "工具 03", "Excel 批量处理", ("输入：混乱表格", "输出：脚本和成品"), "省重复劳动"),
            Segment(23, 28, "loop", "工具 04", "素材去重和命名", ("文件夹丢进去", "重复图和命名表出来"), "运营可用"),
            Segment(28, 31, "warning", "发布前先查三件事", "免费额度、是否免登录、结果能否复用", ("别只讲好处", "把限制讲清楚"), "避坑"),
            Segment(31, 34, "close", "清单放评论区", "模板、提示词、测试截图一起给", ("收藏前先看限制",), "承接动作"),
        ),
    ),
    Prototype(
        slug="open_source_radar_structure_prototype",
        title="这个开源项目让12个Agent先替你审稿",
        lane="open_source_radar",
        duration=35,
        palette=((16, 19, 31), (87, 113, 225), (238, 118, 95)),
        source_pattern="开源雷达：项目能力/热度 -> README或Demo证明 -> 适合谁 -> 运行门槛",
        public_caption="开源项目雷达样片：不要只报星标，前8秒必须把项目能力和可运行证据放出来。",
        segments=(
            Segment(0, 3, "hero", "这个开源项目", "让 12 个 Agent 先替你审稿", badge="不是只报星标"),
            Segment(3, 8, "repo", "README 证明", "规划、审核、修改分开跑", ("任务拆解", "过程可追踪", "方案不行先拦下"), "先给证据"),
            Segment(8, 13, "terminal", "输入一个选题", "系统先拆成 3 个子任务", ("写脚本", "查风险", "补素材"), "看流程"),
            Segment(13, 18, "diagram", "为什么值得收藏", "它解决的是多人协作失控", ("不是聊天更聪明", "而是过程能被审计"), "任务翻译"),
            Segment(18, 24, "demo", "适合谁用", "做短视频、写方案、跑资料整理的人", ("需要批量", "需要复盘", "需要避免瞎跑"), "人群明确"),
            Segment(24, 30, "caveat", "别急着照搬", "先确认安装、模型、数据权限", ("本地能不能跑", "费用怎么算", "私密资料能不能上传"), "限制"),
            Segment(30, 35, "close", "评论区给安装笔记", "包括环境、配置和失败截图", ("能复现再推荐",), "链接承接"),
        ),
    ),
    Prototype(
        slug="office_formula_structure_prototype",
        title="AI做PPT总翻车，是因为需求没说清",
        lane="office_formula",
        duration=32,
        palette=((24, 24, 22), (219, 87, 73), (88, 178, 132)),
        source_pattern="办公公式：失败结果 -> 公式拆解 -> 执行画面 -> 成品对比 -> 模板承接",
        public_caption="AI办公公式样片：从翻车痛点开场，用公式和前后对比证明价值，最后承接模板。",
        segments=(
            Segment(0, 3, "hero", "AI做PPT总翻车", "不是工具不行，是需求没说清", badge="先看错误结果"),
            Segment(3, 7, "bad_good", "错误提示词", "帮我做一页高级感PPT", ("结果：空话多、版式乱、重点散",), "翻车"),
            Segment(7, 12, "formula", "换成 5 格公式", "对象、材料、版式、限制、输出", ("别只说高级感", "说清谁看、放什么、怎么交付"), "公式"),
            Segment(12, 18, "screen", "把真实材料塞进去", "产品截图、数据、结论一句话", ("先给素材", "再让 AI 排版"), "执行"),
            Segment(18, 24, "compare", "前后对比", "从一页空话变成可汇报页面", ("标题能读懂", "数据有位置", "结论在第一屏"), "结果"),
            Segment(24, 29, "recap", "这类选题为什么能爆", "因为观众马上能拿去改自己的文件", ("收藏理由明确", "评论会要模板"), "可复用"),
            Segment(29, 32, "close", "模板放评论区", "直接替换你的材料就能用", ("先试一页，不要全套重做",), "承接"),
        ),
    ),
]


def ensure_dirs() -> None:
    for path in (PUBLIC, INTERNAL, QA, TECHNICAL):
        path.mkdir(parents=True, exist_ok=True)


def ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) * (1 - x)


def blend(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if text_size(draw, candidate, fnt)[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int] = (245, 245, 238),
    max_width: int | None = None,
    line_gap: int = 12,
) -> int:
    x, y = xy
    lines = wrap_text(draw, text, fnt, max_width) if max_width else text.split("\n")
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += text_size(draw, line, fnt)[1] + line_gap
    return y


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: tuple[int, int, int], outline=None, radius=24, width=2) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def background(proto: Prototype, t: float) -> Image.Image:
    base, accent, warm = proto.palette
    img = Image.new("RGB", (WIDTH, HEIGHT), base)
    px = img.load()
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        color = blend(base, blend(accent, warm, 0.18), ratio * 0.28)
        for x in range(WIDTH):
            px[x, y] = color
    draw = ImageDraw.Draw(img)
    for i in range(0, WIDTH, 48):
        shade = blend(base, accent, 0.16)
        draw.line((i, 0, i - 120, HEIGHT), fill=shade, width=1)
    progress_x = int((WIDTH + 160) * ((t * 0.03) % 1)) - 80
    draw.rectangle((progress_x, 0, progress_x + 8, HEIGHT), fill=blend(accent, warm, 0.38))
    return img


def draw_header(draw: ImageDraw.ImageDraw, proto: Prototype, t_global: float, seg: Segment) -> None:
    base, accent, warm = proto.palette
    draw.text((44, 38), proto.lane.replace("_", " ").upper(), font=FONTS["tiny"], fill=blend(warm, (255, 255, 255), 0.2))
    draw.text((44, 72), proto.title, font=FONTS["small"], fill=(230, 233, 225))
    progress = min(1, max(0, t_global / proto.duration))
    draw.rounded_rectangle((44, 118, WIDTH - 44, 128), radius=5, fill=blend(base, (255, 255, 255), 0.18))
    draw.rounded_rectangle((44, 118, int(44 + (WIDTH - 88) * progress), 128), radius=5, fill=warm)
    if seg.badge:
        bw = min(300, 26 * len(seg.badge) + 42)
        rounded(draw, (WIDTH - bw - 44, 42, WIDTH - 44, 92), blend(accent, warm, 0.38), radius=18)
        draw.text((WIDTH - bw - 22, 54), seg.badge, font=FONTS["tiny"], fill=(255, 255, 248))


def bullet_items(bullets: tuple[str, ...] | str) -> tuple[str, ...]:
    if isinstance(bullets, str):
        return (bullets,)
    return bullets


def draw_bullets(draw: ImageDraw.ImageDraw, bullets: tuple[str, ...] | str, y: int, accent: tuple[int, int, int], warm: tuple[int, int, int]) -> None:
    for idx, item in enumerate(bullet_items(bullets)):
        yy = y + idx * 72
        rounded(draw, (54, yy, WIDTH - 54, yy + 54), blend(accent, (0, 0, 0), 0.28), radius=16)
        draw.ellipse((76, yy + 17, 96, yy + 37), fill=warm)
        draw.text((112, yy + 11), item, font=FONTS["small"], fill=(245, 245, 238))


def draw_mock_ui(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, lines: list[str], accent: tuple[int, int, int], warm: tuple[int, int, int], phase: float) -> None:
    x1, y1, x2, y2 = box
    rounded(draw, box, (236, 238, 230), radius=24)
    rounded(draw, (x1, y1, x2, y1 + 68), (37, 41, 45), radius=24)
    draw.text((x1 + 28, y1 + 18), title, font=FONTS["small"], fill=(250, 248, 238))
    for i in range(3):
        draw.ellipse((x2 - 110 + i * 30, y1 + 24, x2 - 94 + i * 30, y1 + 40), fill=blend(accent, warm, i / 3))
    y = y1 + 104
    for idx, line in enumerate(lines):
        w = int((x2 - x1 - 88) * (0.52 + 0.42 * min(1, phase + idx * 0.16)))
        rounded(draw, (x1 + 34, y, x1 + 34 + w, y + 34), blend(accent, (255, 255, 255), 0.76), radius=10)
        draw.text((x1 + 48, y + 3), line, font=FONTS["tiny"], fill=(24, 28, 31))
        y += 56


def draw_mode(draw: ImageDraw.ImageDraw, proto: Prototype, seg: Segment, local_t: float) -> None:
    base, accent, warm = proto.palette
    p = ease(local_t / max(0.1, seg.end - seg.start))
    title_y = 180
    if seg.mode == "hero":
        num = seg.title
        draw.text((54, 208), num, font=FONTS["hero"], fill=warm)
        draw_text(draw, (54, 324), seg.subtitle, FONTS["large"], max_width=WIDTH - 108, fill=(250, 250, 242), line_gap=18)
        rounded(draw, (54, 790, WIDTH - 54, 1010), blend(accent, (0, 0, 0), 0.22), radius=28)
        draw.text((84, 834), "0-3秒只做一件事", font=FONTS["body"], fill=(255, 255, 248))
        draw.text((84, 900), "给观众一个马上能懂的理由", font=FONTS["mid"], fill=warm)
    elif seg.mode == "proof":
        draw_text(draw, (54, title_y), seg.title, FONTS["large"], fill=warm, max_width=WIDTH - 108)
        draw_text(draw, (54, 290), seg.subtitle, FONTS["mid"], max_width=WIDTH - 108)
        draw_mock_ui(draw, (56, 470, WIDTH - 56, 850), "DEMO RESULT", list(bullet_items(seg.bullets)), accent, warm, p)
        draw_bullets(draw, ("第5秒前出现结果", "不是先解释工具"), 910, accent, warm)
    elif seg.mode in {"loop", "screen", "terminal", "repo", "demo"}:
        draw.text((54, title_y), seg.title, font=FONTS["large"], fill=warm)
        draw_text(draw, (54, 278), seg.subtitle, FONTS["mid"], fill=(250, 250, 242), max_width=WIDTH - 108)
        draw_mock_ui(draw, (54, 440, WIDTH - 54, 820), "SCREEN PROOF", list(bullet_items(seg.bullets)), accent, warm, p)
        y = 890
        for label, value in (("痛点", "一句话说清"), ("证明", "画面马上给"), ("承接", "清单或模板")):
            rounded(draw, (54, y, WIDTH - 54, y + 78), blend(base, (255, 255, 255), 0.12), outline=blend(accent, warm, 0.25), radius=18)
            draw.text((80, y + 19), label, font=FONTS["small"], fill=warm)
            draw.text((188, y + 18), value, font=FONTS["small"], fill=(244, 244, 236))
            y += 96
    elif seg.mode == "diagram":
        draw_text(draw, (54, title_y), seg.title, FONTS["large"], fill=warm, max_width=WIDTH - 108)
        draw_text(draw, (54, 292), seg.subtitle, FONTS["mid"], fill=(250, 250, 242), max_width=WIDTH - 108)
        centers = [(180, 620), (360, 500), (540, 620), (360, 760)]
        labels = ["规划", "审核", "修改", "交付"]
        for a, b in zip(centers, centers[1:] + centers[:1]):
            draw.line((a[0], a[1], b[0], b[1]), fill=warm, width=6)
        for (cx, cy), label in zip(centers, labels):
            draw.ellipse((cx - 78, cy - 78, cx + 78, cy + 78), fill=blend(accent, (255, 255, 255), 0.1), outline=warm, width=4)
            tw, th = text_size(draw, label, FONTS["body"])
            draw.text((cx - tw / 2, cy - th / 2), label, font=FONTS["body"], fill=(255, 255, 245))
        draw_bullets(draw, seg.bullets, 910, accent, warm)
    elif seg.mode == "bad_good":
        draw.text((54, title_y), seg.title, font=FONTS["large"], fill=warm)
        draw_text(draw, (54, 286), seg.subtitle, FONTS["mid"], fill=(250, 250, 242), max_width=WIDTH - 108)
        rounded(draw, (54, 442, WIDTH - 54, 650), (244, 231, 221), radius=24)
        draw.text((82, 478), "空话多", font=FONTS["mid"], fill=(142, 38, 38))
        draw.text((82, 548), "重点散", font=FONTS["mid"], fill=(142, 38, 38))
        rounded(draw, (54, 704, WIDTH - 54, 918), (226, 245, 230), radius=24)
        draw.text((82, 740), "对象明确", font=FONTS["mid"], fill=(32, 98, 72))
        draw.text((82, 810), "材料到位", font=FONTS["mid"], fill=(32, 98, 72))
        draw_bullets(draw, seg.bullets, 990, accent, warm)
    elif seg.mode == "formula":
        draw.text((54, title_y), seg.title, font=FONTS["large"], fill=warm)
        draw_text(draw, (54, 286), seg.subtitle, FONTS["mid"], fill=(250, 250, 242), max_width=WIDTH - 108)
        items = ["对象", "材料", "版式", "限制", "输出"]
        for i, item in enumerate(items):
            x = 74 + (i % 2) * 292
            y = 464 + (i // 2) * 142
            rounded(draw, (x, y, x + 252, y + 96), blend(accent, warm, i / 8), radius=18)
            draw.text((x + 56, y + 24), item, font=FONTS["mid"], fill=(255, 255, 245))
        draw_bullets(draw, seg.bullets, 900, accent, warm)
    elif seg.mode == "compare":
        draw.text((54, title_y), seg.title, font=FONTS["large"], fill=warm)
        draw_text(draw, (54, 286), seg.subtitle, FONTS["mid"], fill=(250, 250, 242), max_width=WIDTH - 108)
        rounded(draw, (50, 446, 340, 900), (239, 224, 214), radius=22)
        rounded(draw, (380, 446, 670, 900), (222, 246, 231), radius=22)
        draw.text((88, 492), "之前", font=FONTS["mid"], fill=(138, 45, 42))
        draw.text((418, 492), "之后", font=FONTS["mid"], fill=(34, 94, 70))
        for i in range(5):
            draw.rectangle((88, 590 + i * 48, 276 - i * 10, 610 + i * 48), fill=(190, 140, 130))
            draw.rectangle((418, 590 + i * 48, 616, 610 + i * 48), fill=(82, 160, 119))
        draw_bullets(draw, seg.bullets, 964, accent, warm)
    else:
        draw.text((54, title_y), seg.title, font=FONTS["large"], fill=warm)
        draw_text(draw, (54, 288), seg.subtitle, FONTS["mid"], fill=(250, 250, 242), max_width=WIDTH - 108)
        draw_bullets(draw, seg.bullets or ("先验证，再发布",), 520, accent, warm)
        rounded(draw, (54, 930, WIDTH - 54, 1100), blend(accent, (0, 0, 0), 0.2), radius=26)
        draw.text((86, 972), "结尾必须接住动作", font=FONTS["mid"], fill=(255, 255, 244))
        draw.text((86, 1042), "清单 / 模板 / 安装笔记", font=FONTS["body"], fill=warm)


def render_frame(proto: Prototype, t: float) -> Image.Image:
    seg = next(item for item in proto.segments if item.start <= t < item.end or math.isclose(t, proto.duration))
    local_t = t - seg.start
    img = background(proto, t)
    draw = ImageDraw.Draw(img)
    draw_header(draw, proto, t, seg)
    draw_mode(draw, proto, seg, local_t)
    return img


def transcode_h264(src: Path, dst: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        src.rename(dst)
        return
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(dst),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    src.unlink(missing_ok=True)


def render_video(proto: Prototype) -> Path:
    temp = TECHNICAL / f"{proto.slug}_raw.mp4"
    final = PUBLIC / f"{proto.slug}.mp4"
    writer = cv2.VideoWriter(str(temp), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    total_frames = int(proto.duration * FPS)
    for frame_index in range(total_frames):
        t = frame_index / FPS
        frame = render_frame(proto, t)
        writer.write(cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2BGR))
    writer.release()
    transcode_h264(temp, final)
    return final


def make_contact_sheet(proto: Prototype) -> Path:
    times = [0, 3, 8, proto.duration * 0.52, proto.duration - 1]
    thumbs = []
    for t in times:
        frame = render_frame(proto, min(t, proto.duration - 0.01))
        frame.thumbnail((180, 320))
        thumbs.append(frame.copy())
    sheet = Image.new("RGB", (180 * len(thumbs), 360), (28, 30, 32))
    draw = ImageDraw.Draw(sheet)
    for idx, thumb in enumerate(thumbs):
        x = idx * 180
        sheet.paste(thumb, (x, 0))
        draw.text((x + 12, 326), f"t={times[idx]:.0f}s", font=FONTS["tiny"], fill=(245, 245, 238))
    path = QA / f"{proto.slug}_contact_sheet.jpg"
    sheet.save(path, quality=92)
    return path


def ffprobe(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def write_text_artifacts(videos: dict[str, Path], sheets: dict[str, Path]) -> None:
    storyboard = {
        "release": "v1_structure_prototypes",
        "purpose": "Validate topic, opening, rhythm, and script structure before narrated production.",
        "format": {"width": WIDTH, "height": HEIGHT, "fps": FPS, "audio": "none"},
        "prototypes": [
            {
                "slug": proto.slug,
                "title": proto.title,
                "lane": proto.lane,
                "duration": proto.duration,
                "source_pattern": proto.source_pattern,
                "segments": [seg.__dict__ for seg in proto.segments],
                "video": str(videos[proto.slug].relative_to(RELEASE)),
                "contact_sheet": str(sheets[proto.slug].relative_to(RELEASE)),
            }
            for proto in PROTOTYPES
        ],
    }
    (INTERNAL / "storyboards.json").write_text(json.dumps(storyboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    public_copy = [
        "# Platform Copy",
        "",
        "这些是无旁白结构样片，用来检查选题、开场、节奏和脚本骨架。正式发布前需要替换为真实工具证明、真实录屏和配音。",
        "",
    ]
    for proto in PROTOTYPES:
        public_copy.extend([
            f"## {proto.title}",
            proto.public_caption,
            "",
        ])
    (PUBLIC / "platform_copy.md").write_text("\n".join(public_copy), encoding="utf-8")


def write_release_docs(videos: dict[str, Path], sheets: dict[str, Path], probes: dict[str, dict]) -> None:
    manifest = {
        "release": "v1_structure_prototypes",
        "project": "account_distillation_video_prototypes",
        "status": "prototype",
        "notes": "Silent local-rendered rhythm prototypes. TTS/BGM credentials were unavailable in the local environment.",
        "artifacts": [
            {"category": "final_video", "id": slug, "path": str(path.relative_to(RELEASE))}
            for slug, path in videos.items()
        ]
        + [
            {"category": "review_contact_sheet", "id": slug, "path": str(path.relative_to(RELEASE))}
            for slug, path in sheets.items()
        ]
        + [
            {"category": "copywriting", "path": "public/platform_copy.md"},
            {"category": "storyboard", "path": "internal/storyboards.json"},
            {"category": "qa_report", "path": "qa/local_video_qa_batch.json"},
        ],
    }
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    (RELEASE / "release_manifest.json").write_text(manifest_text, encoding="utf-8")
    (RELEASE / "artifact_manifest.json").write_text(manifest_text, encoding="utf-8")
    (TECHNICAL / "ffprobe_batch.json").write_text(json.dumps(probes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme_lines = [
        "# v1 Structure Prototypes",
        "",
        "Three silent 9:16 rhythm prototypes generated from the AI tools/open-source account distillation package.",
        "",
        "Use these to judge topic promise, first-8-second proof, loop rhythm, and script structure before making narrated versions.",
        "",
        "## Public Videos",
    ]
    for proto in PROTOTYPES:
        readme_lines.append(f"- `{videos[proto.slug].relative_to(RELEASE)}` - {proto.title}")
    readme_lines.extend([
        "",
        "## Known Limits",
        "- No TTS or BGM: MiniMax/Doubao/Suno credentials are not set in this environment.",
        "- Proof screens are local mockups. Replace with verified live tool UI before publishing.",
        "- These are structure tests, not final platform-ready videos.",
        "",
    ])
    (RELEASE / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")
    (PROJECT / "CURRENT_RELEASE.md").write_text(
        "\n".join([
            "# Current Release",
            "",
            "Current prototype release: `release/v1_structure_prototypes/`.",
            "",
            "Use the MP4 files in `public/` for review. They are silent structure prototypes and should not be published as final videos without real proof footage and narration.",
            "",
        ]),
        encoding="utf-8",
    )


def main() -> None:
    ensure_dirs()
    videos: dict[str, Path] = {}
    sheets: dict[str, Path] = {}
    probes: dict[str, dict] = {}
    qa_checks = []
    for proto in PROTOTYPES:
        video = render_video(proto)
        sheet = make_contact_sheet(proto)
        probe = ffprobe(video)
        streams = probe.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        duration = float((probe.get("format") or {}).get("duration", 0))
        ok = width == WIDTH and height == HEIGHT and duration >= proto.duration - 0.2
        qa_checks.append({
            "id": proto.slug,
            "ok": ok,
            "width": width,
            "height": height,
            "duration": duration,
            "expected_duration": proto.duration,
            "has_audio": any(s.get("codec_type") == "audio" for s in streams),
        })
        videos[proto.slug] = video
        sheets[proto.slug] = sheet
        probes[proto.slug] = probe
    write_text_artifacts(videos, sheets)
    (QA / "local_video_qa_batch.json").write_text(json.dumps({"ok": all(item["ok"] for item in qa_checks), "checks": qa_checks}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_release_docs(videos, sheets, probes)
    print(json.dumps({"release": str(RELEASE), "videos": {k: str(v) for k, v in videos.items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
