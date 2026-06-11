#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自适应字幕处理工具
支持竖屏/横屏自动适配、智能换行、动态字体大小
"""

from crewai.tools import BaseTool
from typing import List, Dict, Any, Tuple, Optional, ClassVar
import subprocess
import json
from pathlib import Path
from src.logger import get_logger

logger = get_logger('adaptive_subtitle_tool')


class AdaptiveSubtitleProcessor(BaseTool):
    """自适应字幕处理器 - 完全自动化"""

    name: str = "AdaptiveSubtitleProcessor"
    description: str = "为视频添加完全自适应的字幕（自动适配竖屏/横屏、智能换行、动态字体大小）"

    # 字幕布局配置 (专业短视频字幕风格)
    LAYOUT_CONFIG: ClassVar[Dict[str, Any]] = {
        "portrait": {  # 竖屏 (9:16, 3:4等)
            "font_size_ratio": 0.05,       # 字体大小适中
            "max_chars_per_line": 11,      # 每行字符数，保证不会太挤
            "line_spacing_ratio": 1.5,     # 行间距宽松，更易读
            "bottom_margin_ratio": 0.20,   # 底部边距，留出呼吸空间
            "top_margin_ratio": 0.12,      # 顶部边距
            "side_padding_ratio": 0.05,    # 左右留白
            "max_lines": 2,                # 最多2行
        },
        "landscape": {  # 横屏 (16:9, 16:10等)
            "font_size_ratio": 0.045,      # 横屏字体
            "max_chars_per_line": 20,      # 横屏每行字符
            "line_spacing_ratio": 1.45,    # 行间距
            "bottom_margin_ratio": 0.12,   # 底部边距
            "top_margin_ratio": 0.10,      # 顶部边距
            "side_padding_ratio": 0.08,    # 左右留白
            "max_lines": 2,                # 最多2行
        }
    }

    def _run(
        self,
        video_path: str,
        subtitle_text: str,
        output_path: str,
        position: str = "bottom",  # top/bottom/center
        language: str = "zh",
        font_color: str = "white",
        border_color: str = "black",
        border_width: int = 0,  # 0表示自动计算
        background_color: str = "",  # 空字符串表示无背景
        display_start: float = 0.0,
        display_duration: float = 0.0,  # 0表示自动计算
        fade_in: float = 0.3,
        fade_out: float = 0.5,
        custom_font_path: str = None,
        force_single_line: bool = False  # 强制单行显示
    ) -> Dict[str, Any]:
        """
        为视频添加自适应字幕

        Args:
            video_path: 输入视频路径
            subtitle_text: 字幕文本
            output_path: 输出视频路径
            position: 位置 (top/bottom/center)
            language: 语言 (zh/en等)
            font_color: 字体颜色
            border_color: 描边颜色
            border_width: 描边宽度 (0=自动)
            background_color: 背景色 (空=无背景)
            display_start: 显示开始时间(秒)
            display_duration: 显示时长(秒, 0=自动计算)
            fade_in: 淡入时长(秒)
            fade_out: 淡出时长(秒)
            custom_font_path: 自定义字体路径
            force_single_line: 强制单行显示

        Returns:
            处理结果字典
        """
        try:
            if not subtitle_text or subtitle_text.strip() == "":
                logger.info("字幕文本为空，跳过处理")
                return {
                    'status': 'success',
                    'output_path': video_path,
                    'message': '字幕文本为空'
                }

            # 1. 获取视频信息
            width, height, duration, fps = self._get_video_info(video_path)
            logger.info(f"视频信息: {width}x{height}, {duration:.2f}秒, {fps:.2f}fps")

            # 2. 判断屏幕方向
            aspect_ratio = width / height
            layout_type = "portrait" if aspect_ratio < 1.0 else "landscape"
            config = self.LAYOUT_CONFIG[layout_type]

            logger.info(f"屏幕方向: {layout_type} (宽高比: {aspect_ratio:.2f})")

            # 3. 计算字体大小（自动）
            font_size = self._calculate_font_size(width, height, config)
            logger.info(f"计算字体大小: {font_size}px")

            # 4. 计算描边宽度（自动）
            if border_width == 0:
                border_width = max(2, int(font_size * 0.08))  # 字体大小的8%

            # 5. 智能换行
            if force_single_line:
                lines = [subtitle_text]
            else:
                lines = self._smart_wrap_text(
                    text=subtitle_text,
                    max_chars=config["max_chars_per_line"],
                    max_lines=config["max_lines"],
                    language=language
                )

            logger.info(f"文本换行: {len(lines)}行, 每行最多{config['max_chars_per_line']}字")
            for i, line in enumerate(lines, 1):
                logger.info(f"  第{i}行: {line} ({len(line)}字)")

            # 6. 计算显示时长（自动）
            if display_duration == 0:
                display_duration = self._calculate_display_duration(
                    lines=lines,
                    language=language
                )

            display_end = display_start + display_duration
            logger.info(f"显示时长: {display_duration:.2f}秒 (第{display_start:.2f}秒到第{display_end:.2f}秒)")

            # 7. 计算字幕位置
            line_height = int(font_size * config["line_spacing_ratio"])
            y_positions = self._calculate_positions(
                lines=lines,
                position=position,
                width=width,
                height=height,
                font_size=font_size,
                line_height=line_height,
                config=config
            )

            logger.info(f"字幕位置: {position}, Y坐标: {y_positions}")

            # 8. 构建ffmpeg滤镜
            drawtext_filters = []
            for i, (line, y_pos) in enumerate(zip(lines, y_positions)):
                if not line.strip():
                    continue

                filter_str = self._build_drawtext_filter(
                    text=line,
                    y_pos=y_pos,
                    font_size=font_size,
                    font_color=font_color,
                    border_color=border_color,
                    border_width=border_width,
                    background_color=background_color,
                    display_start=display_start,
                    display_end=display_end,
                    fade_in=fade_in,
                    fade_out=fade_out,
                    custom_font_path=custom_font_path
                )

                if filter_str:
                    drawtext_filters.append(filter_str)

            if not drawtext_filters:
                logger.warning("未生成任何字幕滤镜")
                return {
                    'status': 'success',
                    'output_path': video_path,
                    'message': '无有效字幕'
                }

            # 9. 执行ffmpeg命令
            vf_param = ','.join(drawtext_filters)

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
                    'lines': len(lines),
                    'font_size': font_size,
                    'border_width': border_width,
                    'display_duration': display_duration,
                    'position': position
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
        config: Dict[str, Any]
    ) -> int:
        """
        智能计算字体大小

        规则:
        - 竖屏: 基于宽度计算 (宽度 * 6.5%)
        - 横屏: 基于宽度计算 (宽度 * 4.5%)
        - 最小字体: 24px
        - 最大字体: 80px
        """
        base_size = int(width * config["font_size_ratio"])

        # 限制字体大小范围
        font_size = max(24, min(80, base_size))

        return font_size

    def _smart_wrap_text(
        self,
        text: str,
        max_chars: int,
        max_lines: int,
        language: str = "zh"
    ) -> List[str]:
        """
        智能文本换行

        规则:
        1. 优先在标点符号处换行
        2. 如果没有标点,按字数均匀分配
        3. 英文按单词边界换行（不截断单词）
        4. 控制最大行数,超出部分截断并加省略号

        Args:
            text: 原始文本
            max_chars: 每行最大字符数（对于英文会自动放宽1.8倍）
            max_lines: 最大行数
            language: 语言类型

        Returns:
            换行后的文本列表
        """
        text = text.strip()

        # 对于英文，因为字符宽度通常是中文的一半，所以放宽字符限制
        # 英文平均单词长度约5个字符，所以实际显示宽度约为中文的0.6倍
        # 为了保证视觉宽度一致，英文的max_chars应该是中文的1.8倍
        effective_max_chars = max_chars
        if language not in ["zh", "zh-CN", "zh-TW"]:
            effective_max_chars = int(max_chars * 1.8)

        # 如果文本很短,不需要换行
        if len(text) <= effective_max_chars:
            return [text]

        lines = []
        current_line = ""

        # 中文标点符号
        punctuations = "，。！？；：、,.!?;:"

        if language == "zh" or language == "zh-CN":
            # 中文换行逻辑: 优先在标点处换行
            for i, char in enumerate(text):
                current_line += char

                # 检查是否需要换行
                should_break = False

                if len(current_line) >= max_chars:
                    # 如果当前字符是标点,直接换行
                    if char in punctuations:
                        should_break = True
                    # 检查后面3个字符内是否有标点
                    elif i + 3 < len(text):
                        next_chars = text[i+1:i+4]
                        # 如果后面没有标点,直接换行
                        if not any(p in next_chars for p in punctuations):
                            should_break = True
                    else:
                        should_break = True

                if should_break:
                    lines.append(current_line)
                    current_line = ""

                    # 如果已经达到最大行数,停止处理
                    if len(lines) >= max_lines - 1:
                        # 把剩余文本加到最后一行
                        remaining = text[i+1:]
                        if remaining:
                            # 如果剩余文本太长,截断并加省略号
                            if len(remaining) > max_chars:
                                remaining = remaining[:max_chars-1] + "..."
                            lines.append(remaining)
                        elif current_line:
                            lines.append(current_line)
                        break

            # 添加最后一行
            if current_line and len(lines) < max_lines:
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

                        if len(lines) >= max_lines:
                            # 已达到最大行数，停止处理
                            break
                    else:
                        # 当前行为空，说明单词本身就超长
                        # 保持完整（不截断），即使超过effective_max_chars
                        current_line = word

            # 添加最后一行（如果还有剩余内容且未达到最大行数）
            if current_line and len(lines) < max_lines:
                lines.append(current_line)

        # 如果没有生成任何行,返回原文本(截断)
        if not lines:
            lines = [text[:effective_max_chars]]

        # 限制最大行数
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            if lines[-1] and not lines[-1].endswith("..."):
                lines[-1] = lines[-1][:-3] + "..."

        return lines

    def _calculate_display_duration(
        self,
        lines: List[str],
        language: str = "zh"
    ) -> float:
        """
        智能计算显示时长

        规则:
        - 中文: 4-5字/秒
        - 英文: 3-4个单词/秒
        - 最短: 1.5秒
        - 每增加一行: +0.8秒

        Args:
            lines: 文本行列表
            language: 语言类型

        Returns:
            显示时长(秒)
        """
        total_chars = sum(len(line) for line in lines)

        if language == "zh" or language == "zh-CN":
            # 中文: 4.5字/秒
            base_duration = total_chars / 4.5
        else:
            # 英文: 按单词数计算
            total_words = sum(len(line.split()) for line in lines)
            base_duration = total_words / 3.5

        # 多行阅读需要更多时间
        line_penalty = (len(lines) - 1) * 0.5

        # 计算最终时长
        duration = base_duration + line_penalty

        # 限制范围: 1.5秒 ~ 5秒
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
        """
        计算每行字幕的Y坐标

        Args:
            lines: 文本行列表
            position: 位置 (top/bottom/center)
            width: 视频宽度
            height: 视频高度
            font_size: 字体大小
            line_height: 行高
            config: 布局配置

        Returns:
            每行的Y坐标列表
        """
        total_height = line_height * len(lines)

        if position == "top":
            # 顶部对齐
            start_y = int(height * config["top_margin_ratio"])
        elif position == "center":
            # 居中对齐
            start_y = int((height - total_height) / 2)
        else:  # bottom
            # 底部对齐
            start_y = int(height * (1 - config["bottom_margin_ratio"]) - total_height)

        # 计算每行的Y坐标
        y_positions = []
        for i in range(len(lines)):
            y = start_y + (i * line_height)
            y_positions.append(y)

        return y_positions

    def _build_drawtext_filter(
        self,
        text: str,
        y_pos: int,
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
        """
        构建单行字幕的drawtext滤镜（带阴影效果）

        Args:
            text: 字幕文本
            y_pos: Y坐标
            font_size: 字体大小
            font_color: 字体颜色
            border_color: 描边颜色
            border_width: 描边宽度
            background_color: 背景色
            display_start: 显示开始时间
            display_end: 显示结束时间
            fade_in: 淡入时长
            fade_out: 淡出时长
            custom_font_path: 自定义字体路径

        Returns:
            drawtext滤镜字符串
        """
        if not text.strip():
            return ""

        # 转义文本
        escaped_text = self._escape_text(text)

        # 字体路径（验证文件存在，不存在则 fallback 到默认中文字体）
        if custom_font_path and not Path(custom_font_path).exists():
            logger.warning(f"字体文件不存在: {custom_font_path}，将 fallback 到默认中文字体")
            custom_font_path = None
        if not custom_font_path:
            from src.utils.font_utils import DEFAULT_FONT_PATH
            if Path(DEFAULT_FONT_PATH).exists():
                custom_font_path = DEFAULT_FONT_PATH
        font_param = f":fontfile='{custom_font_path}'" if custom_font_path else ""

        # 背景色(可选)
        box_param = ""
        if background_color:
            box_param = f":box=1:boxcolor={background_color}:boxborderw=10"

        # 计算淡入淡出的alpha值
        fade_end = display_start + fade_in
        fade_start = display_end - fade_out

        # alpha表达式: 淡入 → 完全显示 → 淡出
        alpha_expr = (
            f"'if(lt(t,{display_start}),0,"  # 开始前: 透明
            f"if(lt(t,{fade_end}),(t-{display_start})/{fade_in},"  # 淡入阶段
            f"if(lt(t,{fade_start}),1,"  # 完全显示阶段
            f"if(lt(t,{display_end}),1-(t-{fade_start})/{fade_out},0))))'"  # 淡出阶段
        )

        # 阴影参数 - 让字幕更有层次感
        shadow_x = max(2, int(font_size * 0.04))  # 阴影X偏移
        shadow_y = max(2, int(font_size * 0.04))  # 阴影Y偏移
        shadow_param = f":shadowcolor=black@0.6:shadowx={shadow_x}:shadowy={shadow_y}"

        # 构建完整的drawtext滤镜
        filter_str = (
            f"drawtext=text='{escaped_text}'"
            f":fontcolor={font_color}"
            f":fontsize={font_size}"
            f"{font_param}"
            f":x=(w-text_w)/2"  # 水平居中
            f":y={y_pos}"
            f":bordercolor={border_color}"
            f":borderw={border_width}"
            f"{shadow_param}"
            f"{box_param}"
            f":enable='between(t,{display_start},{display_end})'"
            f":alpha={alpha_expr}"
        )

        return filter_str

    def _escape_text(self, text: str) -> str:
        """转义ffmpeg文本中的特殊字符"""
        # 转义顺序很重要!
        text = text.replace("\\", "\\\\")  # 反斜杠
        text = text.replace("'", "'\\''")  # 单引号
        text = text.replace(":", "\\:")    # 冒号
        text = text.replace("[", "\\[")    # 左方括号
        text = text.replace("]", "\\]")    # 右方括号
        text = text.replace("%", "\\%")    # 百分号
        return text
