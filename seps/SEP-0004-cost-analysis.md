---
sep: 4
title: "SEP-0004: Budget Constraints & Realization Shape"
status: Draft
type: Standards Track
authors:
  - Zhan Rongrui
created: 2026-03-31
requires:
  - 1
  - 2
  - 3
discussion: "https://github.com/spore-lang/spore-evolution/discussions/4"
pr: null
superseded_by: null
---

# SEP-0004: Budget Constraints & Realization Shape

> **Executive Summary**: Replaces positional resource accounting with named realization-shape budgets. A `budget { ... }` block declares integer upper bounds over implementation shape, enabling human review, Agent filling, and EvidenceRecord generation without encoding machine-resource formulas in source signatures.

## Summary

A budget is a quantitative constraint on realization shape:

```spore
fn sort(xs: List[I64]) -> List[I64]
budget {
    branches: 4
    nesting: 3
    recursion: 0
    parallelism: 1
}
properties {
    ordered(xs: List[I64]): is_ordered(sort(xs))
}
{
    ?sort_body
}
```

Budget fields are named integer upper bounds. The initial field set is:

| Field         | Meaning                                             |
| ------------- | --------------------------------------------------- |
| `branches`    | Conditional or match branch count upper bound       |
| `nesting`     | Maximum nested control-expression depth             |
| `recursion`   | Maximum recursive-call depth; `0` forbids recursion |
| `parallelism` | Maximum parallel fan-out                            |
| `calls`       | Function-call count upper bound                     |
| `effects`     | Effect operation count upper bound                  |
| `holes`       | Remaining hole count upper bound                    |

## Motivation

The signature model uses budgets to shape valid realizations. The question is not an
abstract resource formula; it is whether the implementation is small enough,
reviewable enough, and constrained enough for humans, Agents, and checkers to
trust.

Named fields are preferable because each constraint is readable, independently
checkable, and extensible without positional migration.

## Guide-level explanation

### No budget required

Most functions do not need an explicit budget:

```spore
fn add(a: I64, b: I64) -> I64 { a + b }
```

### Review-oriented budget

```spore
fn classify(input: Event) -> Category
budget {
    branches: 6
    nesting: 2
    calls: 4
}
{
    ?classify_body
}
```

This says the realization should stay small and flat enough to review.

### Agent-oriented budget

```spore
fn fetch_all(urls: List[Url]) -> List[Page] ! NetworkError
uses [Http, Spawn]
budget {
    parallelism: 4
    effects: 8
    nesting: 3
}
{
    ?fetch_all_body
}
```

The budget tells an Agent which implementation shapes are acceptable before it
writes a fill.

### Properties and budget together

Properties define validity. Budget defines acceptable realization shape.

```spore
fn dedupe[T: Eq + Hash](xs: List[T]) -> List[T]
budget {
    branches: 3
    nesting: 2
}
properties {
    idempotent(xs: List[T]): dedupe(dedupe(xs)) == dedupe(xs)
    preserves_members(xs: List[T]): same_members(dedupe(xs), xs)
}
{
    ?dedupe_body
}
```

## Reference-level explanation

### Budget item grammar

```ebnf
BudgetBlock = "budget" "{" { BudgetItem } "}" ;
BudgetItem  = Ident ":" IntLiteral ;
```

All values are non-negative integer literals. Field names are resolved by the
budget checker. Unknown fields are diagnostics unless accepted by a project
extension.

### Built-in fields

`branches` counts user-authored conditional alternatives, including match arms
and `if` alternatives.

`nesting` counts nested control expressions and nested scoped concurrency
expressions.

`recursion` counts self-recursive depth admitted by the realization. A value of
`0` rejects direct or mutual recursion in the checked realization.

`parallelism` counts maximum scoped fan-out created by concurrency primitives.

`calls` counts ordinary function-call sites in the realization body.

`effects` counts effect operation sites after handler expansion.

`holes` counts remaining holes admitted in the realization. Public complete
artifacts normally use `holes: 0`.

### Checking relation

For a realization `r` and budget field `f`, checking computes `shape(r, f)` and
requires:

```text
shape(r, f) <= declared(f)
```

When a field is omitted, the checker imposes no source-level upper bound for
that field.

### Hole projection

At a hole site, SEP-0005 receives the enclosing `budget_context` plus any known
shape already committed before and around the hole. The context is advisory for
candidate ranking and normative for accepting a proposed realization.

### Evidence projection

SEP-0006 records budget evidence per checked field:

```text
claim: budget.nesting <= 3
result: passed
observed: 2
```

## Human experience impact

Budgets make review criteria explicit. A reviewer can reject an implementation
because it violates a stated shape bound, not because it feels too complex.

## Agent experience impact

Agents can use budgets before generating code, while ranking candidates, and
after verification. Budget failures become structured repair signals.

## Structured representation / protocol impact

```text
BudgetConstraint
├── field
├── limit
├── source_span
└── owner_signature

BudgetEvidence
├── field
├── limit
├── observed
└── result
```

HoleReport embeds relevant constraints under `budget_context`.

## Diagnostics impact

Budget diagnostics use `B0xxx` codes:

| Code    | Name                 | Meaning                                                     |
| ------- | -------------------- | ----------------------------------------------------------- |
| `B0101` | budget-exceeded      | Observed realization shape exceeds a declared field         |
| `B0102` | unknown-budget-field | Field is not built in and not enabled by extension metadata |
| `B0103` | invalid-budget-value | Value is not a non-negative integer literal                 |
| `B0201` | recursion-disallowed | Realization uses recursion while `recursion: 0`             |
| `B0202` | hole-budget-exceeded | Realization leaves more holes than allowed                  |

## Drawbacks

Budgets constrain shape, not wall-clock performance or host resource usage. They
are review and realization constraints, not benchmarking claims.

Counting rules must be stable enough for tools and formatters. The checker must
therefore publish observed counts in diagnostics and evidence.

## Alternatives considered

### Positional resource vectors

Rejected because positional fields are opaque, look like machine-resource
accounting, and are hard to extend.

### Complexity notation in signatures

Rejected because asymptotic notation belongs to algorithm analysis, not to the
core signature realization workflow.

### No quantitative constraints

Rejected because Agents and reviewers need compact limits for acceptable
implementation shape.

## Prior art

Cyclomatic complexity metrics, lint thresholds, and structured-concurrency
fan-out limits all inform this design. Spore brings those ideas into the
signature so tools can consume them before code exists.

## Backward compatibility and migration

This is a breaking replacement of earlier resource-accounting syntax. Migration
should only introduce a `budget` field when the old annotation represented a
reviewable realization-shape constraint. Routine library operations should often
omit budgets.

## Unresolved questions

1. Should project manifests define default budgets for public functions?
2. Should extension fields be namespaced?
3. Should generated realizations be allowed to temporarily exceed budget during repair loops?
