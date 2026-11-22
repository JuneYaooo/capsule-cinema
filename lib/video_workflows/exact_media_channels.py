"""Environment-driven media channel resolution for exact paid executors.

Exact routes pin call counts, durations and QA contracts — never a provider.
The channel is resolved from the deployment environment on every run, so
operators decide which channels exist; with no usable channel the executor
fails closed before any paid call is attempted.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from custom_tools.image_generation.local_chybenzun_image_adapter import (
    ChybenzunGptImage2Tool,
)
from custom_tools.video_generation.local_autodl_h3_adapter import (
    AutoDLH3VideoGeneratorTool,
)


def _read_task(path: Path, request_id: str) -> str | None:
    """The saved task of this exact request, so a dropped run collects it instead of paying again."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return str(data["task_id"]) if isinstance(data, dict) and data.get("request_id") == request_id and data.get("task_id") else None


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
        message = self.tool._run(
            prompt=prompt,
            output_path=str(output),
            aspect_ratio=aspect_ratio,
            reference_image_path=str(reference) if reference else None,
        )
        ok = isinstance(message, str) and output.is_file() and "\u5931\u8d25" not in message  # the tool reports failure as text
        return {
            "success": ok,
            "model": self.name,
            "request_id": request_id,
            "attempts": 1,
            "output_path": str(output) if ok else None,
            **({} if ok else {"error": str(message)[:300]}),
        }


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
        checkpoint_path = Path(checkpoint_path)
        saved = _read_task(checkpoint_path, request_id)

        def keep_task(task_id: str) -> None:
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            checkpoint_path.write_text(json.dumps({"request_id": request_id, "task_id": task_id}), encoding="utf-8")

        result = self.tool._run(
            prompt=prompt,
            generation_type="image_to_video",
            output_path=str(output),
            image_path=str(image),
            aspect_ratio=aspect_ratio,
            duration=int(duration),
            poll_interval=8,
            max_wait=1200,
            on_task_id=keep_task,
            resume_task_id=saved,
        )
        if not result.get("success") and not result.get("resumable"):
            checkpoint_path.unlink(missing_ok=True)  # the task ended: nothing left to collect
        return result
