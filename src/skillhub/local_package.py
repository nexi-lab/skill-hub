"""Helpers for local package directories."""

from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from skillhub.manifest import load_manifest
from skillhub.models import PackageRecord, SkillManifest


@dataclass(frozen=True)
class LocalPackageFile:
    """A concrete file that should be materialized into Nexus."""

    relative_path: str
    absolute_path: Path


def _ensure_relative_file(package_dir: Path, relative_path: str) -> LocalPackageFile:
    normalized = Path(relative_path)
    if normalized.is_absolute():
        raise ValueError(f"Package paths must be relative: {relative_path}")

    absolute_path = (package_dir / normalized).resolve()
    package_root = package_dir.resolve()
    try:
        absolute_path.relative_to(package_root)
    except ValueError as exc:
        raise ValueError(f"Package path escapes source directory: {relative_path}") from exc

    if not absolute_path.exists():
        raise FileNotFoundError(f"Declared package file not found: {relative_path}")
    if not absolute_path.is_file():
        raise ValueError(f"Declared package path must be a file: {relative_path}")

    return LocalPackageFile(relative_path=normalized.as_posix(), absolute_path=absolute_path)


def _normalize_archive_member(member_name: str) -> tuple[str, ...] | None:
    normalized = PurePosixPath(member_name.strip("/"))
    if not normalized.parts:
        return None
    if normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError(f"Archive member escapes package root: {member_name}")
    if normalized.parts[0] == "__MACOSX":
        return None
    if normalized.name == ".DS_Store":
        return None
    return normalized.parts


def resolve_package_dir(source_dir: str | Path) -> Path:
    """Resolve and validate a local package directory."""
    package_dir = Path(source_dir).expanduser().resolve()
    if not package_dir.exists():
        raise FileNotFoundError(f"Package directory not found: {package_dir}")
    if not package_dir.is_dir():
        raise ValueError(f"Package source must be a directory: {package_dir}")
    return package_dir


def read_local_package_file_bytes(package_dir: str | Path, relative_path: str) -> bytes:
    """Read one declared package file from a local directory."""
    return _ensure_relative_file(resolve_package_dir(package_dir), relative_path).absolute_path.read_bytes()


def collect_declared_package_files(
    package_dir: str | Path,
    manifest: SkillManifest,
) -> list[LocalPackageFile]:
    """Collect all files declared by the manifest for Phase 1 materialization."""
    root = resolve_package_dir(package_dir)
    ordered_paths = [
        "skillhub.yaml",
        manifest.files.skill_doc,
        *manifest.files.references,
        *manifest.files.examples,
        *manifest.files.assets,
        *(entry.path for entry in manifest.entrypoints.scripts),
        *(entry.path for entry in manifest.entrypoints.workflows),
    ]

    seen: set[str] = set()
    files: list[LocalPackageFile] = []
    for relative_path in ordered_paths:
        normalized = Path(relative_path).as_posix()
        if normalized in seen:
            continue
        seen.add(normalized)
        files.append(_ensure_relative_file(root, normalized))
    return files


def extract_package_archive(
    archive_name: str,
    archive_bytes: bytes,
    destination_root: str | Path,
) -> Path:
    """Extract a zip archive into a destination root and return the package directory."""
    root = resolve_package_dir(destination_root)
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            wrote_file = False
            for info in archive.infolist():
                parts = _normalize_archive_member(info.filename)
                if parts is None:
                    continue
                destination = root.joinpath(*parts)
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(info))
                wrote_file = True
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Uploaded package is not a valid zip archive: {archive_name}") from exc

    if not wrote_file:
        raise ValueError(f"Uploaded package archive is empty: {archive_name}")

    direct_manifest = root / "skillhub.yaml"
    if direct_manifest.exists():
        return root

    candidates = sorted({manifest_path.parent for manifest_path in root.rglob("skillhub.yaml")})
    if not candidates:
        raise FileNotFoundError("Uploaded package archive does not contain skillhub.yaml")
    if len(candidates) > 1:
        raise ValueError(
            "Uploaded package archive must contain exactly one package root with skillhub.yaml"
        )
    return candidates[0]


def build_package_archive(files: list[tuple[str, bytes]]) -> bytes:
    """Build a zip archive from relative package paths and file bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_path, content in sorted(files, key=lambda item: item[0]):
            normalized = PurePosixPath(relative_path)
            if normalized.is_absolute() or ".." in normalized.parts:
                raise ValueError(f"Package archive path must stay within package root: {relative_path}")
            archive.writestr(normalized.as_posix(), content)
    return buffer.getvalue()


def compute_local_artifact_digest(files: list[LocalPackageFile]) -> str:
    """Compute a stable digest for the declared package payload."""
    digest = hashlib.sha256()
    for package_file in files:
        digest.update(package_file.relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(package_file.absolute_path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def load_local_package(source_dir: str | Path) -> PackageRecord:
    """Load a local package directory into a catalog record."""
    package_dir = resolve_package_dir(source_dir)
    manifest = load_manifest(package_dir / "skillhub.yaml")
    files = collect_declared_package_files(package_dir, manifest)
    return PackageRecord(
        manifest=manifest,
        source_uri=package_dir.as_uri(),
        artifact_digest=compute_local_artifact_digest(files),
    )
