# Phase 1 API

## Base URL

Local development:

```text
http://127.0.0.1:8040
```

OpenAPI:

- `/docs`
- `/redoc`
- `/openapi.json`

## Design Notes

Phase 1 has two package registration paths:

- `POST /v1/packages/register`
  Use this when another system already owns the manifest payload.
- `POST /v1/packages/register-local`
  Use this when `skill-hub` should read `skillhub.yaml` from a local package directory.

The remote Nexus integration is live in Phase 1:

- preview resolves target paths and remote files
- install writes the declared package files into Nexus

## Nexus Routes

### `GET /health`

Service liveness for `skill-hub`.

Example response:

```json
{
  "status": "ok"
}
```

### `GET /v1/nexus`

Returns the effective remote Nexus configuration.

Example response:

```json
{
  "mode": "remote_http_backed",
  "base_url": "http://127.0.0.1:2026",
  "api_key_configured": true,
  "install_root": "/skills",
  "health_url": "http://127.0.0.1:2026/health",
  "files_api_base": "http://127.0.0.1:2026/api/v2/files"
}
```

### `GET /v1/nexus/health`

Probes remote Nexus health.

Example response:

```json
{
  "nexus": {
    "reachable": true,
    "status": "ok",
    "service": "nexus-rpc",
    "http_status": 200,
    "detail": null
  }
}
```

## Package Routes

### `GET /v1/packages`

Lists all registered package versions.

### `POST /v1/packages/register`

Registers a package version from an explicit manifest payload.

Example request:

```json
{
  "manifest": {
    "schema_version": "1",
    "name": "hello-skill",
    "publisher": "nexi-lab",
    "version": "0.1.0",
    "type": "prompt_pack",
    "description": "Minimal Phase 1 example package.",
    "nexus_version": ">=0.1.0",
    "install_target": "user",
    "capabilities_requested": ["read_skill_docs"],
    "risk_level": "low",
    "credentials": [],
    "permissions": [],
    "files": {
      "skill_doc": "SKILL.md",
      "references": ["references/quickstart.md"],
      "examples": [],
      "assets": []
    },
    "entrypoints": {
      "scripts": [],
      "workflows": [],
      "mcp_servers": []
    }
  },
  "artifact_uri": "file:///absolute/path/to/hello-skill",
  "artifact_digest": "sha256:..."
}
```

### `POST /v1/packages/register-local`

Registers a package version from a local directory.

Example request:

```json
{
  "source_dir": "examples/hello-skill"
}
```

Example response:

```json
{
  "package": {
    "manifest": {
      "schema_version": "1",
      "name": "hello-skill",
      "publisher": "nexi-lab",
      "version": "0.1.0",
      "type": "prompt_pack",
      "description": "Minimal example package for the skill-hub Phase 1 scaffold.",
      "nexus_version": ">=0.1.0",
      "install_target": "user",
      "capabilities_requested": ["read_skill_docs"],
      "risk_level": "low",
      "credentials": [],
      "permissions": [],
      "files": {
        "skill_doc": "SKILL.md",
        "references": ["references/quickstart.md"],
        "examples": [],
        "assets": []
      },
      "entrypoints": {
        "scripts": [],
        "workflows": [],
        "mcp_servers": []
      }
    },
    "artifact_uri": "file:///absolute/path/to/examples/hello-skill",
    "artifact_digest": "sha256:...",
    "created_at": "2026-03-11T00:00:00Z"
  }
}
```

### `GET /v1/packages/{publisher}/{name}`

Lists all known versions for one package key.

### `GET /v1/packages/{publisher}/{name}/{version}`

Returns one specific package version.

## Installation Routes

### `POST /v1/installations/preview`

Resolves where a registered package will land in Nexus and which files will be written.

Example request:

```json
{
  "publisher": "nexi-lab",
  "name": "hello-skill",
  "version": "0.1.0",
  "target": "user",
  "scope_id": "demo-user"
}
```

Example response:

```json
{
  "package_key": "nexi-lab/hello-skill@0.1.0",
  "target": "user",
  "scope_id": "demo-user",
  "nexus_base_url": "http://127.0.0.1:2026",
  "nexus_target_path": "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0",
  "steps": [
    "probe_remote_health",
    "create_install_root",
    "write_package_files",
    "verify_remote_target",
    "record_installation"
  ],
  "capabilities_requested": ["read_skill_docs"],
  "materialized_files": [
    "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/skillhub.yaml",
    "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/SKILL.md",
    "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/references/quickstart.md"
  ]
}
```

### `POST /v1/installations`

Installs a registered package into remote Nexus.

Current Phase 1 behavior:

- creates the target directory in Nexus
- writes the declared files
- verifies the written files with `exists`
- records the install

Example response:

```json
{
  "installation": {
    "id": "2cb09d80-1b48-4f45-b6a6-8a934c3db111",
    "package_key": "nexi-lab/hello-skill@0.1.0",
    "target": "user",
    "scope_id": "demo-user",
    "nexus_base_url": "http://127.0.0.1:2026",
    "nexus_target_path": "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0",
    "source_artifact_uri": "file:///absolute/path/to/examples/hello-skill",
    "materialized_files": [
      "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/skillhub.yaml",
      "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/SKILL.md",
      "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/references/quickstart.md"
    ],
    "status": "installed",
    "created_at": "2026-03-11T00:00:00Z"
  }
}
```

### `GET /v1/installations`

Lists installation records.

### `GET /v1/installations/{installation_id}`

Returns one installation record.

## Phase 1 Stability Contract

The following are intended to remain stable through the rest of Phase 1:

- `skillhub.yaml` schema version `1`
- package key format: `publisher/name@version`
- target scopes: `system`, `zone`, `user`, `agent`
- Nexus target path conventions under `/skills/...`
- the endpoints listed in this document
