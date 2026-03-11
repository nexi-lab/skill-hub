# Phase 1 Architecture

## Executive Summary

Phase 1 makes `skill-hub` a remote Nexus-backed package control plane for skills.

The key boundary is deliberate:

- `skill-hub` owns packaging, cataloging, install previews, and install records
- remote Nexus provides the namespace model that installs resolve into
- runtime execution is deferred to Phase 2

This gives us a real product surface now without pretending that workflows,
MCP mounts, credentials, or permissions are finished.

## Product Statement

In Phase 1, a skill is:

- a directory with `SKILL.md`
- a typed `skillhub.yaml`
- optional support files such as `references/`, `examples/`, `scripts/`, and `assets/`

In Phase 1, installation means:

- validate package metadata
- register a package version
- resolve the target path on a remote Nexus namespace
- record that install against a scope

It does not yet mean:

- executing the skill
- mounting tools
- binding secrets into runtime resources
- enforcing policy in Nexus

## Why Remote Nexus Is Already Part Of Phase 1

Phase 1 is not runtime-heavy, but it is not Nexus-free.

It uses remote Nexus as the authoritative namespace model for where packages land:

- `/skills/system/packages/...`
- `/skills/zones/<zone_id>/...`
- `/skills/users/<user_id>/...`
- `/skills/agents/<agent_id>/...`

That gives us:

- stable install semantics
- future compatibility with Phase 2 materialization
- a clean migration path from “install record” to “runtime-backed install”

## System Boundaries

### skill-hub

Owns:

- manifest validation
- package registration
- package listing
- install preview
- install recording
- API and CLI ergonomics

### Remote Nexus

Phase 1 role:

- namespace anchor
- scope model
- future runtime target

Phase 2 role:

- workflow runtime
- MCP runtime
- credentials / manifests / policy
- install rollback and snapshots

## Architecture Diagram

```text
Authors / CLI / API Clients
          |
          v
+----------------------+
| skill-hub API / CLI  |
| validation + catalog |
| preview + installs   |
+----------------------+
          |
          v
+----------------------+
| Nexus Adapter        |
| remote namespace     |
| planning only        |
+----------------------+
          |
          v
+----------------------+
| Remote Nexus         |
| /skills/... paths    |
| runtime in Phase 2   |
+----------------------+
```

## Core Components

### Manifest Model

`skillhub.yaml` is the machine-readable contract for:

- identity
- package type
- target scope
- risk metadata
- credentials metadata
- permissions metadata
- future runtime entrypoints

### Catalog API

The API exposes:

- remote Nexus config
- package registration
- package listing
- install preview
- install recording

### Nexus Adapter

The adapter resolves package installs into concrete Nexus target paths.

That is the crucial Phase 1 “backed by Nexus” guarantee.

### Example Package

The example package proves the minimum contract and supports docs, tests, and quick start.

## Non-Goals

Phase 1 intentionally avoids:

- artifact registries
- MCP execution
- workflow execution
- live remote Nexus mutation
- policy enforcement
- approval workflows
- billing and reputation

## Phase 2 Expansion

Phase 2 will extend the same adapter boundary to:

- materialize package files into Nexus
- register workflow resources
- register MCP mounts
- bind credentials
- generate access-manifest policy
- support rollback and install previews with real Nexus actions
