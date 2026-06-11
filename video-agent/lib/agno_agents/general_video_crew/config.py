#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agno 通用视频生成配置模块
集中管理所有硬编码配置和常量
"""

from dataclasses import dataclass, field
from typing import Dict, List
from src.utils.font_utils import DEFAULT_FONT_PATH as _DEFAULT_FONT_PATH


@dataclass
class VideoGenerationConfig:
    """视频生成配置"""

    # ========== 时长配置 ==========
    MAX_DURATION: int = 180  # 最大时长(秒)
    DEFAULT_SCENE_DURATION: float = 5.0  # 默认分镜时长(秒)
    COVER_DURATION: float = 0.1  # 封面显示时长(秒)

    # ========== 并发配置 ==========
    IMAGE_CONCURRENCY: int = 10  # 图片生成并发数
    VIDEO_CONCURRENCY: int = 10  # 视频生成并发数
    AUDIO_CONCURRENCY: int = 3  # 音频生成并发数

    # ========== 重试配置 ==========
    MAX_RETRIES: int = 3  # 最大重试次数
    MAX_IMAGE_REGENERATION_ATTEMPTS: int = 2  # 图片质量检测最大重新生成次数
    MAX_VIDEO_REGENERATION_ATTEMPTS: int = 2  # 视频质量检测最大重新生成次数

    # ========== 引擎配置 ==========
    DEFAULT_VIDEO_ENGINE: str = 'seedance'
    DEFAULT_IMAGE_ENGINE: str = 'seedream5'
    TRANSITION_FRAME_ENGINES: List[str] = field(default_factory=list)

    # ========== 备选引擎配置 ==========
    VIDEO_ENGINE_FALLBACK_ORDER: List[str] = field(default_factory=lambda: ['seedance', 'jimeng35pro', 'veo3'])
    IMAGE_ENGINE_FALLBACK_ORDER: List[str] = field(default_factory=lambda: ['seedream5', 'gemini3_pro'])
    ENGINE_TIMEOUT_MINUTES: int = 10

    # ========== 路径配置 ==========
    DEFAULT_FONT_PATH: str = _DEFAULT_FONT_PATH
    BASE_OUTPUT_DIR: str = "output"

    # ========== 视频配置 ==========
    DEFAULT_ASPECT_RATIO: str = '9:16'
    DEFAULT_PLATFORM: str = '抖音'

    # ========== 音频配置 ==========
    DEFAULT_VOICE_SPEED: float = 1.25
    DEFAULT_MUSIC_VOLUME: float = 1.2

    # ========== 字幕配置 ==========
    DEFAULT_SUBTITLE_POSITION: str = 'bottom'
    DEFAULT_FONT_COLOR: str = 'white'
    DEFAULT_BORDER_COLOR: str = 'black'
    DEFAULT_BORDER_WIDTH: int = 0
    DEFAULT_FADE_IN: float = 0.3
    DEFAULT_FADE_OUT: float = 0.5

    # ========== 特性开关 ==========
    ENABLE_IMAGE_QUALITY_CHECK: bool = True
    ENABLE_VIDEO_QUALITY_CHECK: bool = True
    ENABLE_MODERATION: bool = True
    ENABLE_SUBTITLES: bool = True
    ENABLE_BACKGROUND_MUSIC: bool = True
    ENABLE_SOCIAL_MEDIA_COPYWRITING: bool = True

    # ========== 任务配置 ==========
    EXPECTED_TASK_COUNT: int = 11


@dataclass
class VideoGenerationMode:
    """视频生成模式常量"""
    PURE_IMAGE_TO_VIDEO: str = 'pure_image_to_video'
    PURE_TEXT_TO_VIDEO: str = 'pure_text_to_video'
    MIXED: str = 'mixed'

    MODE_DESCRIPTIONS: Dict[str, str] = field(default_factory=lambda: {
        'pure_image_to_video': '纯图生视频(所有分镜都是图生视频)',
        'pure_text_to_video': '纯文生视频(所有分镜都是文生视频)',
        'mixed': '混合模式(包含多种类型分镜的组合)'
    })


@dataclass
class ReferenceType:
    """参考图类型常量"""
    CHARACTER: str = 'character'
    STYLE: str = 'style'
    OBJECT: str = 'object'
    MIXED: str = 'mixed'
    NONE: str = 'none'


@dataclass
class GenerationMode:
    """生成模式常量"""
    TEXT_TO_IMAGE: str = 'text2image'
    IMAGE_TO_IMAGE: str = 'image2image'
    MULTI_IMAGE_FUSION: str = 'multi_image_fusion'
    FAILED: str = 'failed'


@dataclass
class VideoGenerationType:
    """视频生成类型常量"""
    IMAGE_TO_VIDEO: str = 'image_to_video'


@dataclass
class SubtitleLanguage:
    """字幕语言常量"""
    CHINESE: str = 'zh'
    ENGLISH: str = 'en'


# 全局配置实例
CONFIG = VideoGenerationConfig()
MODE = VideoGenerationMode()
REF_TYPE = ReferenceType()
GEN_MODE = GenerationMode()
VIDEO_TYPE = VideoGenerationType()
SUBTITLE_LANG = SubtitleLanguage()


def get_mode_description(mode: str) -> str:
    """获取视频生成模式的描述"""
    return MODE.MODE_DESCRIPTIONS.get(mode, '未知模式')


def validate_video_engine(engine: str, video_generation_mode: str) -> bool:
    """验证视频引擎是否支持指定的生成模式"""
    return engine in CONFIG.VIDEO_ENGINE_FALLBACK_ORDER


def get_recommended_engine(video_generation_mode: str) -> str:
    """根据视频生成模式推荐引擎"""
    return CONFIG.DEFAULT_VIDEO_ENGINE
