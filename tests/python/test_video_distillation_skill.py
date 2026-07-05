import contextlib
import importlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "video-distillation"
SCRIPTS = SKILL_DIR / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

DEFAULT_EXTERNAL_VIDEO_WORKFLOW_ROOT = Path("/Users/june2/code/github/video_workflow")
EXTRACTOR_TOOL_RELATIVE_PATH = Path(
    "backend/video_workflow/custom_tools/extract_content/social_media_content_extractor_tool.py"
)
DEFAULT_EXTRACTOR_TOOL_PATH = DEFAULT_EXTERNAL_VIDEO_WORKFLOW_ROOT / EXTRACTOR_TOOL_RELATIVE_PATH
ROOT_SKILL_FORBIDDEN_MARKERS = [
    "video-distillation",
    "video_distillation",
    "$video-distillation",
    "output/video_distillation",
    "deep video distillation",
    "deep-distilling a selected social video",
    "深度视频蒸馏",
    "视频蒸馏",
]
TIMESTAMP_KEYS = {"timestamp", "timestamps", "timecode", "timecodes"}
TIME_RANGE_KEYS = {"time_range"}
TRANSCRIPT_SNIPPET_KEYS = {
    "copy_evidence",
    "transcript_evidence",
    "transcript_snippet",
    "transcript_snippets",
}
FRAME_PATH_KEYS = {"frame_path", "frame_paths", "keyframe_path", "keyframe_paths"}
MEDIA_INFO_KEYS = {"media_info", "media_info_ref", "media_info_refs", "media_ref"}
INFERENCE_KEYS = {"inference", "inference_marker", "inferred_from", "observed_from"}
PLACEHOLDER_EVIDENCE_TEXT = {
    "placeholder",
    "todo",
    "tbd",
    "n/a",
    "n a",
    "na",
    "none",
    "null",
    "unknown",
    "not captured",
    "non empty but vague",
    "sample",
    "example",
    "dummy",
    "foo",
    "bar",
}
TIME_PART = r"(?:\d+(?:\.\d+)?s?|(?:(?:\d+:)?\d{1,2}:\d{2})(?:\.\d+)?)"
TIME_RANGE_PATTERN = re.compile(rf"\b{TIME_PART}\s*(?:-|–|—|~|\bto\b)\s*{TIME_PART}\b", re.IGNORECASE)
SINGLE_TIMECODE_PATTERN = re.compile(r"\b(?:(?:\d+:)?\d{1,2}:\d{2})(?:\.\d+)?\b")
NUMERIC_TIMESTAMP_PATTERN = re.compile(r"^\d+(?:\.\d+)?s?$", re.IGNORECASE)
TIMESTAMP_LABEL_PATTERN = re.compile(r"\b(?:timestamp|timecode|at)\s*[:=]\s*\d", re.IGNORECASE)
TRANSCRIPT_MARKER_PATTERN = re.compile(r"\b(?:transcript|snippet|quote|caption)\s*[:：]", re.IGNORECASE)
FRAME_PATH_PATTERN = re.compile(
    r"(?:^|/)(?:03_keyframes/)?(?:frames/)?[^\\/\s]*(?:frame|keyframe)[^\\/\s]*\."
    r"(?:jpg|jpeg|png|webp)\b|03_keyframes/",
    re.IGNORECASE,
)
MEDIA_INFO_REF_PATTERN = re.compile(r"\bmedia[_-]?info(?:\.[A-Za-z0-9_]+|\[[^\]]+\]|:)", re.IGNORECASE)
INFERENCE_MARKER_PATTERN = re.compile(
    r"\b(?:inference|inferred|observed)\s*[:：]|\binferred\s+from\b",
    re.IGNORECASE,
)
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def _fresh_import(module_name: str):
    if module_name == "distill_video":
        sys.modules.pop("build_video_distillation_report", None)
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def _network_disabled():
    return mock.patch("socket.socket", side_effect=AssertionError("network disabled"))


def _external_extractor_tool_path(external_video_workflow_root: Path) -> Path:
    return Path(external_video_workflow_root) / EXTRACTOR_TOOL_RELATIVE_PATH


def _write_fake_social_media_extractor(external_video_workflow_root: Path, call_log: Path) -> Path:
    tool_path = _external_extractor_tool_path(external_video_workflow_root)
    tool_path.parent.mkdir(parents=True, exist_ok=True)
    tool_path.write_text(
        f"""
import json
from pathlib import Path

CALL_LOG = Path({str(call_log)!r})


def _json_safe(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class SocialMediaContentExtractorTool:
    def _run(self, *args, **kwargs):
        output_dir = Path(kwargs.get("output_dir") or kwargs.get("run_output_dir") or ".")
        output_dir.mkdir(parents=True, exist_ok=True)
        video_path = output_dir / "fake_extracted_video.mp4"
        video_path.write_bytes(b"fake video bytes from no-network extractor")
        payload = {{
            "args": [_json_safe(item) for item in args],
            "kwargs": {{key: _json_safe(value) for key, value in kwargs.items()}},
        }}
        CALL_LOG.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {{
            "success": True,
            "title": "Fake Douyin share text fixture",
            "source_url": kwargs.get("url") or kwargs.get("share_text") or (args[0] if args else ""),
            "video_file": str(video_path),
            "video_local_path": str(video_path),
            "transcript": "transcript: 先看结果。然后解释原因。最后评论关键词。",
            "metadata": {{"platform": "douyin", "source": "fake_no_network_extractor"}},
        }}
""".lstrip(),
        encoding="utf-8",
    )
    return tool_path


def _make_tiny_video(path: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False

    source_filters = [
        "testsrc2=size=320x568:rate=24:duration=2",
        "color=c=black:s=320x568:d=2",
    ]
    for source_filter in source_filters:
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            source_filter,
            "-an",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode == 0 and path.is_file():
            return True
    return False


def _resolve_path(path_value: str | Path, base: Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else base / path


def _assert_under(testcase: unittest.TestCase, path: Path, parent: Path, label: str) -> None:
    resolved_path = path.resolve()
    resolved_parent = parent.resolve()
    try:
        resolved_path.relative_to(resolved_parent)
    except ValueError:
        testcase.fail(f"{label} should be under {resolved_parent}, got {resolved_path}")


def _assert_not_capsules_path(
    testcase: unittest.TestCase,
    path_value: str | Path,
    label: str,
    base: Path = ROOT,
) -> None:
    raw = str(path_value).replace("\\", "/")
    testcase.assertFalse(
        raw == "capsules" or raw.startswith("capsules/") or "/capsules/" in f"/{raw}",
        f"{label} must not point into capsules/: {raw}",
    )
    candidate = _resolve_path(path_value, base)
    try:
        candidate.resolve().relative_to((ROOT / "capsules").resolve())
    except ValueError:
        return
    testcase.fail(f"{label} resolved inside capsules/: {candidate}")


def _assert_manifest_artifacts_stay_in_run(
    testcase: unittest.TestCase,
    run_dir: Path,
    manifest: dict,
) -> None:
    artifacts = manifest.get("artifacts")
    testcase.assertIsInstance(artifacts, list)
    testcase.assertGreater(len(artifacts), 0)
    for item in artifacts:
        testcase.assertIn("path", item)
        raw_path = item["path"]
        testcase.assertTrue(str(raw_path).strip())
        _assert_not_capsules_path(testcase, raw_path, f"manifest artifact {raw_path}", base=run_dir)
        artifact_path = _resolve_path(raw_path, run_dir)
        _assert_under(testcase, artifact_path, run_dir, f"manifest artifact {raw_path}")


def _is_non_empty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_is_non_empty(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_is_non_empty(item) for item in value)
    return True


def _normalized_evidence_text(value: str) -> str:
    text = value.strip().strip("\"'`")
    return re.sub(r"\s+", " ", text)


def _is_placeholder_evidence_text(value: str) -> bool:
    normalized = _normalized_evidence_text(value).lower()
    normalized = re.sub(r"[\s:._/\-]+", " ", normalized).strip()
    return not normalized or normalized in PLACEHOLDER_EVIDENCE_TEXT


def _looks_like_transcript_snippet(value: str) -> bool:
    text = _normalized_evidence_text(value)
    if _is_placeholder_evidence_text(text):
        return False
    return bool(
        TRANSCRIPT_MARKER_PATTERN.search(text)
        or CJK_PATTERN.search(text)
        or (len(text) >= 8 and len(text.split()) >= 2)
    )


def _has_concrete_media_info_value(value) -> bool:
    if isinstance(value, dict):
        return any(_has_concrete_media_info_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_concrete_media_info_value(item) for item in value)
    if isinstance(value, str):
        return not _is_placeholder_evidence_text(value)
    return value is not None


def _string_has_required_evidence_form(value: str, key_context: str) -> bool:
    text = _normalized_evidence_text(value)
    if _is_placeholder_evidence_text(text):
        return False
    if (
        TIME_RANGE_PATTERN.search(text)
        or SINGLE_TIMECODE_PATTERN.search(text)
        or TIMESTAMP_LABEL_PATTERN.search(text)
        or TRANSCRIPT_MARKER_PATTERN.search(text)
        or FRAME_PATH_PATTERN.search(text)
        or MEDIA_INFO_REF_PATTERN.search(text)
        or INFERENCE_MARKER_PATTERN.search(text)
    ):
        return True
    if key_context in TIMESTAMP_KEYS:
        return bool(NUMERIC_TIMESTAMP_PATTERN.fullmatch(text))
    if key_context in TRANSCRIPT_SNIPPET_KEYS:
        return _looks_like_transcript_snippet(text)
    if key_context in FRAME_PATH_KEYS:
        return bool(FRAME_PATH_PATTERN.search(text))
    if key_context in MEDIA_INFO_KEYS:
        return bool(MEDIA_INFO_REF_PATTERN.search(text))
    if key_context in INFERENCE_KEYS:
        return bool(INFERENCE_MARKER_PATTERN.search(text))
    return False


def _evidence_marker_paths(value, prefix: str = "", key_context: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        if key_context in MEDIA_INFO_KEYS and _has_concrete_media_info_value(value):
            paths.append(prefix or key_context)
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(_evidence_marker_paths(item, child, str(key).lower()))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            child = f"{prefix}[{index}]"
            paths.extend(_evidence_marker_paths(item, child, key_context))
    elif isinstance(value, str):
        if _string_has_required_evidence_form(value, key_context):
            paths.append(prefix or "<text>")
    elif isinstance(value, bool):
        return paths
    elif isinstance(value, (int, float)):
        if key_context in TIMESTAMP_KEYS and value >= 0:
            paths.append(prefix or "<text>")
    return paths


def _assert_has_evidence(testcase: unittest.TestCase, value, label: str) -> None:
    paths = _evidence_marker_paths(value)
    testcase.assertTrue(
        paths,
        f"{label} must include timestamps, transcript snippets, frame paths, media-info refs, "
        f"or explicit inference markers. Placeholder evidence is not enough. Got:\n"
        f"{yaml.safe_dump(value, allow_unicode=True, sort_keys=False)}",
    )


def _scalar_values(value) -> list[str]:
    if isinstance(value, dict):
        scalars: list[str] = []
        for item in value.values():
            scalars.extend(_scalar_values(item))
        return scalars
    if isinstance(value, (list, tuple, set)):
        scalars = []
        for item in value:
            scalars.extend(_scalar_values(item))
        return scalars
    if value is None:
        return []
    return [str(value)]


class EvidenceDisciplineHelperTest(unittest.TestCase):
    def test_helper_rejects_placeholder_only_evidence(self):
        placeholder_values = [
            {"evidence": ["placeholder"]},
            {"evidence": {"timestamp": "placeholder"}},
            {"time_range": "placeholder"},
            {"timestamp": "not captured"},
            {"transcript_snippet": "placeholder"},
            {"media_info": {"duration_seconds": "placeholder"}},
            {"production_route": {"needs_tts": {"evidence": ["non-empty but vague"]}}},
        ]
        for value in placeholder_values:
            with self.subTest(value=value):
                with self.assertRaises(AssertionError):
                    _assert_has_evidence(self, value, "placeholder fixture")

    def test_helper_accepts_concrete_required_evidence_forms(self):
        concrete_values = [
            {"time_range": "0:00-0:03"},
            {"timestamp": 0.0},
            {"transcript_snippet": "别再这样开头了"},
            {"evidence": ["transcript: Watch the first frame change"]},
            {"frame_path": "03_keyframes/frames/frame_0000.jpg"},
            {"media_info_ref": "media_info.duration_seconds"},
            {"inference": "inference: silent source inferred from media_info.has_audio=false"},
        ]
        for value in concrete_values:
            with self.subTest(value=value):
                _assert_has_evidence(self, value, "concrete fixture")


class VideoDistillationSkillShapeTest(unittest.TestCase):
    def test_skill_is_standalone_and_not_capsule_runtime(self):
        self.assertTrue((SKILL_DIR / "SKILL.md").is_file())
        self.assertTrue((SKILL_DIR / "agents" / "openai.yaml").is_file())
        self.assertTrue((SKILL_DIR / "references" / "video-distillation-protocol.md").is_file())
        self.assertTrue((SKILL_DIR / "references" / "output-schema.md").is_file())
        self.assertTrue((SKILL_DIR / "references" / "gemini-video-analysis-prompts.md").is_file())
        self.assertTrue((SKILL_DIR / "references" / "extraction-tool-contract.md").is_file())
        self.assertTrue((SKILL_DIR / "scripts" / "distill_video.py").is_file())
        self.assertTrue((SKILL_DIR / "scripts" / "build_video_distillation_report.py").is_file())

        root_skill = (ROOT / "skill.md").read_text(encoding="utf-8")
        root_skill_lower = root_skill.lower()
        for marker in ROOT_SKILL_FORBIDDEN_MARKERS:
            self.assertNotIn(marker.lower(), root_skill_lower)
        self.assertFalse((ROOT / "capsules" / "video-distillation.capsule").exists())
        self.assertFalse((ROOT / "capsules" / "video_distillation.capsule").exists())

    def test_skill_description_triggers_deep_video_distillation(self):
        content = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: video-distillation", content)
        self.assertIn("深度视频蒸馏", content)
        self.assertIn("文案逻辑", content)
        self.assertIn("整个视频逻辑", content)
        self.assertIn("production route", content)
        self.assertIn("output/video_distillation/<YYYYMMDD_HHMMSS>_<slug>", content)
        self.assertNotIn("output/video_distillation/<run_id>", content)
        self.assertIn("references/extraction-tool-contract.md", content)


class VideoDistillationSchemaTest(unittest.TestCase):
    def test_copy_logic_contains_hook_promise_script_cta_rewrite_and_evidence(self):
        with _network_disabled():
            builders = _fresh_import("build_video_distillation_report")
            result = builders.build_copy_logic(
                source={"title": "3秒告诉你为什么没人看完", "caption": "别再这样开头了 #短视频"},
                transcript="别再这样开头了。前三秒没有结果，观众马上划走。最后记得评论关键词。",
                beats=[
                    {
                        "time_range": "0:00-0:03",
                        "role": "hook",
                        "transcript_evidence": "别再这样开头了",
                    }
                ],
                evidence_level="V2_transcript_ready",
            )

        self.assertEqual("capsule_cinema.video_copy_logic.v1", result["schema_version"])
        self.assertEqual("V2_transcript_ready", result["evidence_level"])
        for key in ["hook", "promise", "script_structure", "cta", "rewrite_template", "confidence"]:
            self.assertIn(key, result)
        for key in ["hook", "promise", "script_structure", "cta", "rewrite_template"]:
            _assert_has_evidence(self, result[key], f"copy_logic.{key}")
        dumped = yaml.safe_dump(result, allow_unicode=True, sort_keys=False)
        self.assertIn("0:00-0:03", dumped)
        self.assertIn("别再这样开头了", dumped)
        self.assertNotIn("别再这样开头了。前三秒没有结果", result["rewrite_template"]["reusable_script_template"])

    def test_beat_timeline_models_whole_video_logic_with_evidence_per_beat(self):
        with _network_disabled():
            builders = _fresh_import("build_video_distillation_report")
            result = builders.build_beat_timeline(
                transcript="先看结果。问题在这里。第三步才是真正的证明。最后评论关键词领取清单。",
                keyframes=[
                    {"path": "03_keyframes/frames/frame_0000.jpg", "timestamp": 0.0, "label": "first_frame"},
                    {"path": "03_keyframes/frames/frame_0003.jpg", "timestamp": 3.0, "label": "opening_3s"},
                    {"path": "03_keyframes/frames/frame_end.jpg", "timestamp": 12.0, "label": "ending"},
                ],
                gemini=None,
            )

        self.assertEqual("capsule_cinema.video_beat_timeline.v1", result["schema_version"])
        roles = [beat["role"] for beat in result["beats"]]
        self.assertIn("hook", roles)
        self.assertIn("proof_or_development", roles)
        self.assertIn("ending_or_cta", roles)
        for beat in result["beats"]:
            self.assertIn("time_range", beat)
            _assert_has_evidence(self, beat, f"beat {beat.get('role')}")
        self.assertIn("core_loop", result["logic_summary"])
        self.assertIn("viewer_question_opened", result["logic_summary"])
        self.assertIn("viewer_question_closed", result["logic_summary"])
        _assert_has_evidence(self, result["logic_summary"], "beat_timeline.logic_summary")
        dumped = yaml.safe_dump(result, allow_unicode=True, sort_keys=False)
        self.assertIn("03_keyframes/frames/frame_0000.jpg", dumped)
        self.assertIn("先看结果", dumped)

    def test_production_logic_classifies_modalities_routes_and_evidenced_sections(self):
        with _network_disabled():
            builders = _fresh_import("build_video_distillation_report")
            copy_logic = builders.build_copy_logic(
                source={"title": "AI卡片视频"},
                transcript="今天用三张卡片讲清楚。",
                beats=[
                    {
                        "time_range": "0:00-0:03",
                        "role": "hook",
                        "transcript_evidence": "今天用三张卡片讲清楚",
                    }
                ],
                evidence_level="V2_transcript_ready",
            )
            result = builders.build_production_logic(
                media_info={
                    "duration_seconds": 18.2,
                    "width": 1080,
                    "height": 1920,
                    "aspect_ratio": "9:16",
                    "has_audio": True,
                },
                keyframes=[
                    {
                        "path": "03_keyframes/frames/frame_0000.jpg",
                        "timestamp": 0.0,
                        "visible_text": "第一张卡片",
                        "label": "first_frame",
                    }
                ],
                gemini={
                    "visual_medium": "text_card_explainer",
                    "motion": ["text_reveal", "hard_cut"],
                    "audio": {"voice": "tts_like", "bgm": "light"},
                },
                copy_logic=copy_logic,
            )

        self.assertEqual("capsule_cinema.video_production_logic.v1", result["schema_version"])
        self.assertIn("visual_style", result)
        self.assertTrue("motion_and_editing" in result or "motion_style" in result)
        self.assertIn("audio_logic", result)
        motion_section = result.get("motion_and_editing") or result.get("motion_style")
        for key, section in [
            ("visual_style", result["visual_style"]),
            ("motion", motion_section),
            ("audio_logic", result["audio_logic"]),
        ]:
            _assert_has_evidence(self, section, f"production_logic.{key}")

        route = result["production_route"]
        for key in [
            "needs_ai_image_generation",
            "needs_ai_video_generation",
            "needs_digital_human",
            "needs_tts",
            "needs_original_voiceover",
            "needs_screen_recording",
            "needs_local_card_rendering",
            "needs_motion_graphics",
            "needs_subtitle_burn_in",
            "needs_bgm",
            "needs_sfx",
            "needs_manual_editing",
        ]:
            self.assertIn(key, route)
            self.assertIn("value", route[key])
            self.assertIn("reason", route[key])
            self.assertIn("evidence", route[key])
            self.assertIsInstance(route[key]["evidence"], list)
            self.assertTrue(any(_is_non_empty(item) for item in route[key]["evidence"]))
            _assert_has_evidence(self, route[key], f"production_route.{key}")

        for key in [
            "cheapest_viable_route",
            "highest_fidelity_route",
            "recommended_route",
            "hardest_part_to_reproduce",
        ]:
            self.assertIn(key, result)
            _assert_has_evidence(self, result[key], f"production_logic.{key}")

    def test_recipe_seed_recursively_excludes_source_identity_private_urls_and_secrets(self):
        forbidden_source = {
            "title": "原账号标题",
            "caption": "原文第一句不要复制 #私域",
            "source_url": "https://v.douyin.com/private/",
            "author_name": "OriginalAuthorName",
            "account_id": "douyin_user_123",
            "signed_play_url": "https://signed.example/video.mp4?X-Amz-Signature=SECRET_SIG",
            "api_key": "sk-secret-fixture",
            "token": "bearer-secret-token",
            "headers": {"Authorization": "Bearer nested-header-token"},
            "cookies": {"sessionid": "cookie-secret-value"},
        }
        transcript = "原文第一句不要复制。第二句也不要出现。"
        with _network_disabled():
            builders = _fresh_import("build_video_distillation_report")
            copy_logic = builders.build_copy_logic(
                source=forbidden_source,
                transcript=transcript,
                beats=[
                    {
                        "time_range": "0:00-0:03",
                        "role": "hook",
                        "transcript_evidence": "原文第一句不要复制",
                    }
                ],
                evidence_level="V2_transcript_ready",
            )
            timeline = builders.build_beat_timeline(
                transcript,
                [{"path": "03_keyframes/frames/frame_0000.jpg", "timestamp": 0.0}],
                None,
            )
            production = builders.build_production_logic(
                {"duration_seconds": 8, "width": 1080, "height": 1920, "aspect_ratio": "9:16", "has_audio": True},
                [{"path": "03_keyframes/frames/frame_0000.jpg", "timestamp": 0.0}],
                None,
                copy_logic,
            )
            seed = builders.build_recipe_seed(copy_logic, timeline, production)

        dumped = yaml.safe_dump(seed, allow_unicode=True, sort_keys=False)
        self.assertEqual("capsule_cinema.video_distillation_recipe_seed.v1", seed["schema_version"])
        for forbidden in _scalar_values(forbidden_source) + ["原文第一句不要复制", "第二句也不要出现"]:
            self.assertNotIn(forbidden, dumped)
        self.assertTrue(seed["source_safety"]["source_identity_forbidden"])
        self.assertTrue(seed["source_safety"]["copy_source_script_forbidden"])
        self.assertTrue(seed["source_safety"]["signed_urls_forbidden"])


class VideoDistillationLocalRunTest(unittest.TestCase):
    def test_cli_local_video_defaults_to_output_video_distillation_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_id = "20260705_120000_cli_default"
            missing_video = tmp_path / "missing.mp4"

            with contextlib.chdir(tmp_path), _network_disabled():
                distill_video = _fresh_import("distill_video")
                stdout = io.StringIO()
                argv = [
                    "distill_video.py",
                    "--local-video",
                    str(missing_video),
                    "--run-id",
                    run_id,
                    "--disable-gemini",
                    "--force",
                ]
                with mock.patch.object(sys, "argv", argv), mock.patch("sys.stdout", stdout):
                    distill_video.main()

            result = json.loads(stdout.getvalue())
            out = _resolve_path(result["output_dir"], tmp_path)
            expected = (tmp_path / "output" / "video_distillation" / run_id).resolve()
            self.assertEqual(expected, out.resolve())
            self.assertFalse(result["success"])
            self.assertEqual("download_failed", result["failed_stage"])
            _assert_not_capsules_path(self, out, "CLI output_dir", base=tmp_path)
            manifest = json.loads((out / "artifact_manifest.json").read_text(encoding="utf-8"))
            _assert_manifest_artifacts_stay_in_run(self, out, manifest)

    def test_local_video_run_writes_required_layout_and_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "fixture.mp4"
            if not _make_tiny_video(video):
                self.skipTest("ffmpeg unavailable for tiny video fixture")

            with _network_disabled():
                distill_video = _fresh_import("distill_video")
                result = distill_video.run_local_distillation(
                    local_video=video,
                    output_root=tmp_path / "runs",
                    run_id="20260705_120001_fixture",
                    transcript_text="先看这个结果。然后解释原因。最后评论关键词。",
                    enable_gemini=False,
                    force=True,
                )

            out = _resolve_path(result["output_dir"], tmp_path)
            self.assertTrue(result["success"])
            _assert_under(self, out, tmp_path / "runs", "local run output_dir")
            _assert_not_capsules_path(self, out, "local run output_dir", base=tmp_path)
            for rel in [
                "00_source/source_input.txt",
                "00_source/media_info.json",
                "00_source/source_status.md",
                "01_media/video.mp4",
                "02_transcript/transcript.txt",
                "02_transcript/transcript_analysis.md",
                "03_keyframes/keyframe_index.json",
                "05_copy/copy_logic.yaml",
                "06_video_logic/beat_timeline.json",
                "07_production_logic/production_logic.yaml",
                "08_synthesis/video_distillation.md",
                "08_synthesis/recipe_seed.yaml",
                "evidence_map.json",
                "artifact_manifest.json",
            ]:
                self.assertTrue((out / rel).exists(), rel)

            evidence = json.loads((out / "evidence_map.json").read_text(encoding="utf-8"))
            manifest = json.loads((out / "artifact_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("V6_recipe_seed_ready", evidence["evidence_level"])
            self.assertTrue(any(item["path"].endswith("copy_logic.yaml") for item in manifest["artifacts"]))
            _assert_manifest_artifacts_stay_in_run(self, out, manifest)

    def test_missing_local_video_writes_partial_failure_manifest_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with _network_disabled():
                distill_video = _fresh_import("distill_video")
                result = distill_video.run_local_distillation(
                    local_video=tmp_path / "missing.mp4",
                    output_root=tmp_path / "runs",
                    run_id="20260705_120002_missing",
                    transcript_text="",
                    enable_gemini=False,
                    force=True,
                )

            out = _resolve_path(result["output_dir"], tmp_path)
            self.assertFalse(result["success"])
            self.assertEqual("download_failed", result["failed_stage"])
            _assert_under(self, out, tmp_path / "runs", "missing local output_dir")
            _assert_not_capsules_path(self, out, "missing local output_dir", base=tmp_path)
            self.assertTrue((out / "00_source/source_status.md").is_file())
            self.assertTrue((out / "artifact_manifest.json").is_file())
            self.assertTrue((out / "evidence_map.json").is_file())
            manifest = json.loads((out / "artifact_manifest.json").read_text(encoding="utf-8"))
            _assert_manifest_artifacts_stay_in_run(self, out, manifest)


class VideoDistillationExtractorContractTest(unittest.TestCase):
    def test_url_distillation_uses_mockable_external_extractor_for_copied_share_text_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_workflow_root = tmp_path / "external_video_workflow"
            call_log = tmp_path / "extractor_call.json"
            fake_tool_path = _write_fake_social_media_extractor(fake_workflow_root, call_log)
            self.assertEqual(_external_extractor_tool_path(fake_workflow_root), fake_tool_path)

            copied_share_text = (
                "8.23 复制打开抖音，看看这个视频：先看结果再解释原因 "
                "https://v.douyin.com/NoNetworkShareText/  #短视频"
            )
            with _network_disabled():
                distill_video = _fresh_import("distill_video")
                result = distill_video.run_url_distillation(
                    url=copied_share_text,
                    output_root=tmp_path / "runs",
                    run_id="20260705_120003_share_text",
                    external_video_workflow_root=fake_workflow_root,
                    dotenv_path=tmp_path / ".env",
                    enable_gemini=False,
                    force=True,
                )

            self.assertTrue(call_log.is_file(), "external extractor should be called through the fake surface")
            call = json.loads(call_log.read_text(encoding="utf-8"))
            call_dump = json.dumps(call, ensure_ascii=False, sort_keys=True)
            self.assertIn(copied_share_text, call_dump)
            self.assertNotIn("account-distillation", call_dump)
            kwargs = call["kwargs"]
            self.assertIs(kwargs.get("save_video"), True)
            transcript_flags = {key: value for key, value in kwargs.items() if "transcript" in key}
            self.assertTrue(
                any(value is True for value in transcript_flags.values()),
                f"extractor kwargs should enable transcript acquisition: {kwargs}",
            )

            out = _resolve_path(result["output_dir"], tmp_path)
            _assert_under(self, out, tmp_path / "runs", "share-text output_dir")
            _assert_not_capsules_path(self, out, "share-text output_dir", base=tmp_path)
            extractor_output_arg = kwargs.get("output_dir") or kwargs.get("run_output_dir")
            self.assertTrue(extractor_output_arg, f"extractor kwargs should include a run output dir: {kwargs}")
            _assert_under(self, Path(str(extractor_output_arg)), out, "extractor output_dir")

            self.assertNotEqual("extractor_import_failed", result.get("failed_stage"))
            self.assertNotEqual("parse_failed", result.get("failed_stage"))
            self.assertTrue((out / "00_source" / "source_status.md").is_file())
            self.assertTrue((out / "artifact_manifest.json").is_file())
            self.assertTrue((out / "evidence_map.json").is_file())
            status = (out / "00_source" / "source_status.md").read_text(encoding="utf-8")
            status_and_result = status + "\n" + json.dumps(result, ensure_ascii=False, default=str)
            self.assertIn(str(fake_tool_path), status_and_result)
            self.assertNotIn("account-distillation", status_and_result)
            manifest = json.loads((out / "artifact_manifest.json").read_text(encoding="utf-8"))
            _assert_manifest_artifacts_stay_in_run(self, out, manifest)

    def test_external_extractor_import_cleanup_removes_transitive_workflow_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_workflow_root = tmp_path / "external_video_workflow"
            package_root = fake_workflow_root / "backend" / "video_workflow"
            tool_dir = package_root / "custom_tools" / "extract_content"
            tool_dir.mkdir(parents=True)
            (package_root / "custom_tools" / "__init__.py").write_text("", encoding="utf-8")
            (tool_dir / "__init__.py").write_text("", encoding="utf-8")
            (tool_dir / "helper.py").write_text("HELPER = 'nested helper'\n", encoding="utf-8")
            (package_root / "video_distillation_external_helper.py").write_text(
                "HELPER = 'top-level helper'\n",
                encoding="utf-8",
            )
            (tool_dir / "social_media_content_extractor_tool.py").write_text(
                "from custom_tools.extract_content import helper\n"
                "import video_distillation_external_helper\n\n"
                "class SocialMediaContentExtractorTool:\n"
                "    def _run(self, **kwargs):\n"
                "        return {\n"
                "            'success': True,\n"
                "            'video_file': 'fake.mp4',\n"
                "            'nested_helper': helper.HELPER,\n"
                "            'top_level_helper': video_distillation_external_helper.HELPER,\n"
                "        }\n",
                encoding="utf-8",
            )

            watched_modules = (
                "custom_tools",
                "custom_tools.extract_content",
                "custom_tools.extract_content.helper",
                "custom_tools.extract_content.social_media_content_extractor_tool",
                "video_distillation_external_helper",
            )
            missing = object()
            original_modules = {name: sys.modules.get(name, missing) for name in watched_modules}
            original_sys_path = list(sys.path)

            with _network_disabled():
                distill_video = _fresh_import("distill_video")
                result = distill_video.extract_with_external_tool(
                    "https://v.douyin.com/NoNetworkTransitiveImport/",
                    tmp_path / "run",
                    fake_workflow_root,
                    tmp_path / ".env",
                )

            self.assertTrue(result.get("success"), result)
            self.assertEqual(original_sys_path, sys.path)
            for module_name, original_module in original_modules.items():
                if original_module is missing:
                    self.assertFalse(module_name in sys.modules, f"{module_name} remained in sys.modules")
                else:
                    self.assertIs(sys.modules.get(module_name), original_module)

    def test_url_distillation_records_import_failure_without_live_network_or_private_deps(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with _network_disabled():
                distill_video = _fresh_import("distill_video")
                result = distill_video.run_url_distillation(
                    url="https://v.douyin.com/NoNetworkFixture/",
                    output_root=tmp_path / "runs",
                    run_id="20260705_120003_url_failure",
                    external_video_workflow_root=tmp_path / "missing_video_workflow",
                    dotenv_path=tmp_path / ".env",
                    enable_gemini=False,
                    force=True,
                )

            out = _resolve_path(result["output_dir"], tmp_path)
            self.assertFalse(result["success"])
            self.assertEqual("extractor_import_failed", result["failed_stage"])
            _assert_under(self, out, tmp_path / "runs", "URL failure output_dir")
            _assert_not_capsules_path(self, out, "URL failure output_dir", base=tmp_path)
            status = (out / "00_source" / "source_status.md").read_text(encoding="utf-8")
            self.assertIn("extractor_import_failed", status)
            self.assertIn("references/extraction-tool-contract.md", status)
            self.assertIn(str(DEFAULT_EXTRACTOR_TOOL_PATH), status)
            self.assertIn(str(_external_extractor_tool_path(tmp_path / "missing_video_workflow")), status)
            self.assertNotIn("account-distillation", status)
            self.assertNotIn("XIAOLVFANG_API_TOKEN", status)
            manifest = json.loads((out / "artifact_manifest.json").read_text(encoding="utf-8"))
            _assert_manifest_artifacts_stay_in_run(self, out, manifest)


if __name__ == "__main__":
    unittest.main()
