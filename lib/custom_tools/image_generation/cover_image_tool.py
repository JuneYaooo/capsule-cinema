#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
封面图生成工具
为视频生成带标题文字的封面图
"""

from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from src.logger import get_logger
from src.utils.font_utils import DEFAULT_FONT_PATH

logger = get_logger('cover_image_tool')


class CoverImageInput(BaseModel):
    """封面图生成输入模型"""
    base_image_path: str = Field(..., description="基础图片路径（通常是第一个场景的图片）")
    title_text: str = Field(..., description="封面标题文字")
    output_path: str = Field(..., description="输出封面图片路径")
    aspect_ratio: str = Field(default='9:16', description="视频宽高比，'9:16' 或 '16:9'")
    font_path: str = Field(default=DEFAULT_FONT_PATH, description="字体文件路径")


class CoverImageGenerator:
    """封面图生成器（静态方法类）"""

    @staticmethod
    def create_cover_with_text(
        base_image_path: str,
        title_text: str,
        output_path: str,
        aspect_ratio: str = '9:16',
        font_path: str = DEFAULT_FONT_PATH
    ) -> str:
        """在基础图片上添加标题文字，生成封面

        Args:
            base_image_path: 基础图片路径
            title_text: 标题文字
            output_path: 输出路径
            aspect_ratio: 宽高比
            font_path: 字体文件路径

        Returns:
            生成的封面图片路径，如果失败返回原图路径
        """
        if not base_image_path or not Path(base_image_path).exists():
            logger.warning("⚠️ 基础图片不存在，无法生成封面")
            return base_image_path

        try:
            # 打开图片
            img = Image.open(base_image_path)
            width, height = img.size

            # 创建绘图对象
            draw = ImageDraw.Draw(img)

            # 根据宽高比调整字体和位置
            if aspect_ratio == "9:16":
                # 竖屏布局 - 文字在中上位置，字体适中
                fontsize = max(80, int(width * 0.12))
                y_pos = int(height * 0.30)
                max_width = int(width * 0.85)  # 文字最大宽度
            else:
                # 横屏布局
                fontsize = max(90, int(width * 0.08))
                y_pos = int(height * 0.30)
                max_width = int(width * 0.85)

            # 加载字体
            try:
                font = ImageFont.truetype(font_path, fontsize)
            except Exception as e:
                logger.warning(f"⚠️ 无法加载字体 {font_path}，使用默认字体: {str(e)}")
                font = ImageFont.load_default()

            # 文字换行处理
            lines = CoverImageGenerator._wrap_text(title_text, font, max_width, draw)

            # 计算总高度
            line_height = fontsize + 10
            total_height = line_height * len(lines)
            current_y = y_pos

            outline_width = 5

            # 逐行绘制
            for line in lines:
                # 计算单行位置（居中）
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                x_pos = (width - text_width) // 2

                # 绘制文字描边（黑色）
                for dx in range(-outline_width, outline_width + 1):
                    for dy in range(-outline_width, outline_width + 1):
                        if dx*dx + dy*dy <= outline_width*outline_width:
                            draw.text((x_pos + dx, current_y + dy), line, font=font, fill='black')

                # 绘制文字主体（白色）
                draw.text((x_pos, current_y), line, font=font, fill='white')

                current_y += line_height

            # 确保输出目录存在
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # 保存封面
            img.save(output_path, quality=95)

            logger.info(f"✅ 封面生成成功: {output_path}")
            logger.info(f"   封面文字: {title_text} ({len(lines)}行)")
            return output_path

        except Exception as e:
            logger.error(f"❌ 封面生成失败: {str(e)}")
            return base_image_path  # 返回原图

    @staticmethod
    def _wrap_text(text: str, font, max_width: int, draw) -> List[str]:
        """文字自动换行（支持中英文混排，英文按单词边界换行）

        Args:
            text: 要换行的文本
            font: 字体对象
            max_width: 最大宽度
            draw: ImageDraw对象

        Returns:
            换行后的文本列表
        """
        import re

        lines = []
        current_line = ""

        # 将文本分割为单词和字符的混合列表
        # 英文单词作为整体，中文字符单独处理
        tokens = re.findall(r'[a-zA-Z0-9]+|[^\sa-zA-Z0-9]|\s', text)

        i = 0
        while i < len(tokens):
            token = tokens[i]
            test_line = current_line + token
            bbox = draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]

            if text_width <= max_width:
                current_line = test_line
                i += 1
            else:
                # 如果当前行不为空，先保存当前行
                if current_line.strip():
                    lines.append(current_line.rstrip())
                    current_line = ""
                else:
                    # 当前行为空但单个token就超过最大宽度
                    # 对于长英文单词，需要强制按字符拆分
                    if re.match(r'[a-zA-Z0-9]+', token):
                        # 长英文单词按字符拆分
                        for char in token:
                            test_line = current_line + char
                            bbox = draw.textbbox((0, 0), test_line, font=font)
                            text_width = bbox[2] - bbox[0]

                            if text_width <= max_width:
                                current_line = test_line
                            else:
                                if current_line:
                                    lines.append(current_line)
                                current_line = char
                        i += 1
                    else:
                        # 中文字符或其他字符直接添加
                        current_line = token
                        i += 1

        # 添加最后一行
        if current_line.strip():
            lines.append(current_line.rstrip())

        return lines if lines else [text]

    @staticmethod
    def get_first_scene_image(image_result: dict) -> str:
        """从图片生成结果中获取第一个场景的图片

        Args:
            image_result: 图片生成结果字典

        Returns:
            第一个场景图片路径，如果不存在返回空字符串
        """
        image_outputs = image_result.get('outputs', {})
        first_image = image_outputs.get(0, '')

        if first_image and Path(first_image).exists():
            logger.info(f"✅ 获取第一个场景图片: {first_image}")
            return first_image
        else:
            logger.warning("⚠️ 第一个场景图片不存在")
            return ''


class CoverImageTool(BaseTool):
    """封面图生成工具"""
    name: str = "Generate Cover Image"
    description: str = "在基础图片上添加标题文字，生成视频封面图"
    args_schema: type[BaseModel] = CoverImageInput

    def _run(
        self,
        base_image_path: str,
        title_text: str,
        output_path: str,
        aspect_ratio: str = '9:16',
        font_path: str = DEFAULT_FONT_PATH
    ) -> str:
        """执行工具"""
        return CoverImageGenerator.create_cover_with_text(
            base_image_path=base_image_path,
            title_text=title_text,
            output_path=output_path,
            aspect_ratio=aspect_ratio,
            font_path=font_path
        )
