"""Official Agnes text-to-image adapter."""

from __future__ import annotations

import base64
import binascii
import io
import os
from pathlib import Path
from typing import Any, Optional, Type

import requests
from PIL import Image
from pydantic import BaseModel, Field

from custom_tools.audio_generation.base_tool_compat import BaseTool


DEFAULT_AGNES_BASE_URL = "https://apihub.agnes-ai.com"
DEFAULT_AGNES_IMAGE_MODEL = "agnes-image-2.1-flash"
AGNES_IMAGE_SIZES = {"1K", "2K", "3K", "4K"}
AGNES_IMAGE_RATIOS = {"9:16", "16:9", "1:1"}


class AgnesImageSchema(BaseModel):
    prompt: str = Field(..., description="Image prompt")
    output_path: str = Field(..., description="Local output image path")
    aspect_ratio: str = Field("9:16", description="9:16, 16:9, or 1:1")
    ratio: Optional[str] = Field(None, description="Agnes ratio alias; overrides aspect_ratio")
    size: str = Field("1K", description="1K, 2K, 3K, or 4K")
    response_format: str = Field("url", description="url or b64_json")
    quality: str = Field("high", description="Compatibility-only quality hint")
    reference_image_path: Optional[str] = Field(
        None,
        description="Unsupported compatibility field; Agnes public adapter is text-to-image only",
    )
    reference_image_paths: Optional[list[str]] = Field(
        None,
        description="Unsupported compatibility field; Agnes public adapter is text-to-image only",
    )


def build_agnes_image_payload(
    *,
    prompt: str,
    model: str = DEFAULT_AGNES_IMAGE_MODEL,
    ratio: str = "9:16",
    size: str = "1K",
    response_format: str = "url",
) -> dict[str, Any]:
    """Build the currently documented Agnes Image 2.1 Flash request."""

    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    normalized_ratio = ratio.strip()
    if normalized_ratio not in AGNES_IMAGE_RATIOS:
        raise ValueError(f"Unsupported Agnes image ratio: {ratio}")
    normalized_size = size.strip().upper()
    if normalized_size not in AGNES_IMAGE_SIZES:
        raise ValueError(f"Unsupported Agnes image size: {size}")
    normalized_response = response_format.strip().lower()
    if normalized_response not in {"url", "b64_json"}:
        raise ValueError("response_format must be url or b64_json")
    return {
        "model": model,
        "prompt": prompt,
        "size": normalized_size,
        "ratio": normalized_ratio,
        "extra_body": {"response_format": normalized_response},
    }


def _extract_image(payload: dict[str, Any]) -> tuple[bytes | None, str | None]:
    records = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        return None, None
    for record in records:
        if not isinstance(record, dict):
            continue
        encoded = record.get("b64_json") or record.get("base64")
        if isinstance(encoded, str) and encoded:
            try:
                return base64.b64decode(encoded, validate=True), None
            except (binascii.Error, ValueError):
                continue
        url = record.get("url") or record.get("image_url")
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            return None, url
    return None, None


def _response_error_code(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    error = payload.get("error") if isinstance(payload, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return str(code) if code not in {None, ""} else ""


def _image_dimensions(content: bytes) -> tuple[int | None, int | None]:
    try:
        with Image.open(io.BytesIO(content)) as image:
            return image.size
    except (OSError, ValueError):
        return None, None


class AgnesImageGeneratorTool(BaseTool):
    name: str = "Agnes Image 2.1 Flash generator"
    description: str = "Generate one image with the official Agnes API and save it locally."
    args_schema: Type[BaseModel] = AgnesImageSchema

    def _run(
        self,
        prompt: str,
        output_path: str,
        aspect_ratio: str = "9:16",
        ratio: Optional[str] = None,
        size: str = "1K",
        response_format: str = "url",
        quality: str = "high",
        reference_image_path: Optional[str] = None,
        reference_image_paths: Optional[list[str]] = None,
        **_: Any,
    ) -> dict[str, Any]:
        del quality
        api_key = os.getenv("AGNES_API_KEY")
        if not api_key:
            return {"success": False, "error": "Missing required env var: AGNES_API_KEY"}
        if reference_image_path or reference_image_paths:
            return {
                "success": False,
                "error": "Agnes public image adapter supports text_to_image only",
            }

        model = os.getenv("AGNES_IMAGE_MODEL") or DEFAULT_AGNES_IMAGE_MODEL
        base_url = (os.getenv("AGNES_BASE_URL") or DEFAULT_AGNES_BASE_URL).rstrip("/")
        timeout = max(1, int(os.getenv("AGNES_TIMEOUT_SECONDS", "300")))
        resolved_ratio = ratio or aspect_ratio
        try:
            payload = build_agnes_image_payload(
                prompt=prompt,
                model=model,
                ratio=resolved_ratio,
                size=size,
                response_format=response_format,
            )
            response = requests.post(
                f"{base_url}/v1/images/generations",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
            )
            if response.status_code >= 400:
                error_code = _response_error_code(response)
                suffix = f" ({error_code})" if error_code else ""
                return {
                    "success": False,
                    "error": f"Agnes image request failed: HTTP {response.status_code}{suffix}",
                    "provider_error_code": error_code or None,
                }

            result = response.json()
            image_bytes, image_url = _extract_image(result)
            if image_bytes is None and image_url:
                download = requests.get(image_url, timeout=timeout)
                download.raise_for_status()
                image_bytes = download.content
            if not image_bytes:
                return {"success": False, "error": "Agnes response did not contain an image"}

            destination = Path(output_path).expanduser()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(image_bytes)
            width, height = _image_dimensions(image_bytes)
            return {
                "success": True,
                "provider": "agnes_official",
                "model": result.get("model") or model,
                "output_path": str(destination),
                "requested_ratio": resolved_ratio,
                "requested_size": payload["size"],
                "actual_width": width,
                "actual_height": height,
            }
        except ValueError as exc:
            return {"success": False, "error": f"Agnes image validation error: {exc}"}
        except (requests.RequestException, OSError) as exc:
            return {"success": False, "error": f"Agnes image error: {exc.__class__.__name__}"}


__all__ = [
    "AgnesImageGeneratorTool",
    "AgnesImageSchema",
    "build_agnes_image_payload",
]
