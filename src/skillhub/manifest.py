"""Manifest loading and example generation."""

from __future__ import annotations

from pathlib import Path

import yaml

from skillhub.models import SkillManifest


def load_manifest(path: str | Path) -> SkillManifest:
    """Load a manifest from YAML."""
    manifest_path = Path(path)
    payload = yaml.safe_load(manifest_path.read_text()) or {}
    return SkillManifest.model_validate(payload)


def dump_example_manifest() -> str:
    """Return a minimal example manifest."""
    example = {
        "schema_version": "1",
        "name": "hello-skill",
        "publisher": "nexi-lab",
        "version": "0.1.0",
        "type": "prompt_pack",
        "description": "Minimal Phase 1 example package.",
        "nexus_version": ">=0.1.0",
        "install_target": "user",
        "capabilities_requested": ["read_skill_docs"],
        "risk_level": "low",
        "credentials": [],
        "permissions": [],
        "files": {
            "skill_doc": "SKILL.md",
            "references": ["references/quickstart.md"],
            "examples": [],
            "assets": [],
        },
        "entrypoints": {
            "scripts": [],
            "workflows": [],
            "mcp_servers": [],
        },
    }
    return yaml.safe_dump(example, sort_keys=False)
