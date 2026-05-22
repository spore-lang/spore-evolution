---
sep: 1
title: "SEP-0001: Core Syntax & Signatures"
status: Accepted
type: Standards Track
authors:
  - Zhan Rongrui
created: 2026-03-31
requires: []
discussion: "https://github.com/spore-lang/spore-evolution/discussions/1"
pr: null
superseded_by: null
---

# SEP-0001: Core Syntax & Signatures

> **Executive Summary**: Defines Spore's root surface grammar and Signature v2 layout. A function declaration is a Base Signature plus optional Intent Signature clauses in fixed order: `uses`, `budget`, `properties`, and body. Later SEPs interpret type, effect, budget, hole, evidence, concurrency, module, and standard-library semantics.

## Summary

This SEP defines the shared syntax root for Spore. The core design is:

```text
Spore = Signature -> Property -> Hole -> Realization -> Evidence
```

A function's Base Signature defines possible implementation space. Its optional
Intent Signature constrains that space with capabilities, quantitative
realization-shape budgets, and semantic properties.

```spore
fn group_by[T, K: Eq](xs: List[T], key: Fn[T, K]) -> Dict[K, List[T]] ! Error
uses [Compare]
budget {
    branches: 4
    nesting: 3
    recursion: 0
    parallelism: 1
}
properties {
    empty(): group_by([], key) == Dict.empty()
    preserves_count(xs: List[T]): len(flatten(values(group_by(xs, key)))) == len(xs)
}
{
    ?group_by_body
}
```

## Motivation

Spore signatures are the shared boundary between humans, compilers, checkers,
and Agents. The grammar must make that boundary regular enough for tools while
remaining readable to programmers.

Signature v2 separates two concerns:

1. **Base Signature**: the callable type boundary the compiler must understand.
2. **Intent Signature**: capabilities, budgets, and properties that guide
   verification, review, realization, and evidence generation.

This keeps type checking, Agent filling, and evidence review connected without
mixing their responsibilities.

## Guide-level explanation

### Minimal functions

```spore
fn add(a: I64, b: I64) -> I64 {
    a + b
}
```

The return type is part of the Base Signature. The last expression in a block is
the block value.

### Base Signature

A Base Signature contains:

- function name
- type parameters and inline bounds
- value parameters
- return type
- error boundary

```spore
fn id[T](x: T) -> T
fn contains[T: Eq](xs: List[T], value: T) -> Bool
fn index[K: Eq + Hash, V](map: Map[K, V], key: K) -> Option[V]
fn load(path: Path) -> Config ! ConfigError
```

Generic constraints are attached to type parameters. A type parameter may have
one bound or a `+` separated bound list.

### Intent Signature

Intent clauses appear after the Base Signature and before the body:

```spore
fn fetch(url: Url) -> Page ! NetworkError | Timeout
uses [Http]
budget {
    branches: 3
    nesting: 2
}
properties {
    valid(url: Url): is_valid_page(fetch(url))
}
{
    ?fetch_body
}
```

`uses` is the capability surface. Runtime effect capabilities are specified by
SEP-0003. Logical and checker capabilities are interpreted by tooling layers.

`budget` is a named block of integer upper bounds over realization shape. SEP-0004
owns the accepted fields and checking model.

`properties` is the source spelling for validity rules. Internally, the compiler
lowers properties into claims owned by SEP-0006.

### Properties

Every property item has the form:

```spore
name(params): expression
```

A zero-argument property is a concrete witness. A parameterized property is a
validity rule over generated or supplied values.

```spore
fn sort(xs: List[I64]) -> List[I64]
properties {
    basic(): sort([3, 1, 2]) == [1, 2, 3]
    ordered(xs: List[I64]): is_ordered(sort(xs))
    permutation(xs: List[I64]): same_members(sort(xs), xs)
}
{
    ?sort_body
}
```

### Holes

Holes are expressions:

```spore
?
?name
?name: Type
```

SEP-0001 owns only the spelling. Hole typing, partial-function behavior,
HoleReport payloads, Agent protocol, and context projection are owned by
SEP-0005.

### Other core forms

Spore remains expression-oriented:

```spore
let result = if ready {
    compute_ready()
} else {
    compute_pending()
};
```

Core declarations include `struct`, `type`, `trait`, `effect`, `handler`,
`const`, `fn`, `impl`, `import`, and `alias`. SEP-0001 defines their syntax;
semantic ownership is delegated to later SEPs.

## Reference-level explanation

### Function signature layout

The canonical order is:

```text
fn <name>[<type-params>](<params>) -> <ReturnType> [! <ErrorTypes>]
[uses [<Capability>, ...]]
[budget { <name>: <integer>, ... }]
[properties { <property-items> }]
{
    <body>
}
```

### EBNF

```ebnf
FunctionDecl      = FunctionSig Block ;
FunctionSig       = FunctionHeader [ UsesClause ] [ BudgetBlock ] [ PropertiesBlock ] ;
FunctionHeader    = { Attribute } [ DocComment ] [ Visibility ] "fn" Ident [ TypeParams ]
                    "(" [ ParamList ] ")" "->" TypeExpr [ ErrorClause ] ;

TypeParams        = "[" TypeParam { "," TypeParam } "]" ;
TypeParam         = Ident [ ":" BoundList ]
                  | "const" Ident ":" TypeExpr ;
BoundList         = Ident { "+" Ident } ;

ParamList         = Param { "," Param } [ "," ] ;
Param             = Ident ":" TypeExpr ;
ErrorClause       = "!" TypeExpr { "|" TypeExpr } ;

UsesClause        = "uses" "[" [ CapabilityList ] "]" ;
CapabilityList    = Ident { "," Ident } ;

BudgetBlock       = "budget" "{" { BudgetItem } "}" ;
BudgetItem        = Ident ":" IntLiteral ;

PropertiesBlock   = "properties" "{" { PropertyItem } "}" ;
PropertyItem      = Ident "(" [ PropertyParamList ] ")" ":" Expr ;
PropertyParamList = PropertyParam { "," PropertyParam } [ "," ] ;
PropertyParam     = Ident ":" TypeExpr ;

Block             = "{" { Statement } [ Expr ] "}" ;
HoleExpr          = "?" [ Ident ] [ ":" TypeExpr ] ;
```

Type, expression, pattern, import, effect, handler, and module grammar remain
part of SEP-0001, while their semantics are delegated.

### Type surface

Primitive type names include `I8`, `I16`, `I32`, `I64`, `U8`, `U16`, `U32`,
`U64`, `F32`, `F64`, `Bool`, `Str`, `()`, and `Never`.

Collection and standard types include `List[T]`, `Vec[T, max: N]`, `Map[K, V]`,
`Set[T]`, `Array[T, N]`, `Option[T]`, `Result[T, E]`, `Ref[T]`, and
`Channel[T]`.

Function types use `Fn[A, B]` in signature positions that need named function
values.

### Delegated semantics

| Surface | Semantic owner |
|---|---|
| Type meaning, inference, traits, refinements | SEP-0002 |
| Runtime effects and handlers | SEP-0003 |
| Budget fields and checking | SEP-0004 |
| Holes and HoleReport projection | SEP-0005 |
| Properties, claims, diagnostics, evidence | SEP-0006 |
| Concurrency forms | SEP-0007 |
| Modules, packages, provenance hashes | SEP-0008 |
| Standard library names | SEP-0009 |

## Human experience impact

Signature v2 keeps simple functions compact and makes richer intent scan in a
stable order. A reader can distinguish the callable boundary from constraints
used by review, verification, or Agents.

## Agent experience impact

Agents can parse signatures without inferring hidden conventions. `uses` limits
available capabilities, `budget` limits realization shape, and `properties`
state the validity criteria the realization must preserve.

## Structured representation / protocol impact

The AST for a function includes:

```text
FunctionDecl
├── base_signature
│   ├── name
│   ├── type_params[]
│   ├── params[]
│   ├── return_type
│   └── error_set[]
├── intent_signature
│   ├── uses[]
│   ├── budget_items[]
│   └── properties[]
└── body
```

This structure feeds HoleReport, Claim, and EvidenceRecord generation.

## Diagnostics impact

Parser diagnostics should point to the specific signature layer:

- base signature syntax errors
- unknown capability names
- malformed budget items
- malformed property declarations
- body or hole syntax errors

Semantic diagnostics are owned by dependent SEPs.

## Drawbacks

Inline bounds can make large type parameter lists denser. The mitigation is to
prefer small generic surfaces and move complex abstraction behind traits and
helper types.

Named budget fields require users to learn accepted budget vocabulary. The
mitigation is that fields are self-describing and extend without positional
migration.

## Alternatives considered

### Separate proof keyword

A separate source keyword for claims was rejected. Users write `properties`; the
compiler may lower those properties into internal claims.

### Positional resource vectors

A positional vector was rejected because positions are opaque to readers and
harder to extend without migration.

### Standalone bound clauses

A separate generic-bound clause was rejected because bounds belong next to the
type variables they constrain.

## Prior art

Rust influenced braces, semicolon behavior, pattern matching, and generic bound
notation. Idris and Agda influenced typed holes. Unison influenced
content-addressed identity. Roc influenced explicit effect boundaries.

## Backward compatibility and migration

Signature v2 is a breaking surface update. Migration tools should:

1. move generic bounds into type parameter lists;
2. rewrite behavioral assertions into `properties` items;
3. replace positional resource annotations with named budget fields only when a
   realization-shape constraint is intended;
4. preserve function bodies and hole names.

## Unresolved questions

1. Should long inline bounds allow line breaks after each type parameter?
2. Which property expression subset should be accepted for generated checking?
3. Should capability names be partitioned by namespace, or is a single capability
   surface sufficient?
