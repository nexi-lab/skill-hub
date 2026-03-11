from fastapi.testclient import TestClient

from skillhub.api import app, service
from skillhub.manifest import load_manifest
from skillhub.models import PackageRegistrationRequest


client = TestClient(app)


def _register_example() -> None:
    manifest = load_manifest("examples/hello-skill/skillhub.yaml")
    service.register_package(
        PackageRegistrationRequest(
            manifest=manifest,
            artifact_uri="file://examples/hello-skill",
            artifact_digest="sha256:test-example",
        )
    )


def test_get_nexus_remote_status() -> None:
    response = client.get("/v1/nexus")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "remote_namespace_backed"
    assert "base_url" in payload
    assert "install_root" in payload


def test_install_preview_returns_nexus_target_path() -> None:
    _register_example()
    response = client.post(
        "/v1/installations/preview",
        json={
            "publisher": "nexi-lab",
            "name": "hello-skill",
            "version": "0.1.0",
            "target": "user",
            "scope_id": "demo-user",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["package_key"] == "nexi-lab/hello-skill@0.1.0"
    assert payload["nexus_target_path"] == "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0"


def test_get_specific_package_version() -> None:
    _register_example()
    response = client.get("/v1/packages/nexi-lab/hello-skill/0.1.0")
    assert response.status_code == 200
    payload = response.json()
    assert payload["package"]["manifest"]["name"] == "hello-skill"
    assert payload["package"]["manifest"]["version"] == "0.1.0"
