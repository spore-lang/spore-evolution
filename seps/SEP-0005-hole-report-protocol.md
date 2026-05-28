---
sep: 5
title: "SEP-0005: Hole System & HoleReport Protocol"
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
discussion: "https://github.com/spore-lang/spore-evolution/discussions/5"
pr: null
superseded_by: null
---

# SEP-0005: Hole System & HoleReport Protocol

> **Executive Summary**: Defines holes as typed absence constrained by Base Signature and Intent Signature context, and normatively specifies the HoleReport records emitted for those holes. HoleReport exposes expected type, visible bindings, effect context, budget context, property context, candidates, dependencies, and confidence data. Agent workflows and candidate rankers are informative projections over this data rather than a required protocol state machine.

## Summary

A hole is written `?name` or `?name: Type` in expression position. Programs with
holes are partial, not broken. The compiler accepts them and emits structured
HoleReports.

```spore
fn validate(order: Order) -> ValidOrder ! ValidationError
uses [DbRead]
budget {
    branches: 5
    nesting: 2
    holes: 1
}
properties {
    accepted(order: Order): match validate(order) {
        ok _ => true,
        fail _ => has_validation_reason(order),
    }
}
{
    ?validate_body
}
```

The hole is typed absence constrained by the surrounding signature and context.

This SEP normatively defines hole syntax, HoleReport records, and the hole
dependency graph. It does not normatively define an Agent workflow state
machine, candidate scoring formula, or human teaching projection. Those topics
are informative guidance here or belong to SEP-0010 when they teach users how to
read HoleReport data.

## Motivation

Traditional unfinished code is opaque to tools. Spore makes incomplete positions
compiler-visible so a human or Agent can receive enough context to propose a
property-preserving realization.

HoleReport is the collaboration boundary. It exposes not only type context, but
also effects, budgets, and properties. Human-facing renderers and Agents may
project this data differently, but the shared record remains the same.

## Guide-level explanation

### Basic holes

```spore
fn add_tax(amount: Money) -> Money {
    ?taxed_amount
}
```

The checker reports the expected type of `?taxed_amount` from return position.

### Annotated holes

```spore
let normalized = ?normalize: Email;
```

The annotation helps the checker and Agent when context is otherwise ambiguous.

### Multiple holes

```spore
fn process(order: Order) -> Receipt ! PaymentError
uses [PaymentGateway]
budget { holes: 2 }
{
    let checked = ?validate_order;
    ?charge_payment
}
```

The dependency graph determines which holes can be realized first.

### Reading HoleReports

A HoleReport is useful to humans, Agents, and tools because the same per-hole
record carries the missing type, visible context, effect context, budget context,
property obligations, candidate data, and dependency edges. Workflow-specific
states are informative guidance rather than part of the required record shape.

## Reference-level explanation

### Hole syntax

```ebnf
HoleExpr = "?" [ Ident ] [ ":" TypeExpr ] ;
```

Holes are valid only in expression positions. Type holes are a separate design
space and are not specified here.

### Normative HoleReport fields

The per-hole object includes:

| Field                  | Meaning                                                |
| ---------------------- | ------------------------------------------------------ |
| `name`                 | Developer-assigned hole name                           |
| `display_name`         | Source spelling with `?`                               |
| `location`             | File and span                                          |
| `expected_type`        | Type the realization must produce                      |
| `type_inferred_from`   | Explanation of the expected type                       |
| `function`             | Enclosing callable name                                |
| `enclosing_signature`  | Normalized Base Signature and Intent Signature summary |
| `bindings`             | Visible local bindings and types                       |
| `binding_dependencies` | Data-flow among visible bindings                       |
| `effect_context`       | Available effect surface and handler context           |
| `budget_context`       | Relevant budget constraints and observed shape data    |
| `property_context`     | Properties the realization must preserve               |
| `failures_to_handle`   | Failure variants still not handled at the site         |
| `candidates`           | Visible functions or templates that may fit            |
| `dependent_holes`      | Holes unlocked by this realization                     |
| `confidence`           | Type and candidate confidence data                     |
| `rejection_reasons`    | Structured reasons from failed verification attempts   |

The per-hole object is the normative schema boundary for tools. JSON producers
may add versioned optional fields, but they must preserve the meaning of these
fields when present. A batch response wraps per-hole objects in a `holes` array
and may include a `dependency_graph` object. A single-hole query returns one
per-hole object directly.

SEP-0010 may attach concept references and render these fields for teaching, but
it does not add required HoleReport fields. Optional teaching metadata is
outside the normative HoleReport schema unless a later SEP moves it here.

### Type inference rule

The hole's expected type is the intersection of constraints from return
position, annotations, function arguments, match arms, operators, and sibling
branch types. If constraints conflict, the nearest syntactic constraint is used
for reporting and a diagnostic is emitted.

### Effect context

`effect_context` includes the declared surface expression, expanded effect set,
active handlers, and discharged effects.

### Budget context

`budget_context` includes inherited budget fields, observed shape around the
hole, and remaining admissible shape when it can be computed structurally.

### Property context

`property_context` includes properties attached to the enclosing signature plus
any local obligations produced by refinements or earlier checks.

### Dependency graph

Edges are classified as:

| Kind       | Meaning                                               |
| ---------- | ----------------------------------------------------- |
| `type`     | Later hole type depends on earlier realization        |
| `value`    | Later hole binding depends on earlier value           |
| `effect`   | Effect availability changes after earlier realization |
| `budget`   | Shape allowance depends on earlier realization        |
| `property` | Property obligation depends on earlier realization    |

The graph must be acyclic for automatic scheduling.

## Human experience impact

Holes let developers sketch architecture with signatures and properties first.
Reports are concrete enough to review one missing realization at a time.

## Agent experience impact

Agents can rank candidates using typed context and reject proposals that exceed
effects, budgets, or properties before asking for human review.

## Structured representation / protocol impact

Batch output:

```json
{
  "holes": [
    {
      "name": "validate_body",
      "expected_type": "ValidOrder ! ValidationError",
      "effect_context": { "declared_surface": "[DbRead]" },
      "budget_context": { "branches": { "limit": 5 } },
      "property_context": { "properties": ["accepted"] }
    }
  ],
  "dependency_graph": {
    "edges": []
  }
}
```

Single-hole queries return the same per-hole object directly.

Human-facing educational renderings of HoleReport records are owned by SEP-0010.
Those renderings must stay projections over the same HoleReport data rather than
forming a separate hole protocol. SEP-0005 remains the owner of per-hole field
names, dependency graph shape, and batch/single-hole query shape.

## Diagnostics impact

Hole diagnostics use `H0xxx` codes:

| Code    | Name                     | Meaning                                            |
| ------- | ------------------------ | -------------------------------------------------- |
| `H0101` | hole-report              | Informational report for an open hole              |
| `H0102` | duplicate-hole-name      | Hole name reused in a module                       |
| `H0201` | hole-outside-expression  | Hole appears outside permitted expression position |
| `H0301` | circular-hole-dependency | Dependency graph has a cycle                       |
| `H0401` | realization-rejected     | Proposed fill failed verification                  |

## Drawbacks

HoleReports can be large. Tools should support compact summaries and on-demand
single-hole queries.

Automated realization can overfit to properties that are too weak. Human review
and richer property design remain important.

## Alternatives considered

### Anonymous holes only

Rejected because named holes make CLI queries, reviews, and Agent coordination
stable.

### Holes as hard errors

Rejected because partial programs are a core collaboration state.

### Separate Agent metadata files

Rejected because the compiler can derive more reliable context directly from
source and typed IR.

## Informational appendix: Realization workflow notes

This workflow is an informative reference loop for Agents and tools. A
conforming HoleReport producer is not required to expose these states, and a
conforming Agent is not required to use this exact state machine.

```text
DISCOVER -> ANALYZE -> PROPOSE -> VERIFY -> ACCEPT or REJECT
```

A proposed fill is reviewable when it is checked against type, effect, budget,
and property context from the HoleReport and either passes those checks or
produces evidence states that the selected policy accepts.

## Informational appendix: Reference candidate ranker

Implementations may rank candidates using the fields exposed by HoleReport. One
reference ranker combines type match, budget fit, required-effect fit, and error
coverage. This ranker is informative. Tools may use a different ranker when they
preserve the normative HoleReport data.

```text
overall = 0.40 * type_match
        + 0.20 * budget_fit
        + 0.25 * required_effects_fit
        + 0.15 * error_coverage
```

## Prior art

Agda, Idris, GHC, and Lean influenced typed holes. Spore differs by making
machine-readable reports the primary design constraint while keeping Agent
workflows as replaceable policy.

## Backward compatibility and migration

Hole syntax remains source-compatible with named holes. Payload consumers must
adapt from older resource-oriented fields to `effect_context`, `budget_context`,
and `property_context`.

## Unresolved questions

1. Should type holes be specified in this SEP or a separate one?
2. Should failed realization attempts be persisted for Agent learning?
3. How should cross-module hole dependencies be represented?
