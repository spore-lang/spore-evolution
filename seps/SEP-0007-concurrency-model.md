---
sep: 7
title: "SEP-0007: Concurrency Model"
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
discussion: "https://github.com/spore-lang/spore-evolution/discussions/7"
pr: null
superseded_by: null
---

# SEP-0007: Concurrency Model

> **Executive Summary**: Defines structured concurrency under the signature model. Concurrency is introduced through scoped expressions and effects, while acceptable fan-out and nesting are constrained by `budget` fields and recorded in evidence.

## Summary

Spore provides structured concurrency primitives:

- `parallel_scope { ... }`
- `spawn { ... }`
- `task.await`
- `select { ... }`
- `Task[T, E]`
- `Channel[T]`

A concurrent function declares the required effects and may constrain its
realization shape with budget fields:

```spore
fn fetch_all(urls: List[Url]) -> List[Page] ! NetworkError
uses [Http, Spawn]
budget {
    parallelism: 4
    nesting: 3
    effects: 8
}
{
    ?fetch_all_body
}
```

## Motivation

Unstructured concurrency creates lifetime leaks and hard-to-review fan-out.
Spore treats concurrency as scoped: spawned tasks cannot outlive their parent
scope, and signature budgets can cap the shape of concurrent realizations.

## Guide-level explanation

### Scoped spawning

```spore
fn fetch_pair(a: Url, b: Url) -> Pair[Page, Page] ! NetworkError
uses [Http, Spawn]
budget { parallelism: 2 }
{
    parallel_scope {
        let left = spawn { fetch(a) };
        let right = spawn { fetch(b) };
        Pair { first: left.await?, second: right.await? }
    }
}
```

### Cancellation

When a scope exits early, unawaited child tasks are cancelled cooperatively.
Cancellation checkpoints happen at effect operations and explicit cancellation
checks inside long-running pure computation.

### Channels

```spore
let channel = Channel.new[I64](capacity: 16);
```

Channels are bounded and typed. Senders and receivers cannot escape their
structured ownership rules.

### Selection

```spore
select {
    value = rx.recv() => value,
    timeout(1000) => fallback(),
}
```

`select` waits for the first ready arm.

## Reference-level explanation

### Effect requirement

`spawn`, scoped task creation, and task scheduling require the `Spawn` effect.
Channel operations require the channel effects defined by the standard library
or platform package that supplies them.

### Scope rule

Every task belongs to exactly one lexical `parallel_scope`. A task must be
awaited, cancelled, or automatically cancelled before the scope returns.

### Budget interaction

`parallelism` bounds maximum fan-out inside the realization. `nesting` bounds
nested concurrency scopes together with other control expressions. `effects`
can bound effect operation sites performed by concurrent branches.

### Type rule for tasks

If expression `e` checks as `T ! E`, then `spawn { e }` checks as `Task[T, E]`.
Awaiting a `Task[T, E]` yields `T` and reintroduces `E` at the await site. A
non-throwing spawned expression uses the empty error boundary, represented as
`Task[T, Never]`.

### Determinism and properties

Schedule-independent behavior is expressed as source properties. The concurrency
checker may emit claims about task lifetime, cancellation coverage, and channel
boundary correctness for evidence generation.

## Human experience impact

Concurrency appears at the signature boundary through `uses [Spawn]` and shape
budgets. Reviewers can see whether fan-out is intended before reading the body.

## Agent experience impact

Agents filling concurrent holes receive effect and budget context, making it
possible to reject unbounded fan-out or missing awaits before proposing code.

## Structured representation / protocol impact

Concurrency verification emits evidence claims such as:

```text
claim: task_scope_closed
claim: parallelism <= 4
claim: all_spawned_tasks_awaited_or_cancelled
```

HoleReport may include concurrency-specific budget and dependency context.

## Diagnostics impact

Concurrency diagnostics use existing categories:

- `F0xxx` for missing effects;
- `B0xxx` for fan-out or nesting budget violations;
- `P0xxx` when a schedule-related property fails;
- `W0xxx` for suspicious but accepted patterns.

## Drawbacks

Structured scopes reject some fire-and-forget patterns. Users must model long
running services through explicit platform or supervisor abstractions.

Budgeted fan-out is conservative when the checker cannot prove a tighter bound.

## Alternatives considered

### Unstructured tasks

Rejected because tasks escaping their lexical scope make lifetime and realization
shape difficult to verify.

### Async coloring

Rejected because splitting function colors makes refactors viral. Spore uses
effects and handlers instead.

### Runtime-only concurrency checks

Rejected because the signature model needs Agent-visible constraints before a
realization is written.

## Prior art

Swift task groups, Kotlin structured concurrency, Koka effect handlers, and Roc
platform boundaries inform this model.

## Backward compatibility and migration

Concurrent code should move fan-out constraints into `budget { parallelism: N }`
and retain explicit `uses [Spawn]` effect declarations.

## Unresolved questions

1. Should cancellation checkpoints be inserted by tools or only written by users?
2. Should channel capacity participate in budget checking?
3. How should deterministic scheduling properties be generated for common patterns?
