import os
import shutil
import sys
import tempfile
import unittest
from uuid import uuid4
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from src.utils.workspace_utils import WorkspaceManager  # noqa: E402


class WorkspaceArtifactContractTest(unittest.TestCase):
    def test_standard_workspace_layout_is_created(self):
        old_output = os.environ.get("OPENCLAW_OUTPUT_DIR")
        output_base = ROOT / "output" / f"test_workspace_contract_{uuid4().hex}"
        try:
            os.environ["OPENCLAW_OUTPUT_DIR"] = str(output_base)
            workspace, dirs = WorkspaceManager.create_workspace(
                workspace_type="general_video",
                user_requirements="standard layout",
            )

            output_root = (ROOT / "output").resolve()
            self.assertTrue(Path(workspace).resolve().is_relative_to(output_root))
            self.assertNotIn("final", dirs)
            for key in ["work", "images", "videos", "audios", "reference_images", "release", "qa", "logs"]:
                self.assertTrue(Path(dirs[key]).is_dir(), f"{key} should exist")
            self.assertTrue(Path(dirs["images"]).as_posix().endswith("/work/images"))
            self.assertTrue(Path(dirs["videos"]).as_posix().endswith("/work/videos"))
            self.assertTrue(Path(dirs["release"]).as_posix().endswith("/release"))
        finally:
            shutil.rmtree(output_base, ignore_errors=True)
            if old_output is None:
                os.environ.pop("OPENCLAW_OUTPUT_DIR", None)
            else:
                os.environ["OPENCLAW_OUTPUT_DIR"] = old_output

    def test_external_output_root_is_rejected(self):
        old_output = os.environ.get("OPENCLAW_OUTPUT_DIR")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["OPENCLAW_OUTPUT_DIR"] = tmp
                with self.assertRaises(ValueError):
                    WorkspaceManager.create_workspace(
                        workspace_type="general_video",
                        user_requirements="external layout",
                    )
        finally:
            if old_output is None:
                os.environ.pop("OPENCLAW_OUTPUT_DIR", None)
            else:
                os.environ["OPENCLAW_OUTPUT_DIR"] = old_output


if __name__ == "__main__":
    unittest.main()
