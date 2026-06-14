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
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Type, Optional
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

    gpt-image-2 使用 OpenAI Images 兼容接口生成图片。带参考图的场景
    暂时保留旧 chat-completions 兼容路径，避免把未验证的编辑接口接进主链路。
    """

    name: str = "GPT Image 2图像生成工具"
    description: str = (
        "使用 gpt-image-2 模型生成图片的工具（Images API 兼容接口）。"
        "参数与 Seedream5ImageGeneratorTool 一致。"
    )

    IMAGE_MODEL: str = "gpt-image-2"

    def _run(
        self,
        prompt: str,
        output_path: str,
        aspect_ratio: str = "9:16",
        reference_image_paths: Optional[List[str]] = None,
        reference_image_path: Optional[str] = None,
        reference_prompt_prefix: str = "",
        quality: str = "hd",
    ) -> str:
        if reference_image_paths is None and reference_image_path is not None:
            reference_image_paths = (
                reference_image_path
                if isinstance(reference_image_path, list)
                else [reference_image_path]
            )

        if reference_image_paths:
            return self._run_legacy_chat_fallback(
                prompt=prompt,
                output_path=output_path,
                aspect_ratio=aspect_ratio,
                reference_image_paths=reference_image_paths,
                reference_prompt_prefix=reference_prompt_prefix,
                quality=quality,
            )

        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            image_data = self._generate_with_images_api(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                quality=quality,
            )
            self._save_image_data(image_data, output_path)
            return f"GPT Image 2 图像生成成功！图像已保存到: {output_path}"
        except Exception as exc:
            return f"GPT Image 2 图像生成失败: {exc}"

    def _run_legacy_chat_fallback(self, **kwargs: Any) -> str:
        previous = os.environ.get("JULING_DEFAULT_IMAGE_MODEL")
        os.environ["JULING_DEFAULT_IMAGE_MODEL"] = self.IMAGE_MODEL
        try:
            return super()._run(**kwargs)
        finally:
            if previous is None:
                os.environ.pop("JULING_DEFAULT_IMAGE_MODEL", None)
            else:
                os.environ["JULING_DEFAULT_IMAGE_MODEL"] = previous

    @staticmethod
    def _size_for_aspect_ratio(aspect_ratio: str) -> str:
        if aspect_ratio == "9:16":
            return "1024x1536"
        if aspect_ratio == "16:9":
            return "1536x1024"
        return "1024x1024"

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

    def _generate_with_images_api(self, prompt: str, aspect_ratio: str, quality: str) -> str:
        base_url = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("JULING_GPT_IMAGE2_BASE_URL")
            or os.getenv("JULING_BASE_URL")
            or "https://api.openai.com"
        ).rstrip("/")
        api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("JULING_GPT_IMAGE2_API_KEY")
            or os.getenv("JULING_API_KEY")
        )
        if not api_key:
            raise ValueError(
                "请设置 OPENAI_API_KEY，或 JULING_GPT_IMAGE2_API_KEY/JULING_API_KEY"
            )

        payload = {
            "model": self.IMAGE_MODEL,
            "prompt": prompt,
            "size": self._size_for_aspect_ratio(aspect_ratio),
            "quality": self._quality_for_images_api(quality),
            "n": 1,
        }
        url = f"{base_url}/v1/images/generations"

        print(f"[GPT Image 2] POST {url}")
        print(f"[GPT Image 2] 模型: {self.IMAGE_MODEL}, 尺寸: {payload['size']}, 质量: {payload['quality']}")

        with httpx.Client(timeout=httpx.Timeout(30, read=180)) as client:
            resp = client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code != 200:
            raise ValueError(f"Images API 请求失败，状态码: {resp.status_code}，响应: {resp.text[:500]}")

        data = resp.json()
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


class Seedream5ImageGenerator:
    """使用巨灵 API 的图像模型生成图片。

    默认模型可通过环境变量 JULING_DEFAULT_IMAGE_MODEL 切换；为空时优先使用
    'seedream-5.0'，并在失败时尝试兼容图片模型。

    base_url / api_key 优先读 JULING_GPT_IMAGE2_*，回落到 JULING_*。
    """

    DEFAULT_MODEL = "seedream-5.0"
    FALLBACK_MODELS = ("gpt-4o-image", "gpt-image-2")

    def __init__(self, aspect_ratio: str = "9:16"):
        # 模型可独立配置；同一中转商下 gpt-image-2 / seedream-5.0 / gpt-4o-image
        # 都走 /v1/chat/completions 流式协议，参数兼容。
        configured_model = os.getenv('JULING_DEFAULT_IMAGE_MODEL')
        self.MODEL = configured_model or self.DEFAULT_MODEL
        self.model_candidates = (
            [configured_model]
            if configured_model
            else [self.DEFAULT_MODEL, *self.FALLBACK_MODELS]
        )

        # 优先用 GPT_IMAGE2 专用配置（额度独立），回落到通用 JULING 配置。
        self.base_url = (
            os.getenv('JULING_GPT_IMAGE2_BASE_URL')
            or os.getenv('JULING_BASE_URL')
        )
        self.api_key = (
            os.getenv('JULING_GPT_IMAGE2_API_KEY')
            or os.getenv('JULING_API_KEY')
        )

        if not self.base_url or not self.api_key:
            raise ValueError(
                "请设置环境变量 JULING_BASE_URL 和 JULING_API_KEY "
                "(或 JULING_GPT_IMAGE2_BASE_URL / JULING_GPT_IMAGE2_API_KEY)"
            )

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
            with httpx.Client(timeout=httpx.Timeout(10, read=None)) as client:
                with client.stream("POST", url, json=payload, headers=self.headers) as resp:
                    if resp.status_code != 200:
                        resp.read()
                        raise Exception(
                            f"API 请求失败，状态码: {resp.status_code}，响应: {resp.text}"
                        )

                    print(f"[Seedream5] 状态码: {resp.status_code}，接收流式响应中...")

                    for line in resp.iter_lines():
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

    def _compress_image(self, image_path: str, max_size_mb: float = 5.0, max_dimension: int = 2048) -> str:
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
        """将图片编码为 base64，超过 5MB 先压缩"""
        file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
        if file_size_mb > 5.0:
            print(f"   图片较大 ({file_size_mb:.2f}MB)，正在压缩...")
            image_path = self._compress_image(image_path)

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
            print(f"[Seedream5] 下载图片: {image_url_or_data[:80]}...")
            resp = requests.get(image_url_or_data, timeout=120)
            resp.raise_for_status()
            with open(output_path, 'wb') as f:
                f.write(resp.content)
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
