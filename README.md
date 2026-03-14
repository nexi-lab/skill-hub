# skill-hub

Nexus-backed skill catalog, package publishing, search, and installation for `SKILL.md` packages.

## One-Liner

`skill-hub` publishes a local `SKILL.md` package into Nexus, makes it searchable, and installs it into `/skills/...` through a clean API.

The bundled Docker stack in this repo is an integration harness for local/GCP validation.
The intended production boundary is: existing Nexus runtime + `skill-hub` app.

## What Works Today

Phase 1 is now genuinely Nexus-backed.

- publish a local package into a Nexus-backed catalog
- persist package metadata and package files inside Nexus
- retrieve package metadata and package content through `skill-hub`
- search the published package catalog, using Nexus search when available
- install published packages into `system`, `zone`, `user`, or `agent` scopes
- run the full stack with Docker: Postgres + Nexus + `skill-hub`

Recommended long-term deployment model:

- Nexus runs as its own runtime/infrastructure stack
- `skill-hub` connects to that Nexus over `NEXUS_BASE_URL` + `NEXUS_API_KEY`
- the bundled compose files remain for smoke tests and demos

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

Start the default stack:

```bash
docker compose -f compose.yaml up --build
```

This builds a thin wrapper around the official Nexus release image `ghcr.io/nexi-lab/nexus:0.9.2`.
The wrapper only patches the missing `libgomp1` runtime dependency so txtai-backed search works correctly with the released image.
The wrapper also bakes in a minimal `config.skillhub.yaml` so the release image does not silently boot with the bundled `config.demo.yaml`, which is a demo profile and not the right runtime shape for `skill-hub`.

If you are developing in a workspace that also has the Nexus repo checked out as the parent directory, you can override the default service and build Nexus from local source:

```bash
docker compose -f compose.yaml -f compose.local.yaml up --build
```

The local-source override uses the Nexus repo’s own root `Dockerfile`, so it includes the same Rust extensions and runtime wiring as the official Nexus image path.

The stack starts:

- `postgres` on the internal Docker network
- `dragonfly` on the internal Docker network
- `nexus` on `http://localhost:2026`
- `skill-hub` on `http://localhost:8040`

Compose enables Nexus search and uses:

- `NEXUS_API_KEY=sk-dev-skillhub-admin-1234567890abcdef`
- `NEXUS_IMAGE=ghcr.io/nexi-lab/nexus:0.9.2`
- `NEXUS_PLATFORM=linux/amd64`
- `NEXUS_CONFIG_FILE=/app/configs/config.skillhub.yaml`
- `NEXUS_CACHE_BACKEND=dragonfly`
- `NEXUS_DRAGONFLY_URL=redis://dragonfly:6379`
- `DRAGONFLY_MAXMEMORY=512mb`
- `DRAGONFLY_THREADS=2`
- `NEXUS_HEALTH_START_PERIOD=120s`
- `SKILLHUB_NEXUS_CATALOG_ROOT=/skill-hub`
- `SKILLHUB_NEXUS_INSTALL_ROOT=/skills`

On the first boot, Postgres initializes the `vector` extension and Nexus may spend extra time downloading the txtai embedding model into the Docker volume cache under `/app/data/.cache`. After that, restarts are much faster.
If you already have an older local stack volume, reset it once so the init SQL runs:

```bash
docker compose -f compose.yaml down -v
docker compose -f compose.yaml up --build
```

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

To confirm semantic search is actually active, inspect Nexus search stats:

```bash
curl -sS http://localhost:2026/api/v2/search/stats
```

You should see `"backend": "txtai"` once the search daemon is ready.

If you want to use a different official Nexus image tag:

```bash
NEXUS_IMAGE=ghcr.io/nexi-lab/nexus:0.9.2 docker compose -f compose.yaml up --build
```

On Apple Silicon, the default release-image path intentionally runs the amd64 image under emulation because the current `0.9.2` arm64 release image still has a ggml runtime issue.
That path is valid for smoke checks, but a full readiness/search validation is more trustworthy on an amd64 host such as the GCP deployment.

To confirm the pgvector database extension is enabled:

```bash
docker exec skillhub-postgres psql -U skillhub -d nexus -c '\dx'
```

You should see `vector` in the installed extensions list for a fresh stack.

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
export NEXUS_API_KEY=sk-dev-skillhub-admin-1234567890abcdef
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
  docker/
    nexus.Dockerfile
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
