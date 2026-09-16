"""Official MiniMax H3 (Hailuo-03) V2 video-generation adapter."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time
from pathlib import Path
from typing import Any, Optional, Sequence, Type

import requests
from pydantic import BaseModel, Field

from custom_tools.audio_generation.base_tool_compat import BaseTool
from .output_dir_utils import default_video_output_dir, resolve_video_output_dir


DEFAULT_MINIMAX_VIDEO_BASE_URL = "https://api.minimaxi.com"
DEFAULT_MINIMAX_H3_MODEL = "MiniMax-H3"
DEFAULT_OUTPUT_DIR = default_video_output_dir("minimax_h3")
MINIMAX_H3_RATIOS = {"adaptive", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}
MINIMAX_H3_RESOLUTION = "2K"
_MEDIA_LIMITS = {"image": 30 * 1024 * 1024, "video": 50 * 1024 * 1024, "audio": 15 * 1024 * 1024}
_MEDIA_SUFFIXES = {
    "image": {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"},
    "video": {".mp4", ".mov"},
    "audio": {".wav", ".mp3"},
}
_TERMINAL_FAILURE_STATES = {"failed", "cancelled", "canceled", "expired"}


class MiniMaxH3VideoSchema(BaseModel):
    prompt: str = Field(..., description="Required non-empty video prompt, maximum 7000 characters")
    generation_type: str = Field(
        "text_to_video",
        description="text_to_video, image_to_video, first_last_frame, or multimodal",
    )
    output_dir: str = Field(DEFAULT_OUTPUT_DIR, description="Local output directory")
    output_path: Optional[str] = Field(None, description="Exact local output path")
    image_path: Optional[str] = Field(None, description="First-frame image for image_to_video")
    image_paths: Optional[list[str]] = Field(None, description="Reference images for multimodal generation; maximum 9")
    first_frame_path: Optional[str] = Field(None, description="First-frame image")
    last_frame_path: Optional[str] = Field(None, description="Last-frame image")
    start_image_path: Optional[str] = Field(None, description="Compatibility alias for first_frame_path")
    end_image_path: Optional[str] = Field(None, description="Compatibility alias for last_frame_path")
    images: Optional[list[str]] = Field(None, description="Compatibility image list")
    video_paths: Optional[list[str]] = Field(None, description="Reference videos; maximum 3")
    audio_paths: Optional[list[str]] = Field(None, description="Reference audio clips; maximum 3")
    aspect_ratio: str = Field("9:16", description="Concrete ratio for text video; adaptive is supported elsewhere")
    ratio: Optional[str] = Field(None, description="Official ratio alias; overrides aspect_ratio")
    resolution: str = Field("2K", description="MiniMax H3 V2 currently supports only 2K")
    duration: int = Field(5, description="Whole seconds from 4 to 15")
    callback_url: Optional[str] = Field(None, description="Optional task-status callback URL")
    aigc_watermark: bool = Field(False, description="Add the provider AIGC watermark")
    poll_interval: int = Field(8, description="Task polling interval in seconds")
    max_wait: int = Field(1200, description="Maximum task wait in seconds")


def _unique(values: Optional[Sequence[str]]) -> list[str]:
    result: list[str] = []
    for value in values or []:
        if value and value not in result:
            result.append(value)
    return result


def _media_url(value: str, kind: str) -> str:
    if value.startswith(("https://", "http://", "mm_file://", "data:")):
        return value

    source = Path(value).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"Reference media does not exist: {source}")
    suffix = source.suffix.lower()
    if suffix not in _MEDIA_SUFFIXES[kind]:
        supported = ", ".join(sorted(_MEDIA_SUFFIXES[kind]))
        raise ValueError(f"Unsupported MiniMax H3 {kind} format {suffix or '<none>'}; supported: {supported}")
    size = source.stat().st_size
    if size > _MEDIA_LIMITS[kind]:
        raise ValueError(f"MiniMax H3 {kind} input exceeds the provider file-size limit")
    if kind == "video" and suffix != ".mp4":
        raise ValueError("Local MOV input must use a public URL or mm_file:// reference; video data URIs support MP4 only")

    mime = mimetypes.guess_type(source.name)[0]
    if not mime:
        mime = {
            ".heic": "image/heic",
            ".heif": "image/heif",
            ".wav": "audio/wav",
            ".mp3": "audio/mp3",
            ".mp4": "video/mp4",
        }.get(suffix, "application/octet-stream")
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _duration_seconds(value: int | float | str) -> int:
    text = str(value).strip().lower()
    if text.endswith("s"):
        text = text[:-1]
    numeric = float(text)
    if not numeric.is_integer():
        raise ValueError("MiniMax H3 duration must use whole seconds")
    result = int(numeric)
    if not 4 <= result <= 15:
        raise ValueError("MiniMax H3 duration must be an integer from 4 to 15")
    return result


def build_minimax_h3_content(
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
    """Build the documented H3 content array and enforce mode exclusivity."""

    prompt = str(prompt or "").strip()
    if not prompt:
        raise ValueError("MiniMax H3 prompt must not be empty")
    if len(prompt) > 7000:
        raise ValueError("MiniMax H3 prompt must not exceed 7000 characters")

    supported_types = {"text_to_video", "image_to_video", "first_last_frame", "multimodal"}
    if generation_type not in supported_types:
        raise ValueError(f"Unsupported generation_type: {generation_type}")

    reference_images = _unique(image_paths)
    reference_videos = _unique(video_paths)
    reference_audios = _unique(audio_paths)
    first_frame = first_frame_path or image_path

    if len(reference_images) > 9:
        raise ValueError("MiniMax H3 supports at most 9 reference images")
    if len(reference_videos) > 3:
        raise ValueError("MiniMax H3 supports at most 3 reference videos")
    if len(reference_audios) > 3:
        raise ValueError("MiniMax H3 supports at most 3 reference audio clips")

    frame_inputs = bool(first_frame or last_frame_path)
    reference_inputs = bool(reference_images or reference_videos or reference_audios)
    if frame_inputs and reference_inputs:
        raise ValueError("MiniMax H3 frame inputs and multimodal reference inputs cannot be mixed")
    if generation_type == "text_to_video" and (frame_inputs or reference_inputs):
        raise ValueError("text_to_video does not accept media inputs")
    if generation_type == "image_to_video" and not first_frame:
        raise ValueError("image_to_video requires image_path or first_frame_path")
    if generation_type == "image_to_video" and last_frame_path:
        raise ValueError("Use first_last_frame when a last frame is supplied")
    if generation_type == "first_last_frame" and not (first_frame and last_frame_path):
        raise ValueError("first_last_frame requires both first and last frame images")
    if generation_type == "multimodal" and not (reference_images or reference_videos):
        raise ValueError("multimodal requires at least one reference image or video")
    if generation_type != "multimodal" and reference_inputs:
        raise ValueError("Reference media requires generation_type=multimodal")

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    if first_frame:
        content.append(
            {"type": "image_url", "image_url": {"url": _media_url(first_frame, "image")}, "role": "first_frame"}
        )
    if last_frame_path:
        content.append(
            {"type": "image_url", "image_url": {"url": _media_url(last_frame_path, "image")}, "role": "last_frame"}
        )
    content.extend(
        {"type": "image_url", "image_url": {"url": _media_url(value, "image")}, "role": "reference_image"}
        for value in reference_images
    )
    content.extend(
        {"type": "video_url", "video_url": {"url": _media_url(value, "video")}, "role": "reference_video"}
        for value in reference_videos
    )
    content.extend(
        {"type": "audio_url", "audio_url": {"url": _media_url(value, "audio")}, "role": "reference_audio"}
        for value in reference_audios
    )
    return content


def build_minimax_h3_payload(
    *,
    prompt: str,
    model: str = DEFAULT_MINIMAX_H3_MODEL,
    generation_type: str = "text_to_video",
    image_path: Optional[str] = None,
    image_paths: Optional[Sequence[str]] = None,
    first_frame_path: Optional[str] = None,
    last_frame_path: Optional[str] = None,
    video_paths: Optional[Sequence[str]] = None,
    audio_paths: Optional[Sequence[str]] = None,
    ratio: str = "9:16",
    resolution: str = MINIMAX_H3_RESOLUTION,
    duration: int | str = 5,
    callback_url: Optional[str] = None,
    aigc_watermark: bool = False,
) -> dict[str, Any]:
    if model != DEFAULT_MINIMAX_H3_MODEL:
        raise ValueError(f"MiniMax H3 V2 requires model={DEFAULT_MINIMAX_H3_MODEL}")
    if str(resolution).strip().upper() != MINIMAX_H3_RESOLUTION.upper():
        raise ValueError("MiniMax H3 V2 currently supports only resolution=2K")

    normalized_ratio = str(ratio or "").strip().lower()
    if normalized_ratio not in MINIMAX_H3_RATIOS:
        raise ValueError(f"Unsupported MiniMax H3 ratio: {ratio}")
    if generation_type == "text_to_video" and normalized_ratio == "adaptive":
        raise ValueError("MiniMax H3 text_to_video requires a concrete ratio, not adaptive")
    if generation_type in {"image_to_video", "first_last_frame"}:
        normalized_ratio = "adaptive"
    if callback_url and not callback_url.startswith(("https://", "http://")):
        raise ValueError("callback_url must be an HTTP(S) URL")

    payload: dict[str, Any] = {
        "model": model,
        "content": build_minimax_h3_content(
            prompt=prompt,
            generation_type=generation_type,
            image_path=image_path,
            image_paths=image_paths,
            first_frame_path=first_frame_path,
            last_frame_path=last_frame_path,
            video_paths=video_paths,
            audio_paths=audio_paths,
        ),
        "resolution": MINIMAX_H3_RESOLUTION,
        "duration": _duration_seconds(duration),
        "ratio": normalized_ratio,
        "aigc_watermark": bool(aigc_watermark),
    }
    if callback_url:
        payload["callback_url"] = callback_url
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > 64 * 1024 * 1024:
        raise ValueError("MiniMax H3 request body exceeds the 64 MB provider limit; use public URLs or mm_file://")
    return payload


def _task_from_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    task = payload.get("task")
    return task if isinstance(task, dict) else payload


def _task_video_url(task: dict[str, Any]) -> str:
    content = task.get("content")
    value = content.get("url") if isinstance(content, dict) else ""
    return value if isinstance(value, str) and value.startswith(("https://", "http://")) else ""


def _error_detail(response: requests.Response) -> tuple[str, str]:
    try:
        payload = response.json()
    except ValueError:
        return "", ""
    if not isinstance(payload, dict):
        return "", ""
    error = payload.get("error")
    if not isinstance(error, dict):
        return "", ""
    message = str(error.get("message") or "")
    # Provider messages should not leak signed/public input URLs into local logs.
    message = re.sub(r"https?://\S+", "[redacted-url]", message)[:300]
    code_match = re.search(r"\((\d+)\)\s*$", message)
    code = code_match.group(1) if code_match else str(error.get("code") or "")
    return code, message


def _task_error(task: dict[str, Any]) -> tuple[str, str]:
    error = task.get("error")
    if not isinstance(error, dict):
        return "", ""
    return str(error.get("code") or ""), str(error.get("message") or "")[:300]


def _download(url: str, destination: Path, *, timeout: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, stream=True, timeout=timeout)
    response.raise_for_status()
    with destination.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)


class MiniMaxH3VideoGeneratorTool(BaseTool):
    name: str = "MiniMax H3 2K video generator"
    description: str = "Generate official MiniMax H3 V2 2K videos and download expiring results locally."
    args_schema: Type[BaseModel] = MiniMaxH3VideoSchema

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
        resolution: str = "2K",
        duration: int | str = 5,
        callback_url: Optional[str] = None,
        aigc_watermark: bool = False,
        poll_interval: int = 8,
        max_wait: int = 1200,
        **extra: Any,
    ) -> dict[str, Any]:
        api_key = os.getenv("MINIMAX_API_KEY")
        if not api_key:
            return {"success": False, "error": "Missing required env var: MINIMAX_API_KEY"}
        if extra:
            unsupported = sorted(name for name, value in extra.items() if value is not None)
            if unsupported:
                return {"success": False, "error": "MiniMax H3 does not support: " + ", ".join(unsupported)}

        model = os.getenv("MINIMAX_VIDEO_MODEL") or DEFAULT_MINIMAX_H3_MODEL
        base_url = (os.getenv("MINIMAX_VIDEO_BASE_URL") or DEFAULT_MINIMAX_VIDEO_BASE_URL).rstrip("/")
        try:
            legacy_images = _unique(images)
            resolved_image_paths = _unique(image_paths)
            if generation_type == "first_last_frame":
                first_frame_path = first_frame_path or start_image_path or (legacy_images[0] if legacy_images else None)
                last_frame_path = last_frame_path or end_image_path or (legacy_images[1] if len(legacy_images) > 1 else None)
                resolved_image_paths = _unique(resolved_image_paths + legacy_images[2:])
            elif generation_type == "image_to_video":
                image_path = image_path or first_frame_path or start_image_path or (legacy_images[0] if legacy_images else None)
                resolved_image_paths = _unique(resolved_image_paths + legacy_images[1:])
            else:
                resolved_image_paths = _unique(resolved_image_paths + legacy_images)

            payload = build_minimax_h3_payload(
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
                callback_url=callback_url,
                aigc_watermark=aigc_watermark,
            )
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            timeout = max(1, int(os.getenv("MINIMAX_VIDEO_TIMEOUT_SECONDS", "300")))
            created = requests.post(
                f"{base_url}/v2/video_generation",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            if created.status_code >= 400:
                error_code, message = _error_detail(created)
                suffix = f" ({error_code})" if error_code else ""
                return {
                    "success": False,
                    "error": f"MiniMax H3 video request failed: HTTP {created.status_code}{suffix}",
                    "provider_error_code": error_code or None,
                    "provider_error_message": message or None,
                }
            created_payload = created.json()
            task_id = str(created_payload.get("task_id") or "") if isinstance(created_payload, dict) else ""
            if not task_id:
                return {"success": False, "error": "MiniMax H3 response did not contain task_id"}

            started = time.monotonic()
            task: dict[str, Any] = {}
            status = "queued"
            video_url = ""
            while time.monotonic() - started <= max(1, int(max_wait)):
                queried = requests.get(
                    f"{base_url}/v2/query/video_generation/{task_id}",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=timeout,
                )
                if queried.status_code >= 400:
                    error_code, message = _error_detail(queried)
                    suffix = f" ({error_code})" if error_code else ""
                    return {
                        "success": False,
                        "error": f"MiniMax H3 task query failed: HTTP {queried.status_code}{suffix}",
                        "provider_error_code": error_code or None,
                        "provider_error_message": message or None,
                        "task_id": task_id,
                    }
                task = _task_from_response(queried.json())
                status = str(task.get("status") or "").lower()
                video_url = _task_video_url(task)
                if status in _TERMINAL_FAILURE_STATES:
                    error_code, message = _task_error(task)
                    suffix = f" ({error_code})" if error_code else ""
                    return {
                        "success": False,
                        "error": f"MiniMax H3 task ended with status {status}{suffix}",
                        "provider_error_code": error_code or None,
                        "provider_error_message": message or None,
                        "task_id": task_id,
                    }
                if status == "succeeded":
                    break
                time.sleep(max(1, int(poll_interval)))
            if status != "succeeded" or not video_url:
                return {
                    "success": False,
                    "error": f"MiniMax H3 task timed out or returned no video (status={status or 'unknown'})",
                    "task_id": task_id,
                }

            resolved_dir = resolve_video_output_dir(output_dir, output_path, DEFAULT_OUTPUT_DIR, ())
            destination = (
                Path(output_path).expanduser()
                if output_path
                else Path(resolved_dir) / f"minimax_h3_{task_id}.mp4"
            )
            _download(video_url, destination, timeout=timeout)
            usage = task.get("usage") if isinstance(task.get("usage"), dict) else {}
            return {
                "success": True,
                "provider": "minimax_official",
                "model": task.get("model") or model,
                "task_id": task_id,
                "output_path": str(destination),
                "generation_type": generation_type,
                "resolution": task.get("resolution") or payload["resolution"],
                "ratio": task.get("ratio") or payload["ratio"],
                "duration": task.get("duration") if task.get("duration") is not None else payload["duration"],
                "usage": usage,
            }
        except ValueError as exc:
            return {"success": False, "error": f"MiniMax H3 video validation error: {exc}"}
        except (requests.RequestException, OSError) as exc:
            return {"success": False, "error": f"MiniMax H3 video error: {exc.__class__.__name__}"}


__all__ = [
    "MiniMaxH3VideoGeneratorTool",
    "MiniMaxH3VideoSchema",
    "build_minimax_h3_content",
    "build_minimax_h3_payload",
]
