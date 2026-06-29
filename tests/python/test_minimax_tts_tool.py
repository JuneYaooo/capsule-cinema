import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))


class MiniMaxTTSToolTest(unittest.TestCase):
    def test_direct_minimax_voice_id_is_passed_through(self):
        from custom_tools.audio_generation.minimax_tts_tool import _resolve_minimax_voice_id

        self.assertEqual(
            _resolve_minimax_voice_id("Chinese (Mandarin)_Radio_Host"),
            "Chinese (Mandarin)_Radio_Host",
        )

    def test_doubao_style_voice_id_still_maps_to_minimax_fallback(self):
        from custom_tools.audio_generation.minimax_tts_tool import _resolve_minimax_voice_id

        self.assertEqual(
            _resolve_minimax_voice_id("zh_male_sunwukong_mars_bigtts"),
            "male-qn-daxuesheng",
        )

    def test_life_sim_historical_male_narrator_alias_maps_to_minimax_voice(self):
        from custom_tools.audio_generation.minimax_tts_tool import _resolve_minimax_voice_id

        self.assertEqual(_resolve_minimax_voice_id("male_narrator"), "audiobook_male_2")


if __name__ == "__main__":
    unittest.main()
