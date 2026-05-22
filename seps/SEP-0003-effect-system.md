---
sep: 3
title: "SEP-0003: Effect System"
status: Draft
type: Standards Track
authors:
  - Zhan Rongrui
created: 2026-03-31
requires:
  - 1
  - 2
discussion: "https://github.com/spore-lang/spore-evolution/discussions/3"
pr: null
superseded_by: null
---

# SEP-0003: Effect System

> **Executive Summary**: Defines runtime effect capabilities inside Signature v2's `uses [...]` capability surface. SEP-0003 owns effect declarations, handlers, alias expansion, and runtime-effect checking; logical and checker capabilities are interpreted by the hole, property, and evidence layers.

## Summary

Spore effects describe observable interactions with the outside world. A
function lists required capabilities in `uses [...]`:

```spore
effect Console {
    fn println(msg: Str) -> ()
}

fn greet(name: Str) -> ()
uses [Console]
{
    perform Console.println("hello " + name)
}
```

`uses` is broader than runtime effects. Runtime effect names are checked by this
SEP. Other capability names may guide property checking, generation, or Agent
behavior and are interpreted outside this SEP.

## Motivation

Effects make external interactions visible at the signature boundary. They help
humans review code, help Agents avoid unauthorized operations, and let Platforms
supply replaceable handlers.

Runtime effect checking should not absorb every non-type constraint. Signature
v2 therefore treats `uses` as a capability surface, while this SEP specifies the
runtime-effect subset.

## Guide-level explanation

### Declaring effects

```spore
effect FileRead {
    fn read(path: Path) -> Str ! IoError
}

effect Clock {
    fn now() -> Instant
}
```

### Using effects

```spore
fn load(path: Path) -> Str ! IoError
uses [FileRead]
{
    perform FileRead.read(path)
}
```

The body may only perform runtime effects included in the declared capability
surface or provided by a narrower local handler context.

### Effect aliases

```spore
effect CliIO = Console | FileRead | FileWrite

fn run(path: Path) -> () ! IoError
uses [CliIO]
{
    ?run_body
}
```

Aliases expand to sets of atomic runtime effects.

### Handlers

```spore
handler MockConsole for Console {
    fn println(msg: Str) -> () { self.output.push(msg) }
}

handle {
    greet("spore")
} with {
    use MockConsole { output: [] }
}
```

Handlers discharge or reinterpret runtime effects inside a lexical scope.

### Capability surface and checker capabilities

A signature may include capability names that are not runtime effects:

```spore
fn sort[T: Ord](xs: List[T]) -> List[T]
uses [Compare]
properties {
    ordered(xs: List[T]): is_ordered(sort(xs))
}
{
    ?sort_body
}
```

`Compare` can be consumed by a checker or Agent even when it has no runtime
effect declaration.

## Reference-level explanation

### Runtime effect set

Each checked body has an available runtime effect set `E_available`. A `perform`
operation requiring effect `E` is valid when `E` is in the available set after
alias expansion and local handler narrowing.

### Capability resolution

The compiler resolves names in `uses [...]` into:

- runtime effects owned by this SEP;
- aliases that expand to runtime effects;
- non-runtime capabilities passed through for other tooling layers.

Unknown names are diagnostics unless a project declares them as tool
capabilities in manifest metadata.

### Handler checking

A handler must implement every operation of the effect it handles. Handler
methods use ordinary function typing and may declare their own required
capabilities.

### Interaction with properties

Effect purity and determinism facts may be inferred and surfaced as evidence,
but source properties remain in the `properties` block and are lowered by
SEP-0006.

## Human experience impact

A reader can inspect `uses [...]` to know what outside-world interaction or tool
capability a function depends on. Runtime effects stay explicit without forcing
separate source keywords for checker-only needs.

## Agent experience impact

HoleReport exposes `capability_context`, allowing Agents to avoid proposing
fills that require unavailable runtime effects or checker capabilities.

## Structured representation / protocol impact

Effect checking emits normalized runtime-effect metadata:

```text
CapabilityContext
├── declared[]
├── runtime_effects[]
├── tool_capabilities[]
├── active_handlers[]
└── discharged_effects[]
```

SEP-0005 embeds this context in HoleReport. SEP-0006 may embed it in evidence.

## Diagnostics impact

Effect diagnostics use `C0xxx` codes:

- unknown runtime effect
- operation performed outside available effect set
- missing handler method
- handler capability escape
- platform does not provide required runtime effect

## Drawbacks

A shared `uses` surface means tools must agree on capability names. Manifest
metadata and package documentation should define non-runtime names clearly.

## Alternatives considered

### Runtime effects only in `uses`

Rejected because property checkers and Agents need the same concise signature
surface for non-runtime capabilities.

### Separate checker capability keyword

Rejected because it fragments intent and makes signatures harder to scan.

## Prior art

Koka influenced algebraic effects. Roc influenced platform-provided handlers.
Rust influenced explicit trait boundaries, though Spore separates traits from
runtime effects.

## Backward compatibility and migration

Existing runtime effect declarations stay conceptually valid. Signatures that
used `uses [...]` for runtime effects continue to map to the runtime-effect
subset; additional capability names require manifest or tooling interpretation.

## Unresolved questions

1. Should non-runtime capabilities be namespaced by package?
2. Should capability aliases be allowed to mix runtime and non-runtime names?
3. How much inferred purity and determinism data should be visible in normal diagnostics?
