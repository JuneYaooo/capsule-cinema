#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕样式解析器 - 从用户要求中解析字幕样式配置
"""

import re
from typing import List, Dict, Any, Optional
from src.logger import get_logger

logger = get_logger('subtitle_style_parser')


class SubtitleStyleParser:
    """字幕样式解析器 - 从用户自然语言要求中提取字幕样式配置"""

    # 颜色映射
    COLOR_MAP = {
        '蓝色': '#4A9EFF',
        '红色': '#FF4444',
        '黄色': '#FFFF00',
        '绿色': '#44FF44',
        '白色': 'white',
        '金色': '#FFD700',
        '橙色': '#FF8C00',
        '紫色': '#9B59B6',
        '粉色': '#FF69B4',
        '黑色': 'black',
    }

    # 位置映射
    POSITION_MAP = {
        '顶部': 'top',
        '上方': 'top',
        '头部': 'top',
        '底部': 'bottom',
        '下方': 'bottom',
        '底下': 'bottom',
        '中间': 'center',
        '居中': 'center',
    }

    @classmethod
    def parse_subtitle_style_from_requirements(
        cls,
        user_requirements: str,
        storyboard: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        从用户要求中解析字幕样式配置

        Args:
            user_requirements: 用户要求文本
            storyboard: 分镜脚本数据（可选）

        Returns:
            字幕样式配置字典:
            {
                "subtitle_mode": "single" | "multi_layer",
                "default_style": "default" | "title" | "dialogue" | "speaker",
                "layers": [
                    {
                        "layer_type": "title",
                        "style": "title",
                        "position": "top",
                        "font_color": "#4A9EFF",
                    },
                    {
                        "layer_type": "dialogue",
                        "style": "dialogue",
                        "position": "bottom",
                    }
                ],
                "use_flexible_subtitle": True | False
            }
        """
        config = {
            "subtitle_mode": "single",
            "default_style": "default",
            "layers": [],
            "use_flexible_subtitle": False
        }

        if not user_requirements:
            return config

        user_requirements = user_requirements.lower()

        # 1. 检测是否需要多层字幕
        multi_layer_patterns = [
            r'(顶部|上方).*(字幕|标题).*(底部|下方).*(字幕|对话)',
            r'(多层|双层|分层).*(字幕)',
            r'(标题|题目).*(对话|字幕)',
        ]

        for pattern in multi_layer_patterns:
            if re.search(pattern, user_requirements):
                config["subtitle_mode"] = "multi_layer"
                config["use_flexible_subtitle"] = True
                logger.info("检测到多层字幕需求")
                break

        # 2. 检测顶部标题字幕
        title_patterns = [
            r'(顶部|上方|头部).*(字幕|标题)',
            r'(一行|有个).*(蓝色|标题).*(顶部|上方)',
        ]

        for pattern in title_patterns:
            if re.search(pattern, user_requirements):
                title_layer = {
                    "layer_type": "title",
                    "style": "title",
                    "position": "top",
                }

                # 检测颜色
                for color_name, color_code in cls.COLOR_MAP.items():
                    if color_name in user_requirements:
                        title_layer["font_color"] = color_code
                        logger.info(f"顶部字幕颜色: {color_name}")
                        break

                config["layers"].append(title_layer)
                config["use_flexible_subtitle"] = True
                logger.info("添加顶部标题字幕层")
                break

        # 3. 检测底部对话字幕
        dialogue_patterns = [
            r'(底部|下方|底下).*(对话|字幕)',
            r'(对话|台词).*(字幕)',
        ]

        for pattern in dialogue_patterns:
            if re.search(pattern, user_requirements):
                dialogue_layer = {
                    "layer_type": "dialogue",
                    "style": "dialogue",
                    "position": "bottom",
                }

                config["layers"].append(dialogue_layer)
                config["use_flexible_subtitle"] = True
                logger.info("添加底部对话字幕层")
                break

        # 4. 检测动态说话人字幕
        speaker_patterns = [
            r'(说话人|人物|角色).*(附近|旁边|周围).*(字幕)',
            r'(动态|跟随).*(字幕)',
            r'(人物).*(对话)',
        ]

        for pattern in speaker_patterns:
            if re.search(pattern, user_requirements):
                speaker_layer = {
                    "layer_type": "speaker",
                    "style": "speaker",
                    "position": "custom",
                }

                config["layers"].append(speaker_layer)
                config["use_flexible_subtitle"] = True
                logger.info("添加动态说话人字幕层")
                break

        # 5. 如果只有单层字幕，检测样式要求
        if not config["layers"]:
            # 检测位置
            for position_name, position_code in cls.POSITION_MAP.items():
                if position_name in user_requirements:
                    config["default_position"] = position_code

            # 检测颜色
            for color_name, color_code in cls.COLOR_MAP.items():
                if color_name in user_requirements:
                    config["default_color"] = color_code
                    logger.info(f"字幕颜色: {color_name}")

            # 如果用户有特殊要求，使用灵活字幕工具
            if "default_position" in config or "default_color" in config:
                config["use_flexible_subtitle"] = True

        # 6. 如果没有检测到任何特殊配置，使用默认配置
        if not config["use_flexible_subtitle"]:
            logger.info("使用默认字幕样式")

        return config

    @classmethod
    def build_subtitle_layers_for_scene(
        cls,
        scene: Dict[str, Any],
        style_config: Dict[str, Any],
        video_duration: float
    ) -> List[Dict[str, Any]]:
        """
        为单个场景构建字幕层配置

        Args:
            scene: 场景数据（包含 subtitles, narration, subtitle_text 等）
            style_config: 从用户要求解析的样式配置
            video_duration: 视频时长

        Returns:
            字幕层列表

        优先级:
            1. 如果 scene 中有 AI 生成的 subtitles 数据（来自 generate_subtitles_task），优先使用
            2. 否则，使用旧逻辑从 subtitle_text/narration 生成
        """
        subtitle_layers = []

        # 【新增】优先使用 AI 生成的字幕数据
        ai_subtitles = scene.get('subtitles', [])
        if ai_subtitles and isinstance(ai_subtitles, list):
            logger.info(f"使用 AI 生成的字幕数据: {len(ai_subtitles)} 条字幕")

            for subtitle in ai_subtitles:
                # AI 生成的字幕格式:
                # {
                #   "text": "字幕文本",
                #   "start_time": 0.0,
                #   "duration": 3.0,
                #   "position": "bottom",
                #   "style": {
                #       "font_color": "white",
                #       "font_size": "medium",
                #       "background": true,
                #       "background_color": "black@0.5",
                #       "bold": false
                #   }
                # }

                text = subtitle.get('text', '')
                if not text:
                    continue

                # 构建字幕层
                layer = {
                    "text": text,
                    "position": subtitle.get('position', 'bottom'),
                    "display_start": subtitle.get('start_time', 0.0),
                    "display_duration": subtitle.get('duration', 0.0),  # 0.0 表示自动计算
                    "style": "default"
                }

                # 应用 AI 生成的样式
                ai_style = subtitle.get('style', {})
                if ai_style:
                    if 'font_color' in ai_style:
                        layer["font_color"] = ai_style['font_color']
                    if 'font_size' in ai_style:
                        layer["font_size"] = ai_style['font_size']
                    if 'background' in ai_style and ai_style['background']:
                        layer["background"] = True
                        layer["background_color"] = ai_style.get('background_color', 'black@0.5')
                    if 'bold' in ai_style:
                        layer["bold"] = ai_style['bold']

                subtitle_layers.append(layer)

            return subtitle_layers

        # 【降级】如果没有 AI 生成的字幕，使用旧逻辑（从用户要求解析 + subtitle_text/narration）
        logger.info("未找到 AI 生成的字幕，使用降级逻辑")

        if style_config["subtitle_mode"] == "multi_layer":
            # 多层字幕模式
            for layer_template in style_config["layers"]:
                layer_type = layer_template["layer_type"]

                # 根据层类型选择文本
                if layer_type == "title":
                    # 标题层：使用场景的key_point或简短描述
                    text = scene.get('key_point', '')
                    if not text:
                        text = scene.get('subtitle_text', '')[:15] if scene.get('subtitle_text') else ''

                elif layer_type == "dialogue":
                    # 对话层：使用subtitle_text
                    text = scene.get('subtitle_text', '')
                    if not text:
                        narration = scene.get('narration', '')
                        if narration:
                            text = narration.strip()[:30]

                elif layer_type == "speaker":
                    # 说话人层：使用narration的片段
                    narration = scene.get('narration', '')
                    if narration:
                        # 分句处理
                        sentences = re.split(r'[，。！？,.!?]', narration)
                        text = sentences[0].strip() if sentences else ''
                    else:
                        text = ''

                else:
                    text = scene.get('subtitle_text', '')

                if text:
                    layer = layer_template.copy()
                    layer["text"] = text
                    layer["display_start"] = 0.0
                    layer["display_duration"] = 0.0  # 自动计算
                    subtitle_layers.append(layer)

        else:
            # 单层字幕模式
            text = scene.get('subtitle_text', '')
            if not text:
                narration = scene.get('narration', '')
                if narration:
                    text = narration.strip()[:30]

            if text:
                layer = {
                    "text": text,
                    "style": style_config.get("default_style", "default"),
                    "position": style_config.get("default_position", "bottom"),
                    "display_start": 0.0,
                    "display_duration": 0.0,
                }

                # 应用自定义颜色
                if "default_color" in style_config:
                    layer["font_color"] = style_config["default_color"]

                subtitle_layers.append(layer)

        return subtitle_layers

    @classmethod
    def merge_user_style_to_scene(
        cls,
        user_requirements: str,
        storyboard: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        完整的字幕样式解析和配置生成

        Args:
            user_requirements: 用户要求
            storyboard: 分镜脚本

        Returns:
            完整的字幕配置
        """
        style_config = cls.parse_subtitle_style_from_requirements(user_requirements, storyboard)

        logger.info("=" * 60)
        logger.info("📝 字幕样式配置:")
        logger.info(f"   模式: {style_config['subtitle_mode']}")
        logger.info(f"   使用灵活字幕工具: {style_config['use_flexible_subtitle']}")
        if style_config["layers"]:
            logger.info(f"   字幕层数: {len(style_config['layers'])}")
            for i, layer in enumerate(style_config["layers"]):
                logger.info(f"   - 第{i+1}层: {layer['layer_type']} ({layer.get('position', 'auto')})")
        logger.info("=" * 60)

        return style_config
