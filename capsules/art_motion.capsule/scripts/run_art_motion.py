#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def resolve_repo_root() -> Path:
    env_root = os.environ.get("CAPSULE_CINEMA_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    for candidate in [Path.cwd(), *Path(__file__).resolve().parents]:
        if (candidate / "scripts" / "local_video_qa.py").is_file() and (candidate / "lib").is_dir():
            return candidate.resolve()
    return Path(__file__).resolve().parents[2]


ROOT = resolve_repo_root()
if str(ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(ROOT / "lib"))

from src.config_registry import load_tool_capabilities  # noqa: E402


DEFAULT_IMAGE_TOOL = "VolcengineImageGeneratorTool"
DEFAULT_VIDEO_TOOL = "Seedance20VideoGeneratorTool"


def resolved_tool(params: dict[str, Any], role: str, default: str) -> str:
    tools = params.get("resolved_tools") if isinstance(params.get("resolved_tools"), dict) else {}
    return str(tools.get(role) or default).strip()


def tool_flags(tool_name: str) -> dict[str, Any]:
    record = load_tool_capabilities().get(tool_name) or {}
    provides = record.get("provides") if isinstance(record.get("provides"), dict) else {}
    return provides.get("flags") if isinstance(provides.get("flags"), dict) else {}


def tool_limits(tool_name: str) -> dict[str, Any]:
    record = load_tool_capabilities().get(tool_name) or {}
    provides = record.get("provides") if isinstance(record.get("provides"), dict) else {}
    return provides.get("limits") if isinstance(provides.get("limits"), dict) else {}


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
        "image_processing_actions": ["normalize_aspect_ratio", "compress_seedance_inputs", "add_subtle_depth_if_useful"],
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
    caption_language: str = "zh-CN",
) -> list[dict[str, Any]]:
    artwork_info = artwork_info or {}
    verified = bool(artwork_info.get("verified"))
    title = str(artwork_info.get("title") or "").strip()
    artist = str(artwork_info.get("artist") or "").strip()
    collection = str(artwork_info.get("collection") or "").strip()
    route = frame_plan.get("motion_route") or "comfortable_immersive"

    if str(caption_language).lower().startswith("en"):
        if verified and (title or artist or collection):
            parts = [part for part in [artist, title, collection] if part]
            hook = ", ".join(parts) + " begins with one detail worth holding."
        elif route == "novel_attention":
            hook = "The image catches attention because stillness begins to move."
        else:
            hook = "From the image itself, its quietest detail is time slowing down."
        subject = prompt.strip() or "this image"
        distinction = "Its special quality is how light, texture, and depth open together."
        if route == "novel_attention":
            distinction = "Its special quality is a restrained surprise inside a familiar frame."
        return [
            {"index": 0, "start": 0.2, "end": 2.0, "text": hook},
            {"index": 1, "start": 2.1, "end": 4.0, "text": f"The image holds the atmosphere of \"{subject[:40]}\"."},
            {"index": 2, "start": 4.1, "end": 6.2, "text": distinction},
            {"index": 3, "start": 6.3, "end": 7.8, "text": "May you keep one clear place inside a moving day."},
        ]

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


def build_seedance_prompt(prompt: str, frame_plan: dict[str, Any], captions: list[dict[str, Any]]) -> str:
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


def build_bgm_selection(
    prompt: str,
    frame_plan: dict[str, Any],
    bgm_query: str = "",
    bgm_path: str = "",
) -> dict[str, Any]:
    if bgm_path.strip():
        return {
            "music_source": "local",
            "bgm_path": bgm_path.strip(),
            "reason": "User or capsule supplied local BGM",
            "needs_bgm": True,
        }
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


def read_json(path: Path, fallback: Any) -> Any:
    if not path or not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def ensure_run_dirs(run_dir: Path) -> dict[str, Path]:
    dirs = {
        "inputs": run_dir / "inputs",
        "analysis": run_dir / "analysis",
        "prompts": run_dir / "prompts",
        "frames": run_dir / "frames",
        "seedance_inputs": run_dir / "frames" / "seedance_inputs",
        "videos": run_dir / "videos",
        "audio": run_dir / "audio",
        "final": run_dir / "final",
        "qa": run_dir / "qa",
        "release": run_dir / "release",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def copy_input_references(reference_images: list[dict[str, Any]], inputs_dir: Path) -> list[dict[str, Any]]:
    copied = []
    for index, ref in enumerate(reference_images):
        source = Path(ref["path"]).expanduser()
        entry = dict(ref)
        if source.is_file():
            target = inputs_dir / f"reference_{index:02d}{source.suffix.lower() or '.img'}"
            shutil.copy2(source, target)
            entry["copied_path"] = str(target)
            entry["path"] = str(target)
        copied.append(entry)
    return copied


def dimensions_for_aspect_ratio(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio == "16:9":
        return 1280, 720
    if aspect_ratio == "1:1":
        return 1024, 1024
    return 720, 1280


def create_synthetic_test_media(run_dir: Path, captions: list[dict[str, Any]], aspect_ratio: str = "9:16") -> dict[str, str]:
    from PIL import Image, ImageDraw

    frames_dir = run_dir / "frames"
    seedance_inputs_dir = frames_dir / "seedance_inputs"
    videos_dir = run_dir / "videos"
    final_dir = run_dir / "final"
    release_dir = run_dir / "release"
    width, height = dimensions_for_aspect_ratio(aspect_ratio)
    start = frames_dir / "start_frame.png"
    end = frames_dir / "end_frame.png"
    for path, color in [(start, (230, 220, 198)), (end, (160, 180, 150))]:
        image = Image.new("RGB", (width, height), color)
        draw = ImageDraw.Draw(image)
        pad_x = max(24, width // 6)
        pad_y = max(24, height // 3)
        draw.rectangle((pad_x, pad_y, width - pad_x, height - pad_y), outline=(80, 70, 60), width=6)
        draw.text((pad_x + 30, min(height - 80, height - pad_y + 40)), "ART FRAME", fill=(70, 60, 50))
        image.save(path)
    seedance_inputs_dir.mkdir(parents=True, exist_ok=True)
    start_jpg = seedance_inputs_dir / "start.jpg"
    end_jpg = seedance_inputs_dir / "end.jpg"
    Image.open(start).convert("RGB").save(start_jpg, "JPEG", quality=92)
    Image.open(end).convert("RGB").save(end_jpg, "JPEG", quality=92)

    seedance = videos_dir / "seedance_raw.mp4"
    final = final_dir / "final_video.mp4"
    release_video = release_dir / "video.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0xddd2bb:s={width}x{height}:d=8:r=24",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=420:duration=8",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(seedance),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.copy2(seedance, final)
    shutil.copy2(final, release_video)
    caption_path = release_dir / "copy.txt"
    caption_path.write_text("\n".join(item["text"] for item in captions), encoding="utf-8")
    return {
        "start": str(start),
        "end": str(end),
        "start_seedance_input": str(start_jpg),
        "end_seedance_input": str(end_jpg),
        "seedance": str(seedance),
        "final": str(final),
        "release_video": str(release_video),
        "caption": str(caption_path),
    }


def write_artifact_manifest(run_dir: Path, media: dict[str, Any], bgm_info: dict[str, Any] | None = None) -> Path:
    bgm_info = bgm_info or {"status": "not_used"}
    prompt_artifacts = media.get("prompt_artifacts", [])
    artifact_specs = [
        ("release_video", "final_video", "Final video"),
        ("caption", "copywriting", "Caption copy"),
        ("caption", "caption", "Caption lines"),
        ("start", "start_frame", "Start frame"),
        ("end", "end_frame", "End frame"),
        ("start_seedance_input", "seedance_input_frame", "Seedance start input"),
        ("end_seedance_input", "seedance_input_frame", "Seedance end input"),
        ("seedance", "raw_video", "Raw Seedance video"),
        ("contact_sheet", "qa", "Contact sheet"),
        ("local_video_qa", "qa", "Local video QA"),
        ("run_notes", "qa", "Run notes"),
    ]
    artifacts = [
        {"path": media[key], "category": category, "title": title}
        for key, category, title in artifact_specs
        if media.get(key)
    ]
    artifacts.extend(
        {"path": str(path), "category": "storyboard_prompt", "title": Path(path).stem}
        for path in prompt_artifacts
    )
    payload = {
        "artifacts": artifacts,
        "final_video": media.get("release_video", ""),
        "raw_seedance_video": media.get("seedance", ""),
        "raw_video": media.get("seedance", ""),
        "start_frame": media.get("start", ""),
        "end_frame": media.get("end", ""),
        "caption_file": media.get("caption", ""),
        "bgm": bgm_info,
        "resolved_tools": dict(media.get("resolved_tools") or {}),
        "toolchain": {"resolved_tools": dict(media.get("resolved_tools") or {})},
    }
    path = run_dir / "artifact_manifest.json"
    write_json(path, payload)
    return path


def discover_existing_media(run_dir: Path, prompt_artifacts: list[str] | None = None) -> dict[str, str]:
    candidates = {
        "start": run_dir / "frames" / "start_frame.png",
        "end": run_dir / "frames" / "end_frame.png",
        "start_seedance_input": run_dir / "frames" / "seedance_inputs" / "start.jpg",
        "end_seedance_input": run_dir / "frames" / "seedance_inputs" / "end.jpg",
        "seedance": run_dir / "videos" / "seedance_raw.mp4",
        "final": run_dir / "final" / "final_video.mp4",
        "release_video": run_dir / "release" / "video.mp4",
        "caption": run_dir / "release" / "copy.txt",
        "contact_sheet": run_dir / "qa" / "contact_sheet.jpg",
        "local_video_qa": run_dir / "qa" / "local_video_qa.json",
        "run_notes": run_dir / "qa" / "run_notes.json",
    }
    media = {key: str(path) for key, path in candidates.items() if path.exists()}
    media["prompt_artifacts"] = prompt_artifacts or []
    return media


def write_prompt_snapshots(
    dirs: dict[str, Path],
    prompt: str,
    frame_plan: dict[str, Any],
    seedance_prompt: str,
    bgm_selection: dict[str, Any],
    *,
    image_tool: str,
    video_tool: str,
) -> list[str]:
    supports_first_last = tool_flags(video_tool).get("first_last_frame") is True
    prompt_files = [
        (
            dirs["prompts"] / "video" / "seedance_v001.json",
            {
                "tool": video_tool,
                "generation_type": "first_last_frame" if supports_first_last else "image_to_video",
                "prompt": seedance_prompt,
                "reference_strategy": (
                    "first and last frames"
                    if supports_first_last
                    else "start frame plus an optional end-state reference"
                ),
                "notes": "Requests native sound effects and explicitly forbids background music.",
            },
        ),
        (
            dirs["prompts"] / "image" / "start_frame_v001.json",
            {
                "tool": image_tool,
                "strategy": frame_plan.get("start_frame_strategy"),
                "prompt": _frame_prompt(prompt, frame_plan, "首帧"),
            },
        ),
        (
            dirs["prompts"] / "image" / "end_frame_v001.json",
            {
                "tool": image_tool,
                "strategy": frame_plan.get("end_frame_strategy"),
                "prompt": _frame_prompt(prompt, frame_plan, "尾帧"),
            },
        ),
        (
            dirs["prompts"] / "music" / "bgm_v001.json",
            {
                "tool": "MusicManager",
                "selection": bgm_selection,
            },
        ),
    ]
    entries = []
    for path, payload in prompt_files:
        write_json(path, payload)
        entries.append(
            {
                "path": str(path),
                "category": path.parent.name,
                "tool": payload.get("tool"),
            }
        )
    index_path = dirs["prompts"] / "prompt_index.json"
    write_json(
        index_path,
        {
            "prompt": prompt,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "entries": entries,
        },
    )
    return [str(index_path), *(entry["path"] for entry in entries)]


def create_contact_sheet(run_dir: Path, media: dict[str, str]) -> str:
    from PIL import Image, ImageDraw

    qa_dir = run_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    output = qa_dir / "contact_sheet.jpg"
    frame_paths = [Path(media.get("start", "")), Path(media.get("end", ""))]
    images = []
    for path in frame_paths:
        if path.is_file():
            image = Image.open(path).convert("RGB")
            image.thumbnail((360, 640))
            images.append((path.stem, image.copy()))
    if not images:
        return ""

    width = sum(image.width for _, image in images) + 24 * (len(images) + 1)
    height = max(image.height for _, image in images) + 80
    sheet = Image.new("RGB", (width, height), (28, 26, 23))
    draw = ImageDraw.Draw(sheet)
    x = 24
    for label, image in images:
        sheet.paste(image, (x, 48))
        draw.text((x, 18), label, fill=(242, 232, 216))
        x += image.width + 24
    sheet.save(output, "JPEG", quality=92)
    return str(output)


def run_local_video_qa(run_dir: Path, aspect_ratio: str, expect_audio: bool = True) -> str:
    output = run_dir / "qa" / "local_video_qa.json"
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "local_video_qa.py"),
        "--run-dir",
        str(run_dir),
        "--aspect-ratio",
        aspect_ratio,
        "--require-prompts",
        "--output",
        str(output),
    ]
    if expect_audio:
        cmd.append("--expect-audio")
    result = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout[-1200:]
        raise RuntimeError(f"local_video_qa failed: {detail}")
    return str(output)


def run_tool(tool_name: str, params: dict[str, Any]) -> dict[str, Any] | str:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run_tool.py"),
        "--tool",
        tool_name,
        "--params",
        json.dumps(params, ensure_ascii=False),
    ]
    result = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"{tool_name} failed: {result.stderr[-1200:] or result.stdout[-1200:]}")

    text = result.stdout.strip()
    try:
        return json.loads(text[text.find("{") :]) if "{" in text else text
    except json.JSONDecodeError:
        return text


def build_prepare_image_command(input_path: Path, output_path: Path, aspect_ratio: str = "9:16") -> list[str]:
    size = "720x1280" if aspect_ratio == "9:16" else "1280x720" if aspect_ratio == "16:9" else "1024x1024"
    crop_size = size.replace("x", ":")
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        f"scale={size}:force_original_aspect_ratio=increase,crop={crop_size}",
        "-frames:v",
        "1",
        "-q:v",
        "3",
        str(output_path),
    ]


def prepare_seedance_input(image_path: Path, output_path: Path, aspect_ratio: str = "9:16") -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(build_prepare_image_command(image_path, output_path, aspect_ratio), check=True)
    return output_path


def _ass_time(seconds: float) -> str:
    centiseconds = int(round(seconds * 100))
    h = centiseconds // 360000
    m = (centiseconds // 6000) % 60
    s = (centiseconds // 100) % 60
    cs = centiseconds % 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def write_ass_captions(path: Path, captions: list[dict[str, Any]], style: dict[str, Any] | None = None) -> Path:
    style = style or {}
    primary = style.get("primary_color") or "&H00F2E8D8"
    outline = style.get("outline_color") or "&H802A241D"
    font = style.get("font") or "STHeiti"
    size = int(style.get("font_size") or 46)
    margin_v = int(style.get("margin_v") or 95)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 720",
        "PlayResY: 1280",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: ArtCaption,{font},{size},{primary},{primary},{outline},&H00000000,0,0,0,0,100,100,0,0,1,2,1,2,48,48,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for item in captions:
        text = str(item["text"]).replace("\n", "\\N").replace(",", "，")
        lines.append(
            f"Dialogue: 0,{_ass_time(float(item['start']))},{_ass_time(float(item['end']))},"
            f"ArtCaption,,0,0,0,,{text}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _frame_prompt(prompt: str, frame_plan: dict[str, Any], target: str) -> str:
    del frame_plan
    base = (
        f"{prompt}。生成{target}。高级艺术感，保持原素材风格，轻微3D空间层次，"
        "柔和展陈光，细节清晰，不要文字、水印、Logo、边框。"
    )
    if target == "首帧":
        return base + "画面应更接近开始、安静、初始、留白或变化前状态。"
    return base + "画面应更接近完成、丰富、盛放、变化后状态，但不要过度夸张。"


def generate_or_select_frame(
    params: dict[str, Any],
    output_dir: Path,
    frame_plan: dict[str, Any],
    frame: str,
    image_tool: str,
) -> Path:
    frames_dir = output_dir / "frames"
    prompt = str(params.get("prompt") or params.get("topic") or "")
    strategy = frame_plan[f"{frame}_frame_strategy"]
    selected_key = f"selected_{frame}_image"
    selected = frame_plan.get(selected_key)
    target = frames_dir / f"{frame}_frame.png"
    target.parent.mkdir(parents=True, exist_ok=True)

    if strategy in {"use_reference", "select_from_inputs"} and selected and Path(selected).is_file():
        from PIL import Image

        Image.open(selected).convert("RGB").save(target, "PNG")
        return target

    reference = frame_plan.get("selected_end_image") or frame_plan.get("selected_start_image") or ""
    tool_params = {
        "prompt": _frame_prompt(prompt, frame_plan, "首帧" if frame == "start" else "尾帧"),
        "output_path": str(target),
        "aspect_ratio": str(params.get("aspect_ratio") or "9:16"),
        "quality": "hd",
    }
    if strategy == "derive_from_reference" and reference and Path(reference).is_file():
        tool_params["reference_image_paths"] = [reference]
    result = run_tool(image_tool, tool_params)

    if isinstance(result, dict) and (
        result.get("status") == "failed"
        or result.get("success") is False
        or bool(result.get("error"))
    ):
        raise RuntimeError(result.get("error") or f"{image_tool} failed")

    if not target.is_file():
        raise RuntimeError(f"frame generation did not create {target}")
    return target


def resolve_bgm(bgm_selection: dict[str, Any], output_dir: Path) -> tuple[str, dict[str, Any]]:
    if bgm_selection.get("music_source") == "local" and bgm_selection.get("bgm_path"):
        path = Path(str(bgm_selection["bgm_path"])).expanduser()
        if not path.is_file():
            raise RuntimeError(f"local BGM not found: {path}")
        info = {
            "status": "local",
            "path": str(path.resolve()),
            "source": "local_bgm_path",
            "license_note": "Local BGM supplied by run params",
        }
        write_json(output_dir / "audio" / "bgm_selection.json", info)
        return str(path.resolve()), info

    from src.utils.music_utils import MusicManager

    bgm_dir = output_dir / "audio"
    path = MusicManager.resolve_online_music_path(bgm_selection, bgm_dir)
    if not path:
        return "", {"status": "unavailable", "source": "online_search", "license_note": "No approved track downloaded"}

    info = {
        "status": "downloaded",
        "path": path,
        "source": "Jamendo or Internet Archive via MusicManager",
        "license_note": "Selected by approved provider search; see local logs for source details",
    }
    write_json(output_dir / "audio" / "bgm_selection.json", info)
    return path, info


def _has_audio_stream(video_path: Path) -> bool:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(video_path),
        ],
        text=True,
        capture_output=True,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def render_final_video(
    raw_video: Path,
    captions_ass: Path,
    bgm_path: str,
    output_path: Path,
    bgm_volume: float = 0.08,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vf = f"ass={captions_ass}"
    raw_has_audio = _has_audio_stream(raw_video)

    if bgm_path and raw_has_audio:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(raw_video),
            "-stream_loop",
            "-1",
            "-i",
            bgm_path,
            "-filter_complex",
            f"[0:v]{vf}[v];[0:a]volume=1.0[a0];[1:a]volume={bgm_volume},atrim=0:8[a1];"
            "[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
    elif bgm_path:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(raw_video),
            "-stream_loop",
            "-1",
            "-i",
            bgm_path,
            "-filter_complex",
            f"[0:v]{vf}[v];[1:a]volume={bgm_volume},atrim=0:8[a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
    else:
        audio_args = ["-c:a", "aac"] if raw_has_audio else ["-an"]
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(raw_video),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            *audio_args,
            str(output_path),
        ]
    subprocess.run(cmd, check=True)
    return output_path


def run_live_pipeline(
    params: dict[str, Any],
    output_dir: Path,
    frame_plan: dict[str, Any],
    captions: list[dict[str, Any]],
    seedance_prompt: str,
    bgm_selection: dict[str, Any],
    *,
    image_tool: str,
    video_tool: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    aspect_ratio = str(params.get("aspect_ratio") or "9:16")
    start = generate_or_select_frame(params, output_dir, frame_plan, "start", image_tool)
    end = generate_or_select_frame(params, output_dir, frame_plan, "end", image_tool)
    start_jpg = prepare_seedance_input(start, output_dir / "frames" / "seedance_inputs" / "start.jpg", aspect_ratio)
    end_jpg = prepare_seedance_input(end, output_dir / "frames" / "seedance_inputs" / "end.jpg", aspect_ratio)
    raw_video = output_dir / "videos" / "seedance_raw.mp4"
    requested_duration = int(params.get("target_duration") or 10)
    duration_options = [
        int(value)
        for value in tool_limits(video_tool).get("duration_options", [])
        if str(value).isdigit()
    ] or [5, 10]
    duration = min(duration_options, key=lambda value: abs(value - requested_duration))
    flags = tool_flags(video_tool)
    video_params: dict[str, Any] = {
        "prompt": seedance_prompt,
        "output_path": str(raw_video),
        "aspect_ratio": aspect_ratio,
        "duration": f"{duration}s",
        "generate_audio": bool(flags.get("native_audio")),
    }
    if flags.get("first_last_frame") is True:
        video_params.update(
            {
                "generation_type": "first_last_frame",
                "start_image_path": str(start_jpg),
                "end_image_path": str(end_jpg),
                "images": [str(start_jpg), str(end_jpg)],
            }
        )
    else:
        video_params.update(
            {
                "generation_type": "image_to_video",
                "image_path": str(start_jpg),
                "image_paths": [str(start_jpg), str(end_jpg)],
            }
        )
    result = run_tool(
        video_tool,
        video_params,
    )
    if isinstance(result, dict) and (
        result.get("status") == "failed"
        or result.get("success") is False
        or bool(result.get("error"))
    ):
        raise RuntimeError(result.get("error") or f"{video_tool} failed")
    if not raw_video.is_file():
        raise RuntimeError(f"{video_tool} output missing: {raw_video}")

    bgm_path, bgm_info = resolve_bgm(bgm_selection, output_dir)
    captions_ass = write_ass_captions(output_dir / "final" / "captions.ass", captions, style=params.get("subtitle_style") or {})
    final = render_final_video(
        raw_video,
        captions_ass,
        bgm_path,
        output_dir / "final" / "final_video.mp4",
        float(params.get("bgm_volume") or 0.08),
    )
    release_video = output_dir / "release" / "video.mp4"
    release_copy = output_dir / "release" / "copy.txt"
    release_video.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final, release_video)
    release_copy.write_text("\n".join(item["text"] for item in captions), encoding="utf-8")
    return {
        "start": str(start),
        "end": str(end),
        "start_seedance_input": str(start_jpg),
        "end_seedance_input": str(end_jpg),
        "seedance": str(raw_video),
        "final": str(final),
        "release_video": str(release_video),
        "caption": str(release_copy),
    }, bgm_info


def run(params: dict[str, Any], output_dir: Path, *, dry_run: bool = False) -> dict[str, Any]:
    prompt = str(params.get("prompt") or params.get("topic") or "").strip()
    refs = normalize_reference_images(params.get("reference_images"))
    if not prompt and not refs:
        raise SystemExit("prompt or reference_images is required")

    dirs = ensure_run_dirs(output_dir)
    prompt_artifacts: list[str] = []
    bgm_info: dict[str, Any] = {"status": "not_used"}
    aspect_ratio = str(params.get("aspect_ratio") or "9:16")
    image_tool = resolved_tool(params, "image", DEFAULT_IMAGE_TOOL)
    video_tool = resolved_tool(params, "video", DEFAULT_VIDEO_TOOL)
    selected_tools = {"image": image_tool, "video": video_tool}
    try:
        copied_refs = copy_input_references(refs, dirs["inputs"])
        frame_plan = decide_frame_plan(
            prompt=prompt,
            reference_images=copied_refs,
            mood=str(params.get("mood") or "auto"),
            style_hint=str(params.get("style_hint") or ""),
        )
        captions = build_caption_lines(
            prompt,
            frame_plan,
            params.get("artwork_info") or {},
            caption_language=str(params.get("caption_language") or "zh-CN"),
        )
        seedance_prompt = build_seedance_prompt(prompt, frame_plan, captions)
        bgm_selection = build_bgm_selection(
            prompt,
            frame_plan,
            str(params.get("bgm_query") or ""),
            str(params.get("bgm_path") or params.get("background_music_path") or ""),
        )

        write_json(dirs["analysis"] / "frame_decision.json", frame_plan)
        write_json(dirs["analysis"] / "captions.json", captions)
        write_text(dirs["prompts"] / "seedance_prompt.txt", seedance_prompt)
        write_json(dirs["prompts"] / "bgm_selection.json", bgm_selection)
        prompt_artifacts = write_prompt_snapshots(
            dirs,
            prompt,
            frame_plan,
            seedance_prompt,
            bgm_selection,
            image_tool=image_tool,
            video_tool=video_tool,
        )

        if dry_run:
            media = create_synthetic_test_media(output_dir, captions, aspect_ratio=aspect_ratio)
            bgm_info = {"status": "dry_run", "source": "synthetic"}
        else:
            media, bgm_info = run_live_pipeline(
                params,
                output_dir,
                frame_plan,
                captions,
                seedance_prompt,
                bgm_selection,
                image_tool=image_tool,
                video_tool=video_tool,
            )
        media["resolved_tools"] = selected_tools
        media["prompt_artifacts"] = prompt_artifacts
        media["contact_sheet"] = create_contact_sheet(output_dir, media)
        media["run_notes"] = str(dirs["qa"] / "run_notes.json")
        media["local_video_qa"] = str(dirs["qa"] / "local_video_qa.json")

        write_json(
            dirs["qa"] / "run_notes.json",
            {
                "status": "success",
                "dry_run": dry_run,
                "resolved_tools": selected_tools,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
        )
        manifest = write_artifact_manifest(output_dir, media, bgm_info)
        media["local_video_qa"] = run_local_video_qa(output_dir, aspect_ratio=aspect_ratio, expect_audio=True)
        manifest = write_artifact_manifest(output_dir, media, bgm_info)
        return {"manifest": str(manifest), "final_video": media["release_video"]}
    except Exception as exc:
        write_json(
            dirs["qa"] / "run_notes.json",
            {
                "status": "failed",
                "dry_run": dry_run,
                "resolved_tools": selected_tools,
                "error": str(exc),
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
        )
        media = discover_existing_media(output_dir, prompt_artifacts)
        media["run_notes"] = str(dirs["qa"] / "run_notes.json")
        write_artifact_manifest(output_dir, media, bgm_info)
        raise SystemExit(str(exc)) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Art frame reference-frame transition video capsule")
    parser.add_argument("--topic", default="", help="User topic or prompt")
    parser.add_argument("--params", default="", help="JSON params path")
    parser.add_argument("--output-dir", required=True, help="Run output directory")
    parser.add_argument("--dry-run", action="store_true", help="Write local synthetic media without API calls")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    params = read_json(Path(args.params), {}) if args.params else {}
    if args.topic and "prompt" not in params:
        params["prompt"] = args.topic
    result = run(params, Path(args.output_dir).expanduser().resolve(), dry_run=args.dry_run or bool(params.get("dry_run")))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
