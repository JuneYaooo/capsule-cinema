import json
from pathlib import Path

from src.utils.workspace_utils import WorkspaceManager


class BaseVideoFlow:
    def __init__(self):
        self.state = {}

    def _setup_workspace(self, workspace_type="video", user_requirements="unknown"):
        workspace_dir, output_dirs = WorkspaceManager.create_workspace(
            base_dir="output",
            workspace_type=workspace_type,
            user_requirements=user_requirements,
        )
        self.state["workspace_dir"] = workspace_dir
        self.state["output_dirs"] = output_dirs
        return workspace_dir, output_dirs

    def _save_storyboard_json(self, storyboard, reference_design=None):
        workspace_dir = Path(self.state.get("workspace_dir", "output"))
        workspace_dir.mkdir(parents=True, exist_ok=True)
        path = workspace_dir / "storyboard.json"
        payload = {
            "storyboard": storyboard,
            "reference_design": reference_design or {},
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

