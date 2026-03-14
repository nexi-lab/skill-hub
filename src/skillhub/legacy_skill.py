"""Helpers for converting legacy ``.skill`` archives into Phase 1 packages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import io
import zipfile

import yaml

from skillhub.local_package import build_package_archive
from skillhub.models import (
    InstallTarget,
    ManifestEntrypoints,
    ManifestFiles,
    PackageType,
    RiskLevel,
    ScriptEntrypoint,
    SkillManifest,
)

_TEXT_REFERENCE_EXTENSIONS = {".md", ".txt"}


@dataclass(frozen=True)
class LegacySkillPackage:
    """In-memory Phase 1 package synthesized from a legacy archive."""

    archive_path: Path
    manifest: SkillManifest
    package_files: dict[str, bytes]

    def build_archive(self) -> bytes:
        """Build a publishable package zip."""
        files = list(self.package_files.items())
        files.append(
            (
                "skillhub.yaml",
                yaml.safe_dump(
                    self.manifest.model_dump(mode="json"),
                    sort_keys=False,
                    allow_unicode=False,
                ).encode("utf-8"),
            )
        )
        return build_package_archive(files)


def _parse_frontmatter(skill_doc_text: str) -> tuple[dict[str, object], str]:
    if not skill_doc_text.startswith("---\n"):
        return {}, skill_doc_text

    lines = skill_doc_text.splitlines()
    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break

    if end_index is None:
        return {}, skill_doc_text

    frontmatter = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).lstrip("\n")
    parsed = yaml.safe_load(frontmatter) or {}
    if not isinstance(parsed, dict):
        raise ValueError("Legacy skill frontmatter must parse into a mapping")
    return parsed, body


def _normalize_member_name(member_name: str) -> str | None:
    normalized = PurePosixPath(member_name.strip("/"))
    if not normalized.parts:
        return None
    if normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError(f"Archive member escapes package root: {member_name}")
    if normalized.name == ".DS_Store" or normalized.parts[0] == "__MACOSX":
        return None
    return normalized.as_posix()


def _strip_common_root(member_names: list[str]) -> dict[str, str]:
    if not member_names:
        return {}
    first_parts = {PurePosixPath(name).parts[0] for name in member_names}
    if len(first_parts) != 1:
        return {name: name for name in member_names}

    root = next(iter(first_parts))
    stripped: dict[str, str] = {}
    for name in member_names:
        path = PurePosixPath(name)
        if len(path.parts) == 1:
            stripped[name] = name
        else:
            stripped[name] = PurePosixPath(*path.parts[1:]).as_posix()

    if any(value == "SKILL.md" for value in stripped.values()):
        return stripped
    return {name: name for name in member_names}


def build_legacy_skill_package(
    archive_path: str | Path,
    *,
    publisher: str,
    version: str,
) -> LegacySkillPackage:
    """Convert one legacy ``.skill`` zip archive into a Phase 1 package."""
    path = Path(archive_path).expanduser().resolve()
    with zipfile.ZipFile(path) as archive:
        raw_member_names = [
            normalized
            for info in archive.infolist()
            if not info.is_dir()
            for normalized in [_normalize_member_name(info.filename)]
            if normalized is not None
        ]
        member_name_map = _strip_common_root(raw_member_names)
        package_files = {
            member_name_map[name]: archive.read(name)
            for name in raw_member_names
        }

    try:
        skill_doc_bytes = package_files["SKILL.md"]
    except KeyError as exc:
        raise FileNotFoundError(f"Legacy skill archive has no SKILL.md: {path}") from exc

    skill_doc_text = skill_doc_bytes.decode("utf-8", errors="replace")
    metadata, _ = _parse_frontmatter(skill_doc_text)

    text_references = sorted(
        relative_path
        for relative_path in package_files
        if relative_path != "SKILL.md"
        and Path(relative_path).suffix.lower() in _TEXT_REFERENCE_EXTENSIONS
        and Path(relative_path).name.lower() != "license.txt"
    )
    script_paths = sorted(
        relative_path for relative_path in package_files if Path(relative_path).suffix.lower() == ".py"
    )
    asset_paths = sorted(
        relative_path
        for relative_path in package_files
        if relative_path not in {"SKILL.md", *text_references}
    )

    manifest = SkillManifest(
        name=str(metadata.get("name") or path.stem.removesuffix(".skill")),
        publisher=publisher,
        version=version,
        type=PackageType.PROMPT_PACK,
        description=str(metadata.get("description") or "").strip(),
        install_target=InstallTarget.USER,
        capabilities_requested=["read_skill_docs"],
        risk_level=RiskLevel.MEDIUM if script_paths else RiskLevel.LOW,
        files=ManifestFiles(
            skill_doc="SKILL.md",
            references=text_references,
            examples=[],
            assets=asset_paths,
        ),
        entrypoints=ManifestEntrypoints(
            scripts=[
                ScriptEntrypoint(name=Path(relative_path).stem, path=relative_path)
                for relative_path in script_paths
            ]
        ),
    )
    return LegacySkillPackage(archive_path=path, manifest=manifest, package_files=package_files)


def read_legacy_skill_description(archive_path: str | Path) -> str:
    """Return the body-less description metadata from a legacy skill archive."""
    package = build_legacy_skill_package(
        archive_path,
        publisher="preview",
        version="0.0.0-preview",
    )
    return package.manifest.description
