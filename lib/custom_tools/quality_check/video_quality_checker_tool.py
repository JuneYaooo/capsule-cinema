"""Provider-free local video sanity checks."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Type

from pydantic import BaseModel, Field

from custom_tools.audio_generation.base_tool_compat import BaseTool


class VideoQualityCheckerSchema(BaseModel):
    video_path: str = Field(..., description="Local video file")
    check_focus: str = Field("quality", description="Technical check focus")


class VideoQualityCheckerTool(BaseTool):
    name: str = "Local video quality checker"
    description: str = "Run provider-free ffprobe checks for playability, dimensions, duration, and streams."
    args_schema: Type[BaseModel] = VideoQualityCheckerSchema

    def _run(self, video_path: str, check_focus: str = "quality", **_: Any) -> dict[str, Any]:
        source = Path(video_path).expanduser()
        if not source.is_file():
            return {"success": False, "has_issues": True, "needs_regeneration": True, "quality_score": 0, "issues": [{"type": "missing_file", "severity": "blocker", "description": str(source)}]}
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)],
                check=True,
                capture_output=True,
                text=True,
            )
            metadata = json.loads(probe.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError, OSError) as exc:
            return {"success": False, "has_issues": True, "needs_regeneration": True, "quality_score": 0, "issues": [{"type": "unreadable_media", "severity": "blocker", "description": exc.__class__.__name__}]}
        streams = metadata.get("streams") or []
        video_stream = next((item for item in streams if item.get("codec_type") == "video"), {})
        duration = float((metadata.get("format") or {}).get("duration") or 0)
        width = int(video_stream.get("width") or 0)
        height = int(video_stream.get("height") or 0)
        issues = []
        if duration <= 0:
            issues.append({"type": "invalid_duration", "severity": "blocker", "description": "duration is zero"})
        if width <= 0 or height <= 0:
            issues.append({"type": "invalid_dimensions", "severity": "blocker", "description": f"{width}x{height}"})
        return {
            "success": not issues,
            "check_type": "local_technical",
            "check_focus": check_focus,
            "has_issues": bool(issues),
            "needs_regeneration": bool(issues),
            "quality_score": 0 if issues else 8,
            "issues": issues,
            "metadata": {"duration": duration, "width": width, "height": height, "size_bytes": source.stat().st_size},
        }
