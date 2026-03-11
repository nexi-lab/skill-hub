# Phase 1 Architecture

## Executive Summary

Phase 1 makes `skill-hub` a real Nexus-backed install control plane.

The important boundary is:

- `skill-hub` owns package metadata, catalog APIs, preview, and install orchestration
- Nexus owns the remote namespace, auth boundary, and installed file state

Phase 1 now performs live remote mutation, but only at the file/package layer.

It still does not claim a runtime for workflows, MCP mounts, credentials, or policy.

## Product Statement

In Phase 1, a skill package is:

- a local directory
- a required `skillhub.yaml`
- a required `SKILL.md`
- optional `references/`, `examples/`, `assets/`, `scripts/`, and `workflows/`

In Phase 1, installation means:

1. validate the manifest and declared files
2. register the package in the catalog
3. resolve the Nexus target path for the requested scope
4. probe remote Nexus health
5. create the target directory in Nexus
6. write the declared package files through `/api/v2/files/*`
7. record the installation in `skill-hub`

It does not yet mean:

- executing package code
- loading workflows into a runtime scheduler
- mounting MCP tools
- binding secrets
- generating enforceable access manifests

## Why Nexus Is In Phase 1

Phase 1 is not just “Nexus-aware”. It directly uses Nexus as the remote file plane.

Specifically, `skill-hub` talks to:

- `GET /health`
- `POST /api/v2/files/mkdir`
- `POST /api/v2/files/write`
- `GET /api/v2/files/exists`

That gives Phase 1 three concrete properties:

- installs land in a real remote system
- package contents are visible in Nexus immediately
- the Phase 2 runtime can build on the same installed paths

## Install Targets

Install targets map to stable Nexus path conventions:

- `system` -> `/skills/system/packages/<publisher>/<name>/<version>`
- `zone` -> `/skills/zones/<zone_id>/<publisher>/<name>/<version>`
- `user` -> `/skills/users/<user_id>/<publisher>/<name>/<version>`
- `agent` -> `/skills/agents/<agent_id>/<publisher>/<name>/<version>`

These path conventions are part of the Phase 1 contract.

## Architecture Diagram

```text
Author / CI / CLI / API client
             |
             v
   +-----------------------+
   | skill-hub API / CLI   |
   | manifest validation   |
   | local package loading |
   | preview + installs    |
   +-----------------------+
             |
             v
   +-----------------------+
   | Nexus Adapter         |
   | /health               |
   | /api/v2/files/*       |
   +-----------------------+
             |
             v
   +-----------------------+
   | Remote Nexus          |
   | /skills/... contents  |
   | future runtime layer  |
   +-----------------------+
```

## Core Components

### Manifest Model

`skillhub.yaml` defines:

- package identity
- package type
- install target
- Nexus compatibility
- declared credentials
- declared capabilities and permission metadata
- file groups
- future runtime entrypoints

### Local Package Loader

The local package loader:

- reads `skillhub.yaml`
- validates that declared files exist
- computes a deterministic package digest
- records a `file://` artifact URI for Phase 1 installs

### Catalog API

The catalog API supports:

- raw package registration
- local-directory registration
- package listing and version lookup
- install preview
- install execution
- install record lookup

### Nexus Adapter

The Nexus adapter is the Phase 1 integration seam.

Its responsibilities are:

- derive target paths from scope
- probe remote Nexus
- create target directories
- write declared files
- verify that the written files exist remotely

## Security Posture In Phase 1

Phase 1 is deliberately conservative.

- package files are materialized as files only
- scripts are not executed
- workflow YAML is not executed
- MCP entrypoints are metadata only
- declared permissions remain informational metadata

## Non-Goals

Phase 1 intentionally excludes:

- OCI artifact storage
- workflow runtime registration
- MCP mounting
- credential binding
- approval workflows
- rollback and snapshots
- billing and reputation

## Phase 2 Expansion

Phase 2 should extend the same install boundary into runtime-aware installs:

- register workflow resources with Nexus
- register MCP mounts
- bind credentials
- generate access manifests
- add rollback and snapshot-aware previews
