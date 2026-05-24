---
sep: 8
title: "SEP-0008: Module & Package System"
status: Draft
type: Standards Track
authors:
  - Zhan Rongrui
created: 2026-03-31
requires:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
discussion: "https://github.com/spore-lang/spore-evolution/discussions/8"
pr: null
superseded_by: null
---

# SEP-0008: Module & Package System

> **Executive Summary**: Defines file-based modules, package manifests, Platform packages, visibility, and content-addressed provenance under the signature model. Packages bind signatures, intents, properties, realizations, evidence, and dependencies through named hashes rather than release ranges.

## Summary

A Spore module is one source file. Its module path is derived from its file path.
Packages are described by `spore.toml`, lock data, and content-addressed inputs.

The signature model changes package identity from callable-only API identity
to provenance over:

- `signature_hash`
- `intent_hash`
- `property_hash`
- `realization_hash`
- `evidence_hash`
- dependency hashes

## Motivation

Package consumers need to know what callable boundary they depend on, which
intent constraints were attached, which realization was used, and what evidence
was generated. Human labels are useful communication, but hashes are the
mechanical identity.

## Guide-level explanation

### Modules

`src/billing/invoice.sp` maps to module `billing.invoice`. There is no source
module header.

```spore
import billing.invoice
import platform.console as console
```

### Visibility

```spore
pub fn public_api() -> () { return }
pub(pkg) fn package_helper() -> () { return }
fn private_helper() -> () { return }
```

### Platform packages

A Platform package provides effect handlers and validates the startup contract
for an application.

```spore
pub fn main() -> ()
uses [Console, Exit]
{
    ?main_body
}
```

### Package provenance

Lock data records hashes for each public subject:

```toml
[[functions]]
name = "billing.invoice.total"
signature-hash = "..."
intent-hash = "..."
property-hash = "..."
realization-hash = "..."
evidence-hash = "..."
```

## Reference-level explanation

### Module resolution

Imports use dot-separated paths. A module may import another module by path and
may introduce a local alias. Selective and wildcard imports are outside this SEP.

### Visibility rules

Private items are visible only inside their defining module. `pub(pkg)` items
are visible inside the package. `pub` items are visible to downstream packages.

### Signature package identity

A package API hash is derived from exported signature and intent hashes. A
package evidence hash is derived from evidence records selected by the package
policy. Realization hashes pin exact implementation artifacts for reproducible
builds.

### Dependency resolution

Dependencies resolve by declared package source plus expected hashes. If a
dependency's signature hash changes, importers must explicitly accept the new
callable boundary. If only a realization hash changes, importers may reuse the
same callable boundary but still record the new realization and evidence.

### Platform startup contract

A selected Platform declares the accepted startup function shape, required
runtime handlers, and host adapter. The compiler verifies the application entry
against that contract.

### Holes and packages

A package may contain holes during development. Public release policies may
require `holes: 0` budget evidence for exported callables before publication.

## Human experience impact

Developers review named hash categories instead of a single opaque digest. This
makes it clearer whether a change altered the callable boundary, intent,
realization, or evidence.

## Agent experience impact

Agents can decide whether a dependency update is relevant to their task by
inspecting the changed hash category and evidence results.

## Structured representation / protocol impact

```text
PackageRecord
├── modules[]
├── exports[]
├── platform?
├── hashes
│   ├── signature_hashes[]
│   ├── intent_hashes[]
│   ├── property_hashes[]
│   ├── realization_hashes[]
│   └── evidence_hashes[]
└── dependencies[]
```

## Diagnostics impact

Module diagnostics use `M0xxx` codes:

| Code    | Name                      | Meaning                                           |
| ------- | ------------------------- | ------------------------------------------------- |
| `M0101` | circular-dependency       | Module graph contains a cycle                     |
| `M0201` | visibility-violation      | Item is not visible from the use site             |
| `M0301` | import-not-found          | Import path cannot be resolved                    |
| `M0401` | signature-hash-changed    | Dependency callable boundary changed              |
| `M0402` | evidence-missing          | Required evidence record is absent                |
| `M0501` | platform-binding-conflict | More than one Platform binding selected           |
| `M0502` | startup-contract-mismatch | Entry function does not satisfy Platform contract |

## Drawbacks

Multiple hash categories are more complex than release-label ranges. Tooling must
render concise labels and explain which category changed.

Evidence-aware package gates may slow publication until checkers have produced
records for required claims.

## Alternatives considered

### Release-label ranges

Rejected because labels cannot prove compatibility or realization identity.

### Single package hash

Rejected because it hides whether a change affected signatures, intents,
properties, realizations, evidence, or dependencies.

### Module declarations in source

Rejected because file paths are already the package structure source of truth.

## Prior art

Unison and Nix influenced content addressing. Cargo and Go modules influenced
lock data and reproducible dependency review. Roc influenced Platform packages.

## Backward compatibility and migration

Package metadata must migrate to named signature hash categories. Existing
manifest fields can remain when they describe package names, paths, and Platform
selection rather than compatibility identity.

## Unresolved questions

1. Which evidence records are required for package publication?
2. Should package APIs include private intent hashes or exported subjects only?
3. How should transitive evidence failures be summarized for users?
