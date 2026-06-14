import hashlib
import mimetypes
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests


class MusicManager:
    AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}
    AUDIO_CONTENT_TYPES = {
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/aac",
        "audio/wav",
        "audio/x-wav",
        "audio/ogg",
        "audio/flac",
        "application/ogg",
    }

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

        return None

    @classmethod
    def resolve_online_music_path(cls, music_selection=None, output_dir=None, logger=None) -> str | None:
        """Download music from an explicit URL or a licensed music search provider.

        This intentionally avoids scraping arbitrary web pages. Direct URLs are accepted
        only when the user/capsule explicitly supplies them. Search uses Jamendo
        when JAMENDO_CLIENT_ID is configured, then Internet Archive CC/public-domain audio.
        """
        if not isinstance(music_selection, dict):
            return None

        output_root = Path(output_dir or Path.cwd() / "online_music")
        output_root.mkdir(parents=True, exist_ok=True)

        direct_url = cls._first_non_empty(
            music_selection,
            "music_url",
            "music_download_url",
            "audio_url",
            "download_url",
            "web_music_url",
        )
        if direct_url:
            cls._log(logger, f"🌐 下载用户指定在线音乐: {cls._safe_url_for_log(direct_url)}")
            return cls.download_audio_url(
                direct_url,
                output_root,
                label=music_selection.get("music_style_id") or music_selection.get("style_id") or "direct",
                logger=logger,
            )

        source = str(music_selection.get("music_source") or "").strip().lower()
        if source and source not in {"online", "web", "search", "jamendo", "archive", "internet_archive"}:
            return None

        if os.getenv("JAMENDO_CLIENT_ID"):
            path = cls.search_and_download_jamendo(music_selection, output_root, logger=logger)
            if path:
                return path

        if str(os.getenv("ONLINE_MUSIC_ENABLE_ARCHIVE") or "true").lower() not in {"0", "false", "no"}:
            return cls.search_and_download_internet_archive(music_selection, output_root, logger=logger)

        return None

    @classmethod
    def search_and_download_jamendo(cls, music_selection: dict[str, Any], output_dir: Path, logger=None) -> str | None:
        query = (
            music_selection.get("music_query")
            or music_selection.get("generation_prompt")
            or music_selection.get("reason")
            or music_selection.get("style")
            or music_selection.get("music_style_id")
            or "instrumental background music"
        )
        client_id = os.getenv("JAMENDO_CLIENT_ID")
        base_url = (os.getenv("JAMENDO_API_BASE") or "https://api.jamendo.com/v3.0").rstrip("/")
        limit = int(os.getenv("ONLINE_MUSIC_SEARCH_LIMIT") or "10")
        timeout = float(os.getenv("ONLINE_MUSIC_REQUEST_TIMEOUT") or "30")

        params = {
            "client_id": client_id,
            "format": "json",
            "limit": max(1, min(limit, 20)),
            "search": query,
            "include": "musicinfo",
            "audioformat": "mp32",
            "groupby": "artist_id",
            "order": "popularity_total",
        }
        if music_selection.get("tags"):
            params["tags"] = music_selection["tags"]

        url = f"{base_url}/tracks/"
        cls._log(logger, f"🔎 Jamendo 搜索在线音乐: {query}")
        response = requests.get(url, params=params, timeout=timeout)
        if response.status_code != 200:
            cls._log(logger, f"⚠️ Jamendo 搜索失败: HTTP {response.status_code}", warning=True)
            return None

        data = response.json()
        results = data.get("results") or []
        for item in results:
            download_url = cls._jamendo_download_url(item)
            if not download_url:
                continue

            title = item.get("name") or item.get("id") or "jamendo"
            artist = item.get("artist_name") or "unknown_artist"
            license_url = item.get("license_ccurl") or item.get("license_url") or ""
            label = f"{artist}_{title}"
            cls._log(
                logger,
                f"🎵 选中 Jamendo 曲目: {artist} - {title}"
                + (f" ({license_url})" if license_url else ""),
            )
            path = cls.download_audio_url(download_url, output_dir, label=label, logger=logger)
            if path:
                return path

        cls._log(logger, "⚠️ Jamendo 没有返回可下载音频", warning=True)
        return None

    @classmethod
    def search_and_download_internet_archive(
        cls,
        music_selection: dict[str, Any],
        output_dir: Path,
        logger=None,
    ) -> str | None:
        query = (
            music_selection.get("music_query")
            or music_selection.get("generation_prompt")
            or music_selection.get("reason")
            or music_selection.get("style")
            or music_selection.get("music_style_id")
            or "instrumental background music"
        )
        rows = int(os.getenv("ONLINE_MUSIC_SEARCH_LIMIT") or "10")
        timeout = float(os.getenv("ONLINE_MUSIC_REQUEST_TIMEOUT") or "30")
        search_base = os.getenv("INTERNET_ARCHIVE_SEARCH_API") or "https://archive.org/advancedsearch.php"
        metadata_base = (os.getenv("INTERNET_ARCHIVE_METADATA_BASE") or "https://archive.org/metadata").rstrip("/")
        download_base = (os.getenv("INTERNET_ARCHIVE_DOWNLOAD_BASE") or "https://archive.org/download").rstrip("/")

        # Keep the query license-scoped. This is not arbitrary page scraping.
        archive_query = (
            f'mediatype:audio AND (licenseurl:*creativecommons.org* OR licenseurl:*publicdomain*) '
            f'AND ({query})'
        )
        params = {
            "q": archive_query,
            "output": "json",
            "rows": max(1, min(rows, 20)),
            "page": 1,
            "fl[]": ["identifier", "title", "creator", "licenseurl"],
            "sort[]": "downloads desc",
        }

        cls._log(logger, f"🔎 Internet Archive 搜索授权音乐: {query}")
        try:
            response = requests.get(search_base, params=params, timeout=timeout)
        except Exception as exc:
            cls._log(logger, f"⚠️ Internet Archive 搜索异常: {exc}", warning=True)
            return None

        if response.status_code != 200:
            cls._log(logger, f"⚠️ Internet Archive 搜索失败: HTTP {response.status_code}", warning=True)
            return None

        docs = ((response.json().get("response") or {}).get("docs") or [])
        for item in docs:
            license_url = item.get("licenseurl") or ""
            if not cls._is_approved_license_url(license_url):
                continue
            identifier = item.get("identifier")
            if not identifier:
                continue

            metadata_url = f"{metadata_base}/{quote(identifier, safe='')}"
            try:
                metadata_response = requests.get(metadata_url, timeout=timeout)
            except Exception as exc:
                cls._log(logger, f"⚠️ Internet Archive metadata 异常: {exc}", warning=True)
                continue
            if metadata_response.status_code != 200:
                continue

            file_info = cls._select_archive_audio_file(metadata_response.json().get("files") or [])
            if not file_info:
                continue

            file_name = file_info.get("name")
            if not file_name:
                continue

            title = item.get("title") or identifier
            creator = item.get("creator") or "internet_archive"
            if isinstance(creator, list):
                creator = creator[0] if creator else "internet_archive"
            label = f"{creator}_{title}"
            download_url = f"{download_base}/{quote(identifier, safe='')}/{quote(file_name)}"
            cls._log(logger, f"🎵 选中 Internet Archive 曲目: {creator} - {title} ({license_url})")
            path = cls.download_audio_url(download_url, output_dir, label=label, logger=logger)
            if path:
                return path

        cls._log(logger, "⚠️ Internet Archive 没有返回可下载授权音频", warning=True)
        return None

    @classmethod
    def _select_archive_audio_file(cls, files: list[dict[str, Any]]) -> dict[str, Any] | None:
        preferred = []
        fallback = []
        for file_info in files:
            name = file_info.get("name") or ""
            ext = Path(name).suffix.lower()
            if ext not in cls.AUDIO_EXTENSIONS:
                continue
            fmt = str(file_info.get("format") or "").lower()
            if "128kbps" in fmt or ext == ".mp3":
                preferred.append(file_info)
            else:
                fallback.append(file_info)
        return (preferred or fallback or [None])[0]

    @staticmethod
    def _is_approved_license_url(value: str) -> bool:
        value = str(value or "").lower()
        return "creativecommons.org" in value or "publicdomain" in value

    @staticmethod
    def _jamendo_download_url(item: dict[str, Any]) -> str | None:
        if item.get("audiodownload_allowed") is False:
            return None
        return (
            item.get("audiodownload")
            or item.get("audio")
            or item.get("prourl")
            or item.get("shareurl")
        )

    @classmethod
    def download_audio_url(cls, url: str, output_dir: Path, label: str = "music", logger=None) -> str | None:
        if not cls._is_http_url(url):
            cls._log(logger, "⚠️ 只支持 http(s) 音频 URL", warning=True)
            return None

        timeout = float(os.getenv("ONLINE_MUSIC_REQUEST_TIMEOUT") or "60")
        max_mb = float(os.getenv("ONLINE_MUSIC_MAX_MB") or "80")
        max_bytes = int(max_mb * 1024 * 1024)
        headers = {"User-Agent": "capsule-cinema/2.0"}

        try:
            with requests.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=True) as response:
                if response.status_code != 200:
                    cls._log(logger, f"⚠️ 在线音乐下载失败: HTTP {response.status_code}", warning=True)
                    return None

                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                content_length = int(response.headers.get("content-length") or "0")
                ext = cls._extension_for_url(url, content_type)
                if content_type and content_type not in cls.AUDIO_CONTENT_TYPES and ext not in cls.AUDIO_EXTENSIONS:
                    cls._log(logger, f"⚠️ 在线音乐不是可识别音频类型: {content_type}", warning=True)
                    return None
                if content_length and content_length > max_bytes:
                    cls._log(logger, f"⚠️ 在线音乐过大: {content_length / 1024 / 1024:.1f}MB", warning=True)
                    return None

                safe_label = cls._safe_filename(label)
                digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
                output_path = output_dir / f"{safe_label}_{digest}{ext}"
                total = 0
                with output_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > max_bytes:
                            output_path.unlink(missing_ok=True)
                            cls._log(logger, f"⚠️ 在线音乐超过大小限制: {max_mb:.0f}MB", warning=True)
                            return None
                        handle.write(chunk)

            if output_path.exists() and output_path.stat().st_size > 0:
                cls._log(logger, f"✅ 在线音乐已下载: {output_path}")
                return str(output_path)
        except Exception as exc:
            cls._log(logger, f"⚠️ 在线音乐下载异常: {exc}", warning=True)

        return None

    @staticmethod
    def _first_non_empty(mapping: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = mapping.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _is_http_url(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @classmethod
    def _extension_for_url(cls, url: str, content_type: str) -> str:
        path = unquote(urlparse(url).path)
        ext = Path(path).suffix.lower()
        if ext in cls.AUDIO_EXTENSIONS:
            return ext

        query = parse_qs(urlparse(url).query)
        for value in query.get("filename", []) + query.get("file", []):
            candidate = Path(unquote(value)).suffix.lower()
            if candidate in cls.AUDIO_EXTENSIONS:
                return candidate

        guessed = mimetypes.guess_extension(content_type or "")
        if guessed == ".oga":
            return ".ogg"
        if guessed in cls.AUDIO_EXTENSIONS:
            return guessed
        return ".mp3"

    @staticmethod
    def _safe_filename(value: str) -> str:
        value = re.sub(r"\s+", "_", str(value or "music").strip())
        value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
        return value.strip("._-")[:80] or "music"

    @staticmethod
    def _safe_url_for_log(url: str) -> str:
        parsed = urlparse(url)
        return parsed._replace(query="", fragment="").geturl()

    @staticmethod
    def _log(logger, message: str, warning: bool = False) -> None:
        if logger is None:
            return
        if warning:
            logger.warning(message)
        else:
            logger.info(message)
