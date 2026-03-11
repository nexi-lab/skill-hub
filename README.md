# skill-hub

Skill packaging, catalog, and installation for `SKILL.md` packages backed by Nexus.

## One-Liner

`skill-hub` turns a local `SKILL.md` directory into a versioned package that installs into a remote Nexus namespace through the official Nexus file APIs.

## What This Repo Is

`skill-hub` is the package and install control plane.

Nexus is the remote filesystem and runtime substrate.

Phase 1 is intentionally narrow:

- define a package contract with `skillhub.yaml`
- keep `SKILL.md` as the model-facing entry document
- register local packages in a catalog API
- preview exactly where a package will land in Nexus
- materialize declared package files into remote Nexus with `/api/v2/files/*`
- track installs across `system`, `zone`, `user`, and `agent` scopes

Phase 1 does not yet:

- execute workflows
- mount MCP servers
- bind credentials into runtime resources
- enforce runtime permissions
- manage rollback or snapshots

## Why Nexus

`skill-hub` uses Nexus as the remote system of record for installed package contents.

That gives us a clean boundary:

- `skill-hub` owns package metadata, catalog APIs, and install orchestration
- Nexus owns remote paths, file materialization, auth, and the future runtime layer

In Phase 1, install targets resolve to:

- `system` -> `/skills/system/packages/<publisher>/<name>/<version>`
- `zone` -> `/skills/zones/<zone_id>/<publisher>/<name>/<version>`
- `user` -> `/skills/users/<user_id>/<publisher>/<name>/<version>`
- `agent` -> `/skills/agents/<agent_id>/<publisher>/<name>/<version>`

## Package Contract

Each package is a directory:

```text
hello-skill/
  skillhub.yaml
  SKILL.md
  references/
    quickstart.md
```

Phase 1 materializes the files explicitly declared by the manifest:

- `skillhub.yaml`
- `files.skill_doc`
- `files.references`
- `files.examples`
- `files.assets`
- declared script and workflow file paths as package assets only

`skillhub.yaml` is the machine-readable contract for:

- package identity
- package type
- Nexus compatibility
- install scope
- declared credentials
- declared capability/permission metadata
- future runtime entrypoints

See the example package in `examples/hello-skill/`.

## Architecture

```text
Author / CI / CLI / API client
             |
             v
      +--------------+
      | skill-hub    |
      | pack/catalog |
      | preview/install
      +--------------+
             |
             v
      +-------------------+
      | Nexus HTTP APIs   |
      | /health           |
      | /api/v2/files/*   |
      +-------------------+
             |
             v
      /skills/<scope>/...
```

## Quick Start

Follow these steps in order.

### 1. Start Nexus

Run a local Nexus daemon in one terminal:

```bash
nexus serve \
  --host 127.0.0.1 \
  --port 2026 \
  --api-key dev-key \
  --data-dir ./.nexus-skillhub
```

### 2. Configure `skill-hub`

In a second terminal:

```bash
cd skill-hub
export NEXUS_BASE_URL=http://127.0.0.1:2026
export NEXUS_API_KEY=dev-key
export SKILLHUB_NEXUS_INSTALL_ROOT=/skills
```

### 3. Install Dependencies

```bash
uv sync
```

### 4. Inspect The Remote Nexus Config

```bash
uv run skillhub nexus-info
```

Expected fields:

- `mode: remote_http_backed`
- `base_url`
- `health_url`
- `files_api_base`

### 5. Probe Nexus Health

```bash
uv run skillhub nexus-check
```

Expected shape:

```json
{
  "reachable": true,
  "status": "ok",
  "service": "nexus-rpc",
  "http_status": 200,
  "detail": null
}
```

### 6. Preview A Real Install

```bash
uv run skillhub preview-install examples/hello-skill --target user --scope-id demo-user
```

The preview shows:

- the resolved Nexus target directory
- the ordered install steps
- the exact remote files that will be written

### 7. Install The Local Package Into Nexus

```bash
uv run skillhub install-local examples/hello-skill --target user --scope-id demo-user
```

Expected result:

- `status` is `installed`
- `nexus_target_path` points at `/skills/users/demo-user/nexi-lab/hello-skill/0.1.0`
- `materialized_files` includes `skillhub.yaml`, `SKILL.md`, and the reference file

### 8. Verify The Remote File In Nexus

```bash
curl -sS \
  -H "Authorization: Bearer $NEXUS_API_KEY" \
  "http://127.0.0.1:2026/api/v2/files/read?path=/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/SKILL.md"
```

You should see the installed `SKILL.md` content from Nexus.

### 9. Start The `skill-hub` API

```bash
uv run skillhub serve --host 127.0.0.1 --port 8040
```

Open:

- `http://127.0.0.1:8040/docs`
- `http://127.0.0.1:8040/redoc`

### 10. Register The Example Package Through The API

```bash
curl -sS -X POST http://127.0.0.1:8040/v1/packages/register-local \
  -H "content-type: application/json" \
  -d '{"source_dir":"examples/hello-skill"}'
```

### 11. Preview The Install Through The API

```bash
curl -sS -X POST http://127.0.0.1:8040/v1/installations/preview \
  -H "content-type: application/json" \
  -d '{
    "publisher": "nexi-lab",
    "name": "hello-skill",
    "version": "0.1.0",
    "target": "user",
    "scope_id": "demo-user"
  }'
```

### 12. Install Through The API

```bash
curl -sS -X POST http://127.0.0.1:8040/v1/installations \
  -H "content-type: application/json" \
  -d '{
    "publisher": "nexi-lab",
    "name": "hello-skill",
    "version": "0.1.0",
    "target": "user",
    "scope_id": "demo-user"
  }'
```

### 13. List Installs

```bash
curl -sS http://127.0.0.1:8040/v1/installations
```

## CLI Commands

```bash
uv run skillhub nexus-info
uv run skillhub nexus-check
uv run skillhub print-example
uv run skillhub validate-manifest examples/hello-skill/skillhub.yaml
uv run skillhub register-local examples/hello-skill
uv run skillhub preview-install examples/hello-skill --target user --scope-id demo-user
uv run skillhub install-local examples/hello-skill --target user --scope-id demo-user
uv run skillhub serve
```

## Phase 1 API

Core routes:

- `GET /health`
- `GET /v1/nexus`
- `GET /v1/nexus/health`
- `GET /v1/packages`
- `POST /v1/packages/register`
- `POST /v1/packages/register-local`
- `GET /v1/packages/{publisher}/{name}`
- `GET /v1/packages/{publisher}/{name}/{version}`
- `POST /v1/installations/preview`
- `POST /v1/installations`
- `GET /v1/installations`
- `GET /v1/installations/{installation_id}`

Detailed docs:

- `docs/architecture/phase1.md`
- `docs/api/phase1.md`

## Repository Layout

```text
skill-hub/
  docs/
    architecture/
    api/
  examples/
    hello-skill/
  src/
    skillhub/
  tests/
```

## Development

Run the test suite:

```bash
uv run pytest
```

Compile-check the source tree:

```bash
uv run python -m compileall src tests
```

## Roadmap

### Phase 1

- local package registration
- remote Nexus health probing
- remote Nexus file materialization
- install preview and install tracking
- stable package path conventions

### Phase 2

- workflow materialization
- MCP package materialization
- credential binding
- access-manifest generation
- rollback and snapshot-aware installs

## License

Apache 2.0. See `LICENSE`.
