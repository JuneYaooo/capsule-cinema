"""Official Volcengine Ark Seedance task adapter (Seedance 2.0 and 2.5).

One implementation serves every Seedance engine. Each tool class is bound to an
engine key (``seedance2.0``, ``seedance2.5``); model id, duration range, reference
counts and reference-length limits all come from ``lib/config/video_engines.yaml``
through :mod:`src.video_engines`, so new limits are a config change.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional, Sequence, Type

import requests
from pydantic import BaseModel, Field

from custom_tools.audio_generation.base_tool_compat import BaseTool
from src.video_engines import VideoEngineSpec, require_engine_spec
from .output_dir_utils import default_video_output_dir, resolve_video_output_dir
from .reference_media import MediaResolver, MediaUploadError, check_durations


DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_ENGINE = "seedance2.0"
DEFAULT_SEEDANCE_MODEL = "doubao-seedance-2-0-260128"  # kept for backward-compatible imports
DEFAULT_OUTPUT_DIR = default_video_output_dir("volcengine_seedance")
GENERATION_TYPES = ("text_to_video", "image_to_video", "first_last_frame", "multimodal")


class VolcengineSeedanceSchema(BaseModel):
    prompt: str = Field(..., description="Video prompt; refer to references as 图片1/视频1/音频1 in list order")
    generation_type: str = Field(
        "text_to_video",
        description=(
            "text_to_video, image_to_video (first frame only), first_last_frame (first+last frame only), "
            "or multimodal (reference images/videos/audios). Frame modes and references cannot be mixed."
        ),
    )
    output_dir: str = Field(DEFAULT_OUTPUT_DIR, description="Local output directory")
    output_path: Optional[str] = Field(None, description="Exact local output path")
    image_path: Optional[str] = Field(None, description="First frame (image_to_video) or first reference image (multimodal)")
    image_paths: Optional[list[str]] = Field(None, description="Reference images; per-engine limit from video_engines.yaml")
    first_frame_path: Optional[str] = Field(None, description="First-frame image")
    last_frame_path: Optional[str] = Field(None, description="Last-frame image")
    start_image_path: Optional[str] = Field(None, description="Compatibility alias for first_frame_path")
    end_image_path: Optional[str] = Field(None, description="Compatibility alias for last_frame_path")
    images: Optional[list[str]] = Field(None, description="Compatibility list for first/last/reference images")
    video_paths: Optional[list[str]] = Field(
        None, description="Reference videos (URL, asset://, or local file uploaded via CAPSULE_MEDIA_UPLOADER)"
    )
    audio_paths: Optional[list[str]] = Field(None, description="Reference audios; per-engine limit from video_engines.yaml")
    aspect_ratio: str = Field("9:16", description="16:9, 4:3, 1:1, 3:4, 9:16, 21:9, or adaptive")
    ratio: Optional[str] = Field(None, description="Official ratio alias; overrides aspect_ratio")
    resolution: str = Field("720p", description="480p, 720p, 1080p, or 4k")
    duration: int | str = Field(5, description="Whole seconds within the engine's duration_range, or -1 for automatic")
    generate_audio: bool = Field(True, description="Generate synchronized model audio")
    watermark: bool = Field(False, description="Add provider watermark")
    return_last_frame: bool = Field(False, description="Download the generated last frame")
    callback_url: Optional[str] = Field(None, description="Optional task-status callback URL")
    execution_expires_after: int = Field(172800, description="Task expiry in seconds")
    priority: int = Field(0, description="Queue priority from 0 to 9")
    safety_identifier: Optional[str] = Field(None, description="Stable end-user safety identifier")
    service_tier: Optional[str] = Field(None, description="Seedance 2.x only supports default online inference")
    max_wait: Optional[int] = Field(None, description="Seconds to wait for the task; defaults per engine")


def _unique(values: Optional[Sequence[str]]) -> list[str]:
    result: list[str] = []
    for value in values or []:
        if value and value not in result:
            result.append(value)
    return result


def _seconds(value: int | float | str, engine: str = DEFAULT_ENGINE) -> int:
    return require_engine_spec(engine).validate_duration(value)


def validate_references(
    spec: VideoEngineSpec,
    *,
    generation_type: str,
    first_frame: Optional[str],
    last_frame: Optional[str],
    references: Sequence[str],
    videos: Sequence[str],
    audios: Sequence[str],
) -> None:
    """Enforce Ark's request rules for one engine before any network call."""

    if generation_type not in GENERATION_TYPES:
        raise ValueError(f"Unsupported generation_type: {generation_type}")
    frames = int(bool(first_frame)) + int(bool(last_frame))
    has_references = bool(references or videos or audios)
    label = spec.key

    if last_frame and not first_frame:
        raise ValueError("last_frame_path requires first_frame_path or image_path")
    # Ark: first-frame, first+last-frame and multimodal reference are mutually exclusive scenarios.
    if frames and has_references:
        raise ValueError(
            f"{label}: first/last frames cannot be combined with reference images, videos or audios; "
            "use multimodal and describe the frame in the prompt, or drop the references"
        )
    if generation_type == "text_to_video" and (frames or has_references):
        raise ValueError("text_to_video does not accept media; use image_to_video, first_last_frame, or multimodal")
    if generation_type == "image_to_video" and not first_frame:
        raise ValueError("image_to_video requires an input image")
    if generation_type == "image_to_video" and last_frame:
        raise ValueError("image_to_video takes one frame; use first_last_frame for two")
    if generation_type == "first_last_frame" and not (first_frame and last_frame):
        raise ValueError("first_last_frame requires both first_frame_path and last_frame_path")
    if generation_type == "multimodal":
        if not has_references:
            raise ValueError("multimodal requires at least one reference image, video or audio")
        if audios and not (references or videos) and not spec.cap("audio_only_reference", False):
            raise ValueError(f"{label} audio references require at least one image or video")

    for kind, items in (("image", references), ("video", videos), ("audio", audios)):
        limit = spec.max_references(kind)
        if len(items) > limit:
            raise ValueError(f"{label} supports at most {limit} reference {kind}s (got {len(items)})")

    check_durations(
        [value for value in videos],
        kind="video",
        per_item_range=spec.cap("reference_video_seconds"),
        max_total=spec.cap("max_reference_video_total_seconds"),
    )
    check_durations(
        [value for value in audios],
        kind="audio",
        per_item_range=spec.cap("reference_audio_seconds"),
        max_total=spec.cap("max_reference_audio_total_seconds"),
    )


def _split_media(
    generation_type: str,
    image_path: Optional[str],
    image_paths: Optional[Sequence[str]],
    first_frame_path: Optional[str],
    last_frame_path: Optional[str],
) -> tuple[Optional[str], Optional[str], list[str]]:
    """Return (first_frame, last_frame, reference_images) for a generation type."""
    references = _unique(image_paths)
    if generation_type == "multimodal":
        # In reference mode a single image is a reference, never a first frame.
        if image_path:
            references = _unique([image_path, *references])
        return first_frame_path, last_frame_path, references
    first_frame = first_frame_path or image_path
    if image_path and first_frame_path and image_path != first_frame_path:
        references = _unique([image_path, *references])
    references = [value for value in references if value not in {first_frame, last_frame_path}]
    return first_frame, last_frame_path, references


def build_video_content(
    *,
    prompt: str,
    generation_type: str = "text_to_video",
    image_path: Optional[str] = None,
    image_paths: Optional[Sequence[str]] = None,
    first_frame_path: Optional[str] = None,
    last_frame_path: Optional[str] = None,
    video_paths: Optional[Sequence[str]] = None,
    audio_paths: Optional[Sequence[str]] = None,
    engine: str = DEFAULT_ENGINE,
    media_resolver: Optional[MediaResolver] = None,
) -> list[dict[str, Any]]:
    """Build official Ark multimodal content within the engine's limits."""

    spec = require_engine_spec(engine)
    first_frame, last_frame, references = _split_media(
        generation_type, image_path, image_paths, first_frame_path, last_frame_path
    )
    videos = _unique(video_paths)
    audios = _unique(audio_paths)
    validate_references(
        spec,
        generation_type=generation_type,
        first_frame=first_frame,
        last_frame=last_frame,
        references=references,
        videos=videos,
        audios=audios,
    )
    if not prompt.strip() and not (first_frame or references or videos):
        raise ValueError("A prompt or visual reference is required")

    resolver = media_resolver or MediaResolver()
    content: list[dict[str, Any]] = []
    if prompt.strip():
        content.append({"type": "text", "text": prompt})
    if first_frame:
        content.append(
            {"type": "image_url", "image_url": {"url": resolver.resolve(first_frame, "image")}, "role": "first_frame"}
        )
    if last_frame:
        content.append(
            {"type": "image_url", "image_url": {"url": resolver.resolve(last_frame, "image")}, "role": "last_frame"}
        )
    # Order inside each kind matches the caller's list, so 图片N / 视频N / 音频N stay aligned.
    content.extend(
        {"type": "image_url", "image_url": {"url": resolver.resolve(value, "image")}, "role": "reference_image"}
        for value in references
    )
    content.extend(
        {"type": "video_url", "video_url": {"url": resolver.resolve(value, "video")}, "role": "reference_video"}
        for value in videos
    )
    content.extend(
        {"type": "audio_url", "audio_url": {"url": resolver.resolve(value, "audio")}, "role": "reference_audio"}
        for value in audios
    )
    return content


def build_video_payload(
    *,
    prompt: str,
    model: Optional[str] = None,
    generation_type: str = "text_to_video",
    image_path: Optional[str] = None,
    image_paths: Optional[Sequence[str]] = None,
    first_frame_path: Optional[str] = None,
    last_frame_path: Optional[str] = None,
    video_paths: Optional[Sequence[str]] = None,
    audio_paths: Optional[Sequence[str]] = None,
    ratio: str = "9:16",
    resolution: str = "720p",
    duration: int | str = 5,
    generate_audio: bool = True,
    watermark: bool = False,
    return_last_frame: bool = False,
    callback_url: Optional[str] = None,
    execution_expires_after: int = 172800,
    priority: int = 0,
    safety_identifier: Optional[str] = None,
    service_tier: Optional[str] = None,
    engine: str = DEFAULT_ENGINE,
    media_resolver: Optional[MediaResolver] = None,
) -> dict[str, Any]:
    spec = require_engine_spec(engine)
    normalized_ratio = ratio.strip().lower()
    if normalized_ratio not in {value.lower() for value in spec.cap("aspect_ratios", [])}:
        raise ValueError(f"Unsupported {spec.key} ratio: {ratio}")
    if (
        spec.cap("frame_modes_require_adaptive_ratio", False)
        and generation_type in {"image_to_video", "first_last_frame"}
    ):
        # Ark requires ratio=adaptive for 2.5 frame tasks; the frame image decides the shape.
        normalized_ratio = "adaptive"
    normalized_resolution = resolution.strip().lower()
    if normalized_resolution not in {value.lower() for value in spec.cap("resolutions", [])}:
        raise ValueError(f"Unsupported {spec.key} resolution: {resolution}")
    if service_tier not in {None, "", "default"}:
        raise ValueError(f"{spec.key} only supports default online inference; flex is unavailable")
    if not 3600 <= int(execution_expires_after) <= 259200:
        raise ValueError("execution_expires_after must be between 3600 and 259200 seconds")
    if not 0 <= int(priority) <= 9:
        raise ValueError("priority must be between 0 and 9")
    if safety_identifier is not None and (not safety_identifier.isascii() or len(safety_identifier) > 64):
        raise ValueError("safety_identifier must be an ASCII string no longer than 64 characters")
    if callback_url and not callback_url.startswith(("https://", "http://")):
        raise ValueError("callback_url must be an HTTP(S) URL")
    resolved_duration = spec.validate_duration(duration)

    payload: dict[str, Any] = {
        "model": model or spec.resolve_model(),
        "content": build_video_content(
            prompt=prompt,
            generation_type=generation_type,
            image_path=image_path,
            image_paths=image_paths,
            first_frame_path=first_frame_path,
            last_frame_path=last_frame_path,
            video_paths=video_paths,
            audio_paths=audio_paths,
            engine=spec.key,
            media_resolver=media_resolver,
        ),
        "resolution": normalized_resolution,
        "ratio": normalized_ratio,
        "duration": resolved_duration,
        "generate_audio": bool(generate_audio),
        "watermark": bool(watermark),
        "return_last_frame": bool(return_last_frame),
        "execution_expires_after": int(execution_expires_after),
        "priority": int(priority),
    }
    if callback_url:
        payload["callback_url"] = callback_url
    if safety_identifier:
        payload["safety_identifier"] = safety_identifier
    # Seedance 2.x only supports online inference and does not accept a mutable
    # service_tier, seed, frames, or camera_fixed parameter.
    return payload


def _task_content(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("content")
    return value if isinstance(value, dict) else {}


def _task_url(payload: dict[str, Any], key: str) -> str:
    value = _task_content(payload).get(key)
    if isinstance(value, dict):
        value = value.get("url")
    return value if isinstance(value, str) and value.startswith(("https://", "http://")) else ""


def _download(url: str, destination: Path, *, timeout: int = 300) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, stream=True, timeout=timeout)
    response.raise_for_status()
    with destination.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)


def _response_error_code(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    error = payload.get("error") if isinstance(payload, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, str) else ""


def _task_error_code(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, str) else ""


class VolcengineSeedanceVideoGeneratorTool(BaseTool):
    """Seedance on the official Ark task API, bound to one engine key."""

    name: str = "Volcengine Ark Seedance 2.0 video generator"
    description: str = "Generate official Seedance 2.0 videos and download expiring results locally."
    args_schema: Type[BaseModel] = VolcengineSeedanceSchema
    engine_key: str = DEFAULT_ENGINE

    def _fail(self, error: str, **fields: Any) -> dict[str, Any]:
        return {"success": False, "engine": self.engine_key, "error": error, **fields}

    def _run(
        self,
        prompt: str,
        generation_type: str = "text_to_video",
        output_dir: str = DEFAULT_OUTPUT_DIR,
        output_path: Optional[str] = None,
        image_path: Optional[str] = None,
        image_paths: Optional[list[str]] = None,
        first_frame_path: Optional[str] = None,
        last_frame_path: Optional[str] = None,
        start_image_path: Optional[str] = None,
        end_image_path: Optional[str] = None,
        images: Optional[list[str]] = None,
        video_paths: Optional[list[str]] = None,
        audio_paths: Optional[list[str]] = None,
        aspect_ratio: str = "9:16",
        ratio: Optional[str] = None,
        resolution: str = "720p",
        duration: int | str = 5,
        generate_audio: bool = True,
        watermark: bool = False,
        return_last_frame: bool = False,
        callback_url: Optional[str] = None,
        execution_expires_after: int = 172800,
        priority: int = 0,
        safety_identifier: Optional[str] = None,
        service_tier: Optional[str] = None,
        poll_interval: int = 8,
        max_wait: Optional[int] = None,
        dry_run: bool = False,
        **extra: Any,
    ) -> dict[str, Any]:
        """Generate one video. ``dry_run=True`` validates the job and returns the request
        summary without uploading media or calling the provider (no cost)."""
        spec = require_engine_spec(self.engine_key)
        unsupported = [name for name in ("seed", "frames", "camera_fixed") if extra.get(name) is not None]
        if unsupported:
            return self._fail(f"{spec.key} does not support: " + ", ".join(unsupported))
        generation_type = str(generation_type or "text_to_video").strip().lower()

        legacy_images = _unique(images)
        resolved_image_paths = _unique(image_paths)
        if generation_type == "first_last_frame":
            first_frame_path = first_frame_path or start_image_path or (legacy_images[0] if legacy_images else None)
            last_frame_path = last_frame_path or end_image_path or (legacy_images[1] if len(legacy_images) > 1 else None)
            resolved_image_paths = _unique(resolved_image_paths + legacy_images[2:])
        elif generation_type == "image_to_video":
            image_path = image_path or start_image_path or (legacy_images[0] if legacy_images else None)
            resolved_image_paths = _unique(resolved_image_paths + legacy_images[1:])
        else:
            resolved_image_paths = _unique(resolved_image_paths + legacy_images)

        model = spec.resolve_model()
        api_key = os.getenv("ARK_API_KEY")
        if not api_key and not dry_run:
            return self._fail("Missing required env var: ARK_API_KEY")
        try:
            payload = build_video_payload(
                prompt=prompt,
                model=model,
                generation_type=generation_type,
                image_path=image_path,
                image_paths=resolved_image_paths,
                first_frame_path=first_frame_path,
                last_frame_path=last_frame_path,
                video_paths=video_paths,
                audio_paths=audio_paths,
                ratio=ratio or aspect_ratio,
                resolution=resolution,
                duration=duration,
                generate_audio=generate_audio,
                watermark=watermark,
                return_last_frame=return_last_frame,
                callback_url=callback_url,
                execution_expires_after=execution_expires_after,
                priority=priority,
                safety_identifier=safety_identifier,
                service_tier=service_tier,
                engine=spec.key,
                media_resolver=MediaResolver(uploader_factory=_PlaceholderUploader) if dry_run else None,
            )
        except (ValueError, FileNotFoundError) as exc:
            return self._fail(f"Volcengine Ark video validation error: {exc}")
        except MediaUploadError as exc:
            return self._fail(f"Reference media upload error: {exc}")

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "engine": spec.key,
                "model": payload["model"],
                "generation_type": generation_type,
                "request": _summarize_payload(payload),
            }
        return self._submit_and_download(
            payload,
            api_key=api_key,
            generation_type=generation_type,
            output_dir=output_dir,
            output_path=output_path,
            return_last_frame=return_last_frame,
            poll_interval=poll_interval,
            max_wait=int(max_wait) if max_wait else spec.default_max_wait_seconds,
        )

    def _submit_and_download(
        self,
        payload: dict[str, Any],
        *,
        api_key: str,
        generation_type: str,
        output_dir: str,
        output_path: Optional[str],
        return_last_frame: bool,
        poll_interval: int,
        max_wait: int,
    ) -> dict[str, Any]:
        base_url = (os.getenv("ARK_BASE_URL") or DEFAULT_ARK_BASE_URL).rstrip("/")
        tasks_url = f"{base_url}/contents/generations/tasks"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        model = payload["model"]
        task_id = ""
        try:
            created = requests.post(tasks_url, headers=headers, json=payload, timeout=300)
            if created.status_code >= 400:
                error_code = _response_error_code(created)
                suffix = f" ({error_code})" if error_code else ""
                return self._fail(
                    f"Volcengine Ark video request failed: HTTP {created.status_code}{suffix}",
                    provider_error_code=error_code or None,
                    model=model,
                )
            result = created.json()
            task_id = str(result.get("id") or "")
            video_url = _task_url(result, "video_url")
            elapsed = 0
            while not video_url and task_id and elapsed <= max_wait:
                status_response = requests.get(f"{tasks_url}/{task_id}", headers=headers, timeout=60)
                if status_response.status_code >= 400:
                    error_code = _response_error_code(status_response)
                    suffix = f" ({error_code})" if error_code else ""
                    return self._fail(
                        f"Volcengine Ark task query failed: HTTP {status_response.status_code}{suffix}",
                        provider_error_code=error_code or None,
                        task_id=task_id,
                        model=model,
                    )
                result = status_response.json()
                status = str(result.get("status") or "").lower()
                if status in {"failed", "error", "cancelled", "canceled", "expired", "rejected"}:
                    error_code = _task_error_code(result)
                    suffix = f" ({error_code})" if error_code else ""
                    return self._fail(
                        f"Volcengine Ark task ended with status {status}{suffix}",
                        provider_error_code=error_code or None,
                        task_id=task_id,
                        model=model,
                    )
                video_url = _task_url(result, "video_url")
                if video_url or status == "succeeded" or elapsed >= max_wait:
                    break
                wait_seconds = max(1, int(poll_interval))
                time.sleep(wait_seconds)
                elapsed += wait_seconds
            if not video_url:
                # The task may still finish: keep task_id so the caller can resume instead of paying again.
                return self._fail(
                    f"Volcengine Ark task timed out after {max_wait}s or returned no video",
                    task_id=task_id,
                    model=model,
                )

            resolved_dir = resolve_video_output_dir(output_dir, output_path, DEFAULT_OUTPUT_DIR, ())
            destination = Path(output_path) if output_path else Path(resolved_dir) / f"seedance_{task_id or int(time.time())}.mp4"
            _download(video_url, destination)

            last_frame_path: Optional[str] = None
            last_frame_url = _task_url(result, "last_frame_url") or _task_url(result, "last_frame")
            if return_last_frame and last_frame_url:
                last_frame_destination = destination.with_name(f"{destination.stem}.last_frame.jpeg")
                _download(last_frame_url, last_frame_destination)
                last_frame_path = str(last_frame_destination)

            usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
            return {
                "success": True,
                "provider": "volcengine_ark",
                "engine": self.engine_key,
                "model": result.get("model") or model,
                "task_id": task_id,
                "output_path": str(destination),
                "last_frame_path": last_frame_path,
                "generation_type": generation_type,
                "resolution": result.get("resolution") or payload["resolution"],
                "ratio": result.get("ratio") or payload["ratio"],
                "duration": result.get("duration") if result.get("duration") is not None else payload["duration"],
                "generate_audio": (
                    result.get("generate_audio")
                    if isinstance(result.get("generate_audio"), bool)
                    else payload["generate_audio"]
                ),
                "usage": usage,
            }
        except (requests.RequestException, OSError) as exc:
            # RequestException messages may contain expiring signed result URLs.
            return self._fail(f"Volcengine Ark video error: {exc.__class__.__name__}", task_id=task_id or None, model=model)


class _PlaceholderUploader:
    """dry_run uploader: records what would be uploaded without touching storage."""

    def upload(self, path: Path) -> str:
        return f"upload://{path.name}"


def _summarize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Payload without base64 bodies, safe to log or print."""
    content = []
    for item in payload.get("content", []):
        kind = item.get("type")
        if kind == "text":
            content.append({"type": "text", "chars": len(item.get("text", ""))})
            continue
        url = str((item.get(kind) or {}).get("url") or "")
        content.append({"type": kind, "role": item.get("role"), "url": url[:40] + "…" if url.startswith("data:") else url})
    return {**{key: value for key, value in payload.items() if key != "content"}, "content": content}


class Seedance25VideoGeneratorTool(VolcengineSeedanceVideoGeneratorTool):
    name: str = "Volcengine Ark Seedance 2.5 video generator"
    description: str = (
        "Generate official Seedance 2.5 videos (up to 30 s, multi-shot, 30 image / 10 video / 10 audio "
        "references) and download expiring results locally."
    )
    engine_key: str = "seedance2.5"


# Backward-compatible public tool name used by existing official-route capsules.
Seedance20VideoGeneratorTool = VolcengineSeedanceVideoGeneratorTool
