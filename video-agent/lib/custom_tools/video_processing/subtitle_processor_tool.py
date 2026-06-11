#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕处理工具集
为视频添加各种样式的字幕、标题，以及视频拼接和背景音乐添加等功能
"""

import os
import subprocess
import platform
import tempfile
import re
from typing import Any, Dict, List, Tuple, Type, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from src.logger import get_logger

logger = get_logger("subtitle_processor")


class SubtitleProcessor:
    """字幕处理器核心类"""
    
    def __init__(self, custom_font_path: str = None, aspect_ratio: str = "16:9"):
        """
        初始化字幕处理器
        
        Args:
            custom_font_path: 自定义字体路径
            aspect_ratio: 视频宽高比，支持 "16:9" (横屏) 或 "9:16" (竖屏)
        """
        logger.info("📝 初始化字幕处理器")
        
        # 检查ffmpeg是否安装
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            logger.info("✅ FFmpeg 已安装")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("❌ FFmpeg 未安装或不在PATH中，请先安装FFmpeg")
        
        # 设置宽高比
        self.aspect_ratio = aspect_ratio
        
        # 使用自定义字体或检测系统字体
        if custom_font_path and os.path.exists(custom_font_path):
            self.chinese_font_path = custom_font_path
            logger.info(f"✅ 使用自定义字体: {self.chinese_font_path}")
        else:
            self.chinese_font_path = self._detect_chinese_font()
            if self.chinese_font_path:
                logger.info(f"✅ 检测到中文字体: {self.chinese_font_path}")
            else:
                logger.warning("⚠️ 未检测到中文字体，字幕可能无法正常显示中文")
    
    def _detect_chinese_font(self) -> str:
        """检测系统中可用的中文字体"""
        system = platform.system().lower()
        candidate_fonts = []
        
        if system == 'darwin':  # macOS
            candidate_fonts.extend([
                '/System/Library/Fonts/Hiragino Sans GB.ttc',
                '/System/Library/Fonts/PingFang.ttc',
                '/System/Library/Fonts/STHeiti Light.ttc',
                '/System/Library/Fonts/STHeiti Medium.ttc',
                '/Library/Fonts/Arial Unicode MS.ttf',
                '/System/Library/Fonts/Apple LiSung Light.ttf'
            ])
        elif system == 'linux':
            candidate_fonts.extend([
                '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
                '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
                '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
                '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                '/usr/share/fonts/truetype/arphic/uming.ttc',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
            ])
        elif system == 'windows':
            windows_fonts_dir = os.path.join('C:', 'Windows', 'Fonts')
            candidate_fonts.extend([
                os.path.join(windows_fonts_dir, 'simhei.ttf'),
                os.path.join(windows_fonts_dir, 'simsun.ttc'),
                os.path.join(windows_fonts_dir, 'msyh.ttc'),
                os.path.join(windows_fonts_dir, 'msyhbd.ttc'),
                os.path.join(windows_fonts_dir, 'arial.ttf')
            ])
        
        for font_path in candidate_fonts:
            if os.path.exists(font_path):
                return font_path
        
        logger.warning("未找到预设的中文字体，将使用系统默认字体")
        return ""
    
    def get_video_info(self, video_path: str) -> Tuple[int, int, float, bool]:
        """获取视频信息（宽度, 高度, 时长, 是否有音频）"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            import json
            info = json.loads(result.stdout)
            
            video_stream = None
            has_audio = False
            for stream in info['streams']:
                if stream['codec_type'] == 'video':
                    video_stream = stream
                elif stream['codec_type'] == 'audio':
                    has_audio = True
            
            if not video_stream:
                raise ValueError("未找到视频流")
            
            width = int(video_stream['width'])
            height = int(video_stream['height'])
            duration = float(info['format']['duration'])
            
            return width, height, duration, has_audio
            
        except Exception as e:
            logger.error(f"获取视频信息失败: {str(e)}")
            raise
    
    def _escape_text_for_ffmpeg(self, text: str) -> str:
        """转义文本以便在FFmpeg中使用"""
        text = text.replace('\\', '\\\\')
        text = text.replace(':', '\\:')
        text = text.replace('[', '\\[')
        text = text.replace(']', '\\]')
        text = text.replace(',', '\\,')
        text = text.replace(';', '\\;')
        text = text.replace("'", "'\\''")
        return text

    def _split_text_to_lines(self, text: str, max_chars_per_line: int = 20) -> List[str]:
        """智能将长文本分割成多行，优化中文显示效果"""
        if len(text) <= max_chars_per_line:
            return [text]
        
        lines = []
        current_line = ""
        
        # 首先按句子分割
        sentences = re.split(r'([。！？]+)', text)
        
        for sentence in sentences:
            if not sentence.strip():
                continue
                
            if len(current_line + sentence) <= max_chars_per_line:
                current_line += sentence
                continue
            
            if current_line.strip():
                lines.append(current_line.strip())
                current_line = ""
            
            if len(sentence) > max_chars_per_line:
                parts = re.split(r'([，、；：]+)', sentence)
                
                for part in parts:
                    if not part.strip():
                        continue
                    
                    if len(current_line + part) <= max_chars_per_line:
                        current_line += part
                    else:
                        if current_line.strip():
                            lines.append(current_line.strip())
                            current_line = ""
                        
                        if len(part) > max_chars_per_line:
                            remaining = part
                            while len(remaining) > max_chars_per_line:
                                split_pos = max_chars_per_line
                                
                                for i in range(max_chars_per_line - 3, max_chars_per_line + 1):
                                    if i < len(remaining) and remaining[i] in '，、；：！？。':
                                        split_pos = i + 1
                                        break
                                    elif i < len(remaining) and remaining[i] in '"）】』」':
                                        split_pos = i + 1
                                        break
                                
                                lines.append(remaining[:split_pos])
                                remaining = remaining[split_pos:]
                            
                            current_line = remaining
                        else:
                            current_line = part
            else:
                current_line += sentence
        
        if current_line.strip():
            lines.append(current_line.strip())
        
        return lines

    def _split_main_title_to_lines(self, title: str, width: int, fontsize: int, max_lines: int = 2) -> List[str]:
        """将主标题智能分行"""
        max_width = width * 0.85
        max_chars_per_line = int(max_width / fontsize)
        
        logger.info(f"📋 主标题分行分析: 标题长度={len(title)}字符, 估算单行最大={max_chars_per_line}字符")
        
        if len(title) <= max_chars_per_line:
            logger.info(f"✅ 主标题长度适中，无需分行")
            return [title]
        
        if len(title) > max_chars_per_line * max_lines:
            logger.warning(f"⚠️ 主标题过长({len(title)}字符)，超过{max_lines}行限制，将进行强制两行分割")
            split_point = len(title) // 2
            line1 = title[:split_point].strip()
            line2 = title[split_point:].strip()
            logger.info(f"✅ 主标题强制分为两行: '{line1}' + '{line2}'")
            return [line1, line2]
            
        logger.info(f"📝 主标题较长({len(title)}字符)，进行智能分行")
        
        split_chars = ['，', '、', ' ', '的', '是', '与', '和', '及', '在', '于', '为', '被']
        best_split_point = -1
        mid_point = len(title) // 2
        search_range = len(title) // 4

        for char in ['，', '。', '！', '？', '；', '：', '、']:
            for offset in range(search_range + 1):
                pos1 = mid_point + offset
                pos2 = mid_point - offset
                if pos1 < len(title) and title[pos1] == char:
                    best_split_point = pos1 + 1
                    break
                if pos2 > 0 and title[pos2] == char:
                    best_split_point = pos2 + 1
                    break
            if best_split_point != -1:
                break
        
        if best_split_point == -1:
            for char in split_chars:
                for offset in range(search_range + 1):
                    pos1 = mid_point + offset
                    pos2 = mid_point - offset
                    if pos1 < len(title) and title[pos1] == char:
                        best_split_point = pos1 + 1
                        break
                    if pos2 > 0 and title[pos2] == char:
                        best_split_point = pos2 + 1
                        break
                if best_split_point != -1:
                    break

        if best_split_point == -1:
            best_split_point = mid_point
            logger.warning(f"⚠️ 未找到理想分割点，在中间位置({best_split_point})强制分割")
        else:
            logger.info(f"🎯 找到最佳分割点: 在'{title[best_split_point-1]}'后分割，位置={best_split_point}")

        line1 = title[:best_split_point].strip()
        line2 = title[best_split_point:].strip()
        
        if len(line1) > max_chars_per_line or len(line2) > max_chars_per_line:
            logger.warning(f"⚠️ 分割后某行可能仍偏长，但会继续处理。第1行{len(line1)}字符，第2行{len(line2)}字符")

        logger.info(f"✅ 主标题成功分为两行: '{line1}' + '{line2}'")
        return [line1, line2]

    def create_subtitle_filter(self, main_title: str, time_text: str, event_text: str,
                              width: int, height: int, subtitle_duration: float = 4.0, 
                              subtitle_start_time: float = 0.0) -> str:
        """创建字幕滤镜（用于历史人物系统）"""
        # 根据宽高比调整布局
        if self.aspect_ratio == "9:16":  # 竖屏
            main_title_y = int(height * 0.08)
            subtitle_base_y = int(height * 0.66)
            main_title_fontsize = max(36, int(min(width, height) * 0.052))
            subtitle_fontsize = max(40, int(min(width, height) * 0.064))
            max_chars_per_line = max(12, min(18, width // (subtitle_fontsize * 1.8)))
        else:  # 横屏 16:9
            main_title_y = int(height * 0.1)
            subtitle_base_y = int(height * (1 - 0.45))
            main_title_fontsize = max(44, int(width * 0.052))
            subtitle_fontsize = max(38, int(width * 0.04))
            max_chars_per_line = max(15, min(25, width // (subtitle_fontsize * 2)))
        
        # 处理主标题分行
        main_title_lines = self._split_main_title_to_lines(main_title, width, main_title_fontsize)
        
        # 转义文本
        escaped_main_title_lines = [self._escape_text_for_ffmpeg(line) for line in main_title_lines]
        escaped_time_text = self._escape_text_for_ffmpeg(time_text)
        escaped_event_text = self._escape_text_for_ffmpeg(event_text)
        
        # 构建滤镜
        filter_parts = []
        font_param = f":fontfile='{self.chinese_font_path}'" if self.chinese_font_path else ""
        subtitle_end_time = subtitle_start_time + subtitle_duration
        
        # 主标题滤镜
        title_line_height = int(main_title_fontsize * 1.2)
        for i, escaped_title_line in enumerate(escaped_main_title_lines):
            if not escaped_title_line.strip():
                continue
            
            if len(escaped_main_title_lines) > 1:
                line_y = main_title_y - (len(escaped_main_title_lines) - 1) * title_line_height // 2 + i * title_line_height
            else:
                line_y = main_title_y
            
            filter_parts.append(
                f"drawtext=text='{escaped_title_line}':fontcolor=white:fontsize={main_title_fontsize}"
                f"{font_param}:x=(w-text_w)/2:y={line_y}:enable='between(t,{subtitle_start_time},{subtitle_end_time})'"
                f":bordercolor=black:borderw=2"
            )
        
        # 处理字幕文本分行
        subtitle_combined = f"{time_text} {event_text}".strip()
        subtitle_lines = self._split_text_to_lines(subtitle_combined, max_chars_per_line)
        
        # 计算行高
        line_height = int(subtitle_fontsize * 1.3)
        
        # 为每行字幕添加滤镜
        for i, line in enumerate(subtitle_lines):
            if not line.strip():
                continue
                
            escaped_line = self._escape_text_for_ffmpeg(line)
            line_y = subtitle_base_y + (i * line_height)
            
            if line_y + line_height > height * 0.92:
                line_y = int(height * 0.92 - line_height)
            
            filter_parts.append(
                f"drawtext=text='{escaped_line}':fontcolor=yellow:fontsize={subtitle_fontsize}"
                f"{font_param}:x=(w-text_w)/2:y={line_y}:enable='between(t,{subtitle_start_time},{subtitle_end_time})'"
                f":bordercolor=black:borderw=3"
            )
        
        return ",".join(filter_parts)


# ============= CrewAI 工具定义 =============

class AddSimpleSubtitleSchema(BaseModel):
    """添加简单字幕的输入参数"""
    video_path: str = Field(..., description="输入视频路径")
    subtitle_text: str = Field(..., description="字幕文本内容")
    output_path: str = Field(..., description="输出视频路径")
    aspect_ratio: str = Field(default="9:16", description="视频宽高比: 16:9 或 9:16")
    fontsize: Optional[int] = Field(default=None, description="字体大小（可选，不指定则自动计算）")
    fontcolor: str = Field(default="white", description="字体颜色")
    position: str = Field(default="bottom", description="字幕位置: bottom 或 center")


class AddHistoricalSubtitleSchema(BaseModel):
    """添加历史人物字幕的输入参数"""
    video_path: str = Field(..., description="输入视频路径")
    output_path: str = Field(..., description="输出视频路径")
    main_title: str = Field(..., description="主标题文本")
    time_text: str = Field(..., description="时间文本")
    event_text: str = Field(..., description="事件文本")
    aspect_ratio: str = Field(default="9:16", description="视频宽高比: 16:9 或 9:16")
    subtitle_duration: float = Field(default=4.0, description="字幕显示时长（秒）")
    subtitle_start_time: float = Field(default=0.0, description="字幕开始显示时间（秒）")


class AddComplexSubtitlesSchema(BaseModel):
    """添加复杂字幕（多个字幕组）的输入参数"""
    video_path: str = Field(..., description="输入视频路径")
    output_path: str = Field(..., description="输出视频路径")
    subtitles_info: List[Dict[str, Any]] = Field(
        ..., 
        description="字幕信息列表，每个字典包含: main_title, scene_data(time, event), start_time"
    )
    aspect_ratio: str = Field(default="9:16", description="视频宽高比: 16:9 或 9:16")


class AddBackgroundMusicSchema(BaseModel):
    """添加背景音乐的输入参数"""
    video_path: str = Field(..., description="输入视频路径")
    music_path: str = Field(..., description="背景音乐文件路径")
    output_path: str = Field(..., description="输出视频路径")


class AddSimpleSubtitleTool(BaseTool):
    name: str = "添加简单字幕"
    description: str = "为视频添加简单的字幕文本，适用于科普视频等场景。支持自动调整字体大小和位置。"
    args_schema: Type[BaseModel] = AddSimpleSubtitleSchema

    def _run(
        self,
        video_path: str,
        subtitle_text: str,
        output_path: str,
        aspect_ratio: str = "9:16",
        fontsize: Optional[int] = None,
        fontcolor: str = "white",
        position: str = "bottom"
    ) -> Dict[str, Any]:
        """添加简单字幕"""
        try:
            processor = SubtitleProcessor(aspect_ratio=aspect_ratio)
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            width, height, duration, _ = processor.get_video_info(video_path)
            
            logger.info(f"📏 视频信息: {width}x{height}, 时长: {duration:.2f}s")
            
            # 根据宽高比调整字体和位置
            if aspect_ratio == "9:16":
                default_fontsize = max(50, int(min(width, height) * 0.08))
                y_pos = int(height * 0.75)
                max_chars_per_line = max(10, min(14, width // (default_fontsize * 2.2)))
            else:
                default_fontsize = max(45, int(width * 0.05))
                y_pos = int(height * 0.75)
                max_chars_per_line = max(12, min(20, width // (default_fontsize * 2.5)))
            
            actual_fontsize = fontsize if fontsize and fontsize >= 30 else default_fontsize
            
            logger.info(f"📝 字幕设置: 字体大小={actual_fontsize}, 位置=y{y_pos}, 每行最大{max_chars_per_line}字符")
            
            # 处理字幕文本分行
            subtitle_lines = processor._split_text_to_lines(subtitle_text, max_chars_per_line)
            
            # 构建滤镜
            filter_parts = []
            font_param = f":fontfile='{processor.chinese_font_path}'" if processor.chinese_font_path else ""
            line_height = int(actual_fontsize * 1.3)
            
            # 多行时调整起始位置
            if len(subtitle_lines) > 1:
                total_height = len(subtitle_lines) * line_height
                y_pos = y_pos - (total_height // 2) + (line_height // 2)
            
            for i, line in enumerate(subtitle_lines):
                if not line.strip():
                    continue
                    
                escaped_line = processor._escape_text_for_ffmpeg(line)
                line_y = y_pos + (i * line_height)
                
                if line_y + line_height > height * 0.92:
                    line_y = int(height * 0.92 - line_height)
                
                filter_parts.append(
                    f"drawtext=text='{escaped_line}':fontcolor={fontcolor}:fontsize={actual_fontsize}"
                    f"{font_param}:x=(w-text_w)/2:y={line_y}"
                    f":bordercolor=black:borderw=3:shadowcolor=black:shadowx=2:shadowy=2"
                )
            
            if not filter_parts:
                logger.warning("⚠️ 没有有效的字幕内容")
                import shutil
                shutil.copy2(video_path, output_path)
                return {
                    'status': 'success',
                    'output_path': output_path,
                    'message': '⚠️ 没有有效字幕，已复制原视频'
                }
            
            # 构建FFmpeg命令
            subtitle_filter = ",".join(filter_parts)
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', subtitle_filter,
                '-c:a', 'copy',
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                output_path
            ]
            
            logger.info("🎬 开始添加字幕...")
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            logger.info(f"✅ 字幕添加完成: {output_path}")
            return {
                'status': 'success',
                'output_path': output_path,
                'message': f'✅ 字幕添加成功'
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg 处理失败: {e.stderr}")
            return {
                'status': 'failed',
                'error': f'FFmpeg 处理失败: {e.stderr}',
                'message': f'❌ 字幕添加失败'
            }
        except Exception as e:
            logger.error(f"字幕处理失败: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'message': f'❌ 字幕处理失败: {str(e)}'
            }


class AddHistoricalSubtitleTool(BaseTool):
    name: str = "添加历史人物字幕"
    description: str = "为历史人物视频添加专业字幕，包含主标题、时间和事件信息。支持字幕时间控制。"
    args_schema: Type[BaseModel] = AddHistoricalSubtitleSchema

    def _run(
        self,
        video_path: str,
        output_path: str,
        main_title: str,
        time_text: str,
        event_text: str,
        aspect_ratio: str = "9:16",
        subtitle_duration: float = 4.0,
        subtitle_start_time: float = 0.0
    ) -> Dict[str, Any]:
        """添加历史人物字幕"""
        try:
            processor = SubtitleProcessor(aspect_ratio=aspect_ratio)
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            width, height, duration, _ = processor.get_video_info(video_path)
            
            logger.info(f"📏 视频信息: {width}x{height}, 时长: {duration:.2f}s")
            logger.info(f"📋 主标题: {main_title}")
            logger.info(f"📋 字幕: {time_text} {event_text}")
            
            # 创建字幕滤镜
            subtitle_filter = processor.create_subtitle_filter(
                main_title, time_text, event_text, width, height,
                subtitle_duration, subtitle_start_time
            )
            
            # 构建FFmpeg命令
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', subtitle_filter,
                '-c:a', 'copy',
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                output_path
            ]
            
            logger.info("🎬 开始添加历史人物字幕...")
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            logger.info(f"✅ 字幕添加完成: {output_path}")
            return {
                'status': 'success',
                'output_path': output_path,
                'message': '✅ 历史人物字幕添加成功'
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg 处理失败: {e.stderr}")
            return {
                'status': 'failed',
                'error': f'FFmpeg 处理失败: {e.stderr}',
                'message': '❌ 字幕添加失败'
            }
        except Exception as e:
            logger.error(f"字幕处理失败: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'message': f'❌ 字幕处理失败: {str(e)}'
            }


class AddComplexSubtitlesTool(BaseTool):
    name: str = "添加复杂多字幕组"
    description: str = "为单个视频添加多个位于不同时间点的字幕组，每组包含主标题、时间和事件信息。"
    args_schema: Type[BaseModel] = AddComplexSubtitlesSchema

    def _run(
        self,
        video_path: str,
        output_path: str,
        subtitles_info: List[Dict[str, Any]],
        aspect_ratio: str = "9:16"
    ) -> Dict[str, Any]:
        """添加复杂多字幕组"""
        try:
            if not subtitles_info:
                logger.warning(f"没有提供字幕信息，将直接复制文件")
                import shutil
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.copy2(video_path, output_path)
                return {
                    'status': 'success',
                    'output_path': output_path,
                    'message': '⚠️ 无字幕信息，已复制原视频'
                }

            processor = SubtitleProcessor(aspect_ratio=aspect_ratio)
            
            logger.info(f"📝 正在为视频添加 {len(subtitles_info)} 组字幕...")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            width, height, _, _ = processor.get_video_info(video_path)
            
            all_filters = []
            subtitle_duration = 2.5

            for info in subtitles_info:
                scene_data = info['scene_data']
                start_time = info['start_time']
                main_title = info['main_title']
                
                logger.info(f"  -> 字幕组: 主标题='{main_title}', 内容='{scene_data.get('time', '')} {scene_data.get('event', '')}', 开始时间={start_time:.2f}s")

                subtitle_filter = processor.create_subtitle_filter(
                    main_title=main_title,
                    time_text=scene_data.get('time', ''),
                    event_text=scene_data.get('event', ''),
                    width=width,
                    height=height,
                    subtitle_duration=subtitle_duration,
                    subtitle_start_time=start_time
                )
                if subtitle_filter:
                    all_filters.append(subtitle_filter)

            if not all_filters:
                raise ValueError("未能创建任何有效的字幕滤镜")

            final_filter_string = ",".join(all_filters)

            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', final_filter_string,
                '-c:a', 'copy',
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                output_path
            ]
            
            logger.info("🎬 正在使用 FFmpeg 应用合并后的字幕滤镜...")
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            logger.info(f"✅ 字幕添加完成: {output_path}")
            return {
                'status': 'success',
                'output_path': output_path,
                'total_subtitles': len(subtitles_info),
                'message': f'✅ 成功添加 {len(subtitles_info)} 组字幕'
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg 处理失败: {e.stderr}")
            return {
                'status': 'failed',
                'error': f'FFmpeg 处理失败: {e.stderr}',
                'message': '❌ 字幕添加失败'
            }
        except Exception as e:
            logger.error(f"字幕处理失败: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'message': f'❌ 字幕处理失败: {str(e)}'
            }


class AddBackgroundMusicTool(BaseTool):
    name: str = "添加背景音乐到视频"
    description: str = "为视频添加背景音乐。如果视频已有音频，会混合原音频和背景音乐；如果无音频，直接添加背景音乐。"
    args_schema: Type[BaseModel] = AddBackgroundMusicSchema

    def _run(
        self,
        video_path: str,
        music_path: str,
        output_path: str
    ) -> Dict[str, Any]:
        """添加背景音乐"""
        try:
            if not os.path.exists(music_path):
                logger.warning(f"背景音乐文件不存在: {music_path}")
                import shutil
                shutil.copy2(video_path, output_path)
                return {
                    'status': 'failed',
                    'error': '背景音乐文件不存在',
                    'output_path': video_path,
                    'message': '⚠️ 背景音乐文件不存在，已复制原视频'
                }
            
            processor = SubtitleProcessor()
            
            logger.info(f"🎵 为视频添加背景音乐...")
            logger.info(f"🎵 音乐文件: {music_path}")
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            _, _, video_duration, has_audio = processor.get_video_info(video_path)
            
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', music_path,
            ]
            
            if has_audio:
                # 有音频，混合
                cmd.extend([
                    '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[a]',
                    '-map', '0:v',
                    '-map', '[a]',
                ])
            else:
                # 无音频，直接使用音乐
                cmd.extend([
                    '-map', '0:v',
                    '-map', '1:a',
                ])
            
            cmd.extend([
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-shortest',
                output_path
            ])
            
            logger.info("🎬 开始添加背景音乐...")
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            logger.info(f"✅ 背景音乐添加完成: {output_path}")
            return {
                'status': 'success',
                'output_path': output_path,
                'message': '✅ 背景音乐添加成功'
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"背景音乐添加失败: {e.stderr}")
            import shutil
            shutil.copy2(video_path, output_path)
            return {
                'status': 'failed',
                'error': e.stderr,
                'output_path': output_path,
                'message': f'❌ 背景音乐添加失败，已复制原视频'
            }
        except Exception as e:
            logger.error(f"背景音乐处理失败: {str(e)}")
            import shutil
            shutil.copy2(video_path, output_path)
            return {
                'status': 'failed',
                'error': str(e),
                'output_path': output_path,
                'message': f'❌ 背景音乐处理失败: {str(e)}'
            }

