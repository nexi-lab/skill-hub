"""In-memory stores for Phase 1."""

from __future__ import annotations

from collections import defaultdict

from skillhub.models import InstallationRecord, PackageRecord


class PackageStore:
    """A simple in-memory package catalog."""

    def __init__(self) -> None:
        self._packages: dict[str, dict[str, PackageRecord]] = defaultdict(dict)

    def upsert(self, package: PackageRecord) -> PackageRecord:
        self._packages[package.package_key][package.manifest.version] = package
        return package

    def list_all(self) -> list[PackageRecord]:
        items: list[PackageRecord] = []
        for versions in self._packages.values():
            items.extend(versions.values())
        return sorted(items, key=lambda item: item.versioned_key)

    def get_versions(self, package_key: str) -> list[PackageRecord]:
        versions = list(self._packages.get(package_key, {}).values())
        return sorted(versions, key=lambda item: item.manifest.version)

    def get(self, package_key: str, version: str) -> PackageRecord | None:
        return self._packages.get(package_key, {}).get(version)


class InstallationStore:
    """A simple in-memory install tracker."""

    def __init__(self) -> None:
        self._installations: list[InstallationRecord] = []

    def add(self, installation: InstallationRecord) -> InstallationRecord:
        self._installations.append(installation)
        return installation

    def list_all(self) -> list[InstallationRecord]:
        return list(self._installations)

    def get(self, installation_id: str) -> InstallationRecord | None:
        for installation in self._installations:
            if installation.id == installation_id:
                return installation
        return None
