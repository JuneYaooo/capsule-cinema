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
            name="demo_recipe",
            display_name="GitHub Skills Showcase",
            version="89",
            status="active",
            source_schema="capsule.package.v1",
            source_path="/tmp/demo_recipe.capsule",
        ),
        promise=CapsulePromise(summary="Show a repository in a short video."),
        match=CapsuleMatch(category="demo_recipe", workflow="demo_video"),
        interface=CapsuleInterface(
            inputs={
                "repo_slug": CapsuleInput(type="string", required=True),
                "production_mode": CapsuleInput(
                    type="string",
                    default="demo_mode",
                    options=["demo_mode"],
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


def nested_list(depth: int) -> list[object]:
    value: list[object] = []
    for _ in range(depth):
        value = [value]
    return value


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
                "name": "demo_recipe",
                "candidate_digest": "sha256:candidate",
                "renderer_digest": "sha256:renderer",
            },
        )
        self.assertEqual(instance["inputs"]["repo_slug"], "Agents365-ai/drawio-skill")
        self.assertEqual(
            instance["inputs"]["production_mode"], "demo_mode"
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

    def test_nested_enum_and_options_use_recursive_type_sensitive_json_equality(self) -> None:
        cases = (
            ("enum", [1], [[True]]),
            ("enum", {"value": 1.0}, [{"value": 1}]),
            ("array", [True], [[1]]),
            ("object", {"value": 1}, [{"value": 1.0}]),
        )
        for input_type, value, options in cases:
            with self.subTest(input_type=input_type):
                definition = repo_definition()
                definition.interface.inputs = {
                    "value": CapsuleInput(
                        type=input_type, required=True, options=options
                    )
                }

                result = configure(definition, {"value": value})

                self.assertEqual(result.status, "invalid")
                self.assertEqual(result.issues[0].code, "input_not_allowed")

    def test_option_comparison_never_calls_custom_equality(self) -> None:
        class EqualityTrap:
            def __eq__(self, other: object) -> bool:
                raise AssertionError("custom equality must not be called")

        for input_type in ("enum", "array", "object"):
            with self.subTest(input_type=input_type):
                definition = repo_definition()
                value = {"item": 1} if input_type == "object" else [1]
                trapped_option = (
                    {"item": EqualityTrap()}
                    if input_type == "object"
                    else [EqualityTrap()]
                )
                definition.interface.inputs = {
                    "value": CapsuleInput(
                        type=input_type, required=True, options=[trapped_option]
                    )
                }

                result = configure(definition, {"value": value})

                self.assertEqual(result.status, "invalid")
                self.assertEqual(result.issues[0].code, "input_not_allowed")

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

    def test_container_inputs_preserve_recursive_json_values_exactly(self) -> None:
        definition = repo_definition()
        definition.interface.inputs = {
            "array_value": CapsuleInput(type="array", required=True),
            "list_value": CapsuleInput(type="list", required=True),
            "object_value": CapsuleInput(type="object", required=True),
        }
        huge_integer = 10**1000
        requested = {
            "array_value": [None, True, "text", 7, 2.5, [huge_integer]],
            "list_value": [{"nested": [False, None]}],
            "object_value": {"items": [{"count": huge_integer}], "ratio": 0.25},
        }

        result = configure(definition, requested)

        self.assertEqual(result.status, "ready")
        self.assertEqual(result.data["instance"]["inputs"], requested)
        self.assertIs(
            type(result.data["instance"]["inputs"]["array_value"][-1][0]), int
        )

    def test_container_inputs_reject_non_json_values_at_any_depth(self) -> None:
        cases = (
            ("array", [object()]),
            ("array", [float("nan")]),
            ("list", [[float("inf")]]),
            ("list", [{1, 2}]),
            ("object", {"nested": object()}),
            ("object", {"nested": {1: "non-string key"}}),
        )
        for input_type, value in cases:
            with self.subTest(input_type=input_type, value_type=type(value).__name__):
                definition = repo_definition()
                definition.interface.inputs = {
                    "value": CapsuleInput(type=input_type, required=True)
                }

                result = configure(definition, {"value": value})

                self.assertEqual(result.status, "invalid")
                self.assertEqual(result.issues[0].code, "invalid_input_type")
                self.assertNotIn("instance", result.data)
                json.dumps(result.model_dump(mode="json"), allow_nan=False)

    def test_non_json_container_default_is_invalid_without_serialization(self) -> None:
        definition = repo_definition()
        definition.interface.inputs = {
            "value": CapsuleInput(type="object", default={"nested": {1, 2}})
        }

        result = configure(definition, {})

        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.issues[0].code, "invalid_input_type")
        self.assertNotIn("instance", result.data)

    def test_non_string_requested_key_returns_an_invalid_envelope(self) -> None:
        result = configure(repo_definition(), {7: "not a declared string key"})

        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.issues[0].code, "unknown_input")
        self.assertIsInstance(result.issues[0].subject, str)
        self.assertNotIn("instance", result.data)

    def test_non_string_requested_key_does_not_call_user_display_or_type_name(self) -> None:
        class NameTrapMeta(type):
            def __getattribute__(cls, name: str) -> object:
                if name == "__name__":
                    raise AssertionError("metaclass name lookup must not be called")
                return super().__getattribute__(name)

        class BadKey(metaclass=NameTrapMeta):
            __hash__ = object.__hash__

            def __repr__(self) -> str:
                raise AssertionError("repr must not be called")

            def __str__(self) -> str:
                raise AssertionError("str must not be called")

        result = configure(repo_definition(), {BadKey(): "invalid key"})

        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.issues[0].code, "unknown_input")
        self.assertEqual(
            result.issues[0].subject,
            "requested input key [type=non-json]",
        )
        self.assertNotIn("instance", result.data)

    def test_number_accepts_a_large_integer_within_the_encoding_limit(self) -> None:
        definition = repo_definition()
        definition.interface.inputs = {"value": CapsuleInput(type="number", required=True)}
        value = 10**1000

        result = configure(definition, {"value": value})

        self.assertEqual(result.status, "ready")
        self.assertEqual(result.data["instance"]["inputs"]["value"], value)

    def test_configure_rejects_values_outside_the_safe_json_encoding_domain(self) -> None:
        unsafe_values = (
            ("integer_digits", 10**10000),
            ("nesting", nested_list(2000)),
            ("container_complexity", [None] * 100_001),
        )
        for source in ("requested", "default"):
            for boundary, value in unsafe_values:
                with self.subTest(source=source, boundary=boundary):
                    definition = repo_definition()
                    input_type = "integer" if type(value) is int else "array"
                    definition.interface.inputs = {
                        "value": CapsuleInput(
                            type=input_type,
                            required=source == "requested",
                            default=value if source == "default" else None,
                        )
                    }

                    result = configure(
                        definition,
                        {"value": value} if source == "requested" else {},
                    )

                    self.assertEqual(result.status, "invalid")
                    self.assertEqual(result.issues[0].code, "invalid_input_type")
                    self.assertNotIn("instance", result.data)

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

    def test_write_instance_rejects_non_json_python_payload_without_touching_target(self) -> None:
        def cyclic_list() -> list[object]:
            value: list[object] = []
            value.append(value)
            return value

        invalid_values = (
            float("nan"),
            float("inf"),
            float("-inf"),
            {1, 2},
            object(),
            cyclic_list(),
            {1: "non-string key"},
            {"nested": [object()]},
        )
        for index, value in enumerate(invalid_values):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as tmp:
                result = configure(
                    repo_definition(), {"repo_slug": "Agents365-ai/drawio-skill"}
                )
                instance = CapsuleInstance.model_validate(result.data["instance"])
                instance.inputs["unsafe"] = value
                destination = Path(tmp) / "instance.json"
                destination.write_bytes(b"existing target\n")

                with self.assertRaisesRegex(ValueError, "instance_not_json_data"):
                    write_instance(instance, destination)

                self.assertEqual(destination.read_bytes(), b"existing target\n")
                self.assertEqual(
                    [path for path in destination.parent.iterdir() if path != destination],
                    [],
                )

    def test_write_instance_preserves_large_values_within_encoding_limits(self) -> None:
        result = configure(
            repo_definition(), {"repo_slug": "Agents365-ai/drawio-skill"}
        )
        instance = CapsuleInstance.model_validate(result.data["instance"])
        huge_integer = 10**1000
        instance.inputs["huge_integer"] = huge_integer
        instance.inputs["nested"] = nested_list(50)
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "instance.json"

            write_instance(instance, destination)

            payload = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(payload["inputs"]["huge_integer"], huge_integer)
            self.assertIs(type(payload["inputs"]["huge_integer"]), int)
            self.assertEqual(payload["inputs"]["nested"], nested_list(50))

    def test_write_instance_rejects_values_outside_the_safe_json_encoding_domain(self) -> None:
        unsafe_values = (
            ("integer_digits", 10**10000),
            ("nesting", nested_list(2000)),
            ("container_complexity", [None] * 100_001),
        )
        for boundary, value in unsafe_values:
            with (
                self.subTest(boundary=boundary),
                tempfile.TemporaryDirectory() as tmp,
            ):
                result = configure(
                    repo_definition(), {"repo_slug": "Agents365-ai/drawio-skill"}
                )
                instance = CapsuleInstance.model_validate(result.data["instance"])
                instance.inputs["unsafe"] = value
                destination = Path(tmp) / "instance.json"
                destination.write_bytes(b"existing target\n")

                with self.assertRaisesRegex(ValueError, "instance_not_json_data"):
                    write_instance(instance, destination)

                self.assertEqual(destination.read_bytes(), b"existing target\n")
                self.assertEqual(
                    [path for path in destination.parent.iterdir() if path != destination],
                    [],
                )


if __name__ == "__main__":
    unittest.main()
