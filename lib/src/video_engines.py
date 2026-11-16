"""Video engine catalog: the single source of truth for engine names and limits.

``lib/config/video_engines.yaml`` (plus an optional ``local-channels/video_engines.yaml``
overlay) describes every runtime video engine: canonical key, accepted aliases,
default model, model-override env vars, and the provider limits a request must
respect. Tools, the unified video entry point, and capsule runtimes read the
catalog instead of keeping their own engine lists or hard-coded numbers.

Tool class ↔ engine binding lives in ``tool_registry.yaml`` (``runtime_engine``);
:func:`runtime_engine_for_tool` resolves it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional

from src.config_registry import load_registry, load_tool_registry


CATALOG_FILE = "video_engines.yaml"


@dataclass(frozen=True)
class VideoEngineSpec:
    key: str
    name: str = ""
    provider: str = ""
    default_model: str = ""
    model_env: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    prompt_language: str = "zh"
    capabilities: dict[str, Any] = field(default_factory=dict)
    features: dict[str, Any] = field(default_factory=dict)

    # -- capability accessors -------------------------------------------------
    def cap(self, name: str, default: Any = None) -> Any:
        return self.capabilities.get(name, default)

    @property
    def duration_range(self) -> tuple[int, int]:
        low, high = self.cap("duration_range", [4, 15])
        return int(low), int(high)

    @property
    def automatic_duration(self) -> Optional[int]:
        value = self.cap("automatic_duration")
        return None if value is None else int(value)

    @property
    def default_max_wait_seconds(self) -> int:
        return int(self.cap("default_max_wait_seconds", 900))

    def max_references(self, kind: str) -> int:
        return int(self.cap(f"max_reference_{kind}s", 0))

    def resolve_model(self) -> str:
        for env_name in self.model_env:
            value = os.getenv(env_name, "").strip()
            if value:
                return value
        return self.default_model

    def validate_duration(self, value: int | float | str) -> int:
        text = str(value).strip().lower()
        if text.endswith("s"):
            text = text[:-1]
        numeric = float(text)
        if not numeric.is_integer():
            raise ValueError(f"{self.key} duration must use whole seconds")
        result = int(numeric)
        if self.automatic_duration is not None and result == self.automatic_duration:
            return result
        low, high = self.duration_range
        if not low <= result <= high:
            auto = f", or {self.automatic_duration}" if self.automatic_duration is not None else ""
            raise ValueError(f"{self.key} duration must be an integer from {low} to {high}{auto}")
        return result


def _spec_from_record(key: str, record: dict[str, Any]) -> VideoEngineSpec:
    return VideoEngineSpec(
        key=key,
        name=str(record.get("name") or key),
        provider=str(record.get("provider") or ""),
        default_model=str(record.get("default_model") or ""),
        model_env=tuple(record.get("model_env") or ()),
        aliases=tuple(str(alias) for alias in record.get("aliases") or ()),
        prompt_language=str(record.get("prompt_language") or "zh"),
        capabilities=dict(record.get("capabilities") or {}),
        features=dict(record.get("features") or {}),
    )


@lru_cache(maxsize=1)
def _catalog() -> dict[str, VideoEngineSpec]:
    records = load_registry(CATALOG_FILE, "engines")
    return {key: _spec_from_record(key, record or {}) for key, record in records.items()}


@lru_cache(maxsize=1)
def _alias_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for spec in _catalog().values():
        for name in (spec.key, *spec.aliases):
            index[name.strip().lower()] = spec.key
    return index


def reload_catalog() -> None:
    """Drop cached catalog data (tests and long-running processes)."""
    _catalog.cache_clear()
    _alias_index.cache_clear()


def normalize_engine_name(engine: str) -> str:
    """Map any accepted spelling (``seedance-2.5``, ``MiniMax-H3``…) to its canonical key.

    Unknown names are returned stripped but otherwise unchanged so that local-overlay
    runtime engines registered only in ``tool_registry.yaml`` keep working.
    """
    value = (engine or "").strip()
    return _alias_index().get(value.lower(), value)


def get_engine_spec(engine: str) -> Optional[VideoEngineSpec]:
    return _catalog().get(normalize_engine_name(engine))


def require_engine_spec(engine: str) -> VideoEngineSpec:
    spec = get_engine_spec(engine)
    if spec is None:
        raise ValueError(f"Video engine {engine!r} is not described in {CATALOG_FILE}")
    return spec


def catalog_engine_keys() -> list[str]:
    return list(_catalog())


def default_engine() -> str:
    rules = _selection_rules()
    return normalize_engine_name(str(rules.get("default") or "seedance2.0"))


def _selection_rules() -> dict[str, Any]:
    from src.config_registry import PUBLIC_CONFIG_DIR, _read

    return dict((_read(PUBLIC_CONFIG_DIR / CATALOG_FILE).get("selection_rules")) or {})


def runtime_engine_for_tool(tool_name: str) -> str:
    """Return the runtime engine bound to a tool class in ``tool_registry.yaml``.

    Returns ``""`` when the class is not a registered video tool.
    """
    record = load_tool_registry().get(str(tool_name or "").strip()) or {}
    runtime_engine = str(record.get("runtime_engine") or "").strip()
    return normalize_engine_name(runtime_engine) if runtime_engine else ""


def registered_video_engines(*, include_inactive: bool = False) -> dict[str, str]:
    """Return ``{runtime_engine: tool_class}`` for registered video-generation tools.

    The first registration of an engine wins, so public tools take precedence over
    later local-overlay records that reuse the same engine key.
    """
    engines: dict[str, str] = {}
    for class_name, record in load_tool_registry().items():
        if not isinstance(record, dict) or record.get("category") != "video_generation":
            continue
        status = str(record.get("status") or "").strip().lower()
        if not include_inactive and status in {"disabled", "suspended"}:
            continue
        runtime_engine = str(record.get("runtime_engine") or "").strip()
        if runtime_engine:
            engines.setdefault(normalize_engine_name(runtime_engine), class_name)
    return engines


__all__ = [
    "VideoEngineSpec",
    "catalog_engine_keys",
    "default_engine",
    "get_engine_spec",
    "normalize_engine_name",
    "registered_video_engines",
    "reload_catalog",
    "require_engine_spec",
    "runtime_engine_for_tool",
]
