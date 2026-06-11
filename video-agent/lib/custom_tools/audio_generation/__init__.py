"""Audio-generation tools.

This module intentionally avoids eager imports. ``minimax_tts_tool`` is a
lightweight fallback/helper and must remain importable without loading Doubao,
CrewAI, or the full universal TTS tool stack.
"""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "DoubaoTTSClient": "custom_tools.audio_generation.doubao_tts_tool",
    "DoubaoTTSTool": "custom_tools.audio_generation.doubao_tts_tool",
    "UniversalTTSBatchTool": "custom_tools.audio_generation.tts_tool",
    "UniversalTTSTool": "custom_tools.audio_generation.tts_tool",
    "WhisperLyricsExtractorTool": "custom_tools.audio_generation.whisper_lyrics_extractor",
    "extract_lyrics_from_audio": "custom_tools.audio_generation.whisper_lyrics_extractor",
    "get_supported_providers": "custom_tools.audio_generation.tts_tool",
    "is_provider_supported": "custom_tools.audio_generation.tts_tool",
    "synthesize_with_minimax": "custom_tools.audio_generation.minimax_tts_tool",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_EXPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value
