# Phase 1 API

## Base URL

Local:

```text
http://127.0.0.1:8040
```

OpenAPI:

- `/docs`
- `/redoc`
- `/openapi.json`

## Nexus Status

### `GET /health`

Liveness for `skill-hub`.

### `GET /v1/nexus`

Returns the effective Nexus integration settings.

Example response:

```json
{
  "mode": "remote_http_backed",
  "base_url": "http://nexus:2026",
  "api_key_configured": true,
  "install_root": "/skills",
  "catalog_root": "/skill-hub",
  "health_url": "http://nexus:2026/health",
  "files_api_base": "http://nexus:2026/api/v2/files",
  "search_api_base": "http://nexus:2026/api/v2/search"
}
```

### `GET /v1/nexus/health`

Probes the configured Nexus instance.

## Packages

### `GET /v1/packages`

Lists all published package versions.

### `GET /v1/packages/search`

Searches the published package catalog.

Query params:

- `q`
- `limit`
- `mode`

Example:

```text
GET /v1/packages/search?q=hello&limit=5&mode=hybrid
```

Example response:

```json
{
  "query": "hello",
  "backend": "nexus_search",
  "hits": [
    {
      "package": {
        "manifest": {
          "name": "hello-skill",
          "publisher": "nexi-lab",
          "version": "0.1.0",
          "type": "prompt_pack"
        },
        "artifact_uri": "nexus:///skill-hub/artifacts/nexi-lab/hello-skill/0.1.0",
        "source_uri": "file:///workspace/examples/hello-skill",
        "artifact_digest": "sha256:...",
        "artifact_files": [
          "skillhub.yaml",
          "SKILL.md",
          "references/quickstart.md"
        ]
      },
      "score": 0.92,
      "snippet": "Use this skill when you want a minimal example...",
      "backend": "nexus_search",
      "matched_path": "/skill-hub/search/nexi-lab/hello-skill/0.1.0/document.md"
    }
  ]
}
```

### `POST /v1/packages/register`

Registers a package record from an explicit manifest payload.

This is metadata-oriented. If the artifact is not already in Nexus, later installs may not succeed.

### `POST /v1/packages/register-local`

Publishes a local package into the Nexus-backed catalog.

Example request:

```json
{
  "source_dir": "/workspace/examples/hello-skill"
}
```

This endpoint:

- validates manifest and declared files
- writes package artifact files to Nexus
- writes package metadata to Nexus
- writes a search document to Nexus
- updates the package index in Nexus

### `GET /v1/packages/{publisher}/{name}`

Lists all versions for one package key.

### `GET /v1/packages/{publisher}/{name}/{version}`

Returns one package record.

### `GET /v1/packages/{publisher}/{name}/{version}/artifact`

Returns artifact metadata:

- package record
- artifact root URI
- declared artifact files

### `GET /v1/packages/{publisher}/{name}/{version}/content?path=...`

Reads one published artifact file from Nexus.

Example:

```text
GET /v1/packages/nexi-lab/hello-skill/0.1.0/content?path=SKILL.md
```

## Installations

### `POST /v1/installations/preview`

Builds an install plan from the published Nexus artifact store into `/skills/...`.

Example response:

```json
{
  "package_key": "nexi-lab/hello-skill@0.1.0",
  "target": "user",
  "scope_id": "demo-user",
  "nexus_base_url": "http://nexus:2026",
  "nexus_target_path": "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0",
  "steps": [
    "probe_remote_health",
    "read_catalog_artifact",
    "create_install_root",
    "write_install_files",
    "verify_remote_target",
    "record_installation"
  ],
  "materialized_files": [
    "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/skillhub.yaml",
    "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/SKILL.md",
    "/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/references/quickstart.md"
  ]
}
```

### `POST /v1/installations`

Installs a published package by copying its files from the Nexus catalog artifact store into `/skills/...`.

### `GET /v1/installations`

Lists installation records.

### `GET /v1/installations/{installation_id}`

Returns one installation record.

## Stability Contract

Phase 1 is intended to keep these stable:

- `skillhub.yaml` schema version `1`
- package key format: `publisher/name@version`
- catalog root conventions under `/skill-hub/...`
- install target conventions under `/skills/...`
- the package and installation routes listed here
