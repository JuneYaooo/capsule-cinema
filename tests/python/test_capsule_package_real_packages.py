import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


CAPSULES = [
    "repo_showcase",
    "life_sim",
    "felt_asmr",
    "guofeng_history",
    "ecommerce_product_showcase",
    "art_motion",
]


class CapsulePackageRealPackagesTest(unittest.TestCase):
    def test_active_capsules_live_under_capsules_not_capsules_v3(self):
        for name in CAPSULES:
            with self.subTest(name=name):
                self.assertTrue((ROOT / "capsules" / f"{name}.capsule" / "capsule.yaml").is_file())
        self.assertFalse((ROOT / "capsules_v3").exists())


if __name__ == "__main__":
    unittest.main()
