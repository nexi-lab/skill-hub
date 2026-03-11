"""Phase 1 service layer."""

from __future__ import annotations

from skillhub.models import (
    InstallPreview,
    InstallationRecord,
    InstallationRequest,
    InstallationStatus,
    PackageRecord,
    PackageRegistrationRequest,
)
from skillhub.nexus_adapter import NexusAdapter
from skillhub.settings import Settings, get_settings
from skillhub.store import InstallationStore, PackageStore


class SkillHubService:
    """Phase 1 coordinator for package registration and remote install tracking."""

    def __init__(
        self,
        package_store: PackageStore | None = None,
        installation_store: InstallationStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._packages = package_store or PackageStore()
        self._installations = installation_store or InstallationStore()
        self._settings = settings or get_settings()
        self._nexus = NexusAdapter(self._settings)

    @property
    def nexus(self) -> NexusAdapter:
        """Expose the Nexus adapter for API handlers."""
        return self._nexus

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

    def get_package_version(self, publisher: str, name: str, version: str) -> PackageRecord:
        """Fetch one package version by key."""
        package_key = f"{publisher}/{name}"
        package = self._packages.get(package_key, version)
        if package is None:
            raise KeyError(f"Unknown package version: {package_key}@{version}")
        return package

    def preview_install(self, request: InstallationRequest) -> InstallPreview:
        """Resolve the remote Nexus target path for a package install."""
        package = self.get_package_version(request.publisher, request.name, request.version)
        return self._nexus.preview_install(package, request.target, request.scope_id)

    def install_package(self, request: InstallationRequest) -> InstallationRecord:
        package = self.get_package_version(request.publisher, request.name, request.version)
        preview = self._nexus.preview_install(package, request.target, request.scope_id)

        installation = InstallationRecord(
            package_key=package.versioned_key,
            target=request.target,
            scope_id=request.scope_id,
            nexus_base_url=preview.nexus_base_url,
            nexus_target_path=preview.nexus_target_path,
            status=InstallationStatus.INSTALLED,
        )
        return self._installations.add(installation)

    def list_installations(self) -> list[InstallationRecord]:
        return self._installations.list_all()
