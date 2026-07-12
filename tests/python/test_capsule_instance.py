import json
import tempfile
import unittest
from pathlib import Path

from src.capsules.instance import CapsuleInstance, configure_instance, write_instance
from src.capsules.model import (
    CapsuleDefinition,
    CapsuleImplementation,
    CapsuleInput,
    CapsuleInterface,
    CapsuleMatch,
    CapsuleMetadata,
    CapsulePromise,
    CapsuleRunner,
)


def repo_definition() -> CapsuleDefinition:
    return CapsuleDefinition(
        metadata=CapsuleMetadata(
            name="repo_showcase",
            display_name="GitHub Skills Showcase",
            version="89",
            status="active",
            source_schema="capsule.package.v1",
            source_path="/tmp/repo_showcase.capsule",
        ),
        promise=CapsulePromise(summary="Show a repository in a short video."),
        match=CapsuleMatch(category="repo_showcase", workflow="repo_showcase_video"),
        interface=CapsuleInterface(
            inputs={
                "repo_slug": CapsuleInput(type="string", required=True),
                "production_mode": CapsuleInput(
                    type="string",
                    default="short_silent_repo_showcase",
                    options=["short_silent_repo_showcase"],
                ),
                "target_duration": CapsuleInput(
                    type="integer", default=10, minimum=1, maximum=10
                ),
                "target_platform": CapsuleInput(
                    type="enum",
                    default="wechat_channels",
                    options=["wechat_channels", "douyin"],
                ),
                "source_asset_manifest_path": CapsuleInput(type="string"),
            }
        ),
        implementation=CapsuleImplementation(
            runner=CapsuleRunner(kind="local_script", entrypoint="scripts/render.py")
        ),
    )


def configure(
    definition: CapsuleDefinition, requested: dict[str, object], *, topic: str = ""
):
    return configure_instance(
        definition,
        requested,
        candidate_digest="sha256:candidate",
        renderer_digest="sha256:renderer",
        topic=topic,
    )


class CapsuleInstanceTests(unittest.TestCase):
    def test_missing_repo_slug_needs_input_and_topic_is_not_inferred(self) -> None:
        result = configure(repo_definition(), {}, topic="Agents365-ai/drawio-skill")

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "needs_input")
        self.assertNotIn("instance", result.data)
        self.assertEqual([issue.code for issue in result.issues], ["missing_required_input"])
        self.assertEqual(result.issues[0].subject, "repo_slug")

    def test_explicit_repo_slug_applies_and_records_defaults(self) -> None:
        result = configure(
            repo_definition(), {"repo_slug": "Agents365-ai/drawio-skill"}
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "ready")
        instance = result.data["instance"]
        self.assertEqual(instance["schema_version"], "capsule.instance/v1")
        self.assertEqual(
            instance["capsule"],
            {
                "name": "repo_showcase",
                "candidate_digest": "sha256:candidate",
                "renderer_digest": "sha256:renderer",
            },
        )
        self.assertEqual(instance["inputs"]["repo_slug"], "Agents365-ai/drawio-skill")
        self.assertEqual(
            instance["inputs"]["production_mode"], "short_silent_repo_showcase"
        )
        self.assertEqual(instance["inputs"]["target_duration"], 10)
        self.assertEqual(instance["inputs"]["target_platform"], "wechat_channels")
        self.assertEqual(
            instance["resolved"]["defaults_applied"],
            ["production_mode", "target_duration", "target_platform"],
        )
        self.assertEqual(instance["resolved"]["inferred_values"], [])
        self.assertEqual(
            instance["approvals"], {"fallback_policy": "no_promise_change"}
        )

    def test_explicit_values_take_precedence_and_manifest_path_is_preserved(self) -> None:
        manifest_path = "../evidence/source asset manifest.json"
        result = configure(
            repo_definition(),
            {
                "repo_slug": "Agents365-ai/drawio-skill",
                "target_duration": 8,
                "target_platform": "douyin",
                "source_asset_manifest_path": manifest_path,
            },
        )

        instance = result.data["instance"]
        self.assertEqual(instance["inputs"]["target_duration"], 8)
        self.assertEqual(instance["inputs"]["target_platform"], "douyin")
        self.assertEqual(instance["inputs"]["source_asset_manifest_path"], manifest_path)
        self.assertEqual(instance["resolved"]["defaults_applied"], ["production_mode"])

    def test_unknown_input_is_invalid(self) -> None:
        result = configure(
            repo_definition(),
            {"repo_slug": "Agents365-ai/drawio-skill", "legacy_cli_flag": True},
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "invalid")
        self.assertNotIn("instance", result.data)
        self.assertEqual([issue.code for issue in result.issues], ["unknown_input"])
        self.assertEqual(result.issues[0].subject, "legacy_cli_flag")

    def test_integer_and_number_reject_boolean_values(self) -> None:
        definition = repo_definition()
        definition.interface.inputs["confidence"] = CapsuleInput(type="number")
        for name, value in (("target_duration", True), ("confidence", False)):
            with self.subTest(name=name):
                result = configure(
                    definition,
                    {"repo_slug": "Agents365-ai/drawio-skill", name: value},
                )
                self.assertEqual(result.status, "invalid")
                self.assertEqual(result.issues[0].code, "invalid_input_type")
                self.assertEqual(result.issues[0].subject, name)

    def test_maximum_and_options_are_enforced(self) -> None:
        cases = (
            ("target_duration", 11, "input_above_maximum"),
            ("production_mode", "long_form", "input_not_allowed"),
        )
        for name, value, code in cases:
            with self.subTest(name=name):
                result = configure(
                    repo_definition(),
                    {"repo_slug": "Agents365-ai/drawio-skill", name: value},
                )
                self.assertEqual(result.status, "invalid")
                self.assertEqual(result.issues[0].code, code)
                self.assertEqual(result.issues[0].subject, name)

    def test_all_normalized_v1_input_types_bind_without_coercion(self) -> None:
        definition = repo_definition()
        definition.interface.inputs = {
            "string_value": CapsuleInput(type="string", required=True),
            "integer_value": CapsuleInput(type="integer", required=True),
            "number_value": CapsuleInput(type="number", required=True),
            "boolean_value": CapsuleInput(type="boolean", required=True),
            "array_value": CapsuleInput(type="array", required=True),
            "list_value": CapsuleInput(type="list", required=True),
            "object_value": CapsuleInput(type="object", required=True),
            "enum_value": CapsuleInput(
                type="enum", required=True, options=["calm", "vivid"]
            ),
        }
        requested = {
            "string_value": "text",
            "integer_value": 3,
            "number_value": 3.5,
            "boolean_value": True,
            "array_value": [1, "two"],
            "list_value": [False],
            "object_value": {"nested": 1},
            "enum_value": "vivid",
        }

        result = configure(definition, requested)

        self.assertEqual(result.status, "ready")
        self.assertEqual(result.data["instance"]["inputs"], requested)

    def test_number_accepts_an_arbitrarily_large_integer_without_float_coercion(self) -> None:
        definition = repo_definition()
        definition.interface.inputs = {"value": CapsuleInput(type="number", required=True)}
        value = 10**1000

        result = configure(definition, {"value": value})

        self.assertEqual(result.status, "ready")
        self.assertEqual(result.data["instance"]["inputs"]["value"], value)

    def test_normalized_v1_input_types_reject_wrong_python_types(self) -> None:
        cases = (
            (CapsuleInput(type="string"), 1),
            (CapsuleInput(type="boolean"), 1),
            (CapsuleInput(type="array"), (1, 2)),
            (CapsuleInput(type="list"), {"0": 1}),
            (CapsuleInput(type="object"), [("key", "value")]),
            (CapsuleInput(type="enum", options=["1"]), 1),
        )
        for field, value in cases:
            with self.subTest(type=field.type):
                definition = repo_definition()
                definition.interface.inputs = {"value": field}
                result = configure(definition, {"value": value})
                self.assertEqual(result.status, "invalid")
                self.assertIn(
                    result.issues[0].code,
                    {"invalid_input_type", "input_not_allowed"},
                )

    def test_minimum_and_wrong_container_types_are_invalid(self) -> None:
        definition = repo_definition()
        definition.interface.inputs["items"] = CapsuleInput(type="array")
        definition.interface.inputs["metadata"] = CapsuleInput(type="object")
        cases = (
            ("target_duration", 0, "input_below_minimum"),
            ("items", ("not", "a", "list"), "invalid_input_type"),
            ("metadata", [], "invalid_input_type"),
        )
        for name, value, code in cases:
            with self.subTest(name=name):
                result = configure(
                    definition,
                    {"repo_slug": "Agents365-ai/drawio-skill", name: value},
                )
                self.assertEqual(result.status, "invalid")
                self.assertEqual(result.issues[0].code, code)

    def test_binding_does_not_mutate_definition(self) -> None:
        definition = repo_definition()
        before = definition.model_dump(mode="json")

        result = configure(
            definition,
            {"repo_slug": "Agents365-ai/drawio-skill", "target_duration": 8},
        )

        self.assertEqual(result.status, "ready")
        self.assertEqual(definition.model_dump(mode="json"), before)

    def test_write_instance_serializes_the_locked_instance(self) -> None:
        result = configure(
            repo_definition(), {"repo_slug": "Agents365-ai/drawio-skill"}
        )
        instance = CapsuleInstance.model_validate(result.data["instance"])
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "nested" / "instance.json"

            written = write_instance(instance, destination)

            self.assertEqual(written, destination)
            self.assertEqual(
                json.loads(destination.read_text(encoding="utf-8")),
                instance.model_dump(mode="json"),
            )


if __name__ == "__main__":
    unittest.main()
