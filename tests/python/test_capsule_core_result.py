import json
import unittest

from src.capsules.result import Issue, ResultEnvelope, failure, success


class CapsuleCoreResultTests(unittest.TestCase):
    def test_success_serializes_stable_defaults(self) -> None:
        result = success("catalog_ready", {"count": 2})
        self.assertEqual(
            json.loads(result.model_dump_json()),
            {
                "ok": True,
                "status": "catalog_ready",
                "data": {"count": 2},
                "issues": [],
            },
        )

    def test_failure_preserves_structured_remediation(self) -> None:
        issue = Issue(
            code="capsule_not_found",
            message="Capsule 'missing' was not found.",
            subject="missing",
            remediation="Run `capsule.py list` to inspect local capsules.",
            details={"search_roots": ["/tmp/capsules"]},
        )
        result = failure("not_found", [issue])
        self.assertFalse(result.ok)
        self.assertEqual(result.issues[0].code, "capsule_not_found")
        self.assertEqual(result.issues[0].severity, "error")

    def test_mutable_defaults_are_not_shared(self) -> None:
        first = ResultEnvelope(ok=True, status="one")
        second = ResultEnvelope(ok=True, status="two")
        first.data["changed"] = True
        first.issues.append(Issue(code="x", message="x"))
        self.assertEqual(second.data, {})
        self.assertEqual(second.issues, [])


if __name__ == "__main__":
    unittest.main()
