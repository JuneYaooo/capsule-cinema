import os
import re
from datetime import datetime
from pathlib import Path

from src.utils.output_paths import get_output_base_dir, OUTPUT_ROOT


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"


class WorkspaceManager:
    @staticmethod
    def create_workspace(base_dir=None, workspace_type="video", user_requirements=""):
        base_dir = get_output_base_dir(base_dir)
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(user_requirements)[:32]).strip("_") or "task"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        workspace = Path(base_dir) / f"{workspace_type}_{timestamp}_{slug}"
        work = workspace / "work"
        dirs = {
            "base": workspace,
            "release": workspace / "release",
            "work": work,
            "qa": workspace / "qa",
            "logs": workspace / "logs",
            "images": work / "images",
            "videos": work / "videos",
            "audios": work / "audios",
            "reference_images": work / "reference_images",
            "subtitles": work / "subtitles",
            "temp": work / "temp",
        }
        for path in dirs.values():
            path.mkdir(parents=True, exist_ok=True)
        dirs["final"] = dirs["release"]
        return str(workspace), {key: str(value) for key, value in dirs.items()}
