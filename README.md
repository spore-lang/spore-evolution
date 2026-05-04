# spore-evolution

Proposal repository for the Spore programming project.

This repository is the long-lived home for major language, tooling, and process proposals that affect Spore as a whole.

## Release-safety notice

The SEPs in this repository are design records and proposal texts. They are not,
by themselves, the current implementation truth, a compatibility guarantee, or a
public release contract for Spore.

All numbered SEPs are currently `Draft`. During this bootstrap phase, readers
should expect some examples and terminology to lag behind the implementation.
For current release behavior, installation guidance, supported syntax, and
implementation status, use the implementation repository first: `spore/README.md`
and `spore/docs/DESIGN.md`.

In particular, older SEP examples may use historical spellings such as
`String`/`Unit`/`Int`/`Float` or scalar cost forms such as `cost ≤ expr` and
`@cost`. Current implementation-facing docs use the active primitive spellings
and the four-slot `cost [compute, alloc, io, parallel]` form where applicable.

## What lives here

- `drafts/` — unnumbered proposal drafts under active discussion
- `seps/` — numbered SEP documents and historical process records
- `templates/` — authoring templates for new proposals
- `schemas/` — machine-readable rules for SEP metadata and shared machine contracts
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

An SEP is the design record for changes to Spore semantics, standard-library
surface, tooling protocols, cross-cutting system design, or the project process itself.
For the decision threshold, lifecycle, and authoring rules, see
[`seps/SEP-0000-process.md`](seps/SEP-0000-process.md).

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
