import httpx

from skillhub.models import PackageRecord, PackageType, SkillManifest
from skillhub.nexus_adapter import NexusAdapter
from skillhub.nexus_adapter import NexusRemoteError
from skillhub.settings import Settings


def _adapter() -> NexusAdapter:
    return NexusAdapter(
        Settings(
            nexus_base_url="http://localhost:2026",
            nexus_api_key="sk-dev-skillhub-admin-1234567890abcdef",
            nexus_install_root="/skills",
            nexus_catalog_root="/skill-hub",
            nexus_timeout_seconds=5.0,
        )
    )


def _package() -> PackageRecord:
    manifest = SkillManifest(
        name="hello-skill",
        publisher="nexi-lab",
        version="0.1.0",
        type=PackageType.PROMPT_PACK,
        description="Minimal example package for the skill-hub Phase 1 scaffold.",
        capabilities_requested=["read_skill_docs"],
    )
    return PackageRecord(
        manifest=manifest,
        artifact_uri="nexus:///skill-hub/artifacts/nexi-lab/hello-skill/0.1.0",
        artifact_files=["skillhub.yaml", "SKILL.md", "references/quickstart.md"],
        search_document_path="/skill-hub/search/nexi-lab/hello-skill/0.1.0/document.md",
    )


def test_mkdir_uses_rpc_endpoint(monkeypatch) -> None:
    adapter = _adapter()
    calls: list[tuple[str, dict[str, object] | None]] = []

    def _fake_rpc(method: str, params: dict[str, object] | None = None) -> dict[str, object]:
        calls.append((method, params))
        return {}

    monkeypatch.setattr(adapter, "_rpc_request", _fake_rpc)

    adapter._mkdir("/skill-hub/index")

    assert calls == [
        ("mkdir", {"path": "/skill-hub/index", "parents": True, "exist_ok": True})
    ]


def test_write_file_uses_rpc_for_text(monkeypatch) -> None:
    adapter = _adapter()
    calls: list[tuple[str, dict[str, object] | None]] = []

    monkeypatch.setattr(adapter, "_ensure_parent_directory", lambda path: None)

    def _fake_rpc(method: str, params: dict[str, object] | None = None) -> dict[str, object]:
        calls.append((method, params))
        return {}

    monkeypatch.setattr(adapter, "_rpc_request", _fake_rpc)

    adapter._write_file("/skill-hub/index/packages.json", b"hello")

    assert calls == [
        ("write", {"path": "/skill-hub/index/packages.json", "content": "hello"})
    ]


def test_write_file_base64_encodes_binary(monkeypatch) -> None:
    adapter = _adapter()
    calls: list[tuple[str, dict[str, object] | None]] = []

    monkeypatch.setattr(adapter, "_ensure_parent_directory", lambda path: None)

    def _fake_rpc(method: str, params: dict[str, object] | None = None) -> dict[str, object]:
        calls.append((method, params))
        return {}

    monkeypatch.setattr(adapter, "_rpc_request", _fake_rpc)

    adapter._write_file("/skill-hub/artifacts/blob.bin", b"\xff\x00")

    assert calls == [
        (
            "write",
            {
                "path": "/skill-hub/artifacts/blob.bin",
                "content": {"__type__": "bytes", "data": "/wA="},
            },
        )
    ]


def test_read_text_decodes_rpc_bytes(monkeypatch) -> None:
    adapter = _adapter()

    monkeypatch.setattr(adapter, "_rpc_request", lambda method, params=None: b"hello")

    assert adapter._read_text("/skill-hub/packages.json") == "hello"


def test_search_packages_retries_after_transient_nexus_error(monkeypatch) -> None:
    adapter = _adapter()
    package = _package()
    calls = {"count": 0}

    monkeypatch.setattr(adapter, "_read_package_index", lambda: [package])
    monkeypatch.setattr("skillhub.nexus_adapter.time.sleep", lambda seconds: None)

    def _fake_request(method, path, *, json_body=None, params=None, expected_statuses=None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise NexusRemoteError("Nexus GET /api/v2/search/query failed (500): Search query failed")
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "path": package.search_document_path,
                        "chunk_text": "# Hello Skill",
                        "score": 0.42,
                    }
                ]
            },
        )

    monkeypatch.setattr(adapter, "_request", _fake_request)

    backend, hits = adapter.search_packages("hello", limit=5, mode="hybrid")

    assert backend == "nexus_search"
    assert calls["count"] == 2
    assert hits[0].package.manifest.name == "hello-skill"
    assert hits[0].backend == "nexus_search"


def test_search_packages_retries_after_empty_results_when_metadata_matches(monkeypatch) -> None:
    adapter = _adapter()
    package = _package()
    calls = {"count": 0}

    monkeypatch.setattr(adapter, "_read_package_index", lambda: [package])
    monkeypatch.setattr("skillhub.nexus_adapter.time.sleep", lambda seconds: None)

    def _fake_request(method, path, *, json_body=None, params=None, expected_statuses=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(200, json={"results": []})
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "path": package.search_document_path,
                        "chunk_text": "# Hello Skill",
                        "score": 0.84,
                    }
                ]
            },
        )

    monkeypatch.setattr(adapter, "_request", _fake_request)

    backend, hits = adapter.search_packages("hello", limit=5, mode="hybrid")

    assert backend == "nexus_search"
    assert calls["count"] == 2
    assert hits[0].matched_path == package.search_document_path


def test_search_document_is_queryable_requires_exact_document(monkeypatch) -> None:
    adapter = _adapter()
    package = _package()

    def _fake_query(query, *, limit, mode, path):
        assert path == package.search_document_path
        return [
            {
                "path": "/skill-hub/search/nexi-lab/other-skill/0.1.0/document.md",
                "score": 0.9,
                "chunk_text": "# Other Skill",
            }
        ]

    monkeypatch.setattr(adapter, "_query_search_results", _fake_query)

    assert adapter._search_document_is_queryable(package) is False


def test_wait_for_search_visibility_retries_until_exact_document_queryable(monkeypatch) -> None:
    adapter = _adapter()
    package = _package()
    attempts = {"count": 0}
    clock = {"value": 100.0}

    def _fake_is_queryable(candidate: PackageRecord) -> bool:
        assert candidate == package
        attempts["count"] += 1
        return attempts["count"] >= 3

    def _fake_sleep(seconds: float) -> None:
        clock["value"] += seconds

    monkeypatch.setattr(adapter, "_search_document_is_queryable", _fake_is_queryable)
    monkeypatch.setattr("skillhub.nexus_adapter.time.sleep", _fake_sleep)
    monkeypatch.setattr("skillhub.nexus_adapter.time.monotonic", lambda: clock["value"])

    adapter._wait_for_search_visibility(package)

    assert attempts["count"] == 3


def test_index_search_document_uses_explicit_index_api(monkeypatch) -> None:
    adapter = _adapter()
    package = _package()
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def _fake_request(method, path, *, json_body=None, params=None, expected_statuses=None):
        calls.append((method, path, json_body))
        return httpx.Response(200, json={"status": "indexed", "count": 1})

    monkeypatch.setattr(adapter, "_request", _fake_request)

    indexed = adapter._index_search_document(package, "# Hello Skill\n")

    assert indexed is True
    assert calls == [
        (
            "POST",
            "/api/v2/search/index",
            {
                "documents": [
                    {
                        "id": package.search_document_path,
                        "path": package.search_document_path,
                        "text": "# Hello Skill\n",
                    }
                ]
            },
        )
    ]


def test_index_search_document_falls_back_when_explicit_indexing_fails(monkeypatch) -> None:
    adapter = _adapter()
    package = _package()

    def _fake_request(method, path, *, json_body=None, params=None, expected_statuses=None):
        raise NexusRemoteError("Nexus POST /api/v2/search/index failed (500): Search index failed")

    monkeypatch.setattr(adapter, "_request", _fake_request)

    indexed = adapter._index_search_document(package, "# Hello Skill\n")

    assert indexed is False
