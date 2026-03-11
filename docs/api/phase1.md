# Phase 1 API

## Base URL

Local development:

```text
http://127.0.0.1:8040
```

## OpenAPI

- `/docs`
- `/redoc`
- `/openapi.json`

## Endpoints

### `GET /health`

Returns service liveness.

Example response:

```json
{
  "status": "ok"
}
```

### `GET /v1/nexus`

Returns the effective remote Nexus configuration used for install planning.

Example response:

```json
{
  "mode": "remote_namespace_backed",
  "base_url": "http://localhost:2026",
  "api_key_configured": true,
  "install_root": "/skills"
}
```

### `GET /v1/packages`

Lists all registered package versions.

Example response:

```json
{
  "packages": []
}
```

### `POST /v1/packages/register`

Registers a new package version.

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
  "artifact_uri": "file://examples/hello-skill",
  "artifact_digest": "sha256:phase1-example"
}
```

### `GET /v1/packages/{publisher}/{name}`

Lists all known versions for one package key.

Example:

```text
GET /v1/packages/nexi-lab/hello-skill
```

### `GET /v1/packages/{publisher}/{name}/{version}`

Returns one specific package version.

Example:

```text
GET /v1/packages/nexi-lab/hello-skill/0.1.0
```

### `POST /v1/installations/preview`

Resolves where a package would land inside the remote Nexus namespace.

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
  "nexus_base_url": "http://localhost:2026",
  "nexus_target_path": "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0",
  "steps": [
    "resolve_remote_namespace",
    "materialize_skill_docs",
    "record_installation"
  ],
  "capabilities_requested": ["read_skill_docs"]
}
```

### `POST /v1/installations`

Records an install against a scope.

It currently records the resolved target path; it does not yet execute remote Nexus mutations.

### `GET /v1/installations`

Lists recorded installs.

## Phase 1 Stability Contract

The following are intended to remain stable across the rest of Phase 1:

- `skillhub.yaml` schema version `1`
- package key format: `publisher/name@version`
- target scopes: `system`, `zone`, `user`, `agent`
- remote Nexus namespace path conventions
- API routes listed in this document
