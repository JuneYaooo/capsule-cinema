"""Pydantic contracts for storyboard and continuity artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]


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
    raw_scenes = data.get("storyboard") or data.get("scenes") or []
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
