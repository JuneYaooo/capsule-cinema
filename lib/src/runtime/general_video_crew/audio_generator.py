#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频生成 runtime 模块
负责处理所有与音频生成相关的逻辑
"""

from pathlib import Path
from typing import Dict, List
from src.logger import get_logger
from src.utils.audio_generation_helper import AudioGenerationHelper
from .config import CONFIG

logger = get_logger('audio_generator')


class AudioGenerator:
    """音频生成器"""

    def __init__(self, max_workers: int = None):
        """
        初始化音频生成器

        Args:
            max_workers: 最大并发数，默认使用配置值
        """
        self.max_workers = max_workers or CONFIG.AUDIO_CONCURRENCY

    def generate_audios(
        self,
        storyboard: List[Dict],
        voice_selection: Dict,
        audios_dir: str,
        max_retries: int = None
    ) -> Dict:
        """
        批量生成音频（支持每个分镜使用不同音色,支持并发生成）

        Args:
            storyboard: 分镜列表
            voice_selection: 音色选择结果
            audios_dir: 音频输出目录
            max_retries: 最大重试次数

        Returns:
            音频生成结果字典
        """
        max_retries = max_retries or CONFIG.MAX_RETRIES

        # 构建音色映射表
        voice_map = self._build_voice_map(voice_selection)

        # 使用AudioGenerationHelper进行并发生成
        helper = AudioGenerationHelper(max_workers=self.max_workers)
        return helper.generate_audios_concurrent(
            storyboard=storyboard,
            voice_map=voice_map,
            audios_dir=audios_dir,
            max_retries=max_retries
        )

    def _build_voice_map(self, voice_selection: Dict) -> Dict:
        """
        构建音色映射表

        Args:
            voice_selection: 音色选择结果

        Returns:
            音色映射字典
        """
        voice_mode = voice_selection.get('voice_mode', 'single')
        main_voice = voice_selection.get('main_voice', {})
        character_voices = voice_selection.get('character_voices', [])

        voice_map = {}

        # 添加主音色
        if main_voice:
            main_tag = main_voice.get('character_tag', 'main')
            voice_map[main_tag] = main_voice
            voice_map['main'] = main_voice

        # 添加角色音色
        for cv in character_voices:
            character_tag = cv.get('character_tag', '')
            if character_tag:
                voice_map[character_tag] = cv

        return voice_map

    @staticmethod
    def log_voice_selection(content_requirements: Dict, voice_selection: Dict):
        """
        输出音色选择结果

        Args:
            content_requirements: 内容需求分析结果
            voice_selection: 音色选择结果
        """
        if content_requirements.get('needs_audio', True) and voice_selection:
            voice_type = voice_selection.get('voice_type', '未知')
            speed = voice_selection.get('speed', CONFIG.DEFAULT_VOICE_SPEED)
            logger.info(f"🎙️ 选择的音色: {voice_type}, 语速: {speed}x")
