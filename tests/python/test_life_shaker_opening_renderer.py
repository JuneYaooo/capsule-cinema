import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RENDERER_PATH = ROOT / "capsule_assets" / "life_sim" / "templates" / "life_shaker_opening_renderer.py"


def load_renderer():
    spec = importlib.util.spec_from_file_location("life_shaker_opening_renderer", RENDERER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_provided_candidate_terms_are_not_padded_with_defaults():
    renderer = load_renderer()
    terms = ["稳赢幻觉", "补时三分钟", "追回一次", "账单先到", "删掉入口"]

    display_terms = renderer.candidate_terms_for_display(terms)

    assert display_terms == terms
    assert "夜班英雄" not in display_terms


def test_empty_candidate_terms_fall_back_to_defaults():
    renderer = load_renderer()

    assert renderer.candidate_terms_for_display([]) == renderer.DEFAULT_CANDIDATES


def test_default_audio_timing_matches_capsule_opening_policy():
    renderer = load_renderer()

    parser = renderer.build_parser()
    args = parser.parse_args(["--background", "bg.png", "--output", "opening.mp4"])

    assert args.tts_start == 0.0
    assert args.sfx_volume == 0.35
