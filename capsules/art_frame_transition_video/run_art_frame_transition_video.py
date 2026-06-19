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
        "veo_inputs": run_dir / "frames" / "veo_inputs",
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


def create_synthetic_test_media(run_dir: Path, captions: list[dict[str, Any]]) -> dict[str, str]:
    from PIL import Image, ImageDraw

    frames_dir = run_dir / "frames"
    videos_dir = run_dir / "videos"
    final_dir = run_dir / "final"
    release_dir = run_dir / "release"
    start = frames_dir / "start_frame.png"
    end = frames_dir / "end_frame.png"
    for path, color in [(start, (230, 220, 198)), (end, (160, 180, 150))]:
        image = Image.new("RGB", (720, 1280), color)
        draw = ImageDraw.Draw(image)
        draw.rectangle((120, 420, 600, 860), outline=(80, 70, 60), width=6)
        draw.text((150, 900), "ART FRAME", fill=(70, 60, 50))
        image.save(path)

    veo = videos_dir / "veo_raw.mp4"
    final = final_dir / "final_video.mp4"
    release_video = release_dir / "video.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=0xddd2bb:s=720x1280:d=8:r=24",
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
        str(veo),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.copy2(veo, final)
    shutil.copy2(final, release_video)
    caption_path = release_dir / "copy.txt"
    caption_path.write_text("\n".join(item["text"] for item in captions), encoding="utf-8")
    return {
        "start": str(start),
        "end": str(end),
        "veo": str(veo),
        "final": str(final),
        "release_video": str(release_video),
        "caption": str(caption_path),
    }


def write_artifact_manifest(run_dir: Path, media: dict[str, str], bgm_info: dict[str, Any] | None = None) -> Path:
    bgm_info = bgm_info or {"status": "not_used"}
    artifacts = [
        {"path": media["release_video"], "category": "final_video", "title": "Final video"},
        {"path": media["caption"], "category": "copywriting", "title": "Caption copy"},
        {"path": media["caption"], "category": "caption", "title": "Caption lines"},
        {"path": media["start"], "category": "start_frame", "title": "Start frame"},
        {"path": media["end"], "category": "end_frame", "title": "End frame"},
        {"path": media["veo"], "category": "raw_video", "title": "Raw Veo video"},
        {"path": str(run_dir / "prompts" / "veo_prompt.txt"), "category": "storyboard_prompt", "title": "Veo prompt"},
        {"path": str(run_dir / "qa" / "run_notes.json"), "category": "qa", "title": "Run notes"},
    ]
    payload = {
        "artifacts": artifacts,
        "final_video": media["release_video"],
        "raw_veo_video": media["veo"],
        "start_frame": media["start"],
        "end_frame": media["end"],
        "caption_file": media["caption"],
        "bgm": bgm_info,
    }
    path = run_dir / "artifact_manifest.json"
    write_json(path, payload)
    return path


def run_live_pipeline(
    params: dict[str, Any],
    output_dir: Path,
    frame_plan: dict[str, Any],
    captions: list[dict[str, Any]],
    veo_prompt: str,
    bgm_selection: dict[str, Any],
) -> tuple[dict[str, str], dict[str, Any]]:
    raise SystemExit("live mode requires the Task 4 live pipeline")


def run(params: dict[str, Any], output_dir: Path, *, dry_run: bool = False) -> dict[str, Any]:
    prompt = str(params.get("prompt") or params.get("topic") or "").strip()
    refs = normalize_reference_images(params.get("reference_images"))
    if not prompt and not refs:
        raise SystemExit("prompt or reference_images is required")

    dirs = ensure_run_dirs(output_dir)
    copied_refs = copy_input_references(refs, dirs["inputs"])
    frame_plan = decide_frame_plan(
        prompt=prompt,
        reference_images=copied_refs,
        mood=str(params.get("mood") or "auto"),
        style_hint=str(params.get("style_hint") or ""),
    )
    captions = build_caption_lines(prompt, frame_plan, params.get("artwork_info") or {})
    veo_prompt = build_veo_prompt(prompt, frame_plan, captions)
    bgm_selection = build_bgm_selection(prompt, frame_plan, str(params.get("bgm_query") or ""))

    write_json(dirs["analysis"] / "frame_decision.json", frame_plan)
    write_json(dirs["analysis"] / "captions.json", captions)
    write_text(dirs["prompts"] / "veo_prompt.txt", veo_prompt)
    write_json(dirs["prompts"] / "bgm_selection.json", bgm_selection)

    if dry_run:
        media = create_synthetic_test_media(output_dir, captions)
        bgm_info = {"status": "dry_run", "source": "synthetic"}
    else:
        media, bgm_info = run_live_pipeline(params, output_dir, frame_plan, captions, veo_prompt, bgm_selection)

    write_json(
        dirs["qa"] / "run_notes.json",
        {
            "status": "success",
            "dry_run": dry_run,
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        },
    )
    manifest = write_artifact_manifest(output_dir, media, bgm_info)
    return {"manifest": str(manifest), "final_video": media["release_video"]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Art frame first/last-frame transition video capsule")
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
