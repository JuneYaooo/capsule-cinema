"""Compatibility aliases for the canonical general-video runtime generators."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "AudioGenerator": "audio_generator",
    "ImageGenerator": "image_generator",
    "PostProcessor": "post_processor",
    "VideoGenerator": "video_generator",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"{__name__}.{_EXPORTS[name]}")
    value = getattr(module, name)
    globals()[name] = value
    return value
