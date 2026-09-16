"""Exact, fail-closed production route for the cat_life v8 capsule.

The ordinary general-video runtime is deliberately flexible: it can plan with
Agno, generate scene TTS concurrently, retry image quality failures, and use
generic still-image assembly.  Those behaviours violate cat_life v8.  This
module provides the capsule's narrower route: 25 serial standard gpt-image-2
calls, one MiniMax narration call, the packaged flipbook/SFX tools, nineteen
unique micro-cuts, and local release packaging.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageDraw, ImageFont

from custom_tools.audio_generation.minimax_tts_tool import synthesize_with_minimax
from custom_tools.image_generation.local_177911_image_adapter import GptImage2Tool
from src.contracts import get_scene_prompt
from video_workflows.provider_request_ids import scoped_request_id


ASPECT_SIZES = {"16:9": (1920, 1080), "9:16": (1080, 1920), "3:4": (1080, 1440)}
IMAGE_MODEL = "gpt-image-2"
IMAGE_PROVIDER = "juling_177911"
TTS_MODEL = "speech-2.8-turbo"
TTS_VOICE = "male-qn-jingying"
TTS_SPEED = 1.18
CAT_LIFE_CAPSULE_VERSION = 8


class CatLifeExactError(RuntimeError):
    """A non-retryable exact-route failure."""


def preflight_cat_life_exact() -> dict[str, Any]:
    """Verify the exact executor and all local native dependencies without a POST."""
    capsule_dir = Path(__file__).resolve().parents[3] / "capsules" / "cat_life.capsule"
    required = [
        capsule_dir / "assets" / "cat_fate_flipbook_opening_renderer.py",
        capsule_dir / "assets" / "gear_lock_opening_sfx_mixer.py",
        capsule_dir / "assets" / "cat_life_windup_gear_sfx.mp3",
        capsule_dir / "assets" / "cat_life_final_landing_sfx.mp3",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise CatLifeExactError("cat_life exact local assets missing: " + ", ".join(missing))
    if not hasattr(GptImage2Tool, "generate_exact_once"):
        raise CatLifeExactError("GptImage2Tool exact single-attempt surface is missing")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise CatLifeExactError("cat_life exact route requires ffmpeg and ffprobe")
    try:
        from fontTools.ttLib import TTFont  # noqa: F401
    except ImportError as exc:
        raise CatLifeExactError("cat_life exact route requires fontTools") from exc
    font_probe = subprocess.run(
        ["fc-match", "-f", "%{file}", ":lang=zh-cn"],
        capture_output=True,
        text=True,
    ) if shutil.which("fc-match") else None
    if font_probe is not None and (font_probe.returncode != 0 or not font_probe.stdout.strip()):
        raise CatLifeExactError("cat_life exact route has no discoverable CJK font")
    return {
        "ok": True,
        "provider_calls": 0,
        "image_model": IMAGE_MODEL,
        "image_quality": "standard",
        "image_calls": 25,
        "image_serial": True,
        "image_automatic_retries": 0,
        "tts_model": TTS_MODEL,
        "tts_voice": TTS_VOICE,
        "tts_speed": TTS_SPEED,
        "tts_calls": 1,
        "tts_fallback": False,
        "native_opening_renderer": True,
        "native_sfx_mixer": True,
        "local_original_bgm": True,
    }


def _write_json(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _run(command: list[str], *, label: str) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-1200:]
        raise CatLifeExactError(f"{label} failed: {detail}")


def _probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
            "-of", "json", str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise CatLifeExactError(f"ffprobe failed for {path.name}")
    data = json.loads(result.stdout)
    data["duration"] = float((data.get("format") or {}).get("duration") or 0)
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded_durations(weights: list[float], total: float) -> list[float]:
    """Distribute TTS-led body time while preserving the 1-5s micro-cut contract."""
    if not weights or not len(weights) * 1.0 <= total <= len(weights) * 5.0:
        raise CatLifeExactError(
            f"measured narration leaves {total:.3f}s for {len(weights)} body cuts; "
            "the exact 1-5s micro-cut route cannot represent it"
        )
    remaining = float(total)
    unresolved = set(range(len(weights)))
    result = [0.0] * len(weights)
    safe_weights = [max(0.001, float(value)) for value in weights]
    while unresolved:
        weight_sum = sum(safe_weights[index] for index in unresolved)
        changed = False
        for index in list(unresolved):
            proposed = remaining * safe_weights[index] / weight_sum
            if proposed < 1.0:
                result[index] = 1.0
                remaining -= 1.0
                unresolved.remove(index)
                changed = True
            elif proposed > 5.0:
                result[index] = 5.0
                remaining -= 5.0
                unresolved.remove(index)
                changed = True
        if not changed:
            weight_sum = sum(safe_weights[index] for index in unresolved)
            for index in unresolved:
                result[index] = remaining * safe_weights[index] / weight_sum
            break
    # Absorb float error in the last cut without changing the route bounds.
    result[-1] += total - sum(result)
    if any(value < 0.999 or value > 5.001 for value in result):
        raise CatLifeExactError("bounded duration allocation escaped the 1-5s contract")
    return result


def _call_image_once(
    tool: GptImage2Tool,
    *,
    prompt: str,
    output: Path,
    aspect_ratio: str,
    reference: Path | None,
    request_id: str,
) -> dict[str, Any]:
    result = tool.generate_exact_once(
        prompt=prompt,
        output_path=str(output),
        request_id=request_id,
        aspect_ratio=aspect_ratio,
        reference_image_path=str(reference) if reference else "",
    )
    if not result.get("success") or not output.is_file():
        error = result.get("error") or "exact image result missing"
        raise CatLifeExactError(f"image request {request_id} failed without retry: {error}")
    return result


def _render_body_clip(image: Path, output: Path, duration: float, size: tuple[int, int]) -> None:
    width, height = size
    frames = max(1, int(round(duration * 30)))
    # 1.2% slow push-in: it is the capsule's native micro-motion, not a
    # provider-failure fallback.  Each cut still uses an independently paid image.
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
            "-movflags", "+faststart", str(output),
        ],
        label=f"body micro-cut {output.stem}",
    )


def _generate_programmatic_bgm(output: Path, duration: float) -> None:
    """Generate an original, deterministic local instrumental bed with FFmpeg."""
    expression = (
        "0.030*sin(2*PI*196*t)*(0.72+0.28*sin(2*PI*0.071*t))"
        "+0.022*sin(2*PI*246.94*t)*(0.70+0.30*sin(2*PI*0.053*t))"
        "+0.016*sin(2*PI*293.66*t)*(0.68+0.32*sin(2*PI*0.041*t))"
    )
    fade_out_at = max(0.0, duration - 1.2)
    _run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
            "-i", f"aevalsrc={expression}:s=48000:d={duration:.6f}",
            "-af", f"lowpass=f=1800,aecho=0.8:0.35:160|320:0.18|0.10,"
            f"afade=t=in:st=0:d=0.8,afade=t=out:st={fade_out_at:.6f}:d=1.2,"
            f"atrim=0:{duration:.6f},alimiter=limit=0.90",
            "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", str(output),
        ],
        label="programmatic original BGM",
    )


def _cover(source_images: list[Path], output: Path, title: str, font_path: str, size: tuple[int, int]) -> None:
    width, height = size
    canvas = Image.new("RGB", size, "#16120f")
    panel_width = width // len(source_images)
    for index, path in enumerate(source_images):
        with Image.open(path) as image:
            image = image.convert("RGB")
            scale = max(panel_width / image.width, height / image.height)
            resized = image.resize((math.ceil(image.width * scale), math.ceil(image.height * scale)))
            left = max(0, (resized.width - panel_width) // 2)
            top = max(0, (resized.height - height) // 2)
            canvas.paste(resized.crop((left, top, left + panel_width, top + height)), (index * panel_width, 0))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, int(height * 0.66), width, height), fill=(12, 9, 7, 190))
    font = ImageFont.truetype(font_path, max(42, width // 24))
    draw.text((width // 2, int(height * 0.79)), title, font=font, anchor="mm", fill="#fff4db", stroke_width=2, stroke_fill="#2b160c")
    Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB").save(output, quality=94)


def _contact_sheet(images: list[Path], output: Path) -> None:
    thumb_size = (320, 180)
    columns = 5
    rows = math.ceil(len(images) / columns)
    sheet = Image.new("RGB", (columns * thumb_size[0], rows * thumb_size[1]), "#111111")
    for index, path in enumerate(images):
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail(thumb_size)
            x = (index % columns) * thumb_size[0] + (thumb_size[0] - image.width) // 2
            y = (index // columns) * thumb_size[1] + (thumb_size[1] - image.height) // 2
            sheet.paste(image, (x, y))
    sheet.save(output, quality=91)


def execute_cat_life_exact(
    state: dict[str, Any],
    *,
    image_tool_factory: Callable[[], GptImage2Tool] = GptImage2Tool,
    tts_synthesizer: Callable[..., dict] = synthesize_with_minimax,
) -> dict[str, Any]:
    """Execute cat_life v8 exactly and return a general-video result shape."""
    workspace = Path(state["workspace_dir"])
    dirs = {key: Path(value) for key, value in (state.get("output_dirs") or {}).items()}
    release = dirs["release"]
    work = dirs["work"]
    images_dir = dirs["images"]
    refs_dir = dirs["reference_images"]
    audios_dir = dirs["audios"]
    videos_dir = dirs["videos"]
    public_dir = release / "public"
    technical_dir = release / "technical"
    internal_dir = release / "internal"
    qa_dir = workspace / "qa"
    assembly_dir = work / "assembly"
    music_dir = work / "music"
    for directory in (public_dir, technical_dir, internal_dir, qa_dir, assembly_dir, music_dir):
        directory.mkdir(parents=True, exist_ok=True)

    source = json.loads(Path(state["storyboard_path"]).read_text(encoding="utf-8"))
    storyboard = state["storyboard"]
    opening = source["opening"]
    aspect_ratio = state.get("aspect_ratio") or "16:9"
    if aspect_ratio not in ASPECT_SIZES:
        raise CatLifeExactError(f"unsupported cat_life aspect ratio: {aspect_ratio}")
    size = ASPECT_SIZES[aspect_ratio]

    character_prompt = str(source.get("character_reference_prompt") or "").strip()
    if not character_prompt:
        raise CatLifeExactError("locked storyboard is missing character_reference_prompt")
    candidate_prompts = opening["candidate_prompts"]
    candidate_lives = opening["candidate_lives"]
    result_index = int(opening["result_index"])
    if not 0 <= result_index < 5:
        raise CatLifeExactError("opening.result_index must select one of five candidates")

    callback = state.get("progress_callback")
    tool = image_tool_factory()
    image_calls: list[dict[str, Any]] = []

    def generate(role: str, index: int, prompt: str, output: Path, reference: Path | None) -> Path:
        request_id = scoped_request_id(
            prefix=f"cat-life-{role}",
            output_dir=workspace,
            logical_key=f"{role}:{index:02d}",
        )
        if callable(callback):
            callback("paid_media_started", provider=IMAGE_PROVIDER, model=IMAGE_MODEL, request_id=request_id)
        result = _call_image_once(
            tool, prompt=prompt, output=output, aspect_ratio=aspect_ratio,
            reference=reference, request_id=request_id,
        )
        image_calls.append({
            "sequence": len(image_calls) + 1,
            "role": role,
            "role_index": index,
            "request_id": request_id,
            "attempts": 1,
            "provider": result.get("provider") or IMAGE_PROVIDER,
            "model": result.get("model") or IMAGE_MODEL,
            "quality": "standard",
            "image_pro_used": False,
            "output_path": str(output),
            "sha256": _sha256(output),
            "provider_output_path": result.get("provider_output_path"),
            "provider_output_sha256": (
                _sha256(Path(result["provider_output_path"]))
                if result.get("provider_output_path")
                and Path(result["provider_output_path"]).is_file()
                else None
            ),
            "provider_output_size": result.get("provider_output_size"),
            "normalized_output_size": result.get("normalized_output_size"),
            "local_aspect_normalization": result.get("local_aspect_normalization"),
        })
        return output

    character = generate("character_reference", 1, character_prompt, refs_dir / "character_reference.png", None)
    opening_images = [
        generate("opening_candidate", index + 1, prompt, images_dir / f"opening_{index + 1:02d}.png", character)
        for index, prompt in enumerate(candidate_prompts)
    ]
    body_images = [
        generate(
            "body", index + 1, get_scene_prompt(scene, "image"),
            images_dir / f"body_{index + 1:02d}.png", character,
        )
        for index, scene in enumerate(storyboard)
    ]
    if len(image_calls) != 25:
        raise CatLifeExactError(f"exact image call budget drifted to {len(image_calls)} instead of 25")
    body_hashes = [_sha256(path) for path in body_images]
    if len(set(body_hashes)) != 19:
        raise CatLifeExactError("cat_life body image content hashes are not all unique")
    image_budget_path = _write_json(technical_dir / "image_generation_budget.json", {
        "provider": IMAGE_PROVIDER,
        "model": IMAGE_MODEL,
        "quality": "standard",
        "image_pro_used": False,
        "serial": True,
        "automatic_retries": 0,
        "expected_calls": 25,
        "actual_calls": len(image_calls),
        "calls": image_calls,
        "body_unique_paths": len({str(path.resolve()) for path in body_images}) == 19,
        "body_unique_hashes": len(set(body_hashes)) == 19,
    })

    opening_narration = str(opening["opening_narration"]).strip()
    body_narration = [str(scene.get("narration") or "").strip() for scene in storyboard]
    if any(not text for text in body_narration):
        raise CatLifeExactError("all nineteen body cuts require narration for unified TTS")
    narration_text = "\n".join([opening_narration, *body_narration])
    narration_path = audios_dir / "cat_life_unified_narration.mp3"
    tts_request_id = scoped_request_id(
        prefix="cat-life-tts",
        output_dir=workspace,
        logical_key="unified-narration",
    )
    if callable(callback):
        callback("paid_media_started", provider="minimax", model=TTS_MODEL, request_id=tts_request_id)
    tts_result = tts_synthesizer(
        narration_text,
        str(narration_path),
        voice_type=TTS_VOICE,
        speed=TTS_SPEED,
        request_id=tts_request_id,
    )
    if not tts_result.get("success") or not narration_path.is_file():
        raise CatLifeExactError(
            f"single MiniMax request {tts_request_id} failed without fallback/retry: "
            f"{tts_result.get('error') or 'audio missing'}"
        )
    narration_duration = _probe(narration_path)["duration"]
    tts_manifest_path = _write_json(technical_dir / "tts_manifest.json", {
        "provider": "minimax",
        "model": TTS_MODEL,
        "voice": TTS_VOICE,
        "speed": TTS_SPEED,
        "request_id": tts_request_id,
        "calls": 1,
        "automatic_retries": 0,
        "fallback_used": False,
        "output_path": str(narration_path),
        "duration_seconds": narration_duration,
        "text_sha256": hashlib.sha256(narration_text.encode("utf-8")).hexdigest(),
    })

    opening_duration = float(opening["duration_seconds"])
    body_total = narration_duration - opening_duration
    body_durations = _bounded_durations(
        [float(scene["duration"]) for scene in storyboard], body_total
    )

    capsule_dir = Path(__file__).resolve().parents[3] / "capsules" / "cat_life.capsule"
    assets = capsule_dir / "assets"
    sfx_path = audios_dir / "cat_life_opening_sfx.wav"
    sfx_manifest = technical_dir / "opening_sfx_manifest.json"
    _run([
        sys.executable, str(assets / "gear_lock_opening_sfx_mixer.py"),
        "--output", str(sfx_path), "--manifest", str(sfx_manifest),
        "--duration", f"{opening_duration:.6f}", "--gear-start", "0.20",
        "--gear-end", f"{float(opening['identity_lock_seconds']):.6f}",
        "--landing-at", f"{float(opening['landing_at_seconds']):.6f}",
    ], label="packaged cat_life opening SFX mixer")

    opening_video = videos_dir / "00_cat_life_opening.mp4"
    opening_manifest = technical_dir / "opening_renderer_manifest.json"
    renderer_command = [
        sys.executable, str(assets / "cat_fate_flipbook_opening_renderer.py"),
        "--output", str(opening_video), "--manifest", str(opening_manifest),
        "--aspect-ratio", aspect_ratio, "--topic", str(state.get("capsule_params", {}).get("topic") or state.get("video_title") or "模拟猫生"),
        "--candidate-terms", json.dumps(candidate_lives, ensure_ascii=False),
        "--result-index", str(result_index), "--duration", f"{opening_duration:.6f}",
        "--lock-at", f"{float(opening['identity_lock_seconds']):.6f}",
        "--impact-at", f"{float(opening['landing_at_seconds']):.6f}",
        "--refresh-count", str(int(opening["refresh_count"])),
        "--sfx", str(sfx_path), "--sfx-volume", "1.0",
    ]
    for path in opening_images:
        renderer_command.extend(["--candidate-image", str(path)])
    params = state.get("capsule_params") or {}
    if params.get("opening_font_bold_path"):
        renderer_command.extend(["--font-bold", str(params["opening_font_bold_path"])])
    if params.get("opening_font_regular_path"):
        renderer_command.extend(["--font-regular", str(params["opening_font_regular_path"])])
    _run(renderer_command, label="native cat_life flipbook renderer")

    body_clips: list[Path] = []
    for index, (image_path, duration) in enumerate(zip(body_images, body_durations), start=1):
        clip = videos_dir / f"body_{index:02d}.mp4"
        _render_body_clip(image_path, clip, duration, size)
        body_clips.append(clip)

    concat_list = assembly_dir / "visual_concat.txt"
    concat_list.write_text(
        "".join(f"file '{str(path).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n" for path in [opening_video, *body_clips]),
        encoding="utf-8",
    )
    clean_concat = assembly_dir / "01_concat.mp4"
    _run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", str(concat_list), "-map", "0:v:0", "-an", "-c:v", "libx264",
        "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30",
        "-t", f"{narration_duration:.6f}", "-movflags", "+faststart", str(clean_concat),
    ], label="clean cat_life visual concat")

    bgm_path = music_dir / "cat_life_original_programmatic_bgm.wav"
    _generate_programmatic_bgm(bgm_path, narration_duration)
    bgm_manifest_path = _write_json(technical_dir / "bgm_manifest.json", {
        "source": "locally generated deterministic FFmpeg synthesis",
        "third_party_recording_used": False,
        "suno_used": False,
        "output_path": str(bgm_path),
        "sha256": _sha256(bgm_path),
    })

    final_video = public_dir / "cat_life.mp4"
    _run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(clean_concat),
        "-i", str(narration_path), "-i", str(sfx_path), "-i", str(bgm_path),
        "-filter_complex",
        f"[1:a]volume=1.0,atrim=0:{narration_duration:.6f}[voice];"
        f"[2:a]volume=1.0,apad=whole_dur={narration_duration:.6f},atrim=0:{narration_duration:.6f}[sfx];"
        f"[3:a]volume=0.06,atrim=0:{narration_duration:.6f}[bgm];"
        f"[voice][sfx][bgm]amix=inputs=3:duration=longest:normalize=0,"
        f"atrim=0:{narration_duration:.6f},alimiter=limit=0.95[a]",
        "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-t", f"{narration_duration:.6f}", "-movflags", "+faststart", str(final_video),
    ], label="cat_life final audio assembly")

    opening_data = json.loads(opening_manifest.read_text(encoding="utf-8"))
    font_path = opening_data["fonts"]["bold"]
    cover_path = public_dir / "cover.jpg"
    _cover([opening_images[result_index], body_images[8], body_images[-1]], cover_path, state.get("video_title") or "模拟猫生", font_path, size)
    contact_sheet = qa_dir / "contact_sheet.jpg"
    _contact_sheet([character, *opening_images, *body_images], contact_sheet)

    publishing = {
        "platform": state.get("platform") or "douyin",
        "title": state.get("video_title") or "模拟猫生",
        "cover_text": state.get("video_title") or "模拟猫生",
        "disclosure": "本视频为 AI 生成的虚构猫城故事，人物、地点与情节均为虚构。",
        "body": "如果你抽中这段猫生，会在第几个选择停下来？\n\n本视频为 AI 生成的虚构故事。",
    }
    publishing_path = _write_json(public_dir / "publishing_package.json", publishing)
    (public_dir / "publishing_copy.txt").write_text(
        f"{publishing['title']}\n\n{publishing['body']}\n", encoding="utf-8"
    )

    final_probe = _probe(final_video)
    video_stream = next((item for item in final_probe.get("streams", []) if item.get("codec_type") == "video"), {})
    audio_stream = next((item for item in final_probe.get("streams", []) if item.get("codec_type") == "audio"), {})
    drift = abs(final_probe["duration"] - narration_duration)
    qa = {
        "ok": bool(
            final_video.is_file() and video_stream and audio_stream and drift < 0.3
            and len(set(body_hashes)) == 19 and len(image_calls) == 25
        ),
        "final_video": str(final_video),
        "duration_seconds": final_probe["duration"],
        "narration_duration_seconds": narration_duration,
        "duration_drift_seconds": drift,
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "video_codec": video_stream.get("codec_name"),
        "audio_codec": audio_stream.get("codec_name"),
        "body_subtitles": False,
        "image_calls": len(image_calls),
        "body_unique_image_hashes": len(set(body_hashes)),
        "opening_renderer": opening_data.get("renderer"),
        "opening_sfx_mixer": json.loads(sfx_manifest.read_text(encoding="utf-8")).get("mixer"),
        "blockers": [],
    }
    if not qa["ok"]:
        qa["blockers"].append("cat_life_exact_release_gate_failed")
    qa_path = _write_json(qa_dir / "cat_life_exact_qa.json", qa)
    if not qa["ok"]:
        raise CatLifeExactError("cat_life exact QA failed")

    release_checkpoint = {
        "status": "pass",
        "release_ready": True,
        "blockers": [],
        "checks": {
            "exact_image_budget": True,
            "single_minimax_tts": True,
            "native_opening_renderer": True,
            "native_sfx_mixer": True,
            "unique_body_images": True,
            "body_subtitles_disabled": True,
            "duration_aligned_to_tts": drift < 0.3,
        },
    }
    checkpoint_path = _write_json(qa_dir / "cat_life_release_checkpoint.json", release_checkpoint)

    prompts_dir = workspace / "prompts"
    prompt_entries = []
    for call in image_calls:
        prompt_entries.append({
            "category": "image", "role": call["role"], "request_id": call["request_id"],
            "model": IMAGE_MODEL, "quality": "standard", "output_path": call["output_path"],
        })
    prompt_entries.append({
        "category": "tts", "request_id": tts_request_id, "model": TTS_MODEL,
        "voice": TTS_VOICE, "speed": TTS_SPEED, "calls": 1, "output_path": str(narration_path),
    })
    prompt_index = _write_json(prompts_dir / "prompt_index.json", {
        "schema": "capsule_cinema.prompt_index.v1",
        "capsule": "cat_life",
        "agno_planner_skipped": True,
        "entries": prompt_entries,
    })

    artifacts = []
    for category, path, title in [
        ("final_video", final_video, "Cat Life final video"),
        ("cover", cover_path, "Cat Life cover"),
        ("contact_sheet", contact_sheet, "Cat Life review contact sheet"),
        ("publishing_package", Path(publishing_path), "Cat Life publishing package"),
        ("voiceover", narration_path, "Cat Life unified MiniMax narration"),
        ("bgm", bgm_path, "Cat Life original programmatic BGM"),
        ("qa_report", Path(qa_path), "Cat Life exact QA report"),
        ("release_checkpoint", Path(checkpoint_path), "Cat Life release checkpoint"),
        ("storyboard", Path(state["storyboard_path"]), "Cat Life locked storyboard"),
        ("provider_request_ledger", Path(prompt_index), "Cat Life Provider request index"),
        ("provider_request_ledger", Path(image_budget_path), "Cat Life image request ledger"),
        ("audio_qa", Path(tts_manifest_path), "Cat Life TTS manifest"),
        ("decision_log", Path(bgm_manifest_path), "Cat Life BGM generation record"),
        ("capsule_gate_report", opening_manifest, "Cat Life opening renderer manifest"),
        ("capsule_gate_report", sfx_manifest, "Cat Life opening SFX manifest"),
    ]:
        artifacts.append({
            "category": category,
            "title": title,
            "path": str(path),
            "size_bytes": path.stat().st_size,
        })
    artifacts.append({
        "category": "character_ref",
        "title": "Cat Life normalized character reference",
        "path": str(character),
        "size_bytes": character.stat().st_size,
    })
    artifacts.extend({
        "category": "storyboard_image",
        "title": f"Cat Life normalized storyboard image {index:02d}",
        "path": str(path),
        "size_bytes": path.stat().st_size,
    } for index, path in enumerate([*opening_images, *body_images], start=1))
    artifacts.extend({
        "category": "scene_video",
        "title": f"Cat Life scene video {index:02d}",
        "path": str(path),
        "size_bytes": path.stat().st_size,
    } for index, path in enumerate([opening_video, *body_clips], start=1))
    for call in image_calls:
        provider_path = call.get("provider_output_path")
        if provider_path and Path(provider_path).is_file():
            artifacts.append({
                "category": "source_visual",
                "title": (
                    "Cat Life original Provider image "
                    f"{int(call['sequence']):02d} ({call['role']})"
                ),
                "path": str(provider_path),
                "size_bytes": Path(provider_path).stat().st_size,
            })

    manifest = {
        "schema_version": 1,
        "status": "complete",
        "deliverable": True,
        "release_recommendation": "pass",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "workflow": "general_video",
        "capsule": "cat_life",
        "capsule_version": CAT_LIFE_CAPSULE_VERSION,
        "workspace_dir": str(workspace),
        "video_title": state.get("video_title"),
        "final_video": str(final_video),
        "cover": str(cover_path),
        "contact_sheet": str(contact_sheet),
        "publishing_package": publishing_path,
        "qa_report": qa_path,
        "release_checkpoint": checkpoint_path,
        "technical": {
            "image_provider": IMAGE_PROVIDER,
            "image_model": IMAGE_MODEL,
            "image_pro_used": False,
            "aspect_ratio": aspect_ratio,
            "body_subtitles": False,
            "opening": opening_data["technical"]["opening"],
            "agno_planner_skipped": True,
            "image_expected_calls": 25,
            "image_actual_calls": 25,
            "tts_calls": 1,
            "tts_model": TTS_MODEL,
            "tts_voice": TTS_VOICE,
            "tts_speed": TTS_SPEED,
            "body_unique_image_hashes": 19,
        },
        "generation_summary": {
            "total_scenes": 19,
            "video_engine": "local_exact_micro_cut",
            "video_route": "unique_image2_keyframes_with_micro_cuts",
            "image_generation": {"total": 25, "successful": 25, "failed": 0},
            "video_generation": {"total": 20, "generated": 20, "failed": 0},
            "audio_generated": True,
            "subtitles_added": False,
            "bgm_added": True,
            "generation_blockers": [],
        },
        "technical_evidence": {
            "image_budget": image_budget_path,
            "tts_manifest": tts_manifest_path,
            "bgm_manifest": bgm_manifest_path,
            "opening_manifest": str(opening_manifest),
            "opening_sfx_manifest": str(sfx_manifest),
        },
        "artifacts": artifacts,
    }
    artifact_manifest_path = _write_json(workspace / "artifact_manifest.json", manifest)

    state.update({
        "final_video": str(final_video),
        "cover_image": str(cover_path),
        "contact_sheet": str(contact_sheet),
        "artifact_manifest_path": artifact_manifest_path,
        "references_result": {"outputs": {"protagonist_cat": str(character)}},
        "image_generation_result": {
            "outputs": {index: str(path) for index, path in enumerate(body_images)},
            "details": [call for call in image_calls if call["role"] == "body"],
            "summary": {"total_scenes": 19, "successful": 19, "failed": 0, "provider_calls": 25},
        },
        "video_generation_result": {
            "outputs": {index: str(path) for index, path in enumerate(body_clips)},
            "summary": {"total": 19, "generated": 19, "failed": 0, "video_route": "unique_image2_keyframes_with_micro_cuts"},
        },
        "audio_generation_result": {
            "outputs": [str(narration_path)],
            "summary": {"calls": 1, "provider": "minimax", "model": TTS_MODEL},
        },
        "bgm_added_result": True,
        "social_media_copywriting": {"saved_path": publishing_path, "platform": state.get("platform")},
        "cat_life_exact": True,
    })
    return {
        "success": True,
        "video_type": "general_video",
        "workspace_dir": str(workspace),
        "output_paths": {key: str(value) for key, value in dirs.items()},
        "final_video": str(final_video),
        "cover_image": str(cover_path),
        "contact_sheet": str(contact_sheet),
        "storyboard": storyboard,
        "storyboard_path": state["storyboard_path"],
        "artifact_manifest_path": artifact_manifest_path,
        "video_title": state.get("video_title"),
        "social_media_copywriting": state["social_media_copywriting"],
        "generation_blockers": [],
        "generation_summary": {
            "total_scenes": 19,
            "video_engine": "local_exact_micro_cut",
            "video_route": "unique_image2_keyframes_with_micro_cuts",
            "video_generated": 20,
            "video_failed": 0,
            "image_generated": 25,
            "image_failed": 0,
            "audio_generated": True,
            "subtitles_added": False,
            "bgm_added": True,
            "provider_image_calls": 25,
            "provider_tts_calls": 1,
        },
        "cat_life_exact": True,
    }
