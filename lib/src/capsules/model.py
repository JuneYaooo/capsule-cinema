from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class CapsuleMetadata(BaseModel):
    name: str
    display_name: str
    version: str
    status: str
    source_schema: str
    source_path: str

    @field_validator("name", "display_name", "version", "source_schema", "source_path")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()


class CapsulePromise(BaseModel):
    summary: str


class CapsuleMatch(BaseModel):
    category: str = ""
    workflow: str = ""
    capabilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    when_to_use: list[str] = Field(default_factory=list)
    when_not_to_use: list[str] = Field(default_factory=list)


class CapsuleInput(BaseModel):
    type: str
    required: bool = False
    description: str = ""
    default: Any = None
    options: list[Any] = Field(default_factory=list)
    minimum: int | float | None = None
    maximum: int | float | None = None

    @field_validator("minimum", "maximum", mode="before")
    @classmethod
    def require_strict_finite_bound(cls, value: Any) -> int | float | None:
        if value is None or type(value) is int:
            return value
        if type(value) is float and math.isfinite(value):
            return value
        raise ValueError("numeric bounds must be strict finite int or float values")

    @model_validator(mode="after")
    def require_ordered_bounds(self) -> CapsuleInput:
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("minimum must not exceed maximum")
        return self


class CapsuleInterface(BaseModel):
    inputs: dict[str, CapsuleInput] = Field(default_factory=dict)


class CapsuleReadOrder(BaseModel):
    routing: list[str] = Field(default_factory=list)
    planning: list[str] = Field(default_factory=list)
    generation: list[str] = Field(default_factory=list)
    qa: list[str] = Field(default_factory=list)
    learning: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @field_validator("routing", "planning", "generation", "qa", "learning")
    @classmethod
    def require_ordered_unique_resources(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("read_order resources must not be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("read_order resources must be unique within a stage")
        return normalized


class CapsuleRunner(BaseModel):
    kind: Literal["preset", "local_script"]
    entrypoint: str


class CapsuleImplementation(BaseModel):
    runner: CapsuleRunner


class CapsuleDefinition(BaseModel):
    metadata: CapsuleMetadata
    promise: CapsulePromise
    match: CapsuleMatch
    interface: CapsuleInterface
    implementation: CapsuleImplementation
    read_order: CapsuleReadOrder = Field(default_factory=CapsuleReadOrder)

    def public_summary(self) -> dict[str, Any]:
        required = sorted(name for name, field in self.interface.inputs.items() if field.required)
        return {
            "name": self.metadata.name,
            "display_name": self.metadata.display_name,
            "version": self.metadata.version,
            "status": self.metadata.status,
            "summary": self.promise.summary,
            "category": self.match.category,
            "workflow": self.match.workflow,
            "capabilities": self.match.capabilities,
            "tags": self.match.tags,
            "when_to_use": self.match.when_to_use,
            "when_not_to_use": self.match.when_not_to_use,
            "required_inputs": required,
            "inputs": {
                name: field.model_dump(exclude_none=True)
                for name, field in sorted(self.interface.inputs.items())
            },
            "read_order": self.read_order.model_dump(mode="json"),
            "source_schema": self.metadata.source_schema,
        }
