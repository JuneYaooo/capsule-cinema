import os
from pathlib import Path


class SoundEffectsManager:
    SOUND_EFFECTS_DIR = Path(os.getenv("VIDEO_SOUND_EFFECTS_DIR", "video_resources/sound_effects"))

    @classmethod
    def get_available_sound_effects(cls):
        if not cls.SOUND_EFFECTS_DIR.exists():
            return []
        return sorted(path.name for path in cls.SOUND_EFFECTS_DIR.iterdir() if path.is_file())

    @classmethod
    def get_sound_effect_path(cls, filename):
        if not filename:
            return None
        path = cls.SOUND_EFFECTS_DIR / filename
        return str(path) if path.exists() else None

