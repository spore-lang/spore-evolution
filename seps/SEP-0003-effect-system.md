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

> **Executive Summary**: Defines the signature model's `uses` effect surface. SEP-0003 owns atomic effect declarations, surface declarations, handlers, surface expansion, and effect checking. Non-effect constraints belong to `budget`, `properties`, or future tooling metadata rather than `uses`.

## Summary

Spore effects describe observable interactions with the outside world. A
function lists its ambient effect surface in `uses`:

```spore
effect Console {
    fn println(msg: Str) -> ();
}

fn greet(name: Str) -> ()
uses [Console]
{
    perform Console.println("hello " + name)
}
```

`uses` is an effect surface. Every item in a `uses` surface expression must
resolve to an atomic effect or to a named surface that expands to atomic
effects.

## Motivation

Effects make external interactions visible at the signature boundary. They help
humans review code, help Agents avoid unavailable operations, and let Platforms
supply replaceable handlers.

Effect checking should not absorb every non-type constraint. The signature model keeps
runtime interaction in `uses`, realization shape in `budget`, and semantic
requirements in `properties`.

## Guide-level explanation

### Declaring effects

```spore
effect FileRead {
    fn read(path: Path) -> Str ! IoError;
}

effect Clock {
    fn now() -> Instant;
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

The body may only perform effects included in the declared effect surface or
provided by a narrower local handler context. Effect operations are addressed by
qualified names such as `Console.println` or `FileRead.read`.

### Surface declarations

```spore
surface CliIO = [Console, FileRead, FileWrite]

fn run(path: Path) -> () ! IoError
uses [CliIO]
{
    ?run_body
}

fn app(path: Path) -> () ! IoError
uses [CliIO, Clock]
{
    ?app_body
}
```

Surfaces expand to finite sets of atomic effects. They are not sum types,
logical OR, or error unions.

### Handlers

```spore
handler MockIO for [Console] {
    fn Console.println(msg: Str) -> () { self.output.push(msg) }
}

handle {
    greet("spore")
} with {
    use MockIO { output: [] }
}
```

Handlers discharge or reinterpret effects inside a lexical scope.

### Non-effect requirements

Properties, checker guidance, and Agent-generation requirements do not appear in
`uses` surface expressions. They should be expressed through `properties`,
`budget`, package metadata, or future tooling metadata owned by a separate SEP.

## Reference-level explanation

### Effect set

Each checked body has an available effect set `E_available`. A `perform`
operation requiring effect `E` is valid when `E` is in the available set after
surface expansion and local handler narrowing.

### Surface resolution

The compiler resolves names in a `uses` surface expression into:

- atomic effects owned by this SEP;
- named surfaces that expand to atomic effects.

Unknown names are diagnostics. Surface expansion is unordered, duplicate-free,
and recursive cycles are diagnostics.

### Handler checking

A handler targets a surface expression and must implement every operation of the
atomic effects it claims to discharge. Handler methods name operations with a
qualified identifier such as `Console.println`. Handler methods use ordinary
function typing and may declare their own required effects.

### Interaction with properties

Effect purity and determinism facts may be inferred and surfaced as evidence,
but source properties remain in the `properties` block and are lowered by
SEP-0006.

## Human experience impact

A reader can inspect a function's `uses` surface expression to know what
outside-world interaction it depends on. Effect names stay explicit without
mixing runtime behavior with checker-only guidance.

## Agent experience impact

HoleReport exposes `effect_context`, allowing Agents to avoid proposing fills
that require unavailable effects.

## Structured representation / protocol impact

Effect checking emits normalized effect metadata:

```text
EffectContext
├── declared_surface
├── expanded_effects[]
├── active_handlers[]
└── discharged_effects[]
```

SEP-0005 embeds this context in HoleReport. SEP-0006 may embed it in evidence.

## Diagnostics impact

Effect diagnostics use `F0xxx` codes:

- unknown effect
- operation performed outside available effect set
- missing handler method
- handler effect escape
- platform does not provide required effect

## Drawbacks

Using a separate `surface` declaration adds one more noun to the language.
That cost is acceptable because it keeps `effect` for atomic protocols and keeps
`uses` free of overloaded `|` syntax. Tools that need non-effect guidance still
require a separate surface rather than piggybacking on `uses`. The benefit is
that the language effect model stays clear and handler checking remains local.

## Alternatives considered

### Broader `uses` surface

Rejected because mixing effects with checker or Agent guidance made `uses`
an unclear heterogeneous bucket.

### Separate checker keyword in core syntax

Deferred because checker-specific guidance needs its own design rather than a
second ad hoc signature list in SEP-0003.

## Prior art

Koka influenced algebraic effects. Roc influenced platform-provided handlers.
Rust influenced explicit trait boundaries, though Spore separates traits from
effects.

## Backward compatibility and migration

Existing atomic effect declarations stay conceptually valid. Legacy shorthand
forms such as `effect IO = A | B` should migrate to `surface IO = [A, B]`.
Signatures that used `uses [A, B]` for effects continue to map directly, though
surface expressions may now mix atomic effects and named surfaces. Non-effect
names that were previously placed in `uses` should move to properties, package
metadata, or a future tooling surface.

## Unresolved questions

1. Should effect names be partitioned by namespace?
2. Should named surfaces be allowed to reference package-qualified effect names?
3. How much inferred purity and determinism data should be visible in normal diagnostics?
