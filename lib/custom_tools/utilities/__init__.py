"""Utility tools with lazy local-overlay support."""

from importlib import import_module

_EXPORTS = {
    "ReadConfigYamlTool": "custom_tools.utilities.read_config_yaml_tool",
    "SocialMediaCopywritingTool": "custom_tools.utilities.social_media_copywriting_tool",
    "ArtStyleManagerTool": "custom_tools.utilities.art_style_manager_tool",
    "ListSoundEffectsTool": "custom_tools.utilities.sound_effects_tool",
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
