# Spore Roadmap

This is a living document. It describes *what* Spore intends to build, organized by system area. For *how* and *why* at the design level, see individual SEPs.

## Compiler core (`sporec`)

Design basis: [SEP-0006](seps/SEP-0006-compiler-architecture.md)

- Cranelift code generation (native binary output)
- Incremental compilation via salsa (module-level, signature-hash-based invalidation)
- End-to-end pipeline: Source → Lex → Parse → HIR → TypedHIR → Cranelift IR → native

## Hole system

Design basis: [SEP-0005](seps/SEP-0005-hole-system.md)

- Stabilize HoleReport protocol (versioned JSON schema)
- Hole priority and annotation system (`@requires-review`, `@agent-fillable`)
- Multi-hole atomic fill with cross-hole consistency checking
- Agent fill-and-verify loop: propose → validate → review if flagged

## Type system

Design basis: [SEP-0002](seps/SEP-0002-type-system.md)

- L0 refinement type enforcement (decidable predicates at type-check time)
- L1 abstract interpretation propagation (value flow analysis, no SMT)
- Property-based test generation from refinement predicates

## Capability and effect system

Design basis: [SEP-0003](seps/SEP-0003-effect-capability-system.md)

- Platform effect handler dispatch (runtime)
- Capability hierarchy formalization (lattice properties)
- Reference CLI platform: filesystem, network, process, clock, random
- Reference web platform: HTTP server, request/response

## Cost model

Design basis: [SEP-0004](seps/SEP-0004-cost-analysis.md)

- Symbolic cost expression grammar with decidability proof
- Recursive cost analysis (three-tier)
- Cost-aware scheduling hints for runtime

## Concurrency

Design basis: [SEP-0007](seps/SEP-0007-concurrency-model.md)

- Runtime execution of structured concurrency primitives (`spawn`, `await`, `parallel_scope`)
- Compiler-enforced task lifetimes (child cannot outlive parent)
- Cancellation propagation
- Concurrent cost model: conservative max across parallel lanes
- Channel linearity checks

## Module and package system

Design basis: [SEP-0008](seps/SEP-0008-module-package-system.md)

- Content-addressed package store (local `.spore-store` + pluggable backends)
- `spore.toml` + `.spore-lock` manifest workflow
- Package discovery, search, and documentation generation

## Diagnostics and developer experience

Design basis: [SEP-0006](seps/SEP-0006-compiler-architecture.md)

- LSP server (`spore-lsp`) with completions, diagnostics, go-to-definition, hole integration
- `spore watch` with real-time incremental diagnostics
- `spore watch --json` NDJSON events for IDE/Agent consumption

## Standard library

Design basis: [SEP-0009](seps/SEP-0009-standard-library.md)

- `spore.list`, `spore.map`, `spore.set`, `spore.str`, `spore.math`, `spore.ref`
- All further libraries as third-party packages

## Self-hosting

Design basis: [SEP-0006](seps/SEP-0006-compiler-architecture.md)

- Partial self-hosting: parser, type checker, cost analyzer rewritten in Spore
- Performance target: compiled output within 2x of equivalent Rust for compute-bound code
- Formal language specification (beyond design docs)
- Stability policy: backward compatibility for signatures and hole protocol

## Long-term explorations

These are not committed but may influence future design:

- Distributed capability delegation with cryptographic attestation
- Optional formal verification mode for safety-critical paths
- Visual hole explorer for interactive dependency graph navigation
- Cross-platform compilation: WASM, embedded, GPU via capability-gated backends
