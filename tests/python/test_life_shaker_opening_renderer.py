import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RENDERER_PATH = ROOT / "capsules" / "life_sim.capsule" / "assets" / "life_shaker_opening_renderer.py"


def load_renderer():
    spec = importlib.util.spec_from_file_location("life_shaker_opening_renderer", RENDERER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


class LifeShakerOpeningRendererTest(unittest.TestCase):
    def test_provided_candidate_terms_are_not_padded_with_defaults(self):
        renderer = load_renderer()
        terms = ["稳赢幻觉", "补时三分钟", "追回一次", "账单先到", "删掉入口"]

        display_terms = renderer.candidate_terms_for_display(terms)

        self.assertEqual(display_terms, terms)
        self.assertNotIn("夜班英雄", display_terms)

    def test_empty_candidate_terms_fall_back_to_defaults(self):
        renderer = load_renderer()

        self.assertEqual(renderer.candidate_terms_for_display([]), renderer.DEFAULT_CANDIDATES)

    def test_default_audio_timing_matches_capsule_opening_policy(self):
        renderer = load_renderer()

        parser = renderer.build_parser()
        args = parser.parse_args(["--background", "bg.png", "--output", "opening.mp4"])

        self.assertEqual(args.tts_start, 0.0)
        self.assertEqual(args.sfx_volume, 0.35)


if __name__ == "__main__":
    unittest.main()
