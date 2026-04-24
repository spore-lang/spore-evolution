# Spore Design Vision

Spore is a compiled, general-purpose programming language where **intent is a first-class citizen**.

## Core principles

### 1. Signatures are gravity centers

A function signature is a complete specification: input/output types, error sets, cost budget, and required effects. All downstream analysis flows from the signature. The body can be empty — the intent is already fully expressed.

### 2. Holes are collaboration points, not errors

A program with holes compiles successfully. It is *partial*, not broken. Holes are the primary mechanism for structured collaboration between humans, Agents, and teams. The compiler provides a self-contained HoleReport for each hole so that any reader — human or machine — can propose a fill without additional context.

### 3. Architecture first, details later

The recommended workflow is top-down: define signatures and types, verify the skeleton with the compiler, then fill holes iteratively in dependency order. Design-critical decisions must be reviewed explicitly before implementation proceeds.

### 4. The compiler is a documentation assistant

Every compiler output — diagnostics, hole reports, incremental events, dependency graphs — is available in both human-readable and machine-readable form. Humans see clear error messages with repair hints; Agents see structured JSON suitable for automated reasoning.

### 5. Explicit effect and cost models

Every side effect must be covered by declared effects. Every computational cost can be bounded and verified at compile time. A function's impact is fully assessable from its signature alone.

### 6. Content-addressed, not version-numbered

Modules are identified by content hashes (signature hash for interface compatibility, implementation hash for caching). No semver, no diamond dependency conflicts.

## Intellectual heritage

| Language | Idea adopted |
|----------|-------------|
| **Agda** | Holes as first-class typed placeholders |
| **Idris** | Elaboration — the compiler fills in details the programmer omits |
| **Unison** | Content-addressed code — modules identified by hash, not name+version |
| **Elm** | Human-friendly error messages as a primary design goal |
| **Roc** | Managed effects — all IO through platform-provided effect handlers |

## Guiding questions for every design decision

1. Does this make user intent **clearer** or more obscure?
2. Does this **reduce** ambiguity for Agents?
3. Can the key semantics be exported in a **stable, machine-readable** form?
4. Does it improve or degrade **diagnostics and repair workflows**?
5. Does it preserve **conceptual coherence** with the rest of Spore?
