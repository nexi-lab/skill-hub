"""Typer CLI for Phase 1."""

from __future__ import annotations

import json
from pathlib import Path

import typer
import uvicorn

from skillhub.manifest import dump_example_manifest, load_manifest
from skillhub.models import InstallTarget, PackageRecord
from skillhub.nexus_adapter import NexusAdapter
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


@app.command("preview-install")
def preview_install(
    path: Path,
    target: InstallTarget = InstallTarget.USER,
    scope_id: str = "demo-user",
) -> None:
    """Preview the remote Nexus namespace path for a manifest."""
    manifest = load_manifest(path)
    adapter = NexusAdapter(get_settings())
    package = PackageRecord(manifest=manifest)
    preview = adapter.preview_install(package, target, scope_id)
    typer.echo(json.dumps(preview.model_dump(mode="json"), indent=2))


@app.command("serve")
def serve(host: str = "127.0.0.1", port: int = 8040) -> None:
    """Run the development API server."""
    uvicorn.run("skillhub.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
