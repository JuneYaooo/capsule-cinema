import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.capsules.catalog import discover_capsules
from src.capsules.loader import load_definition


ROOT = Path(__file__).resolve().parents[2]
CAPSULES = ROOT / "capsules"
EXPECTED = {
    "art_motion",
    "ecommerce_product_showcase",
    "felt_asmr",
    "guofeng_history",
    "life_sim",
    "repo_showcase",
}


def digest_package(package: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        digest.update(path.relative_to(package).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def tracked_package_names() -> set[str]:
    completed = subprocess.run(
        ["git", "ls-files", "capsules/*.capsule/**"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return {
        Path(line).parts[1].removesuffix(".capsule")
        for line in completed.stdout.splitlines()
        if line
    }


class CapsuleCoreRealPackageTests(unittest.TestCase):
    def test_all_tracked_v1_packages_load_without_mutation(self) -> None:
        self.assertEqual(tracked_package_names(), EXPECTED)
        packages = {name: CAPSULES / f"{name}.capsule" for name in EXPECTED}
        self.assertTrue(all(path.is_dir() for path in packages.values()))
        before = {name: digest_package(path) for name, path in packages.items()}
        definitions = {name: load_definition(path) for name, path in packages.items()}
        after = {name: digest_package(path) for name, path in packages.items()}
        self.assertEqual(before, after)
        self.assertEqual(set(definitions), EXPECTED)
        self.assertEqual(
            {item.implementation.runner.kind for item in definitions.values()},
            {"preset", "local_script"},
        )

    def test_catalog_returns_every_tracked_v1_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in EXPECTED:
                (root / f"{name}.capsule").symlink_to(
                    CAPSULES / f"{name}.capsule",
                    target_is_directory=True,
                )

            result = discover_capsules([root])

        self.assertTrue(result.ok)
        self.assertEqual({item["name"] for item in result.data["capsules"]}, EXPECTED)


if __name__ == "__main__":
    unittest.main()
