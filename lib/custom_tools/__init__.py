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
    "Gemini3ProImageGeneratorTool": "custom_tools.image_generation",
    "GptImage2Tool": "custom_tools.image_generation",
    "GptImage2ProTool": "custom_tools.image_generation",
    "Gemini3VideoAnalyzer": "custom_tools.quality_check",
    "GenerateAllImagesTool": "custom_tools.image_generation",
    "GenerateAllVideosTool": "custom_tools.video_generation",
    "GenerateSceneImageTool": "custom_tools.image_generation",
    "GenerateVideoFromImageTool": "custom_tools.video_generation",
    "GenerateVideoFromTextTool": "custom_tools.video_generation",
    "GetAudioDurationTool": "custom_tools.video_processing",
    "GetVideoDurationTool": "custom_tools.video_processing",
    "ImageQualityCheckerTool": "custom_tools.quality_check",
    "ImageToVideoFallbackTool": "custom_tools.video_processing",
    "Jimeng35ProVideoGeneratorTool": "custom_tools.video_generation",
    "ListSoundEffectsTool": "custom_tools.utilities",
    "ReadConfigYamlTool": "custom_tools.utilities",
    "ReferenceImageGenerator": "custom_tools.image_generation",
    "ReferenceImageTool": "custom_tools.image_generation",
    "Seedream5ImageGeneratorTool": "custom_tools.image_generation",
    "Seedance20VideoGeneratorTool": "custom_tools.video_generation",
    "SeedanceFastVideoGeneratorTool": "custom_tools.video_generation",
    "SeedanceVideoGeneratorTool": "custom_tools.video_generation",
    "SocialMediaCopywritingTool": "custom_tools.utilities",
    "SubtitleStyleParser": "custom_tools.video_processing",
    "SunoMusicTool": "custom_tools.music_generation",
    "TrimVideoTool": "custom_tools.video_processing",
    "UniversalMusicGenerationTool": "custom_tools.music_generation",
    "UniversalTTSTool": "custom_tools.audio_generation",
    "UniversalTTSBatchTool": "custom_tools.audio_generation",
    "UniversalVideoGenerationTool": "custom_tools.video_generation",
    "Veo3VideoGeneratorTool": "custom_tools.video_generation",
    "Veo31VideoGeneratorTool": "custom_tools.video_generation",
    "VideoFrameExtractor": "custom_tools.video_processing",
    "VideoQualityCheckerTool": "custom_tools.quality_check",
    "VideoSubtitleTool": "custom_tools.video_processing",
    "VideoTimeLengthManager": "custom_tools.video_processing",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_EXPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value
