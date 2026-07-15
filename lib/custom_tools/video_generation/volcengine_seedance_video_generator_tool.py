"""Official Volcengine Ark Seedance task adapter."""

from __future__ import annotations

import base64
import mimetypes
import os
import time
from pathlib import Path
from typing import Any, Iterable, Optional, Type

import requests
from pydantic import BaseModel, Field

from custom_tools.audio_generation.base_tool_compat import BaseTool
from .output_dir_utils import default_video_output_dir, resolve_video_output_dir


DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_OUTPUT_DIR = default_video_output_dir("volcengine_seedance")


class VolcengineSeedanceSchema(BaseModel):
    prompt: str = Field(..., description="Video prompt")
    generation_type: str = Field("text_to_video", description="text_to_video or image_to_video")
    output_dir: str = Field(DEFAULT_OUTPUT_DIR, description="Local output directory")
    output_path: Optional[str] = Field(None, description="Exact local output path")
    image_path: Optional[str] = Field(None, description="Input image for image-to-video")
    image_paths: Optional[list[str]] = Field(None, description="Optional reference images")
    aspect_ratio: str = Field("9:16", description="9:16, 16:9, or 1:1")
    duration: int | str = Field(5, description="Duration in seconds")
    generate_audio: bool = Field(False, description="Request model-generated audio")
    watermark: bool = Field(False, description="Add provider watermark")


def _seconds(value: int | float | str) -> int:
    text = str(value).strip().lower()
    if text.endswith("s"):
        text = text[:-1]
    result = int(round(float(text)))
    if result <= 0:
        raise ValueError("duration must be positive")
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


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _first(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for record in _walk(payload):
        for key in keys:
            value = record.get(key)
            if isinstance(value, (str, int)) and str(value):
                return str(value)
            if isinstance(value, dict) and isinstance(value.get("url"), str):
                return value["url"]
    return ""


class VolcengineSeedanceVideoGeneratorTool(BaseTool):
    name: str = "Volcengine Ark Seedance video generator"
    description: str = "Generate a video with the official Volcengine Ark task API and download it locally."
    args_schema: Type[BaseModel] = VolcengineSeedanceSchema

    def _run(
        self,
        prompt: str,
        generation_type: str = "text_to_video",
        output_dir: str = DEFAULT_OUTPUT_DIR,
        output_path: Optional[str] = None,
        image_path: Optional[str] = None,
        image_paths: Optional[list[str]] = None,
        aspect_ratio: str = "9:16",
        duration: int | str = 5,
        generate_audio: bool = False,
        watermark: bool = False,
        poll_interval: int = 8,
        max_wait: int = 900,
        **_: Any,
    ) -> dict[str, Any]:
        api_key = os.getenv("ARK_API_KEY")
        model = os.getenv("ARK_SEEDANCE_MODEL") or os.getenv("ARK_SEEDANCE20_MODEL")
        if not api_key or not model:
            missing = [name for name, value in (("ARK_API_KEY", api_key), ("ARK_SEEDANCE_MODEL", model)) if not value]
            return {"success": False, "error": "Missing required env vars: " + ", ".join(missing)}
        if generation_type not in {"text_to_video", "image_to_video"}:
            return {"success": False, "error": f"Unsupported generation_type: {generation_type}"}
        refs = list(image_paths or [])
        if image_path and image_path not in refs:
            refs.insert(0, image_path)
        if generation_type == "image_to_video" and not refs:
            return {"success": False, "error": "image_to_video requires image_path"}

        base_url = (os.getenv("ARK_BASE_URL") or DEFAULT_ARK_BASE_URL).rstrip("/")
        tasks_url = f"{base_url}/contents/generations/tasks"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content.extend(
            {"type": "image_url", "image_url": {"url": _media_url(value)}, "role": "reference_image"}
            for value in refs
        )
        payload = {
            "model": model,
            "content": content,
            "ratio": aspect_ratio,
            "duration": _seconds(duration),
            "generate_audio": bool(generate_audio),
            "watermark": bool(watermark),
        }

        try:
            created = requests.post(tasks_url, headers=headers, json=payload, timeout=180)
            if created.status_code >= 400:
                return {"success": False, "error": f"Volcengine Ark video request failed: HTTP {created.status_code}"}
            result = created.json()
            task_id = _first(result, ("id", "task_id", "taskId"))
            video_url = _first(result, ("video_url", "download_url", "output_url"))
            elapsed = 0
            while not video_url and task_id and elapsed <= max_wait:
                time.sleep(max(1, poll_interval))
                elapsed += max(1, poll_interval)
                status_response = requests.get(f"{tasks_url}/{task_id}", headers=headers, timeout=60)
                if status_response.status_code >= 400:
                    return {"success": False, "error": f"Volcengine Ark task query failed: HTTP {status_response.status_code}", "task_id": task_id}
                result = status_response.json()
                status = _first(result, ("status", "state", "task_status")).lower()
                if status in {"failed", "error", "cancelled", "canceled", "expired", "rejected"}:
                    return {"success": False, "error": f"Volcengine Ark task ended with status {status}", "task_id": task_id}
                video_url = _first(result, ("video_url", "download_url", "output_url"))
            if not video_url:
                return {"success": False, "error": "Volcengine Ark task timed out or returned no video", "task_id": task_id}

            resolved_dir = resolve_video_output_dir(output_dir, output_path, DEFAULT_OUTPUT_DIR, ())
            destination = Path(output_path) if output_path else Path(resolved_dir) / f"seedance_{task_id or int(time.time())}.mp4"
            destination.parent.mkdir(parents=True, exist_ok=True)
            download = requests.get(video_url, stream=True, timeout=300)
            download.raise_for_status()
            with destination.open("wb") as handle:
                for chunk in download.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
            return {
                "success": True,
                "provider": "volcengine_ark",
                "task_id": task_id,
                "output_path": str(destination),
                "generation_type": generation_type,
            }
        except (requests.RequestException, OSError, ValueError) as exc:
            return {"success": False, "error": f"Volcengine Ark video error: {exc.__class__.__name__}"}


# Backward-compatible public tool name used by existing official-route capsules.
Seedance20VideoGeneratorTool = VolcengineSeedanceVideoGeneratorTool
