#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频时长管理工具
提供视频和音频时长的获取、计算和剪辑功能
"""

import subprocess
import json
from pathlib import Path
from typing import Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from src.logger import get_logger

logger = get_logger('video_duration_tool')


class VideoDurationInput(BaseModel):
    """视频时长输入模型"""
    video_path: str = Field(..., description="视频文件路径")


class AudioDurationInput(BaseModel):
    """音频时长输入模型"""
    audio_path: str = Field(..., description="音频文件路径")


class TrimVideoInput(BaseModel):
    """视频剪辑输入模型"""
    input_path: str = Field(..., description="输入视频路径")
    output_path: str = Field(..., description="输出视频路径")
    duration: float = Field(..., description="目标时长（秒）")


class VideoTimeLengthManager:
    """视频时长管理器（静态方法类）"""

    @staticmethod
    def get_video_duration(video_path: str) -> float:
        """获取视频时长（秒）

        Args:
            video_path: 视频文件路径

        Returns:
            视频时长（秒），如果获取失败返回 5.0
        """
        try:
            cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            duration = float(data['format']['duration'])
            return duration
        except Exception as e:
            logger.warning(f"⚠️ 无法获取视频时长: {str(e)}")
            return 5.0  # 默认返回5秒

    @staticmethod
    def get_audio_duration(audio_path: str) -> Optional[float]:
        """获取音频时长（秒）

        Args:
            audio_path: 音频文件路径

        Returns:
            音频时长（秒），如果获取失败返回 None
        """
        try:
            cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json',
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            duration = float(data['format']['duration'])
            return duration
        except Exception as e:
            logger.warning(f"⚠️ 无法获取音频时长: {str(e)}")
            return None

    @staticmethod
    def calculate_final_duration(
        scene_duration: float,
        actual_video_duration: float,
        audio_duration: Optional[float] = None,
        scene_index: int = 0
    ) -> float:
        """计算最终视频时长

        逻辑：
        - 如果有配音：视频时长不能小于配音时长，然后取分镜时长和实际视频时长的最小值
        - 如果无配音：取分镜时长和实际视频时长的最小值

        Args:
            scene_duration: 分镜指定的时长
            actual_video_duration: 实际视频时长
            audio_duration: 音频时长（如果有）
            scene_index: 场景索引（用于日志）

        Returns:
            最终时长（秒）
        """
        if audio_duration is not None:
            # 有配音：以音频时长为准，不再被 scene_duration 限制
            buffer = 0.3  # 音频结束后的缓冲时间（秒）
            final_duration = audio_duration + buffer
            # 不超过实际视频时长（避免超出素材）
            final_duration = min(final_duration, actual_video_duration)
            # 保底：不能短于音频本身
            final_duration = max(final_duration, audio_duration)
            logger.info(
                f"  场景{scene_index}: 配音{audio_duration:.2f}秒, "
                f"分镜{scene_duration:.2f}秒, 实际{actual_video_duration:.2f}秒 "
                f"→ 最终{final_duration:.2f}秒（以音频为准）"
            )
        else:
            # 无配音：取分镜时长和实际视频时长的最小值
            final_duration = min(scene_duration, actual_video_duration)
            logger.info(
                f"  场景{scene_index}: 分镜{scene_duration:.2f}秒, "
                f"实际{actual_video_duration:.2f}秒 → 最终{final_duration:.2f}秒"
            )

        return final_duration

    @staticmethod
    def trim_video(input_path: str, output_path: str, duration: float) -> bool:
        """剪辑视频到指定时长

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            duration: 目标时长（秒）

        Returns:
            是否成功
        """
        try:
            # 使用视频copy + 音频重编码模式，避免音频断续问题
            # 视频使用copy（快速），音频重新编码确保连贯
            cmd = [
                'ffmpeg', '-i', input_path,
                '-t', str(duration),
                '-c:v', 'copy',  # 视频流复制（快速）
                '-c:a', 'aac',   # 音频重新编码为aac，确保连贯
                '-b:a', '192k',  # 音频码率192kbps（高质量）
                '-ar', '44100',  # 统一采样率
                '-y', output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"✅ 视频剪辑成功: {output_path}")
            return True
        except Exception as e:
            logger.error(f"❌ 视频剪辑失败: {str(e)}")
            return False

    @staticmethod
    def trim_audio(input_path: str, output_path: str, duration: float) -> bool:
        """剪辑音频到指定时长

        Args:
            input_path: 输入音频路径
            output_path: 输出音频路径
            duration: 目标时长（秒）

        Returns:
            是否成功
        """
        try:
            # 修复：保持原始 MP3 格式，使用 copy 避免重新编码
            # 原先使用 aac 编码但输出 .mp3 扩展名会导致 ffmpeg 错误 234
            cmd = [
                'ffmpeg', '-i', input_path,
                '-t', str(duration),
                '-c:a', 'copy',  # 直接复制音频流，不重新编码
                '-y', output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"✅ 音频剪辑成功: {output_path}")
            return True
        except Exception as e:
            logger.error(f"❌ 音频剪辑失败: {str(e)}")
            return False


class GetVideoDurationTool(BaseTool):
    """获取视频时长工具"""
    name: str = "Get Video Duration"
    description: str = "获取视频文件的时长（秒）"
    args_schema: type[BaseModel] = VideoDurationInput

    def _run(self, video_path: str) -> float:
        """执行工具"""
        return VideoTimeLengthManager.get_video_duration(video_path)


class GetAudioDurationTool(BaseTool):
    """获取音频时长工具"""
    name: str = "Get Audio Duration"
    description: str = "获取音频文件的时长（秒）"
    args_schema: type[BaseModel] = AudioDurationInput

    def _run(self, audio_path: str) -> Optional[float]:
        """执行工具"""
        return VideoTimeLengthManager.get_audio_duration(audio_path)


class TrimVideoTool(BaseTool):
    """视频剪辑工具"""
    name: str = "Trim Video"
    description: str = "将视频剪辑到指定时长"
    args_schema: type[BaseModel] = TrimVideoInput

    def _run(self, input_path: str, output_path: str, duration: float) -> bool:
        """执行工具"""
        return VideoTimeLengthManager.trim_video(input_path, output_path, duration)
