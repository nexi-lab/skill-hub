"""Phase 1 service layer."""

from __future__ import annotations

from pathlib import Path

from skillhub.local_package import collect_declared_package_files, load_local_package
from skillhub.models import (
    InstallPreview,
    InstallationRecord,
    InstallationRequest,
    InstallationStatus,
    LocalPackageRegistrationRequest,
    NexusRemoteHealth,
    PackageRecord,
    PackageSearchHit,
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
        self._settings = settings or get_settings()
        self._nexus = NexusAdapter(self._settings)
        self._packages = package_store or PackageStore(adapter=self._nexus)
        self._installations = installation_store or InstallationStore(adapter=self._nexus)

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

    def register_local_package(self, request: LocalPackageRegistrationRequest) -> PackageRecord:
        """Register a package directly from a local source directory."""
        package_dir = Path(request.source_dir)
        package = load_local_package(package_dir)
        package_files = collect_declared_package_files(package_dir, package.manifest)
        return self._packages.upsert(package, package_files)

    def list_packages(self) -> list[PackageRecord]:
        return self._packages.list_all()

    def search_packages(
        self,
        query: str,
        *,
        limit: int = 10,
        mode: str = "hybrid",
    ) -> tuple[str, list[PackageSearchHit]]:
        """Search the package catalog."""
        return self._packages.search(query, limit=limit, mode=mode)

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

    def get_package_artifact_content(
        self,
        publisher: str,
        name: str,
        version: str,
        path: str,
    ) -> str:
        """Read one package artifact file from Nexus."""
        package = self.get_package_version(publisher, name, version)
        return self._nexus.get_package_artifact_content(package, path)

    def probe_nexus(self) -> NexusRemoteHealth:
        """Probe remote Nexus health."""
        return self._nexus.probe_remote()

    def preview_install(self, request: InstallationRequest) -> InstallPreview:
        """Resolve the remote Nexus target path for a package install."""
        package = self.get_package_version(request.publisher, request.name, request.version)
        return self._nexus.preview_install(package, request.target, request.scope_id)

    def install_package(self, request: InstallationRequest) -> InstallationRecord:
        package = self.get_package_version(request.publisher, request.name, request.version)
        plan = self._nexus.build_install_plan(package, request.target, request.scope_id)
        materialized_files = self._nexus.apply_install_plan(plan)

        installation = InstallationRecord(
            package_key=package.versioned_key,
            target=request.target,
            scope_id=request.scope_id,
            nexus_base_url=self._settings.nexus_base_url,
            nexus_target_path=plan.nexus_target_path,
            source_artifact_uri=package.source_uri or package.artifact_uri,
            materialized_files=materialized_files,
            status=InstallationStatus.INSTALLED,
        )
        return self._installations.add(installation)

    def list_installations(self) -> list[InstallationRecord]:
        return self._installations.list_all()

    def get_installation(self, installation_id: str) -> InstallationRecord:
        installation = self._installations.get(installation_id)
        if installation is None:
            raise KeyError(f"Unknown installation: {installation_id}")
        return installation
