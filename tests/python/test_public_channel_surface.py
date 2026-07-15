import json
import subprocess
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


class PublicChannelSurfaceTest(unittest.TestCase):
    def setUp(self):
        self.registry = yaml.safe_load(
            (ROOT / "lib/config/tool_registry.yaml").read_text(encoding="utf-8")
        )
        self.capabilities = yaml.safe_load(
            (ROOT / "lib/config/tool_capabilities.yaml").read_text(encoding="utf-8")
        )
        self.env_registry = json.loads(
            (ROOT / "lib/config/env_registry.json").read_text(encoding="utf-8")
        )

    def test_public_provider_allowlist(self):
        allowed = {
            "volcengine_ark",
            "official_tts",
            "minimax_official",
            "doubao_official",
            "runninghub",
            "local",
        }
        providers = {
            record.get("provider")
            for record in self.registry["tools"].values()
            if record.get("provider")
        }
        self.assertLessEqual(providers, allowed)
        self.assertNotIn("local_only", {record.get("status") for record in self.registry["tools"].values()})

    def test_public_cloud_env_categories_are_allowlisted(self):
        allowed_categories = {
            "runtime",
            "planning_runtime",
            "volcengine_official",
            "minimax_official",
            "doubao_official",
            "runninghub_example",
        }
        self.assertLessEqual(
            {record["category"] for record in self.env_registry["env"]},
            allowed_categories,
        )

    def test_capabilities_match_public_registry(self):
        registered = set(self.registry["tools"])
        for tool_name, record in self.capabilities["tools"].items():
            self.assertIn(tool_name, registered)
            self.assertIn(record.get("status"), {"approved", "example"})

    def test_tracked_tree_does_not_include_local_adapter_files(self):
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        tracked = result.stdout.splitlines()
        self.assertFalse(any("/local_" in path and "_adapter" in path for path in tracked))
        self.assertFalse(any(path.startswith("local-channels/") for path in tracked))

    def test_public_capsules_do_not_select_local_only_tools(self):
        public_tools = set(self.registry["tools"])
        result = subprocess.run(
            ["git", "ls-files", "capsules/*.capsule/contracts/runtime.yaml"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        for relative_path in result.stdout.splitlines():
            runtime_path = ROOT / relative_path
            data = yaml.safe_load(runtime_path.read_text(encoding="utf-8")) or {}
            for role in (data.get("roles") or {}).values():
                selected = role.get("validated_with") if isinstance(role, dict) else None
                if selected and "/" not in selected and selected.endswith("Tool"):
                    self.assertIn(selected, public_tools, runtime_path)


if __name__ == "__main__":
    unittest.main()
