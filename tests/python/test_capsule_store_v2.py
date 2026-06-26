import argparse
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAPSULE_STORE_PATH = ROOT / "scripts" / "capsule_store.py"


def load_capsule_store():
    spec = importlib.util.spec_from_file_location("capsule_store", CAPSULE_STORE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upsert_args(**overrides):
    base = dict(
        name="cap",
        display_name="Cap",
        status="active",
        execution_mode="preset",
        description="d",
        category="test",
        tags="test",
        config_json="{}",
        method_json="{}",
        input_schema_json='{"topic":{"type":"string","required":true}}',
        quality_rules_json='[{"id":"final_video_required","type":"artifact_required"}]',
        local_assets_json="[]",
        examples_json=None,
        local_script_path="",
        notes="",
        bump_version=False,
        changelog="create",
        change_source="test",
        allow_ephemeral=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class NormalizeAssetReuseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = load_capsule_store()

    def test_defaults_reuse_to_reference_only(self):
        out = self.store.normalize_local_assets([{"key": "a", "role": "bgm", "path": "/x.mp3"}])
        self.assertEqual(out[0]["reuse"], "reference_only")

    def test_keeps_reuse_always(self):
        out = self.store.normalize_local_assets(
            [{"key": "a", "role": "bgm", "reuse": "always", "path": "/x.mp3"}]
        )
        self.assertEqual(out[0]["reuse"], "always")

    def test_invalid_reuse_coerced_to_reference_only(self):
        out = self.store.normalize_local_assets(
            [{"key": "a", "role": "bgm", "reuse": "whatever", "path": "/x.mp3"}]
        )
        self.assertEqual(out[0]["reuse"], "reference_only")


class StoreV2DbTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = load_capsule_store()

    def setUp(self):
        self._old_db = os.environ.get("VIDEO_CAPSULE_DB")
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["VIDEO_CAPSULE_DB"] = str(Path(self._tmp.name) / "capsules.sqlite")

    def tearDown(self):
        if self._old_db is None:
            os.environ.pop("VIDEO_CAPSULE_DB", None)
        else:
            os.environ["VIDEO_CAPSULE_DB"] = self._old_db
        self._tmp.cleanup()

    def _show(self, name):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.store.show(argparse.Namespace(name=name, json=True, contract=False))
        return json.loads(out.getvalue())

    def test_examples_round_trip(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.store.upsert(
                _upsert_args(
                    name="ex_cap",
                    examples_json='[{"kind":"opening_terms","value":["玄学自救"]}]',
                )
            )
        payload = self._show("ex_cap")
        self.assertEqual(payload["examples"][0]["kind"], "opening_terms")
        self.assertEqual(payload["examples"][0]["value"], ["玄学自救"])

    def test_doctor_fails_on_ephemeral_asset_path(self):
        eph = Path(self._tmp.name) / "output" / "run_123" / "release" / "final.mp3"
        eph.parent.mkdir(parents=True, exist_ok=True)
        eph.write_bytes(b"x")
        with contextlib.redirect_stdout(io.StringIO()):
            self.store.upsert(
                _upsert_args(
                    name="eph_cap",
                    allow_ephemeral=True,
                    local_assets_json=json.dumps(
                        [{"key": "bgm", "role": "bgm", "reuse": "always", "path": str(eph)}]
                    ),
                )
            )
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stdout(io.StringIO()):
                self.store.doctor(argparse.Namespace(name="eph_cap", warnings_ok=True))

    def test_doctor_fails_on_non_enum_asset_role(self):
        stable = Path(self._tmp.name) / "assets" / "x.mp4"
        stable.parent.mkdir(parents=True, exist_ok=True)
        stable.write_bytes(b"x")
        with contextlib.redirect_stdout(io.StringIO()):
            self.store.upsert(
                _upsert_args(
                    name="role_cap",
                    local_assets_json=json.dumps(
                        [{"key": "vid", "role": "successful_run_example", "reuse": "always",
                          "path": str(stable)}]
                    ),
                )
            )
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stdout(io.StringIO()):
                self.store.doctor(argparse.Namespace(name="role_cap", warnings_ok=True))

    def test_doctor_fails_on_absolute_path_in_method(self):
        baked = Path(self._tmp.name) / "output" / "run" / "preview.mp4"
        baked.parent.mkdir(parents=True, exist_ok=True)
        baked.write_bytes(b"x")
        with contextlib.redirect_stdout(io.StringIO()):
            self.store.upsert(
                _upsert_args(
                    name="path_cap",
                    method_json=json.dumps({"opening": {"accepted_reference_video": str(baked)}}),
                )
            )
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stdout(io.StringIO()):
                self.store.doctor(argparse.Namespace(name="path_cap", warnings_ok=True))

    def test_doctor_ok_on_clean_v2_capsule(self):
        stable = Path(self._tmp.name) / "capsule_assets" / "bgm.mp3"
        stable.parent.mkdir(parents=True, exist_ok=True)
        stable.write_bytes(b"x")
        with contextlib.redirect_stdout(io.StringIO()):
            self.store.upsert(
                _upsert_args(
                    name="clean_cap",
                    method_json=json.dumps({"opening": ["单窗口抽取卡，按主题写候选词"]}),
                    local_assets_json=json.dumps(
                        [{"key": "bgm", "role": "bgm", "reuse": "always", "path": str(stable)}]
                    ),
                    examples_json='[{"kind":"opening_terms","value":["玄学自救"]}]',
                )
            )
        # Clean capsule: no issues, warnings tolerated.
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.store.doctor(argparse.Namespace(name="clean_cap", warnings_ok=True))
        self.assertIn("doctor:", out.getvalue())

    def test_record_run_dir_persists_quality_failure_and_feedback(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.store.upsert(_upsert_args(name="qa_fail_cap"))

        run_dir = Path(self._tmp.name) / "output" / "qa_fail_run"
        qa_dir = run_dir / "qa"
        qa_dir.mkdir(parents=True)
        final_video = run_dir / "release" / "final.mp4"
        final_video.parent.mkdir(parents=True)
        final_video.write_bytes(b"fake mp4")
        qa_report = {
            "ok": False,
            "release_ready": False,
            "status": "fail",
            "score": 67,
            "score_max": 100,
            "final_video": str(final_video),
            "probe": {"ok": True, "duration": 8.0, "width": 1080, "height": 1920},
            "blockers": [
                {
                    "id": "main_subject_not_deformed",
                    "description": "玻璃盒压下后内容物穿过玻璃边界。",
                    "detail": "00:08",
                }
            ],
            "warnings": [],
        }
        qa_path = qa_dir / "video_quality_score.json"
        qa_path.write_text(json.dumps(qa_report, ensure_ascii=False), encoding="utf-8")

        with contextlib.redirect_stdout(io.StringIO()):
            self.store.record_run_dir(
                argparse.Namespace(
                    name="qa_fail_cap",
                    run_dir=str(run_dir),
                    topic="asmr glass box",
                    status="",
                    input_params_json=None,
                    manifest_path="",
                    qa_report=str(qa_path),
                    final_video="",
                    notes="",
                    error="",
                )
            )

        payload = self._show("qa_fail_cap")
        last_run = payload["run_history"][-1]
        self.assertEqual("failed", last_run["status"])
        self.assertEqual("fail", last_run["quality_status"])
        self.assertFalse(last_run["release_ready"])
        self.assertEqual(67, last_run["quality_score"])
        self.assertEqual(str(qa_path.resolve()), last_run["quality_report_path"])
        self.assertEqual("main_subject_not_deformed", last_run["qa_blockers"][0]["id"])
        self.assertEqual(str(final_video), last_run["final_video"])
        self.assertEqual("qa_failure", payload["feedback"][-1]["type"])
        self.assertEqual("blocker", payload["feedback"][-1]["severity"])
        self.assertIn("main_subject_not_deformed", payload["feedback"][-1]["summary"])

    def test_doctor_fails_active_capsule_with_latest_failed_run(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.store.upsert(_upsert_args(name="latest_failed_cap"))
            self.store.record_run(
                argparse.Namespace(
                    name="latest_failed_cap",
                    topic="failed sample",
                    status="failed",
                    input_params_json=None,
                    workspace_dir="",
                    final_video="",
                    manifest_path="",
                    compliance_report_json=None,
                    metrics_json=json.dumps({"quality_status": "fail"}),
                    notes="",
                    error="quality blockers",
                )
            )

        with self.assertRaises(SystemExit):
            with contextlib.redirect_stdout(io.StringIO()):
                self.store.doctor(argparse.Namespace(name="latest_failed_cap", warnings_ok=True))

    def test_list_shows_latest_run_status(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.store.upsert(_upsert_args(name="listed_failed_cap"))
            self.store.record_run(
                argparse.Namespace(
                    name="listed_failed_cap",
                    topic="failed sample",
                    status="failed",
                    input_params_json=None,
                    workspace_dir="",
                    final_video="",
                    manifest_path="",
                    compliance_report_json=None,
                    metrics_json=None,
                    notes="",
                    error="quality blockers",
                )
            )

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.store.list_capsules(argparse.Namespace(status=None, execution_mode=None))

        self.assertIn("listed_failed_cap", output.getvalue())
        self.assertIn("last=failed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
