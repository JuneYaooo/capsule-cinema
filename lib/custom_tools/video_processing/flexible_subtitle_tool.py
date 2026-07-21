#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵活字幕处理工具 - 支持多层字幕、自定义样式、动态位置
"""

from crewai.tools import BaseTool
from typing import List, Dict, Any, Tuple, Optional, ClassVar, Union
import subprocess
import json
import re
from pathlib import Path
from src.logger import get_logger
from src.utils.font_utils import ffmpeg_fontfile_option, get_default_font

logger = get_logger('flexible_subtitle_tool')


class FlexibleSubtitleProcessor(BaseTool):
    """灵活字幕处理器 - 支持多层字幕和自定义样式"""

    name: str = "FlexibleSubtitleProcessor"
    description: str = "为视频添加灵活的多层字幕（支持自定义样式、颜色、位置、多层叠加）"

    # 预设字幕样式 (电影字幕风格为默认)
    PRESET_STYLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        "default": {  # 电影字幕风格 - 优雅简洁
            "position": "bottom",
            "font_color": "#FFFEF0",  # 柔和米白色
            "border_color": "#1A1A1A",  # 深灰色描边
            "border_width": 2,  # 细描边
            "background_color": "",  # 无背景，干净
            "font_size_ratio": 0.042,  # 适中字号
            "max_chars_per_line": 18,
        },
        "cinema": {  # 经典电影字幕
            "position": "bottom",
            "font_color": "#FFFEF0",
            "border_color": "#1A1A1A",
            "border_width": 2,
            "background_color": "",
            "font_size_ratio": 0.040,
            "max_chars_per_line": 20,
        },
        "title": {  # 标题字幕
            "position": "top",
            "font_color": "#FFFEF0",
            "border_color": "#1A1A1A",
            "border_width": 2,
            "background_color": "",
            "font_size_ratio": 0.045,
            "max_chars_per_line": 22,
        },
        "dialogue": {  # 对话字幕
            "position": "bottom",
            "font_color": "#FFFEF0",
            "border_color": "#1A1A1A",
            "border_width": 2,
            "background_color": "",
            "font_size_ratio": 0.038,
            "max_chars_per_line": 16,
        },
        "speaker": {  # 说话人字幕
            "position": "custom",
            "font_color": "#FFE4B5",  # 淡金色，区分说话人
            "border_color": "#1A1A1A",
            "border_width": 2,
            "background_color": "",
            "font_size_ratio": 0.032,
            "max_chars_per_line": 14,
        },
        "narration": {  # 旁白字幕
            "position": "center",
            "font_color": "#E8E8E8",  # 浅灰白色
            "border_color": "#1A1A1A",
            "border_width": 2,
            "background_color": "",
            "font_size_ratio": 0.040,
            "max_chars_per_line": 20,
        },
    }

    # 字幕布局配置 (电影字幕风格)
    LAYOUT_CONFIG: ClassVar[Dict[str, Any]] = {
        "portrait": {
            "top_margin_ratio": 0.12,
            "bottom_margin_ratio": 0.13,  # 底部边距，字幕往上调
            "center_offset_ratio": 0.0,
            "line_spacing_ratio": 1.2,  # 紧凑行间距
        },
        "landscape": {
            "top_margin_ratio": 0.10,
            "bottom_margin_ratio": 0.06,  # 更贴近底部
            "center_offset_ratio": 0.0,
            "line_spacing_ratio": 1.15,  # 紧凑行间距
        }
    }

    def _run(
        self,
        video_path: str,
        subtitles: Union[str, List[Dict[str, Any]]],
        output_path: str,
        language: str = "zh",
        custom_font_path: str = None,
    ) -> Dict[str, Any]:
        """
        为视频添加灵活的多层字幕

        Args:
            video_path: 输入视频路径
            subtitles: 字幕配置
                - 如果是字符串: 使用默认样式的单层字幕
                - 如果是列表: 多层字幕配置，每个元素包含:
                  {
                    "text": "字幕文本",
                    "style": "default/title/dialogue/speaker/narration",
                    "position": "top/bottom/center/custom",  # 可选，覆盖style中的position
                    "font_color": "white",  # 可选，覆盖style中的颜色
                    "custom_position": {"x": "w/2", "y": "100"},  # position="custom"时使用
                    "display_start": 0.0,
                    "display_duration": 0.0,  # 0=自动计算
                  }
            output_path: 输出视频路径
            language: 语言 (zh/en等)
            custom_font_path: 自定义字体路径

        Returns:
            处理结果字典
        """
        try:
            # 1. 规范化字幕输入
            if isinstance(subtitles, str):
                subtitle_layers = [{
                    "text": subtitles,
                    "style": "default",
                    "display_start": 0.0,
                    "display_duration": 0.0,
                }]
            else:
                subtitle_layers = subtitles

            if not subtitle_layers:
                logger.info("字幕配置为空，跳过处理")
                return {
                    'status': 'success',
                    'output_path': video_path,
                    'message': '字幕配置为空'
                }

            # 2. 获取视频信息
            width, height, duration, fps = self._get_video_info(video_path)
            logger.info(f"视频信息: {width}x{height}, {duration:.2f}秒, {fps:.2f}fps")

            # 3. 判断屏幕方向
            aspect_ratio = width / height
            layout_type = "portrait" if aspect_ratio < 1.0 else "landscape"
            layout_config = self.LAYOUT_CONFIG[layout_type]

            logger.info(f"屏幕方向: {layout_type} (宽高比: {aspect_ratio:.2f})")
            logger.info(f"准备添加 {len(subtitle_layers)} 层字幕")

            # 4. 为每层字幕生成滤镜
            all_drawtext_filters = []

            for layer_idx, layer in enumerate(subtitle_layers):
                text = layer.get('text', '').strip()
                if not text:
                    logger.warning(f"第{layer_idx+1}层字幕文本为空，跳过")
                    continue

                # 获取样式配置
                style_name = layer.get('style', 'default')
                style_config = self._get_style_config(style_name, layer)

                # 计算字体大小
                font_size = self._calculate_font_size(width, height, style_config)

                # 计算描边宽度
                border_width = style_config.get('border_width', 0)
                if border_width == 0:
                    border_width = max(2, int(font_size * 0.08))

                # 智能换行
                max_chars = style_config.get('max_chars_per_line', 20)
                lines = self._smart_wrap_text(text, max_chars, language)

                # 计算显示时长
                display_start = layer.get('display_start', 0.0)
                display_duration = layer.get('display_duration', 0.0)
                if display_duration == 0:
                    display_duration = self._calculate_display_duration(lines, language)

                display_end = display_start + display_duration

                # 计算位置
                position = layer.get('position', style_config.get('position', 'bottom'))
                custom_position = layer.get('custom_position')

                if position == 'custom' and custom_position:
                    # 使用自定义位置
                    y_positions = self._calculate_custom_positions(
                        lines, custom_position, font_size, layout_config
                    )
                else:
                    # 使用预设位置
                    line_height = int(font_size * layout_config["line_spacing_ratio"])
                    y_positions = self._calculate_positions(
                        lines, position, width, height, font_size, line_height, layout_config
                    )

                # 生成drawtext滤镜
                for i, (line, y_pos) in enumerate(zip(lines, y_positions)):
                    if not line.strip():
                        continue

                    filter_str = self._build_drawtext_filter(
                        text=line,
                        x_pos=layer.get('custom_position', {}).get('x', '(w-text_w)/2'),
                        y_pos=y_pos,
                        font_size=font_size,
                        font_color=layer.get('font_color', style_config['font_color']),
                        border_color=style_config['border_color'],
                        border_width=border_width,
                        background_color=style_config.get('background_color', ''),
                        display_start=display_start,
                        display_end=display_end,
                        fade_in=layer.get('fade_in', 0.3),
                        fade_out=layer.get('fade_out', 0.5),
                        custom_font_path=custom_font_path
                    )

                    if filter_str:
                        all_drawtext_filters.append(filter_str)

                logger.info(f"  ✅ 第{layer_idx+1}层 ({style_name}): \"{text[:15]}...\" "
                           f"| {len(lines)}行 | {display_duration:.1f}秒 | {position}")

            if not all_drawtext_filters:
                logger.warning("未生成任何字幕滤镜")
                return {
                    'status': 'success',
                    'output_path': video_path,
                    'message': '无有效字幕'
                }

            # 5. 执行ffmpeg命令
            vf_param = ','.join(all_drawtext_filters)

            cmd = [
                'ffmpeg', '-i', video_path,
                '-vf', vf_param,
                '-c:a', 'copy',
                '-y', output_path
            ]

            logger.info(f"执行ffmpeg命令...")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)

            logger.info(f"✅ 字幕添加成功: {output_path}")

            return {
                'status': 'success',
                'output_path': output_path,
                'video_info': {
                    'width': width,
                    'height': height,
                    'aspect_ratio': aspect_ratio,
                    'layout_type': layout_type
                },
                'subtitle_info': {
                    'layers': len(subtitle_layers),
                    'total_filters': len(all_drawtext_filters),
                }
            }

        except subprocess.CalledProcessError as e:
            error_msg = f"ffmpeg执行失败: {e.stderr if e.stderr else str(e)}"
            logger.error(error_msg)
            return {
                'status': 'failed',
                'error': error_msg,
                'output_path': video_path
            }
        except Exception as e:
            error_msg = f"字幕处理异常: {str(e)}"
            logger.error(error_msg)
            return {
                'status': 'failed',
                'error': error_msg,
                'output_path': video_path
            }

    def _get_style_config(self, style_name: str, layer: Dict[str, Any]) -> Dict[str, Any]:
        """获取样式配置，支持从用户输入覆盖"""
        # 从预设样式开始
        if style_name in self.PRESET_STYLES:
            style = self.PRESET_STYLES[style_name].copy()
        else:
            logger.warning(f"未知样式 '{style_name}'，使用默认样式")
            style = self.PRESET_STYLES['default'].copy()

        # 用户自定义覆盖
        for key in ['font_color', 'border_color', 'border_width', 'background_color',
                    'font_size_ratio', 'max_chars_per_line']:
            if key in layer:
                style[key] = layer[key]

        return style

    def _parse_user_subtitle_requirements(self, user_requirements: str) -> List[Dict[str, Any]]:
        """
        从用户要求中解析字幕样式配置

        示例:
        - "顶部蓝色字幕" -> title样式
        - "底部对话字幕" -> dialogue样式
        - "说话人附近的字幕" -> speaker样式
        """
        subtitle_layers = []

        # 检测是否需要顶部标题字幕
        if re.search(r'(顶部|上方|头部).*(字幕|标题)', user_requirements, re.IGNORECASE):
            subtitle_layers.append({
                "layer_type": "title",
                "style": "title",
                "position": "top",
            })

        # 检测是否需要底部对话字幕
        if re.search(r'(底部|下方|底下).*(对话|字幕)', user_requirements, re.IGNORECASE):
            subtitle_layers.append({
                "layer_type": "dialogue",
                "style": "dialogue",
                "position": "bottom",
            })

        # 检测是否需要说话人字幕
        if re.search(r'(说话人|人物|角色).*(附近|旁边|周围).*(字幕)', user_requirements, re.IGNORECASE):
            subtitle_layers.append({
                "layer_type": "speaker",
                "style": "speaker",
                "position": "custom",
            })

        # 检测颜色要求
        color_patterns = {
            '蓝色': '#4A9EFF',
            '红色': '#FF4444',
            '黄色': '#FFFF00',
            '绿色': '#44FF44',
            '白色': 'white',
            '金色': '#FFD700',
        }

        for color_name, color_code in color_patterns.items():
            if color_name in user_requirements:
                # 如果指定了颜色，应用到第一层字幕
                if subtitle_layers:
                    subtitle_layers[0]['font_color'] = color_code

        # 如果没有检测到任何配置，返回默认配置
        if not subtitle_layers:
            subtitle_layers.append({
                "layer_type": "default",
                "style": "default",
                "position": "bottom",
            })

        return subtitle_layers

    def _get_video_info(self, video_path: str) -> Tuple[int, int, float, float]:
        """获取视频信息"""
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration,r_frame_rate',
            '-of', 'json',
            video_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        stream = data['streams'][0]

        width = int(stream['width'])
        height = int(stream['height'])
        duration = float(stream.get('duration', 5.0))

        fps_str = stream['r_frame_rate']
        fps_num, fps_den = map(int, fps_str.split('/'))
        fps = fps_num / fps_den if fps_den != 0 else 30.0

        return width, height, duration, fps

    def _calculate_font_size(
        self,
        width: int,
        height: int,
        style_config: Dict[str, Any]
    ) -> int:
        """智能计算字体大小"""
        base_size = int(width * style_config.get("font_size_ratio", 0.045))
        font_size = max(24, min(80, base_size))
        return font_size

    def _smart_wrap_text(
        self,
        text: str,
        max_chars: int,
        language: str = "zh"
    ) -> List[str]:
        """
        智能文本换行

        对于英文，因为字符宽度通常是中文的一半，会自动放宽字符限制1.8倍
        确保英文单词不会被截断
        """
        text = text.strip()

        # 对于英文，因为字符宽度通常是中文的一半，所以放宽字符限制
        # 为了保证视觉宽度一致，英文的max_chars应该是中文的1.8倍
        effective_max_chars = max_chars
        if language not in ["zh", "zh-CN", "zh-TW"]:
            effective_max_chars = int(max_chars * 1.8)

        if len(text) <= effective_max_chars:
            return [text]

        lines = []
        current_line = ""
        punctuations = "，。！？；：、,.!?;:"

        if language == "zh" or language == "zh-CN":
            for i, char in enumerate(text):
                current_line += char

                should_break = False
                if len(current_line) >= max_chars:
                    if char in punctuations:
                        should_break = True
                    elif i + 3 < len(text):
                        next_chars = text[i+1:i+4]
                        if not any(p in next_chars for p in punctuations):
                            should_break = True
                    else:
                        should_break = True

                if should_break:
                    lines.append(current_line)
                    current_line = ""

            if current_line:
                lines.append(current_line)
        else:
            # 英文换行逻辑: 按单词边界换行，避免截断单词
            # 使用effective_max_chars（已放宽1.8倍）
            words = text.split()
            current_line = ""

            for word in words:
                # 计算添加这个单词后的行长度
                if current_line:
                    # 如果当前行已有内容，需要加空格再加单词
                    test_line = current_line + " " + word
                else:
                    # 如果当前行为空，直接是这个单词
                    test_line = word

                # 判断是否超过最大字符数（使用放宽后的限制）
                if len(test_line) <= effective_max_chars:
                    # 可以放入当前行
                    current_line = test_line
                else:
                    # 超过最大字符数
                    if current_line:
                        # 当前行已有内容，先保存当前行
                        lines.append(current_line)
                        # 单词放到新行（即使单词本身超长，也保持完整不截断）
                        current_line = word
                    else:
                        # 当前行为空，说明单词本身就超长
                        # 保持完整（不截断），即使超过effective_max_chars
                        current_line = word

            # 添加最后一行（如果还有剩余内容）
            if current_line:
                lines.append(current_line)

        return lines if lines else [text[:effective_max_chars]]

    def _calculate_display_duration(
        self,
        lines: List[str],
        language: str = "zh"
    ) -> float:
        """智能计算显示时长"""
        total_chars = sum(len(line) for line in lines)

        if language == "zh" or language == "zh-CN":
            base_duration = total_chars / 4.5
        else:
            total_words = sum(len(line.split()) for line in lines)
            base_duration = total_words / 3.5

        line_penalty = (len(lines) - 1) * 0.5
        duration = base_duration + line_penalty
        duration = max(1.5, min(5.0, duration))

        return round(duration, 2)

    def _calculate_positions(
        self,
        lines: List[str],
        position: str,
        width: int,
        height: int,
        font_size: int,
        line_height: int,
        config: Dict[str, Any]
    ) -> List[int]:
        """计算每行字幕的Y坐标"""
        total_height = line_height * len(lines)

        if position == "top":
            start_y = int(height * config["top_margin_ratio"])
        elif position == "center":
            start_y = int((height - total_height) / 2)
        else:  # bottom
            start_y = int(height * (1 - config["bottom_margin_ratio"]) - total_height)

        y_positions = []
        for i in range(len(lines)):
            y = start_y + (i * line_height)
            y_positions.append(y)

        return y_positions

    def _calculate_custom_positions(
        self,
        lines: List[str],
        custom_position: Dict[str, Any],
        font_size: int,
        config: Dict[str, Any]
    ) -> List[Union[str, int]]:
        """计算自定义位置（支持动态表达式）"""
        base_y = custom_position.get('y', 'h/2')
        line_height = int(font_size * config["line_spacing_ratio"])

        y_positions = []
        for i in range(len(lines)):
            if isinstance(base_y, str):
                # 支持表达式，如 "h/2", "h*0.3"
                y_positions.append(base_y if i == 0 else f"{base_y}+{i*line_height}")
            else:
                y_positions.append(int(base_y) + i * line_height)

        return y_positions

    def _build_drawtext_filter(
        self,
        text: str,
        x_pos: Union[str, int],
        y_pos: Union[str, int],
        font_size: int,
        font_color: str,
        border_color: str,
        border_width: int,
        background_color: str,
        display_start: float,
        display_end: float,
        fade_in: float,
        fade_out: float,
        custom_font_path: Optional[str] = None
    ) -> str:
        """构建单行字幕的drawtext滤镜"""
        if not text.strip():
            return ""

        escaped_text = self._escape_text(text)
        if custom_font_path and not Path(custom_font_path).exists():
            logger.warning(f"字体文件不存在: {custom_font_path}，将 fallback 到默认中文字体")
            custom_font_path = None
        if not custom_font_path:
            try:
                custom_font_path = get_default_font()
            except FileNotFoundError as exc:
                logger.warning(str(exc))
        font_param = ffmpeg_fontfile_option(custom_font_path)

        # 背景色处理
        box_param = ""
        if background_color:
            box_param = f":box=1:boxcolor={background_color}:boxborderw=10"

        # 淡入淡出
        fade_end = display_start + fade_in
        fade_start = display_end - fade_out

        alpha_expr = (
            f"'if(lt(t,{display_start}),0,"
            f"if(lt(t,{fade_end}),(t-{display_start})/{fade_in},"
            f"if(lt(t,{fade_start}),1,"
            f"if(lt(t,{display_end}),1-(t-{fade_start})/{fade_out},0))))'"
        )

        # X位置处理
        if isinstance(x_pos, str):
            x_param = x_pos
        else:
            x_param = str(x_pos)

        # Y位置处理
        if isinstance(y_pos, str):
            y_param = y_pos
        else:
            y_param = str(y_pos)

        filter_str = (
            f"drawtext=text='{escaped_text}'"
            f":fontcolor={font_color}"
            f":fontsize={font_size}"
            f"{font_param}"
            f":x={x_param}"
            f":y={y_param}"
            f":bordercolor={border_color}"
            f":borderw={border_width}"
            f"{box_param}"
            f":enable='between(t,{display_start},{display_end})'"
            f":alpha={alpha_expr}"
        )

        return filter_str

    def _escape_text(self, text: str) -> str:
        """转义ffmpeg文本中的特殊字符"""
        text = text.replace("\\", "\\\\")
        text = text.replace("'", "'\\''")
        text = text.replace(":", "\\:")
        text = text.replace("[", "\\[")
        text = text.replace("]", "\\]")
        text = text.replace("%", "\\%")
        return text
