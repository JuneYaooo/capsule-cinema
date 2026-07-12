import unittest

from pydantic import ValidationError

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


def definition() -> CapsuleDefinition:
    return CapsuleDefinition(
        metadata=CapsuleMetadata(
            name="art_motion",
            display_name="Art Motion",
            version="1",
            status="active",
            source_schema="capsule.package.v1",
            source_path="/tmp/art_motion.capsule",
        ),
        promise=CapsulePromise(summary="Turn a prompt into an art-motion short."),
        match=CapsuleMatch(
            category="art_transition",
            workflow="art_first_last_frame_video",
            capabilities=["image_to_video"],
            tags=["art"],
            when_to_use=["art"],
            when_not_to_use=[],
        ),
        interface=CapsuleInterface(
            inputs={
                "prompt": CapsuleInput(type="string", required=True),
                "mood": CapsuleInput(type="string", default="auto", options=["auto", "novel"]),
            }
        ),
        implementation=CapsuleImplementation(
            runner=CapsuleRunner(kind="local_script", entrypoint="scripts/run.py")
        ),
    )


class CapsuleCoreModelTests(unittest.TestCase):
    def test_public_summary_hides_runner_kind_and_entrypoint(self) -> None:
        summary = definition().public_summary()
        self.assertEqual(summary["name"], "art_motion")
        self.assertEqual(summary["required_inputs"], ["prompt"])
        self.assertNotIn("implementation", summary)
        self.assertNotIn("runner", summary)
        self.assertNotIn("entrypoint", str(summary))

    def test_input_options_are_preserved(self) -> None:
        self.assertEqual(definition().interface.inputs["mood"].options, ["auto", "novel"])

    def test_input_numeric_bounds_are_preserved(self) -> None:
        field = CapsuleInput(type="integer", minimum=4, maximum=10)
        self.assertEqual(field.minimum, 4)
        self.assertEqual(field.maximum, 10)

    def test_blank_identity_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            CapsuleMetadata(
                name=" ",
                display_name="Broken",
                version="1",
                status="draft",
                source_schema="capsule.package.v1",
                source_path="/tmp/broken",
            )


if __name__ == "__main__":
    unittest.main()
