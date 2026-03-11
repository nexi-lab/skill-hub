"""Remote Nexus HTTP integration for Phase 1 installs."""

from __future__ import annotations

import base64
from dataclasses import dataclass

import httpx

from skillhub.local_package import LocalPackageFile, collect_declared_package_files
from skillhub.models import (
    InstallPreview,
    InstallTarget,
    NexusRemoteHealth,
    NexusRemoteStatus,
    PackageRecord,
)
from skillhub.settings import Settings


class NexusRemoteError(RuntimeError):
    """Raised when remote Nexus rejects or fails an operation."""


@dataclass(frozen=True)
class InstallPlan:
    """A concrete Phase 1 install plan against remote Nexus."""

    package_key: str
    steps: tuple[str, ...]
    nexus_target_path: str
    package_files: tuple[LocalPackageFile, ...]
    materialized_files: tuple[str, ...]


class NexusAdapter:
    """Remote Nexus boundary backed by the Phase 1 HTTP file APIs."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def describe_remote(self) -> NexusRemoteStatus:
        """Return the effective remote Nexus configuration."""
        base_url = self._settings.nexus_base_url.rstrip("/")
        return NexusRemoteStatus(
            base_url=base_url,
            api_key_configured=self._settings.nexus_api_key_configured,
            install_root=self._settings.nexus_install_root,
            health_url=f"{base_url}/health",
            files_api_base=f"{base_url}/api/v2/files",
        )

    def probe_remote(self) -> NexusRemoteHealth:
        """Probe remote Nexus health without mutating state."""
        status = self.describe_remote()
        try:
            with httpx.Client(timeout=self._settings.nexus_timeout_seconds) as client:
                response = client.get(status.health_url, headers=self._auth_headers())
            payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            return NexusRemoteHealth(
                reachable=response.is_success,
                status=payload.get("status"),
                service=payload.get("service"),
                http_status=response.status_code,
                detail=payload.get("detail"),
            )
        except httpx.RequestError as exc:
            return NexusRemoteHealth(
                reachable=False,
                detail=str(exc),
            )

    def _auth_headers(self) -> dict[str, str]:
        if not self._settings.nexus_api_key:
            return {}
        return {"Authorization": f"Bearer {self._settings.nexus_api_key}"}

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

    def _plan_files(self, package: PackageRecord) -> tuple[LocalPackageFile, ...]:
        source_dir = package.local_source_dir
        if source_dir is None:
            return ()
        return tuple(collect_declared_package_files(source_dir, package.manifest))

    def build_install_plan(
        self,
        package: PackageRecord,
        target: InstallTarget,
        scope_id: str,
    ) -> InstallPlan:
        """Build the concrete remote install plan for a package."""
        nexus_target_path = self._target_path(package, target, scope_id)
        package_files = self._plan_files(package)
        materialized_files = tuple(
            f"{nexus_target_path}/{package_file.relative_path}" for package_file in package_files
        )
        return InstallPlan(
            package_key=package.versioned_key,
            steps=(
                "probe_remote_health",
                "create_install_root",
                "write_package_files",
                "verify_remote_target",
                "record_installation",
            ),
            nexus_target_path=nexus_target_path,
            package_files=package_files,
            materialized_files=materialized_files,
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
            nexus_base_url=self._settings.nexus_base_url.rstrip("/"),
            nexus_target_path=plan.nexus_target_path,
            steps=list(plan.steps),
            capabilities_requested=list(package.manifest.capabilities_requested),
            materialized_files=list(plan.materialized_files),
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, object] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, object]:
        base_url = self._settings.nexus_base_url.rstrip("/")
        url = f"{base_url}{path}"
        try:
            with httpx.Client(timeout=self._settings.nexus_timeout_seconds) as client:
                response = client.request(
                    method,
                    url,
                    headers=self._auth_headers(),
                    json=json_body,
                    params=params,
                )
        except httpx.RequestError as exc:
            raise NexusRemoteError(f"Failed to reach Nexus at {url}: {exc}") from exc

        if response.status_code >= 400:
            detail = response.text.strip() or response.reason_phrase
            raise NexusRemoteError(f"Nexus {method} {path} failed ({response.status_code}): {detail}")

        if not response.content:
            return {}
        if response.headers.get("content-type", "").startswith("application/json"):
            return dict(response.json())
        return {}

    def _mkdir(self, path: str) -> None:
        self._request(
            "POST",
            "/api/v2/files/mkdir",
            json_body={"path": path, "parents": True},
        )

    def _write_file(self, path: str, content: bytes) -> None:
        try:
            payload = {
                "path": path,
                "content": content.decode("utf-8"),
            }
        except UnicodeDecodeError:
            payload = {
                "path": path,
                "content": base64.b64encode(content).decode("ascii"),
                "encoding": "base64",
            }
        self._request("POST", "/api/v2/files/write", json_body=payload)

    def _exists(self, path: str) -> bool:
        response = self._request("GET", "/api/v2/files/exists", params={"path": path})
        return bool(response.get("exists"))

    def apply_install_plan(self, plan: InstallPlan) -> list[str]:
        """Materialize declared package files into remote Nexus."""
        if not plan.package_files:
            raise NexusRemoteError(
                "Phase 1 install requires a local file:// artifact source. "
                "Register the package from a local directory first."
            )

        health = self.probe_remote()
        if not health.reachable:
            raise NexusRemoteError(
                f"Remote Nexus is unreachable at {self._settings.nexus_base_url}: {health.detail or 'unknown error'}"
            )

        self._mkdir(plan.nexus_target_path)
        written_paths: list[str] = []
        for package_file in plan.package_files:
            target_path = f"{plan.nexus_target_path}/{package_file.relative_path}"
            self._write_file(target_path, package_file.absolute_path.read_bytes())
            written_paths.append(target_path)

        for written_path in written_paths:
            if not self._exists(written_path):
                raise NexusRemoteError(f"Nexus did not report installed file: {written_path}")
        return written_paths
