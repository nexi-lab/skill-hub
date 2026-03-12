# skill-hub

Nexus-backed skill catalog, package publishing, search, and installation for `SKILL.md` packages.

## One-Liner

`skill-hub` publishes a local `SKILL.md` package into Nexus, makes it searchable, and installs it into `/skills/...` through a clean API.

## What Works Today

Phase 1 is now genuinely Nexus-backed.

- publish a local package into a Nexus-backed catalog
- persist package metadata and package files inside Nexus
- retrieve package metadata and package content through `skill-hub`
- search the published package catalog, using Nexus search when available
- install published packages into `system`, `zone`, `user`, or `agent` scopes
- run the full stack with Docker: Postgres + Nexus + `skill-hub`

What is still out of scope:

- workflow execution
- MCP runtime materialization
- credential binding
- enforceable permission manifests
- rollback and snapshots

## System Model

`skill-hub` is the control plane.

Nexus is the package store, search substrate, and install target.

Published package state lives in Nexus under:

- catalog metadata: `/skill-hub/packages/...`
- published artifacts: `/skill-hub/artifacts/...`
- search documents: `/skill-hub/search/...`
- installation records: `/skill-hub/installations/...`

Installed package contents land under:

- `/skills/system/packages/...`
- `/skills/zones/<zone_id>/...`
- `/skills/users/<user_id>/...`
- `/skills/agents/<agent_id>/...`

## API Surface

Current API:

- `GET /health`
- `GET /v1/nexus`
- `GET /v1/nexus/health`
- `GET /v1/packages`
- `GET /v1/packages/search`
- `POST /v1/packages/register`
- `POST /v1/packages/register-local`
- `GET /v1/packages/{publisher}/{name}`
- `GET /v1/packages/{publisher}/{name}/{version}`
- `GET /v1/packages/{publisher}/{name}/{version}/artifact`
- `GET /v1/packages/{publisher}/{name}/{version}/content?path=...`
- `POST /v1/installations/preview`
- `POST /v1/installations`
- `GET /v1/installations`
- `GET /v1/installations/{installation_id}`

OpenAPI:

- `/docs`
- `/redoc`

## CLI Surface

```bash
uv run skillhub nexus-info
uv run skillhub nexus-check
uv run skillhub register-local examples/hello-skill
uv run skillhub search-packages hello
uv run skillhub read-package-file nexi-lab hello-skill 0.1.0 SKILL.md
uv run skillhub preview-install examples/hello-skill --target user --scope-id demo-user
uv run skillhub install-local examples/hello-skill --target user --scope-id demo-user
uv run skillhub serve
```

## Quick Start: Docker E2E

This is the intended end-to-end path.

### 1. Start The Stack

If you want to use the published Nexus image:

```bash
docker compose -f compose.yaml up --build
```

If you are developing in a workspace that also has the Nexus repo checked out as the parent directory, build Nexus from local source:

```bash
docker compose -f compose.yaml -f compose.local.yaml up --build
```

The stack starts:

- `postgres` on the internal Docker network
- `nexus` on `http://localhost:2026`
- `skill-hub` on `http://localhost:8040`

Compose enables Nexus search and uses:

- `NEXUS_API_KEY=dev-key`
- `SKILLHUB_NEXUS_CATALOG_ROOT=/skill-hub`
- `SKILLHUB_NEXUS_INSTALL_ROOT=/skills`

### 2. Verify The Stack

```bash
curl -sS http://localhost:8040/health
curl -sS http://localhost:8040/v1/nexus
curl -sS http://localhost:8040/v1/nexus/health
```

### 3. Publish The Example Package

When using Docker, `register-local` must point at a path that exists inside the `skill-hub` container. The compose file mounts this repo’s `examples/` directory at `/workspace/examples`.

```bash
curl -sS -X POST http://localhost:8040/v1/packages/register-local \
  -H "content-type: application/json" \
  -d '{"source_dir":"/workspace/examples/hello-skill"}'
```

What this does:

- validates `skillhub.yaml`
- copies declared package files into Nexus under `/skill-hub/artifacts/...`
- writes package metadata under `/skill-hub/packages/...`
- writes a search document under `/skill-hub/search/...`

### 4. Search The Catalog

```bash
curl -sS "http://localhost:8040/v1/packages/search?q=hello&limit=5"
```

If Nexus search is healthy, this uses Nexus search. If not, `skill-hub` falls back to metadata search.

### 5. Retrieve The Published Package

Artifact metadata:

```bash
curl -sS http://localhost:8040/v1/packages/nexi-lab/hello-skill/0.1.0/artifact
```

Read a published file:

```bash
curl -sS "http://localhost:8040/v1/packages/nexi-lab/hello-skill/0.1.0/content?path=SKILL.md"
```

### 6. Preview The Install

```bash
curl -sS -X POST http://localhost:8040/v1/installations/preview \
  -H "content-type: application/json" \
  -d '{
    "publisher": "nexi-lab",
    "name": "hello-skill",
    "version": "0.1.0",
    "target": "user",
    "scope_id": "demo-user"
  }'
```

### 7. Install The Package

```bash
curl -sS -X POST http://localhost:8040/v1/installations \
  -H "content-type: application/json" \
  -d '{
    "publisher": "nexi-lab",
    "name": "hello-skill",
    "version": "0.1.0",
    "target": "user",
    "scope_id": "demo-user"
  }'
```

### 8. Run The Smoke Script

```bash
bash scripts/e2e_smoke.sh
```

## Local Development

Without Docker:

```bash
export NEXUS_BASE_URL=http://127.0.0.1:2026
export NEXUS_API_KEY=dev-key
export SKILLHUB_NEXUS_CATALOG_ROOT=/skill-hub
export SKILLHUB_NEXUS_INSTALL_ROOT=/skills

uv sync
uv run skillhub serve
```

## Developer Verification

```bash
uv run pytest
uv run python -m compileall src tests
docker compose -f compose.yaml config
docker compose -f compose.yaml -f compose.local.yaml config
```

## Repo Layout

```text
skill-hub/
  docs/
    api/
    architecture/
  examples/
    hello-skill/
  scripts/
    e2e_smoke.sh
  src/
    skillhub/
  compose.yaml
  compose.local.yaml
```

## Architecture And API Docs

- `docs/architecture/phase1.md`
- `docs/api/phase1.md`

## License

Apache 2.0. See `LICENSE`.
