import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_video.py"


def load_run_video():
    spec = importlib.util.spec_from_file_location("run_video_for_delivery_intent", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeliveryIntentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_video = load_run_video()

    def test_plain_subtitled_video_does_not_imply_tts_explainer(self):
        self.assertFalse(
            self.run_video.infer_narration_intent(
                "做一个 30 秒竖屏短视频，主题是一只橘猫做饭",
                capsule=None,
            )
        )

    def test_explicit_voiceover_text_implies_tts_explainer(self):
        self.assertTrue(
            self.run_video.infer_narration_intent(
                "做一个 30 秒讲解视频，需要旁白配音",
                capsule=None,
            )
        )

    def test_legacy_flat_has_narration_does_not_imply_tts_explainer(self):
        capsule = {"config": {"has_narration": True}}

        self.assertFalse(
            self.run_video.infer_narration_intent(
                "做一期胶囊视频",
                capsule=capsule,
            )
        )

    def test_capsule_unified_tts_contract_implies_tts_explainer(self):
        capsule = {"config": {"output_contract": {"voice": "unified_tts"}}}

        self.assertTrue(
            self.run_video.infer_narration_intent(
                "做一期胶囊视频",
                capsule=capsule,
            )
        )

    def test_no_narration_capsule_overrides_generic_text(self):
        capsule = {"config": {"output_contract": {"voice": "none"}}}

        self.assertFalse(
            self.run_video.infer_narration_intent(
                "做一个带字幕的视频",
                capsule=capsule,
            )
        )


if __name__ == "__main__":
    unittest.main()
