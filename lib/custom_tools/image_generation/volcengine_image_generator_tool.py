"""Official Volcengine Ark image-generation adapter.

Only official Ark credentials are supported here. Alternative OpenAI-compatible
or relay endpoints belong in the Git-ignored ``local-channels/`` overlay.
"""

from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any, Optional, Type

import requests
from pydantic import BaseModel, Field

from custom_tools.audio_generation.base_tool_compat import BaseTool


DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


class VolcengineImageSchema(BaseModel):
    prompt: str = Field(..., description="Image prompt")
    output_path: str = Field(..., description="Local output image path")
    aspect_ratio: str = Field("9:16", description="9:16, 16:9, or 1:1")
    quality: str = Field("high", description="Quality hint")
    reference_image_path: Optional[str] = Field(None, description="Optional local or HTTPS reference image")
    reference_image_paths: Optional[list[str]] = Field(None, description="Optional reference images")


def _data_url(path: str) -> str:
    if path.startswith(("https://", "http://", "data:")):
        return path
    source = Path(path).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"Reference image does not exist: {source}")
    mime = mimetypes.guess_type(source.name)[0] or "image/jpeg"
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _extract_image(payload: dict[str, Any]) -> tuple[bytes | None, str | None]:
    records = payload.get("data") or payload.get("images") or []
    if isinstance(records, dict):
        records = [records]
    for record in records:
        if not isinstance(record, dict):
            continue
        encoded = record.get("b64_json") or record.get("base64")
        if encoded:
            return base64.b64decode(encoded), None
        url = record.get("url") or record.get("image_url")
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            return None, url
    return None, None


class VolcengineImageGeneratorTool(BaseTool):
    name: str = "Volcengine Ark image generator"
    description: str = "Generate images through the official Volcengine Ark API and save them locally."
    args_schema: Type[BaseModel] = VolcengineImageSchema

    def _run(
        self,
        prompt: str,
        output_path: str,
        aspect_ratio: str = "9:16",
        quality: str = "high",
        reference_image_path: Optional[str] = None,
        reference_image_paths: Optional[list[str]] = None,
        **_: Any,
    ) -> dict[str, Any]:
        api_key = os.getenv("ARK_API_KEY")
        model = os.getenv("ARK_SEEDREAM_MODEL")
        if not api_key or not model:
            missing = [name for name, value in (("ARK_API_KEY", api_key), ("ARK_SEEDREAM_MODEL", model)) if not value]
            return {"success": False, "error": "Missing required env vars: " + ", ".join(missing)}

        base_url = (os.getenv("ARK_BASE_URL") or DEFAULT_ARK_BASE_URL).rstrip("/")
        size = {
            "9:16": "1440x2560",
            "16:9": "2560x1440",
            "1:1": "2048x2048",
        }.get(aspect_ratio, "2048x2048")
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "response_format": "b64_json",
            "watermark": False,
        }
        refs = list(reference_image_paths or [])
        if reference_image_path and reference_image_path not in refs:
            refs.append(reference_image_path)
        if refs:
            payload["image"] = [_data_url(value) for value in refs]
        # Keep ``quality`` as a caller-facing hint for compatibility. Official
        # Ark image models derive quality from the configured endpoint and size;
        # do not send relay-style, non-contract parameters.

        try:
            response = requests.post(
                f"{base_url}/images/generations",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=180,
            )
            if response.status_code >= 400:
                return {"success": False, "error": f"Volcengine Ark image request failed: HTTP {response.status_code}"}
            image_bytes, image_url = _extract_image(response.json())
            if image_bytes is None and image_url:
                download = requests.get(image_url, timeout=180)
                download.raise_for_status()
                image_bytes = download.content
            if not image_bytes:
                return {"success": False, "error": "Volcengine Ark response did not contain an image"}
            destination = Path(output_path).expanduser()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(image_bytes)
            return {
                "success": True,
                "provider": "volcengine_ark",
                "output_path": str(destination),
                "aspect_ratio": aspect_ratio,
            }
        except requests.RequestException as exc:
            return {"success": False, "error": f"Volcengine Ark network error: {exc.__class__.__name__}"}
