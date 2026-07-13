import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class RunVideoLocalScriptGuardTest(unittest.TestCase):
    def test_run_video_delegates_local_script_capsule_to_unified_dispatch(self):
        (ROOT / "output").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "output") as tmp:
            environment = dict(os.environ)
            environment["OPENCLAW_OUTPUT_DIR"] = tmp
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "run_video.py"),
                    "--user_requirements",
                    "测试本地脚本胶囊路由",
                    "--capsule",
                    "life_sim",
                    "--storyboard_only",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
                timeout=20,
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            final_start = result.stdout.rfind("\n{")
            self.assertGreaterEqual(final_start, 0, result.stdout)
            payload = json.loads(result.stdout[final_start + 1 :])
            workspace = Path(payload["workspace_dir"])
            self.assertTrue(workspace.is_relative_to(Path(tmp).resolve()))
            self.assertEqual(payload["run_status"], "storyboard_only")
            self.assertTrue(
                (workspace / "lifecycle" / "capsule.production-plan.json").is_file()
            )
            self.assertNotIn("run_general_video_flow", result.stderr)


if __name__ == "__main__":
    unittest.main()
