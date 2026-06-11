#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini3-Pro 图片生成工具
使用 OpenAI 兼容格式调用 Gemini-3-Pro-Image API 生成图片，支持文生图和图生图
"""

import os
import base64
import re
import requests
from pathlib import Path
from typing import Dict, Any, List, Type, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

load_dotenv()


class Gemini3ProImageGeneratorSchema(BaseModel):
    """Gemini3Pro图像生成工具的输入参数"""
    prompt: str = Field(..., description="图像生成的文本提示词")
    output_path: str = Field(..., description="生成图像的保存路径")
    aspect_ratio: str = Field(default="9:16", description="宽高比: '16:9' 或 '9:16'")
    reference_image_paths: Optional[List[str]] = Field(default=None, description="参考图片路径列表（可选）")
    reference_image_path: Optional[str] = Field(default=None, description="单个参考图片路径（可选，兼容参数）")
    quality: str = Field(default="high", description="图像质量")
    size: str = Field(default="auto", description="图片尺寸")


class Gemini3ProImageGeneratorTool(BaseTool):
    name: str = "Gemini3Pro图像生成工具"
    description: str = (
        "使用Gemini-3-Pro-Image模型通过OpenAI兼容格式生成图片。"
        "支持文生图和图生图功能，适用于创意设计、内容创作等场景。"
    )
    args_schema: Type[BaseModel] = Gemini3ProImageGeneratorSchema

    def _run(
        self,
        prompt: str,
        output_path: str,
        aspect_ratio: str = "9:16",
        reference_image_paths: Optional[List[str]] = None,
        reference_image_path: Optional[str] = None,
        quality: str = "high",
        size: str = "auto"
    ) -> str:
        try:
            if reference_image_paths is None and reference_image_path is not None:
                if isinstance(reference_image_path, list):
                    reference_image_paths = reference_image_path
                else:
                    reference_image_paths = [reference_image_path]

            generator = Gemini3ProImageGenerator(aspect_ratio=aspect_ratio)

            scene_data = {'index': 1, 'image_prompt': prompt}

            output_dir_path = os.path.dirname(output_path)
            if output_dir_path:
                os.makedirs(output_dir_path, exist_ok=True)

            result_path = generator.generate_scene_image(
                scene_data=scene_data,
                output_path=output_path,
                reference_image_paths=reference_image_paths,
                quality=quality,
                size=size
            )

            return f"✅ Gemini3Pro图像生成成功！图像已保存到: {result_path}"

        except Exception as e:
            return f"❌ Gemini3Pro图像生成失败: {str(e)}"


class Gemini3ProImageGenerator:
    """使用Gemini-3-Pro-Image模型通过OpenAI兼容格式生成图片"""

    def __init__(self, aspect_ratio: str = "9:16"):
        self.base_url = os.getenv('GEMINI3_PRO_BASE_URL')
        self.api_key = os.getenv('GEMINI3_PRO_API_KEY')
        self.model_name = "gemini-3-pro-image-preview"

        self.aspect_ratio = aspect_ratio
        if aspect_ratio == "9:16":
            self.default_size = "1024x1536"
        else:
            self.default_size = "1536x1024"

        print(f"🎨 初始化Gemini3Pro图片生成器 (宽高比: {self.aspect_ratio}, 默认尺寸: {self.default_size})")

        if not self.base_url or not self.api_key:
            raise ValueError("请配置 GEMINI3_PRO_BASE_URL 和 GEMINI3_PRO_API_KEY")

    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为base64格式（带data URI前缀）"""
        with open(image_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode('utf-8')
        suffix = Path(image_path).suffix.lower()
        mime_types = {
            '.jpeg': 'image/jpeg', '.jpg': 'image/jpeg',
            '.png': 'image/png', '.webp': 'image/webp',
            '.bmp': 'image/bmp', '.gif': 'image/gif'
        }
        mime_type = mime_types.get(suffix, 'image/png')
        return f"data:{mime_type};base64,{encoded}"

    def _download_image(self, url: str, output_path: str) -> bool:
        """下载图片文件"""
        try:
            print(f"📥 正在下载图片: {url}")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"✅ 图片已保存到: {output_path}")
            return True
        except Exception as e:
            print(f"❌ 下载失败: {e}")
            return False

    def _save_image_from_data(self, data: str, output_path: str) -> str:
        """从URL或base64数据保存图片到文件"""
        if data.startswith('data:image/'):
            base64_data = data.split(',')[1]
            image_data = base64.b64decode(base64_data)
            with open(output_path, 'wb') as f:
                f.write(image_data)
            return output_path
        else:
            self._download_image(data, output_path)
            return output_path

    def _generate_with_chat(self, prompt: str, size: str = "auto", quality: str = "high") -> str:
        """
        使用 OpenAI 兼容的 Chat 接口生成图片（文生图）

        Returns:
            图片URL或base64数据
        """
        url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
        full_prompt = f"{prompt} {self.aspect_ratio}"

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": full_prompt}
            ]
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        print(f"🔗 发送请求到Gemini3Pro API (文生图): {url}")
        print(f"🔄 使用提示词: {full_prompt[:100]}{'...' if len(full_prompt) > 100 else ''}")

        response = requests.post(url, headers=headers, json=payload, timeout=300)

        print(f"📥 收到响应，状态码: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ API请求失败: {response.text}")
            response.raise_for_status()

        result = response.json()

        if "choices" in result:
            content = result["choices"][0]["message"].get("content", "")

            # 尝试提取 base64 图片
            b64_match = re.search(r'data:image/([\w]+);base64,([A-Za-z0-9+/=]+)', content)
            if b64_match:
                fmt = b64_match.group(1)
                b64_data = b64_match.group(2)
                print(f"✅ 获取到base64图片数据 (格式: {fmt})")
                return f"data:image/{fmt};base64,{b64_data}"

            # 直接URL
            if content.startswith("http"):
                print(f"✅ 获取到图片URL: {content}")
                return content

            # 从响应中提取URL
            url_patterns = [
                r'!\[.*?\]\((https?://[^\)]+)\)',
                r'(https?://[^\s\)]+\.(?:jpg|jpeg|png|gif|webp))',
                r'(https?://[^\s\)]+)'
            ]
            for pattern in url_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    print(f"✅ 从响应中提取到图片URL: {matches[0]}")
                    return matches[0]

            raise ValueError(f"未在响应中找到图片数据。响应内容: {content[:200]}")

        raise ValueError("API响应格式异常")

    def _generate_with_edits(self, prompt: str, image_paths: List[str], size: str = "auto", quality: str = "high") -> str:
        """
        使用 Chat Completions 接口 + multimodal 格式实现图生图

        Returns:
            图片URL或base64数据
        """
        url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
        full_prompt = (
            f"Please strictly follow the character appearance, clothing, hairstyle, "
            f"and facial features from the reference image. {prompt} {self.aspect_ratio}. "
            f"Keep the character features from the reference, only change pose, expression and background."
        )

        print(f"🔗 发送请求到Gemini3Pro API (图生图-chat): {url}")
        print(f"🔄 使用提示词: {full_prompt[:100]}...")
        print(f"📷 参考图片数量: {len(image_paths)}")

        # 构建 multimodal content: 先放参考图，再放文本提示
        content_parts = []
        for image_path in image_paths:
            if os.path.exists(image_path):
                print(f"   添加参考图: {os.path.basename(image_path)}")
                b64_data_uri = self._encode_image_to_base64(image_path)
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": b64_data_uri}
                })

        content_parts.append({"type": "text", "text": full_prompt})

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": content_parts}
            ]
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, json=payload, timeout=300)

        print(f"📥 收到响应，状态码: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ API请求失败: {response.text}")
            response.raise_for_status()

        result = response.json()

        if "choices" in result:
            content = result["choices"][0]["message"].get("content", "")

            # 尝试提取 base64 图片
            b64_match = re.search(r'data:image/([\w]+);base64,([A-Za-z0-9+/=]+)', content)
            if b64_match:
                fmt = b64_match.group(1)
                b64_data = b64_match.group(2)
                print(f"✅ 获取到base64图片数据 (格式: {fmt})")
                return f"data:image/{fmt};base64,{b64_data}"

            # 直接URL
            if content.startswith("http"):
                print(f"✅ 获取到图片URL: {content}")
                return content

            # 从响应中提取URL
            url_patterns = [
                r'!\[.*?\]\((https?://[^\)]+)\)',
                r'(https?://[^\s\)]+\.(?:jpg|jpeg|png|gif|webp))',
                r'(https?://[^\s\)]+)'
            ]
            for pattern in url_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    print(f"✅ 从响应中提取到图片URL: {matches[0]}")
                    return matches[0]

            raise ValueError(f"未在响应中找到图片数据。响应内容: {content[:200]}")

        raise ValueError("API响应格式异常")

    def generate_scene_image(
        self,
        scene_data: Dict[str, Any],
        output_path: str,
        reference_image_paths: Optional[List[str]] = None,
        quality: str = "high",
        size: str = "auto"
    ) -> str:
        """为单个场景生成图片，支持文生图和图生图"""
        scene_index = scene_data.get('index', 0)
        image_prompt = scene_data.get('image_prompt', '')

        if not image_prompt:
            raise ValueError(f"场景 {scene_index} 缺少 image_prompt")

        output_dir_from_path = os.path.dirname(output_path)
        if output_dir_from_path:
            os.makedirs(output_dir_from_path, exist_ok=True)

        try:
            image_data = None

            if reference_image_paths:
                print(f"📋 参考图片列表: {reference_image_paths}")
                valid_paths = [path for path in reference_image_paths if os.path.exists(path)]
                print(f"✅ 有效参考图片: {valid_paths}")

                if valid_paths:
                    print(f"🖼️ [Gemini3Pro-图生图] 场景 {scene_index} 使用参考图: {[os.path.basename(p) for p in valid_paths]}")
                    image_data = self._generate_with_edits(
                        prompt=image_prompt,
                        image_paths=valid_paths,
                        size=size,
                        quality=quality
                    )
                else:
                    print(f"⚠️ 参考图路径无效，切换到文生图模式")
                    reference_image_paths = None

            if image_data is None:
                print(f"🎨 [Gemini3Pro-文生图] 开始生成图片: {image_prompt[:100]}{'...' if len(image_prompt) > 100 else ''}")
                image_data = self._generate_with_chat(
                    prompt=image_prompt,
                    size=size,
                    quality=quality
                )

            print(f"🔗 保存图片数据")
            self._save_image_from_data(image_data, output_path)
            print(f"✅ [Gemini3Pro] 图片已保存至: {output_path}")

            return output_path

        except Exception as e:
            print(f"❌ Gemini3Pro 图片处理失败: {str(e)}")
            raise
