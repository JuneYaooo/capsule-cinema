"""Local quality checks plus optional Git-ignored analyzers."""

from importlib import import_module

_EXPORTS = {
    "ImageQualityCheckerTool": "custom_tools.quality_check.image_quality_checker_tool",
    "VideoQualityCheckerTool": "custom_tools.quality_check.video_quality_checker_tool",
    "ContentModerationTool": "custom_tools.quality_check.content_moderation_tool",
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
