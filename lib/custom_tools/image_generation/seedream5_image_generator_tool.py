#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Seedream 5.0 图像生成 CrewAI 工具（巨灵 API）
使用巨灵 API 的 OpenAI 兼容接口（/v1/chat/completions 流式）生成图片，
支持文生图和图生图。

环境变量：
- JULING_BASE_URL: 巨灵 API 地址
- JULING_API_KEY: 巨灵 API 密钥
"""

import os
import re
import json
import base64
import contextlib
import mimetypes
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Dict, Any, List, Type, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from PIL import Image
from io import BytesIO

import httpx

load_dotenv()


class Seedream5ImageGeneratorSchema(BaseModel):
    """Seedream 5.0 图像生成工具的输入参数"""
    prompt: str = Field(
        ...,
        description="图像生成的文本提示词，描述要生成的图像内容（推荐使用中文）"
    )
    output_path: str = Field(
        ...,
        description="生成图像的保存路径，包含文件名和扩展名"
    )
    aspect_ratio: str = Field(
        default="9:16",
        description="图片宽高比，支持 '16:9' (横屏) 或 '9:16' (竖屏) 或 '1:1' (方形)"
    )
    reference_image_paths: Optional[List[str]] = Field(
        default=None,
        description="参考图片路径列表，用于图生图功能（可选）"
    )
    reference_prompt_prefix: str = Field(
        default="",
        description="图生图时的提示词前缀（可选）"
    )
    mask_path: Optional[str] = Field(
        default=None,
        description="图片编辑 mask 路径（可选，仅 gpt-image-2 edits 使用）"
    )
    quality: str = Field(
        default="hd",
        description="图像质量：'hd'(高清) 或 'standard'(标准)"
    )


class Seedream5ImageGeneratorTool(BaseTool):
    name: str = "Seedream5图像生成工具"
    description: str = (
        "使用 Seedream 5.0 模型生成图片的工具（巨灵 API）。支持文生图和图生图功能。"
        "可以根据文本描述生成高质量图像，也可以基于参考图片进行图像生成。"
        "对中文 prompt 支持良好，推荐优先使用中文提示词。"
    )
    args_schema: Type[BaseModel] = Seedream5ImageGeneratorSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _run(
        self,
        prompt: str,
        output_path: str,
        aspect_ratio: str = "9:16",
        reference_image_paths: Optional[List[str]] = None,
        reference_image_path: Optional[str] = None,
        reference_prompt_prefix: str = "",
        mask_path: Optional[str] = None,
        quality: str = "hd"
    ) -> str:
        """
        执行 Seedream 5.0 图像生成

        Args:
            prompt: 图像生成提示词（推荐中文）
            output_path: 输出文件路径
            aspect_ratio: 图片宽高比
            reference_image_paths: 参考图片路径列表（可选）
            reference_prompt_prefix: 图生图时的提示词前缀（可选）
            mask_path: 图片编辑 mask 路径（Seedream5 当前忽略）
            quality: 图像质量

        Returns:
            生成结果的描述信息
        """
        try:
            if reference_image_paths is None and reference_image_path is not None:
                reference_image_paths = (
                    reference_image_path
                    if isinstance(reference_image_path, list)
                    else [reference_image_path]
                )

            generator = Seedream5ImageGenerator(aspect_ratio=aspect_ratio)

            scene_data = {
                'index': 1,
                'image_prompt': prompt
            }

            output_dir_path = os.path.dirname(output_path)
            if output_dir_path:
                os.makedirs(output_dir_path, exist_ok=True)

            result_path = generator.generate_scene_image(
                scene_data=scene_data,
                output_path=output_path,
                reference_image_paths=reference_image_paths,
                reference_prompt_prefix=reference_prompt_prefix
            )

            return f"Seedream5 图像生成成功！图像已保存到: {result_path}"

        except Exception as e:
            return f"Seedream5 图像生成失败: {str(e)}"


class GptImage2Tool(Seedream5ImageGeneratorTool):
    """GPT Image 2 图像生成工具。

    gpt-image-2 使用 OpenAI Images 兼容接口生成图片。
    """

    name: str = "GPT Image 2图像生成工具"
    description: str = (
        "使用 Krill AI/OpenAI 兼容 Images API 的 gpt-image-2 模型生成图片。"
        "参数与 Seedream5ImageGeneratorTool 一致。"
    )

    IMAGE_MODEL: ClassVar[str] = "gpt-image-2"
    OPENAI_IMAGES_BASE_URL: ClassVar[str] = "https://api.openai.com/v1"
    KRILL_IMAGES_BASE_URL: ClassVar[str] = "https://api.krill-ai.com/v1"

    def _run(
        self,
        prompt: str,
        output_path: str,
        aspect_ratio: str = "9:16",
        reference_image_paths: Optional[List[str]] = None,
        reference_image_path: Optional[str] = None,
        reference_prompt_prefix: str = "",
        mask_path: Optional[str] = None,
        quality: str = "hd",
    ) -> str:
        if reference_image_paths is None and reference_image_path is not None:
            reference_image_paths = (
                reference_image_path
                if isinstance(reference_image_path, list)
                else [reference_image_path]
            )

        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            prompt_for_model = self._prompt_with_aspect_ratio(prompt, aspect_ratio)
            if reference_image_paths:
                if reference_prompt_prefix:
                    prompt_for_model = f"{reference_prompt_prefix}\n{prompt_for_model}"
                image_data = self._generate_with_edits_api(
                    prompt=prompt_for_model,
                    image_paths=reference_image_paths,
                    aspect_ratio=aspect_ratio,
                    quality=quality,
                    mask_path=mask_path,
                )
            else:
                image_data = self._generate_with_images_api(
                    prompt=prompt_for_model,
                    aspect_ratio=aspect_ratio,
                    quality=quality,
                )
            self._save_image_data(image_data, output_path)
            self._validate_saved_image_aspect_ratio(output_path, aspect_ratio)
            return f"GPT Image 2 图像生成成功！图像已保存到: {output_path}"
        except Exception as exc:
            return f"GPT Image 2 图像生成失败: {exc}"

    @staticmethod
    def _size_for_aspect_ratio(aspect_ratio: str) -> str:
        return "auto"

    @staticmethod
    def _krill_size_for_aspect_ratio(aspect_ratio: str) -> str:
        size_map = {
            "9:16": "1024x1792",
            "16:9": "1792x1024",
            "1:1": "1024x1024",
        }
        return size_map.get(aspect_ratio, "1024x1024")

    @classmethod
    def _size_for_images_api(cls, aspect_ratio: str, key_source: str) -> str:
        if key_source == "KRILL_GPT_IMAGE2_API_KEY":
            return cls._krill_size_for_aspect_ratio(aspect_ratio)
        return cls._size_for_aspect_ratio(aspect_ratio)

    @staticmethod
    def _prompt_with_aspect_ratio(prompt: str, aspect_ratio: str) -> str:
        if not aspect_ratio:
            return prompt
        full_width_ratio = aspect_ratio.replace(":", "：")
        if aspect_ratio in prompt or full_width_ratio in prompt:
            return prompt
        return f"{prompt}\n\n画面比例：{aspect_ratio}，严格按这个比例构图。"

    @staticmethod
    def _quality_for_images_api(quality: str) -> str:
        quality_map = {
            "standard": "medium",
            "hd": "high",
            "low": "low",
            "medium": "medium",
            "high": "high",
            "auto": "auto",
        }
        return quality_map.get((quality or "").lower(), "high")

    @classmethod
    def _selected_model(cls) -> str:
        return cls.IMAGE_MODEL

    @classmethod
    def _selected_api_key(cls) -> tuple[str, str]:
        for key in (
            "KRILL_GPT_IMAGE2_API_KEY",
            "GPT_IMAGE2_API_KEY",
            "JULING_GPT_IMAGE2_API_KEY",
            "OPENAI_API_KEY",
        ):
            value = os.getenv(key)
            if value:
                return value, key
        raise ValueError("请设置 KRILL_GPT_IMAGE2_API_KEY、GPT_IMAGE2_API_KEY、JULING_GPT_IMAGE2_API_KEY 或 OPENAI_API_KEY")

    @classmethod
    def _default_base_url(cls, endpoint: str, key_source: str) -> str:
        if key_source == "KRILL_GPT_IMAGE2_API_KEY":
            return os.getenv("KRILL_GPT_IMAGE2_BASE_URL", cls.KRILL_IMAGES_BASE_URL)
        if key_source == "JULING_GPT_IMAGE2_API_KEY":
            return (
                os.getenv("JULING_GPT_IMAGE2_BASE_URL")
                or os.getenv("JULING_BASE_URL")
                or cls.OPENAI_IMAGES_BASE_URL
            )
        if key_source == "OPENAI_API_KEY":
            return os.getenv("OPENAI_BASE_URL", cls.OPENAI_IMAGES_BASE_URL)
        return cls.OPENAI_IMAGES_BASE_URL

    @classmethod
    def _base_url_for_endpoint(cls, endpoint: str, key_source: str) -> str:
        if key_source == "KRILL_GPT_IMAGE2_API_KEY":
            env_names = (
                ("KRILL_GPT_IMAGE2_EDIT_BASE_URL", "KRILL_GPT_IMAGE2_BASE_URL")
                if endpoint == "edits"
                else ("KRILL_GPT_IMAGE2_BASE_URL",)
            )
        elif key_source == "JULING_GPT_IMAGE2_API_KEY":
            env_names = (
                ("JULING_GPT_IMAGE2_EDIT_BASE_URL", "JULING_GPT_IMAGE2_BASE_URL", "JULING_BASE_URL")
                if endpoint == "edits"
                else ("JULING_GPT_IMAGE2_BASE_URL", "JULING_BASE_URL")
            )
        else:
            env_names = (
                ("GPT_IMAGE2_EDIT_BASE_URL", "GPT_IMAGE2_BASE_URL")
                if endpoint == "edits"
                else ("GPT_IMAGE2_BASE_URL",)
            )

        configured = next((os.getenv(name) for name in env_names if os.getenv(name)), None)

        base_url = configured or cls._default_base_url(endpoint, key_source)
        return base_url.rstrip("/")

    @classmethod
    def _images_endpoint_url(cls, base_url: str, endpoint: str) -> str:
        base = base_url.rstrip("/")
        suffix = f"/images/{endpoint}"
        if base.endswith(suffix):
            return base
        if base.endswith("/images"):
            return f"{base}/{endpoint}"
        if base.endswith("/v1"):
            return f"{base}{suffix}"
        return f"{base}/v1{suffix}"

    @staticmethod
    def _auth_headers(api_key: str, *, json_content: bool) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
        if json_content:
            headers["Content-Type"] = "application/json"
        return headers

    def _generate_with_images_api(self, prompt: str, aspect_ratio: str, quality: str) -> str:
        api_key, key_source = self._selected_api_key()
        base_url = self._base_url_for_endpoint("generations", key_source)

        payload = {
            "model": self._selected_model(),
            "prompt": self._prompt_with_aspect_ratio(prompt, aspect_ratio),
            "size": self._size_for_images_api(aspect_ratio, key_source),
            "quality": self._quality_for_images_api(quality),
            "n": 1,
        }
        url = self._images_endpoint_url(base_url, "generations")

        print(f"[GPT Image 2] POST {url}")
        print(f"[GPT Image 2] 模型: {payload['model']}, 尺寸: {payload['size']}, 比例: {aspect_ratio}, 质量: {payload['quality']}")

        with httpx.Client(timeout=httpx.Timeout(30, read=180)) as client:
            resp = client.post(
                url,
                json=payload,
                headers=self._auth_headers(api_key, json_content=True),
            )

        if not (200 <= resp.status_code < 300):
            raise ValueError(f"Images API 请求失败，状态码: {resp.status_code}，响应: {resp.text[:500]}")

        return self._image_data_from_response(resp.json())

    def _generate_with_edits_api(
        self,
        prompt: str,
        image_paths: List[str],
        aspect_ratio: str,
        quality: str,
        mask_path: Optional[str] = None,
    ) -> str:
        api_key, key_source = self._selected_api_key()
        base_url = self._base_url_for_endpoint("edits", key_source)
        url = self._images_endpoint_url(base_url, "edits")

        data = {
            "model": self._selected_model(),
            "prompt": self._prompt_with_aspect_ratio(prompt, aspect_ratio),
            "size": self._size_for_images_api(aspect_ratio, key_source),
            "quality": self._quality_for_images_api(quality),
            "n": "1",
        }
        print(f"[GPT Image 2] POST {url}")
        print(f"[GPT Image 2] 编辑参考图: {len(image_paths)} 张, 尺寸: {data['size']}, 比例: {aspect_ratio}, 质量: {data['quality']}")

        with contextlib.ExitStack() as stack:
            files = []
            for image_path in image_paths:
                path = Path(image_path).expanduser()
                if not path.exists():
                    raise FileNotFoundError(f"参考图片不存在: {path}")
                mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
                files.append(("image[]", (path.name, stack.enter_context(path.open("rb")), mime_type)))

            if mask_path:
                path = Path(mask_path).expanduser()
                if not path.exists():
                    raise FileNotFoundError(f"mask 文件不存在: {path}")
                mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
                files.append(("mask", (path.name, stack.enter_context(path.open("rb")), mime_type)))

            resp = requests.post(
                url,
                data=data,
                files=files,
                headers=self._auth_headers(api_key, json_content=False),
                timeout=300,
            )

        if not (200 <= resp.status_code < 300):
            raise ValueError(f"Images Edit API 请求失败，状态码: {resp.status_code}，响应: {resp.text[:500]}")

        return self._image_data_from_response(resp.json())

    @staticmethod
    def _image_data_from_response(data: Dict[str, Any]) -> str:
        items = data.get("data") or []
        if not items:
            raise ValueError("Images API 未返回 data")

        first = items[0]
        if first.get("b64_json"):
            return f"data:image/png;base64,{first['b64_json']}"
        if first.get("url"):
            return first["url"]

        raise ValueError(f"Images API 未返回图片 URL 或 b64_json，字段: {list(first.keys())}")

    @staticmethod
    def _expected_aspect_ratio_value(aspect_ratio: str) -> Optional[float]:
        if not aspect_ratio or ":" not in aspect_ratio:
            return None
        try:
            width, height = aspect_ratio.split(":", 1)
            return float(width) / float(height)
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    @classmethod
    def _validate_saved_image_aspect_ratio(
        cls,
        output_path: str,
        aspect_ratio: str,
        tolerance: float = 0.03,
    ) -> None:
        expected = cls._expected_aspect_ratio_value(aspect_ratio)
        if expected is None:
            return

        with Image.open(output_path) as image:
            width, height = image.size

        if not width or not height:
            raise ValueError(f"图片尺寸无效，无法校验比例: {output_path}")

        actual = width / height
        if abs(actual - expected) > tolerance:
            raise ValueError(
                f"图片实际输出比例不符合 {aspect_ratio}: "
                f"实际尺寸 {width}x{height}，实际比例 {actual:.4f}"
            )

    @staticmethod
    def _save_image_data(image_url_or_data: str, output_path: str) -> None:
        if image_url_or_data.startswith("data:image/"):
            base64_data = image_url_or_data.split(",", 1)[1]
            Path(output_path).write_bytes(base64.b64decode(base64_data))
            print(f"[GPT Image 2] 图片已保存 (base64): {output_path}")
            return

        if image_url_or_data.startswith("http"):
            print(f"[GPT Image 2] 下载图片: {image_url_or_data[:80]}...")
            resp = requests.get(image_url_or_data, timeout=120)
            resp.raise_for_status()
            Path(output_path).write_bytes(resp.content)
            print(f"[GPT Image 2] 图片已保存 (URL): {output_path}")
            return

        raise ValueError(f"未知图片格式: {image_url_or_data[:100]}")


class GptImage2ProTool(GptImage2Tool):
    """GPT Image 2 Pro generation through the user-approved ZeakAI channel."""

    name: str = "GPT Image 2 Pro图像生成工具"
    description: str = (
        "使用 ZeakAI 的 gpt-image-2-pro 兼容 Images API 生成图片。"
        "参数与 GptImage2Tool 一致，仅在用户或项目策略显式选择 ZeakAI 时使用。"
    )

    IMAGE_MODEL: ClassVar[str] = "gpt-image-2-pro"
    ZEAKAI_DEFAULT_BASE_URL: ClassVar[str] = "https://api.zeakai.com/v1"

    def _run(
        self,
        prompt: str,
        output_path: str,
        aspect_ratio: str = "9:16",
        reference_image_paths: Optional[List[str]] = None,
        reference_image_path: Optional[str] = None,
        reference_prompt_prefix: str = "",
        mask_path: Optional[str] = None,
        quality: str = "hd",
    ) -> str:
        if reference_image_paths is None and reference_image_path is not None:
            reference_image_paths = (
                reference_image_path
                if isinstance(reference_image_path, list)
                else [reference_image_path]
            )

        endpoint_mode = self._endpoint_mode()
        if endpoint_mode in {"chat", "auto"} and not mask_path:
            try:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                prompt_for_model = self._prompt_with_aspect_ratio(prompt, aspect_ratio)
                if reference_image_paths and reference_prompt_prefix:
                    prompt_for_model = f"{reference_prompt_prefix}\n{prompt_for_model}"
                image_data = self._generate_with_chat_api(
                    prompt=prompt_for_model,
                    image_paths=reference_image_paths or [],
                    aspect_ratio=aspect_ratio,
                    quality=quality,
                )
                self._save_image_data(image_data, output_path)
                self._validate_saved_image_aspect_ratio(output_path, aspect_ratio)
                return f"GPT Image 2 Pro 图像生成成功！图像已保存到: {output_path}"
            except Exception as exc:
                if endpoint_mode == "chat":
                    return f"GPT Image 2 Pro 图像生成失败: {exc}"
                print(f"[GPT Image 2 Pro] chat 端点失败，回退 images: {exc}")

        result = super()._run(
            prompt=prompt,
            output_path=output_path,
            aspect_ratio=aspect_ratio,
            reference_image_paths=reference_image_paths,
            reference_prompt_prefix=reference_prompt_prefix,
            mask_path=mask_path,
            quality=quality,
        )
        return result.replace("GPT Image 2 图像生成", "GPT Image 2 Pro 图像生成", 1)

    @staticmethod
    def _size_for_aspect_ratio(aspect_ratio: str) -> str:
        size_map = {
            "9:16": "1024x1792",
            "16:9": "1792x1024",
            "1:1": "1024x1024",
        }
        return size_map.get(aspect_ratio, "1024x1792")

    @staticmethod
    def _endpoint_mode() -> str:
        raw = (
            os.getenv("ZEAKAI_GPT_IMAGE2_PRO_ENDPOINT")
            or os.getenv("GPT_IMAGE_ENDPOINT")
            or "auto"
        )
        mode = raw.strip().lower()
        return mode if mode in {"chat", "images", "auto"} else "auto"

    @classmethod
    def _selected_model(cls) -> str:
        return os.getenv("ZEAKAI_GPT_IMAGE2_PRO_MODEL", cls.IMAGE_MODEL)

    @staticmethod
    def _quality_for_images_api(quality: str) -> str:
        if not quality or quality == "auto":
            quality = os.getenv("ZEAKAI_GPT_IMAGE2_PRO_QUALITY", "high")
        return GptImage2Tool._quality_for_images_api(quality)

    @classmethod
    def _selected_api_key(cls) -> tuple[str, str]:
        for key in (
            "ZEAKAI_API_KEY",
            "ZEAKAI_GPT_IMAGE2_PRO_API_KEY",
        ):
            value = os.getenv(key)
            if value:
                return value, key
        raise ValueError("请设置 ZEAKAI_API_KEY/ZEAKAI_BASE_URL，或 ZEAKAI_GPT_IMAGE2_PRO_API_KEY/ZEAKAI_GPT_IMAGE2_PRO_BASE_URL")

    @classmethod
    def _default_base_url(cls, endpoint: str, key_source: str) -> str:
        return os.getenv("ZEAKAI_BASE_URL", cls.ZEAKAI_DEFAULT_BASE_URL)

    @classmethod
    def _base_url_for_endpoint(cls, endpoint: str, key_source: str) -> str:
        if endpoint == "edits":
            configured = (
                os.getenv("ZEAKAI_GPT_IMAGE2_PRO_EDIT_BASE_URL")
                or os.getenv("ZEAKAI_BASE_URL")
                or os.getenv("ZEAKAI_GPT_IMAGE2_PRO_BASE_URL")
            )
        else:
            configured = os.getenv("ZEAKAI_BASE_URL") or os.getenv("ZEAKAI_GPT_IMAGE2_PRO_BASE_URL")

        base_url = configured or cls._default_base_url(endpoint, key_source)
        return base_url.rstrip("/")

    @classmethod
    def _chat_endpoint_url(cls, base_url: str) -> str:
        base = base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    def _generate_with_chat_api(
        self,
        prompt: str,
        image_paths: List[str],
        aspect_ratio: str,
        quality: str,
    ) -> str:
        api_key, key_source = self._selected_api_key()
        base_url = self._base_url_for_endpoint("chat", key_source)
        url = self._chat_endpoint_url(base_url)

        content_parts: list[dict] = []
        for image_path in image_paths:
            path = Path(image_path).expanduser()
            if not path.exists():
                raise FileNotFoundError(f"参考图片不存在: {path}")
            content_parts.append({"type": "image_url", "image_url": {"url": self._file_to_data_url(path)}})
        content_parts.append({"type": "text", "text": prompt})

        payload = {
            "model": self._selected_model(),
            "messages": [{"role": "user", "content": content_parts}],
            "stream": True,
            "size": self._size_for_aspect_ratio(aspect_ratio),
            "quality": self._quality_for_images_api(quality),
            "n": 1,
        }

        print(f"[GPT Image 2 Pro] POST {url}")
        print(f"[GPT Image 2 Pro] 模型: {payload['model']}, 尺寸: {payload['size']}, 比例: {aspect_ratio}, 质量: {payload['quality']}")

        resp = requests.post(
            url,
            json=payload,
            headers=self._auth_headers(api_key, json_content=True),
            stream=True,
            timeout=240,
        )
        if not (200 <= resp.status_code < 300):
            try:
                body = resp.text[:500]
            finally:
                resp.close()
            raise ValueError(f"Chat API 请求失败，状态码: {resp.status_code}，响应: {body}")

        chunks: list[str] = []
        try:
            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="ignore") if isinstance(raw_line, bytes) else str(raw_line)
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str in {"", "[DONE]"}:
                    continue
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta") or {}
                    piece = delta.get("content") or ""
                    if piece:
                        chunks.append(piece)
        finally:
            resp.close()

        text = "".join(chunks).strip()
        if not text:
            raise ValueError("Chat API 流式返回为空")
        return self._image_data_from_text(text)

    @staticmethod
    def _file_to_data_url(path: Path) -> str:
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        return f"data:{mime_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"

    @staticmethod
    def _image_data_from_text(content: str) -> str:
        text = content.strip()
        if text.startswith("data:image/"):
            return text

        markdown_data = re.search(r"!\[[^\]]*\]\((data:image/[^)]+)\)", text)
        if markdown_data:
            return markdown_data.group(1)

        markdown_url = re.search(r"!\[[^\]]*\]\((https?://[^\s\)]+)\)", text)
        if markdown_url:
            return markdown_url.group(1)

        urls = re.findall(r"https?://[^\s\)\]\"']+", text)
        for url in urls:
            if re.search(r"\.(png|jpe?g|webp|gif)(\?|$)", url, re.I):
                return url
        if urls:
            return urls[0]

        stripped = re.sub(r"\s+", "", text)
        if len(stripped) > 200:
            base64.b64decode(stripped[:200], validate=True)
            return f"data:image/png;base64,{stripped}"

        raise ValueError(f"未能从 Chat API 响应提取图片: {text[:300]}")


class Seedream5ImageGenerator:
    """使用巨灵 API 的图像模型生成图片。

    默认模型可通过环境变量 JULING_DEFAULT_IMAGE_MODEL 切换；为空时优先使用
    'seedream-5.0'。

    base_url / api_key 读取 JULING_*。
    """

    DEFAULT_MODEL = "seedream-5.0"

    def __init__(self, aspect_ratio: str = "9:16"):
        configured_model = os.getenv('JULING_DEFAULT_IMAGE_MODEL')
        self.MODEL = configured_model or self.DEFAULT_MODEL
        self.model_candidates = [self.MODEL]

        self.base_url = os.getenv('JULING_BASE_URL')
        self.api_key = os.getenv('JULING_API_KEY')

        if not self.base_url or not self.api_key:
            raise ValueError("请设置环境变量 JULING_BASE_URL 和 JULING_API_KEY")

        self.base_url = self.base_url.rstrip("/")
        self.aspect_ratio = aspect_ratio

        if aspect_ratio == "9:16":
            self.size = "1080x1920"
        elif aspect_ratio == "16:9":
            self.size = "1920x1080"
        else:
            self.size = "1024x1024"

        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        print(f"[ImageGen] 初始化 model={self.MODEL} 比例={self.aspect_ratio} 尺寸={self.size}")

    def _stream_request(self, payload: Dict[str, Any]) -> Optional[str]:
        """发送流式请求并解析 SSE 响应，返回拼接后的 content"""
        url = f"{self.base_url}/v1/chat/completions"
        payload["stream"] = True

        print(f"[Seedream5] POST {url}")

        content_parts = []
        try:
            read_timeout = float(os.getenv("SEEDREAM5_READ_TIMEOUT", "240"))
            total_timeout = float(os.getenv("SEEDREAM5_TOTAL_TIMEOUT", "300"))
            deadline = time.monotonic() + max(1.0, total_timeout)
            with httpx.Client(timeout=httpx.Timeout(10, read=read_timeout)) as client:
                with client.stream("POST", url, json=payload, headers=self.headers) as resp:
                    if resp.status_code != 200:
                        resp.read()
                        raise Exception(
                            f"API 请求失败，状态码: {resp.status_code}，响应: {resp.text}"
                        )

                    print(f"[Seedream5] 状态码: {resp.status_code}，接收流式响应中...")

                    for line in resp.iter_lines():
                        if time.monotonic() > deadline:
                            raise TimeoutError(f"Seedream5 流式响应总超时: {total_timeout:g}s")
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        for choice in chunk.get("choices", []):
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                content_parts.append(content)

        except httpx.ConnectError as e:
            raise Exception(f"连接失败: {e}")
        except httpx.ReadTimeout as e:
            raise Exception(f"读取超时: {e}")

        full_content = "".join(content_parts)
        if full_content:
            print(f"[Seedream5] 收到内容长度: {len(full_content)} 字符")
        return full_content if full_content else None

    def _build_prompt(self, prompt: str) -> str:
        """将比例信息拼入 prompt"""
        if self.aspect_ratio and self.aspect_ratio != "1:1":
            return f"{prompt}，{self.aspect_ratio}比例"
        return prompt

    def _compress_image(self, image_path: str, max_size_mb: float = 2.0, max_dimension: int = 1024) -> str:
        """压缩图片以满足 API 限制"""
        import tempfile

        file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
        img = Image.open(image_path)
        width, height = img.size
        print(f"   原始图片: {width}x{height}, {file_size_mb:.2f}MB")

        needs_resize = width > max_dimension or height > max_dimension
        needs_compress = file_size_mb > max_size_mb

        if not needs_resize and not needs_compress:
            return image_path

        if needs_resize:
            if width > height:
                new_width = max_dimension
                new_height = int(height * (max_dimension / width))
            else:
                new_height = max_dimension
                new_width = int(width * (max_dimension / height))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"   调整尺寸: {new_width}x{new_height}")

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_path = temp_file.name
        temp_file.close()

        quality = 95
        while quality >= 60:
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            img.save(temp_path, 'JPEG', quality=quality, optimize=True)
            compressed_size_mb = os.path.getsize(temp_path) / (1024 * 1024)

            if compressed_size_mb <= max_size_mb:
                print(f"   压缩完成: {compressed_size_mb:.2f}MB (质量={quality})")
                return temp_path

            quality -= 10

        return temp_path

    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为 base64，参考图过大时先压缩。"""
        file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
        max_size_mb = float(os.getenv("SEEDREAM5_REFERENCE_MAX_MB", "2.0"))
        max_dimension = int(os.getenv("SEEDREAM5_REFERENCE_MAX_DIMENSION", "1024"))
        with Image.open(image_path) as image:
            width, height = image.size
        if file_size_mb > max_size_mb or width > max_dimension or height > max_dimension:
            print(
                f"   参考图片较大 ({width}x{height}, {file_size_mb:.2f}MB)，"
                f"压缩到 <= {max_dimension}px / {max_size_mb:.1f}MB..."
            )
            image_path = self._compress_image(
                image_path,
                max_size_mb=max_size_mb,
                max_dimension=max_dimension,
            )

        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def _generate_text_to_image(self, prompt: str) -> str:
        """文生图：纯文本提示生成图片，返回图片 URL 或 base64"""
        full_prompt = self._build_prompt(prompt)
        print(f"[Seedream5-文生图] 提示词: {full_prompt[:100]}{'...' if len(full_prompt) > 100 else ''}")

        last_error = None
        for model in self.model_candidates:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": full_prompt,
                    }
                ],
            }
            try:
                print(f"[Seedream5-文生图] 使用模型: {model}")
                content = self._stream_request(payload)
                if not content:
                    raise ValueError("Seedream5 API 未返回有效内容")
                return self._extract_image_from_content(content)
            except Exception as exc:
                last_error = exc
                print(f"[Seedream5-文生图] 模型 {model} 失败: {exc}")

        raise last_error or ValueError("Seedream5 API 未返回有效内容")

    def _generate_image_to_image(self, prompt: str, image_paths: List[str]) -> str:
        """图生图：基于参考图片 + 文本提示生成图片"""
        full_prompt = self._build_prompt(
            f"参考图片的角色特征，生成一张高质量图片。要求：{prompt}"
        )
        print(f"[Seedream5-图生图] 提示词: {full_prompt[:100]}{'...' if len(full_prompt) > 100 else ''}")

        content_parts = [{"type": "text", "text": full_prompt}]

        for i, image_path in enumerate(image_paths, 1):
            if not os.path.exists(image_path):
                print(f"   跳过不存在的参考图片: {image_path}")
                continue

            b64 = self._encode_image_to_base64(image_path)
            content_parts.insert(0, {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })
            print(f"   添加参考图 {i}: {os.path.basename(image_path)}")

        if len(content_parts) <= 1:
            raise ValueError("没有有效的参考图片")

        last_error = None
        for model in self.model_candidates:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": content_parts,
                    }
                ],
            }
            try:
                print(f"[Seedream5-图生图] 使用模型: {model}")
                content = self._stream_request(payload)
                if not content:
                    raise ValueError("Seedream5 API 未返回有效内容")
                return self._extract_image_from_content(content)
            except Exception as exc:
                last_error = exc
                print(f"[Seedream5-图生图] 模型 {model} 失败: {exc}")

        raise last_error or ValueError("Seedream5 API 未返回有效内容")

    def _extract_image_from_content(self, content: str) -> str:
        """从 API 返回内容中提取图片 URL 或 base64 数据。

        gpt-image-2 与 seedream-5.0 都通过 markdown 返回，但 gpt-image-2 经常返回
        ``![image](data:image/png;base64,...)``，所以两种 URL 都要识别。
        """
        content = content.strip()

        # 1. markdown 图片链接，先匹配 http(s)，再匹配 data:URL
        md_http = re.findall(r'!\[[^\]]*\]\((https?://[^)\s]+)\)', content)
        if md_http:
            print(f"[ImageGen] 找到 {len(md_http)} 个 http 图片 URL")
            return md_http[0]

        md_data = re.findall(
            r'!\[[^\]]*\]\((data:image/[a-zA-Z]+;base64,[A-Za-z0-9+/=]+)\)',
            content,
        )
        if md_data:
            print(f"[ImageGen] 找到 {len(md_data)} 个 base64 内联图片")
            return md_data[0]

        # 2. 尝试 JSON 格式
        try:
            data = json.loads(content)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        return item["image_url"]["url"]
            elif isinstance(data, dict) and "url" in data:
                return data["url"]
        except (json.JSONDecodeError, TypeError):
            pass

        # 3. 直接 URL
        if content.startswith("http"):
            return content.split()[0]

        # 4. data URL
        if content.startswith("data:image"):
            return content

        # 5. 纯 base64
        if len(content) > 200:
            try:
                base64.b64decode(content[:100])
                return f"data:image/png;base64,{content}"
            except Exception:
                pass

        # 6. 从文本中提取任意 URL
        urls = re.findall(r'(https?://[^\s\)]+)', content)
        if urls:
            print(f"[ImageGen] 从内容中提取到 URL: {urls[0][:80]}...")
            return urls[0]

        raise ValueError(
            f"未能从图像 API 响应中提取图片，内容前 300 字符: {content[:300]}"
        )

    def _save_image(self, image_url_or_data: str, output_path: str) -> str:
        """从 URL 或 base64 data URL 保存图片"""
        if image_url_or_data.startswith('data:image/'):
            base64_data = image_url_or_data.split(',', 1)[1]
            image_bytes = base64.b64decode(base64_data)
            with open(output_path, 'wb') as f:
                f.write(image_bytes)
            print(f"[Seedream5] 图片已保存 (base64): {output_path}")
        elif image_url_or_data.startswith('http'):
            parsed = urlparse(image_url_or_data)
            safe_url_label = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            print(f"[Seedream5] 下载图片: {safe_url_label}")
            total_timeout = float(os.getenv("SEEDREAM5_DOWNLOAD_TIMEOUT", "120"))
            read_timeout = float(os.getenv("SEEDREAM5_DOWNLOAD_READ_TIMEOUT", "30"))
            deadline = time.monotonic() + max(1.0, total_timeout)
            resp = requests.get(
                image_url_or_data,
                stream=True,
                timeout=(10, read_timeout),
            )
            resp.raise_for_status()
            with open(output_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=1024 * 64):
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"Seedream5 图片下载总超时: {total_timeout:g}s")
                    if chunk:
                        f.write(chunk)
            print(f"[Seedream5] 图片已保存 (URL): {output_path}")
        else:
            raise ValueError(f"未知图片格式: {image_url_or_data[:100]}")

        return output_path

    def generate_scene_image(
        self,
        scene_data: Dict[str, Any],
        output_dir: str = None,
        output_path: str = None,
        reference_image_paths: List[str] = None,
        reference_prompt_prefix: str = ""
    ) -> str:
        """
        为单个场景生成图片，支持文生图和图生图。

        Args:
            scene_data: 场景数据，包含 'image_prompt' 和 'index'
            output_dir: 图片保存目录（当 output_path 未提供时使用）
            output_path: 完整的输出文件路径（优先使用）
            reference_image_paths: 参考图路径列表（可选）
            reference_prompt_prefix: 图生图时的提示词前缀（可选）

        Returns:
            生成的图片路径
        """
        scene_index = scene_data.get('index', 0)
        image_prompt = scene_data.get('image_prompt', '')

        if not image_prompt:
            raise ValueError(f"场景 {scene_index} 缺少 image_prompt")

        final_prompt = f"{reference_prompt_prefix}{image_prompt}" if reference_prompt_prefix else image_prompt

        if output_path:
            output_dir_from_path = os.path.dirname(output_path)
            if output_dir_from_path:
                os.makedirs(output_dir_from_path, exist_ok=True)
        else:
            if not output_dir:
                output_dir = "."
            if isinstance(scene_index, str):
                safe_filename = f"scene_{scene_index}.jpg"
            else:
                safe_filename = f"scene_{scene_index:02d}.jpg"
            output_path = os.path.join(output_dir, safe_filename)
            os.makedirs(output_dir, exist_ok=True)

        try:
            image_data = None

            if reference_image_paths and any(os.path.exists(p) for p in reference_image_paths):
                valid_paths = [p for p in reference_image_paths if os.path.exists(p)]
                print(f"[Seedream5-图生图] 场景 {scene_index} 使用参考图: "
                      f"{[os.path.basename(p) for p in valid_paths]}")
                image_data = self._generate_image_to_image(final_prompt, valid_paths)
            else:
                print(f"[Seedream5-文生图] 场景 {scene_index} 生成图片: "
                      f"{final_prompt[:100]}{'...' if len(final_prompt) > 100 else ''}")
                image_data = self._generate_text_to_image(final_prompt)

            self._save_image(image_data, output_path)
            print(f"[Seedream5] 图片已保存至: {output_path}")
            return output_path

        except Exception as e:
            print(f"[Seedream5] 图片处理失败: {str(e)}")
            raise
