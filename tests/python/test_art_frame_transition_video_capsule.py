import importlib.util
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "capsules" / "art_frame_transition_video" / "run_art_frame_transition_video.py"


def load_capsule_script():
    spec = importlib.util.spec_from_file_location("art_frame_transition_video", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ArtFrameDecisionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_capsule_script()

    def test_single_complete_reference_becomes_end_anchor(self):
        refs = self.script.normalize_reference_images(
            [{"path": "/tmp/full_bloom_finished.jpg", "description": "finished full bloom artwork"}]
        )

        plan = self.script.decide_frame_plan(
            "让这幅花瓶画慢慢长出花草，整体舒适高级",
            refs,
            mood="auto",
        )

        self.assertEqual(plan["anchor_frame"], "end")
        self.assertEqual(plan["start_frame_strategy"], "derive_from_reference")
        self.assertEqual(plan["end_frame_strategy"], "use_reference")
        self.assertEqual(plan["motion_route"], "comfortable_immersive")
        self.assertIn("derive_consistent_start_frame", plan["image_processing_actions"])

    def test_two_references_are_ordered_by_simple_and_rich_state(self):
        refs = self.script.normalize_reference_images(
            [
                {"path": "/tmp/empty_vase_start.jpg", "description": "empty quiet initial state"},
                {"path": "/tmp/full_flowers_end.jpg", "description": "full flowering finished state"},
            ]
        )

        plan = self.script.decide_frame_plan("从空瓶到盛放", refs, mood="auto")

        self.assertEqual(plan["anchor_frame"], "both")
        self.assertEqual(plan["start_frame_strategy"], "select_from_inputs")
        self.assertEqual(plan["end_frame_strategy"], "select_from_inputs")
        self.assertEqual(plan["selected_start_image"], "/tmp/empty_vase_start.jpg")
        self.assertEqual(plan["selected_end_image"], "/tmp/full_flowers_end.jpg")

    def test_modern_surreal_prompt_uses_novel_route(self):
        refs = self.script.normalize_reference_images([])

        plan = self.script.decide_frame_plan(
            "现代艺术装置，画里的几何体从画布里浮出来，要新奇吸引人",
            refs,
            mood="auto",
            style_hint="现代艺术",
        )

        self.assertEqual(plan["motion_route"], "novel_attention")
        self.assertEqual(plan["start_frame_strategy"], "generate_from_text")
        self.assertEqual(plan["end_frame_strategy"], "generate_from_text")


class ArtFrameCaptionPromptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_capsule_script()

    def test_famous_art_caption_uses_provided_fact_hook(self):
        plan = self.script.decide_frame_plan("参考一幅馆藏名画，做艺术化变化", [], mood="auto")

        captions = self.script.build_caption_lines(
            "画面是一幅安静的花园",
            plan,
            artwork_info={
                "title": "睡莲",
                "artist": "莫奈",
                "collection": "橘园美术馆",
                "verified": True,
            },
        )

        first = captions[0]["text"]
        self.assertIn("莫奈", first)
        self.assertIn("睡莲", first)
        self.assertIn("橘园美术馆", first)

    def test_uncertain_art_caption_does_not_invent_collection(self):
        plan = self.script.decide_frame_plan("像一幅古典画，但不知道作者", [], mood="auto")

        captions = self.script.build_caption_lines("像一幅古典画，但不知道作者", plan, artwork_info={})

        joined = "\n".join(item["text"] for item in captions)
        self.assertIn("从画面气质看", joined)
        self.assertNotIn("收藏于", joined)
        self.assertNotIn("博物馆", joined)

    def test_veo_prompt_requests_sound_effects_and_forbids_background_music(self):
        plan = self.script.decide_frame_plan("让颜料在画布里慢慢流动", [], mood="novel")
        captions = self.script.build_caption_lines("让颜料在画布里慢慢流动", plan)

        veo_prompt = self.script.build_veo_prompt("让颜料在画布里慢慢流动", plan, captions)

        self.assertIn("sound effects", veo_prompt.lower())
        self.assertIn("no background music", veo_prompt.lower())
        self.assertIn("artistic", veo_prompt.lower())

    def test_bgm_selection_has_no_remote_url_fields(self):
        plan = self.script.decide_frame_plan("安静的博物馆画作", [], mood="comfortable")

        selection = self.script.build_bgm_selection("安静的博物馆画作", plan, bgm_query="")

        self.assertEqual(selection["music_source"], "online")
        self.assertIn("music_query", selection)
        self.assertNotIn("music_url", selection)
        self.assertNotIn("download_url", selection)

    def test_caption_language_can_generate_english_lines(self):
        plan = self.script.decide_frame_plan("a quiet museum still life", [], mood="comfortable")

        captions = self.script.build_caption_lines(
            "a quiet museum still life",
            plan,
            caption_language="en",
        )

        joined = "\n".join(item["text"] for item in captions)
        self.assertIn("the image", joined.lower())
        self.assertNotIn("从画面气质看", joined)


class ArtFrameDryRunContractTest(unittest.TestCase):
    def test_dry_run_writes_manifest_prompts_and_qa_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            params = {
                "prompt": "一幅静物画里的花慢慢醒来",
                "reference_images": [],
                "aspect_ratio": "9:16",
                "mood": "comfortable",
                "dry_run": True,
            }
            params_path = root / "params.json"
            run_dir = root / "run"
            params_path.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [
                    "python3.12",
                    str(SCRIPT_PATH),
                    "--topic",
                    "一幅静物画里的花慢慢醒来",
                    "--params",
                    str(params_path),
                    "--output-dir",
                    str(run_dir),
                    "--dry-run",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            manifest = json.loads((run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
            self.assertTrue((run_dir / "analysis" / "frame_decision.json").is_file())
            self.assertTrue((run_dir / "prompts" / "veo_prompt.txt").is_file())
            self.assertTrue((run_dir / "prompts" / "prompt_index.json").is_file())
            self.assertTrue((run_dir / "qa" / "run_notes.json").is_file())
            self.assertTrue((run_dir / "qa" / "contact_sheet.jpg").is_file())
            self.assertTrue((run_dir / "qa" / "local_video_qa.json").is_file())
            self.assertTrue((run_dir / "frames" / "veo_inputs" / "start.jpg").is_file())
            self.assertTrue((run_dir / "frames" / "veo_inputs" / "end.jpg").is_file())
            categories = {item["category"] for item in manifest["artifacts"]}
            self.assertIn("final_video", categories)
            self.assertIn("caption", categories)
            self.assertIn("storyboard_prompt", categories)
            self.assertIn("veo_input_frame", categories)
            self.assertIn("qa", categories)
            prompt_paths = [
                item["path"]
                for item in manifest["artifacts"]
                if item["category"] == "storyboard_prompt"
            ]
            self.assertIn(str((run_dir / "prompts" / "prompt_index.json").resolve()), prompt_paths)
            manifest_text = json.dumps(manifest, ensure_ascii=False)
            self.assertNotIn("http://", manifest_text)
            self.assertNotIn("https://", manifest_text)

    def test_dry_run_respects_16x9_aspect_ratio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            params = {
                "prompt": "一幅横屏静物画慢慢亮起",
                "aspect_ratio": "16:9",
                "dry_run": True,
            }
            params_path = root / "params.json"
            run_dir = root / "run"
            params_path.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [
                    "python3.12",
                    str(SCRIPT_PATH),
                    "--params",
                    str(params_path),
                    "--output-dir",
                    str(run_dir),
                    "--dry-run",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height",
                    "-of",
                    "json",
                    str(run_dir / "release" / "video.mp4"),
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            stream = json.loads(probe.stdout)["streams"][0]
            self.assertEqual((stream["width"], stream["height"]), (1280, 720))

    def test_live_failure_writes_run_notes_and_partial_manifest(self):
        script = load_capsule_script()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            original = script.run_live_pipeline

            def fail_live(*_args, **_kwargs):
                raise RuntimeError("simulated veo failure")

            script.run_live_pipeline = fail_live
            try:
                with self.assertRaises(SystemExit):
                    script.run({"prompt": "需要失败记录的测试"}, run_dir, dry_run=False)
            finally:
                script.run_live_pipeline = original

            notes = json.loads((run_dir / "qa" / "run_notes.json").read_text(encoding="utf-8"))
            manifest = json.loads((run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(notes["status"], "failed")
            self.assertIn("simulated veo failure", notes["error"])
            self.assertIn("storyboard_prompt", {item["category"] for item in manifest["artifacts"]})


class ArtFrameLiveHelpersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_capsule_script()

    def test_ass_caption_file_contains_readable_style_and_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "captions.ass"
            captions = [
                {"start": 0.2, "end": 2.0, "text": "这幅画先用一个细节留住你"},
                {"start": 2.1, "end": 4.0, "text": "光线慢慢醒来"},
            ]

            self.script.write_ass_captions(output, captions, style={"primary_color": "&H00F5E8D0"})

            text = output.read_text(encoding="utf-8")
            self.assertIn("[V4+ Styles]", text)
            self.assertIn("这幅画先用一个细节留住你", text)
            self.assertIn("MarginV", text)

    def test_prepare_veo_input_command_uses_9x16_size(self):
        command = self.script.build_prepare_image_command(
            Path("in.png"),
            Path("out.jpg"),
            aspect_ratio="9:16",
        )

        joined = " ".join(command)
        self.assertIn("720x1280", joined)
        self.assertEqual(command[0], "ffmpeg")


class ArtFrameCapsulePackageTest(unittest.TestCase):
    def test_capsule_package_manifest_registers_local_script(self):
        package_path = ROOT / "capsules" / "art_frame_transition_video.capsule.zip"
        self.assertTrue(package_path.is_file())
        with zipfile.ZipFile(package_path) as package:
            manifest = json.loads(package.read("manifest.json").decode("utf-8"))
            names = set(package.namelist())

        capsule = manifest["capsule"]
        self.assertEqual(capsule["name"], "art_frame_transition_video")
        self.assertEqual(capsule["execution_mode"], "local_script")
        self.assertEqual(capsule["local_script_path"], "script/run_art_frame_transition_video.py")
        self.assertIn("script/run_art_frame_transition_video.py", names)
        self.assertEqual(capsule["config"]["video_engine"], "Veo31VideoGeneratorTool")
        self.assertEqual(capsule["config"]["add_background_music"], True)
        self.assertEqual(capsule["config"]["has_narration"], False)
        manifest_text = json.dumps(manifest, ensure_ascii=False)
        self.assertNotIn("https://", manifest_text)
        self.assertNotIn("Bearer ", manifest_text)


class ArtFrameReadmeTest(unittest.TestCase):
    def test_readme_mentions_new_tool_natural_language_examples(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("新增工具", text)
        self.assertIn("安装或启用", text)
        self.assertIn("注册完整流程", text)
        self.assertNotIn("### Veo 3.1 首尾帧视频", text)
        self.assertNotIn("### 艺术图像首尾帧动态短片", text)
