"""
视频处理工具模块
包含视频拼接、字幕、放大等后期处理工具
"""

from .video_duration_tool import GetVideoDurationTool, GetAudioDurationTool, TrimVideoTool, VideoTimeLengthManager
from .adaptive_subtitle_tool import AdaptiveSubtitleProcessor
from .flexible_subtitle_tool import FlexibleSubtitleProcessor
from .subtitle_style_parser import SubtitleStyleParser
from .video_subtitle_tool import VideoSubtitleTool, burn_subtitle_to_video
from .video_concatenate_tool import ConcatenateVideosTool, AddBackgroundMusicTool
from .image_to_video_fallback_tool import ImageToVideoFallbackTool, create_video_from_image_simple
from .video_frame_extractor_tool import VideoFrameExtractor, extract_video_last_frame, extract_video_first_frame

__all__ = [
    'ConcatenateVideosTool',
    'GetVideoDurationTool',
    'GetAudioDurationTool',
    'TrimVideoTool',
    'VideoTimeLengthManager',
    'AdaptiveSubtitleProcessor',
    'FlexibleSubtitleProcessor',
    'SubtitleStyleParser',
    'AddBackgroundMusicTool',
    'VideoSubtitleTool',
    'burn_subtitle_to_video',
    'ImageToVideoFallbackTool',
    'create_video_from_image_simple',
    'VideoFrameExtractor',
    'extract_video_last_frame',
    'extract_video_first_frame',
]
