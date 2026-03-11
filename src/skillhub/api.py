"""FastAPI application for Phase 1."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from skillhub.models import (
    InstallationListResponse,
    InstallationRequest,
    InstallationResponse,
    InstallPreview,
    NexusRemoteStatus,
    PackageListResponse,
    PackageRegistrationRequest,
    PackageVersionResponse,
    PackageVersionsResponse,
)
from skillhub.service import SkillHubService

app = FastAPI(
    title="skill-hub",
    version="0.1.0",
    summary="Remote Nexus-backed skill catalog and install control plane.",
    description=(
        "Phase 1 of skill-hub packages, registers, previews, and records installs "
        "for SKILL.md-based packages using remote Nexus namespace conventions."
    ),
)
service = SkillHubService()


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness endpoint."""
    return {"status": "ok"}


@app.get("/v1/nexus", response_model=NexusRemoteStatus, tags=["nexus"])
def get_nexus_remote() -> NexusRemoteStatus:
    """Expose the effective remote Nexus configuration used for planning."""
    return service.nexus.describe_remote()


@app.get("/v1/packages", response_model=PackageListResponse, tags=["packages"])
def list_packages() -> PackageListResponse:
    """List registered package versions."""
    return PackageListResponse(packages=service.list_packages())


@app.post(
    "/v1/packages/register",
    status_code=201,
    response_model=PackageVersionResponse,
    tags=["packages"],
)
def register_package(request: PackageRegistrationRequest) -> PackageVersionResponse:
    """Register a package version in the catalog."""
    package = service.register_package(request)
    return PackageVersionResponse(package=package)


@app.get(
    "/v1/packages/{publisher}/{name}",
    response_model=PackageVersionsResponse,
    tags=["packages"],
)
def get_package_versions(publisher: str, name: str) -> PackageVersionsResponse:
    """List versions for a package key."""
    packages = service.get_package_versions(publisher, name)
    if not packages:
        raise HTTPException(status_code=404, detail="Package not found")
    return PackageVersionsResponse(packages=packages)


@app.get(
    "/v1/packages/{publisher}/{name}/{version}",
    response_model=PackageVersionResponse,
    tags=["packages"],
)
def get_package_version(publisher: str, name: str, version: str) -> PackageVersionResponse:
    """Get one specific package version."""
    try:
        package = service.get_package_version(publisher, name, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PackageVersionResponse(package=package)


@app.post("/v1/installations/preview", response_model=InstallPreview, tags=["installations"])
def preview_install(request: InstallationRequest) -> InstallPreview:
    """Preview the remote Nexus namespace path for an install."""
    try:
        return service.preview_install(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/v1/installations",
    status_code=201,
    response_model=InstallationResponse,
    tags=["installations"],
)
def install_package(request: InstallationRequest) -> InstallationResponse:
    """Record a package install for a target scope."""
    try:
        installation = service.install_package(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InstallationResponse(installation=installation)


@app.get("/v1/installations", response_model=InstallationListResponse, tags=["installations"])
def list_installations() -> InstallationListResponse:
    """List recorded installs."""
    return InstallationListResponse(installations=service.list_installations())
