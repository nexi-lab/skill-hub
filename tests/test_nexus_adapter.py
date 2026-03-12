from skillhub.nexus_adapter import NexusAdapter
from skillhub.settings import Settings


def _adapter() -> NexusAdapter:
    return NexusAdapter(
        Settings(
            nexus_base_url="http://localhost:2026",
            nexus_api_key="dev-key",
            nexus_install_root="/skills",
            nexus_catalog_root="/skill-hub",
            nexus_timeout_seconds=5.0,
        )
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
