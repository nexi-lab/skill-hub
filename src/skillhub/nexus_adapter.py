"""Boundary for Nexus remote namespace integration.

Phase 1 is remote Nexus-backed, but only at the namespace and install-planning
layer. Packages resolve into stable Nexus target paths without yet executing
runtime resources such as workflows or MCP mounts.
"""

from __future__ import annotations

from dataclasses import dataclass

from skillhub.models import InstallPreview, InstallTarget, NexusRemoteStatus, PackageRecord
from skillhub.settings import Settings


@dataclass(frozen=True)
class InstallPlan:
    """Phase 1/2 installation plan skeleton."""

    package_key: str
    steps: tuple[str, ...]
    nexus_target_path: str


class NexusAdapter:
    """Remote Nexus namespace planning boundary."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def describe_remote(self) -> NexusRemoteStatus:
        """Return the effective remote Nexus configuration."""
        return NexusRemoteStatus(
            base_url=self._settings.nexus_base_url,
            api_key_configured=self._settings.nexus_api_key_configured,
            install_root=self._settings.nexus_install_root,
        )

    def _scope_prefix(self, target: InstallTarget, scope_id: str) -> str:
        if target is InstallTarget.SYSTEM:
            return f"{self._settings.nexus_install_root}/system/packages"
        if target is InstallTarget.ZONE:
            return f"{self._settings.nexus_install_root}/zones/{scope_id}"
        if target is InstallTarget.USER:
            return f"{self._settings.nexus_install_root}/users/{scope_id}"
        return f"{self._settings.nexus_install_root}/agents/{scope_id}"

    def _target_path(self, package: PackageRecord, target: InstallTarget, scope_id: str) -> str:
        prefix = self._scope_prefix(target, scope_id)
        manifest = package.manifest
        return f"{prefix}/{manifest.publisher}/{manifest.name}/{manifest.version}"

    def build_install_plan(
        self,
        package: PackageRecord,
        target: InstallTarget,
        scope_id: str,
    ) -> InstallPlan:
        """Build a stable install plan for Phase 1."""
        nexus_target_path = self._target_path(package, target, scope_id)
        return InstallPlan(
            package_key=package.versioned_key,
            steps=(
                "resolve_remote_namespace",
                "materialize_skill_docs",
                "record_installation",
            ),
            nexus_target_path=nexus_target_path,
        )

    def preview_install(
        self,
        package: PackageRecord,
        target: InstallTarget,
        scope_id: str,
    ) -> InstallPreview:
        """Return the resolved Phase 1 install preview."""
        plan = self.build_install_plan(package, target, scope_id)
        return InstallPreview(
            package_key=package.versioned_key,
            target=target,
            scope_id=scope_id,
            nexus_base_url=self._settings.nexus_base_url,
            nexus_target_path=plan.nexus_target_path,
            steps=list(plan.steps),
            capabilities_requested=list(package.manifest.capabilities_requested),
        )

    def apply_install_plan(self, _plan: InstallPlan) -> None:
        raise NotImplementedError("Phase 2: Nexus runtime integration is not implemented yet.")
