"""Official Volcengine Ark Seedance 2.0 task adapter."""

from __future__ import annotations

import base64
import mimetypes
import os
import time
from pathlib import Path
from typing import Any, Optional, Sequence, Type

import requests
from pydantic import BaseModel, Field

from custom_tools.audio_generation.base_tool_compat import BaseTool
from .output_dir_utils import default_video_output_dir, resolve_video_output_dir


DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_SEEDANCE_MODEL = "doubao-seedance-2-0-260128"
DEFAULT_OUTPUT_DIR = default_video_output_dir("volcengine_seedance")
SEEDANCE_RATIOS = {"16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive"}
SEEDANCE_RESOLUTIONS = {"480p", "720p", "1080p", "4k"}


class VolcengineSeedanceSchema(BaseModel):
    prompt: str = Field(..., description="Video prompt")
    generation_type: str = Field(
        "text_to_video",
        description="text_to_video, image_to_video, first_last_frame, or multimodal",
    )
    output_dir: str = Field(DEFAULT_OUTPUT_DIR, description="Local output directory")
    output_path: Optional[str] = Field(None, description="Exact local output path")
    image_path: Optional[str] = Field(None, description="Legacy first-frame image")
    image_paths: Optional[list[str]] = Field(None, description="Reference images; maximum 9 total images")
    first_frame_path: Optional[str] = Field(None, description="First-frame image")
    last_frame_path: Optional[str] = Field(None, description="Last-frame image")
    start_image_path: Optional[str] = Field(None, description="Compatibility alias for first_frame_path")
    end_image_path: Optional[str] = Field(None, description="Compatibility alias for last_frame_path")
    images: Optional[list[str]] = Field(None, description="Compatibility list for first/last/reference images")
    video_paths: Optional[list[str]] = Field(None, description="Reference videos; maximum 3")
    audio_paths: Optional[list[str]] = Field(None, description="Reference audios; maximum 3")
    aspect_ratio: str = Field("9:16", description="16:9, 4:3, 1:1, 3:4, 9:16, 21:9, or adaptive")
    ratio: Optional[str] = Field(None, description="Official ratio alias; overrides aspect_ratio")
    resolution: str = Field("720p", description="480p, 720p, 1080p, or 4k")
    duration: int | str = Field(5, description="Integer seconds from 4 to 15, or -1 for automatic")
    generate_audio: bool = Field(True, description="Generate synchronized model audio")
    watermark: bool = Field(False, description="Add provider watermark")
    return_last_frame: bool = Field(False, description="Download the generated last frame")
    callback_url: Optional[str] = Field(None, description="Optional task-status callback URL")
    execution_expires_after: int = Field(172800, description="Task expiry in seconds")
    priority: int = Field(0, description="Queue priority from 0 to 9")
    safety_identifier: Optional[str] = Field(None, description="Stable end-user safety identifier")
    service_tier: Optional[str] = Field(None, description="Seedance 2.0 only supports default online inference")


def _seconds(value: int | float | str) -> int:
    text = str(value).strip().lower()
    if text.endswith("s"):
        text = text[:-1]
    numeric = float(text)
    if not numeric.is_integer():
        raise ValueError("Seedance 2.0 duration must use whole seconds")
    result = int(numeric)
    if result != -1 and not 4 <= result <= 15:
        raise ValueError("Seedance 2.0 duration must be an integer from 4 to 15, or -1")
    return result


def _media_url(value: str) -> str:
    if value.startswith(("https://", "http://", "data:")):
        return value
    source = Path(value).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"Reference media does not exist: {source}")
    mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _unique(values: Optional[Sequence[str]]) -> list[str]:
    result: list[str] = []
    for value in values or []:
        if value and value not in result:
            result.append(value)
    return result


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
) -> list[dict[str, Any]]:
    """Build official Ark multimodal content with Seedance 2.0 limits."""

    supported_types = {"text_to_video", "image_to_video", "first_last_frame", "multimodal"}
    if generation_type not in supported_types:
        raise ValueError(f"Unsupported generation_type: {generation_type}")

    references = _unique(image_paths)
    first_frame = first_frame_path
    if image_path:
        if first_frame and first_frame != image_path:
            references.insert(0, image_path)
        elif not first_frame:
            first_frame = image_path
    references = [value for value in _unique(references) if value not in {first_frame, last_frame_path}]
    videos = _unique(video_paths)
    audios = _unique(audio_paths)
    image_count = len(references) + int(bool(first_frame)) + int(bool(last_frame_path))

    if image_count > 9:
        raise ValueError("Seedance 2.0 supports at most 9 input images")
    if len(videos) > 3:
        raise ValueError("Seedance 2.0 supports at most 3 input videos")
    if len(audios) > 3:
        raise ValueError("Seedance 2.0 supports at most 3 input audios")
    if audios and not (image_count or videos):
        raise ValueError("Seedance 2.0 audio references require at least one image or video")
    if last_frame_path and not first_frame:
        raise ValueError("last_frame_path requires first_frame_path or image_path")
    if generation_type == "text_to_video" and (image_count or videos or audios):
        raise ValueError("text_to_video does not accept media; use image_to_video, first_last_frame, or multimodal")
    if generation_type == "image_to_video" and not image_count:
        raise ValueError("image_to_video requires an input image")
    if generation_type == "first_last_frame" and not (first_frame and last_frame_path):
        raise ValueError("first_last_frame requires both first_frame_path and last_frame_path")
    if generation_type == "multimodal" and not (image_count or videos):
        raise ValueError("multimodal requires at least one image or video")
    if not prompt.strip() and not (image_count or videos):
        raise ValueError("A prompt or visual reference is required")

    content: list[dict[str, Any]] = []
    if prompt.strip():
        content.append({"type": "text", "text": prompt})
    if first_frame:
        content.append(
            {"type": "image_url", "image_url": {"url": _media_url(first_frame)}, "role": "first_frame"}
        )
    if last_frame_path:
        content.append(
            {"type": "image_url", "image_url": {"url": _media_url(last_frame_path)}, "role": "last_frame"}
        )
    content.extend(
        {"type": "image_url", "image_url": {"url": _media_url(value)}, "role": "reference_image"}
        for value in references
    )
    content.extend(
        {"type": "video_url", "video_url": {"url": _media_url(value)}, "role": "reference_video"}
        for value in videos
    )
    content.extend(
        {"type": "audio_url", "audio_url": {"url": _media_url(value)}, "role": "reference_audio"}
        for value in audios
    )
    return content


def build_video_payload(
    *,
    prompt: str,
    model: str = DEFAULT_SEEDANCE_MODEL,
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
) -> dict[str, Any]:
    normalized_ratio = ratio.strip().lower()
    if normalized_ratio not in SEEDANCE_RATIOS:
        raise ValueError(f"Unsupported Seedance 2.0 ratio: {ratio}")
    normalized_resolution = resolution.strip().lower()
    if normalized_resolution not in SEEDANCE_RESOLUTIONS:
        raise ValueError(f"Unsupported Seedance 2.0 resolution: {resolution}")
    if service_tier not in {None, "", "default"}:
        raise ValueError("Seedance 2.0 only supports default online inference; flex is unavailable")
    if not 3600 <= int(execution_expires_after) <= 259200:
        raise ValueError("execution_expires_after must be between 3600 and 259200 seconds")
    if not 0 <= int(priority) <= 9:
        raise ValueError("priority must be between 0 and 9")
    if safety_identifier is not None and (not safety_identifier.isascii() or len(safety_identifier) > 64):
        raise ValueError("safety_identifier must be an ASCII string no longer than 64 characters")
    if callback_url and not callback_url.startswith(("https://", "http://")):
        raise ValueError("callback_url must be an HTTP(S) URL")

    payload: dict[str, Any] = {
        "model": model,
        "content": build_video_content(
            prompt=prompt,
            generation_type=generation_type,
            image_path=image_path,
            image_paths=image_paths,
            first_frame_path=first_frame_path,
            last_frame_path=last_frame_path,
            video_paths=video_paths,
            audio_paths=audio_paths,
        ),
        "resolution": normalized_resolution,
        "ratio": normalized_ratio,
        "duration": _seconds(duration),
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
    # Seedance 2.0 only supports online inference and does not accept a mutable
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
    name: str = "Volcengine Ark Seedance 2.0 video generator"
    description: str = "Generate official Seedance 2.0 videos and download expiring results locally."
    args_schema: Type[BaseModel] = VolcengineSeedanceSchema

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
        max_wait: int = 900,
        **extra: Any,
    ) -> dict[str, Any]:
        api_key = os.getenv("ARK_API_KEY")
        if not api_key:
            return {"success": False, "error": "Missing required env var: ARK_API_KEY"}
        unsupported = [name for name in ("seed", "frames", "camera_fixed") if extra.get(name) is not None]
        if unsupported:
            return {"success": False, "error": "Seedance 2.0 does not support: " + ", ".join(unsupported)}

        model = os.getenv("ARK_SEEDANCE_MODEL") or os.getenv("ARK_SEEDANCE20_MODEL") or DEFAULT_SEEDANCE_MODEL
        base_url = (os.getenv("ARK_BASE_URL") or DEFAULT_ARK_BASE_URL).rstrip("/")
        tasks_url = f"{base_url}/contents/generations/tasks"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
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
            )
            created = requests.post(tasks_url, headers=headers, json=payload, timeout=180)
            if created.status_code >= 400:
                error_code = _response_error_code(created)
                suffix = f" ({error_code})" if error_code else ""
                return {
                    "success": False,
                    "error": f"Volcengine Ark video request failed: HTTP {created.status_code}{suffix}",
                    "provider_error_code": error_code or None,
                }
            result = created.json()
            task_id = str(result.get("id") or "")
            video_url = _task_url(result, "video_url")
            elapsed = 0
            while not video_url and task_id and elapsed <= max_wait:
                status_response = requests.get(f"{tasks_url}/{task_id}", headers=headers, timeout=60)
                if status_response.status_code >= 400:
                    error_code = _response_error_code(status_response)
                    suffix = f" ({error_code})" if error_code else ""
                    return {
                        "success": False,
                        "error": f"Volcengine Ark task query failed: HTTP {status_response.status_code}{suffix}",
                        "provider_error_code": error_code or None,
                        "task_id": task_id,
                    }
                result = status_response.json()
                status = str(result.get("status") or "").lower()
                if status in {"failed", "error", "cancelled", "canceled", "expired", "rejected"}:
                    error_code = _task_error_code(result)
                    suffix = f" ({error_code})" if error_code else ""
                    return {
                        "success": False,
                        "error": f"Volcengine Ark task ended with status {status}{suffix}",
                        "provider_error_code": error_code or None,
                        "task_id": task_id,
                    }
                video_url = _task_url(result, "video_url")
                if video_url or status == "succeeded" or elapsed >= max_wait:
                    break
                wait_seconds = max(1, int(poll_interval))
                time.sleep(wait_seconds)
                elapsed += wait_seconds
            if not video_url:
                return {"success": False, "error": "Volcengine Ark task timed out or returned no video", "task_id": task_id}

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
        except ValueError as exc:
            return {"success": False, "error": f"Volcengine Ark video validation error: {exc}"}
        except (requests.RequestException, OSError) as exc:
            # RequestException messages may contain expiring signed result URLs.
            return {"success": False, "error": f"Volcengine Ark video error: {exc.__class__.__name__}"}


# Backward-compatible public tool name used by existing official-route capsules.
Seedance20VideoGeneratorTool = VolcengineSeedanceVideoGeneratorTool
