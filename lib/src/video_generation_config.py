#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared configuration for the general-video pipeline."""

from dataclasses import dataclass, field
from typing import Dict, List

from src.utils.font_utils import DEFAULT_FONT_PATH as _DEFAULT_FONT_PATH


@dataclass
class VideoGenerationConfig:
    """Video generation defaults shared by planning and runtime modules."""

    # Duration
    MAX_DURATION: int = 180
    DEFAULT_SCENE_DURATION: float = 5.0
    COVER_DURATION: float = 0.1

    # Concurrency
    IMAGE_CONCURRENCY: int = 10
    VIDEO_CONCURRENCY: int = 10
    AUDIO_CONCURRENCY: int = 3
    IMAGE_SCENE_TIMEOUT_SECONDS: float = 300.0

    # Retry / QA
    MAX_RETRIES: int = 3
    MAX_IMAGE_REGENERATION_ATTEMPTS: int = 2
    MAX_VIDEO_REGENERATION_ATTEMPTS: int = 2

    # Engines
    DEFAULT_VIDEO_ENGINE: str = "seedance-fast"
    DEFAULT_IMAGE_ENGINE: str = "gpt-image-2"
    TRANSITION_FRAME_ENGINES: List[str] = field(default_factory=list)
    SUPPORTED_VIDEO_ENGINES: List[str] = field(
        default_factory=lambda: ["seedance-fast", "seedance", "seedance2.0", "jimeng35pro", "veo3", "veo3.1"]
    )
    ENGINE_TIMEOUT_MINUTES: int = 10

    # Paths
    DEFAULT_FONT_PATH: str = _DEFAULT_FONT_PATH
    BASE_OUTPUT_DIR: str = "output"

    # Video
    DEFAULT_ASPECT_RATIO: str = "9:16"
    DEFAULT_PLATFORM: str = "抖音"

    # Audio
    DEFAULT_VOICE_SPEED: float = 1.1
    DEFAULT_MUSIC_VOLUME: float = 1.2

    # Subtitles
    DEFAULT_SUBTITLE_POSITION: str = "bottom"
    DEFAULT_FONT_COLOR: str = "#FFFEF0"
    DEFAULT_BORDER_COLOR: str = "#1A1A1A"
    DEFAULT_BORDER_WIDTH: int = 2
    DEFAULT_FADE_IN: float = 0.2
    DEFAULT_FADE_OUT: float = 0.3

    # Feature flags
    ENABLE_IMAGE_QUALITY_CHECK: bool = True
    ENABLE_VIDEO_QUALITY_CHECK: bool = True
    ENABLE_MODERATION: bool = True
    ENABLE_SUBTITLES: bool = True
    ENABLE_BACKGROUND_MUSIC: bool = True
    ENABLE_SOCIAL_MEDIA_COPYWRITING: bool = True

    # Planning
    EXPECTED_TASK_COUNT: int = 11


@dataclass
class VideoGenerationMode:
    """Video generation mode constants."""

    PURE_IMAGE_TO_VIDEO: str = "pure_image_to_video"
    PURE_TEXT_TO_VIDEO: str = "pure_text_to_video"
    MIXED: str = "mixed"

    MODE_DESCRIPTIONS: Dict[str, str] = field(
        default_factory=lambda: {
            "pure_image_to_video": "纯图生视频(所有分镜都是图生视频)",
            "pure_text_to_video": "纯文生视频(所有分镜都是文生视频)",
            "mixed": "混合模式(包含多种类型分镜的组合)",
        }
    )


@dataclass
class ReferenceType:
    """Reference image type constants."""

    CHARACTER: str = "character"
    STYLE: str = "style"
    OBJECT: str = "object"
    MIXED: str = "mixed"
    NONE: str = "none"


@dataclass
class GenerationMode:
    """Image generation mode constants."""

    TEXT_TO_IMAGE: str = "text2image"
    IMAGE_TO_IMAGE: str = "image2image"
    MULTI_IMAGE_FUSION: str = "multi_image_fusion"
    FAILED: str = "failed"


@dataclass
class VideoGenerationType:
    """Scene video generation type constants."""

    IMAGE_TO_VIDEO: str = "image_to_video"


@dataclass
class SubtitleLanguage:
    """Subtitle language constants."""

    CHINESE: str = "zh"
    ENGLISH: str = "en"


CONFIG = VideoGenerationConfig()
MODE = VideoGenerationMode()
REF_TYPE = ReferenceType()
GEN_MODE = GenerationMode()
VIDEO_TYPE = VideoGenerationType()
SUBTITLE_LANG = SubtitleLanguage()


def get_mode_description(mode: str) -> str:
    """Return a human-readable description for a generation mode."""
    return MODE.MODE_DESCRIPTIONS.get(mode, "未知模式")


def normalize_video_engine_name(engine: str) -> str:
    """Return the canonical runtime video engine name."""
    value = (engine or "").strip()
    aliases = {
        "seedance-2.0": "seedance2.0",
        "seedance20": "seedance2.0",
        "seedance_2_0": "seedance2.0",
    }
    return aliases.get(value, value)


def validate_video_engine(engine: str, video_generation_mode: str) -> bool:
    """Validate whether a video engine is currently supported."""
    del video_generation_mode
    return normalize_video_engine_name(engine) in CONFIG.SUPPORTED_VIDEO_ENGINES


def get_recommended_engine(video_generation_mode: str) -> str:
    """Return the default engine for the current runtime."""
    return CONFIG.DEFAULT_VIDEO_ENGINE


__all__ = [
    "VideoGenerationConfig",
    "VideoGenerationMode",
    "ReferenceType",
    "GenerationMode",
    "VideoGenerationType",
    "SubtitleLanguage",
    "CONFIG",
    "MODE",
    "REF_TYPE",
    "GEN_MODE",
    "VIDEO_TYPE",
    "SUBTITLE_LANG",
    "normalize_video_engine_name",
    "get_mode_description",
    "validate_video_engine",
    "get_recommended_engine",
]
