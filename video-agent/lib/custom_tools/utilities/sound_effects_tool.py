#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音效管理工具
提供音效列表查询功能，供 Agent 使用
"""

import json
from typing import Any, Type, Dict
from pathlib import Path
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from src.utils.sound_effects_utils import SoundEffectsManager
from src.logger import get_logger

logger = get_logger('sound_effects_tool')


class ListSoundEffectsSchema(BaseModel):
    """列出音效文件的输入参数"""
    pass  # 不需要任何参数


class ListSoundEffectsTool(BaseTool):
    name: str = "列出可用音效"
    description: str = (
        "列出音效库中所有可用的音效文件及其适用场景。"
        "音效文件存放在 video_resources/sounds/ 目录中。"
        "使用此工具可以获取最新的音效列表，然后根据分镜内容选择合适的音效。"
    )
    args_schema: Type[BaseModel] = ListSoundEffectsSchema

    def _run(self) -> str:
        """
        列出所有可用的音效文件（动态扫描音效目录）

        Returns:
            包含音效列表的纯文本字符串（避免 JSON 序列化导致的中文编码问题）
        """
        try:
            logger.info("🔊 [ListSoundEffectsTool] 开始扫描音效库...")
            logger.info(f"   📂 音效目录: {SoundEffectsManager.SOUND_EFFECTS_DIR.resolve()}")

            # 获取所有可用音效（会自动打印详细日志）
            sound_effects = SoundEffectsManager.get_available_sound_effects()

            if not sound_effects:
                logger.warning("⚠️ [ListSoundEffectsTool] 音效库为空")
                return "⚠️ 音效库中没有音效文件，请设置 needs_sound_effects = false"

            logger.info(f"🔊 [ListSoundEffectsTool] 找到 {len(sound_effects)} 个音效文件:")
            for sound_file in sound_effects:
                logger.info(f"   - {sound_file}")

            # 返回纯文本格式，避免 JSON 序列化导致的中文编码问题
            # Agno 框架在序列化 dict 时可能会将中文转换为 Unicode 转义序列
            result_text = f"""✅ 找到 {len(sound_effects)} 个音效文件。

【可用音效列表】（你只能从以下列表中选择，严禁编造文件名）：

"""
            for i, sound_file in enumerate(sound_effects, 1):
                result_text += f"{i}. {sound_file}\n"

            result_text += """
【重要提醒】：
- 你必须使用上面列表中的完整文件名（包括 .mp3 后缀）
- 严禁修改文件名或编造不存在的文件
- 如果列表中没有合适的音效，就不要添加
- 示例：如果想要咀嚼音效，请使用 "咀嚼.mp3"（如果存在于列表中）
"""

            logger.info(f"🔊 [ListSoundEffectsTool] ⚠️ 警告：Agent 必须从以上列表中选择，不能编造文件名！")
            logger.info(f"   正确示例：'{sound_effects[0]}' ✅")
            logger.info(f"   错误示例：'常用_脚步声.mp3' ❌（此文件不存在）")

            return result_text

        except Exception as e:
            error_msg = f"列出音效失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return f"❌ {error_msg}，请设置 needs_sound_effects = false"
