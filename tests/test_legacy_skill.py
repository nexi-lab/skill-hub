from __future__ import annotations

import io
from pathlib import Path
import zipfile

from skillhub.legacy_skill import build_legacy_skill_package


def _make_legacy_skill_archive(path: Path) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "demo-skill/SKILL.md",
            """---
name: demo-skill
description: Demonstration legacy skill
---

# Demo Skill

Use this for demonstrations.
""",
        )
        archive.writestr("demo-skill/reference.md", "# Reference\n")
        archive.writestr("demo-skill/examples/howto.md", "# Example\n")
        archive.writestr("demo-skill/scripts/tool.py", "print('hi')\n")
        archive.writestr("demo-skill/LICENSE.txt", "license\n")


def test_build_legacy_skill_package(tmp_path: Path) -> None:
    archive_path = tmp_path / "demo.skill"
    _make_legacy_skill_archive(archive_path)

    package = build_legacy_skill_package(
        archive_path,
        publisher="nexus-builtin",
        version="0.1.0-test",
    )

    assert package.manifest.name == "demo-skill"
    assert package.manifest.publisher == "nexus-builtin"
    assert package.manifest.files.skill_doc == "SKILL.md"
    assert package.manifest.files.references == [
        "examples/howto.md",
        "reference.md",
    ]
    assert "LICENSE.txt" in package.manifest.files.assets
    assert package.manifest.entrypoints.scripts[0].path == "scripts/tool.py"


def test_build_archive_includes_generated_manifest(tmp_path: Path) -> None:
    archive_path = tmp_path / "demo.skill"
    _make_legacy_skill_archive(archive_path)
    package = build_legacy_skill_package(
        archive_path,
        publisher="nexus-builtin",
        version="0.1.0-test",
    )

    archive_bytes = package.build_archive()
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        names = sorted(archive.namelist())
        assert "skillhub.yaml" in names
        assert "SKILL.md" in names
        assert "reference.md" in names
        assert "examples/howto.md" in names
        assert "scripts/tool.py" in names
