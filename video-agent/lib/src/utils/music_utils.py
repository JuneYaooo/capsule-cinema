import os
from pathlib import Path


class MusicManager:
    @staticmethod
    def should_add_music(
        music_selection=None,
        needs_bgm=True,
        user_config_enabled=True,
        add_background_music=True,
        **kwargs,
    ):
        del kwargs
        if music_selection and music_selection.get("needs_bgm") is False:
            return False
        return bool(needs_bgm and user_config_enabled and add_background_music)

    @staticmethod
    def get_music_path(music_selection=None, manual_path=None, background_music_path=None, **kwargs):
        del kwargs
        for candidate in (manual_path, background_music_path):
            if candidate and Path(candidate).exists():
                return str(Path(candidate))

        filename = ""
        if isinstance(music_selection, dict):
            filename = music_selection.get("music_filename") or music_selection.get("filename") or ""
        if not filename:
            return None

        resource_root = Path(os.getenv("VIDEO_RESOURCES_PATH", "video_resources"))
        for base_dir in (
            resource_root / "music",
            Path("video_resources") / "music",
            Path(__file__).resolve().parents[2] / "video_resources" / "music",
        ):
            candidate = base_dir / filename
            if candidate.exists():
                return str(candidate)
        return None

