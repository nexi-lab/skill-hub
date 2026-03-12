# Usage Guide

This guide walks through every way to use `skill-hub` — from first install to managing packages through the REST API.

## Prerequisites

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) package manager
- A running [Nexus](https://github.com/nexi-lab/nexus) instance (local or remote)

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/nexi-lab/skill-hub.git
cd skill-hub
uv sync
```

## Configuration

`skill-hub` is configured through environment variables:

| Variable | Description | Default |
|---|---|---|
| `NEXUS_BASE_URL` | URL of the Nexus server | `http://localhost:2026` |
| `NEXUS_API_KEY` | Bearer token for Nexus authentication | *(none)* |
| `SKILLHUB_NEXUS_INSTALL_ROOT` | Root path in Nexus for installed packages | `/skills` |
| `SKILLHUB_NEXUS_TIMEOUT_SECONDS` | HTTP timeout for Nexus calls | `5` |

Set them in your shell before running any command:

```bash
export NEXUS_BASE_URL=http://127.0.0.1:2026
export NEXUS_API_KEY=dev-key
export SKILLHUB_NEXUS_INSTALL_ROOT=/skills
```

## Writing a Skill Package

A skill package is a directory containing at minimum a `skillhub.yaml` manifest and a `SKILL.md` file:

```text
my-skill/
  skillhub.yaml      # package manifest (required)
  SKILL.md            # model-facing documentation (required)
  references/         # optional reference docs
    guide.md
  examples/           # optional examples
  assets/             # optional static assets
```

### The Manifest (`skillhub.yaml`)

The manifest declares package identity, type, files, and metadata. Generate a starter template with:

```bash
uv run skillhub print-example
```

Here is a minimal manifest:

```yaml
schema_version: "1"
name: my-skill
publisher: my-org
version: 0.1.0
type: prompt_pack
description: A short description of what this skill does.
nexus_version: ">=0.1.0"
install_target: user
capabilities_requested:
  - read_skill_docs
risk_level: low
credentials: []
permissions: []
files:
  skill_doc: SKILL.md
  references:
    - references/guide.md
  examples: []
  assets: []
entrypoints:
  scripts: []
  workflows: []
  mcp_servers: []
```

**Key fields:**

- `type` — one of `prompt_pack`, `workflow_pack`, `mcp_server`, or `bundle`
- `install_target` — default scope: `system`, `zone`, `user`, or `agent`
- `files.skill_doc` — path to the `SKILL.md` file (always required)
- `files.references` / `files.examples` / `files.assets` — additional files to materialize into Nexus

### Validate Your Manifest

```bash
uv run skillhub validate-manifest my-skill/skillhub.yaml
```

On success this prints the normalized package key (e.g. `my-org/my-skill@0.1.0`).

## CLI Usage

All CLI commands are run via `uv run skillhub <command>`.

### Check Nexus Connectivity

```bash
# Show the resolved Nexus configuration
uv run skillhub nexus-info

# Probe the Nexus health endpoint
uv run skillhub nexus-check
```

### Preview an Install

Before installing, preview what will happen. This shows the resolved Nexus target directory and the files that will be written — without making any changes:

```bash
uv run skillhub preview-install my-skill/ --target user --scope-id alice
```

### Install a Package

Register and install a local package into Nexus in one step:

```bash
uv run skillhub install-local my-skill/ --target user --scope-id alice
```

This will:

1. Validate the manifest
2. Register the package in the in-memory catalog
3. Create the target directory in Nexus
4. Upload all declared files

The output includes:

- `status` — should be `installed`
- `nexus_target_path` — the Nexus directory where files were written
- `materialized_files` — list of every file uploaded with its remote path and SHA-256 digest

### Register Without Installing

To register a package in the catalog without installing it:

```bash
uv run skillhub register-local my-skill/
```

You can then install it later through the API.

### Install Scopes

The `--target` flag controls where the package lands in Nexus:

| Target | Nexus Path | Use Case |
|---|---|---|
| `system` | `/skills/system/packages/<pub>/<name>/<ver>` | Global, shared across all users |
| `zone` | `/skills/zones/<id>/<pub>/<name>/<ver>` | Shared within a zone/team |
| `user` | `/skills/users/<id>/<pub>/<name>/<ver>` | Per-user install |
| `agent` | `/skills/agents/<id>/<pub>/<name>/<ver>` | Bound to a specific agent |

For `zone`, `user`, and `agent` targets, `--scope-id` is required to identify the specific scope.

## API Usage

Start the API server:

```bash
uv run skillhub serve --host 127.0.0.1 --port 8040
```

Interactive API docs are available at:

- Swagger UI: `http://127.0.0.1:8040/docs`
- ReDoc: `http://127.0.0.1:8040/redoc`

### Health Check

```bash
curl http://127.0.0.1:8040/health
```

### Register a Package

```bash
curl -X POST http://127.0.0.1:8040/v1/packages/register-local \
  -H "content-type: application/json" \
  -d '{"source_dir": "examples/hello-skill"}'
```

### List Packages

```bash
curl http://127.0.0.1:8040/v1/packages
```

### Get a Specific Package Version

```bash
curl http://127.0.0.1:8040/v1/packages/nexi-lab/hello-skill/0.1.0
```

### Preview an Install

```bash
curl -X POST http://127.0.0.1:8040/v1/installations/preview \
  -H "content-type: application/json" \
  -d '{
    "publisher": "nexi-lab",
    "name": "hello-skill",
    "version": "0.1.0",
    "target": "user",
    "scope_id": "demo-user"
  }'
```

### Install a Package

```bash
curl -X POST http://127.0.0.1:8040/v1/installations \
  -H "content-type: application/json" \
  -d '{
    "publisher": "nexi-lab",
    "name": "hello-skill",
    "version": "0.1.0",
    "target": "user",
    "scope_id": "demo-user"
  }'
```

### List Installations

```bash
curl http://127.0.0.1:8040/v1/installations
```

### Get a Specific Installation

```bash
# Replace <id> with the installation UUID from the install response
curl http://127.0.0.1:8040/v1/installations/<id>
```

## Verifying Installed Files

After installing, you can verify files were written to Nexus using the Nexus file API directly:

```bash
curl -H "Authorization: Bearer $NEXUS_API_KEY" \
  "$NEXUS_BASE_URL/api/v2/files/read?path=/skills/users/demo-user/nexi-lab/hello-skill/0.1.0/SKILL.md"
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

## Further Reading

- [Architecture (Phase 1)](architecture/phase1.md) — design decisions and component breakdown
- [API Reference (Phase 1)](api/phase1.md) — complete endpoint documentation with request/response schemas
- [Example package](../examples/hello-skill/) — a working `hello-skill` package to use as a starting point
