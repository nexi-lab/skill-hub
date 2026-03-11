"""Boundary for future Nexus runtime integration.

Phase 1 does not execute packages through Nexus. This adapter is the seam
where Phase 2 will translate registered packages into Nexus-native runtime
resources such as workflows, MCP mounts, manifests, and access manifests.
"""

from __future__ import annotations

from dataclasses import dataclass

from skillhub.models import PackageRecord


@dataclass(frozen=True)
class InstallPlan:
    """Phase 2 installation plan skeleton."""

    package_key: str
    steps: tuple[str, ...]


class NexusAdapter:
    """Future runtime integration boundary."""

    def build_install_plan(self, package: PackageRecord) -> InstallPlan:
        return InstallPlan(
            package_key=package.versioned_key,
            steps=(
                "snapshot_scope",
                "materialize_skill_docs",
                "register_runtime_resources",
                "apply_permissions",
            ),
        )

    def apply_install_plan(self, _plan: InstallPlan) -> None:
        raise NotImplementedError("Phase 2: Nexus runtime integration is not implemented yet.")
