---
sep: 9
title: "SEP-0009: Standard Library Surface"
status: Draft
type: Standards Track
authors:
  - Spore Contributors
created: 2026-04-01
requires: [1, 2, 3, 4, 6, 7, 8]
discussion: "https://github.com/spore-lang/spore-evolution/discussions"
pr: null
superseded_by: null
---

# SEP-0009: Standard Library Surface

> **Executive Summary**: Defines the standard library surface under the signature model. Standard APIs use inline generic bounds, routine functions omit budget annotations, and core behavior is documented through properties where the property is part of public intent.

## Summary

The standard library provides small, predictable modules for common data and
platform needs:

- `spore.list`
- `spore.option`
- `spore.result`
- `spore.map`
- `spore.set`
- `spore.str`
- `spore.math`
- `spore.ref`

Routine operations do not carry explicit budgets unless realization shape is
part of the contract.

The snippets in this SEP are standard-library surface sketches. A signature that
omits a body states an API item the standard library must provide; it is not a
requirement that this SEP spell out the implementation body.

## Motivation

The standard library should demonstrate the idiomatic signature model: compact Base
Signatures, inline bounds, effects through `uses`, and properties for behavior
that users rely on.

## Guide-level explanation

### Option

```spore
enum Option[T] {
    Some(T),
    None,
}

impl[T] Option[T] {
    fn map[U](self, f: Fn[T, U]) -> Option[U];
    fn unwrap_or(self, default: T) -> T;
    fn is_some(self) -> Bool;
    fn is_none(self) -> Bool;
}
```

### Result

```spore
enum Result[T, E] {
    Ok(T),
    Err(E),
}

impl[T, E] Result[T, E] {
    fn map[U](self, f: Fn[T, U]) -> Result[U, E];
    fn map_err[F](self, f: Fn[E, F]) -> Result[T, F];
    fn is_ok(self) -> Bool;
    fn is_err(self) -> Bool;
}
```

### Lists and indexed containers

`List[T]` is the ordinary sequence type. `Array[T, N]` and `Vec[T, max: N]`
carry compile-time index information when APIs need a static size parameter.

```spore
trait Len {
    fn len(self) -> I64;
}

impl[T] Len for List[T] {
    fn len(self) -> I64;
}
```

### Maps and sets

The standard library must provide abstract `Map[K, V]` and `Set[T]` types. This
SEP specifies their surface, not their representation.

```spore
@foreign
type Map[K, V];

@foreign
type Set[T];

impl[K: Eq + Hash, V] Map[K, V] {
    fn empty() -> Map[K, V];
    fn get(self, key: K) -> Option[V];
    fn insert(self, key: K, value: V) -> Map[K, V];
    fn contains_key(self, key: K) -> Bool;
}

impl[T: Eq + Hash] Set[T] {
    fn empty() -> Set[T];
    fn contains(self, item: T) -> Bool;
}
```

### Properties for standard APIs

Properties are used when behavior is part of public intent:

```spore
fn reverse[T](xs: List[T]) -> List[T]
properties {
    involutive(xs: List[T]): reverse(reverse(xs)) == xs
}
{
    ?reverse_body
}
```

## Reference-level explanation

### Prelude

The prelude exports primitive traits, common data types, and small helpers that
are safe to use without imports. Platform-specific effects remain in Platform
packages.

### Trait style

Shared operation names should be expressed as trait or inherent methods rather
than type-prefixed helper functions. Receiver type and trait resolution select
the correct operation.

### Inline bounds

All standard-library generic bounds are written in type parameter lists:

```spore
fn to_debug_string[T: Debug](value: T) -> Str;
fn contains[T: Eq](xs: List[T], value: T) -> Bool;
```

### Effects

Platform functions declare effects through `uses`:

```spore
@foreign
fn read_file(path: Path) -> Str ! IoError
uses [FileRead];
```

### Budgets

Standard-library signatures omit routine budgets. A budget is written only when
reviewability or realization shape is part of the public contract.

## Human experience impact

The library remains easy to scan. Properties document behavior where it matters,
without forcing every helper to carry extra annotation noise.

## Agent experience impact

Agents can rely on stable trait names, inline bounds, and standard properties
when selecting candidates for hole realization.

## Structured representation / protocol impact

Standard-library metadata should publish:

```text
StdItem
├── module
├── name
├── signature
├── properties[]
├── required_effects[]
└── evidence_policy
```

## Diagnostics impact

Standard-library diagnostics reuse core categories:

- `E0xxx` for missing trait bounds or type mismatch;
- `F0xxx` for effect misuse;
- `P0xxx` for failed standard properties;
- `M0xxx` for import or visibility issues.

## Drawbacks

Omitting routine budgets means the standard library is not a benchmark contract.
That is intentional: budgets shape realizations, while performance guidance
belongs in library documentation and evidence policies when needed.

## Alternatives considered

### Type-prefixed helper names

Rejected because shared trait and inherent methods keep APIs smaller and more
composable.

### Budgets on every function

Rejected because it creates annotation noise and falsely suggests every API has
a public realization-shape contract.

### Platform operations in the prelude

Rejected because effects should remain explicit through selected Platform
packages.

## Prior art

Rust influenced trait-based shared operation names. Elm and Roc influenced small
standard surfaces and platform separation. ML-family libraries influenced
compact algebraic data APIs.

## Backward compatibility and migration

Standard-library specs should migrate to inline bounds and properties. Routine
resource annotations should be removed unless they describe an intentional
realization-shape bound.

## Unresolved questions

1. Which standard properties are required for publication?
2. Should standard property suites be generated into package evidence records?
3. Which Platform packages should be distributed with the standard library set?
