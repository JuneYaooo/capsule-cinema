"""Provider-free local image sanity checks."""

from pathlib import Path
from typing import Any, Type

from PIL import Image
from pydantic import BaseModel, Field

from custom_tools.audio_generation.base_tool_compat import BaseTool


class ImageQualityCheckerSchema(BaseModel):
    image_path: str
    original_prompt: str = ""
    check_focus: str = "quality"


class ImageQualityCheckerTool(BaseTool):
    name: str = "Local image quality checker"
    description: str = "Check that a local image is readable and has usable dimensions."
    args_schema: Type[BaseModel] = ImageQualityCheckerSchema

    def _run(self, image_path: str, original_prompt: str = "", check_focus: str = "quality", **_: Any) -> dict[str, Any]:
        source = Path(image_path).expanduser()
        issues = []
        try:
            with Image.open(source) as image:
                image.verify()
            with Image.open(source) as image:
                width, height = image.size
                mode = image.mode
            if width < 256 or height < 256:
                issues.append({"type": "low_resolution", "severity": "high", "description": f"{width}x{height}"})
        except (OSError, FileNotFoundError) as exc:
            return {"success": False, "has_issues": True, "needs_regeneration": True, "quality_score": 0, "issues": [{"type": "unreadable_image", "severity": "blocker", "description": exc.__class__.__name__}]}
        return {"success": not issues, "check_type": "local_technical", "check_focus": check_focus, "has_issues": bool(issues), "needs_regeneration": bool(issues), "quality_score": 5 if issues else 8, "issues": issues, "metadata": {"width": width, "height": height, "mode": mode, "prompt_present": bool(original_prompt)}}
