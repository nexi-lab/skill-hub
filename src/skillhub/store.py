"""Catalog stores with Nexus-backed persistence and in-memory fallback."""

from __future__ import annotations

from collections import defaultdict

from skillhub.local_package import LocalPackageFile
from skillhub.models import InstallationRecord, PackageRecord, PackageSearchHit
from skillhub.nexus_adapter import NexusAdapter


class PackageStore:
    """Package catalog with optional Nexus-backed persistence."""

    def __init__(self, adapter: NexusAdapter | None = None) -> None:
        self._adapter = adapter
        self._packages: dict[str, dict[str, PackageRecord]] = defaultdict(dict)

    def upsert(
        self,
        package: PackageRecord,
        package_files: list[LocalPackageFile] | None = None,
    ) -> PackageRecord:
        if self._adapter is not None:
            return self._adapter.publish_package(package, package_files)
        stored = package
        if package_files:
            stored = package.model_copy(
                update={
                    "artifact_uri": package.artifact_uri or package.source_uri,
                    "artifact_files": [item.relative_path for item in package_files],
                }
            )
        self._packages[stored.package_key][stored.manifest.version] = stored
        return stored

    def list_all(self) -> list[PackageRecord]:
        if self._adapter is not None:
            return self._adapter.list_packages()
        items: list[PackageRecord] = []
        for versions in self._packages.values():
            items.extend(versions.values())
        return sorted(items, key=lambda item: item.versioned_key)

    def get_versions(self, package_key: str) -> list[PackageRecord]:
        if self._adapter is not None:
            versions = [item for item in self._adapter.list_packages() if item.package_key == package_key]
            return sorted(versions, key=lambda item: item.manifest.version)
        versions = list(self._packages.get(package_key, {}).values())
        return sorted(versions, key=lambda item: item.manifest.version)

    def get(self, package_key: str, version: str) -> PackageRecord | None:
        if self._adapter is not None:
            publisher, name = package_key.split("/", 1)
            return self._adapter.get_package(publisher, name, version)
        return self._packages.get(package_key, {}).get(version)

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        mode: str = "hybrid",
    ) -> tuple[str, list[PackageSearchHit]]:
        if self._adapter is not None:
            return self._adapter.search_packages(query, limit=limit, mode=mode)
        lowered = query.lower()
        hits: list[PackageSearchHit] = []
        for package in self.list_all():
            haystack = "\n".join(
                [
                    package.manifest.publisher,
                    package.manifest.name,
                    package.manifest.version,
                    package.manifest.description,
                    *package.manifest.capabilities_requested,
                ]
            ).lower()
            if lowered not in haystack:
                continue
            hits.append(
                PackageSearchHit(
                    package=package,
                    score=1.0,
                    snippet=package.manifest.description,
                    backend="memory_fallback",
                )
            )
        return ("memory_fallback", hits[:limit])


class InstallationStore:
    """Install tracker with optional Nexus-backed persistence."""

    def __init__(self, adapter: NexusAdapter | None = None) -> None:
        self._adapter = adapter
        self._installations: list[InstallationRecord] = []

    def add(self, installation: InstallationRecord) -> InstallationRecord:
        if self._adapter is not None:
            return self._adapter.upsert_installation(installation)
        self._installations.append(installation)
        return installation

    def list_all(self) -> list[InstallationRecord]:
        if self._adapter is not None:
            return self._adapter.list_installations()
        return list(self._installations)

    def get(self, installation_id: str) -> InstallationRecord | None:
        if self._adapter is not None:
            return self._adapter.get_installation(installation_id)
        for installation in self._installations:
            if installation.id == installation_id:
                return installation
        return None
