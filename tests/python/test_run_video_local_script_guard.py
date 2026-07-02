import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class RunVideoLocalScriptGuardTest(unittest.TestCase):
    def test_run_video_refuses_local_script_capsule_without_explicit_fallback(self):
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
        )

        self.assertNotEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        self.assertIn("requires local_script execution", combined)
        self.assertIn("scripts/run_capsule.py", combined)
        self.assertNotIn("run_general_video_flow", combined)


if __name__ == "__main__":
    unittest.main()
