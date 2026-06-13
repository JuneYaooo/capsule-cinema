import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASE_MANIFEST_PATH = ROOT / "scripts" / "release_manifest.py"


def load_release_manifest():
    spec = importlib.util.spec_from_file_location("release_manifest", RELEASE_MANIFEST_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_release_manifest()

    def test_builds_minimal_manifest_from_workspace_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "release").mkdir()
            (workspace / "release" / "final_video.mp4").write_bytes(b"video")
            (workspace / "release" / "cover.png").write_bytes(b"cover")
            (workspace / "release" / "qa_report.json").write_text("{}", encoding="utf-8")
            (workspace / "storyboard.json").write_text("{}", encoding="utf-8")

            data = self.manifest.build_release_manifest(
                workspace,
                capsule_name="demo",
                toolchain={"video": "jimeng35pro"},
                created_at="2026-01-01T00:00:00+00:00",
            )

            self.assertEqual(list(data.keys()), self.manifest.MANIFEST_FIELDS)
            self.assertTrue(data["workspace"].endswith(tmp))
            self.assertTrue(data["final_video"].endswith("release/final_video.mp4"))
            self.assertTrue(data["cover"].endswith("release/cover.png"))
            self.assertTrue(data["storyboard_path"].endswith("storyboard.json"))
            self.assertEqual(len(data["qa_paths"]), 1)
            self.assertEqual(data["capsule_name"], "demo")
            self.assertEqual(data["toolchain"]["video"], "jimeng35pro")

    def test_writes_manifest_to_release_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            output = self.manifest.write_release_manifest(workspace, capsule_name="demo")

            self.assertEqual(output, workspace / "release" / "release_manifest.json")
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["capsule_name"], "demo")


if __name__ == "__main__":
    unittest.main()
