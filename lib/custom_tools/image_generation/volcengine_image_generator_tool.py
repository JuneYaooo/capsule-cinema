"""Official Volcengine Ark Seedream 5.0 Pro image-generation adapter.

Only official Ark credentials are supported here. Alternative OpenAI-compatible
or relay endpoints belong in the Git-ignored ``local-channels/`` overlay.
"""

from __future__ import annotations

import base64
import binascii
import mimetypes
import os
import re
from pathlib import Path
from typing import Any, Optional, Sequence, Type

import requests
from pydantic import BaseModel, Field

from custom_tools.audio_generation.base_tool_compat import BaseTool


DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_SEEDREAM_MODEL = "doubao-seedream-5-0-pro-260628"
SEEDREAM_PRO_MAX_REFERENCE_IMAGES = 10
_ASPECT_RATIO_SIZES = {
    "9:16": "1440x2560",
    "16:9": "2560x1440",
    "1:1": "2048x2048",
    "4:3": "2304x1728",
    "3:4": "1728x2304",
    "21:9": "2688x1152",
}


class VolcengineImageSchema(BaseModel):
    prompt: str = Field(..., description="Image prompt")
    output_path: str = Field(..., description="Local output image path")
    aspect_ratio: str = Field("9:16", description="Output aspect ratio used when size is omitted")
    size: Optional[str] = Field(None, description="Official size such as 2K, or WIDTHxHEIGHT")
    quality: str = Field("high", description="Compatibility-only quality hint")
    output_format: str = Field("png", description="png or jpeg")
    response_format: str = Field("b64_json", description="b64_json or url")
    watermark: bool = Field(False, description="Add the provider AI watermark")
    optimize_prompt_options: Optional[dict[str, Any]] = Field(None, description="Official prompt optimization options")
    reference_image_path: Optional[str] = Field(None, description="Optional local, data, or HTTPS reference image")
    reference_image_paths: Optional[list[str]] = Field(None, description="Up to 10 reference images")


def _data_url(path: str) -> str:
    if path.startswith(("https://", "http://", "data:")):
        return path
    source = Path(path).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"Reference image does not exist: {source}")
    mime = mimetypes.guess_type(source.name)[0] or "image/jpeg"
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _normalize_references(
    reference_image_path: Optional[str],
    reference_image_paths: Optional[Sequence[str]],
) -> list[str]:
    references: list[str] = []
    for value in ([reference_image_path] if reference_image_path else []) + list(reference_image_paths or []):
        if value and value not in references:
            references.append(value)
    if len(references) > SEEDREAM_PRO_MAX_REFERENCE_IMAGES:
        raise ValueError(
            f"Seedream 5.0 Pro supports at most {SEEDREAM_PRO_MAX_REFERENCE_IMAGES} reference images"
        )
    return references


def _validate_size(size: str) -> str:
    normalized = size.strip()
    if normalized.upper() in {"1K", "2K", "4K"}:
        return normalized.upper()
    if re.fullmatch(r"[1-9]\d{2,4}x[1-9]\d{2,4}", normalized, flags=re.IGNORECASE):
        return normalized.lower()
    raise ValueError("size must be 1K, 2K, 4K, or WIDTHxHEIGHT")


def _is_seedream_4_0(model: str) -> bool:
    return "seedream-4-0" in model.lower()


def build_image_payload(
    *,
    prompt: str,
    model: str = DEFAULT_SEEDREAM_MODEL,
    aspect_ratio: str = "9:16",
    size: Optional[str] = None,
    output_format: str = "png",
    response_format: str = "b64_json",
    watermark: bool = False,
    optimize_prompt_options: Optional[dict[str, Any]] = None,
    reference_image_path: Optional[str] = None,
    reference_image_paths: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    """Build a strongly validated, non-streaming Seedream 5.0 Pro request."""

    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    normalized_output = output_format.strip().lower()
    if normalized_output not in {"png", "jpeg"}:
        raise ValueError("output_format must be png or jpeg")
    normalized_response = response_format.strip().lower()
    if normalized_response not in {"url", "b64_json"}:
        raise ValueError("response_format must be url or b64_json")
    if size is None:
        if aspect_ratio not in _ASPECT_RATIO_SIZES:
            raise ValueError(f"Unsupported aspect_ratio: {aspect_ratio}")
        resolved_size = _ASPECT_RATIO_SIZES[aspect_ratio]
    else:
        resolved_size = _validate_size(size)

    references = _normalize_references(reference_image_path, reference_image_paths)
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": resolved_size,
        "response_format": normalized_response,
        "watermark": bool(watermark),
    }
    if _is_seedream_4_0(model):
        if normalized_output != "jpeg":
            raise ValueError("Seedream 4.0 only supports its default JPEG output; use output_format=jpeg")
    else:
        payload["output_format"] = normalized_output
    if references:
        payload["image"] = [_data_url(value) for value in references]
    if optimize_prompt_options is not None:
        if not isinstance(optimize_prompt_options, dict):
            raise ValueError("optimize_prompt_options must be an object")
        payload["optimize_prompt_options"] = optimize_prompt_options
    # Seedream 5.0 Pro generates one image and does not support group-image or
    # streaming parameters, so neither is sent to the official API.
    return payload


def _extract_image(payload: dict[str, Any]) -> tuple[bytes | None, str | None, str | None]:
    records = payload.get("data") or payload.get("images") or []
    if isinstance(records, dict):
        records = [records]
    for record in records:
        if not isinstance(record, dict):
            continue
        image_size = record.get("size") if isinstance(record.get("size"), str) else None
        encoded = record.get("b64_json") or record.get("base64")
        if encoded:
            try:
                return base64.b64decode(encoded, validate=True), None, image_size
            except (binascii.Error, ValueError):
                continue
        url = record.get("url") or record.get("image_url")
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            return None, url, image_size
    return None, None, None


def _response_error_code(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    error = payload.get("error") if isinstance(payload, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, str) else ""


class VolcengineImageGeneratorTool(BaseTool):
    name: str = "Volcengine Ark Seedream image generator"
    description: str = "Generate one image with official Seedream 5.0 Pro and save it locally."
    args_schema: Type[BaseModel] = VolcengineImageSchema

    def _run(
        self,
        prompt: str,
        output_path: str,
        aspect_ratio: str = "9:16",
        size: Optional[str] = None,
        quality: str = "high",
        output_format: str = "png",
        response_format: str = "b64_json",
        watermark: bool = False,
        optimize_prompt_options: Optional[dict[str, Any]] = None,
        reference_image_path: Optional[str] = None,
        reference_image_paths: Optional[list[str]] = None,
        **_: Any,
    ) -> dict[str, Any]:
        api_key = os.getenv("ARK_API_KEY")
        if not api_key:
            return {"success": False, "error": "Missing required env var: ARK_API_KEY"}

        model = os.getenv("ARK_SEEDREAM_MODEL") or DEFAULT_SEEDREAM_MODEL
        base_url = (os.getenv("ARK_BASE_URL") or DEFAULT_ARK_BASE_URL).rstrip("/")
        try:
            payload = build_image_payload(
                prompt=prompt,
                model=model,
                aspect_ratio=aspect_ratio,
                size=size,
                output_format=output_format,
                response_format=response_format,
                watermark=watermark,
                optimize_prompt_options=optimize_prompt_options,
                reference_image_path=reference_image_path,
                reference_image_paths=reference_image_paths,
            )
            # ``quality`` remains a caller-facing compatibility hint. Official
            # Seedream quality is controlled by model and size, not this field.
            response = requests.post(
                f"{base_url}/images/generations",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=300,
            )
            if response.status_code >= 400:
                error_code = _response_error_code(response)
                suffix = f" ({error_code})" if error_code else ""
                return {
                    "success": False,
                    "error": f"Volcengine Ark image request failed: HTTP {response.status_code}{suffix}",
                    "provider_error_code": error_code or None,
                }
            result = response.json()
            image_bytes, image_url, actual_size = _extract_image(result)
            if image_bytes is None and image_url:
                download = requests.get(image_url, timeout=300)
                download.raise_for_status()
                image_bytes = download.content
            if not image_bytes:
                return {"success": False, "error": "Volcengine Ark response did not contain an image"}

            destination = Path(output_path).expanduser()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(image_bytes)
            usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
            return {
                "success": True,
                "provider": "volcengine_ark",
                "model": result.get("model") or model,
                "output_path": str(destination),
                "aspect_ratio": aspect_ratio,
                "size": actual_size or payload["size"],
                "output_format": payload.get("output_format", "jpeg"),
                "usage": usage,
            }
        except ValueError as exc:
            return {"success": False, "error": f"Volcengine Ark image validation error: {exc}"}
        except (requests.RequestException, OSError) as exc:
            return {"success": False, "error": f"Volcengine Ark image error: {exc.__class__.__name__}"}
