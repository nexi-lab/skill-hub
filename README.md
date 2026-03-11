# skill-hub

`skill-hub` is a Phase 1 package catalog and install control plane for skills built on top of Nexus concepts.

Phase 1 is intentionally light on runtime execution. It focuses on:

- package structure
- manifest validation
- package registration
- install tracking
- examples and docs

Phase 1 does not yet do full Nexus runtime orchestration. In particular, it does not yet:

- mount MCP servers
- execute workflows through Nexus
- generate Nexus access manifests
- run arbitrary package scripts automatically

That is Phase 2.

## Why This Repo Exists

The long-term goal is a dedicated `nexi-lab/skill-hub` repository that:

- distributes skills as immutable package artifacts
- keeps `SKILL.md` for agent-facing instructions
- adds a machine-readable `skillhub.yaml`
- evolves into a Nexus-backed runtime control plane

For now, this scaffold provides the Phase 1 foundation:

- a package manifest model
- a FastAPI catalog API
- a Typer CLI for manifest validation
- a stub Nexus adapter boundary for Phase 2
- an example skill package

## Repository Layout

```text
skill-hub/
  docs/
    architecture/
  examples/
    hello-skill/
  src/
    skillhub/
  tests/
```

## Phase 1 Model

Each skill package contains:

- `SKILL.md`
- `skillhub.yaml`
- optional `references/`
- optional `examples/`
- optional `scripts/`
- optional `assets/`

`skillhub.yaml` is the source of truth for machine-readable metadata.

`SKILL.md` remains the source of truth for agent-facing usage instructions.

## Quick Start

```bash
uv sync
uv run uvicorn skillhub.api:app --reload
uv run skillhub validate-manifest examples/hello-skill/skillhub.yaml
```

## Initial API Surface

- `GET /health`
- `GET /v1/packages`
- `POST /v1/packages/register`
- `GET /v1/packages/{publisher}/{name}`
- `POST /v1/installations`
- `GET /v1/installations`

## Phase 2 Direction

Phase 2 will add real Nexus runtime integration through the adapter boundary in `src/skillhub/nexus_adapter.py`:

- workflow registration/execution
- MCP mount/install flows
- credentials binding
- access-manifest generation
- install preview / rollback
