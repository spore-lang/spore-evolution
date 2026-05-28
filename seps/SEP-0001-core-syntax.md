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

Contains name, type parameters with inline bounds, value parameters, and
result type. Outcomes are expressed inside `TypeExpr` itself:

```spore
enum LoadError {
    Io(IoError),
    Parse(ParseError),
}

fn id[T](x: T) -> T
fn contains[T: Eq](xs: List[T], value: T) -> Bool
fn load(path: Path) -> Config ! LoadError
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

### Outcome types and propagation

`A ! E` is a first-class outcome type. It does not mean a list of error names;
it means a value that either succeeds with `A` or fails with `E`. Multiple
failure forms are modeled by ordinary `enum` types:

```spore
enum LoadError {
    File(FileReadError),
    Parse(ParseError),
}

fn load(path: Path) -> Config ! LoadError {
    let text = read_text(path)?;
    parse_config(text)
}
```

`fail` constructs a failure, postfix `?` propagates it to the enclosing outcome
boundary, and outcome matches use `ok` / `fail` patterns:

```spore
match load(path) {
    ok config => config,
    fail err => recover(err),
}
```

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
`type Name;` declaration is reserved for externally-provided opaque types and
must be marked `@foreign`. Refinement semantics are owned by SEP-0002:

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

### Effect surfaces

`effect` declares an atomic effect protocol. `surface` names a reusable effect
surface expression:

```spore
effect Console {
    fn println(msg: Str) -> ();
}

effect FileRead {
    fn read(path: Path) -> Str ! FileReadError;
}

surface IO = [Console, FileRead]

fn run(path: Path) -> ()
uses [IO]
{
    ?run_body
}
```

Surface semantics are owned by SEP-0003.

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
fn <name>[<type-params>](<params>) -> <ResultType>
[uses <SurfaceExpr>]
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
                | SurfaceDecl
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
                  "(" [ ParamList ] ")" "->" TypeExpr ;

TypeParams      = "[" TypeParam { "," TypeParam } "]" ;
TypeArgs        = "[" TypeExpr { "," TypeExpr } [ "," ] "]" ;
TypeParam       = Ident [ ":" BoundList ]
                | "const" Ident ":" TypeExpr ;
BoundList       = Ident { "+" Ident } ;

ParamList       = Param { "," Param } [ "," ] ;
Param           = ReceiverParam | Ident ":" TypeExpr ;
ReceiverParam   = "self" [ ":" TypeExpr ] ;

TypeExpr        = RefinementTypeExpr [ "!" PrimaryTypeExpr ] ;
RefinementTypeExpr = PrimaryTypeExpr [ "when" Expr ] ;
PrimaryTypeExpr = Ident [ TypeArgs ]
                | "(" [ TypeExpr { "," TypeExpr } [ "," ] ] ")" [ "->" TypeExpr ]
                | "{" [ FieldDecl { "," FieldDecl } [ "," ] ] "}"
                | "?" [ Ident ] ;

UsesClause      = "uses" SurfaceExpr ;
SurfaceDecl     = { Attribute } [ Visibility ] "surface" Ident [ TypeParams ] "=" SurfaceExpr ;
SurfaceExpr     = Ident [ TypeArgs ]
                | "[" [ SurfaceItem { "," SurfaceItem } [ "," ] ] "]" ;
SurfaceItem     = Ident [ TypeArgs ] ;

BudgetBlock     = "budget" "{" { BudgetItem } "}" ;
BudgetItem      = Ident ":" IntLiteral ;

PropertiesBlock = "properties" "{" { PropertyItem } "}" ;
PropertyItem    = Ident "(" [ PropertyParamList ] ")" ":" Expr ;
PropertyParamList = PropertyParam { "," PropertyParam } [ "," ] ;
PropertyParam   = Ident ":" TypeExpr ;

Block           = "{" { Statement } [ Expr ] "}" ;
HoleExpr        = "?" [ Ident ] [ ":" TypeExpr ] ;
FailExpr        = "fail" Expr ;
TryExpr         = Expr "?" ;
OutcomePattern  = "ok" Pattern | "fail" Pattern ;

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
EffectDecl      = { Attribute } [ Visibility ] "effect" Ident [ TypeParams ]
                  "{" { MemberFunction } "}" ;
HandlerDecl     = { Attribute } [ Visibility ] "handler" Ident "for" SurfaceExpr
                  "{" { HandlerItem } "}" ;
HandlerItem     = "fn" QualifiedIdent [ TypeParams ]
                  "(" [ ParamList ] ")" "->" TypeExpr ( Block | ";" ) ;
QualifiedIdent  = Ident "." Ident ;
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
- `type Name;` is syntactically valid only for externally-provided opaque types
  and must carry `@foreign`.
- Unparenthesized outcome chaining such as `A ! E ! F` is rejected. Nested
  outcomes must be written with parentheses.
- `surface` names a reusable effect-surface expression. It is not a sum type,
  logical OR, or error union.
- Handler items must name effect operations with a qualified identifier such as
  `Console.println`.

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
├── base_signature  (name, type_params, params, result_type)
├── intent_signature (uses, budget_items, properties)
└── body

OutcomeType
├── success_type
└── failure_type
```

This structure feeds HoleReport, Claim, and EvidenceRecord generation.

## Diagnostics impact

Parser diagnostics point to the specific signature layer. Semantic diagnostics
are owned by dependent SEPs.

## Backward compatibility and migration

This is a breaking surface. Migration tools should:

1. Rewrite `type Name { ... }` to `enum Name { ... }`.
2. Rewrite legacy `-> A ! E1 | E2` forms into `-> A ! ErrorEnum` with an
   explicit `enum` failure type.
3. Rewrite `effect IO = A | B` into `surface IO = [A, B]`.
4. Rewrite `foreign fn` and `foreign type` to `@foreign` attributes.
5. Mark external opaque declarations as `@foreign type Name;`.
6. Move generic bounds into type parameter lists.
7. Replace positional resource annotations with named `budget` fields.

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
