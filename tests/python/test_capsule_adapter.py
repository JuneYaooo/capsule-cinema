import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from src.capsule_adapter import reconcile  # noqa: E402


class ReconcileAudioTest(unittest.TestCase):
    def test_silent_contract_with_native_audio_tool_mutes_and_adds_negatives(self):
        directive = reconcile({"clip_audio": "silent"}, {"flags": {"native_audio": True}})

        self.assertIn("mute_audio", directive.post_steps)
        self.assertIn("no speech", directive.prompt_negatives)
        self.assertTrue(directive.notes)

    def test_silent_contract_with_silent_tool_is_noop(self):
        directive = reconcile({"clip_audio": "silent"}, {"flags": {"native_audio": False}})

        self.assertEqual(directive.post_steps, [])
        self.assertEqual(directive.prompt_negatives, [])

    def test_native_contract_is_noop(self):
        directive = reconcile({"clip_audio": "native"}, {"flags": {"native_audio": True}})

        self.assertEqual(directive.post_steps, [])
        self.assertEqual(directive.prompt_negatives, [])

    def test_native_contract_blocks_when_tool_has_no_native_audio(self):
        directive = reconcile({"clip_audio": "native"}, {"flags": {"native_audio": False}})

        self.assertIn("native_audio", directive.blocked)

    def test_sfx_only_contract_blocks_without_voice_stripping_support(self):
        directive = reconcile({"clip_audio": "sfx_only"}, {"flags": {"native_audio": True}})

        self.assertIn("strip_voice_post_processor", directive.blocked)
        self.assertNotIn("strip_voice", directive.post_steps)


class ReconcileOnFrameTextTest(unittest.TestCase):
    def test_required_text_is_blocked_until_image_runtime_consumes_directives(self):
        directive = reconcile(
            {"on_frame_text": "required"},
            {"enums": {"text_rendering": "reliable"}},
        )

        self.assertIn("on_frame_text_runtime", directive.blocked)
        self.assertEqual(directive.post_steps, [])
        self.assertEqual(directive.prompt_additions, [])

    def test_required_text_overlay_fallback_is_blocked_until_overlay_runtime_exists(self):
        directive = reconcile(
            {"on_frame_text": "required", "on_frame_text_fallback": "overlay"},
            {"enums": {"text_rendering": "unreliable"}},
        )

        self.assertIn("overlay_text_runtime", directive.blocked)
        self.assertNotIn("overlay_text", directive.post_steps)
        self.assertTrue(directive.notes)

    def test_no_on_frame_text_is_noop(self):
        directive = reconcile({"on_frame_text": "none"}, {"enums": {"text_rendering": "unreliable"}})

        self.assertEqual(directive.post_steps, [])
        self.assertEqual(directive.prompt_additions, [])


if __name__ == "__main__":
    unittest.main()
