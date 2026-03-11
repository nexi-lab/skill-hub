"""Typer CLI for Phase 1."""

from __future__ import annotations

import json
from pathlib import Path

import typer
import uvicorn

from skillhub.local_package import load_local_package
from skillhub.manifest import dump_example_manifest, load_manifest
from skillhub.models import InstallTarget, InstallationRequest, LocalPackageRegistrationRequest, PackageRecord
from skillhub.nexus_adapter import NexusAdapter
from skillhub.service import SkillHubService
from skillhub.settings import get_settings

app = typer.Typer(help="skill-hub Phase 1 CLI")


@app.command("validate-manifest")
def validate_manifest(path: Path) -> None:
    """Validate a skillhub.yaml file and print its normalized key."""
    manifest = load_manifest(path)
    typer.echo(f"Valid manifest: {manifest.versioned_key}")


@app.command("print-example")
def print_example() -> None:
    """Print a minimal example manifest."""
    typer.echo(dump_example_manifest())


@app.command("nexus-info")
def nexus_info() -> None:
    """Print the effective remote Nexus configuration."""
    adapter = NexusAdapter(get_settings())
    typer.echo(json.dumps(adapter.describe_remote().model_dump(mode="json"), indent=2))


@app.command("nexus-check")
def nexus_check() -> None:
    """Probe the configured remote Nexus service."""
    adapter = NexusAdapter(get_settings())
    typer.echo(json.dumps(adapter.probe_remote().model_dump(mode="json"), indent=2))


def _load_package_record(path: Path) -> PackageRecord:
    if path.is_dir():
        return load_local_package(path)
    if path.name == "skillhub.yaml":
        return load_local_package(path.parent)
    manifest = load_manifest(path)
    return PackageRecord(manifest=manifest)


@app.command("preview-install")
def preview_install(
    path: Path,
    target: InstallTarget = InstallTarget.USER,
    scope_id: str = "demo-user",
) -> None:
    """Preview the Nexus install plan for a local package or manifest."""
    adapter = NexusAdapter(get_settings())
    package = _load_package_record(path)
    preview = adapter.preview_install(package, target, scope_id)
    typer.echo(json.dumps(preview.model_dump(mode="json"), indent=2))


@app.command("register-local")
def register_local(path: Path) -> None:
    """Register a package version from a local directory."""
    service = SkillHubService()
    package = service.register_local_package(
        LocalPackageRegistrationRequest(source_dir=str(path))
    )
    typer.echo(json.dumps(package.model_dump(mode="json"), indent=2))


@app.command("install-local")
def install_local(
    path: Path,
    target: InstallTarget = InstallTarget.USER,
    scope_id: str = "demo-user",
) -> None:
    """Register and install a local package into remote Nexus."""
    service = SkillHubService()
    package = service.register_local_package(
        LocalPackageRegistrationRequest(source_dir=str(path))
    )
    installation = service.install_package(
        InstallationRequest(
            publisher=package.manifest.publisher,
            name=package.manifest.name,
            version=package.manifest.version,
            target=target,
            scope_id=scope_id,
        )
    )
    typer.echo(json.dumps(installation.model_dump(mode="json"), indent=2))


@app.command("serve")
def serve(host: str = "127.0.0.1", port: int = 8040) -> None:
    """Run the development API server."""
    uvicorn.run("skillhub.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
