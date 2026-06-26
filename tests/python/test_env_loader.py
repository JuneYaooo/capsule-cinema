import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENV_LOADER_PATH = ROOT / "scripts" / "env_loader.py"


def load_env_loader():
    spec = importlib.util.spec_from_file_location("env_loader", ENV_LOADER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EnvLoaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = load_env_loader()

    def test_loads_repository_root_dotenv_by_default(self):
        key = "CAPSULE_CINEMA_ENV_LOADER_TEST_KEY"
        old_key = os.environ.get(key)
        old_dotenv = os.environ.get("DOTENV_PATH")
        try:
            os.environ.pop(key, None)
            os.environ.pop("DOTENV_PATH", None)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                env_path = root / ".env"
                env_path.write_text(f"{key}=loaded_from_root\n", encoding="utf-8")

                loaded = self.loader.load_video_agent_env(root)

                self.assertEqual(env_path, loaded)
                self.assertEqual("loaded_from_root", os.environ.get(key))
        finally:
            if old_key is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_key
            if old_dotenv is None:
                os.environ.pop("DOTENV_PATH", None)
            else:
                os.environ["DOTENV_PATH"] = old_dotenv

    def test_dotenv_path_override_still_wins(self):
        key = "CAPSULE_CINEMA_ENV_LOADER_OVERRIDE_TEST_KEY"
        old_key = os.environ.get(key)
        old_dotenv = os.environ.get("DOTENV_PATH")
        try:
            os.environ.pop(key, None)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "repo"
                root.mkdir()
                override = Path(tmp) / "override.env"
                (root / ".env").write_text(f"{key}=root_value\n", encoding="utf-8")
                override.write_text(f"{key}=override_value\n", encoding="utf-8")
                os.environ["DOTENV_PATH"] = str(override)

                loaded = self.loader.load_video_agent_env(root)

                self.assertEqual(override, loaded)
                self.assertEqual("override_value", os.environ.get(key))
        finally:
            if old_key is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_key
            if old_dotenv is None:
                os.environ.pop("DOTENV_PATH", None)
            else:
                os.environ["DOTENV_PATH"] = old_dotenv


if __name__ == "__main__":
    unittest.main()
