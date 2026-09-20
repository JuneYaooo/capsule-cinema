"""Environment-driven media channel resolution for exact paid executors.

Exact routes pin call counts, durations and QA contracts — never a provider.
The channel is resolved from the deployment environment on every run, so
operators decide which channels exist; with no usable channel the executor
fails closed before any paid call is attempted.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from custom_tools.image_generation.local_chybenzun_image_adapter import (
    ChybenzunGptImage2Tool,
)
from custom_tools.video_generation.local_autodl_h3_adapter import (
    AutoDLH3VideoGeneratorTool,
)


class ExactChannelError(RuntimeError):
    """Raised when no environment-configured channel can serve a role."""


def _configured(*names: str) -> bool:
    return all(os.getenv(name, "").strip() for name in names)


def resolve_image_channel() -> tuple[str, Any]:
    """Resolve the image channel from the environment, fail-closed."""

    if _configured("CHYBENZUN_GPT_IMAGE2_API_KEY", "CHYBENZUN_GPT_IMAGE2_BASE_URL"):
        return "gpt-image-2", ChybenzunGptImage2Tool()
    raise ExactChannelError(
        "no environment-configured image channel: expected "
        "CHYBENZUN_GPT_IMAGE2_API_KEY/CHYBENZUN_GPT_IMAGE2_BASE_URL (gpt-image-2)"
    )


def resolve_video_channel() -> tuple[str, Any]:
    """Resolve the video channel from the environment, fail-closed."""

    if _configured("AUTODL_ART_TOKEN"):
        return "autodl_h3", AutoDLH3VideoGeneratorTool()
    raise ExactChannelError(
        "no environment-configured video channel: expected AUTODL_ART_TOKEN (AutoDL H3)"
    )


class ExactImageChannel:
    """Uniform image-call surface over the resolved channel tool."""

    def __init__(self) -> None:
        self.name, self.tool = resolve_image_channel()

    def generate(
        self,
        *,
        prompt: str,
        output: Path,
        aspect_ratio: str,
        request_id: str,
        reference: Path | None = None,
    ) -> dict[str, Any]:
        return self.tool._run(
            prompt=prompt,
            output_path=str(output),
            aspect_ratio=aspect_ratio,
            output_format="png",
            response_format="b64_json",
            watermark=False,
            request_id=request_id,
            reference_image_path=str(reference) if reference else None,
        )


class ExactVideoChannel:
    """Uniform video-call surface over the resolved channel tool.

    H3 clips are silent; scene audio comes from the executors' local mixing
    pipeline, so ``native_audio`` is accepted for contract compatibility and
    ignored.
    """

    def __init__(self) -> None:
        self.name, self.tool = resolve_video_channel()

    def generate(
        self,
        *,
        prompt: str,
        image: Path,
        output: Path,
        duration: int,
        aspect_ratio: str,
        request_id: str,
        checkpoint_path: Path,
        native_audio: bool = False,
    ) -> dict[str, Any]:
        return self.tool._run(
            prompt=prompt,
            generation_type="image_to_video",
            output_path=str(output),
            image_path=str(image),
            aspect_ratio=aspect_ratio,
            duration=int(duration),
            watermark=False,
            poll_interval=8,
            max_wait=1200,
            checkpoint_path=str(checkpoint_path),
            request_id=request_id,
        )
