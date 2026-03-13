"""FastAPI application for Phase 1."""

from __future__ import annotations

from fastapi import Body, FastAPI, HTTPException, Query, Response

from skillhub.models import (
    InstallationListResponse,
    InstallationRequest,
    InstallationResponse,
    InstallPreview,
    PackageArtifactResponse,
    PackageContentResponse,
    LocalPackageRegistrationRequest,
    NexusRemoteHealthResponse,
    NexusRemoteStatus,
    PackageListResponse,
    PackageRegistrationRequest,
    PackageSearchResponse,
    PackageVersionResponse,
    PackageVersionsResponse,
)
from skillhub.nexus_adapter import NexusRemoteError
from skillhub.service import SkillHubService

app = FastAPI(
    title="skill-hub",
    version="0.1.0",
    summary="Nexus-backed skill packaging, catalog, and install control plane.",
    description=(
        "Phase 1 of skill-hub validates local skill packages, registers them in a catalog, "
        "and materializes declared package files into remote Nexus through the /api/v2/files APIs."
    ),
)
service = SkillHubService()


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness endpoint."""
    return {"status": "ok"}


@app.get("/v1/nexus", response_model=NexusRemoteStatus, tags=["nexus"])
def get_nexus_remote() -> NexusRemoteStatus:
    """Expose the effective remote Nexus configuration used for installs."""
    return service.nexus.describe_remote()


@app.get("/v1/nexus/health", response_model=NexusRemoteHealthResponse, tags=["nexus"])
def get_nexus_remote_health() -> NexusRemoteHealthResponse:
    """Probe the configured remote Nexus service."""
    return NexusRemoteHealthResponse(nexus=service.probe_nexus())


@app.get("/v1/packages", response_model=PackageListResponse, tags=["packages"])
def list_packages() -> PackageListResponse:
    """List registered package versions."""
    return PackageListResponse(packages=service.list_packages())


@app.get("/v1/packages/search", response_model=PackageSearchResponse, tags=["packages"])
def search_packages(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    mode: str = Query("hybrid"),
) -> PackageSearchResponse:
    """Search the Nexus-backed package catalog."""
    backend, hits = service.search_packages(q, limit=limit, mode=mode)
    return PackageSearchResponse(query=q, backend=backend, hits=hits)


@app.post(
    "/v1/packages/register",
    status_code=201,
    response_model=PackageVersionResponse,
    tags=["packages"],
)
def register_package(request: PackageRegistrationRequest) -> PackageVersionResponse:
    """Register package metadata only. Internal/admin compatibility endpoint."""
    package = service.register_package(request)
    return PackageVersionResponse(package=package)


@app.post(
    "/v1/packages/register-local",
    status_code=201,
    response_model=PackageVersionResponse,
    tags=["packages"],
)
def register_local_package(request: LocalPackageRegistrationRequest) -> PackageVersionResponse:
    """Register a package from a server-local source directory. Internal/admin endpoint."""
    try:
        package = service.register_local_package(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PackageVersionResponse(package=package)


@app.post(
    "/v1/packages/upload",
    status_code=201,
    response_model=PackageVersionResponse,
    tags=["packages"],
)
def upload_package(
    archive: bytes = Body(..., media_type="application/zip"),
    filename: str = Query("package.zip", min_length=1),
) -> PackageVersionResponse:
    """Upload a zip archive that contains skillhub.yaml and the declared package files."""
    try:
        package = service.upload_package_archive(filename, archive)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NexusRemoteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
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


@app.get(
    "/v1/packages/{publisher}/{name}/{version}/artifact",
    response_model=PackageArtifactResponse,
    tags=["packages"],
)
def get_package_artifact(publisher: str, name: str, version: str) -> PackageArtifactResponse:
    """Return package artifact metadata stored in Nexus."""
    try:
        package = service.get_package_version(publisher, name, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PackageArtifactResponse(
        package=package,
        artifact_root=package.artifact_uri,
        files=package.artifact_files,
    )


@app.get(
    "/v1/packages/{publisher}/{name}/{version}/content",
    response_model=PackageContentResponse,
    tags=["packages"],
)
def get_package_content(
    publisher: str,
    name: str,
    version: str,
    path: str = Query(..., min_length=1),
) -> PackageContentResponse:
    """Read one package artifact file from the Nexus-backed catalog."""
    try:
        content = service.get_package_artifact_content(publisher, name, version, path)
        package = service.get_package_version(publisher, name, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NexusRemoteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return PackageContentResponse(package_key=package.versioned_key, path=path, content=content)


@app.get(
    "/v1/packages/{publisher}/{name}/{version}/download",
    tags=["packages"],
)
def download_package(publisher: str, name: str, version: str) -> Response:
    """Download one published package version as a zip archive."""
    try:
        filename, archive = service.download_package_archive(publisher, name, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except NexusRemoteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    """Install a package by materializing its declared files into remote Nexus."""
    try:
        installation = service.install_package(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NexusRemoteError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return InstallationResponse(installation=installation)


@app.get("/v1/installations", response_model=InstallationListResponse, tags=["installations"])
def list_installations() -> InstallationListResponse:
    """List recorded installs."""
    return InstallationListResponse(installations=service.list_installations())


@app.get(
    "/v1/installations/{installation_id}",
    response_model=InstallationResponse,
    tags=["installations"],
)
def get_installation(installation_id: str) -> InstallationResponse:
    """Fetch one installation record."""
    try:
        installation = service.get_installation(installation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InstallationResponse(installation=installation)
