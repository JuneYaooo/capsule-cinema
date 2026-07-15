"""Local-only BGM selection for the public runtime."""

from pathlib import Path


class MusicManager:
    AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}

    @staticmethod
    def should_add_music(music_selection=None, needs_bgm=True, user_config_enabled=True, add_background_music=True, **kwargs):
        del kwargs
        if music_selection and music_selection.get("needs_bgm") is False:
            return False
        return bool(needs_bgm and user_config_enabled and add_background_music)

    @staticmethod
    def get_music_path(music_selection=None, manual_path=None, background_music_path=None, **kwargs):
        del kwargs
        candidates = [manual_path, background_music_path]
        if isinstance(music_selection, dict):
            candidates.extend(
                music_selection.get(key)
                for key in ("music_path", "bgm_path", "capsule_asset_path")
            )
        for candidate in candidates:
            if not candidate:
                continue
            path = Path(candidate).expanduser()
            if path.is_file() and path.suffix.lower() in MusicManager.AUDIO_EXTENSIONS:
                return str(path)
        return None

    @staticmethod
    def resolve_online_music_path(music_selection=None, output_dir=None, logger=None):
        """The public channel policy does not download from unlisted sources."""
        del music_selection, output_dir
        if logger:
            logger.info("公开渠道策略：未提供本地/胶囊 BGM，跳过在线下载")
        return None
