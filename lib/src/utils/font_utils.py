"""字体工具：返回有效的中文字体路径。

历史问题：候选字体全都不存在时直接返回空串，ffmpeg 烧字幕会退化到默认拉丁字体，
中文字符画成豆腐方框。

新策略：
1. 维护一组候选路径（环境变量 → 项目内 → macOS 系统中文字体）。
2. 不仅检查"文件存在"，还做"glyph 有效性校验"——用 fontTools 看字体里是否真的
   含有典型中文字符；以避免找到一个只含 ASCII 的字体当中文字幕用。
3. 找不到任何有效中文字体时抛出明确异常，而不是静默返回空串。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional

from src.logger import get_logger

logger = get_logger("font_utils")

_LIB_DIR = Path(__file__).resolve().parents[2]
_RESOURCE_DIR = Path(os.getenv("VIDEO_RESOURCES_PATH", str(_LIB_DIR / "video_resources")))
_ENV_DEFAULT_FONT_PATH = os.getenv("VIDEO_DEFAULT_FONT_PATH", "")

_FONT_CANDIDATES = [
    _ENV_DEFAULT_FONT_PATH,
    str(_RESOURCE_DIR / "fonts" / "QingNiaoHuaGuangJianMeiHei-2.ttf"),
    str(_RESOURCE_DIR / "fonts" / "STHeiti-Medium.ttc"),
    str(_RESOURCE_DIR / "fonts" / "NotoSansSC-Regular.otf"),
    str(_LIB_DIR / "config" / "fonts" / "NotoSansSC-Regular.otf"),
    # macOS 系统兜底（绝大多数 Mac 都有）
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    # Linux 常见
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]

# 用一组涵盖常用部首/笔画的汉字做 glyph 校验，比单字"中"更可靠
_GLYPH_PROBES = ("中", "国", "枸", "杞", "茶", "养")

_validity_cache: dict[str, bool] = {}


def _has_chinese_glyphs(font_path: str) -> bool:
    """检查字体是否含有典型中文字符的 glyph。结果缓存。"""
    if font_path in _validity_cache:
        return _validity_cache[font_path]

    try:
        from fontTools.ttLib import TTFont, TTCollection

        path_lower = font_path.lower()
        if path_lower.endswith(".ttc"):
            collection = TTCollection(font_path)
            fonts = list(collection.fonts)
        else:
            fonts = [TTFont(font_path)]

        for font in fonts:
            try:
                cmap = font.getBestCmap() or {}
            except Exception:
                continue
            if all(ord(c) in cmap for c in _GLYPH_PROBES):
                _validity_cache[font_path] = True
                return True

        _validity_cache[font_path] = False
        return False
    except Exception as exc:  # noqa: BLE001
        # fontTools 缺失或文件损坏；保守起见判定为不可用
        logger.debug(f"字体 glyph 校验失败 {font_path}: {exc}")
        _validity_cache[font_path] = False
        return False


def _iter_existing(paths: Iterable[str]) -> Iterable[str]:
    seen: set[str] = set()
    for p in paths:
        if not p or p in seen:
            continue
        seen.add(p)
        if Path(p).exists():
            yield p


def get_default_font(verify_glyphs: bool = True) -> str:
    """返回首个存在且（可选）glyph 校验通过的中文字体路径。"""
    for candidate in _iter_existing(_FONT_CANDIDATES):
        if not verify_glyphs or _has_chinese_glyphs(candidate):
            logger.info(f"🔤 使用字体: {candidate}")
            return candidate
        logger.warning(f"⚠️ 字体存在但缺少中文 glyph，跳过: {candidate}")

    raise FileNotFoundError(
        "找不到可用的中文字体。请设置环境变量 VIDEO_DEFAULT_FONT_PATH 指向一个含"
        "中文 glyph 的 .ttf/.ttc，或把字体放到 video_resources/fonts/ 下。"
    )


def _safe_default_font() -> str:
    """模块加载阶段调用——失败时返回空串，由调用方在用时再触发硬错误。"""
    try:
        return get_default_font()
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return ""


DEFAULT_FONT_PATH = _safe_default_font()


def get_font_path(font_name: str = "QingNiaoHuaGuangJianMeiHei-2.ttf") -> str:
    """按文件名在已知字体目录里找一个，找不到退到默认中文字体。"""
    for base_dir in (_RESOURCE_DIR / "fonts", _LIB_DIR / "config" / "fonts"):
        font_path = base_dir / font_name
        if font_path.exists() and _has_chinese_glyphs(str(font_path)):
            return str(font_path)
    return DEFAULT_FONT_PATH
