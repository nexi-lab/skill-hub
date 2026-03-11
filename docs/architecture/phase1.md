# Phase 1 Architecture

## Goal

Build the thinnest useful version of `skill-hub`:

- define the package format
- register packages in a catalog
- track installs
- keep a clean boundary for Nexus runtime integration

## Why Phase 1 Is Runtime-Light

Phase 1 is intentionally not the runtime executor.

That avoids overbuilding around:

- workflow execution
- MCP mount orchestration
- credentials binding
- access-manifest generation
- rollback and install preview

All of those become Phase 2 concerns.

## Components

### API

FastAPI app that exposes:

- package registration
- package listing
- install tracking

### Manifest Model

`skillhub.yaml` provides typed metadata for:

- package identity
- install target
- risk level
- declared credentials
- declared capabilities
- future runtime entrypoints

### Example Package

The example package demonstrates the minimum contract:

- `SKILL.md`
- `skillhub.yaml`
- `references/`

### Nexus Adapter

The adapter exists now as a stub so Phase 2 work lands in the right place.

The adapter will eventually:

- create install plans
- materialize package files into Nexus
- register workflows
- mount MCP servers
- apply access-manifest policy

## Phase 1 Non-Goals

- no auto-execution of package scripts
- no generic remote tool execution surface
- no package artifact registry yet
- no billing or reputation
- no org approval workflow

## Phase 2 Entry Criteria

Move to Phase 2 once these are stable:

- manifest schema
- package catalog shape
- install state model
- CLI ergonomics
- package examples
