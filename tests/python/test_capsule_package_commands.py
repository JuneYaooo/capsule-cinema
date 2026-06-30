import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


class CapsulePackageCommandsTest(unittest.TestCase):
    def test_neutral_converter_and_validator_modules_import(self):
        from capsule_package_convert import convert_capsule  # noqa: PLC0415
        from capsule_package_validate import validate_capsule_dir  # noqa: PLC0415

        self.assertTrue(callable(convert_capsule))
        self.assertTrue(callable(validate_capsule_dir))


if __name__ == "__main__":
    unittest.main()
