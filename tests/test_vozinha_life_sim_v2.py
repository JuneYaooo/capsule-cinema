import importlib.util
import inspect
import sys
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "output" / "vozinha_life_sim" / "scripts" / "render_vozinha_life_sim.py"


def load_render_module():
    spec = importlib.util.spec_from_file_location("render_vozinha_life_sim", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_timeline_uses_fast_life_sim_microcuts():
    module = load_render_module()
    timeline = module.build_timeline(150.0)
    body = [item for item in timeline if not item["key"].startswith("INTRO")]
    durations = [round(item["end"] - item["start"], 3) for item in body]

    assert [item["key"] for item in timeline[:4]] == [
        "INTRO_SERIES",
        "INTRO_HINT",
        "INTRO_ROLL",
        "INTRO_LOCK",
    ]
    assert timeline[0]["text"] == "每天体验一种人生。"
    assert timeline[1]["text"] == "今天体验的是佛得角门将沃齐尼亚的人生。"
    assert timeline[0]["start"] == 0.0
    assert timeline[0]["end"] == module.INTRO_SERIES_END
    assert timeline[1]["start"] == module.INTRO_SERIES_END
    assert timeline[1]["end"] == module.INTRO_HINT_END
    assert timeline[2]["start"] == module.INTRO_HINT_END
    assert timeline[2]["end"] == module.INTRO_ROLL_END
    assert timeline[3]["start"] == module.INTRO_ROLL_END
    assert timeline[3]["end"] == module.INTRO_DURATION
    assert module.INTRO_DURATION >= 5.4
    assert len(body) >= 60
    assert max(durations) <= 3.0
    assert min(durations) >= 1.0
    assert sum(d <= 3.0 for d in durations) / len(durations) >= 0.95
    assert abs(timeline[-1]["end"] - 150.0) < 0.01


def test_timeline_has_semantic_visual_intents():
    module = load_render_module()
    timeline = module.build_timeline(150.0)
    body = [item for item in timeline if not item["key"].startswith("INTRO")]

    required = {"visual_key", "visual_intent", "text", "title"}
    assert all(required.issubset(item.keys()) for item in body)
    assert any("明德卢" in item["text"] and "海风" in item["visual_intent"] for item in body)
    assert any("七次扑救" in item["text"] and "扑救" in item["visual_intent"] for item in body)
    assert any("母亲" in item["text"] and "母亲" in item["visual_intent"] for item in body)


def test_life_sim_opening_uses_fixed_series_copy():
    module = load_render_module()

    assert module.SERIES_TITLE == "每天体验一种人生"
    assert module.INTRO_HINT == "今天体验的是"
    assert module.INTRO_RESULT == "佛得角门将沃齐尼亚的人生"
    assert module.INTRO_NARRATION == "每天体验一种人生。今天体验的是佛得角门将沃齐尼亚的人生。"
    assert module.NARRATION.startswith("每天体验一种人生。今天体验的是")
    assert "每天一个模拟人生" not in "\n".join(module.opening_visible_copy())
    assert "今天抽到" not in "\n".join(module.opening_visible_copy())


def test_timeline_uses_many_distinct_visual_sources():
    module = load_render_module()
    timeline = module.build_timeline(196.596)
    body = [item for item in timeline if not item["key"].startswith("INTRO")]
    visual_keys = [item["visual_key"] for item in body]
    counts = {key: visual_keys.count(key) for key in set(visual_keys)}

    assert len(module.VISUALS) >= 35
    assert len(set(visual_keys)) >= 35
    assert max(counts.values()) <= 4


def test_repeated_story_sections_use_extra_scene_masters():
    module = load_render_module()
    timeline = module.build_timeline(196.596)
    body = [item for item in timeline if not item["key"].startswith("INTRO")]
    groups = [module.visual_group_key(item["visual_key"]) for item in body]
    max_run = 1
    current_run = 1
    for previous, current in zip(groups, groups[1:]):
        if current == previous:
            current_run += 1
        else:
            max_run = max(max_run, current_run)
            current_run = 1
    max_run = max(max_run, current_run)

    scene_masters = {visual.key for visual in module.BASE_VISUALS}
    assert {
        "mindelo_market_morning",
        "childhood_red_dust_dive",
        "local_club_gate",
        "career_passport_table",
        "praia_bar_watchparty",
        "global_search_room",
    }.issubset(scene_masters)
    assert max_run <= 4


def test_visual_style_contract_selectively_regenerates_bad_keyframes():
    module = load_render_module()
    prepare_source = inspect.getsource(module.prepare_visual_assets)
    variant_source = inspect.getsource(module.create_visual_variant)

    assert module.VERSION == "vozinha_life_sim_20260622_v11_more_scenes_sentence_subtitles"
    assert module.VISUAL_GENERATION_MODE == "selective_regenerate_non_anime_or_bad_bases"
    assert module.USE_ORIGINAL_GPT_IMAGE2_KEYFRAMES is False
    assert module.EXTERNAL_IMAGE_GENERATION_ENABLED is True
    assert module.REGENERATE_BASE_VISUALS is False
    assert module.IMAGE_GENERATION_FALLBACK_TO_PREVIOUS is False
    assert module.BASE_VISUAL_REUSE_MODE == "reuse_originals_except_flagged_bases"
    assert set(module.SELECTIVE_REGENERATE_BASE_KEYS) == set(module.NEW_SCENE_BASE_KEYS)
    assert set(module.SELECTIVE_REGENERATE_BASE_KEYS).issubset({visual.key for visual in module.BASE_VISUALS})
    assert all("not photorealistic" in module.unified_anime_prompt(visual) for visual in module.BASE_VISUALS)
    mindelo = next(visual for visual in module.BASE_VISUALS if visual.key == "mindelo_harbor")
    assert "不要成年男性特写" in module.unified_anime_prompt(mindelo)
    assert "SELECTIVE_REGENERATE_BASE_KEYS" in prepare_source
    assert "shutil.copy2" in prepare_source
    assert "anime_unify" not in prepare_source
    assert "ImageEnhance" not in variant_source
    assert "GaussianBlur" not in variant_source


def test_subtitle_events_do_not_split_words_or_names():
    module = load_render_module()
    timeline = module.build_timeline(196.596)
    subtitle_events = module.build_subtitle_events(timeline)
    subtitles = [event[2].replace("\\N", "") for event in subtitle_events]

    assert any("1986年6月3日，你出生在佛得角圣维森特岛。" in item for item in subtitles)
    assert any("从Batuque到Mindelense。" in item for item in subtitles)
    assert any("佩德里、亚马尔、罗德里，名字像浪头压来。" in item for item in subtitles)
    assert any("全世界突然搜索，Vozinha是谁。" in item for item in subtitles)
    assert all("你出" != item for item in subtitles)
    assert all("V" != item and "ozinha是谁。" != item for item in subtitles)
    assert all("换" != item and "成世界最响掌声。" != item for item in subtitles)


def test_subtitle_alignment_report_uses_stt_timing_evidence():
    module = load_render_module()
    source = inspect.getsource(module.write_subtitle_alignment_report)
    timeline_source = inspect.getsource(module.build_timeline_from_stt)

    assert "write_stt_timing_report" in source
    assert hasattr(module, "write_stt_timing_report")
    assert hasattr(module, "write_timeline_sync_report")
    assert hasattr(module, "build_timeline_from_stt")
    assert module.SUBTITLE_TIMING_EVIDENCE_MODE == "whisper_tiny_segment_timing"
    assert "whisper.load_model" in inspect.getsource(module.transcribe_narration_with_whisper)
    assert "split_long_timeline_segments" in timeline_source


def test_clean_anime_filter_softens_pure_black_ink_lines():
    module = load_render_module()
    image = Image.new("RGB", (module.W, module.H), (214, 220, 216))
    draw = ImageDraw.Draw(image)
    draw.rectangle((950, 0, 970, module.H), fill=(0, 0, 0))

    softened = module.anime_unify(image)
    line_pixel = softened.getpixel((960, module.H // 2))

    assert min(line_pixel) >= 40


def test_clean_anime_filter_reduces_harsh_saturation():
    module = load_render_module()
    image = Image.new("RGB", (module.W, module.H), (235, 32, 18))

    softened = module.anime_unify(image)
    pixel = softened.getpixel((module.W // 2, module.H // 2))

    assert max(pixel) - min(pixel) <= 150
