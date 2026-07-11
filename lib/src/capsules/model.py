from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


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


class CapsuleInterface(BaseModel):
    inputs: dict[str, CapsuleInput] = Field(default_factory=dict)


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
            "source_schema": self.metadata.source_schema,
        }
