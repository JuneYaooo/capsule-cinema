"""Video tools with lazy public and local-overlay resolution."""

from importlib import import_module


_EXPORTS = {
    "VolcengineSeedanceVideoGeneratorTool": "custom_tools.video_generation.volcengine_seedance_video_generator_tool",
    "Seedance20VideoGeneratorTool": "custom_tools.video_generation.volcengine_seedance_video_generator_tool",
    "GenerateVideoFromTextTool": "custom_tools.video_generation.video_generation_tool",
    "GenerateVideoFromImageTool": "custom_tools.video_generation.video_generation_tool",
    "GenerateAllVideosTool": "custom_tools.video_generation.video_generation_tool",
    "UniversalVideoGenerationTool": "custom_tools.video_generation.video_generation_tool",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    module_path = _EXPORTS.get(name)
    if module_path is None:
        from src.config_registry import load_tool_registry

        module_path = (load_tool_registry().get(name) or {}).get("module")
    if not module_path:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value
