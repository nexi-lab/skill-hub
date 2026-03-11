"""Core domain models for Phase 1."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class PackageType(StrEnum):
    """Top-level package types supported by the hub."""

    WORKFLOW_PACK = "workflow_pack"
    PROMPT_PACK = "prompt_pack"
    MCP_SERVER = "mcp_server"
    BUNDLE = "bundle"


class InstallTarget(StrEnum):
    """Scope where a package is intended to land."""

    SYSTEM = "system"
    ZONE = "zone"
    USER = "user"
    AGENT = "agent"


class RiskLevel(StrEnum):
    """Coarse risk declaration for Phase 1."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CredentialType(StrEnum):
    """Credential categories declared by a package."""

    OAUTH = "oauth"
    API_KEY = "api_key"
    SECRET = "secret"


class CredentialRequirement(BaseModel):
    """A declared credential dependency."""

    name: str = Field(..., description="Stable key used by the package.")
    type: CredentialType = Field(..., description="How the secret is provided.")
    required: bool = Field(default=True)
    description: str = Field(default="")


class PermissionRequest(BaseModel):
    """Requested capability label for human review.

    Phase 1 treats these as informative metadata only.
    """

    capability: str = Field(..., description="Capability identifier such as outbound_http.")
    reason: str = Field(default="")


class ManifestFiles(BaseModel):
    """Logical file groupings inside a package."""

    skill_doc: str = "SKILL.md"
    references: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)


class ScriptEntrypoint(BaseModel):
    """Declared script entrypoint.

    Phase 1 validates these as metadata only; it does not execute them.
    """

    name: str
    path: str
    runtime: str = Field(default="python3.12")


class WorkflowEntrypoint(BaseModel):
    """Workflow artifact to be materialized in Phase 2."""

    path: str


class MCPServerEntrypoint(BaseModel):
    """Mounted MCP server description for Phase 2."""

    name: str
    transport: Literal["stdio", "http", "sse"]
    command: str | None = None
    url: str | None = None
    args: list[str] = Field(default_factory=list)


class ManifestEntrypoints(BaseModel):
    """Package entrypoint groups."""

    scripts: list[ScriptEntrypoint] = Field(default_factory=list)
    workflows: list[WorkflowEntrypoint] = Field(default_factory=list)
    mcp_servers: list[MCPServerEntrypoint] = Field(default_factory=list)


class SkillManifest(BaseModel):
    """Machine-readable package manifest."""

    schema_version: Literal["1"] = "1"
    name: str
    publisher: str
    version: str
    type: PackageType
    description: str = ""
    nexus_version: str = Field(default=">=0.1.0")
    install_target: InstallTarget = InstallTarget.USER
    capabilities_requested: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    credentials: list[CredentialRequirement] = Field(default_factory=list)
    permissions: list[PermissionRequest] = Field(default_factory=list)
    files: ManifestFiles = Field(default_factory=ManifestFiles)
    entrypoints: ManifestEntrypoints = Field(default_factory=ManifestEntrypoints)

    @field_validator("name", "publisher", "version")
    @classmethod
    def _no_blank_values(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @property
    def package_key(self) -> str:
        """Canonical package key without version."""
        return f"{self.publisher}/{self.name}"

    @property
    def versioned_key(self) -> str:
        """Canonical package key including version."""
        return f"{self.package_key}@{self.version}"


class PackageRegistrationRequest(BaseModel):
    """API request for registering a package version."""

    manifest: SkillManifest
    artifact_uri: str = Field(default="")
    artifact_digest: str = Field(default="")


class PackageRecord(BaseModel):
    """Stored package version metadata."""

    manifest: SkillManifest
    artifact_uri: str = ""
    artifact_digest: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def package_key(self) -> str:
        return self.manifest.package_key

    @property
    def versioned_key(self) -> str:
        return self.manifest.versioned_key


class InstallationStatus(StrEnum):
    """Lifecycle for tracked installs."""

    PENDING = "pending"
    INSTALLED = "installed"
    FAILED = "failed"


class InstallationRequest(BaseModel):
    """Install a package into a target scope."""

    publisher: str
    name: str
    version: str
    target: InstallTarget
    scope_id: str = Field(..., description="The user, agent, or zone identifier.")


class InstallationRecord(BaseModel):
    """Tracked install state."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    package_key: str
    target: InstallTarget
    scope_id: str
    status: InstallationStatus = InstallationStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
