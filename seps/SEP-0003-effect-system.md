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

### State primitive effects

A state primitive effect is a standard atomic effect whose purpose is to carry a
minimal state or event boundary without exposing user-level mutation. State
primitive effects are still ordinary atomic effects for `uses` resolution,
handler checking, and HoleReport effect context.

An effect belongs to the state primitive set only when it satisfies all of these
membership rules:

1. It cannot be defined as a composition of other effects.
2. It carries one minimal state or event responsibility.
3. It is broadly useful across application, test, and tooling contexts.
4. A Platform package can provide a host handler and an in-memory mock handler.
5. Its operation set is small and stable enough to be part of the standard
   effect surface.

The initial state primitive set is defined by SEP-0009. Adding a new state
primitive effect requires a separate SEP because it changes the standard effect
taxonomy and the Platform conformance surface.

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
effect Console {
    fn println(msg: Str) -> ();
}

effect Output[T] {
    fn emit(value: T) -> ();
}

handler MockConsole handles [Console] uses [Output[Str]] {
    impl Console {
        fn println(self, msg: Str) -> () {
            perform Output.emit(msg)
        }
    }
}

handle {
    greet("spore")
} with {
    use MockConsole {}
}
```

Handlers discharge or reinterpret effects inside a lexical scope. The example
omits the `Output[Str]` handler; the enclosing test or Platform scope must
install it explicitly.

### Handler state policy

Handler fields are immutable runtime configuration. Handler method bodies may
read `self` and fields on `self`, but they may not assign to `self.field` or
otherwise update handler instance payload. Spore does not add `mut`, `mut self`,
or mutable handler fields for stateful handlers.

Stateful handler use cases route through state primitive effects such as
`Cell`, `Output`, `Map`, `Clock`, and `Random`. A handler that needs state lists
the relevant primitive effects in its own `uses` clause and performs those
effects in method bodies.

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

State primitive effects resolve as atomic effects. Their primitive status
affects standard-library and Platform obligations, not the surface-expansion
algorithm.

### Handler checking

A handler targets a surface expression and must implement every operation of the
atomic effects it claims to discharge. Handler methods live inside an
`impl Effect { ... }` block, write `self` as the first parameter, use ordinary
function typing, and may declare their own required effects. The receiver is
read-only.

Handler instances are lexical and task-local. Installing a handler with
`handle ... with` affects only the dynamic extent of that expression inside the
installing task. Spawned or sibling tasks do not inherit the handler instance
unless that handler is installed in their own dynamic extent.

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
Handler fields are instance payload and do not participate in `signature_hash`,
`intent_hash`, or `property_hash`. Hashes cover callable boundaries and intent
metadata; handler payload values are runtime configuration for a specific
installation.

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
