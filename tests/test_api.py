from fastapi.testclient import TestClient

import skillhub.api as api_module
from skillhub.service import SkillHubService


def _fresh_client() -> TestClient:
    api_module.service = SkillHubService()
    return TestClient(api_module.app)


def _register_local_example(client: TestClient) -> None:
    response = client.post(
        "/v1/packages/register-local",
        json={"source_dir": "examples/hello-skill"},
    )
    assert response.status_code == 201


def test_get_nexus_remote_status() -> None:
    client = _fresh_client()
    response = client.get("/v1/nexus")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "remote_http_backed"
    assert payload["health_url"].endswith("/health")
    assert payload["files_api_base"].endswith("/api/v2/files")


def test_register_local_package() -> None:
    client = _fresh_client()
    response = client.post(
        "/v1/packages/register-local",
        json={"source_dir": "examples/hello-skill"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["package"]["manifest"]["name"] == "hello-skill"
    assert payload["package"]["artifact_uri"].startswith("file://")
    assert payload["package"]["artifact_digest"].startswith("sha256:")


def test_install_preview_returns_materialized_files() -> None:
    client = _fresh_client()
    _register_local_example(client)
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
    assert payload["materialized_files"] == [
        "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/skillhub.yaml",
        "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/SKILL.md",
        "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/references/quickstart.md",
    ]


def test_install_materializes_declared_files(monkeypatch) -> None:
    client = _fresh_client()
    _register_local_example(client)

    def _fake_apply_install_plan(plan):
        return list(plan.materialized_files)

    monkeypatch.setattr(api_module.service.nexus, "apply_install_plan", _fake_apply_install_plan)

    response = client.post(
        "/v1/installations",
        json={
            "publisher": "nexi-lab",
            "name": "hello-skill",
            "version": "0.1.0",
            "target": "user",
            "scope_id": "demo-user",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["installation"]["status"] == "installed"
    assert payload["installation"]["source_artifact_uri"].startswith("file://")
    assert payload["installation"]["materialized_files"] == [
        "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/skillhub.yaml",
        "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/SKILL.md",
        "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/references/quickstart.md",
    ]
