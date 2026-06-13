import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from src.utils.workspace_utils import WorkspaceManager  # noqa: E402


class WorkspaceArtifactContractTest(unittest.TestCase):
    def test_standard_workspace_layout_is_created(self):
        old_output = os.environ.get("OPENCLAW_OUTPUT_DIR")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["OPENCLAW_OUTPUT_DIR"] = tmp
                workspace, dirs = WorkspaceManager.create_workspace(
                    workspace_type="general_video_agno",
                    user_requirements="standard layout",
                )

                self.assertTrue(str(workspace).startswith(tmp))
                self.assertEqual(dirs["final"], dirs["release"])
                for key in ["work", "images", "videos", "audios", "reference_images", "release", "qa", "logs"]:
                    self.assertTrue(Path(dirs[key]).is_dir(), f"{key} should exist")
                self.assertTrue(Path(dirs["images"]).as_posix().endswith("/work/images"))
                self.assertTrue(Path(dirs["videos"]).as_posix().endswith("/work/videos"))
                self.assertTrue(Path(dirs["release"]).as_posix().endswith("/release"))
        finally:
            if old_output is None:
                os.environ.pop("OPENCLAW_OUTPUT_DIR", None)
            else:
                os.environ["OPENCLAW_OUTPUT_DIR"] = old_output


if __name__ == "__main__":
    unittest.main()
