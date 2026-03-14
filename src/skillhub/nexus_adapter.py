"""Remote Nexus integration for the package catalog and installs."""

from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import httpx

from skillhub.local_package import LocalPackageFile
from skillhub.models import (
    InstallPreview,
    InstallTarget,
    InstallationRecord,
    NexusRemoteHealth,
    NexusRemoteStatus,
    PackageRecord,
    PackageSearchHit,
)
from skillhub.settings import Settings


class NexusRemoteError(RuntimeError):
    """Raised when remote Nexus rejects or fails an operation."""


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InstallPlan:
    """A concrete install plan sourced from the Nexus catalog artifact store."""

    package_key: str
    steps: tuple[str, ...]
    nexus_target_path: str
    source_artifact_root: str
    source_files: tuple[str, ...]
    materialized_files: tuple[str, ...]


class NexusAdapter:
    """Remote Nexus boundary backed by health, files, and search APIs."""

    _SEARCH_RETRY_DELAYS_SECONDS = (0.0, 0.15, 0.35)
    _SEARCH_PUBLISH_WAIT_TIMEOUT_SECONDS = 10.0
    _SEARCH_PUBLISH_WAIT_POLL_SECONDS = 0.25

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def catalog_root(self) -> str:
        return self._settings.nexus_catalog_root.rstrip("/")

    @property
    def package_index_path(self) -> str:
        return f"{self.catalog_root}/index/packages.json"

    @property
    def installation_index_path(self) -> str:
        return f"{self.catalog_root}/index/installations.json"

    @property
    def catalog_packages_root(self) -> str:
        return f"{self.catalog_root}/packages"

    @property
    def catalog_artifacts_root(self) -> str:
        return f"{self.catalog_root}/artifacts"

    @property
    def catalog_search_root(self) -> str:
        return f"{self.catalog_root}/search"

    @property
    def catalog_installations_root(self) -> str:
        return f"{self.catalog_root}/installations"

    def describe_remote(self) -> NexusRemoteStatus:
        """Return the effective remote Nexus configuration."""
        base_url = self._settings.nexus_base_url.rstrip("/")
        return NexusRemoteStatus(
            base_url=base_url,
            api_key_configured=self._settings.nexus_api_key_configured,
            install_root=self._settings.nexus_install_root,
            catalog_root=self.catalog_root,
            health_url=f"{base_url}/health",
            files_api_base=f"{base_url}/api/v2/files",
            search_api_base=f"{base_url}/api/v2/search",
        )

    def probe_remote(self) -> NexusRemoteHealth:
        """Probe remote Nexus health without mutating state."""
        status = self.describe_remote()
        try:
            with httpx.Client(timeout=self._settings.nexus_timeout_seconds) as client:
                response = client.get(status.health_url, headers=self._auth_headers())
            payload = self._json_or_empty(response)
            return NexusRemoteHealth(
                reachable=response.is_success,
                status=payload.get("status"),
                service=payload.get("service"),
                http_status=response.status_code,
                detail=payload.get("detail"),
            )
        except httpx.RequestError as exc:
            return NexusRemoteHealth(reachable=False, detail=str(exc))

    def _auth_headers(self) -> dict[str, str]:
        if not self._settings.nexus_api_key:
            return {}
        return {"Authorization": f"Bearer {self._settings.nexus_api_key}"}

    def _json_or_empty(self, response: httpx.Response) -> dict[str, Any]:
        if not response.content:
            return {}
        if response.headers.get("content-type", "").startswith("application/json"):
            payload = response.json()
            if isinstance(payload, dict):
                return dict(payload)
        return {}

    def _decode_rpc_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            marker = value.get("__type__")
            if marker == "bytes" and isinstance(value.get("data"), str):
                return base64.b64decode(value["data"])
            return {key: self._decode_rpc_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._decode_rpc_value(item) for item in value]
        return value

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, object] | None = None,
        params: dict[str, str] | None = None,
        expected_statuses: set[int] | None = None,
    ) -> httpx.Response:
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

        allowed = expected_statuses or {200}
        if response.status_code not in allowed:
            detail = response.text.strip() or response.reason_phrase
            raise NexusRemoteError(f"Nexus {method} {path} failed ({response.status_code}): {detail}")
        return response

    def _rpc_request(
        self,
        method: str,
        params: dict[str, object] | None = None,
    ) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {},
        }
        response = self._request(
            "POST",
            f"/api/nfs/{method}",
            json_body=payload,
        )
        body = self._json_or_empty(response)
        error = body.get("error")
        if error:
            raise NexusRemoteError(f"Nexus RPC {method} failed: {error}")
        return self._decode_rpc_value(body.get("result"))

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

    def _artifact_root_path(self, package: PackageRecord) -> str:
        return f"{self.catalog_artifacts_root}/{package.manifest.publisher}/{package.manifest.name}/{package.manifest.version}"

    def _artifact_index_path(self, package: PackageRecord) -> str:
        return f"{self._artifact_root_path(package)}/artifact-index.json"

    def _package_record_path(
        self,
        publisher: str,
        name: str,
        version: str,
    ) -> str:
        return f"{self.catalog_packages_root}/{publisher}/{name}/{version}/package.json"

    def _package_search_document_path(
        self,
        publisher: str,
        name: str,
        version: str,
    ) -> str:
        return f"{self.catalog_search_root}/{publisher}/{name}/{version}/document.md"

    def _installation_path(self, installation_id: str) -> str:
        return f"{self.catalog_installations_root}/{installation_id}.json"

    def _mkdir(self, path: str) -> None:
        self._rpc_request("mkdir", {"path": path, "parents": True, "exist_ok": True})

    def _ensure_parent_directory(self, path: str) -> None:
        parent = str(PurePosixPath(path).parent)
        if parent and parent != ".":
            self._mkdir(parent)

    def _write_file(self, path: str, content: bytes) -> None:
        self._ensure_parent_directory(path)
        try:
            rpc_content: object = content.decode("utf-8")
        except UnicodeDecodeError:
            rpc_content = {
                "__type__": "bytes",
                "data": base64.b64encode(content).decode("ascii"),
            }
        self._rpc_request("write", {"path": path, "content": rpc_content})

    def _write_text(self, path: str, content: str) -> None:
        self._write_file(path, content.encode("utf-8"))

    def _write_json(self, path: str, payload: dict[str, Any]) -> None:
        self._write_text(path, json.dumps(payload, indent=2, sort_keys=True))

    def _exists(self, path: str) -> bool:
        try:
            result = self._rpc_request("exists", {"path": path})
        except NexusRemoteError:
            response = self._request(
                "GET",
                "/api/v2/files/exists",
                params={"path": path},
            )
            return bool(self._json_or_empty(response).get("exists"))
        if isinstance(result, dict):
            return bool(result.get("exists"))
        return bool(result)

    def _read_text(self, path: str) -> str | None:
        try:
            content = self._rpc_request("read", {"path": path})
        except NexusRemoteError as exc:
            lowered = str(exc).lower()
            if "not found" in lowered or "file_not_found" in lowered:
                return None
            raise
        if content is None:
            return ""
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace")
        if isinstance(content, dict):
            value = content.get("content")
            if value is None:
                return ""
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return str(value)
        return str(content)

    def _read_bytes(self, path: str) -> bytes:
        content = self._rpc_request("read", {"path": path})
        if isinstance(content, bytes):
            return content
        if isinstance(content, dict):
            value = content.get("content")
            if isinstance(value, bytes):
                return value
            if isinstance(value, str):
                return value.encode("utf-8")
        if isinstance(content, str):
            return content.encode("utf-8")
        raise NexusRemoteError(f"Unexpected RPC read payload for {path}: {type(content).__name__}")

    def _read_json(self, path: str) -> dict[str, Any] | None:
        content = self._read_text(path)
        if content is None:
            return None
        if not content.strip():
            return {}
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise NexusRemoteError(f"Expected JSON object at {path}")
        return payload

    def _notify_search_refresh(self, path: str, change_type: str = "update") -> None:
        try:
            self._request(
                "POST",
                "/api/v2/search/refresh",
                params={"path": path, "change_type": change_type},
                expected_statuses={200, 202, 503},
            )
        except NexusRemoteError:
            return

    def _index_search_document(self, package: PackageRecord, document_text: str) -> bool:
        """Prefer explicit indexing for synthetic package search documents.

        Falls back to refresh-based indexing when the remote Nexus does not yet
        implement ``/api/v2/search/index`` correctly.
        """
        try:
            self._request(
                "POST",
                "/api/v2/search/index",
                json_body={
                    "documents": [
                        {
                            "id": package.search_document_path,
                            "path": package.search_document_path,
                            "text": document_text,
                        }
                    ]
                },
            )
            return True
        except NexusRemoteError as exc:
            logger.debug(
                "Explicit Nexus search indexing failed for %s, falling back to refresh: %s",
                package.versioned_key,
                exc,
            )
            return False

    def _metadata_fallback_hits(
        self,
        packages: list[PackageRecord],
        query: str,
    ) -> list[PackageSearchHit]:
        lowered = query.lower()
        fallback_hits: list[PackageSearchHit] = []
        for package in packages:
            haystack = "\n".join(
                [
                    package.manifest.publisher,
                    package.manifest.name,
                    package.manifest.version,
                    package.manifest.description,
                    *package.manifest.capabilities_requested,
                    *package.artifact_files,
                ]
            ).lower()
            if lowered not in haystack:
                continue
            fallback_hits.append(
                PackageSearchHit(
                    package=package,
                    score=1.0,
                    snippet=package.manifest.description,
                    backend="metadata_fallback",
                    matched_path=package.search_document_path,
                )
            )
        return fallback_hits

    def _query_search_results(
        self,
        query: str,
        *,
        limit: int,
        mode: str,
        path: str,
    ) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            "/api/v2/search/query",
            params={
                "q": query,
                "type": mode,
                "limit": str(limit),
                "path": path,
            },
        )
        payload = self._json_or_empty(response)
        results = payload.get("results", [])
        return [item for item in results if isinstance(item, dict)]

    def _search_hits_from_results(
        self,
        results: list[dict[str, Any]],
        package_map: dict[tuple[str, str, str], PackageRecord],
    ) -> list[PackageSearchHit]:
        hits: list[PackageSearchHit] = []
        seen: set[str] = set()
        for result in results:
            matched_path = str(result.get("path", ""))
            parts = PurePosixPath(
                matched_path.removeprefix(f"{self.catalog_search_root}/")
            ).parts
            if len(parts) != 4 or parts[-1] != "document.md":
                continue
            key = (parts[0], parts[1], parts[2])
            package = package_map.get(key)
            if package is None or package.versioned_key in seen:
                continue
            seen.add(package.versioned_key)
            hits.append(
                PackageSearchHit(
                    package=package,
                    score=float(result["score"]) if result.get("score") is not None else None,
                    snippet=str(result.get("chunk_text", "")),
                    backend="nexus_search",
                    matched_path=matched_path,
                )
            )
        return hits

    def _search_document_is_queryable(self, package: PackageRecord) -> bool:
        readiness_queries = (
            (package.versioned_key, "keyword"),
            (package.manifest.name, "keyword"),
            (package.manifest.name, "semantic"),
        )
        for query, mode in readiness_queries:
            try:
                results = self._query_search_results(
                    query,
                    limit=1,
                    mode=mode,
                    path=package.search_document_path,
                )
            except NexusRemoteError:
                continue
            if any(str(item.get("path", "")) == package.search_document_path for item in results):
                return True
        return False

    def _wait_for_search_visibility(self, package: PackageRecord) -> None:
        deadline = time.monotonic() + self._SEARCH_PUBLISH_WAIT_TIMEOUT_SECONDS
        while True:
            if self._search_document_is_queryable(package):
                return
            if time.monotonic() >= deadline:
                logger.debug(
                    "Search document was not queryable before publish returned: %s",
                    package.versioned_key,
                )
                return
            time.sleep(self._SEARCH_PUBLISH_WAIT_POLL_SECONDS)

    def _read_package_index(self) -> list[PackageRecord]:
        payload = self._read_json(self.package_index_path)
        if not payload:
            return []
        return [
            PackageRecord.model_validate(item)
            for item in payload.get("packages", [])
            if isinstance(item, dict)
        ]

    def _write_package_index(self, packages: list[PackageRecord]) -> None:
        ordered = sorted(packages, key=lambda item: item.versioned_key)
        self._write_json(
            self.package_index_path,
            {"packages": [package.model_dump(mode="json") for package in ordered]},
        )

    def _read_installation_index(self) -> list[InstallationRecord]:
        payload = self._read_json(self.installation_index_path)
        if not payload:
            return []
        return [
            InstallationRecord.model_validate(item)
            for item in payload.get("installations", [])
            if isinstance(item, dict)
        ]

    def _write_installation_index(self, installations: list[InstallationRecord]) -> None:
        ordered = sorted(installations, key=lambda item: item.created_at)
        self._write_json(
            self.installation_index_path,
            {"installations": [item.model_dump(mode="json") for item in ordered]},
        )

    def build_search_document(
        self,
        package: PackageRecord,
        package_files: list[LocalPackageFile] | None = None,
    ) -> str:
        """Build the search document indexed by Nexus semantic search."""
        files_by_path = {item.relative_path: item for item in package_files or []}
        sections = [
            f"# {package.versioned_key}",
            f"publisher: {package.manifest.publisher}",
            f"name: {package.manifest.name}",
            f"version: {package.manifest.version}",
            f"type: {package.manifest.type}",
            f"description: {package.manifest.description}",
            f"risk_level: {package.manifest.risk_level}",
        ]
        if package.manifest.capabilities_requested:
            sections.append(
                "capabilities: " + ", ".join(package.manifest.capabilities_requested)
            )
        if package.artifact_files:
            sections.append("files: " + ", ".join(package.artifact_files))

        skill_path = package.manifest.files.skill_doc
        skill_file = files_by_path.get(skill_path)
        if skill_file is not None:
            sections.extend(["", "## SKILL.md", skill_file.absolute_path.read_text()])

        for reference in package.manifest.files.references:
            reference_file = files_by_path.get(reference)
            if reference_file is None:
                continue
            sections.extend(["", f"## {reference}", reference_file.absolute_path.read_text()])

        return "\n".join(sections).strip() + "\n"

    def publish_package(
        self,
        package: PackageRecord,
        package_files: list[LocalPackageFile] | None = None,
    ) -> PackageRecord:
        """Publish package metadata and optional local artifact files into Nexus."""
        artifact_root = self._artifact_root_path(package)
        artifact_files = list(package.artifact_files)
        if package_files:
            artifact_files = [item.relative_path for item in package_files]
            for package_file in package_files:
                self._write_file(
                    f"{artifact_root}/{package_file.relative_path}",
                    package_file.absolute_path.read_bytes(),
                )
            self._write_json(
                self._artifact_index_path(package),
                {
                    "package_key": package.versioned_key,
                    "artifact_digest": package.artifact_digest,
                    "files": artifact_files,
                    "source_uri": package.source_uri,
                },
            )

        stored = package.model_copy(
            update={
                "artifact_uri": f"nexus://{artifact_root}",
                "artifact_files": artifact_files,
                "catalog_record_path": self._package_record_path(
                    package.manifest.publisher,
                    package.manifest.name,
                    package.manifest.version,
                ),
                "search_document_path": self._package_search_document_path(
                    package.manifest.publisher,
                    package.manifest.name,
                    package.manifest.version,
                ),
            }
        )

        search_document = self.build_search_document(stored, package_files)
        self._write_text(
            stored.search_document_path,
            search_document,
        )
        self._write_json(stored.catalog_record_path, stored.model_dump(mode="json"))

        packages = [
            item for item in self._read_package_index() if item.versioned_key != stored.versioned_key
        ]
        packages.append(stored)
        self._write_package_index(packages)
        if not self._index_search_document(stored, search_document):
            self._notify_search_refresh(stored.search_document_path, "create")
        self._notify_search_refresh(stored.catalog_record_path, "create")
        self._wait_for_search_visibility(stored)
        return stored

    def upsert_installation(self, installation: InstallationRecord) -> InstallationRecord:
        """Persist an installation record into Nexus."""
        path = self._installation_path(installation.id)
        self._write_json(path, installation.model_dump(mode="json"))
        installations = [
            item for item in self._read_installation_index() if item.id != installation.id
        ]
        installations.append(installation)
        self._write_installation_index(installations)
        return installation

    def list_packages(self) -> list[PackageRecord]:
        """List all catalog packages from Nexus."""
        return self._read_package_index()

    def get_package(self, publisher: str, name: str, version: str) -> PackageRecord | None:
        """Read one package version from the Nexus catalog."""
        payload = self._read_json(self._package_record_path(publisher, name, version))
        if payload is None:
            return None
        return PackageRecord.model_validate(payload)

    def list_installations(self) -> list[InstallationRecord]:
        """List all installation records from Nexus."""
        return self._read_installation_index()

    def get_installation(self, installation_id: str) -> InstallationRecord | None:
        """Read one installation from Nexus."""
        payload = self._read_json(self._installation_path(installation_id))
        if payload is None:
            return None
        return InstallationRecord.model_validate(payload)

    def _artifact_root_from_uri(self, package: PackageRecord) -> str:
        if package.artifact_uri.startswith("nexus://"):
            return package.artifact_uri.removeprefix("nexus://")
        return ""

    def get_package_artifact_content(self, package: PackageRecord, relative_path: str) -> str:
        """Read one text file from the Nexus-backed package artifact."""
        content = self.get_package_artifact_bytes(package, relative_path)
        return content.decode("utf-8", errors="replace")

    def get_package_artifact_bytes(self, package: PackageRecord, relative_path: str) -> bytes:
        """Read one file from the Nexus-backed package artifact."""
        normalized = PurePosixPath(relative_path).as_posix()
        if normalized not in package.artifact_files:
            raise NexusRemoteError(
                f"Package artifact does not declare file: {relative_path}"
            )
        artifact_root = self._artifact_root_from_uri(package)
        if not artifact_root:
            raise NexusRemoteError("Package artifact is not stored in Nexus")
        content = self._read_bytes(f"{artifact_root}/{normalized}")
        if content is None:
            raise NexusRemoteError(f"Artifact file missing from Nexus: {normalized}")
        return content

    def search_packages(
        self,
        query: str,
        *,
        limit: int = 10,
        mode: str = "hybrid",
    ) -> tuple[str, list[PackageSearchHit]]:
        """Search the package catalog, preferring Nexus semantic search."""
        packages = self._read_package_index()
        package_map = {
            (item.manifest.publisher, item.manifest.name, item.manifest.version): item
            for item in packages
        }
        fallback_hits = self._metadata_fallback_hits(packages, query)
        search_delays = (
            self._SEARCH_RETRY_DELAYS_SECONDS if fallback_hits else self._SEARCH_RETRY_DELAYS_SECONDS[:1]
        )

        for delay in search_delays:
            if delay:
                time.sleep(delay)
            try:
                results = self._query_search_results(
                    query,
                    limit=limit,
                    mode=mode,
                    path=self.catalog_search_root,
                )
            except NexusRemoteError as exc:
                logger.debug("Nexus search failed, retrying before fallback: %s", exc)
                continue
            hits = self._search_hits_from_results(results, package_map)
            if hits:
                return ("nexus_search", hits[:limit])

        return ("metadata_fallback", fallback_hits[:limit])

    def build_install_plan(
        self,
        package: PackageRecord,
        target: InstallTarget,
        scope_id: str,
    ) -> InstallPlan:
        """Build the concrete remote install plan for a package."""
        nexus_target_path = self._target_path(package, target, scope_id)
        artifact_root = self._artifact_root_from_uri(package)
        artifact_files = tuple(package.artifact_files)
        materialized_files = tuple(f"{nexus_target_path}/{item}" for item in artifact_files)
        return InstallPlan(
            package_key=package.versioned_key,
            steps=(
                "probe_remote_health",
                "read_catalog_artifact",
                "create_install_root",
                "write_install_files",
                "verify_remote_target",
                "record_installation",
            ),
            nexus_target_path=nexus_target_path,
            source_artifact_root=artifact_root,
            source_files=artifact_files,
            materialized_files=materialized_files,
        )

    def preview_install(
        self,
        package: PackageRecord,
        target: InstallTarget,
        scope_id: str,
    ) -> InstallPreview:
        """Return the resolved install preview."""
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

    def apply_install_plan(self, plan: InstallPlan) -> list[str]:
        """Materialize catalog artifact files into the install target."""
        if not plan.source_artifact_root or not plan.source_files:
            raise NexusRemoteError(
                "Package is not published into the Nexus catalog yet. "
                "Register it through the Nexus-backed catalog first."
            )

        health = self.probe_remote()
        if not health.reachable:
            raise NexusRemoteError(
                f"Remote Nexus is unreachable at {self._settings.nexus_base_url}: {health.detail or 'unknown error'}"
            )

        self._mkdir(plan.nexus_target_path)
        written_paths: list[str] = []
        for relative_path in plan.source_files:
            source_path = f"{plan.source_artifact_root}/{relative_path}"
            target_path = f"{plan.nexus_target_path}/{relative_path}"
            self._write_file(target_path, self._read_bytes(source_path))
            written_paths.append(target_path)
            self._notify_search_refresh(target_path, "create")

        for written_path in written_paths:
            if not self._exists(written_path):
                raise NexusRemoteError(f"Nexus did not report installed file: {written_path}")
        return written_paths
