---
sep: 1
title: "SEP-0001: Core Syntax & Signatures"
status: Draft
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

> **Executive Summary**: Defines Spore's root surface grammar and signature
> layout. A function declaration is a Base Signature plus optional Intent
> Signature clauses in fixed order: `uses`, `budget`, `properties`, and body.
> Later SEPs interpret type, effect, budget, hole, property, concurrency,
> module, and standard-library semantics.

## Summary

SEP-0001 owns the **spelling** of every surface form. Semantics belong to
later SEPs. The core model is:

```text
Spore = Signature -> Property -> Hole -> Realization -> Evidence
```

## Motivation

Spore signatures are the shared boundary between humans, compilers, checkers,
and Agents. The grammar must be regular enough for tools and readable for
programmers. SEP-0001 makes that boundary explicit and stable so every later
SEP can extend semantics without revisiting surface spelling.

## Guide-level explanation

### Minimal function

```spore
fn add(a: I64, b: I64) -> I64 {
    a + b
}
```

### Base Signature

Contains name, type parameters with inline bounds, value parameters, return
type, and optional error boundary:

```spore
fn id[T](x: T) -> T
fn contains[T: Eq](xs: List[T], value: T) -> Bool
fn load(path: Path) -> Config ! IoError | ParseError
```

### Intent Signature

Clauses appear after the Base Signature in fixed order — `uses`, `budget`,
`properties` — then the body:

```spore
fn fetch(url: Url) -> Page ! NetworkError
uses [Http]
budget { branches: 4, nesting: 2 }
properties {
    valid(url: Url): is_valid_page(fetch(url))
}
{
    ?fetch_body
}
```

Clause semantics are delegated: `uses` → SEP-0003, `budget` → SEP-0004,
`properties` → SEP-0006.

### Data types

`struct` defines product types; `enum` defines sum types:

```spore
struct Point { x: I64, y: I64 }

enum Shape {
    Circle(I64),
    Rect(I64, I64),
}
```

### Type declarations

`type = Expr` defines transparent aliases and refinement aliases. A bodyless
`type Name;` form is only a syntactic placeholder; without `@foreign`, later
semantic checks should warn and ask for either `@foreign` or a real definition.
Refinement semantics are owned by SEP-0002:

```spore
type Meters = I64
type NonEmptyStr = Str when self.len() > 0
```

### Methods and receivers

Inside `trait` and `impl`, the first parameter may be `self` — shorthand for
`self: Self`. Borrowed receiver forms (`&self`) are not part of SEP-0001:

```spore
trait Display {
    fn show(self) -> Str;
}

impl Display for Point {
    fn show(self) -> Str { ?show_body }
}
```

### Foreign declarations

`@foreign` marks declarations whose implementation or representation is
provided externally:

```spore
@foreign
fn fast_pow(base: F64, exp: F64) -> F64
uses [Native];

@foreign
type Map[K, V];
```

External-linking and ABI semantics are owned by SEP-0008.

### Attributes

Attributes attach metadata to any item:

```spore
@export("C")
pub fn score(raw: I64) -> F64 { raw.to_f64() / 100.0 }

@foreign("ssl", name = "SSL_new")
fn ssl_new() -> Ptr[SSL]
uses [Native];
```

Attribute grammar is defined here; which attributes are valid and their
semantics are owned by SEP-0008.

### Holes

A hole is a typed expression placeholder:

```spore
?
?name
?name: Type
```

Hole semantics and HoleReport are owned by SEP-0005.

## Reference-level explanation

### Signature layout

```text
fn <name>[<type-params>](<params>) -> <ReturnType> [! <ErrorType> { | <ErrorType> }]
[uses [<Effect>, ...]]
[budget { <field>: <int>, ... }]
[properties { <name>(<params>): <expr>, ... }]
( <block> | ";" )
```

### EBNF

```ebnf
SourceFile      = { ItemDecl } ;
ItemDecl        = FunctionDecl
                | StructDecl
                | EnumDecl
                | TypeDecl
                | TraitDecl
                | EffectDecl
                | HandlerDecl
                | ImplDecl
                | ConstDecl
                | ImportDecl ;

Attribute       = "@" Ident [ "(" AttrArgs ")" ] ;
AttrArgs        = AttrArg { "," AttrArg } ;
AttrArg         = Ident "=" AttrValue | AttrValue ;
AttrValue       = Ident | StrLiteral | IntLiteral ;

FunctionDecl    = FunctionSig ( Block | ";" ) ;
FunctionSig     = FunctionHeader [ UsesClause ] [ BudgetBlock ] [ PropertiesBlock ] ;
FunctionHeader  = { Attribute } [ DocComment ] [ Visibility ]
                  "fn" Ident [ TypeParams ]
                  "(" [ ParamList ] ")" "->" TypeExpr [ ErrorClause ] ;

TypeParams      = "[" TypeParam { "," TypeParam } "]" ;
TypeParam       = Ident [ ":" BoundList ]
                | "const" Ident ":" TypeExpr ;
BoundList       = Ident { "+" Ident } ;

ParamList       = Param { "," Param } [ "," ] ;
Param           = ReceiverParam | Ident ":" TypeExpr ;
ReceiverParam   = "self" [ ":" TypeExpr ] ;
ErrorClause     = "!" TypeExpr { "|" TypeExpr } ;

UsesClause      = "uses" "[" [ EffectList ] "]" ;
EffectList      = Ident { "," Ident } ;

BudgetBlock     = "budget" "{" { BudgetItem } "}" ;
BudgetItem      = Ident ":" IntLiteral ;

PropertiesBlock = "properties" "{" { PropertyItem } "}" ;
PropertyItem    = Ident "(" [ PropertyParamList ] ")" ":" Expr ;
PropertyParamList = PropertyParam { "," PropertyParam } [ "," ] ;
PropertyParam   = Ident ":" TypeExpr ;

Block           = "{" { Statement } [ Expr ] "}" ;
HoleExpr        = "?" [ Ident ] [ ":" TypeExpr ] ;

StructDecl      = { Attribute } [ Visibility ] "struct" Ident [ TypeParams ]
                  "{" [ FieldDecl { "," FieldDecl } [ "," ] ] "}" ;
FieldDecl       = Ident ":" TypeExpr ;

EnumDecl        = { Attribute } [ Visibility ] "enum" Ident [ TypeParams ]
                  "{" [ VariantDecl { "," VariantDecl } [ "," ] ] "}" ;
VariantDecl     = Ident [ "(" [ TypeExpr { "," TypeExpr } [ "," ] ] ")" ] ;

TypeDecl        = { Attribute } [ Visibility ] "type" Ident [ TypeParams ]
                  ( "=" TypeExpr | ";" ) ;

TraitDecl       = { Attribute } [ Visibility ] "trait" Ident [ TypeParams ]
                  "{" { MemberFunction } "}" ;
EffectDecl      = { Attribute } [ Visibility ] "effect" Ident
                  ( "{" { MemberFunction } "}"
                  | "=" Ident { "|" Ident } ) ;
HandlerDecl     = { Attribute } "handler" Ident "for" TypeExpr
                  "{" { FunctionDecl } "}" ;
ImplDecl        = { Attribute } "impl" [ TypeParams ] TypeExpr [ "for" TypeExpr ]
                  "{" { FunctionDecl } "}" ;
MemberFunction  = FunctionSig ( Block | ";" ) ;

ConstDecl       = { Attribute } [ Visibility ] "const" Ident ":" TypeExpr "=" Expr ;
ImportDecl      = "import" ModulePath [ "as" Ident ] ;
ModulePath      = Ident { "." Ident } ;
Visibility      = "pub" | "pub" "(" "pkg" ")" ;
```

**Grammar notes:**

- A function marked `@foreign` must end with `;` (no body); ordinary `fn` may
  end with `;` (bodyless signature) or a block.
- `ReceiverParam` is only valid as the first parameter inside `trait` or
  `impl`. Bare `self` normalizes to `self: Self`.
- `type = Expr` defines aliases; `enum` covers all sum types.
- `type Name;` is syntactically valid. Without `@foreign`, compilers should
  warn and suggest adding `@foreign` or a real definition. Warning semantics
  are defined by SEP-0002.

### Delegated semantics

| Surface                                     | Semantic owner |
| ------------------------------------------- | -------------- |
| Type aliases, refinements, trait bounds     | SEP-0002       |
| `enum` variant layout and pattern rules     | SEP-0002       |
| Effects, `perform`, handlers                | SEP-0003       |
| Budget fields and checking                  | SEP-0004       |
| Holes and HoleReport                        | SEP-0005       |
| Properties, claims, evidence                | SEP-0006       |
| Concurrency forms (`Task`, `spawn`, etc.)   | SEP-0007       |
| Modules, `@export`, `@foreign`, ABI linking | SEP-0008       |
| Standard library names                      | SEP-0009       |

## Human experience impact

Simple functions stay compact. Richer intent is readable because `uses`,
`budget`, and `properties` always appear in the same order before the body.

## Agent experience impact

Agents can parse signatures without inferring hidden conventions. Each clause
has a fixed position and fixed spelling.

## Structured representation / protocol impact

```text
FunctionDecl
├── base_signature  (name, type_params, params, return_type, error_set)
├── intent_signature (uses, budget_items, properties)
└── body
```

This structure feeds HoleReport, Claim, and EvidenceRecord generation.

## Diagnostics impact

Parser diagnostics point to the specific signature layer. Semantic diagnostics
are owned by dependent SEPs.

## Backward compatibility and migration

This is a breaking surface. Migration tools should:

1. Rewrite `type Name { ... }` to `enum Name { ... }`.
2. Rewrite `foreign fn` and `foreign type` to `@foreign` attributes.
3. Mark external opaque declarations as `@foreign type Name;`.
4. Move generic bounds into type parameter lists.
5. Replace positional resource annotations with named `budget` fields.

## Drawbacks

Inline bounds make large type parameter lists denser. The mitigation is to
prefer small generic surfaces and hide complex abstraction behind traits.

Named budget fields require users to learn accepted vocabulary. Fields are
self-describing and extend without positional migration.

## Alternatives considered

**`type` for sum types**: rejected in favor of `enum` to keep keyword intent
unambiguous and align with established convention.

**`alias` keyword**: rejected; `type = Expr` already covers aliases without
adding vocabulary.

**Bare `type Name;` as immediately-valid opaque type**: rejected. The syntax is
accepted so editors and incremental parsers can represent unfinished code, but
compilers should warn unless the declaration is marked `@foreign` or completed
with a real definition.

**Separate proof keyword**: rejected; users write `properties`, compiler lowers
them internally.

## Prior art

Rust influenced braces, semicolons, generic bound notation, and the
`struct`/`enum` pairing. Haskell influenced `foreign` as FFI vocabulary.
Kotlin, Swift, and Java influenced attribute-style metadata. Idris and Agda
influenced typed holes. OCaml influenced abstract type declarations. Roc
influenced explicit effect boundaries.

## Unresolved questions

1. Should long inline bounds allow line breaks after each type parameter?
2. Which property expression subset is accepted for automated checking?
3. Should effect names be partitioned by namespace?
