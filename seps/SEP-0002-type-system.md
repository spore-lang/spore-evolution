---
sep: 2
title: "SEP-0002: Type System"
status: Draft
type: Standards Track
authors:
  - Zhan Rongrui
created: 2026-03-31
requires:
  - 1
discussion: "https://github.com/spore-lang/spore-evolution/discussions/2"
pr: null
superseded_by: null
---

# SEP-0002: Type System

> **Executive Summary**: Defines Spore's type system under the signature model. Base signatures are fully annotated, generic bounds live inline in type parameter lists, and type checking produces the type evidence consumed by HoleReport and EvidenceRecord payloads.

## Summary

Spore uses nominal-primary static typing with bidirectional inference inside
function bodies. Function signatures are explicit: parameters, result type,
outcome boundary, and type-parameter bounds are all written at the callable
boundary.

```spore
fn identity[T](x: T) -> T { x }
fn member[T: Eq](xs: List[T], value: T) -> Bool { ?member_body }
fn insert[K: Eq + Hash, V](map: Map[K, V], key: K, value: V) -> Map[K, V] { ?insert_body }
```

## Motivation

The type system gives the signature model its base notion of possibility. A realization
must inhabit the target type before property, budget, or evidence checks can
mean anything.

The design goals are:

- make callable boundaries explicit;
- keep body inference local and predictable;
- distinguish traits from effects;
- expose typed holes as useful collaboration points;
- produce stable machine facts for downstream protocols.

## Guide-level explanation

### Primitive and composite types

Primitive type names include `I8`, `I16`, `I32`, `I64`, `U8`, `U16`, `U32`,
`U64`, `F32`, `F64`, `Bool`, `Str`, `()`, and `Never`.

Composite types use square brackets:

```spore
List[I64]
Option[Str]
Array[I64, N]
Vec[Order, max: N]
```

Outcome types are first-class and use `!` inside the type surface:

```spore
User ! ParseError
List[Config ! LoadError]
```

### Structs and variants

```spore
struct Point { x: I64, y: I64 }

enum Shape {
    Circle(I64),
    Rect(I64, I64),
}
```

Types are nominal. Two structs with identical fields but different names are
different types.

### Traits and inline bounds

Traits define type interfaces:

```spore
trait Display {
    fn show(self) -> Str;
}

fn to_string[T: Display](value: T) -> Str {
    value.show()
}
```

Inside trait and impl members, `self` is receiver shorthand for `self: Self`.
It may only appear as the first parameter; receiver ownership refinements are
outside this SEP.

Multiple bounds use `+` inside the type parameter list:

```spore
fn index[K: Eq + Hash, V](map: Map[K, V], key: K) -> Option[V] {
    ?index_body
}
```

### Refinement types

Refinement types attach predicates to ordinary types:

```spore
type NonEmptyStr = Str when self.len() > 0
```

Refinement checking is staged: decidable checks happen during type checking,
flow-sensitive propagation happens through abstract interpretation, and harder
obligations become claims for the evidence layer.

### Outcome types

`A ! E` is a first-class outcome type. `A` is the success type and `E` is the
failure type. Errors are ordinary values; multiple failure forms are modeled by
ordinary `enum` types rather than inline unions:

```spore
enum LoadError {
    Io(IoError),
    Parse(ParseError),
}

fn parse(input: Str) -> Config ! ParseError
fn load(path: Path) -> Config ! LoadError
```

`Result[T, E]` is not part of the core type surface. Source programs use `A ! E`
directly.

`fail err` constructs a failure outcome. If `expr : A ! E`, then `expr?`
eliminates the outcome at the expression site and propagates failures to the
enclosing outcome boundary. Outcome matches use `ok` / `fail` patterns at the
surface level.

### Holes

A hole synthesizes or checks against the expected type from context:

```spore
fn parse(input: Str) -> Config ! ParseError {
    ?parse_body
}
```

The checker records the expected type and surrounding bindings for SEP-0005.

## Reference-level explanation

### Type judgments

Core checking uses two judgments:

```text
Γ |- e => T      expression synthesizes type T
Γ |- e <= T      expression checks against expected type T
```

Function bodies are checked against the result type from the Base Signature.
Holes are compatible with the expected type but recorded as incomplete terms.

### Inline bounds

A type parameter has this normalized shape:

```text
TypeParam { name, kind?, bounds[] }
```

Bounds are trait requirements. Effects do not appear in type parameter bounds;
effect checking belongs to SEP-0003.

### Inference boundary

Signatures must be explicit. Local bindings may omit annotations when the
right-hand side synthesizes a type:

```spore
let message = "ready";
let count = 42;
```

### Outcome typing

Outcome types are normalized into a pair:

```text
OutcomeType
├── success_type
└── failure_type
```

A call is valid when the callee's failure type is handled locally, propagated by
`?`, or explicitly transformed into the caller's declared failure type. `fail e`
checks against an expected outcome when `e` inhabits the failure type. Bare
`A ! E ! F` is rejected without parentheses so `!` does not become an ambiguous
chain operator.

### Property body typing

A source property body is an ordinary Spore expression checked under the
surrounding callable's type environment.

If a property item is written as:

```spore
properties {
    name(params...): body
}
```

then `body` must check against `Bool`. A body with any other result type is a
type error. Property parameters introduce local bindings with the declared types
for the property body only; they do not change the callable's Base Signature.

The property body inherits the enclosing callable's effect context. It may only
perform effects included in the enclosing `uses` surface or effects discharged
by a narrower local handler context. A property body that requires an unavailable
effect is an effect-checking error.

The type checker does not need to decide whether every well-typed property is
true. It only establishes that the property is a `Bool` expression in the right
type and effect context. Decidable failures may become immediate diagnostics;
undecidable obligations lower into SEP-0006 claims.

### Refinement obligations

When a refinement predicate is decidable in the type checker, it is discharged
immediately. Otherwise the checker emits a property-level obligation that the
compiler can lower into a Claim for evidence processing. This is the same claim
and evidence channel used for source properties. Source properties and
refinement obligations differ in where they come from, not in the shape of the
downstream claim record.

## Human experience impact

Inline bounds keep type requirements near the variables they constrain. The
signature remains the place where readers learn what can be passed, returned, or
failed.

## Agent experience impact

Agents receive precise expected types for holes and can filter candidate
realizations by trait bounds, outcome boundaries, and visible bindings without
parsing prose.

## Structured representation / protocol impact

TypedHIR records:

```text
FunctionType
├── type_params[]
├── params[]
├── result_type
├── outcome_shape?
└── trait_obligations[]
```

When `result_type` is an outcome, `outcome_shape` records the normalized
`success_type` / `failure_type` pair. HoleReport receives `type.expected`,
`type.inferred_from`, visible bindings, and unsatisfied trait obligations.

## Diagnostics impact

Type diagnostics use `E0xxx` codes. Important categories include unknown type,
return mismatch, outcome mismatch, unhandled failure propagation, missing trait
implementation, unsatisfied refinement, and ambiguous hole type.

A bodyless `type Name;` declaration without `@foreign` should produce a hard
error that asks the author to either mark the type as external (`@foreign type
Name;`) or provide a real definition (`type Name = ...`).

## Drawbacks

Dense generic headers can become difficult to read. Formatters should allow one
type parameter per line for highly constrained functions.

Refinement obligations that become evidence claims may surprise users who expect
all refinements to be checked immediately.

## Alternatives considered

### Structural typing

Rejected because nominal types give clearer diagnostics and package boundaries.

### Inferred public signatures

Rejected because the signature model relies on explicit callable boundaries as shared
intent.

### Separate bound clauses

Rejected because they split generic requirements away from the type variables.

## Prior art

Rust influenced traits and explicit callable boundaries. ML-family languages
influenced algebraic data types and inference. Liquid types influenced the
refinement model.

## Backward compatibility and migration

Migration moves generic constraints into type parameter lists and preserves body
inference behavior. Public API hashes must treat the normalized inline-bound
form as the source of truth.

## Unresolved questions

1. Which refinement predicates should remain in the immediate decidable subset?
2. How should associated types display inside compact signature hovers?
3. Should trait aliases be permitted in inline bounds?
