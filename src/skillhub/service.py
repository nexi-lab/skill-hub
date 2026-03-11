"""Phase 1 service layer."""

from __future__ import annotations

from skillhub.models import (
    InstallationRecord,
    InstallationRequest,
    InstallationStatus,
    PackageRecord,
    PackageRegistrationRequest,
)
from skillhub.store import InstallationStore, PackageStore


class SkillHubService:
    """Phase 1 coordinator for package registration and install tracking."""

    def __init__(
        self,
        package_store: PackageStore | None = None,
        installation_store: InstallationStore | None = None,
    ) -> None:
        self._packages = package_store or PackageStore()
        self._installations = installation_store or InstallationStore()

    def register_package(self, request: PackageRegistrationRequest) -> PackageRecord:
        package = PackageRecord(
            manifest=request.manifest,
            artifact_uri=request.artifact_uri,
            artifact_digest=request.artifact_digest,
        )
        return self._packages.upsert(package)

    def list_packages(self) -> list[PackageRecord]:
        return self._packages.list_all()

    def get_package_versions(self, publisher: str, name: str) -> list[PackageRecord]:
        package_key = f"{publisher}/{name}"
        return self._packages.get_versions(package_key)

    def install_package(self, request: InstallationRequest) -> InstallationRecord:
        package_key = f"{request.publisher}/{request.name}"
        package = self._packages.get(package_key, request.version)
        if package is None:
            raise KeyError(f"Unknown package version: {package_key}@{request.version}")

        installation = InstallationRecord(
            package_key=package.versioned_key,
            target=request.target,
            scope_id=request.scope_id,
            status=InstallationStatus.INSTALLED,
        )
        return self._installations.add(installation)

    def list_installations(self) -> list[InstallationRecord]:
        return self._installations.list_all()
