"""Core tools for the local video-agent runtime.

Keep this package lightweight. Importing ``custom_tools`` should not import
provider SDKs or CrewAI/Agno dependencies; callers that need a tool get it via
lazy attribute loading below.
"""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "AdaptiveSubtitleProcessor": "custom_tools.video_processing",
    "AddBackgroundMusicTool": "custom_tools.video_processing",
    "ArtStyleManagerTool": "custom_tools.utilities",
    "ConcatenateVideosTool": "custom_tools.video_processing",
    "CoverImageGenerator": "custom_tools.image_generation",
    "CoverImageTool": "custom_tools.image_generation",
    "DoubaoTTSTool": "custom_tools.audio_generation",
    "FlexibleSubtitleProcessor": "custom_tools.video_processing",
    "VolcengineImageGeneratorTool": "custom_tools.image_generation",
    "GenerateAllImagesTool": "custom_tools.image_generation",
    "GenerateAllVideosTool": "custom_tools.video_generation",
    "GenerateSceneImageTool": "custom_tools.image_generation",
    "GenerateVideoFromImageTool": "custom_tools.video_generation",
    "GenerateVideoFromTextTool": "custom_tools.video_generation",
    "GetAudioDurationTool": "custom_tools.video_processing",
    "GetVideoDurationTool": "custom_tools.video_processing",
    "ImageQualityCheckerTool": "custom_tools.quality_check",
    "ImageToVideoFallbackTool": "custom_tools.video_processing",
    "ListSoundEffectsTool": "custom_tools.utilities",
    "ReadConfigYamlTool": "custom_tools.utilities",
    "ReferenceImageGenerator": "custom_tools.image_generation",
    "ReferenceImageTool": "custom_tools.image_generation",
    "Seedance20VideoGeneratorTool": "custom_tools.video_generation",
    "SocialMediaCopywritingTool": "custom_tools.utilities",
    "SubtitleStyleParser": "custom_tools.video_processing",
    "TrimVideoTool": "custom_tools.video_processing",
    "UniversalTTSTool": "custom_tools.audio_generation",
    "UniversalTTSBatchTool": "custom_tools.audio_generation",
    "UniversalVideoGenerationTool": "custom_tools.video_generation",
    "VideoFrameExtractor": "custom_tools.video_processing",
    "VideoQualityCheckerTool": "custom_tools.quality_check",
    "VideoSubtitleTool": "custom_tools.video_processing",
    "VideoTimeLengthManager": "custom_tools.video_processing",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    module_path = _EXPORTS.get(name)
    if module_path is None:
        from src.config_registry import load_tool_registry

        module_path = (load_tool_registry().get(name) or {}).get("module")
    if not module_path:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_path)
    value = getattr(module, name)
    globals()[name] = value
    return value
