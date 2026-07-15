"""Image tools with lazy public and local-overlay resolution."""

from importlib import import_module


_EXPORTS = {
    "VolcengineImageGeneratorTool": "custom_tools.image_generation.volcengine_image_generator_tool",
    "CoverImageTool": "custom_tools.image_generation.cover_image_tool",
    "CoverImageGenerator": "custom_tools.image_generation.cover_image_tool",
    "ReferenceImageTool": "custom_tools.image_generation.reference_image_tool",
    "ReferenceImageGenerator": "custom_tools.image_generation.reference_image_tool",
    "GenerateSceneImageTool": "custom_tools.image_generation.image_generation_tool",
    "GenerateAllImagesTool": "custom_tools.image_generation.image_generation_tool",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    module_path = _EXPORTS.get(name)
    if module_path is None:
        from src.config_registry import load_tool_registry

        record = load_tool_registry().get(name) or {}
        module_path = record.get("module")
    if not module_path:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value
