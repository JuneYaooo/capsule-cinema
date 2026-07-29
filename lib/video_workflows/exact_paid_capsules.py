"""Fail-closed exact executors for paid fixed-count capsule routes.

These routes intentionally avoid the generic Agno planner and the generic
concurrent/retrying media generators.  A caller supplies one locked storyboard;
the executor performs each paid request once, serially, records local evidence,
and releases only after technical QA passes.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from custom_tools.audio_generation.minimax_tts_tool import synthesize_with_minimax
from custom_tools.image_generation.volcengine_image_generator_tool import (
    DEFAULT_SEEDREAM_MODEL,
    VolcengineImageGeneratorTool,
)
from custom_tools.video_generation.local_video_adapter_b import (
    Seedance20VideoGeneratorTool,
)
from src.contracts import get_scene_prompt
from video_workflows.provider_request_ids import scoped_request_id


ASPECT_SIZES = {"16:9": (1920, 1080), "9:16": (1080, 1920), "3:4": (1080, 1440)}
SEEDANCE_MODEL = "doubao-seedance-2-0-260128"
GUOFENG_NARRATION_CJK_RANGE = (175, 190)
FELT_ASMR_CAPSULE_VERSION = 2
GUOFENG_CAPSULE_VERSION = 10
GUOFENG_TTS_VOICE = "Chinese (Mandarin)_Radio_Host"
# Two production samples from the pinned Radio Host voice measured 52.776s and
# 58.320s for 175-190 CJK narration at 0.8x.  Locking the one allowed provider
# request to 0.9x projects those samples to 46.9-51.8s, inside the 45-55s gate.
# This value is fixed before the paid call; it is never a retry-time adjustment
# or a local post-processing correction.
GUOFENG_TTS_SPEED = 0.9
LIFE_SIM_CAPSULE_VERSION = 26
LIFE_SIM_TTS_VOICE = "male-qn-jingying"
GUOFENG_PHOTOREAL_PROMPT_MARKERS = (
    "photoreal",
    "photo-real",
    "live action",
    "live-action",
    "realistic skin",
    "cinematic still",
    "photographic",
    "photography",
    "camera lens",
    "shallow depth of field",
    "bokeh",
    "摄影写实",
    "真人写实",
    "电影剧照",
    "电影摄影",
    "写实人像",
    "真实皮肤",
    "实拍",
)
GUOFENG_IMAGE_STYLE_PREFIX = (
    "Strong non-photorealistic 2D Chinese ink-wash guoman illustration on warm ivory "
    "xuan paper; visibly hand-painted black ink outlines, wet-ink blooms, dry-brush "
    "edges, simplified non-identifiable faces, flat mineral-color accents, generous "
    "negative space. This is painted animation concept art, never a photograph, never "
    "a live-action actor, never realistic skin or a camera still. "
)


class ExactCapsuleError(RuntimeError):
    """A secret-free, non-retryable exact-route failure."""


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _run(command: list[str], label: str) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip()[-1000:]
        raise ExactCapsuleError(f"{label} failed: {detail}")


def _probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height,sample_rate,channels",
            "-of", "json", str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ExactCapsuleError(f"ffprobe failed for {path.name}")
    payload = json.loads(result.stdout)
    payload["duration"] = float((payload.get("format") or {}).get("duration") or 0)
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _font() -> str:
    if shutil.which("fc-match"):
        result = subprocess.run(
            ["fc-match", "-f", "%{file}", ":lang=zh-cn"],
            capture_output=True,
            text=True,
        )
        candidate = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        if result.returncode == 0 and candidate and Path(candidate).is_file():
            return candidate
    for candidate in (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ):
        if Path(candidate).is_file():
            return candidate
    raise ExactCapsuleError("exact route requires a discoverable CJK font")


def preflight_exact_paid_capsules() -> dict[str, Any]:
    required = ["ffmpeg", "ffprobe"]
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        raise ExactCapsuleError("exact route missing executables: " + ", ".join(missing))
    _font()
    life_assets = Path(__file__).resolve().parents[2] / "capsules" / "life_sim.capsule" / "assets"
    asset_names = (
        "life_shaker_opening_renderer.py",
        "life_shaker_background_16x9.png",
        "life_shaker_background_9x16.png",
        "life_shaker_machine_sfx.wav",
    )
    missing_assets = [name for name in asset_names if not (life_assets / name).is_file()]
    if missing_assets:
        raise ExactCapsuleError("life_sim exact assets missing: " + ", ".join(missing_assets))
    return {
        "ok": True,
        "provider_calls": 0,
        "planner": "locked_storyboard_no_agno",
        "serial": True,
        "automatic_paid_post_retries": 0,
        "felt_asmr": {"image_calls": 6, "video_calls": 6, "tts_calls": 0},
        "guofeng_history": {"image_calls": 10, "video_calls": 10, "tts_calls": 1},
        "life_sim": {"image_calls": 22, "video_calls": 0, "tts_calls": 1},
    }


def _locked_storyboard(
    params: dict[str, Any], output_dir: Path, *, expected_scenes: int
) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    raw = str(params.get("storyboard_path") or "").strip()
    if not raw:
        raise ExactCapsuleError("exact route requires params.storyboard_path")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (output_dir / path).resolve()
    else:
        path = path.resolve()
    try:
        path.relative_to(output_dir.resolve())
    except ValueError as exc:
        raise ExactCapsuleError("storyboard_path must stay inside the run output directory") from exc
    if not path.is_file() or path.suffix.lower() != ".json" or path.stat().st_size > 5 * 1024 * 1024:
        raise ExactCapsuleError("storyboard_path must be a regular JSON file under 5 MiB")
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExactCapsuleError("locked storyboard is not valid JSON") from exc
    scenes = source.get("storyboard") if isinstance(source, dict) else None
    if not isinstance(scenes, list) or len(scenes) != expected_scenes:
        raise ExactCapsuleError(f"locked storyboard requires exactly {expected_scenes} scenes")
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict) or not get_scene_prompt(scene, "image"):
            raise ExactCapsuleError(f"scene {index} requires an image prompt")
        duration = scene.get("duration")
        if not isinstance(duration, (int, float)) or float(duration) <= 0:
            raise ExactCapsuleError(f"scene {index} requires a positive duration")
    return path, source, scenes


def _image_once(
    tool: VolcengineImageGeneratorTool,
    *,
    prompt: str,
    output: Path,
    aspect_ratio: str,
    request_id: str,
    reference: Path | None = None,
) -> dict[str, Any]:
    result = tool._run(
        prompt=prompt,
        output_path=str(output),
        aspect_ratio=aspect_ratio,
        output_format="png",
        response_format="b64_json",
        watermark=False,
        request_id=request_id,
        reference_image_path=str(reference) if reference else None,
    )
    if not result.get("success") or not output.is_file():
        raise ExactCapsuleError(
            "official Seedream request failed without retry: "
            + str(result.get("error") or "image missing")
        )
    return result


def _guofeng_image_prompt(prompt: str) -> str:
    """Lock the historical route to illustrated input before any paid request."""

    normalized = prompt.casefold()
    blocked = [marker for marker in GUOFENG_PHOTOREAL_PROMPT_MARKERS if marker in normalized]
    if blocked:
        raise ExactCapsuleError(
            "guofeng_history image prompt requests photoreal/live-action rendering: "
            + ", ".join(blocked)
        )
    return (
        GUOFENG_IMAGE_STYLE_PREFIX
        + prompt.strip()
        + " No text, no watermark, no logo; avoid frontal portrait framing and keep "
        "people in three-quarter, profile, distant, silhouette, or partial-body views."
    )


def _guofeng_inkwash_reference(source: Path, output: Path) -> dict[str, Any]:
    """Create a deterministic illustrated reference without another Provider call.

    Seedream can drift from an ink-wash prompt into live-action costume photography.
    Seedance rejects such inputs as possible real-person privacy content.  The exact
    route therefore keeps the paid original as evidence, but sends this visibly
    illustrated derivative to both later Seedream reference calls and Seedance.
    """

    try:
        with Image.open(source) as opened:
            rgb = opened.convert("RGB")
    except (OSError, ValueError) as exc:
        raise ExactCapsuleError(f"guofeng_history cannot stylize {source.name}") from exc

    radius = max(1.0, min(rgb.size) / 900.0)
    softened = rgb.filter(ImageFilter.GaussianBlur(radius=radius))
    gray = ImageOps.autocontrast(ImageOps.grayscale(softened), cutoff=1)
    poster = gray.point(lambda value: min(255, int(round(value / 32.0) * 32)))
    paper_tones = ImageOps.colorize(poster, black="#1d211f", white="#f2ead8")

    edge_strength = ImageOps.autocontrast(gray.filter(ImageFilter.FIND_EDGES), cutoff=1)
    strong_edges = edge_strength.point(lambda value: 255 if value >= 48 else 0)
    ink_lines = ImageOps.invert(strong_edges)
    ink_lines = ImageEnhance.Contrast(ink_lines).enhance(1.8)
    ink_rgb = Image.merge("RGB", (ink_lines, ink_lines, ink_lines))

    muted_color = ImageEnhance.Color(softened).enhance(0.10)
    muted_color = ImageOps.posterize(muted_color, 4)
    painted = Image.blend(paper_tones, muted_color, 0.12)
    painted = ImageChops.multiply(painted, ink_rgb)
    painted = Image.blend(painted, Image.new("RGB", rgb.size, "#eee4cf"), 0.08)

    unique_colors = painted.getcolors(maxcolors=257)
    if unique_colors is None:
        raise ExactCapsuleError(
            "guofeng_history local ink-wash reference exceeds 256-color illustration gate"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    painted.save(output, format="PNG", optimize=True)
    if not output.is_file() or output.stat().st_size == 0:
        raise ExactCapsuleError("guofeng_history local ink-wash reference is missing")
    return {
        "source": str(source),
        "output": str(output),
        "width": painted.width,
        "height": painted.height,
        "unique_colors": len(unique_colors),
        "source_sha256": _sha256(source),
        "output_sha256": _sha256(output),
        "provider_calls": 0,
        "style": "deterministic_inkwash_guoman_v1",
    }


def _video_once(
    tool: Seedance20VideoGeneratorTool,
    *,
    prompt: str,
    image: Path,
    output: Path,
    duration: int,
    native_audio: bool,
    checkpoint_path: Path,
    request_id: str,
) -> dict[str, Any]:
    os.environ.setdefault("ARK_SEEDANCE20_MODEL", SEEDANCE_MODEL)
    result = tool._run(
        prompt=prompt,
        generation_type="image_to_video",
        output_path=str(output),
        image_path=str(image),
        aspect_ratio="9:16",
        duration=f"{duration}s",
        generate_audio=native_audio,
        watermark=False,
        poll_interval=8,
        max_wait=1200,
        checkpoint_path=str(checkpoint_path),
        request_id=request_id,
    )
    if result.get("error") or not output.is_file():
        raise ExactCapsuleError(
            "official Seedance request failed without resubmit: "
            + str(result.get("error") or "video missing")
        )
    return result


def _tts_once(
    *, text: str, output: Path, voice: str, speed: float, request_id: str
) -> dict[str, Any]:
    if not text.strip():
        raise ExactCapsuleError("unified narration text is empty")
    result = synthesize_with_minimax(
        text,
        str(output),
        voice_type=voice,
        speed=speed,
        request_id=request_id,
    )
    if not result.get("success") or not output.is_file():
        raise ExactCapsuleError(
            f"MiniMax request {request_id} failed without retry/fallback: "
            + str(result.get("error") or "audio missing")
        )
    return result


def _programmatic_bgm(output: Path, duration: float, *, guofeng: bool = False) -> None:
    notes = ("174.61", "220", "261.63") if guofeng else ("196", "246.94", "293.66")
    expression = "+".join(
        f"0.018*sin(2*PI*{note}*t)*(0.70+0.30*sin(2*PI*0.0{index + 4}*t))"
        for index, note in enumerate(notes)
    )
    _run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
            "-i", f"aevalsrc={expression}:s=48000:d={duration:.6f}",
            "-af", "lowpass=f=1700,afade=t=in:st=0:d=0.7,alimiter=limit=0.9",
            "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", str(output),
        ],
        "local original BGM",
    )


def _render_still(image: Path, output: Path, duration: float, size: tuple[int, int]) -> None:
    width, height = size
    frames = max(1, round(duration * 30))
    increment = 0.012 / frames
    vf = (
        f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
        f"crop={width * 2}:{height * 2},"
        f"zoompan=z='min(zoom+{increment:.10f},1.012)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:"
        f"s={width}x{height}:fps=30,format=yuv420p"
    )
    _run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1",
            "-i", str(image), "-vf", vf, "-frames:v", str(frames), "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-threads", "2",
            "-movflags", "+faststart", str(output),
        ],
        f"local micro-cut {output.stem}",
    )


def _allocate(weights: list[float], total: float, minimum: float = 1.0, maximum: float = 5.0) -> list[float]:
    if not weights or not len(weights) * minimum <= total <= len(weights) * maximum:
        raise ExactCapsuleError("measured narration cannot fit the fixed micro-cut bounds")
    safe = [max(0.001, float(item)) for item in weights]
    result = [0.0] * len(safe)
    open_indices = set(range(len(safe)))
    remaining = total
    while open_indices:
        denominator = sum(safe[index] for index in open_indices)
        changed = False
        for index in list(open_indices):
            value = remaining * safe[index] / denominator
            if value < minimum:
                result[index] = minimum
                remaining -= minimum
                open_indices.remove(index)
                changed = True
            elif value > maximum:
                result[index] = maximum
                remaining -= maximum
                open_indices.remove(index)
                changed = True
        if not changed:
            denominator = sum(safe[index] for index in open_indices)
            for index in open_indices:
                result[index] = remaining * safe[index] / denominator
            break
    result[-1] += total - sum(result)
    return result


def _concat_list(paths: list[Path], output: Path) -> None:
    def escaped(path: Path) -> str:
        return str(path).replace("'", "'\\''")
    output.write_text("".join(f"file '{escaped(path)}'\n" for path in paths), encoding="utf-8")


def _contact_sheet(images: list[Path], output: Path, *, columns: int = 5) -> None:
    thumb = (320, 180)
    rows = math.ceil(len(images) / columns)
    sheet = Image.new("RGB", (columns * thumb[0], rows * thumb[1]), "#111")
    for index, path in enumerate(images):
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail(thumb)
            x = index % columns * thumb[0] + (thumb[0] - image.width) // 2
            y = index // columns * thumb[1] + (thumb[1] - image.height) // 2
            sheet.paste(image, (x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=91)


def _cover(image: Path, output: Path, title: str, size: tuple[int, int]) -> None:
    width, height = size
    with Image.open(image) as source:
        source = source.convert("RGB")
        scale = max(width / source.width, height / source.height)
        resized = source.resize((math.ceil(source.width * scale), math.ceil(source.height * scale)))
        left = (resized.width - width) // 2
        top = (resized.height - height) // 2
        canvas = resized.crop((left, top, left + width, top + height)).convert("RGBA")
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rectangle((0, int(height * 0.68), width, height), fill=(0, 0, 0, 175))
    font = ImageFont.truetype(_font(), max(42, width // 22))
    draw.text((width // 2, int(height * 0.82)), title, font=font, anchor="mm", fill="white", stroke_width=2, stroke_fill="black")
    Image.alpha_composite(canvas, layer).convert("RGB").save(output, quality=94)


def _manifest(
    *,
    capsule: str,
    version: int,
    output_dir: Path,
    final_video: Path,
    storyboard_path: Path,
    images: list[Path],
    scene_videos: list[Path],
    qa_path: Path,
    checkpoint_path: Path,
    cover_path: Path,
    contact_sheet: Path,
    extra_artifacts: list[tuple[str, Path, str]],
    technical: dict[str, Any],
) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    entries = [
        ("final_video", final_video, f"{capsule} final video"),
        ("storyboard", storyboard_path, f"{capsule} locked storyboard"),
        ("qa_report", qa_path, f"{capsule} technical QA"),
        ("release_checkpoint", checkpoint_path, f"{capsule} release checkpoint"),
        ("cover", cover_path, f"{capsule} cover"),
        ("contact_sheet", contact_sheet, f"{capsule} review contact sheet"),
        *extra_artifacts,
    ]
    entries.extend(("storyboard_image", path, f"{capsule} image {index:02d}") for index, path in enumerate(images, 1))
    entries.extend(("scene_video", path, f"{capsule} scene {index:02d}") for index, path in enumerate(scene_videos, 1))
    for category, path, title in entries:
        if path.is_file():
            artifacts.append({"category": category, "path": str(path), "title": title, "size_bytes": path.stat().st_size})
    payload = {
        "schema_version": 1,
        "status": "complete",
        "deliverable": True,
        "release_recommendation": "pass",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "capsule": capsule,
        "capsule_version": version,
        "final_video": str(final_video),
        "technical": technical,
        "artifacts": artifacts,
    }
    _write_json(output_dir / "artifact_manifest.json", payload)
    return payload


def execute_felt_asmr(topic: str, params: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    storyboard_path, source, scenes = _locked_storyboard(params, output_dir, expected_scenes=6)
    if abs(sum(float(scene["duration"]) for scene in scenes) - 36.0) > 0.05:
        raise ExactCapsuleError("felt_asmr scene durations must sum to 36 seconds")
    for index, scene in enumerate(scenes, 1):
        duration = float(scene["duration"])
        if duration != int(duration) or not 4 <= int(duration) <= 15:
            raise ExactCapsuleError(f"felt_asmr scene {index} duration must be an integer 4-15 seconds")
        if not get_scene_prompt(scene, "video"):
            raise ExactCapsuleError(f"felt_asmr scene {index} requires a video prompt")

    images_dir = output_dir / "work" / "images"
    videos_dir = output_dir / "work" / "videos"
    release = output_dir / "release" / "public"
    qa_dir = output_dir / "qa"
    for path in (images_dir, videos_dir, release, qa_dir):
        path.mkdir(parents=True, exist_ok=True)
    image_tool = VolcengineImageGeneratorTool()
    video_tool = Seedance20VideoGeneratorTool()
    images: list[Path] = []
    image_calls: list[dict[str, Any]] = []
    reference: Path | None = None
    for index, scene in enumerate(scenes, 1):
        path = images_dir / f"scene_{index:02d}.png"
        image_request_id = scoped_request_id(
            prefix="felt-asmr-image",
            output_dir=output_dir,
            logical_key=f"scene:{index:02d}",
        )
        result = _image_once(
            image_tool,
            prompt=get_scene_prompt(scene, "image"),
            output=path,
            aspect_ratio="9:16",
            request_id=image_request_id,
            reference=reference,
        )
        images.append(path)
        image_calls.append({"index": index, "request_id": image_request_id, "model": result.get("model") or DEFAULT_SEEDREAM_MODEL, "attempts": 1, "sha256": _sha256(path)})
        reference = reference or path
    if len({_sha256(path) for path in images}) != 6:
        raise ExactCapsuleError("felt_asmr requires six unique generated images")

    scene_videos: list[Path] = []
    video_calls: list[dict[str, Any]] = []
    for index, (scene, image) in enumerate(zip(scenes, images), 1):
        path = videos_dir / f"scene_{index:02d}.mp4"
        video_request_id = scoped_request_id(
            prefix="felt-asmr-video",
            output_dir=output_dir,
            logical_key=f"scene:{index:02d}",
        )
        result = _video_once(
            video_tool,
            prompt=get_scene_prompt(scene, "video") + " Native close-mic wool-felt ASMR only; no speech, no music, no text.",
            image=image,
            output=path,
            duration=int(scene["duration"]),
            native_audio=True,
            checkpoint_path=output_dir / "technical" / "seedance" / f"scene_{index:02d}.json",
            request_id=video_request_id,
        )
        probe = _probe(path)
        if not any(stream.get("codec_type") == "audio" for stream in probe.get("streams", [])):
            raise ExactCapsuleError(f"felt_asmr scene {index} has no native audio")
        scene_videos.append(path)
        video_calls.append({"index": index, "request_id": video_request_id, "task_id": result.get("task_id"), "attempts": 1, "duration": probe["duration"]})

    concat_file = output_dir / "work" / "concat.txt"
    _concat_list(scene_videos, concat_file)
    raw_concat = output_dir / "work" / "01_concat.mp4"
    _run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-t", "36", "-movflags", "+faststart", str(raw_concat),
    ], "felt ASMR concat")
    bgm = output_dir / "work" / "felt_original_bgm.wav"
    _programmatic_bgm(bgm, 36.0)
    final_video = release / "felt_asmr.mp4"
    _run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw_concat), "-i", str(bgm),
        "-filter_complex", "[0:a]volume=1.0[native];[1:a]volume=0.025[bgm];[native][bgm]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]",
        "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", "36",
        "-movflags", "+faststart", str(final_video),
    ], "felt ASMR final mix")
    cover = release / "cover.jpg"
    contact = qa_dir / "contact_sheet.jpg"
    _cover(images[-1], cover, source.get("video_title") or topic, (1080, 1920))
    _contact_sheet(images, contact, columns=3)
    final_probe = _probe(final_video)
    video_stream = next((item for item in final_probe.get("streams", []) if item.get("codec_type") == "video"), {})
    audio_stream = next((item for item in final_probe.get("streams", []) if item.get("codec_type") == "audio"), {})
    qa = {"ok": bool(abs(final_probe["duration"] - 36) < 0.35 and video_stream.get("width") == 1080 and video_stream.get("height") == 1920 and audio_stream), "duration": final_probe["duration"], "width": video_stream.get("width"), "height": video_stream.get("height"), "native_audio_segments": 6, "image_calls": 6, "video_calls": 6, "blockers": []}
    if not qa["ok"]:
        qa["blockers"].append("felt_asmr_exact_release_gate_failed")
    qa_path = Path(_write_json(qa_dir / "felt_asmr_exact_qa.json", qa))
    checkpoint = {"status": "pass" if qa["ok"] else "blocked", "release_ready": qa["ok"], "blockers": qa["blockers"]}
    checkpoint_path = Path(_write_json(qa_dir / "release_checkpoint.json", checkpoint))
    if not qa["ok"]:
        raise ExactCapsuleError("felt_asmr exact QA failed")
    ledger = Path(_write_json(output_dir / "technical" / "provider_ledger.json", {"serial": True, "automatic_retries": 0, "images": image_calls, "videos": video_calls}))
    manifest = _manifest(capsule="felt_asmr", version=FELT_ASMR_CAPSULE_VERSION, output_dir=output_dir, final_video=final_video, storyboard_path=storyboard_path, images=images, scene_videos=scene_videos, qa_path=qa_path, checkpoint_path=checkpoint_path, cover_path=cover, contact_sheet=contact, extra_artifacts=[("provider_request_ledger", ledger, "Felt ASMR Provider ledger"), ("bgm", bgm, "Felt ASMR original local BGM")], technical={"agno_planner_skipped": True, "image_model": DEFAULT_SEEDREAM_MODEL, "video_model": SEEDANCE_MODEL, "image_calls": 6, "video_calls": 6, "tts_calls": 0, "native_audio": True, "automatic_paid_post_retries": 0})
    return {"success": True, "deliverable": True, "run_status": "completed", "final_video": str(final_video), "artifact_manifest_path": str(output_dir / "artifact_manifest.json"), "generation_summary": {"image_generated": 6, "video_generated": 6, "audio_generated": True}, "manifest": manifest}


def _srt_from_scenes(scenes: list[dict[str, Any]], duration: float, output: Path) -> None:
    texts = [str(scene.get("narration") or "").strip() for scene in scenes]
    weights = [max(1, len(text)) for text in texts]
    allocations = [duration * weight / sum(weights) for weight in weights]
    def stamp(seconds: float) -> str:
        milliseconds = round(seconds * 1000)
        hours, remainder = divmod(milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        secs, millis = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    cursor = 0.0
    blocks = []
    for index, (text, length) in enumerate(zip(texts, allocations), 1):
        end = cursor + length
        blocks.append(f"{index}\n{stamp(cursor)} --> {stamp(end)}\n{text}\n")
        cursor = end
    output.write_text("\n".join(blocks), encoding="utf-8")


def execute_guofeng_history(topic: str, params: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    storyboard_path, source, scenes = _locked_storyboard(params, output_dir, expected_scenes=10)
    durations = [int(scene["duration"]) for scene in scenes]
    if any(float(scene["duration"]) != duration or not 4 <= duration <= 15 for scene, duration in zip(scenes, durations)) or sum(durations) != 55:
        raise ExactCapsuleError("guofeng_history requires ten integer 4-15s clips totaling 55 seconds")
    if any(not get_scene_prompt(scene, "video") or not str(scene.get("narration") or "").strip() for scene in scenes):
        raise ExactCapsuleError("guofeng_history scenes require image, video, and narration fields")
    image_prompts = [_guofeng_image_prompt(get_scene_prompt(scene, "image")) for scene in scenes]
    narration_text = str(params.get("narration_text") or source.get("narration_text") or "").strip()
    if not narration_text:
        narration_text = "\n".join(str(scene["narration"]).strip() for scene in scenes)
    narration_cjk_count = len(re.findall(r"[\u4e00-\u9fff]", narration_text))
    minimum_cjk, maximum_cjk = GUOFENG_NARRATION_CJK_RANGE
    if not minimum_cjk <= narration_cjk_count <= maximum_cjk:
        raise ExactCapsuleError(
            "guofeng_history narration requires "
            f"{minimum_cjk}-{maximum_cjk} CJK characters before MiniMax TTS, "
            f"got {narration_cjk_count}"
        )
    work = output_dir / "work"
    images_dir, videos_dir, audio_dir = work / "images", work / "videos", work / "audio"
    release, qa_dir = output_dir / "release" / "public", output_dir / "qa"
    for path in (images_dir, videos_dir, audio_dir, release, qa_dir):
        path.mkdir(parents=True, exist_ok=True)
    narration = audio_dir / "guofeng_history_narration.mp3"
    request_id = scoped_request_id(
        prefix="guofeng-history-tts",
        output_dir=output_dir,
        logical_key="unified-narration",
    )
    _tts_once(
        text=narration_text,
        output=narration,
        voice=GUOFENG_TTS_VOICE,
        speed=GUOFENG_TTS_SPEED,
        request_id=request_id,
    )
    narration_duration = _probe(narration)["duration"]
    if not 45.0 <= narration_duration <= 55.0:
        raise ExactCapsuleError(f"guofeng_history narration must measure 45-55s, got {narration_duration:.3f}s")
    image_tool, video_tool = VolcengineImageGeneratorTool(), Seedance20VideoGeneratorTool()
    stylized_dir = work / "inkwash_references"
    stylized_dir.mkdir(parents=True, exist_ok=True)
    images, stylized_images, image_calls = [], [], []
    reference: Path | None = None
    for index, (scene, image_prompt) in enumerate(zip(scenes, image_prompts), 1):
        path = images_dir / f"scene_{index:02d}.png"
        image_request_id = scoped_request_id(
            prefix="guofeng-history-image",
            output_dir=output_dir,
            logical_key=f"scene:{index:02d}",
        )
        result = _image_once(
            image_tool,
            prompt=image_prompt,
            output=path,
            aspect_ratio="9:16",
            request_id=image_request_id,
            reference=reference,
        )
        images.append(path)
        stylized = stylized_dir / f"scene_{index:02d}.png"
        style_evidence = _guofeng_inkwash_reference(path, stylized)
        stylized_images.append(stylized)
        image_calls.append({"index": index, "request_id": image_request_id, "model": result.get("model") or DEFAULT_SEEDREAM_MODEL, "attempts": 1, "sha256": _sha256(path), "seedance_input_sha256": style_evidence["output_sha256"], "local_style": style_evidence["style"]})
        reference = reference or stylized
    if len({_sha256(path) for path in images}) != 10:
        raise ExactCapsuleError("guofeng_history requires ten unique generated images")
    if len({_sha256(path) for path in stylized_images}) != 10:
        raise ExactCapsuleError("guofeng_history requires ten unique local ink-wash references")
    scene_videos, video_calls = [], []
    for index, (scene, image, duration) in enumerate(zip(scenes, stylized_images, durations), 1):
        path = videos_dir / f"scene_{index:02d}.mp4"
        video_request_id = scoped_request_id(
            prefix="guofeng-history-video",
            output_dir=output_dir,
            logical_key=f"scene:{index:02d}",
        )
        result = _video_once(video_tool, prompt=get_scene_prompt(scene, "video") + " No speech, no subtitles, no music, no text.", image=image, output=path, duration=duration, native_audio=False, checkpoint_path=output_dir / "technical" / "seedance" / f"scene_{index:02d}.json", request_id=video_request_id)
        scene_videos.append(path)
        video_calls.append({"index": index, "request_id": video_request_id, "task_id": result.get("task_id"), "attempts": 1, "duration": _probe(path)["duration"]})
    concat_file = work / "concat.txt"
    _concat_list(scene_videos, concat_file)
    concat = work / "01_concat.mp4"
    _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-t", f"{narration_duration:.6f}", str(concat)], "guofeng concat")
    subtitles = work / "guofeng_history.srt"
    _srt_from_scenes(scenes, narration_duration, subtitles)
    bgm = work / "guofeng_original_bgm.wav"
    _programmatic_bgm(bgm, narration_duration, guofeng=True)
    final_video = release / "guofeng_history.mp4"
    escaped_srt = str(subtitles).replace("'", "'\\''").replace(":", "\\:")
    _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(concat), "-i", str(narration), "-i", str(bgm), "-vf", f"subtitles='{escaped_srt}':force_style='FontName=Noto Sans CJK SC,FontSize=19,PrimaryColour=&H00FFFFFF,OutlineColour=&H00101010,BorderStyle=1,Outline=2,Shadow=0,MarginV=90,Alignment=2'", "-filter_complex", "[1:a]volume=1.0[voice];[2:a]volume=0.045[bgm];[voice][bgm]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]", "-map", "0:v:0", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-t", f"{narration_duration:.6f}", "-movflags", "+faststart", str(final_video)], "guofeng subtitle and audio assembly")
    cover, contact = release / "cover.jpg", qa_dir / "contact_sheet.jpg"
    _cover(stylized_images[0], cover, source.get("video_title") or topic, (1080, 1920))
    _contact_sheet(stylized_images, contact)
    probe = _probe(final_video)
    video_stream = next((item for item in probe.get("streams", []) if item.get("codec_type") == "video"), {})
    audio_stream = next((item for item in probe.get("streams", []) if item.get("codec_type") == "audio"), {})
    qa = {"ok": bool(abs(probe["duration"] - narration_duration) < 0.35 and video_stream.get("width") == 1080 and video_stream.get("height") == 1920 and audio_stream), "duration": probe["duration"], "narration_duration": narration_duration, "image_calls": 10, "video_calls": 10, "tts_calls": 1, "subtitles": "burned", "blockers": []}
    if not qa["ok"]:
        qa["blockers"].append("guofeng_history_exact_release_gate_failed")
    qa_path = Path(_write_json(qa_dir / "guofeng_history_exact_qa.json", qa))
    checkpoint_path = Path(_write_json(qa_dir / "release_checkpoint.json", {"status": "pass" if qa["ok"] else "blocked", "release_ready": qa["ok"], "blockers": qa["blockers"]}))
    if not qa["ok"]:
        raise ExactCapsuleError("guofeng_history exact QA failed")
    ledger = Path(_write_json(output_dir / "technical" / "provider_ledger.json", {"serial": True, "automatic_retries": 0, "images": image_calls, "videos": video_calls, "tts": {"request_id": request_id, "calls": 1, "voice": GUOFENG_TTS_VOICE, "speed": GUOFENG_TTS_SPEED}}))
    manifest = _manifest(capsule="guofeng_history", version=GUOFENG_CAPSULE_VERSION, output_dir=output_dir, final_video=final_video, storyboard_path=storyboard_path, images=images, scene_videos=scene_videos, qa_path=qa_path, checkpoint_path=checkpoint_path, cover_path=cover, contact_sheet=contact, extra_artifacts=[("provider_request_ledger", ledger, "Guofeng Provider ledger"), ("voiceover", narration, "Guofeng unified MiniMax narration"), ("subtitle", subtitles, "Guofeng subtitles"), ("bgm", bgm, "Guofeng original local BGM"), *[("seedance_input", path, f"Guofeng local ink-wash reference {index:02d}") for index, path in enumerate(stylized_images, 1)]], technical={"agno_planner_skipped": True, "image_model": DEFAULT_SEEDREAM_MODEL, "video_model": SEEDANCE_MODEL, "image_calls": 10, "video_calls": 10, "tts_calls": 1, "tts_voice": GUOFENG_TTS_VOICE, "tts_speed": GUOFENG_TTS_SPEED, "automatic_paid_post_retries": 0, "seedance_input_style": "deterministic_inkwash_guoman_v1", "local_style_provider_calls": 0})
    return {"success": True, "deliverable": True, "run_status": "completed", "final_video": str(final_video), "artifact_manifest_path": str(output_dir / "artifact_manifest.json"), "generation_summary": {"image_generated": 10, "video_generated": 10, "audio_generated": True, "subtitles_added": True}, "manifest": manifest}


def _life_sim_contract(
    params: dict[str, Any], output_dir: Path
) -> tuple[Path, dict[str, Any], list[dict[str, Any]], str, str, dict[str, Any], float]:
    storyboard_path, source, scenes = _locked_storyboard(params, output_dir, expected_scenes=22)
    aspect = str(params.get("aspect_ratio") or "16:9")
    if aspect not in ASPECT_SIZES:
        raise ExactCapsuleError("life_sim aspect ratio is unsupported")
    if params.get("generation_budget_ack") is not True:
        raise ExactCapsuleError("life_sim requires generation_budget_ack=true")
    character_bible = params.get("character_bible") or source.get("character_bible")
    style_contract = params.get("style_contract") or source.get("style_contract")
    if not isinstance(character_bible, dict) or not character_bible or not isinstance(style_contract, dict) or not style_contract:
        raise ExactCapsuleError("life_sim requires non-empty character_bible and style_contract")
    required_scene_fields = ("narration", "continuity_anchor", "voice_visual_relation", "actor_state")
    for index, scene in enumerate(scenes, 1):
        missing = [field for field in required_scene_fields if not scene.get(field)]
        if not (scene.get("narration_sentence_ids") or scene.get("sentence_boundary")):
            missing.append("narration_sentence_ids_or_sentence_boundary")
        if missing:
            raise ExactCapsuleError(
                f"life_sim scene {index} is missing locked continuity fields: {', '.join(missing)}"
            )
    narration_text = str(params.get("narration_text") or source.get("narration_text") or "").strip() or "\n".join(str(scene["narration"]).strip() for scene in scenes)
    opening = source.get("opening") if isinstance(source.get("opening"), dict) else {}
    opening_tts = str(opening.get("tts") or source.get("opening_tts") or "").strip()
    if opening_tts and not narration_text.startswith(opening_tts):
        narration_text = opening_tts + "\n" + narration_text
    opening_duration = float(opening.get("duration_seconds") or 3.75)
    if not 3.4 <= opening_duration <= 4.5:
        raise ExactCapsuleError("life_sim opening duration must be 3.4-4.5 seconds")
    return storyboard_path, source, scenes, aspect, narration_text, opening, opening_duration


def _validate_life_sim_images(images: list[Path], aspect: str) -> list[str]:
    if len(images) != 22:
        raise ExactCapsuleError("life_sim requires exactly 22 recovered images")
    expected_ratio = ASPECT_SIZES[aspect][0] / ASPECT_SIZES[aspect][1]
    hashes: list[str] = []
    for index, path in enumerate(images, 1):
        if path.name != f"scene_{index:02d}.png" or not path.is_file() or path.stat().st_size <= 0:
            raise ExactCapsuleError(f"life_sim recovered image {index:02d} is missing or empty")
        try:
            with Image.open(path) as image:
                width, height = image.size
                image.load()
        except (OSError, ValueError) as exc:
            raise ExactCapsuleError(
                f"life_sim recovered image {index:02d} is not decodable"
            ) from exc
        if width <= 0 or height <= 0 or abs((width / height) - expected_ratio) > 0.01:
            raise ExactCapsuleError(
                f"life_sim recovered image {index:02d} does not match aspect {aspect}"
            )
        hashes.append(_sha256(path))
    if len(set(hashes)) != 22:
        raise ExactCapsuleError("life_sim requires 22 unique generated image hashes")
    return hashes


def _assemble_life_sim(
    *,
    topic: str,
    params: dict[str, Any],
    output_dir: Path,
    storyboard_path: Path,
    source: dict[str, Any],
    scenes: list[dict[str, Any]],
    aspect: str,
    narration_text: str,
    opening: dict[str, Any],
    opening_duration: float,
    narration: Path,
    images: list[Path],
    image_calls: list[dict[str, Any]],
    recovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    image_hashes = _validate_life_sim_images(images, aspect)
    if not narration.is_file() or narration.stat().st_size <= 0:
        raise ExactCapsuleError("life_sim narration is missing or empty")
    narration_duration = _probe(narration)["duration"]
    if not 52 <= narration_duration <= 70:
        raise ExactCapsuleError(f"life_sim narration must measure 52-70s, got {narration_duration:.3f}s")
    if len(image_calls) != 22:
        raise ExactCapsuleError("life_sim Provider ledger requires exactly 22 image calls")

    work = output_dir / "work"
    images_dir, videos_dir, audio_dir = work / "images", work / "videos", work / "audio"
    release, qa_dir = output_dir / "release" / "public", output_dir / "qa"
    for path in (images_dir, videos_dir, audio_dir, release, qa_dir):
        path.mkdir(parents=True, exist_ok=True)
    request_id = scoped_request_id(
        prefix="life-sim-tts",
        output_dir=output_dir,
        logical_key="unified-narration",
    )
    body_duration = narration_duration - opening_duration
    body_durations = _allocate([float(scene["duration"]) for scene in scenes], body_duration)
    capsule_dir = Path(__file__).resolve().parents[2] / "capsules" / "life_sim.capsule"
    assets = capsule_dir / "assets"
    opening_video = videos_dir / "00_life_shaker.mp4"
    opening_manifest = output_dir / "technical" / "opening_renderer_manifest.json"
    background = assets / ("life_shaker_background_16x9.png" if aspect == "16:9" else "life_shaker_background_9x16.png")
    candidate_terms = opening.get("candidate_terms") or params.get("opening_candidate_terms") or []
    _run([sys.executable, str(assets / "life_shaker_opening_renderer.py"), "--background", str(background), "--output", str(opening_video), "--aspect-ratio", aspect, "--topic", str(opening.get("topic_short_name") or topic), "--candidate-terms", json.dumps(candidate_terms, ensure_ascii=False), "--sfx", str(assets / "life_shaker_machine_sfx.wav"), "--duration", f"{opening_duration:.3f}", "--font-bold", _font(), "--font-regular", _font(), "--manifest", str(opening_manifest)], "life shaker opening renderer")
    body_clips = []
    for index, (image, duration) in enumerate(zip(images, body_durations), 1):
        path = videos_dir / f"body_{index:02d}.mp4"
        _render_still(image, path, duration, ASPECT_SIZES[aspect])
        body_clips.append(path)
    concat_file = work / "concat.txt"
    _concat_list([opening_video, *body_clips], concat_file)
    concat = work / "01_concat.mp4"
    _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-threads", "2", "-pix_fmt", "yuv420p", "-r", "30", "-t", f"{narration_duration:.6f}", str(concat)], "life_sim visual concat")
    bgm = work / "life_sim_original_bgm.wav"
    _programmatic_bgm(bgm, narration_duration)
    final_video = release / "life_sim.mp4"
    _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(concat), "-i", str(narration), "-i", str(assets / "life_shaker_machine_sfx.wav"), "-i", str(bgm), "-filter_complex", f"[1:a]volume=1.0[voice];[2:a]volume=0.34,apad=whole_dur={narration_duration:.6f},atrim=0:{narration_duration:.6f}[sfx];[3:a]volume=0.055[bgm];[voice][sfx][bgm]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.95[a]", "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{narration_duration:.6f}", "-movflags", "+faststart", str(final_video)], "life_sim audio assembly")
    cover, contact = release / "cover.jpg", qa_dir / "contact_sheet.jpg"
    _cover(images[0], cover, source.get("video_title") or topic, ASPECT_SIZES[aspect])
    _contact_sheet(images, contact)
    probe = _probe(final_video)
    video_stream = next((item for item in probe.get("streams", []) if item.get("codec_type") == "video"), {})
    audio_stream = next((item for item in probe.get("streams", []) if item.get("codec_type") == "audio"), {})
    width, height = ASPECT_SIZES[aspect]
    qa = {"ok": bool(abs(probe["duration"] - narration_duration) < 0.35 and video_stream.get("width") == width and video_stream.get("height") == height and audio_stream), "duration": probe["duration"], "narration_duration": narration_duration, "width": video_stream.get("width"), "height": video_stream.get("height"), "image_calls": 22, "tts_calls": 1, "body_subtitles": False, "unique_image_hashes": len(set(image_hashes)), "recovery": recovery, "blockers": []}
    if not qa["ok"]:
        qa["blockers"].append("life_sim_exact_release_gate_failed")
    qa_path = Path(_write_json(qa_dir / "life_sim_exact_qa.json", qa))
    checkpoint_path = Path(_write_json(qa_dir / "release_checkpoint.json", {"status": "pass" if qa["ok"] else "blocked", "release_ready": qa["ok"], "blockers": qa["blockers"]}))
    if not qa["ok"]:
        raise ExactCapsuleError("life_sim exact QA failed")
    ledger_payload: dict[str, Any] = {"serial": True, "automatic_retries": 0, "images": image_calls, "tts": {"request_id": request_id, "calls": 1, "voice": LIFE_SIM_TTS_VOICE, "speed": 1.18}}
    if recovery is not None:
        ledger_payload["recovery"] = recovery
    ledger = Path(_write_json(output_dir / "technical" / "provider_ledger.json", ledger_payload))
    technical = {"agno_planner_skipped": True, "image_model": DEFAULT_SEEDREAM_MODEL, "image_calls": 22, "video_calls": 0, "tts_calls": 1, "tts_voice": LIFE_SIM_TTS_VOICE, "tts_speed": 1.18, "body_subtitles": False, "opening_renderer": "life_shaker_opening_renderer", "automatic_paid_post_retries": 0}
    if recovery is not None:
        technical.update(recovery)
    manifest = _manifest(capsule="life_sim", version=LIFE_SIM_CAPSULE_VERSION, output_dir=output_dir, final_video=final_video, storyboard_path=storyboard_path, images=images, scene_videos=[opening_video, *body_clips], qa_path=qa_path, checkpoint_path=checkpoint_path, cover_path=cover, contact_sheet=contact, extra_artifacts=[("provider_request_ledger", ledger, "Life Sim Provider ledger"), ("voiceover", narration, "Life Sim unified MiniMax narration"), ("bgm", bgm, "Life Sim original local BGM"), ("capsule_gate_report", opening_manifest, "Life Sim opening renderer manifest")], technical=technical)
    return {"success": True, "deliverable": True, "run_status": "completed", "final_video": str(final_video), "artifact_manifest_path": str(output_dir / "artifact_manifest.json"), "generation_summary": {"image_generated": 22, "video_generated": 23, "audio_generated": True, "subtitles_added": False}, "manifest": manifest}


def execute_life_sim(topic: str, params: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    (
        storyboard_path,
        source,
        scenes,
        aspect,
        narration_text,
        opening,
        opening_duration,
    ) = _life_sim_contract(params, output_dir)
    work = output_dir / "work"
    images_dir, audio_dir = work / "images", work / "audio"
    images_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    narration = audio_dir / "life_sim_narration.mp3"
    request_id = scoped_request_id(
        prefix="life-sim-tts",
        output_dir=output_dir,
        logical_key="unified-narration",
    )
    _tts_once(text=narration_text, output=narration, voice=LIFE_SIM_TTS_VOICE, speed=1.18, request_id=request_id)
    image_tool = VolcengineImageGeneratorTool()
    images: list[Path] = []
    image_calls: list[dict[str, Any]] = []
    reference: Path | None = None
    for index, scene in enumerate(scenes, 1):
        path = images_dir / f"scene_{index:02d}.png"
        image_request_id = scoped_request_id(
            prefix="life-sim-image",
            output_dir=output_dir,
            logical_key=f"scene:{index:02d}",
        )
        result = _image_once(
            image_tool,
            prompt=get_scene_prompt(scene, "image"),
            output=path,
            aspect_ratio=aspect,
            request_id=image_request_id,
            reference=reference,
        )
        images.append(path)
        image_calls.append({"index": index, "request_id": image_request_id, "model": result.get("model") or DEFAULT_SEEDREAM_MODEL, "attempts": 1, "sha256": _sha256(path)})
        reference = reference or path
    return _assemble_life_sim(
        topic=topic,
        params=params,
        output_dir=output_dir,
        storyboard_path=storyboard_path,
        source=source,
        scenes=scenes,
        aspect=aspect,
        narration_text=narration_text,
        opening=opening,
        opening_duration=opening_duration,
        narration=narration,
        images=images,
        image_calls=image_calls,
    )


def recover_life_sim_local(
    topic: str,
    params: dict[str, Any],
    output_dir: Path,
    *,
    job_id: str,
    recovery_evidence: dict[str, Any],
    recovery_source_rootfs_sha256: str,
) -> dict[str, Any]:
    """Reassemble an accepted Life Sim run without any Provider capability."""

    if os.environ.get("EXACT_PAID_RECOVERY_OFFLINE") != "1":
        raise ExactCapsuleError("life_sim recovery requires EXACT_PAID_RECOVERY_OFFLINE=1")
    forbidden_provider_env = (
        "ARK_API_KEY",
        "MINIMAX_API_KEY",
        "MINIMAX_GROUP_ID",
        "MINIMAX_BASE_URL",
        "FACTORY_GATEWAY_TOKEN",
        "FACTORY_GATEWAY_API_KEY",
    )
    present = [name for name in forbidden_provider_env if os.environ.get(name)]
    if present:
        raise ExactCapsuleError("life_sim recovery refuses Provider credentials: " + ", ".join(present))
    if not re.fullmatch(r"[0-9a-f]{64}", recovery_source_rootfs_sha256):
        raise ExactCapsuleError("life_sim recovery source rootfs SHA-256 is invalid")
    expected = {
        "job_id": job_id,
        "provider_calls": 23,
        "captured_provider_calls": 23,
        "usage_events": 23,
        "seedream_calls": 22,
        "minimax_calls": 1,
        "other_provider_calls": 0,
    }
    mismatches = [
        key for key, value in expected.items() if recovery_evidence.get(key) != value
    ]
    if mismatches:
        raise ExactCapsuleError(
            "life_sim recovery evidence does not close: " + ", ".join(mismatches)
        )
    (
        storyboard_path,
        source,
        scenes,
        aspect,
        narration_text,
        opening,
        opening_duration,
    ) = _life_sim_contract(params, output_dir)
    images = [output_dir / "work" / "images" / f"scene_{index:02d}.png" for index in range(1, 23)]
    image_hashes = _validate_life_sim_images(images, aspect)
    image_calls = [
        {
            "index": index,
            "request_id": scoped_request_id(
                prefix="life-sim-image",
                output_dir=output_dir,
                logical_key=f"scene:{index:02d}",
            ),
            "model": DEFAULT_SEEDREAM_MODEL,
            "attempts": 1,
            "sha256": image_hash,
            "reused": True,
        }
        for index, image_hash in enumerate(image_hashes, 1)
    ]
    recovery = {
        "recovery_mode": "offline_local_assembly",
        "recovery_job_id": job_id,
        "provider_calls_reused": 23,
        "new_provider_calls": 0,
        "automatic_paid_post_retries": 0,
        "recovery_source_rootfs_sha256": recovery_source_rootfs_sha256,
        "provider_reconciliation": expected,
    }
    return _assemble_life_sim(
        topic=topic,
        params=params,
        output_dir=output_dir,
        storyboard_path=storyboard_path,
        source=source,
        scenes=scenes,
        aspect=aspect,
        narration_text=narration_text,
        opening=opening,
        opening_duration=opening_duration,
        narration=output_dir / "work" / "audio" / "life_sim_narration.mp3",
        images=images,
        image_calls=image_calls,
        recovery=recovery,
    )
