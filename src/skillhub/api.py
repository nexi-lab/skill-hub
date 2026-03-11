"""FastAPI application for Phase 1."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from skillhub.models import InstallationRequest, PackageRegistrationRequest
from skillhub.service import SkillHubService

app = FastAPI(title="skill-hub", version="0.1.0")
service = SkillHubService()


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness endpoint."""
    return {"status": "ok"}


@app.get("/v1/packages")
def list_packages() -> list[dict]:
    """List registered package versions."""
    return [package.model_dump(mode="json") for package in service.list_packages()]


@app.post("/v1/packages/register", status_code=201)
def register_package(request: PackageRegistrationRequest) -> dict:
    """Register a package version in the catalog."""
    package = service.register_package(request)
    return package.model_dump(mode="json")


@app.get("/v1/packages/{publisher}/{name}")
def get_package_versions(publisher: str, name: str) -> dict[str, list[dict]]:
    """List versions for a package key."""
    packages = service.get_package_versions(publisher, name)
    if not packages:
        raise HTTPException(status_code=404, detail="Package not found")
    return {"packages": [package.model_dump(mode="json") for package in packages]}


@app.post("/v1/installations", status_code=201)
def install_package(request: InstallationRequest) -> dict:
    """Track a package install for a target scope."""
    try:
        installation = service.install_package(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return installation.model_dump(mode="json")


@app.get("/v1/installations")
def list_installations() -> list[dict]:
    """List recorded installs."""
    return [item.model_dump(mode="json") for item in service.list_installations()]
