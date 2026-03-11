"""Typer CLI for Phase 1."""

from __future__ import annotations

from pathlib import Path

import typer

from skillhub.manifest import dump_example_manifest, load_manifest

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
