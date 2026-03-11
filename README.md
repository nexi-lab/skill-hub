# skill-hub

Remote Nexus-backed skill packaging, catalog, and installation control plane.

`skill-hub` is an open source package manager for `SKILL.md`-based skills. In Phase 1, it gives teams a clean package format, a typed manifest, a catalog API, and install previews that resolve into stable paths on a remote Nexus namespace. It does not yet execute workflows, mount MCP servers, or enforce runtime permissions. That is Phase 2.

## One-Liner

`skill-hub` turns `SKILL.md` directories into versioned, installable packages backed by remote Nexus namespace conventions.

## What Phase 1 Does

- defines the package contract with `skillhub.yaml`
- keeps `SKILL.md` as the agent-facing usage document
- validates package manifests locally
- registers package versions in a catalog API
- previews where a package will land in a remote Nexus namespace
- records installs against `system`, `zone`, `user`, or `agent` scopes
- exposes a clean OpenAPI surface for Phase 1 clients

## What Phase 1 Does Not Do

- execute workflows through Nexus
- mount MCP servers
- generate Nexus access manifests
- bind credentials into runtime resources
- run arbitrary package scripts automatically

## Why This Exists

The long-term goal is a dedicated `nexi-lab/skill-hub` repository that:

- distributes skills as immutable artifacts
- supports `SKILL.md` plus references, examples, scripts, and assets
- uses `skillhub.yaml` for machine-readable metadata
- evolves into a Nexus-backed runtime control plane

Phase 1 is the foundation. It is intentionally narrow and concrete.

## Package Structure

Each package contains:

- `SKILL.md`
- `skillhub.yaml`
- optional `references/`
- optional `examples/`
- optional `scripts/`
- optional `assets/`

Example:

```text
hello-skill/
  SKILL.md
  skillhub.yaml
  references/
    quickstart.md
```

## Manifest Contract

`skillhub.yaml` is the machine-readable source of truth.

It currently defines:

- package identity: `name`, `publisher`, `version`
- package type: `prompt_pack`, `workflow_pack`, `mcp_server`, `bundle`
- intended Nexus compatibility: `nexus_version`
- target scope: `system | zone | user | agent`
- declared credentials
- declared capabilities / permissions metadata
- package file groups
- future runtime entrypoints

See the example in [examples/hello-skill/skillhub.yaml](/Users/taofeng/nexus/skill-hub/examples/hello-skill/skillhub.yaml).

## Remote Nexus Model

Phase 1 is already Nexus-backed in one specific sense: installs resolve to stable paths on a remote Nexus namespace.

The hub uses:

- `NEXUS_BASE_URL`
- `NEXUS_API_KEY`
- `SKILLHUB_NEXUS_INSTALL_ROOT`

to plan where packages should land.

Example resolved install paths:

- `system` -> `/skills/system/packages/<publisher>/<name>/<version>`
- `zone` -> `/skills/zones/<zone_id>/<publisher>/<name>/<version>`
- `user` -> `/skills/users/<user_id>/<publisher>/<name>/<version>`
- `agent` -> `/skills/agents/<agent_id>/<publisher>/<name>/<version>`

Phase 1 resolves and records these paths. Phase 2 will materialize runtime resources behind them.

## API Summary

The FastAPI app exposes:

- `GET /health`
- `GET /v1/nexus`
- `GET /v1/packages`
- `POST /v1/packages/register`
- `GET /v1/packages/{publisher}/{name}`
- `GET /v1/packages/{publisher}/{name}/{version}`
- `POST /v1/installations/preview`
- `POST /v1/installations`
- `GET /v1/installations`

Interactive docs are available at:

- `http://127.0.0.1:8040/docs`
- `http://127.0.0.1:8040/redoc`

## Quick Start

Follow these steps exactly.

### 1. Choose A Remote Nexus

You need a reachable Nexus server.

Example:

```bash
export NEXUS_BASE_URL=http://localhost:2026
export NEXUS_API_KEY=nx_your_api_key_here
```

Optional install root override:

```bash
export SKILLHUB_NEXUS_INSTALL_ROOT=/skills
```

### 2. Verify The Repo Layout

```bash
cd skill-hub
```

### 3. Install Dependencies

```bash
uv sync
```

### 4. Check The Effective Nexus Config

```bash
uv run skillhub nexus-info
```

You should see JSON including:

- `mode: remote_namespace_backed`
- your `base_url`
- whether an API key is configured

### 5. Validate The Example Manifest

```bash
uv run skillhub validate-manifest examples/hello-skill/skillhub.yaml
```

Expected output:

```text
Valid manifest: nexi-lab/hello-skill@0.1.0
```

### 6. Preview The Install Path From The CLI

```bash
uv run skillhub preview-install examples/hello-skill/skillhub.yaml --target user --scope-id demo-user
```

Expected output includes:

- `package_key`
- `nexus_base_url`
- `nexus_target_path`
- `steps`

### 7. Start The API

```bash
uv run skillhub serve --host 127.0.0.1 --port 8040
```

Leave that running in one terminal.

### 8. Inspect The API Contract

In a second terminal:

```bash
curl http://127.0.0.1:8040/v1/nexus
```

### 9. Register The Example Package

```bash
curl -X POST http://127.0.0.1:8040/v1/packages/register \
  -H 'content-type: application/json' \
  -d '{
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
    "artifact_uri": "file://examples/hello-skill",
    "artifact_digest": "sha256:phase1-example"
  }'
```

### 10. Preview The Install Through The API

```bash
curl -X POST http://127.0.0.1:8040/v1/installations/preview \
  -H 'content-type: application/json' \
  -d '{
    "publisher": "nexi-lab",
    "name": "hello-skill",
    "version": "0.1.0",
    "target": "user",
    "scope_id": "demo-user"
  }'
```

You should see a `nexus_target_path` like:

```text
/skills/users/demo-user/nexi-lab/hello-skill/0.1.0
```

### 11. Record The Install

```bash
curl -X POST http://127.0.0.1:8040/v1/installations \
  -H 'content-type: application/json' \
  -d '{
    "publisher": "nexi-lab",
    "name": "hello-skill",
    "version": "0.1.0",
    "target": "user",
    "scope_id": "demo-user"
  }'
```

### 12. List Recorded Installs

```bash
curl http://127.0.0.1:8040/v1/installations
```

## Developer Commands

```bash
uv run skillhub print-example
uv run skillhub validate-manifest examples/hello-skill/skillhub.yaml
uv run skillhub preview-install examples/hello-skill/skillhub.yaml --target user --scope-id demo-user
uv run skillhub serve
PYTHONPATH=src python3 -m pytest
```

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

## Architecture

- [Phase 1 Architecture](/Users/taofeng/nexus/skill-hub/docs/architecture/phase1.md)
- [Phase 1 API](/Users/taofeng/nexus/skill-hub/docs/api/phase1.md)

## Roadmap

### Phase 1

- package structure
- manifest schema
- remote Nexus namespace planning
- catalog registration
- install preview and install recording

### Phase 2

- workflow package materialization
- MCP package materialization
- credentials binding
- access-manifest generation
- rollback / install preview with real Nexus actions

## License

Apache 2.0. See [LICENSE](/Users/taofeng/nexus/skill-hub/LICENSE).
