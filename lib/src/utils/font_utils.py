"""Cross-platform font discovery for Pillow and FFmpeg renderers.

Resolution order:
1. Explicit environment overrides.
2. Fonts packaged in the repository's resource directories.
3. Known macOS, Windows, and Linux system font locations.
4. Fontconfig (when ``fc-match`` is available).

Chinese renderers fail with an actionable error when no CJK font is available.
Silently falling back to Pillow's bitmap font would render Chinese as tofu boxes.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from src.logger import get_logger

logger = get_logger("font_utils")

_LIB_DIR = Path(__file__).resolve().parents[2]
_RESOURCE_DIR = Path(os.getenv("VIDEO_RESOURCES_PATH", str(_LIB_DIR / "video_resources")))
_FONT_EXTENSIONS = {".otf", ".ttf", ".ttc"}

# A small set spanning common radicals/strokes is more reliable than probing only “中”.
_GLYPH_PROBES = ("中", "国", "枸", "杞", "茶", "养")

_REGULAR_CJK_FILENAMES = (
    "NotoSansSC-Regular.otf",
    "NotoSansCJK-Regular.ttc",
    "SourceHanSansSC-Regular.otf",
    "SourceHanSansCN-Regular.otf",
    "QingNiaoHuaGuangJianMeiHei-2.ttf",
    "STHeiti-Medium.ttc",
    "msyh.ttc",
    "simhei.ttf",
    "simsun.ttc",
    "Deng.ttf",
    "wqy-microhei.ttc",
    "wqy-zenhei.ttc",
)
_BOLD_CJK_FILENAMES = (
    "NotoSansSC-Bold.otf",
    "NotoSansCJK-Bold.ttc",
    "SourceHanSansSC-Bold.otf",
    "SourceHanSansCN-Bold.otf",
    "STHeiti-Medium.ttc",
    "msyhbd.ttc",
    "simhei.ttf",
    "Dengb.ttf",
    "wqy-zenhei.ttc",
)
_REGULAR_LATIN_FILENAMES = (
    "Arial.ttf",
    "arial.ttf",
    "Helvetica.ttc",
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
)
_BOLD_LATIN_FILENAMES = (
    "Arial Bold.ttf",
    "arialbd.ttf",
    "Helvetica.ttc",
    "DejaVuSans-Bold.ttf",
    "LiberationSans-Bold.ttf",
)

_FONTCONFIG_CJK_REGULAR = (
    "Noto Sans CJK SC:lang=zh-cn:style=Regular",
    "Noto Sans SC:lang=zh-cn:style=Regular",
    "Source Han Sans SC:lang=zh-cn:style=Regular",
    "Microsoft YaHei:lang=zh-cn:style=Regular",
    "WenQuanYi Zen Hei:lang=zh-cn",
    ":lang=zh-cn",
)
_FONTCONFIG_CJK_BOLD = (
    "Noto Sans CJK SC:lang=zh-cn:style=Bold",
    "Noto Sans SC:lang=zh-cn:style=Bold",
    "Source Han Sans SC:lang=zh-cn:style=Bold",
    "Microsoft YaHei:lang=zh-cn:style=Bold",
    "WenQuanYi Zen Hei:lang=zh-cn:style=Bold",
    ":lang=zh-cn:style=Bold",
)
_FONTCONFIG_LATIN_REGULAR = ("Arial:style=Regular", "Helvetica:style=Regular", "sans-serif:style=Regular")
_FONTCONFIG_LATIN_BOLD = ("Arial:style=Bold", "Helvetica:style=Bold", "sans-serif:style=Bold")

_validity_cache: dict[str, bool] = {}
_fonttools_warned = False


def _has_chinese_glyphs(font_path: str) -> bool:
    """Return whether a font file contains the probe CJK glyphs; cache the result."""
    normalized = str(Path(font_path).expanduser())
    if normalized in _validity_cache:
        return _validity_cache[normalized]

    global _fonttools_warned
    try:
        from fontTools.ttLib import TTCollection, TTFont
    except ImportError:
        if not _fonttools_warned:
            logger.warning(
                "fontTools is not installed; trusting known CJK font candidates without glyph validation. "
                "Install it with `pip install fonttools` for strict validation."
            )
            _fonttools_warned = True
        _validity_cache[normalized] = True
        return True

    fonts = []
    try:
        if normalized.casefold().endswith(".ttc"):
            fonts = list(TTCollection(normalized).fonts)
        else:
            fonts = [TTFont(normalized)]
        for font in fonts:
            cmap = font.getBestCmap() or {}
            if all(ord(character) in cmap for character in _GLYPH_PROBES):
                _validity_cache[normalized] = True
                return True
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Font glyph validation failed for {normalized}: {exc}")
    finally:
        for font in fonts:
            try:
                font.close()
            except Exception:  # noqa: BLE001
                pass

    _validity_cache[normalized] = False
    return False


def _iter_unique_existing(paths: Iterable[str | Path]) -> Iterable[str]:
    seen: set[str] = set()
    for raw_path in paths:
        if not raw_path:
            continue
        path = Path(raw_path).expanduser()
        try:
            normalized = str(path.resolve())
        except OSError:
            normalized = str(path)
        key = os.path.normcase(normalized)
        if key in seen:
            continue
        seen.add(key)
        if path.is_file() and path.suffix.casefold() in _FONT_EXTENSIONS:
            yield normalized


def _project_font_dirs() -> tuple[Path, ...]:
    return (_RESOURCE_DIR / "fonts", _LIB_DIR / "config" / "fonts")


def _system_font_dirs(
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> tuple[Path, ...]:
    """Return font roots without assuming Windows is installed on ``C:``."""
    detected = (system or platform.system()).casefold()
    env = os.environ if environ is None else environ
    user_home = home or Path.home()

    if detected == "windows":
        windows_root = Path(env.get("WINDIR") or env.get("SystemRoot") or "C:/Windows")
        roots = [windows_root / "Fonts"]
        local_app_data = env.get("LOCALAPPDATA")
        if local_app_data:
            roots.append(Path(local_app_data) / "Microsoft" / "Windows" / "Fonts")
        return tuple(roots)
    if detected == "darwin":
        return (
            Path("/System/Library/Fonts"),
            Path("/System/Library/Fonts/Supplemental"),
            Path("/Library/Fonts"),
            user_home / "Library" / "Fonts",
        )
    return (
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        user_home / ".local" / "share" / "fonts",
        user_home / ".fonts",
    )


def _environment_candidates(*, bold: bool) -> tuple[str, ...]:
    role_name = "VIDEO_FONT_BOLD_PATH" if bold else "VIDEO_FONT_REGULAR_PATH"
    return (os.getenv(role_name, ""), os.getenv("VIDEO_DEFAULT_FONT_PATH", ""))


def _filenames(*, bold: bool, require_cjk: bool) -> tuple[str, ...]:
    if require_cjk:
        return _BOLD_CJK_FILENAMES if bold else _REGULAR_CJK_FILENAMES
    return _BOLD_LATIN_FILENAMES if bold else _REGULAR_LATIN_FILENAMES


def _packaged_font_candidates(*, bold: bool, require_cjk: bool) -> Iterable[Path]:
    filenames = _filenames(bold=bold, require_cjk=require_cjk)
    if bold:
        filenames = (*filenames, *_filenames(bold=False, require_cjk=require_cjk))
    for root in _project_font_dirs():
        for filename in filenames:
            yield root / filename


def _system_path_candidates(*, bold: bool, require_cjk: bool) -> Iterable[Path]:
    filenames = _filenames(bold=bold, require_cjk=require_cjk)
    if bold:
        # A regular CJK font is a better final fallback than missing glyphs.
        filenames = (*filenames, *_filenames(bold=False, require_cjk=require_cjk))
    for root in _system_font_dirs():
        for filename in filenames:
            yield root / filename

    # Fonts whose installed filename/location is platform-specific or contains spaces.
    if require_cjk:
        if bold:
            yield Path("/System/Library/Fonts/STHeiti Medium.ttc")
            yield Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
            yield Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
        else:
            yield Path("/System/Library/Fonts/Hiragino Sans GB.ttc")
            yield Path("/System/Library/Fonts/STHeiti Light.ttc")
            yield Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
            yield Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc")
            yield Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
        yield Path("/System/Library/Fonts/PingFang.ttc")
        yield Path("/System/Library/Fonts/Supplemental/Songti.ttc")
    elif bold:
        yield Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
    else:
        yield Path("/System/Library/Fonts/Supplemental/Arial.ttf")
        yield Path("/System/Library/Fonts/Helvetica.ttc")


def _fontconfig_queries(*, bold: bool, require_cjk: bool) -> Sequence[str]:
    if require_cjk:
        return _FONTCONFIG_CJK_BOLD if bold else _FONTCONFIG_CJK_REGULAR
    return _FONTCONFIG_LATIN_BOLD if bold else _FONTCONFIG_LATIN_REGULAR


@lru_cache(maxsize=4)
def _fontconfig_candidates(bold: bool, require_cjk: bool) -> tuple[str, ...]:
    executable = shutil.which("fc-match")
    if not executable:
        return ()
    found: list[str] = []
    for query in _fontconfig_queries(bold=bold, require_cjk=require_cjk):
        try:
            result = subprocess.run(
                [executable, "-f", "%{file}\n", query],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            found.extend(line.strip() for line in result.stdout.splitlines() if line.strip())
    return tuple(found)


def resolve_font_path(
    *,
    bold: bool = False,
    require_cjk: bool = True,
    preferred_paths: Iterable[str | Path] = (),
    verify_glyphs: bool = True,
) -> str:
    """Resolve a usable font path on macOS, Windows, or Linux.

    ``preferred_paths`` lets a caller preserve a CLI/profile override without
    duplicating platform-specific fallback lists.
    """
    def candidates() -> Iterable[str | Path]:
        yield from preferred_paths
        yield from _environment_candidates(bold=bold)
        yield from _packaged_font_candidates(bold=bold, require_cjk=require_cjk)
        yield from _system_path_candidates(bold=bold, require_cjk=require_cjk)
        # Keep subprocess-based discovery lazy: an explicit, packaged, or known
        # system font should not pay for multiple fc-match processes.
        yield from _fontconfig_candidates(bold, require_cjk)

    for candidate in _iter_unique_existing(candidates()):
        if not require_cjk or not verify_glyphs or _has_chinese_glyphs(candidate):
            logger.info(f"🔤 Using font: {candidate}")
            return candidate
        logger.warning(f"Font exists but lacks required Chinese glyphs, skipping: {candidate}")

    role = "bold" if bold else "regular"
    raise FileNotFoundError(
        f"No usable {role} {'CJK ' if require_cjk else ''}font was found. "
        f"Set {'VIDEO_FONT_BOLD_PATH' if bold else 'VIDEO_FONT_REGULAR_PATH'} or "
        "VIDEO_DEFAULT_FONT_PATH to a .ttf/.ttc/.otf file. On Linux, install "
        "Noto Sans CJK (for example `apt install fonts-noto-cjk`)."
    )


def load_pil_font(
    size: int,
    *,
    bold: bool = False,
    require_cjk: bool = True,
    preferred_paths: Iterable[str | Path] = (),
):
    """Resolve and load a Pillow FreeType font without a tofu-prone fallback."""
    from PIL import ImageFont

    path = resolve_font_path(
        bold=bold,
        require_cjk=require_cjk,
        preferred_paths=preferred_paths,
    )
    return ImageFont.truetype(path, size=size, index=0)


def escape_font_path_for_ffmpeg(font_path: str | Path) -> str:
    """Escape a font path for FFmpeg's single-quoted ``drawtext`` syntax.

    Windows drive-letter colons are filter-option separators unless escaped,
    and native backslashes are easier to handle after normalizing to slashes.
    The returned value is intended for a command passed as a subprocess list;
    no shell-escaping layer is included.
    """
    normalized = str(font_path).replace("\\", "/")
    return normalized.replace("'", "\\'").replace(":", "\\:")


def ffmpeg_fontfile_option(font_path: str | Path | None) -> str:
    """Build a portable optional ``drawtext`` fontfile fragment."""
    if not font_path:
        return ""
    return f":fontfile='{escape_font_path_for_ffmpeg(font_path)}'"


def get_default_font(verify_glyphs: bool = True) -> str:
    """Backward-compatible regular CJK font resolver."""
    return resolve_font_path(verify_glyphs=verify_glyphs)


def _safe_default_font() -> str:
    """Avoid failing imports; consumers that require text still fail when loading it."""
    try:
        return get_default_font()
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return ""


DEFAULT_FONT_PATH = _safe_default_font()


def get_font_path(font_name: str = "QingNiaoHuaGuangJianMeiHei-2.ttf") -> str:
    """Find a packaged font by filename, falling back to system discovery."""
    preferred = tuple(directory / font_name for directory in _project_font_dirs())
    return resolve_font_path(preferred_paths=preferred)
