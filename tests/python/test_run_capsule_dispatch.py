import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class RunCapsuleDispatchTest(unittest.TestCase):
    def make_local_script_capsule(self, root: Path) -> Path:
        capsule = root / "demo_local.capsule"
        write_text(
            capsule / "capsule.yaml",
            """
schema_version: capsule.package.v1
profile: video.okf.capsule.v1
name: demo_local
display_name: Demo Local
version: 1
status: active
execution_mode: local_script
category: demo
primary_workflow: demo
summary: Demo local-script capsule.
capabilities:
- local_script
tags:
- demo
when_to_use:
- demo
when_not_to_use: []
read_order: {}
entrypoints:
  local_script: scripts/demo_executor.py
""".lstrip(),
        )
        write_text(capsule / "CARD.md", "# Demo Local\n")
        write_text(
            capsule / "contracts" / "runtime.yaml",
            """
roles: {}
output_contract:
  voice: none
defaults:
  aspect_ratio: '16:9'
  target_duration: 30
""".lstrip(),
        )
        write_text(capsule / "contracts" / "input_schema.yaml", "fields: {}\n")
        write_text(capsule / "quality" / "rules.yaml", "rules: []\n")
        write_text(capsule / "assets" / "index.yaml", "assets: []\n")
        write_text(
            capsule / "scripts" / "demo_executor.py",
            """
#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--topic", required=True)
parser.add_argument("--params", required=True)
parser.add_argument("--output-dir", required=True)
args = parser.parse_args()

out = Path(args.output_dir)
out.mkdir(parents=True, exist_ok=True)
params = json.loads(Path(args.params).read_text(encoding="utf-8"))
(out / "reports").mkdir(exist_ok=True)
(out / "reports" / "executor_args.json").write_text(json.dumps({
    "topic": args.topic,
    "params_path": args.params,
    "output_dir": args.output_dir,
    "aspect_ratio": params.get("aspect_ratio"),
    "config_aspect_ratio": params.get("config", {}).get("aspect_ratio"),
}, ensure_ascii=False, indent=2), encoding="utf-8")
(out / "artifact_manifest.json").write_text(json.dumps({
    "schema_version": 1,
    "capsule": "demo_local",
    "artifacts": []
}, ensure_ascii=False, indent=2), encoding="utf-8")
""".lstrip(),
        )
        return capsule

    def test_dispatcher_invokes_capsule_local_script_with_merged_params(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            capsule = self.make_local_script_capsule(tmp)
            input_params = tmp / "params.json"
            input_params.write_text(
                json.dumps({"generation_budget_ack": True}, ensure_ascii=False),
                encoding="utf-8",
            )
            output_dir = tmp / "run"

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "run_capsule.py"),
                    "--capsule",
                    str(capsule),
                    "--topic",
                    "首富千金的一生",
                    "--params",
                    str(input_params),
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            executor_args = json.loads((output_dir / "reports" / "executor_args.json").read_text(encoding="utf-8"))
            self.assertEqual(executor_args["topic"], "首富千金的一生")
            self.assertEqual(executor_args["output_dir"], str(output_dir.resolve()))
            self.assertEqual(executor_args["aspect_ratio"], "16:9")
            self.assertEqual(executor_args["config_aspect_ratio"], "16:9")

            dispatch = json.loads((output_dir / "reports" / "capsule_dispatch.json").read_text(encoding="utf-8"))
            self.assertTrue(dispatch["ok"])
            self.assertEqual(dispatch["capsule"], "demo_local")
            self.assertEqual(dispatch["execution_mode"], "local_script")
            self.assertTrue(dispatch["local_script_path"].endswith("scripts/demo_executor.py"))

            manifest = json.loads((output_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["execution_script"], dispatch["local_script_path"])
            self.assertEqual(manifest["capsule_execution_mode"], "local_script")

    def test_dispatcher_runs_release_gate_report_after_local_script(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            capsule = self.make_local_script_capsule(tmp)
            write_text(
                capsule / "quality" / "release_gates.yaml",
                """
gates:
- id: fallback_generated_card_preview_only
  phase: release
  severity: blocker
  checker: fallback_blocks_approved_release
  params:
    fallback_markers:
    - fallback_generated_card
    allowed_release_status:
    - preview
    - blocked
""".lstrip(),
            )
            script = capsule / "scripts" / "demo_executor.py"
            text = script.read_text(encoding="utf-8")
            script.write_text(
                text.replace(
                    '"artifacts": []',
                    '"status": "approved", "artifacts": [{"category": "source_material", "asset_type": "fallback_generated_card"}]',
                ),
                encoding="utf-8",
            )
            output_dir = tmp / "run"

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "run_capsule.py"),
                    "--capsule",
                    str(capsule),
                    "--topic",
                    "fallback should block",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0, result.stderr + result.stdout)
            gate_report = json.loads((output_dir / "qa" / "capsule_gate_report.json").read_text(encoding="utf-8"))
            self.assertFalse(gate_report["ok"])
            self.assertIn("fallback_generated_card_preview_only", gate_report["blockers"])
            dispatch = json.loads((output_dir / "reports" / "capsule_dispatch.json").read_text(encoding="utf-8"))
            self.assertFalse(dispatch["ok"])
            self.assertEqual(dispatch["error"], "capsule_release_gates_blocked")


if __name__ == "__main__":
    unittest.main()
