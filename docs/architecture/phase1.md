# Phase 1 Architecture

## Executive Summary

Phase 1 is no longer just install planning.

`skill-hub` now uses Nexus as:

- the package catalog store
- the published artifact store
- the package search substrate
- the install destination

This gives a real end-to-end product surface without building a second runtime.

## Boundaries

### skill-hub

Owns:

- package validation
- package publishing
- package metadata APIs
- package search orchestration
- install preview
- install orchestration
- installation records

### Nexus

Owns:

- remote file persistence
- search indexing and search queries
- durable package artifact storage
- installed package contents under `/skills/...`

## Package Lifecycle

### Publish

Publishing a local package does four things:

1. load `skillhub.yaml`
2. validate all declared package files
3. write artifact files into Nexus under `/skill-hub/artifacts/...`
4. write package metadata and a search document into Nexus

### Search

Package search is routed through Nexus search when available:

- search documents live under `/skill-hub/search/...`
- `skill-hub` calls Nexus search with `path=/skill-hub/search`
- results are mapped back to package records

If Nexus search is not enabled, `skill-hub` falls back to metadata search.

### Install

Install now copies from the Nexus-backed package artifact store into `/skills/...`.

That means install no longer depends on the original local package directory after publish.

## Storage Layout

```text
/skill-hub/
  index/
    packages.json
    installations.json
  packages/
    <publisher>/<name>/<version>/package.json
  artifacts/
    <publisher>/<name>/<version>/...
  search/
    <publisher>/<name>/<version>/document.md
  installations/
    <installation_id>.json
```

Install targets:

```text
/skills/system/packages/<publisher>/<name>/<version>
/skills/zones/<zone_id>/<publisher>/<name>/<version>
/skills/users/<user_id>/<publisher>/<name>/<version>
/skills/agents/<agent_id>/<publisher>/<name>/<version>
```

## Why This Shape

This structure solves the core Phase 1 problems:

- package catalog survives restarts
- published packages are retrievable
- installs can be repeated later
- search can be delegated to Nexus instead of duplicated
- Phase 2 can build runtime semantics on top of the same paths

## Search Model

Each published package gets a search document built from:

- manifest metadata
- `SKILL.md`
- declared reference files

That document is what Nexus indexes.

The package record remains the authoritative machine-readable object.

## Non-Goals

Phase 1 still excludes:

- workflow execution
- MCP mounting
- credentials binding
- runtime permission enforcement
- rollback/snapshots
- billing, reviews, or marketplace economics

## Phase 2 Direction

Phase 2 should build on the same catalog paths and add:

- workflow materialization
- MCP package materialization
- credential binding
- access manifest generation
- rollback and snapshot-aware installs
