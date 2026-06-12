#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agno 通用视频生成模块
使用 Agno 框架实现的视频生成 Crew
"""

from .crew import AgnoGeneralVideoCrew
from .flow import AgnoGeneralVideoFlow, run_agno_general_video_flow
from .agents import AgnoVideoAgents
from .tasks import AgnoVideoTasks
from .config import (
    CONFIG,
    MODE,
    REF_TYPE,
    GEN_MODE,
    VIDEO_TYPE,
    SUBTITLE_LANG,
    get_mode_description,
    validate_video_engine,
    get_recommended_engine
)

__all__ = [
    # 主要类
    'AgnoGeneralVideoCrew',
    'AgnoGeneralVideoFlow',
    'AgnoVideoAgents',
    'AgnoVideoTasks',

    # 便捷函数
    'run_agno_general_video_flow',

    # 配置
    'CONFIG',
    'MODE',
    'REF_TYPE',
    'GEN_MODE',
    'VIDEO_TYPE',
    'SUBTITLE_LANG',

    # 辅助函数
    'get_mode_description',
    'validate_video_engine',
    'get_recommended_engine',
]
