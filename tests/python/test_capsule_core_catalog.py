import tempfile
import unittest
from pathlib import Path

from src.capsules.catalog import discover_capsules, show_capsule


def write_preset(root: Path, name: str, schema: str = "capsule.package.v1") -> Path:
    package = root / f"{name}.capsule"
    (package / "contracts").mkdir(parents=True)
    (package / "capsule.yaml").write_text(
        f"""schema_version: {schema}
name: {name}
display_name: {name.title()}
version: 1
status: active
execution_mode: preset
summary: {name} summary
category: demo
primary_workflow: demo
capabilities: []
tags: []
when_to_use: []
when_not_to_use: []
entrypoints: {{preset: general_video}}
""",
        encoding="utf-8",
    )
    (package / "contracts" / "input_schema.yaml").write_text(
        "fields: {}\n", encoding="utf-8"
    )
    return package


class CapsuleCoreCatalogTests(unittest.TestCase):
    def test_discovery_is_sorted_and_keeps_valid_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_preset(root, "zeta")
            write_preset(root, "alpha")
            write_preset(root, "broken", "capsule.package.v99")
            result = discover_capsules([root])
            self.assertTrue(result.ok)
            self.assertEqual(
                [item["name"] for item in result.data["capsules"]], ["alpha", "zeta"]
            )
            self.assertEqual(result.data["count"], 2)
            self.assertEqual(result.issues[0].code, "unsupported_capsule_schema")
            self.assertEqual(result.issues[0].severity, "warning")
            self.assertNotIn("implementation", result.data["capsules"][0])

    def test_discovery_deduplicates_resolved_packages_and_scans_immediate_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_preset(root, "visible")
            write_preset(root / "nested", "hidden")
            (root / "ignored.capsule").write_text("not a directory\n", encoding="utf-8")

            result = discover_capsules([root, root / "."])

            self.assertTrue(result.ok)
            self.assertEqual(
                [item["name"] for item in result.data["capsules"]], ["visible"]
            )
            self.assertEqual(result.issues, [])

    def test_show_returns_public_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_preset(root, "demo")

            result = show_capsule("demo", [root])

            self.assertTrue(result.ok)
            self.assertEqual(result.status, "capsule_ready")
            self.assertEqual(result.data["capsule"]["name"], "demo")
            self.assertNotIn("implementation", result.data["capsule"])
            self.assertNotIn("entrypoint", str(result.data["capsule"]))

    def test_show_returns_stable_not_found_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = show_capsule("missing", [Path(tmp)])
            self.assertFalse(result.ok)
            self.assertEqual(result.status, "not_found")
            self.assertEqual(result.issues[0].code, "capsule_not_found")

    def test_show_maps_invalid_package_to_invalid_capsule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = write_preset(Path(tmp), "broken", "capsule.package.v99")

            result = show_capsule(package)

            self.assertFalse(result.ok)
            self.assertEqual(result.status, "invalid_capsule")
            self.assertEqual(result.issues[0].code, "unsupported_capsule_schema")
            self.assertEqual(
                result.issues[0].remediation,
                "Run the doctor command for package diagnostics.",
            )

    def test_public_catalog_errors_keep_codes_without_absolute_package_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="TOP_SECRET_ROOT_") as tmp:
            root = Path(tmp)
            malformed = write_preset(root, "malformed")
            (malformed / "capsule.yaml").write_text(
                "schema_version: [\n", encoding="utf-8"
            )
            missing_entrypoint = write_preset(root, "missing_entrypoint")
            (missing_entrypoint / "capsule.yaml").write_text(
                (missing_entrypoint / "capsule.yaml")
                .read_text(encoding="utf-8")
                .replace("execution_mode: preset", "execution_mode: local_script")
                .replace(
                    "entrypoints: {preset: general_video}",
                    "entrypoints: {local_script: scripts/missing.py}",
                ),
                encoding="utf-8",
            )

            result = discover_capsules([root])
            payload = result.model_dump_json()

            self.assertEqual(
                {issue.code for issue in result.issues},
                {"invalid_capsule_document", "runner_entrypoint_missing"},
            )
            self.assertNotIn(str(root), payload)
            self.assertNotIn("TOP_SECRET_ROOT_", payload)
            for issue in result.issues:
                self.assertIn(issue.subject, {"malformed", "missing_entrypoint"})
                self.assertFalse(
                    set(issue.details)
                    - {"schema_version", "field", "parameters", "return_code"}
                )

            show = show_capsule(malformed)
            self.assertEqual(show.issues[0].code, "invalid_capsule_document")
            self.assertNotIn(str(root), show.model_dump_json())


if __name__ == "__main__":
    unittest.main()
