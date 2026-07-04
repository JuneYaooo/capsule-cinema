import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


class DistillDouyinAccountHelpersTest(unittest.TestCase):
    def test_safe_slug_keeps_url_code_and_removes_unsafe_characters(self):
        from distill_douyin_account import safe_slug

        self.assertEqual("Abc123Demo", safe_slug("https://v.douyin.com/Abc123Demo/"))
        self.assertEqual("account_123", safe_slug("账号 123"))
        self.assertEqual("douyin_account", safe_slug("!!!"))

    def test_normalize_video_extracts_nested_stats_hashtags_and_urls(self):
        from distill_douyin_account import normalize_video

        normalized = normalize_video(
            {
                "aweme_id": "7366",
                "desc": "普通人别乱学 #职场 #成长",
                "create_time": 1710000000,
                "duration": 34567,
                "statistics": {
                    "digg_count": 1200,
                    "comment_count": 34,
                    "share_count": 56,
                    "collect_count": 78,
                },
                "author": {"nickname": "样本作者", "signature": "讲真实经验"},
                "video": {
                    "play_addr": {"url_list": ["https://example.com/play.mp4"]},
                    "cover": {"url_list": ["https://example.com/cover.jpg"]},
                },
            },
            index=1,
        )

        self.assertEqual(1, normalized["index"])
        self.assertEqual("7366", normalized["aweme_id"])
        self.assertEqual("普通人别乱学 #职场 #成长", normalized["description"])
        self.assertEqual(["职场", "成长"], normalized["hashtags"])
        self.assertEqual(34567, normalized["duration_ms"])
        self.assertEqual(1200, normalized["stats"]["digg_count"])
        self.assertEqual(1368, normalized["engagement_score"])
        self.assertEqual("样本作者", normalized["author"]["nickname"])
        self.assertEqual(["https://example.com/play.mp4"], normalized["play_urls"])
        self.assertEqual(["https://example.com/cover.jpg"], normalized["cover_urls"])

    def test_normalize_video_accepts_external_crawler_flat_shape(self):
        from distill_douyin_account import normalize_video

        normalized = normalize_video(
            {
                "title": "真正高级的吸引力，来自若即若离 #心理 #人性",
                "duration": 572,
                "liked_count": 498,
                "comment_count": 14,
                "share_count": 111,
                "collected_count": 371,
                "nickname": "样本账号",
                "publish_time": "07月02日",
                "thumbnail": "https://example.com/cover.jpg",
                "share_link": "https://example.com/share/",
                "video_url": "https://example.com/video.mp4",
            },
            index=1,
        )

        self.assertEqual("真正高级的吸引力，来自若即若离 #心理 #人性", normalized["description"])
        self.assertEqual(572000, normalized["duration_ms"])
        self.assertEqual(572, normalized["duration_seconds"])
        self.assertEqual(498, normalized["stats"]["digg_count"])
        self.assertEqual(994, normalized["engagement_score"])
        self.assertEqual("样本账号", normalized["author"]["nickname"])
        self.assertEqual("07月02日", normalized["create_time"])
        self.assertIn("https://example.com/share/", normalized["play_urls"])
        self.assertIn("https://example.com/video.mp4", normalized["play_urls"])
        self.assertEqual(["https://example.com/cover.jpg"], normalized["cover_urls"])

    def test_extract_video_list_accepts_common_crawler_shapes(self):
        from distill_douyin_account import extract_video_list

        direct = {"success": True, "video_list": [{"desc": "a"}]}
        nested = {"success": True, "data": {"data": {"aweme_list": [{"desc": "b"}]}}}

        self.assertEqual("a", extract_video_list(direct)[0]["desc"])
        self.assertEqual("b", extract_video_list(nested)[0]["desc"])

    def test_summarize_videos_ranks_hashtags_and_top_examples(self):
        from distill_douyin_account import normalize_video, summarize_videos

        videos = [
            normalize_video({"desc": "强钩子 #职场", "statistics": {"digg_count": 3}}, 1),
            normalize_video({"desc": "真实案例 #职场 #成长", "statistics": {"digg_count": 9}}, 2),
        ]
        summary = summarize_videos(videos)

        self.assertEqual(2, summary["video_count"])
        self.assertEqual("职场", summary["top_hashtags"][0]["tag"])
        self.assertEqual("真实案例 #职场 #成长", summary["top_videos"][0]["description"])

    def test_build_presentation_recipe_detects_minimal_card_explainer_shape(self):
        from distill_douyin_account import build_presentation_recipe, normalize_video, summarize_videos

        videos = [
            normalize_video(
                {
                    "title": "操控他人认知的本质，从来不是说服 #心理",
                    "duration": 743,
                    "liked_count": 1000,
                    "nickname": "样本账号",
                    "video_url": "https://example.com/a.mp4",
                },
                1,
            ),
            normalize_video(
                {
                    "title": "识人的最高境界：看别人不经意流露的东西 #人性",
                    "duration": 970,
                    "liked_count": 2000,
                    "nickname": "样本账号",
                    "video_url": "https://example.com/b.mp4",
                },
                2,
            ),
        ]
        summary = summarize_videos(videos)
        recipe = build_presentation_recipe(videos, summary)

        self.assertEqual("minimal_text_card_explainer", recipe["format_type"])
        self.assertEqual("local_card_rendering_tts_ffmpeg", recipe["implementation_route"])
        self.assertIn("white", recipe["palette"]["background"])
        self.assertIn("bold_black_core_sentence", recipe["layout"])
        self.assertIn("key_sentence_replacement", recipe["motion"])
        self.assertIn("do_not_copy_account_logo_or_name", recipe["avoid"])

    def test_build_presentation_recipe_uses_visual_probe_for_svg_distillation(self):
        from distill_douyin_account import build_presentation_recipe, normalize_video, summarize_videos

        videos = [
            normalize_video(
                {
                    "title": "操控他人认知的本质，从来不是说服 #心理",
                    "duration": 743,
                    "liked_count": 1000,
                    "video_url": "https://example.com/a.mp4",
                },
                1,
            )
        ]
        summary = summarize_videos(videos)
        probe_report = {
            "top_video_probes": [
                {
                    "frames": [
                        {"label": "start", "path": "visual_probe/top_16_start.jpg"},
                        {"label": "mid_01", "path": "visual_probe/top_16_mid_01.jpg"},
                        {"label": "mid_04", "path": "visual_probe/top_16_mid_04.jpg"},
                    ]
                }
            ]
        }

        recipe = build_presentation_recipe(videos, summary, probe_report=probe_report)

        self.assertEqual("observed_from_metadata_and_keyframes", recipe["observed_or_inferred"])
        self.assertIn("semantic_vector_metaphor", recipe["layout"])
        self.assertIn("vector_reveal", recipe["motion"])
        self.assertEqual(
            ["person_silhouette", "red_path_or_arc", "environment_symbol", "system_panel"],
            recipe["visual_component_library"]["required_families"],
        )
        self.assertIn("middle_semantic_svg_scene_required", recipe["visual_quality_gates"])
        self.assertIn("animated_vector_reveal_required", recipe["visual_quality_gates"])
        self.assertIn("top_16_start.jpg", recipe["evidence"]["keyframe_paths"][0])

    def test_format_classifier_routes_product_showcase_without_knowledge_card_bias(self):
        from distill_douyin_account import (
            build_presentation_recipe,
            build_universal_distillation,
            classify_video_format,
            normalize_video,
            summarize_videos,
        )

        videos = [
            normalize_video(
                {
                    "title": "新款筋膜枪开箱实测，三档力度对比 #开箱 #测评 #好物",
                    "duration": 47,
                    "liked_count": 1200,
                    "video_url": "https://example.com/product-a.mp4",
                },
                1,
            ),
            normalize_video(
                {
                    "title": "桌面无线充电器真实使用一周，优缺点都说 #产品测评 #种草",
                    "duration": 58,
                    "liked_count": 1800,
                    "video_url": "https://example.com/product-b.mp4",
                },
                2,
            ),
        ]
        summary = summarize_videos(videos)

        classification = classify_video_format(videos, summary)
        presentation = build_presentation_recipe(videos, summary)
        universal = build_universal_distillation(videos, summary)

        self.assertEqual("product_showcase", classification["primary_format"])
        self.assertGreater(classification["confidence"], 0)
        self.assertEqual("product_showcase", presentation["format_type"])
        self.assertEqual("demonstration_evidence_sequence", presentation["implementation_route"])
        self.assertIn("product_closeup", presentation["visual_component_library"]["required_families"])
        self.assertNotIn("semantic_vector_metaphor", presentation["layout"])
        self.assertEqual("universal_account_distillation.v1", universal["schema_version"])
        self.assertEqual("product_showcase", universal["format_classifier"]["primary_format"])
        self.assertEqual("product_showcase", universal["capsule_seed"]["format_family"])

    def test_format_classifier_routes_story_drama_and_requires_scene_level_evidence(self):
        from distill_douyin_account import build_presentation_recipe, classify_video_format, normalize_video, summarize_videos

        videos = [
            normalize_video(
                {
                    "title": "婆婆突然来访，儿媳一句话全家沉默 #短剧 #反转 #家庭",
                    "duration": 92,
                    "liked_count": 3100,
                    "video_url": "https://example.com/drama-a.mp4",
                },
                1,
            ),
            normalize_video(
                {
                    "title": "老板装穷试探员工，结局太反转 #剧情 #职场短剧",
                    "duration": 76,
                    "liked_count": 2600,
                    "video_url": "https://example.com/drama-b.mp4",
                },
                2,
            ),
        ]
        summary = summarize_videos(videos)

        classification = classify_video_format(videos, summary)
        recipe = build_presentation_recipe(videos, summary)

        self.assertEqual("story_drama", classification["primary_format"])
        self.assertIn("conflict_scene_setup", recipe["layout"])
        self.assertIn("character_blocking", recipe["visual_component_library"]["required_families"])
        self.assertIn("scene_continuity_review_required", recipe["visual_quality_gates"])

    def test_replication_recipe_uses_format_specific_language_without_growth_bias(self):
        from distill_douyin_account import (
            build_presentation_recipe,
            build_replication_recipe,
            normalize_video,
            summarize_videos,
        )

        videos = [
            normalize_video(
                {
                    "title": "新款筋膜枪开箱实测，三档力度对比 #开箱 #测评 #好物",
                    "duration": 47,
                    "liked_count": 1200,
                    "video_url": "https://example.com/product-a.mp4",
                },
                1,
            )
        ]
        summary = summarize_videos(videos)
        presentation = build_presentation_recipe(videos, summary)

        recipe = build_replication_recipe(
            "https://example.com/creator-share/",
            "0-1",
            videos,
            summary,
            presentation,
            analysis_mode="metadata_only",
        )

        self.assertIn("product_showcase", recipe)
        self.assertIn("产品", recipe)
        self.assertIn("证据", recipe)
        self.assertNotIn("人格系统", recipe)
        self.assertNotIn("内在主权", recipe)


class DistillDouyinAccountRunTest(unittest.TestCase):
    def test_run_distillation_with_fake_crawler_writes_standalone_artifacts(self):
        from distill_douyin_account import run_distillation

        class FakeCrawler:
            def _run(self, url, range):
                return {
                    "success": True,
                    "video_count": 2,
                    "video_list": [
                        {
                            "aweme_id": "1",
                            "desc": "普通人别急着离职 #职场",
                            "statistics": {"digg_count": 100, "comment_count": 10, "share_count": 5},
                            "author": {"nickname": "职场样本"},
                        },
                        {
                            "aweme_id": "2",
                            "desc": "真正拉开差距的是复盘 #成长",
                            "statistics": {"digg_count": 300, "comment_count": 20, "share_count": 15},
                            "author": {"nickname": "职场样本"},
                        },
                    ],
                    "data": {"raw": True},
                }

        with tempfile.TemporaryDirectory() as tmp:
            result = run_distillation(
                url="https://example.com/creator-share/",
                range_str="0-1",
                output_base_dir=Path(tmp),
                crawler_factory=lambda: FakeCrawler(),
                timestamp="20260704_120000",
                enable_auto_probe=False,
            )

            output_dir = Path(result["output_dir"])
            self.assertTrue((output_dir / "raw_crawl_response.json").is_file())
            self.assertTrue((output_dir / "video_index.json").is_file())
            self.assertTrue((output_dir / "evidence_manifest.json").is_file())
            self.assertTrue((output_dir / "account_distillation.md").is_file())
            self.assertTrue((output_dir / "universal_distillation.json").is_file())
            self.assertTrue((output_dir / "replication_recipe.md").is_file())
            self.assertTrue((output_dir / "presentation_recipe.md").is_file())
            self.assertTrue((output_dir / "presentation_recipe.json").is_file())
            self.assertTrue((output_dir / "content_formula.yaml").is_file())
            self.assertTrue((output_dir / "cover_formula.yaml").is_file())
            self.assertTrue((output_dir / "motion_formula.yaml").is_file())
            self.assertTrue((output_dir / "audio_formula.yaml").is_file())
            self.assertTrue((output_dir / "quality_gates.yaml").is_file())
            self.assertTrue((output_dir / "capsule_seed.yaml").is_file())
            self.assertTrue((output_dir / "recipe_seed.yaml").is_file())
            self.assertTrue((output_dir / "artifact_manifest.json").is_file())

            index = json.loads((output_dir / "video_index.json").read_text(encoding="utf-8"))
            seed = yaml.safe_load((output_dir / "recipe_seed.yaml").read_text(encoding="utf-8"))
            capsule_seed = yaml.safe_load((output_dir / "capsule_seed.yaml").read_text(encoding="utf-8"))
            evidence = json.loads((output_dir / "evidence_manifest.json").read_text(encoding="utf-8"))
            motion_formula = yaml.safe_load((output_dir / "motion_formula.yaml").read_text(encoding="utf-8"))
            audio_formula = yaml.safe_load((output_dir / "audio_formula.yaml").read_text(encoding="utf-8"))
            recipe = (output_dir / "replication_recipe.md").read_text(encoding="utf-8")
            universal = json.loads((output_dir / "universal_distillation.json").read_text(encoding="utf-8"))
            presentation = json.loads((output_dir / "presentation_recipe.json").read_text(encoding="utf-8"))

        self.assertEqual(2, index["summary"]["video_count"])
        self.assertEqual("douyin_account_replication_seed.v1", seed["schema_version"])
        self.assertEqual("capsule_cinema.account_evidence_manifest.v1", evidence["schema_version"])
        self.assertEqual("L0_metadata_only", evidence["evidence_level"])
        self.assertIn("camera_pacing_motion_claims", evidence["blocked_claims"])
        self.assertEqual("blocked_without_L2", motion_formula["evidence_status"])
        self.assertEqual("blocked_without_L2", audio_formula["evidence_status"])
        self.assertEqual("capsule_cinema.account_capsule_seed.v1", capsule_seed["schema_version"])
        self.assertEqual("L0_metadata_only", capsule_seed["evidence_level"])
        self.assertEqual("universal_account_distillation.v1", universal["schema_version"])
        self.assertIn("capsule_seed", universal)
        self.assertIn("presentation_recipe", seed)
        self.assertEqual(universal["format_classifier"]["primary_format"], presentation["format_type"])
        self.assertIn("复刻配方", recipe)
        self.assertIn("视频呈现方式", recipe)
        self.assertIn("metadata_only", result["analysis_mode"])

    def test_run_distillation_accepts_probe_report_and_writes_visual_evidence(self):
        from distill_douyin_account import run_distillation

        class FakeCrawler:
            def _run(self, url, range):
                return {
                    "success": True,
                    "video_list": [
                        {
                            "aweme_id": "1",
                            "desc": "真正让人卡住的不是懒 #成长",
                            "duration": 28,
                            "statistics": {"digg_count": 100},
                            "video_url": "https://example.com/a.mp4",
                        }
                    ],
                }

        probe_report = {
            "top_video_probes": [
                {
                    "aweme_id": "1",
                    "frames": [
                        {"label": "start", "path": "visual_probe/top_16_start.jpg"},
                        {"label": "mid", "path": "visual_probe/top_16_mid_04.jpg"},
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            result = run_distillation(
                url="https://example.com/creator-share/",
                range_str="0-1",
                output_base_dir=Path(tmp),
                crawler_factory=lambda: FakeCrawler(),
                timestamp="20260704_130000",
                probe_report=probe_report,
                enable_auto_probe=False,
            )

            output_dir = Path(result["output_dir"])
            presentation = json.loads((output_dir / "presentation_recipe.json").read_text(encoding="utf-8"))
            seed = yaml.safe_load((output_dir / "recipe_seed.yaml").read_text(encoding="utf-8"))
            distillation = (output_dir / "account_distillation.md").read_text(encoding="utf-8")

        self.assertEqual("metadata_plus_visual_probe", result["analysis_mode"])
        self.assertEqual("observed_from_metadata_and_keyframes", presentation["observed_or_inferred"])
        self.assertEqual(2, presentation["evidence"]["keyframe_count"])
        self.assertIn("top_16_mid_04.jpg", presentation["evidence"]["keyframe_paths"][1])
        self.assertEqual("metadata_plus_visual_probe", seed["source"]["analysis_mode"])
        self.assertIn("metadata_plus_visual_probe", distillation)
        self.assertIn("关键帧", distillation)

    def test_run_distillation_auto_probe_can_upgrade_to_multimodal_evidence(self):
        from distill_douyin_account import run_distillation

        class FakeCrawler:
            def _run(self, url, range):
                return {
                    "success": True,
                    "video_list": [
                        {
                            "aweme_id": "1",
                            "desc": "新款筋膜枪开箱实测，三档力度对比 #开箱 #测评",
                            "duration": 47,
                            "statistics": {"digg_count": 900, "comment_count": 30},
                            "video_url": "https://example.com/product-a.mp4",
                        }
                    ],
                }

        fetched: list[str] = []

        def fake_media_fetcher(video, media_dir):
            fetched.append(video["aweme_id"])
            media_path = Path(media_dir) / f"{video['aweme_id']}.mp4"
            media_path.parent.mkdir(parents=True, exist_ok=True)
            media_path.write_bytes(b"fake media")
            return {
                "ok": True,
                "aweme_id": video["aweme_id"],
                "source_url": video["play_urls"][0],
                "path": str(media_path),
            }

        def fake_probe_runner(media_items, output_dir):
            self.assertEqual(1, len(media_items))
            frame_path = Path(output_dir) / "visual_probe" / "top_1_start.jpg"
            frame_path.parent.mkdir(parents=True, exist_ok=True)
            frame_path.write_bytes(b"jpg")
            return {
                "top_video_probes": [
                    {
                        "aweme_id": media_items[0]["aweme_id"],
                        "frames": [{"label": "start", "path": str(frame_path)}],
                    }
                ],
                "subtitle_ocr": [{"text": "三档力度实测"}],
                "transcripts": [{"text": "先看这个三档力度差异"}],
                "audio_probe": {"has_voice": True, "has_bgm": True, "speech_rate_cpm": 255},
                "rhythm": {"cuts_per_minute": 18, "first_cut_seconds": 1.2},
            }

        with tempfile.TemporaryDirectory() as tmp:
            result = run_distillation(
                url="https://example.com/creator-share/",
                range_str="0-1",
                output_base_dir=Path(tmp),
                crawler_factory=lambda: FakeCrawler(),
                timestamp="20260704_140000",
                enable_auto_probe=True,
                media_fetcher=fake_media_fetcher,
                probe_runner=fake_probe_runner,
            )

            output_dir = Path(result["output_dir"])
            evidence = json.loads((output_dir / "evidence_manifest.json").read_text(encoding="utf-8"))
            motion_formula = yaml.safe_load((output_dir / "motion_formula.yaml").read_text(encoding="utf-8"))
            audio_formula = yaml.safe_load((output_dir / "audio_formula.yaml").read_text(encoding="utf-8"))
            quality_gates = yaml.safe_load((output_dir / "quality_gates.yaml").read_text(encoding="utf-8"))
            universal = json.loads((output_dir / "universal_distillation.json").read_text(encoding="utf-8"))

        self.assertEqual(["1"], fetched)
        self.assertEqual("metadata_plus_multimodal_probe", result["analysis_mode"])
        self.assertEqual("L2_multimodal_probe", evidence["evidence_level"])
        self.assertIn("keyframes", evidence["available_signals"])
        self.assertIn("audio", evidence["available_signals"])
        self.assertIn("rhythm", evidence["available_signals"])
        self.assertEqual("observed_from_L2_probe", motion_formula["evidence_status"])
        self.assertEqual("observed_from_L2_probe", audio_formula["evidence_status"])
        self.assertIn("first_three_seconds_gate", {gate["id"] for gate in quality_gates["gates"]})
        self.assertEqual("L2_multimodal_probe", universal["capsule_seed"]["evidence_level"])


if __name__ == "__main__":
    unittest.main()
