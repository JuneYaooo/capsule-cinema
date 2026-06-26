#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频字幕合成工具
将 SRT 字幕烧录到视频中，支持美化样式
"""

import os
import json
import re
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from crewai.tools import BaseTool
from pydantic import Field

from src.logger import get_logger

logger = get_logger('video_subtitle_tool')


class VideoSubtitleTool(BaseTool):
    """视频字幕合成工具 - 将字幕烧录到视频中"""

    name: str = "video_subtitle_tool"
    description: str = (
        "将 SRT 字幕文件烧录到视频中，生成带字幕的视频。"
        "支持自定义字幕样式（字体、大小、颜色、位置等）。"
    )

    def _run(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: Optional[str] = None,
        font_name: str = "PingFang SC",
        font_size: int = 24,
        font_color: str = "&HFFFFFF",  # 白色
        outline_color: str = "&H000000",  # 黑色边框
        outline_width: int = 2,
        shadow_color: str = "&H80000000",  # 半透明黑色阴影
        shadow_offset: int = 1,
        margin_v: int = 80,  # 底部边距
        alignment: int = 2,  # 底部居中（2=底部居中，8=顶部居中）
        bold: bool = True,
        **kwargs
    ) -> str:
        """
        将字幕烧录到视频中

        Args:
            video_path: 输入视频路径
            subtitle_path: SRT字幕文件路径
            output_path: 输出视频路径（可选，默认在同目录生成 _subtitled.mp4）
            font_name: 字体名称，默认 "PingFang SC"
            font_size: 字体大小，默认 24
            font_color: 字体颜色（ASS格式），默认白色 "&HFFFFFF"
            outline_color: 边框颜色（ASS格式），默认黑色 "&H000000"
            outline_width: 边框宽度，默认 2
            shadow_color: 阴影颜色（ASS格式），默认半透明黑色 "&H80000000"
            shadow_offset: 阴影偏移，默认 1
            margin_v: 字幕底部边距（像素），默认 80
            alignment: 字幕对齐方式（2=底部居中，8=顶部居中），默认 2
            bold: 是否粗体，默认 True

        Returns:
            生成结果信息
        """
        try:
            # 验证输入
            video_path = Path(video_path)
            subtitle_path = Path(subtitle_path)

            if not video_path.exists():
                error_msg = f"❌ 视频文件不存在: {video_path}"
                logger.error(error_msg)
                return error_msg

            if not subtitle_path.exists():
                error_msg = f"❌ 字幕文件不存在: {subtitle_path}"
                logger.error(error_msg)
                return error_msg

            # 确定输出路径
            if output_path is None:
                output_path = video_path.parent / f"{video_path.stem}_subtitled.mp4"
            else:
                output_path = Path(output_path)

            output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"📝 开始合成字幕到视频...")
            logger.info(f"   输入视频: {video_path.name}")
            logger.info(f"   字幕文件: {subtitle_path.name}")
            logger.info(f"   输出视频: {output_path.name}")
            logger.info(f"   字体: {font_name}, 大小: {font_size}")

            width, height = self._probe_video_size(video_path)

            # 将 SRT 转换为 ASS（更好的样式支持）
            ass_subtitle_path = self._convert_srt_to_ass(
                subtitle_path,
                font_name=font_name,
                font_size=font_size,
                font_color=font_color,
                outline_color=outline_color,
                outline_width=outline_width,
                shadow_color=shadow_color,
                shadow_offset=shadow_offset,
                margin_v=margin_v,
                alignment=alignment,
                bold=bold,
                play_res_x=width,
                play_res_y=height
            )

            # 使用 ffmpeg 烧录字幕
            self._burn_subtitle_with_ffmpeg(
                video_path=str(video_path),
                subtitle_path=str(ass_subtitle_path),
                output_path=str(output_path)
            )

            # 清理临时 ASS 文件
            if ass_subtitle_path.exists():
                ass_subtitle_path.unlink()

            if output_path.exists():
                file_size = output_path.stat().st_size / (1024 * 1024)
                success_msg = f"✅ 字幕合成成功!\n"
                success_msg += f"   输出: {output_path}\n"
                success_msg += f"   大小: {file_size:.2f} MB"
                logger.info(success_msg)
                return success_msg
            else:
                error_msg = f"❌ 字幕合成失败: 输出文件未生成"
                logger.error(error_msg)
                return error_msg

        except Exception as e:
            error_msg = f"❌ 字幕合成失败: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.error(traceback.format_exc())
            return error_msg

    def _convert_srt_to_ass(
        self,
        srt_path: Path,
        font_name: str,
        font_size: int,
        font_color: str,
        outline_color: str,
        outline_width: int,
        shadow_color: str,
        shadow_offset: int,
        margin_v: int,
        alignment: int,
        bold: bool,
        play_res_x: int,
        play_res_y: int
    ) -> Path:
        """
        将 SRT 字幕转换为 ASS 格式，添加样式

        Returns:
            ASS 字幕文件路径
        """
        ass_path = srt_path.parent / f"{srt_path.stem}.ass"

        # 读取 SRT 内容
        with open(srt_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()

        # 解析 SRT
        subtitles = self._parse_srt(srt_content)

        # 生成 ASS 内容
        ass_content = self._generate_ass_content(
            subtitles=subtitles,
            font_name=font_name,
            font_size=font_size,
            font_color=font_color,
            outline_color=outline_color,
            outline_width=outline_width,
            shadow_color=shadow_color,
            shadow_offset=shadow_offset,
            margin_v=margin_v,
            alignment=alignment,
            bold=bold,
            play_res_x=play_res_x,
            play_res_y=play_res_y
        )

        # 写入 ASS 文件
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        logger.info(f"   ✅ SRT 已转换为 ASS: {ass_path.name}")
        return ass_path

    def _parse_srt(self, srt_content: str) -> list:
        """
        解析 SRT 字幕内容

        Returns:
            字幕列表: [{"start": "00:00:10.000", "end": "00:00:12.300", "text": "字幕内容"}, ...]
        """
        subtitles = []
        blocks = srt_content.strip().split('\n\n')

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                # 第一行是序号
                # 第二行是时间轴
                time_line = lines[1]
                if ' --> ' in time_line:
                    start, end = time_line.split(' --> ')
                    # 第三行及之后是文本
                    text = '\n'.join(lines[2:])
                    subtitles.append({
                        'start': start.strip(),
                        'end': end.strip(),
                        'text': text.strip()
                    })

        return subtitles

    def _generate_ass_content(
        self,
        subtitles: list,
        font_name: str,
        font_size: int,
        font_color: str,
        outline_color: str,
        outline_width: int,
        shadow_color: str,
        shadow_offset: int,
        margin_v: int,
        alignment: int,
        bold: bool,
        play_res_x: int,
        play_res_y: int
    ) -> str:
        """
        生成 ASS 字幕内容

        Returns:
            ASS 格式的字幕内容
        """
        # ASS 文件头
        ass_header = f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+
Collisions: Normal
PlayDepth: 0
PlayResX: {play_res_x}
PlayResY: {play_res_y}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{font_color},&H000000FF,{outline_color},{shadow_color},{-1 if bold else 0},0,0,0,100,100,0,0,1,{outline_width},{shadow_offset},{alignment},10,10,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        from .adaptive_subtitle_tool import AdaptiveSubtitleProcessor

        subtitle_wrapper = AdaptiveSubtitleProcessor()

        def wrap_ass_text(raw_text: str) -> str:
            text = (raw_text or "").strip()
            if not text:
                return ""

            normalized_text = text.replace("\\N", " ").replace("\r", " ").replace("\n", " ")
            language = "zh" if re.search(r"[\u4e00-\u9fff]", normalized_text) else "en"
            safe_width = max(320, int(play_res_x * 0.72))
            max_chars = max(8, min(18, int(safe_width / max(font_size, 1))))
            lines = subtitle_wrapper._smart_wrap_text(
                text=normalized_text,
                max_chars=max_chars,
                max_lines=3,
                language=language,
            )
            return "\\N".join(line.strip() for line in lines if line.strip())

        # 生成字幕事件
        events = []
        for sub in subtitles:
            start = self._srt_time_to_ass_time(sub['start'])
            end = self._srt_time_to_ass_time(sub['end'])
            text = wrap_ass_text(sub['text'])
            events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

        return ass_header + '\n'.join(events)

    def _probe_video_size(self, video_path: Path) -> tuple[int, int]:
        """
        获取视频分辨率，用于写入 ASS PlayRes，避免字幕按默认脚本分辨率被放大。
        """
        try:
            result = subprocess.run(
                [
                    'ffprobe',
                    '-v',
                    'error',
                    '-select_streams',
                    'v:0',
                    '-show_entries',
                    'stream=width,height',
                    '-of',
                    'json',
                    str(video_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            streams = json.loads(result.stdout).get('streams') or []
            if streams:
                width = int(streams[0].get('width') or 720)
                height = int(streams[0].get('height') or 1280)
                return width, height
        except Exception as exc:
            logger.warning(f"无法探测视频尺寸，使用默认竖屏分辨率: {exc}")
        return 720, 1280

    def _srt_time_to_ass_time(self, srt_time: str) -> str:
        """
        将 SRT 时间格式转换为 ASS 时间格式
        SRT: 00:00:10,000
        ASS: 0:00:10.00
        """
        # 替换逗号为点号
        srt_time = srt_time.replace(',', '.')
        # 移除毫秒的第三位（ASS只用两位）
        parts = srt_time.split('.')
        if len(parts) == 2:
            milliseconds = parts[1][:2]  # 只取前两位
            srt_time = f"{parts[0]}.{milliseconds}"
        # 移除开头的 0（如果小时是 00）
        if srt_time.startswith('00:'):
            srt_time = srt_time[1:]  # 变成 0:00:10.00
        return srt_time

    def _burn_subtitle_with_ffmpeg(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str
    ):
        """
        使用 ffmpeg 烧录字幕到视频
        """
        # 构建 ffmpeg 命令
        # 使用 subtitles filter 烧录字幕
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vf', f"subtitles={subtitle_path}",
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'copy',  # 保留原音频
            '-pix_fmt', 'yuv420p',
            output_path
        ]

        logger.info(f"   🔧 执行 ffmpeg 命令...")

        # 执行命令
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=600  # 10分钟超时
            )
            logger.info(f"   ✅ ffmpeg 执行成功")
        except subprocess.CalledProcessError as e:
            error_msg = f"ffmpeg 执行失败:\n{e.stderr}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except subprocess.TimeoutExpired:
            error_msg = "ffmpeg 执行超时（10分钟）"
            logger.error(error_msg)
            raise Exception(error_msg)


def burn_subtitle_to_video(
    video_path: str,
    subtitle_path: str,
    output_path: Optional[str] = None,
    **kwargs
) -> str:
    """
    便捷函数：将字幕烧录到视频中

    Args:
        video_path: 输入视频路径
        subtitle_path: SRT字幕文件路径
        output_path: 输出视频路径（可选）
        **kwargs: 其他样式参数

    Returns:
        生成结果信息
    """
    tool = VideoSubtitleTool()
    return tool._run(
        video_path=video_path,
        subtitle_path=subtitle_path,
        output_path=output_path,
        **kwargs
    )
