"""Pydantic contracts for storyboard and continuity artifacts."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

try:
    from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
except ModuleNotFoundError:
    def ConfigDict(**kwargs: Any) -> dict[str, Any]:
        return dict(kwargs)

    def Field(default: Any = None, *, default_factory: Any = None, **_: Any) -> Any:
        if default_factory is not None:
            return default_factory()
        return default

    def field_validator(*_: Any, **__: Any) -> Any:
        def decorator(func: Any) -> Any:
            return func
        return decorator

    def model_validator(*_: Any, **__: Any) -> Any:
        def decorator(func: Any) -> Any:
            return func
        return decorator

    class BaseModel:
        def __init__(self, **kwargs: Any) -> None:
            for key, value in getattr(self, "__annotations__", {}).items():
                if key in kwargs:
                    setattr(self, key, kwargs[key])
                elif hasattr(type(self), key):
                    setattr(self, key, deepcopy(getattr(type(self), key)))
                else:
                    setattr(self, key, None)
            for key, value in kwargs.items():
                if not hasattr(self, key):
                    setattr(self, key, value)

        @classmethod
        def model_validate(cls, data: dict[str, Any]) -> Any:
            return cls(**data)

        def model_dump(self, **_: Any) -> dict[str, Any]:
            def convert(value: Any) -> Any:
                if hasattr(value, "model_dump"):
                    return value.model_dump()
                if isinstance(value, list):
                    return [convert(item) for item in value]
                if isinstance(value, dict):
                    return {key: convert(item) for key, item in value.items()}
                return value

            return {
                key: convert(getattr(self, key))
                for key in getattr(self, "__annotations__", {})
            }


def _clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]


def _to_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_storyboard_scenes(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return canonical storyboard scenes without mutating the source."""
    storyboard = data.get("storyboard")
    if isinstance(storyboard, list):
        return storyboard
    return []


def set_storyboard_scenes(data: dict[str, Any], scenes: list[dict[str, Any]]) -> None:
    """Write scenes to the canonical storyboard field."""
    data["storyboard"] = scenes


def scene_order(scene: dict[str, Any], fallback: int) -> int:
    """Stable sort key for canonical index documents."""
    if "index" in scene:
        return _to_int(scene.get("index"), fallback) or fallback
    return fallback


def scene_display_id(scene: dict[str, Any], fallback: int) -> int:
    """User-facing 1-based scene id."""
    if "index" in scene:
        return _to_int(scene.get("index"), fallback) or fallback
    return fallback


def scene_id_candidates(scene: dict[str, Any], fallback: int) -> set[int]:
    """All ids that may refer to a scene in the canonical schema."""
    index = _to_int(scene.get("index"))
    if index is not None:
        return {index}
    return set()


def scene_matches_id(scene: dict[str, Any], requested_id: int, fallback: int) -> bool:
    return requested_id in scene_id_candidates(scene, fallback)


def find_scene_by_id(
    scenes: list[dict[str, Any]],
    requested_id: int,
) -> tuple[int | None, dict[str, Any] | None]:
    for idx, scene in enumerate(scenes, start=1):
        if scene_matches_id(scene, requested_id, idx):
            return idx - 1, scene
    return None, None


def _first_non_empty(scene: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = scene.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def get_scene_prompt(scene: dict[str, Any], kind: str) -> str:
    if kind == "image":
        return _first_non_empty(
            scene,
            ["image_prompt", "image_prompt_chinese", "image_prompt_english"],
        )
    if kind == "video":
        return _first_non_empty(
            scene,
            ["video_prompt", "video_prompt_chinese", "video_prompt_english"],
        )
    raise ValueError(f"unsupported prompt kind: {kind}")


class CharacterContract(BaseModel):
    model_config = ConfigDict(extra="allow")

    character_id: str
    character_name: str = ""
    character_description: str = ""
    identity_anchor: str = ""
    fixed_traits: list[str] = Field(default_factory=list)
    allowed_variations: list[str] = Field(default_factory=list)

    @field_validator("fixed_traits", "allowed_variations", mode="before")
    @classmethod
    def normalize_list(cls, value: Any) -> list[str]:
        return _clean_list(value)


class StyleContract(BaseModel):
    model_config = ConfigDict(extra="allow")

    style_anchor_id: str = "main_style"
    style_name: str = ""
    style_description: str = ""
    fixed_style_traits: list[str] = Field(default_factory=list)
    allowed_style_variations: list[str] = Field(default_factory=list)

    @field_validator("fixed_style_traits", "allowed_style_variations", mode="before")
    @classmethod
    def normalize_list(cls, value: Any) -> list[str]:
        return _clean_list(value)


class SceneContract(BaseModel):
    model_config = ConfigDict(extra="allow")

    scene_id: int = 0
    description: str = ""
    duration: float = 5.0
    video_generation_type: str = "image_to_video"
    chapter_id: str = "chapter_01"
    continuity_group: str = ""
    character_ids: list[str] = Field(default_factory=list)
    style_anchor: str = "main_style"
    continuity_notes: str = ""
    needs_reference: bool = False
    reference_type: str = "none"
    reference_ids: list[str] = Field(default_factory=list)
    use_style_reference: bool = True
    image_prompt_chinese: str = ""
    image_prompt_english: str = ""
    video_prompt_chinese: str = ""
    video_prompt_english: str = ""

    @field_validator("character_ids", "reference_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: Any) -> list[str]:
        return _clean_list(value)

    @model_validator(mode="after")
    def fill_continuity_defaults(self) -> "SceneContract":
        if not self.continuity_group:
            self.continuity_group = f"scene_{self.scene_id:02d}"
        if self.character_ids and not self.reference_ids:
            self.reference_ids = list(self.character_ids)
        if self.reference_ids and self.reference_type == "none":
            self.reference_type = "character"
        if self.reference_ids:
            self.needs_reference = True
        return self


class ConsistencyContract(BaseModel):
    model_config = ConfigDict(extra="allow")

    long_chain_ready: bool = True
    style_anchor_id: str = "main_style"
    fixed_style_traits: list[str] = Field(default_factory=list)
    allowed_style_variations: list[str] = Field(default_factory=list)
    characters: list[CharacterContract] = Field(default_factory=list)
    continuity_groups: list[str] = Field(default_factory=list)
    chapters: list[str] = Field(default_factory=list)

    @field_validator("fixed_style_traits", "allowed_style_variations", "continuity_groups", "chapters", mode="before")
    @classmethod
    def normalize_list(cls, value: Any) -> list[str]:
        return _clean_list(value)


class StoryboardDocument(BaseModel):
    model_config = ConfigDict(extra="allow")

    reference_design: dict[str, Any] = Field(default_factory=dict)
    consistency_contract: ConsistencyContract = Field(default_factory=ConsistencyContract)
    storyboard: list[SceneContract] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


def _style_from_reference(reference_design: dict[str, Any]) -> StyleContract:
    style_data = reference_design.get("style_reference") or {}
    if not isinstance(style_data, dict):
        style_data = {}
    return StyleContract.model_validate(style_data)


def _characters_from_reference(reference_design: dict[str, Any]) -> list[CharacterContract]:
    characters = reference_design.get("characters") or []
    if not isinstance(characters, list):
        return []
    normalized: list[CharacterContract] = []
    for index, item in enumerate(characters, start=1):
        if not isinstance(item, dict):
            continue
        data = dict(item)
        data.setdefault("character_id", data.get("id") or f"char_{index:03d}")
        data.setdefault("character_name", data.get("name", ""))
        data.setdefault("character_description", data.get("description", ""))
        normalized.append(CharacterContract.model_validate(data))
    return normalized


def build_consistency_contract(reference_design: dict[str, Any], scenes: list[SceneContract]) -> ConsistencyContract:
    style = _style_from_reference(reference_design)
    characters = _characters_from_reference(reference_design)
    return ConsistencyContract(
        long_chain_ready=True,
        style_anchor_id=style.style_anchor_id,
        fixed_style_traits=style.fixed_style_traits,
        allowed_style_variations=style.allowed_style_variations,
        characters=characters,
        continuity_groups=sorted({scene.continuity_group for scene in scenes if scene.continuity_group}),
        chapters=sorted({scene.chapter_id for scene in scenes if scene.chapter_id}),
    )


def normalize_storyboard_document(data: dict[str, Any]) -> StoryboardDocument:
    reference_design = data.get("reference_design") or {}
    raw_scenes = get_storyboard_scenes(data)
    scenes: list[SceneContract] = []
    if isinstance(raw_scenes, list):
        for index, raw_scene in enumerate(raw_scenes):
            if not isinstance(raw_scene, dict):
                continue
            scene_data = dict(raw_scene)
            scene_data.setdefault("scene_id", scene_data.get("index", index))
            scene_data.setdefault("chapter_id", "chapter_01")
            scene_data.setdefault("style_anchor", "main_style")
            scenes.append(SceneContract.model_validate(scene_data))

    consistency_contract = data.get("consistency_contract")
    if isinstance(consistency_contract, dict):
        contract = ConsistencyContract.model_validate(consistency_contract)
        if not contract.continuity_groups or not contract.chapters:
            rebuilt = build_consistency_contract(reference_design, scenes)
            contract.continuity_groups = contract.continuity_groups or rebuilt.continuity_groups
            contract.chapters = contract.chapters or rebuilt.chapters
            contract.characters = contract.characters or rebuilt.characters
            contract.fixed_style_traits = contract.fixed_style_traits or rebuilt.fixed_style_traits
            contract.allowed_style_variations = contract.allowed_style_variations or rebuilt.allowed_style_variations
    else:
        contract = build_consistency_contract(reference_design, scenes)

    return StoryboardDocument(
        reference_design=reference_design,
        consistency_contract=contract,
        storyboard=scenes,
        created_at=str(data.get("created_at") or datetime.now().isoformat()),
    )
