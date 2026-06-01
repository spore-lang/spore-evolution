---
sep: 6
title: "SEP-0006: Compiler Architecture"
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
discussion: "https://github.com/spore-lang/spore-evolution/discussions/6"
pr: null
superseded_by: null
---

# SEP-0006: Compiler Architecture

> **Executive Summary**: Defines the Spore compiler pipeline under the signature model. The compiler parses Base and Intent Signatures, lowers source properties into internal Claims, verifies realizations, and emits EvidenceRecords with provenance hashes for signatures, intents, properties, realizations, checkers, and dependencies.

## Summary

The compiler pipeline is:

```text
Lex -> Parse -> Resolve -> TypeCheck -> Verify -> Codegen
```

Three intermediate representations are used:

- AST: parsed surface syntax
- HIR: resolved names, normalized signatures, and desugared expressions
- TypedHIR: typed bodies, hole reports, claims, and verification inputs

Evidence generation is part of verification. Evidence is not source text.

## Motivation

Spore is built for humans and Agents to share the same compiler facts. The
compiler must therefore expose:

- normalized signatures;
- typed hole reports;
- internal claims derived from properties;
- structured diagnostics;
- evidence records bound to stable provenance hashes.

## Guide-level explanation

### Checking a file

```bash
spore check src/main.sp
spore check --json src/main.sp
sporec query-hole src/main.sp ?build_response --json
```

A successful check may still report open holes. A complete realization has no
open holes and has evidence for the required claims.

### Properties become claims

```spore
fn add(a: I64, b: I64) -> I64
properties {
    commutative(a: I64, b: I64): add(a, b) == add(b, a)
}
{
    a + b
}
```

The parser records a source property. SEP-0002 first checks the property body as
an ordinary Spore expression whose result type must be `Bool` and whose required
effects must fit inside the enclosing effect context. After that check, the
compiler lowers the property into an internal `Claim` with normalized subject,
parameters, predicate expression, effect context, and source span.

A `Claim` may originate from a source `properties` item, a refinement obligation,
a budget check, an effect check, or a validator. Source properties and
refinement obligations share the same `Claim` and `EvidenceRecord` structure so
tools do not need a separate property protocol.

### Evidence records

Evidence records answer: what was checked, by which checker, against which
realization, with which result?

```text
EvidenceRecord
├── subject
├── claim
├── checker
├── result
└── provenance
```

## Reference-level explanation

### Pipeline

```text
parse(source) -> Ast
resolve(ast) -> Hir
check(hir) -> TypedHir
verify(typed_hir) -> VerificationBundle
codegen(typed_hir) -> Artifact
```

### HIR responsibilities

HIR owns:

- canonical Base Signature representation;
- Intent Signature representation;
- import and visibility resolution;
- effect name resolution;
- property-to-claim lowering stubs;
- hole registration.

### TypedHIR responsibilities

TypedHIR owns:

- bidirectional type checking;
- trait resolution;
- effect checking;
- budget shape checking;
- hole report generation;
- Claim construction from properties;
- realization validation inputs.

### EvidenceRecord structure

```text
EvidenceRecord
├── subject
│   ├── function
│   ├── hole
│   ├── module
│   └── artifact
├── claim
│   ├── type
│   ├── effect
│   ├── budget
│   ├── property
│   └── validator
├── checker
│   ├── name
│   ├── revision
│   └── config
├── result
│   ├── passed
│   ├── failed
│   ├── unknown
│   └── skipped
└── provenance
    ├── signature_hash
    ├── intent_hash
    ├── property_hash
    ├── realization_hash
    ├── checker_hash
    └── dependency_hashes
```

### Hash boundaries

`signature_hash` covers the normalized Base Signature.

`intent_hash` covers `uses`, `budget`, and `properties` after canonicalization.

`property_hash` covers the normalized property set attached to a subject.

`realization_hash` covers a concrete completed body or generated artifact.

`checker_hash` identifies the checker implementation and configuration.

`dependency_hashes` bind imported modules and package inputs.

For property claims, `result.passed` means the checker established the property
for the checked subject. `result.failed` means the checker produced a failing
case, counter-witness, or direct contradiction. `result.unknown` means the
property was well typed but the checker could not decide it with the available
analysis or evidence. `result.skipped` means the checker did not run.

A well-typed property with `unknown` evidence remains visible to tools and
reviewers. It is not the same as a type error and does not by itself reject
compilation. Release gates and package policies may choose stricter treatment
for unknown evidence.

### Watch mode

`spore watch --json` emits newline-delimited events:

```json
{"event":"compile_result","file":"src/main.sp","status":"ok","diagnostics":[]}
{"event":"hole_graph_update","holes_total":1,"ready_to_fill":1,"blocked":0}
{"event":"evidence_update","records_added":3,"records_failed":0}
```

## Human experience impact

Compiler output stays readable while still mapping to stable machine records.
Evidence lets reviewers see which properties and budgets were checked rather
than inferring trust from a green command alone.

## Agent experience impact

Agents can consume diagnostics, HoleReports, claims, and evidence without text
scraping. Failed evidence gives repair direction.

## Structured representation / protocol impact

The machine projection centers on shared records:

```text
Diagnostic
HoleReport
Claim
EvidenceRecord
VerificationBundle
```

Default text, JSON, LSP, and watch outputs are renderings over these records.
SEP-0010 owns the concept registry and explain protocol layered over these same
records. SEP-0010 teaching metadata is optional metadata over these shared
records. It does not change the identity, hash, or required fields of
`Diagnostic`, `HoleReport`, `Claim`, `EvidenceRecord`, or `VerificationBundle`.

## Diagnostics impact

Diagnostic categories are:

| Prefix  | Category                       |
| ------- | ------------------------------ |
| `E0xxx` | Type errors                    |
| `F0xxx` | Effect violations              |
| `B0xxx` | Budget violations              |
| `H0xxx` | Hole diagnostics               |
| `P0xxx` | Property and claim diagnostics |
| `M0xxx` | Module and package errors      |
| `W0xxx` | Warnings                       |

Property diagnostics include failed property checks, counter-witnesses, and
properties that reached an open hole. A property body that does not check as
`Bool` is reported as a type diagnostic because the source expression is ill
typed. A property body that checks as `Bool` but fails or remains unknown is
reported as a property or claim diagnostic because the source shape is valid and
the evidence result is the issue.

Diagnostic teaching metadata, concept references, and `spore explain` behavior
are owned by SEP-0010.

## Drawbacks

Evidence records add storage and schema complexity. The benefit is a durable,
inspectable audit trail for human and Agent workflows.

Separating signature, intent, property, and realization hashes requires users to
learn more than one identity concept. Tooling should render them with labels and
short forms.

## Alternatives considered

### Text-only diagnostics

Rejected because Agents and CI need stable structured payloads.

### Single full-content hash

Rejected because body-only realization changes should not force every dependent
to treat the callable boundary as changed.

### Source-level evidence

Rejected because evidence should be generated by checkers and bound to
provenance, not hand-written as trusted source text.

## Prior art

Rust influenced diagnostics and HIR structure. Elm influenced human-readable
errors. Unison influenced content-addressing. Proof assistants influenced the
claim/evidence separation.

## Backward compatibility and migration

Tooling must migrate from older diagnostic prefixes and hash labels to signature
model names. JSON consumers should key on explicit record fields rather than parse
human messages.

## Unresolved questions

1. Should evidence records be persisted beside build artifacts or in package lock data?
2. How should skipped and unknown evidence affect release gates?
3. Should checker configuration be normalized as source text, JSON, or a typed IR?
