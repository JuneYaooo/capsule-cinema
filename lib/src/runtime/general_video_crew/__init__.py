"""Canonical runtime generators for the general-video pipeline."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "AudioGenerator": ".audio_generator",
    "ImageGenerator": ".image_generator",
    "PostProcessor": ".post_processor",
    "VideoGenerator": ".video_generator",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_EXPORTS[name], __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
