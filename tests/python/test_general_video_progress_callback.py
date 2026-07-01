import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
SCRIPT = ROOT / "scripts" / "run_video.py"

if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from video_workflows.general_video.crew import AgnoGeneralVideoCrew  # noqa: E402
from video_workflows.general_video.flow import AgnoGeneralVideoFlow  # noqa: E402


def load_run_video():
    spec = importlib.util.spec_from_file_location("run_video_for_progress_callback", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GeneralVideoProgressCallbackTest(unittest.TestCase):
    def test_run_video_emits_progress_event_to_original_stdout(self):
        run_video = load_run_video()
        captured = io.StringIO()
        redirected_stdout = io.StringIO()
        original_stdout = sys.__stdout__
        try:
            sys.__stdout__ = captured
            with contextlib.redirect_stdout(redirected_stdout):
                run_video.emit_progress_event("workspace_created", workspace_dir="/tmp/capsule/work")
        finally:
            sys.__stdout__ = original_stdout

        self.assertEqual(redirected_stdout.getvalue(), "")
        self.assertEqual(
            json.loads(captured.getvalue().strip()),
            {"event": "workspace_created", "workspace_dir": "/tmp/capsule/work"},
        )

    def test_flow_forwards_progress_callback_to_crew_state(self):
        calls = []

        class FakeCrew:
            def kickoff(self, state):
                calls.append(state)
                return {
                    "success": True,
                    "workspace_dir": "/tmp/capsule/work",
                    "output_paths": {},
                    "storyboard": [],
                    "storyboard_path": "/tmp/capsule/work/storyboard.json",
                    "video_title": "Progress Test",
                    "planning_results": {},
                }

        callback = lambda event, **payload: None
        flow = AgnoGeneralVideoFlow.__new__(AgnoGeneralVideoFlow)
        flow.crew = FakeCrew()

        result = flow.run(
            "做一个进度测试视频",
            target_duration=30,
            storyboard_only=True,
            progress_callback=callback,
        )

        self.assertTrue(result["success"])
        self.assertIs(calls[0].get("progress_callback"), callback)

    def test_crew_emits_workspace_created_after_setup(self):
        crew = AgnoGeneralVideoCrew.__new__(AgnoGeneralVideoCrew)
        events = []

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            def fake_setup_workspace(video_name, base_dir=None):
                crew.workspace_dir = workspace
                crew.output_paths = {"work": str(workspace / "work")}
                return crew.output_paths

            def stop_after_workspace(user_requirements, target_duration, state=None):
                raise RuntimeError("stop after workspace")

            crew.workspace_dir = None
            crew.output_paths = {}
            crew.setup_workspace = fake_setup_workspace
            crew.run_planning_phase = stop_after_workspace

            result = crew.kickoff({
                "user_requirements": "做一个进度测试视频",
                "target_duration": 30,
                "progress_callback": lambda event, **payload: events.append((event, payload)),
            })

        self.assertFalse(result["success"])
        self.assertEqual(
            events,
            [("workspace_created", {"workspace_dir": str(workspace)})],
        )


if __name__ == "__main__":
    unittest.main()
