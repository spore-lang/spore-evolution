# spore-evolution

Proposal repository for the Spore programming language.

This repository is the long-lived home for major language, tooling, and process proposals that affect Spore as a whole.

## What lives here

- `drafts/` — unnumbered proposal drafts under active discussion
- `seps/` — numbered SEP documents and historical process records
- `templates/` — authoring templates for new proposals
- `schemas/` — machine-readable rules for SEP metadata
- `scripts/` — repository validation and automation helpers

## Current entry points

- [`VISION.md`](VISION.md) — design philosophy and core principles
- [`ROADMAP.md`](ROADMAP.md) — long-term plan organized by system area
- [`seps/SEP-0000-process.md`](seps/SEP-0000-process.md) — the draft SEP process
- [`seps-index.json`](seps-index.json) — generated machine-readable SEP index
- [`templates/standards-track.md`](templates/standards-track.md) — Standards Track template
- [`templates/process.md`](templates/process.md) — Process template
- [`templates/informational.md`](templates/informational.md) — Informational template

## What is an SEP?

**SEP** stands for **Spore Enhancement Proposal**.

An SEP is the design record for substantial changes to:

- Spore itself
- the standard library or core tools
- diagnostics and machine-readable language protocols
- package/module/effect/capability/cost systems
- the Spore evolution process itself

Small bug fixes, routine refactors, editorial changes, and implementation-only work should usually go through normal repository pull requests instead of the SEP process.

## Status

The process in this repository is still being bootstrapped.

`SEP-0000` is intentionally a draft. We expect to revise the process, template, and metadata rules before treating them as settled.

## Tooling direction

The current first-pass automation stack is:

- Shared local/CI hook runner: `prek`
- Markdown lint: `rumdl`
- Prose and terminology lint: `Vale`
- Link checking: `lychee`
- Spelling: `typos`
- Front matter schema validation: `check-jsonschema`
- Machine-readable SEP index: committed `seps-index.json`, checked for drift in local hooks and CI
- SEP-specific repository rules: minimal repo-local Python checks
- CI platform: GitHub Actions

The static site stack is intentionally deferred for now. We want to stabilize the proposal workflow and quality gates first, then choose the publishing stack separately.
