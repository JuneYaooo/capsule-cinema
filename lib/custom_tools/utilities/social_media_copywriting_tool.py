"""Provider-free packaging of already-authored social copy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Type

from pydantic import BaseModel, Field

from custom_tools.audio_generation.base_tool_compat import BaseTool


class SocialMediaCopywritingToolSchema(BaseModel):
    video_path: str
    video_info: Dict[str, Any] = Field(default_factory=dict)
    platform: str = "douyin"
    output_dir: str


class SocialMediaCopywritingTool(BaseTool):
    name: str = "Package social media copy"
    description: str = "Write provided titles, descriptions, tags, and comments to a local publishing package."
    args_schema: Type[BaseModel] = SocialMediaCopywritingToolSchema

    def _run(self, video_path: str, video_info: Dict[str, Any] | None = None, platform: str = "douyin", output_dir: str = "", **_: Any) -> Dict[str, Any]:
        source = Path(video_path).expanduser()
        if not source.is_file():
            return {"success": False, "error": f"video does not exist: {source}", "copywriting": [], "comments": []}
        info = dict(video_info or {})
        package = {
            "success": True,
            "platform": platform,
            "video_path": str(source),
            "title": info.get("title") or info.get("video_title") or "",
            "description": info.get("description") or info.get("copy") or "",
            "tags": info.get("tags") or [],
            "comments": info.get("comments") or [],
            "generation": "provided_copy_only",
        }
        destination = Path(output_dir).expanduser() / f"{platform}_copywriting.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
        package["saved_path"] = str(destination)
        return package
