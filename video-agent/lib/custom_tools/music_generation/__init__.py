"""
音乐生成工具模块
包含AI音乐生成、歌词生成等工具
"""

from .suno_music_tool import (
    SunoMusicTool,
    SunoMusicCustomTool,
    SunoLyricsTool,
    SunoMusicClient
)
from .music_generation_tool import (
    UniversalMusicGenerationTool,
    UniversalLyricsGenerationTool,
    get_supported_providers,
    is_provider_supported
)

__all__ = [
    # Suno专用工具
    'SunoMusicTool',
    'SunoMusicCustomTool',
    'SunoLyricsTool',
    'SunoMusicClient',

    # 通用工具
    'UniversalMusicGenerationTool',
    'UniversalLyricsGenerationTool',

    # 辅助函数
    'get_supported_providers',
    'is_provider_supported',
]
