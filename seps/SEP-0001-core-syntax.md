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

> **Executive Summary**: Defines Spore's core syntax and function-signature layout. SEP-0001 fixes the shared surface forms that later SEPs interpret: type syntax, error clauses, effect clauses, cost clauses, holes, concurrency forms, imports, and `spec` blocks. Detailed type, effect, cost, hole, compiler, concurrency, module, and standard-library semantics are delegated to their corresponding SEPs.

## Summary

This proposal defines the core syntax and function-signature surface for the Spore programming language. Spore uses expression-oriented curly-brace syntax, Rust-style semicolon rules, algebraic data type syntax, pattern matching, square-bracket generics, and a regular function signature structure with optional `!`, `where`, `cost`, `uses`, and `spec` clauses.

This SEP specifies the **surface grammar** and cross-SEP signature layout. SEP-0002 specifies type meaning and checking, SEP-0003 specifies effect semantics, SEP-0004 specifies cost verification, SEP-0005 specifies holes, SEP-0006 specifies compiler behavior and diagnostics, SEP-0007 specifies concurrency semantics, SEP-0008 specifies module/package resolution, and SEP-0009 specifies the standard-library surface. SEP-0001 remains dependency-free so those later SEPs can depend on a stable syntactic root without creating cycles.

## Normative scope and dependency boundaries

SEP-0001 is the root syntax SEP. Later SEPs may assign semantics to forms defined here, but they must not re-specify incompatible grammar.

| Surface area | SEP-0001 owns | Semantic owner |
|---|---|---|
| Function declarations | clause order, delimiters, optional body shape | SEP-0002 for type checking, SEP-0004 for cost, SEP-0003 for effects |
| Type syntax | identifiers, generic brackets, tuple/function/refinement syntax forms | SEP-0002 |
| Error clauses and `?` / `throw` syntax | spelling and placement | SEP-0002 for error-set typing and propagation |
| `effect`, `handler`, `perform`, `handle` | declaration and expression grammar | SEP-0003 |
| `cost [...]` | clause placement and expression syntax envelope | SEP-0004 |
| `spec { ... }` | clause placement and item grammar | SEP-0006 for test execution, diagnostics, and spec hashing |
| Holes (`?name`) | expression grammar | SEP-0005 |
| `parallel_scope`, `spawn`, `select`, `await` | expression grammar | SEP-0007 |
| `import`, `alias`, visibility | declaration grammar | SEP-0008 |
| Prelude and library names | examples only | SEP-0009 |

Unless explicitly marked as grammar, examples that mention type names, effect names, cost values, module paths, or standard-library items are illustrative.

## Motivation

Spore's syntax is designed to balance human readability with predictable machine processing. Curly-brace blocks, explicit delimiters, a fixed operator set, and ordered function clauses make source text regular enough for compilers, formatters, LSPs, and agents to process without relying on implicit layout or custom operator rules.

Spore aims to occupy a practical syntactic design point:

1. **Human-readable syntax**: expression-oriented syntax with familiar braces, semicolons, `let`, `fn`, `match`, and postfix type annotations.
2. **Machine-readable structure**: a fixed operator set, explicit delimiters, and a predictable function-clause order.
3. **Progressive signatures**: simple functions remain short, while functions that need additional metadata can add clauses in one canonical order.
4. **One iteration style**: loop keywords are absent from the surface language; recursive and library-based iteration are the accepted syntactic idioms.

## Guide-level explanation

This section introduces the surface forms defined by this SEP.

### Your first Spore function

A minimal Spore function has a name, typed parameters, a return type, and a block body:

```spore
fn add(a: I64, b: I64) -> I64 {
    a + b
}
```

The last expression in a block is the block value.

### Variables and immutability

All bindings are immutable by default:

```spore
let name = "Alice";
let age = 30;
let greeting = f"Hello, {name}! You are {age} years old.";
```

Shadowing reuses a binding name in a later binding:

```spore
let x = 10;
let x = x + 5;  // shadows the previous x
```

For local mutable state, `Ref[T]` is written as a normal generic type:

```spore
let counter = Ref.new(0);
counter.set(counter.get() + 1);
counter.update(|x| x + 1);  // atomic read-modify-write
```

### Semicolons: statements vs. expressions

Spore uses Rust-style semicolon semantics:

- **With semicolon** → statement, value is discarded
- **Without semicolon** → expression, value is returned

```spore
let result = {
    let a = 10;      // statement (semicolon)
    let b = 20;      // statement (semicolon)
    a + b             // expression (no semicolon) — this is the block's value
};
// result == 30
```

### Conditionals are expressions

`if`/`else` returns a value:

```spore
let abs_value = if x >= 0 { x } else { -x };

let category = if age < 13 {
    "child"
} else if age < 20 {
    "teenager"
} else {
    "adult"
};
```

### Pattern matching

`match` expressions use comma-terminated arms:

```spore
type Shape =
    Circle(radius: F64)
    | Rectangle(width: F64, height: F64)
    | Triangle(base: F64, height: F64);

fn area(shape: Shape) -> F64 {
    match shape {
        Circle(r) => 3.14159 * r * r,
        Rectangle(w, h) => w * h,
        Triangle(b, h) => 0.5 * b * h,
    }
}
```

Guards and or-patterns are supported:

```spore
let label = match score {
    n if n >= 90 => "excellent",
    n if n >= 70 => "good",
    n if n >= 50 => "pass",
    _ => "fail",
};

let is_weekend = match day {
    "Saturday" | "Sunday" => true,
    _ => false,
};
```

### No loop syntax

Spore has **no** `for`, `while`, `loop`, `break`, or `continue` syntax. Iteration is expressed with recursion or library functions:

```spore
// Sum a list using fold
fn sum(numbers: List[I64]) -> I64 {
    numbers.fold(0, |acc, x| acc + x)
}

// Factorial using recursion
fn factorial(n: I64) -> I64 {
    fn go(n: I64, acc: I64) -> I64 {
        if n <= 1 { acc } else { go(n - 1, n * acc) }
    }
    go(n, 1)
}

// Filter and transform using library functions
let result = numbers
    |> filter(|x| x > 0)
    |> map(|x| x * 2)
    |> fold(0, |acc, x| acc + x);
```

### Pipe operator

The pipe operator `|>` passes the left-hand value as the first argument to the right-hand function:

```spore
// These are equivalent:
let result = format(process(validate(parse(data))));

let result = data
    |> parse
    |> validate
    |> process
    |> format;

// With additional arguments:
x |> f(y, z)    // equivalent to: f(x, y, z)
x |> f(_, y)    // equivalent to: f(x, y)
f(_, y)         // equivalent to: |x| f(x, y)
```

The `_` placeholder form is a general call-position partial application form:
any call argument written as `_` is converted into a lambda parameter. Pipe use
is only the most common spelling because `x |> f(_, y)` reads as "send `x` into
the placeholder".

### Ranges and slices

Ranges create sequences; slices extract sub-lists:

```spore
// Half-open range [start, end)
let range1 = 1..10;      // 1, 2, 3, ..., 9

// Closed range [start, end]
let range2 = 1..=10;     // 1, 2, 3, ..., 10

// Summing 1 to 100 using a range with fold
let sum = (1..=100).fold(0, |acc, x| acc + x);

// List slicing
let sublist    = list[2..5];   // elements at index 2, 3, 4
let all_from_3 = list[3..];   // index 3 to end
let first_5    = list[..5];   // first 5 elements
```

### Method chaining and pipe equivalence

Method chains and pipes are interchangeable styles:

```spore
// Method chain style (fluent API)
let result = text
    .trim()
    .to_lowercase()
    .split(" ")
    .filter(|word| word.len() > 3)
    .map(|word| capitalize(word))
    .collect();

// Equivalent pipe style
let result = text
    |> trim
    |> to_lowercase
    |> split(" ")
    |> filter(|word| word.len() > 3)
    |> map(|word| capitalize(word))
    |> collect;
```

### Error handling

Errors are declared in the function signature with `!` and propagated with `?`:

```spore
type FileError =
    NotFound(path: Str)
    | PermissionDenied(path: Str)
    | IoError(message: Str);

fn read_config(path: Str) -> Config ! FileError | ParseError {
    let content = read_file(path)?;     // propagates FileError
    let config = parse_toml(content)?;  // propagates ParseError
    config
}
```

Error-set typing, propagation, conversion, and recovery patterns are owned by
SEP-0002. SEP-0001 only fixes the spelling and placement of `!`, `?`, and
`throw`.

### Generic types with square brackets

Spore uses square brackets for generics, not angle brackets:

```spore
type Option[T] =
    Some(T)
    | None;

type Result[T, E] =
    Ok(T)
    | Err(E);

struct Pair[A, B] {
    first: A,
    second: B,
}

fn identity[T](x: T) -> T {
    x
}
```

### Function signatures: from simple to complex

The canonical signature order is:

```text
fn name[T](params) -> ReturnType ! ErrorSet
where T: Bound
cost [compute, alloc, io, parallel]
uses [Effect1, Effect2]
spec {
    <spec-items>
}
{
    body
}
```

Only the clauses that are needed are written:

```spore
fn add(a: I64, b: I64) -> I64 {
    a + b
}

fn parse_int(input: Str) -> I64 ! InvalidFormat {
    ?parse_int_body
}

fn serialize[T](value: T) -> Bytes ! SerializeError
where T: Serialize
cost [500, 50, 0, 1]
{
    ?serialize_body
}

fn sync_user_data(user_id: UserId, source: DataSource) -> SyncReport ! NetworkTimeout | AuthExpired
cost [8500, 200, 800, 4]
uses [NetConnect, FileRead, Clock]
{
    ?sync_body
}
```

Detailed behavior of error sets, cost vectors, effect requirements, and `spec`
execution is delegated to SEP-0002, SEP-0004, SEP-0003, and SEP-0006.

### Traits, effects, and the `uses` clause

Spore separates type interfaces from effect tracking:

This section is the **normative surface syntax** for these forms. SEP-0002 and SEP-0003 reference the same constructs semantically rather than re-specifying their grammar.

```spore
// trait: type interface
trait Display {
    fn show(self) -> Str;
}

trait Serialize {
    fn serialize(self) -> Bytes ! SerializeError;
}

// effect: external world operations
effect Console {
    fn println(msg: Str) -> ();
    fn read_line() -> Str ! IoError;
}

// effect alias (uses | for union)
effect HttpClient = NetConnect | Clock;
effect CLI = Console | FileRead | FileWrite | Env | Spawn | Exit;
```

SEP-0001 fixes the grammar for `trait`, `effect`, `handler`, `perform`,
`handle`, and `uses [...]`. SEP-0002 owns trait semantics; SEP-0003 owns effect
algebra, handler behavior, inferred effect attributes, and alias expansion. At the
syntax level, a `uses` clause is a bracketed list of effect names or aliases:

```spore
fn query_database(sql: Str) -> Data ! DbError | Timeout
uses [NetConnect]
{
    ?query_database_body
}

fn run_cli(config_path: Str) -> () ! Error
uses [CLI]
{
    ?run_cli_body
}
```

### Behavioral specification (`spec` clause)

A function signature may include a `spec` block after `where`, `cost`, and `uses`, immediately before the function body. SEP-0001 fixes only the placement and item syntax:

```spore
fn name(params) -> Return
spec {
    example "label": expr
    law "label": |x: T| expr
    law "refined": |x: I32 when self >= 0| expr
}
{
    body
}
```

`example` and `law` type checking, executable checking, diagnostics, and spec
hashing are specified in SEP-0006. Hole-report projection of `spec` metadata is
specified in SEP-0005.

### Struct and type definitions

```spore
// Named-field struct
struct User {
    id: I64,
    name: Str,
    email: Str,
}

impl Display for User {
    fn to_string(self) -> Str {
        f"User({self.name}, {self.email})"
    }
}

impl Serialize for User {
    fn serialize(self) -> Str ! SerializeError {
        ?serialize_body
    }
}

// Tuple struct
struct Color(I64, I64, I64);

// Unit struct
struct NoData;

// Sum type (algebraic data type)
type BinaryTree[T] =
    Leaf(T)
    | Node(left: BinaryTree[T], value: T, right: BinaryTree[T])
    | Empty;

// Refinement type
type PositiveInt = I64 when self > 0;
type Percentage = F64 when self >= 0.0 && self <= 100.0;
type I32 = I64 when self >= -2147483648 && self <= 2147483647;
type U8 = I64 when self >= 0 && self <= 255;
```

Field punning allows omitting the value when the variable name matches the field name, both in construction and pattern matching:

```spore
let name = "Alice";
let email = "alice@example.com";

// Full form
let user1 = User { name: name, email: email };

// Punned form (equivalent)
let user2 = User { name, email };

// Punning in pattern matching
match user {
    User { name, email, .. } => f"Name: {name}, Email: {email}",
}
```

### Strings

```spore
// Regular string
"Hello, World!"

// Raw string (no escape processing)
r"C:\Users\path\to\file"

// Format string (f-string)
f"Hello {name}, you are {age} years old"
f"Result: {2 + 2}"

// Template string (t-string) — returns a template object
let tmpl = t"Dear {customer}, your order {id} is ready.";
let msg = tmpl.bind([("customer", "Bob"), ("id", "12345")]);

// Multi-line string (newlines are literal)
let query = "SELECT *
FROM users
WHERE active = true";

// Multi-line with f-string
let html = f"<div>
    <h1>{title}</h1>
    <p>{body}</p>
</div>";
```

Format strings (`f"..."`) and template strings (`t"..."`) both accept embedded
Spore expressions. Template-library behavior, escaping policy beyond the shared
string literal rules, and sanitization belong to SEP-0009.

### Lambdas

```spore
let double = |x| x * 2;
let add = |a, b| a + b;
let complex = |x, y| {
    let sum = x + y;
    let product = x * y;
    sum * product
};
```

### Concurrency

SEP-0001 fixes only the concurrency expression forms. Task lifetime, channel
behavior, scheduling, cancellation, and timeout semantics are owned by SEP-0007.

```spore
parallel_scope {
    let a = spawn { compute_a() };
    let b = spawn { compute_b() };
    [a.await, b.await]
}
```

### Modules and imports

```spore
// src/math.sp
pub fn add(a: I64, b: I64) -> I64 { a + b }
fn helper() -> I64 { 42 }  // private by default

import std.collections as collections;
import std.math as math;
```

## Reference-level explanation

### Lexical structure

#### Source text encoding

Spore source files are UTF-8 encoded. Identifiers may contain Unicode letters, ASCII digits, and underscores. Identifiers must begin with a letter or underscore.

**Character literals.** Single-quoted character literals are not part of the grammar. Length-1 text is written as a `Str` literal, for example `"a"` or `"世"`. Character-oriented standard-library helpers are specified by SEP-0009.

#### Keywords

The complete reserved keyword table:

| Keyword | Purpose |
|---|---|
| `fn` | Function definition |
| `let` | Immutable binding |
| `if` / `else` | Conditional expression |
| `match` | Pattern matching expression |
| `struct` | Struct type definition |
| `type` | Type alias / sum type definition |
| `trait` | Type interface definition (trait) |
| `effect` | Effect definition / effect alias |
| `handler` | Effect handler implementation |
| `perform` | Invoke an effect operation |
| `impl` | Trait implementation block |
| `pub` / `pub(pkg)` | Visibility modifiers (public / package-visible) |
| `import` | Module import |
| `alias` | Type alias |
| `when` | Refinement predicate introducer |
| `where` | Generic type constraints |
| `uses` | Effect requirement declaration |
| `cost` | Four-slot cost vector clause |
| `spec` | Behavioral specification block in function declarations and `impl` methods |
| `example` | Concrete labeled example item inside a `spec` block |
| `law` | Universally quantified assertion inside a `spec` block |
| `spawn` | Spawn concurrent task |
| `select` | Channel multiplex expression |
| `parallel_scope` | Structured concurrency scope |
| `const` | Compile-time constant definition |
| `return` | Early return from function |
| `throw` | Throw an error value |
| `handle` | Bind effect handler expression |
| `with` | Handler binding (with handle) |
| `implements` | Reserved (use `impl ... for ...`) |
| `as` | Rename in imports |
| `in` | Reserved |
| `mut` | Reserved |
| `static` | Reserved |
| `async` | Reserved |
| `await` | Reserved spelling for postfix `.await` |
| `move` | Reserved |
| `ref` | Reserved |
| `self` | Current instance in trait/handler methods (regular identifier) |
| `super` | Parent module reference |
| `crate` | Crate root reference |
| `enum` | Reserved (use `type` with variants) |
| `union` | Reserved |
| `unsafe` | Reserved |
| `extern` | Reserved |
| `macro` | Reserved |
| `on` | Inline effect arm introducer inside `handle … with { … }` |
| `from` | Channel receive binder in `select` arms (`value from rx`) |
| `use` | Named handler binding inside `handle … with { … }` |
| `timeout` | Timeout arm in `select` expressions |
| `true` / `false` | Boolean literals |
| `Some` / `None` | Option type constructors |
| `Ok` / `Err` | Result type constructors |
| `Result` / `Option` / `Ref` | Built-in parameterized types |

**Attributes.** Function-level attributes use the `@name(args)` form — a decorator-style prefix placed before `fn` (and before any doc comment). Examples: `@allows(validate, sanitize)`, `@allow(missing_spec)`. The `@` sigil is not a standalone operator; the full attribute form is parsed as part of `FunctionHeader`.

#### Operators

| Category | Operators | Description |
|---|---|---|
| Arithmetic | `+` `-` `*` `/` `%` | Add, subtract, multiply, divide, modulo |
| Comparison | `==` `!=` `<` `>` `<=` `>=` | Equality and ordering |
| Logical | `&&` `\|\|` `!` | And, or, not |
| Bitwise | `&` `\|` `^` `~` `<<` `>>` | AND, OR, XOR, NOT, shifts |
| Pipe | `\|>` | Data-flow pipe |
| Error propagation | `?` | Propagate error from Result |
| Range | `..` `..=` | Half-open and closed range |
| Field access | `.` | Field / method access |
| Assignment | `=` | Binding assignment |
| Call | `()` | Function / method invocation |
| Index | `[]` | Index access and generic parameters |

Spore has a **fixed operator set** — no custom operators are allowed.

#### Operator precedence

13 levels, from highest to lowest:

| Level | Operators | Associativity | Description |
|---|---|---|---|
| 1 | `.` `()` `[]` | Left | Field access, call, index |
| 2 | `-` (unary) `!` `~` | Right (prefix) | Unary negation, logical not, bitwise not |
| 3 | `*` `/` `%` | Left | Multiplicative |
| 4 | `+` `-` | Left | Additive |
| 5 | `<<` `>>` | Left | Bit shift |
| 6 | `&` | Left | Bitwise AND |
| 7 | `^` | Left | Bitwise XOR |
| 8 | `\|` | Left | Bitwise OR |
| 9 | `==` `!=` `<` `>` `<=` `>=` | Non-associative | Comparison |
| 10 | `&&` | Left | Logical AND (short-circuit) |
| 11 | `\|\|` | Left | Logical OR (short-circuit) |
| 12 | `..` `..=` | Non-associative | Range |
| 13 | `\|>` | Left | Pipe |

The error propagation operator `?` is a postfix operator that binds tighter than any binary operator — it applies immediately to the preceding expression.

The assignment operator `=` appears only in `let` bindings and is not an expression-level operator.

#### Literals

**Integers:**

```text
42          // decimal
-123        // negative decimal
1_000_000   // underscore separators
0xFF        // hexadecimal
0o755       // octal
0b1010_1100 // binary
42i32       // explicitly typed signed integer
255u8       // explicitly typed unsigned integer
```

Unsuffixed integer literals default to **`I64`** unless a checking context fixes
another integer width. Suffixes are accepted for every fixed-width integer:
`i8`, `i16`, `i32`, `i64`, `u8`, `u16`, `u32`, and `u64`. Suffix overflow is a
type-checking error, not a separate grammar form.

**Floats:**

```text
3.14
-0.001
1.0e-10
2.5e+3
1_000.5
3.14f32
```

Unsuffixed floats default to **`F64`** unless a checking context fixes another
float width. Suffixes are accepted for `f32` and `f64`.

**Booleans:** `true`, `false`

**Strings** (including “single character” text as length-1 `Str` values):

```text
"Hello, World!"                    // regular string
r"C:\Users\path\to\file"          // raw string (no escapes)
f"Hello {name}, age {age}"        // format string
t"Dear {customer}, order {id}"    // template string
```

#### Comments

```spore
// Line comment

/// Doc comment (supports Markdown)
/// # Example
/// ```spore
/// let x = add(1, 2);
/// ```

/* Block comment
   /* can be nested */
   continues here
*/
```

#### Identifiers and naming conventions

| Convention | Used for | Examples |
|---|---|---|
| `snake_case` | Variables, functions, modules | `user_name`, `calculate_total`, `http_client` |
| `PascalCase` | Types, traits, effects, enum variants | `UserAccount`, `Serialize`, `Some` |
| `SCREAMING_SNAKE_CASE` | Constants | `MAX_BUFFER_SIZE`, `PI` |

### EBNF Grammar

Effect handling uses `perform <expr>`, top-level `handler <Effect> as <HandlerName>(...) { ... }`, and `handle { ... } with { ... }`. Handler-block entries are either `use HandlerName { ... }` or `on Effect.op(...) => ...`.

```ebnf
(* ═══════════════════════════════════════════════════ *)
(*  Spore — Complete EBNF Grammar                     *)
(* ═══════════════════════════════════════════════════ *)

(* ─── Top-level ───────────────────────────────────── *)

Program         = { TopLevelItem } ;

TopLevelItem    = ImportDecl
                | AliasDecl
                | StructDecl
                | TypeDecl
                | TraitDecl
                | EffectDecl
                | HandlerDecl
                | ImplDecl
                | ConstDecl
                | FunctionDecl ;

(* ─── Imports & Aliases ───────────────────────────── *)

ImportDecl      = "import" ImportPath [ "as" Ident ] ";" ;
ImportPath      = Ident { "." Ident } ;

AliasDecl       = [ Visibility ] "alias" Ident "=" QualifiedIdent ";" ;

(* ─── Module ──────────────────────────────────────── *)
(* REMOVED: Module names are derived from file paths (see SEP-0008).
   The `module` keyword is not part of the surface syntax. *)

(* ─── Struct ──────────────────────────────────────── *)

StructDecl      = [ Visibility ] "struct" Ident [ TypeParams ] StructBody ;

StructBody      = "{" FieldList "}"            (* named-field struct *)
                | "(" TypeList ")" ";"         (* tuple struct *)
                | ";" ;                        (* unit struct *)

FieldList       = Field { "," Field } [ "," ] ;
Field           = Ident ":" TypeExpr ;

(* ─── Type (sum types / aliases) ──────────────────── *)

TypeDecl        = [ Visibility ] "type" Ident [ TypeParams ]
                  "=" TypeDefBody
                  [ WhereClause ] ";" ;

TypeDefBody     = VariantList                  (* sum type *)
                | TypeExpr                     (* type alias *)
                | TypeExpr "when" Expr ;       (* refinement type; predicate may reference `self` *)

VariantList     = [ "|" ] Variant { "|" Variant } ;
Variant         = Ident [ "(" FieldList ")" ]
                | Ident [ "(" TypeList ")" ] ;

(* ─── Trait ────────────────────────────────────────── *)

TraitDecl       = [ Visibility ] "trait" Ident [ TypeParams ]
                  [ ":" BoundExpr ]
                  "{" { TraitItem } "}" ;

TraitItem       = AssocType
                | TraitFunctionSig ( ";" | Block ) ;

AssocType       = "type" Ident ";" ;

(* ─── Effect ──────────────────────────────────────── *)

EffectDecl      = [ Visibility ] "effect" Ident [ TypeParams ]
                  ( EffectBlock | "=" EffectAlias ";" ) ;

EffectBlock     = "{" { EffectOpDecl } "}" ;
EffectOpDecl    = FunctionHeader ";" ;

EffectAlias     = Ident { "|" Ident } ;

(* ─── Handler ─────────────────────────────────────── *)

HandlerDecl     = "handler" Ident "as" Ident [ "(" ParamList ")" ]
                  "{" { FunctionDecl } "}" ;

PerformExpr     = "perform" Expr ;

HandleExpr      = "handle" Block "with" HandlerBlock ;
HandlerBlock    = "{" [ HandlerEntry { "," HandlerEntry } [ "," ] ] "}" ;
HandlerEntry    = InlineHandlerBinding | NamedHandlerBinding ;
NamedHandlerBinding
                = "use" Ident "{" [ HandlerPayload { "," HandlerPayload } [ "," ] ] "}" ;
HandlerPayload  = Ident ":" Expr ;
InlineHandlerBinding
                = "on" Ident "." Ident "(" [ Ident { "," Ident } ] ")" "=>" Expr ;

(* ─── Impl (Trait Implementation) ─────────────────── *)

ImplDecl        = "impl" Ident [ TypeParams ] "for" Ident [ TypeParams ]
                  [ WhereClause ] "{" { FunctionDecl } "}" ;

(* ─── Const ───────────────────────────────────────── *)

ConstDecl       = [ Visibility ] "const" Ident ":" TypeExpr "=" Expr ";" ;

(* ─── Function Declaration ────────────────────────── *)

FunctionDecl    = FunctionSig Block ;

FunctionSig     = FunctionHeader [ SpecClause ] ;

TraitFunctionSig = FunctionHeader [ SpecClause ] ;

(* ─── Attributes ─────────────────────────────────── *)

Attribute       = "@" Ident [ "(" [ AttrArgList ] ")" ] ;
AttrArgList     = AttrArg { "," AttrArg } [ "," ] ;
AttrArg         = Ident | StringLiteral | IntLiteral ;

(* ─── Function Declaration ────────────────────────── *)

FunctionHeader  = { Attribute }
                  [ DocComment ]
                  [ Visibility ] "fn" Ident [ TypeParams ]
                  "(" [ ParamList ] ")" [ "->" TypeExpr ]
                  [ ErrorClause ]
                  [ WhereClause ]
                  [ CostClause ]
                  [ UsesClause ] ;

DocComment      = { "///" CommentText } ;

Visibility      = "pub" | "pub" "(" "pkg" ")" ;

TypeParams      = "[" TypeParam { "," TypeParam } "]" ;
TypeParam       = Ident
                | "const" Ident ":" TypeExpr ;

ParamList       = Param { "," Param } [ "," ] ;
Param           = Ident ":" TypeExpr ;

ErrorClause     = "!" TypeExpr { "|" TypeExpr } ;

WhereClause     = "where" WhereConstraint { "," WhereConstraint } ;
WhereConstraint = Ident ":" BoundExpr ;
BoundExpr       = Ident { "+" Ident } ;

UsesClause      = "uses" "[" [ EffectList ] "]" ;
EffectList      = Ident { "," Ident } ;

CostClause      = "cost" "[" CostExpr "," CostExpr "," CostExpr "," CostExpr "]" ;
CostExpr        = IntLiteral
                | Ident                        (* parameter reference *)
                | CostExpr "*" CostExpr
                | CostExpr "+" CostExpr
                | FunctionCall ;               (* e.g., log2(n) *)
FunctionCall    = Ident "(" [ ArgList ] ")" ;

(* ─── Spec Clause ─────────────────────────────────── *)

SpecClause      = "spec" "{" { SpecItem } "}" ;

SpecItem        = ExampleItem
                | LawItem ;

ExampleItem     = "example" StringLiteral ":" Expr
                | "example" StringLiteral Block ;

LawItem         = "law" StringLiteral ":" LawLambdaExpr ;

LawLambdaExpr   = "|" [ LawParamList ] "|" ( Expr | Block ) ;
LawParamList    = LawParam { "," LawParam } [ "," ] ;
LawParam        = Ident ":" TypeExpr [ "when" Expr ] ;

(* ─── Type Expressions ────────────────────────────── *)

TypeExpr        = Ident [ "[" TypeList "]" ]           (* named type, optionally generic *)
                | "fn" "(" [ TypeList ] ")" "->" TypeExpr  (* function type *)
                | "(" TypeList ")"                      (* tuple type *)
                | "Self"                                (* self type in traits/handlers *)
                | "?" ;                                 (* type hole *)

TypeList        = TypeExpr { "," TypeExpr } [ "," ] ;

QualifiedIdent  = Ident { "." Ident } ;

(* ─── Expressions ─────────────────────────────────── *)

Expr            = LetExpr
                | IfExpr
                | MatchExpr
                | LambdaExpr
                | ReturnExpr
                | ThrowExpr
                | PerformExpr
                | SpawnExpr
                | SelectExpr
                | ParallelScopeExpr
                | HandleExpr
                | PipeExpr ;

PipeExpr        = OrExpr { "|>" OrExpr } ;

OrExpr          = AndExpr { "||" AndExpr } ;
AndExpr         = CompareExpr { "&&" CompareExpr } ;

CompareExpr     = BitwiseOrExpr [ CompareOp BitwiseOrExpr ] ;
CompareOp       = "==" | "!=" | "<" | ">" | "<=" | ">=" ;

BitwiseOrExpr   = BitwiseXorExpr { "|" BitwiseXorExpr } ;
BitwiseXorExpr  = BitwiseAndExpr { "^" BitwiseAndExpr } ;
BitwiseAndExpr  = ShiftExpr { "&" ShiftExpr } ;

ShiftExpr       = AddExpr { ( "<<" | ">>" ) AddExpr } ;

AddExpr         = MulExpr { ( "+" | "-" ) MulExpr } ;
MulExpr         = UnaryExpr { ( "*" | "/" | "%" ) UnaryExpr } ;

UnaryExpr       = ( "-" | "!" | "~" ) UnaryExpr
                | PostfixExpr ;

PostfixExpr     = PrimaryExpr { PostfixOp } ;
PostfixOp       = "?" | "." "await" | "." Ident | "." Ident "(" [ ArgList ] ")"
                | "(" [ ArgList ] ")" | "[" Expr "]"
                | "[" [ Expr ] ".." [ Expr ] "]"
                | "[" [ Expr ] "..=" Expr "]" ;

PrimaryExpr     = Literal
                | Ident
                | QualifiedIdent
                | "(" Expr ")"
                | Block
                | StructLiteral
                | ListLiteral
                | HoleExpr ;

(* ─── Specific Expression Forms ───────────────────── *)

LetExpr         = "let" Pattern [ ":" TypeExpr ] "=" Expr ";" ;

IfExpr          = "if" Expr Block [ "else" ( IfExpr | Block ) ] ;

MatchExpr       = "match" Expr "{" { MatchArm } "}" ;
MatchArm        = Pattern [ "if" Expr ] "=>" Expr "," ;

LambdaExpr      = "|" [ LambdaParams ] "|" ( Expr | Block ) ;
LambdaParams    = LambdaParam { "," LambdaParam } ;
LambdaParam     = Ident [ ":" TypeExpr ] ;

ReturnExpr      = "return" [ Expr ] ;
ThrowExpr       = "throw" Expr ;

SpawnExpr       = "spawn" Block ;

SelectExpr      = "select" "{" { SelectArm } "}" ;
SelectArm       = Ident "from" Expr "=>" Expr ","
                | "timeout" "(" Expr ")" "=>" Expr "," ;

ParallelScopeExpr = "parallel_scope" Block ;

Block           = "{" { Statement } [ Expr ] "}" ;
Statement       = Expr ";"
                | LetExpr
                | FunctionDecl ;               (* local function *)

(* ─── Struct & List Literals ──────────────────────── *)

StructLiteral   = QualifiedIdent "{" FieldInitList "}" ;
FieldInitList   = FieldInit { "," FieldInit } [ "," ] ;
FieldInit       = Ident ":" Expr
                | Ident ;                      (* field punning *)

ListLiteral     = "[" [ ExprList ] "]" ;
ExprList        = Expr { "," Expr } [ "," ] ;

ArgList         = Expr { "," Expr } [ "," ] ;

(* ─── Patterns ────────────────────────────────────── *)

Pattern         = OrPattern ;
OrPattern       = SinglePattern { "|" SinglePattern } ;

SinglePattern   = LiteralPattern
                | WildcardPattern
                | BindingPattern
                | ConstructorPattern
                | StructPattern
                | ListPattern
                | "(" Pattern ")" ;

LiteralPattern  = IntLiteral | FloatLiteral | StringLiteral
                | "true" | "false" ;
WildcardPattern = "_" ;
BindingPattern  = Ident ;

ConstructorPattern = QualifiedIdent "(" [ PatternList ] ")" ;
StructPattern   = QualifiedIdent "{" FieldPatternList [ "," ".." ] "}" ;
FieldPatternList= FieldPattern { "," FieldPattern } ;
FieldPattern    = Ident ":" Pattern
                | Ident ;                      (* field punning *)

ListPattern     = "[" [ ListPatternElems ] "]" ;
ListPatternElems= Pattern { "," Pattern } [ "," ".." Ident ] ;

PatternList     = Pattern { "," Pattern } [ "," ] ;

(* ─── Hole ────────────────────────────────────────── *)

HoleExpr        = "?"
                | "?" Ident
                | "?" Ident ":" TypeExpr ;

(* ─── Literals ────────────────────────────────────── *)

Literal         = IntLiteral | FloatLiteral | BoolLiteral
                | StringLiteral ;

IntLiteral      = ( DecimalInt | HexInt | OctalInt | BinaryInt ) [ IntSuffix ] ;
DecimalInt      = [ "-" ] Digit { Digit | "_" } ;
HexInt          = "0x" HexDigit { HexDigit | "_" } ;
OctalInt        = "0o" OctDigit { OctDigit | "_" } ;
BinaryInt       = "0b" BinDigit { BinDigit | "_" } ;
IntSuffix       = "i8" | "i16" | "i32" | "i64"
                | "u8" | "u16" | "u32" | "u64" ;

FloatLiteral    = [ "-" ] Digit { Digit | "_" } "." Digit { Digit | "_" }
                  [ ( "e" | "E" ) [ "+" | "-" ] Digit { Digit } ]
                  [ FloatSuffix ] ;
FloatSuffix     = "f32" | "f64" ;

BoolLiteral     = "true" | "false" ;

StringLiteral   = '"' { StringChar } '"'
                | 'r"' { RawChar } '"'
                | 'f"' { FStringPart } '"'
                | 't"' { TStringPart } '"' ;

FStringPart     = FStringText | "{" Expr "}" ;
TStringPart     = FStringText | "{" Expr "}" ;

EscapeSeq       = "\\" ( "n" | "t" | "r" | "\\" | '"' | "0"
                | "u{" HexDigit { HexDigit } "}" ) ;
StringChar      = EscapeSeq | ? any Unicode scalar except `"` or `\` ? ;
FStringText     = EscapeSeq | ? any Unicode scalar except `"`, `\`, `{`, or `}` ? ;
RawChar         = ? any Unicode scalar except `"` ? ;
CommentText     = ? any text until line end ? ;

(* ─── Identifier ──────────────────────────────────── *)

Ident           = ( Letter | "_" ) { Letter | Digit | "_" } ;
Letter          = "a".."z" | "A".."Z" | UnicodeLetter ;
UnicodeLetter   = ? any Unicode scalar with the Unicode Letter property ? ;
Digit           = "0".."9" ;
HexDigit        = Digit | "a".."f" | "A".."F" ;
OctDigit        = "0".."7" ;
BinDigit        = "0" | "1" ;
```

### Function signature layout

Function clauses appear in this canonical order:

```text
fn <name>[<generics>](<params>) -> <ReturnType> [! <ErrorTypes>]
[where <GenericName>: <Constraint>, ...]
[cost [<compute_expr>, <alloc_expr>, <io_expr>, <parallel_expr>]]
[uses [<Effect>, ...]]
[spec { <examples and laws> }]
{
    <body>
}
```

SEP-0001 owns this order and the delimiter forms. Clause meaning is delegated:
return and error typing to SEP-0002, cost checking to SEP-0004, effect checking
to SEP-0003, `spec` execution and diagnostics to SEP-0006, and any
hole-specific projection of signature metadata to SEP-0005.

**Clause ordering** is the canonical source and formatter order: `where` →
`cost` → `uses` → `spec`.

**`self` in trait and handler methods:** The `self` identifier is a regular parameter name used as the first parameter in trait method signatures. It is not a keyword with special scoping rules.

```spore
trait Display {
    fn to_string(self) -> Str;
}

trait Collection {
    type Item;
    fn len(self) -> I64;
    fn is_empty(self) -> Bool {
        self.len() == 0
    }
}
```

### Expression forms

This section summarizes syntax only. Expression typing, evaluation order,
exhaustiveness checking, closure capture, lowering, and error propagation
semantics are delegated to SEP-0002 and SEP-0006.

**Blocks** use `{ ... }` with semicolon-terminated statements and an optional
tail expression.

**If expressions** use `if Expr Block [else (IfExpr | Block)]`.

**Match expressions** use `match Expr { Pattern [if Expr] => Expr, ... }`.

**Lambda expressions** use `|params| expr` or `|params| { ... }`.

**Pipe expressions** use `left |> right`.

**Try expressions** use postfix `?`.

### Pattern matching details

Supported pattern forms:

| Pattern | Syntax | Example |
|---|---|---|
| Literal | `42`, `"hello"`, `true` | `0 => "zero"` |
| Variable binding | `name` | `Some(x) => x` |
| Wildcard | `_` | `_ => "other"` |
| Constructor | `Ctor(p1, p2)` | `Some(value) => value` |
| Struct | `Name { f1, f2, .. }` | `Point { x, y } => x + y` |
| List (empty) | `[]` | `[] => "empty"` |
| List (head..tail) | `[h, ..t]` | `[head, ..tail] => head` |
| List (exact) | `[a, b]` | `[a, b] => a + b` |
| Or | `p1 \| p2` | `"Sat" \| "Sun" => true` |
| Guard | `p if cond` | `n if n > 0 => "positive"` |
| Nested | `Ok(Some(x))` | `Ok(Some(v)) => v` |

### Type system

This subsection is a syntax-facing overview. SEP-0002 is authoritative for primitive type meaning, inference, refinement checking, trait resolution, and type display.

**Primitive type names:** `I8`, `I16`, `I32`, `I64`, `U8`, `U16`, `U32`, `U64`, `F32`, `F64`, `Bool`, `Str`, `Unit`, and `Never`.

**Collection type syntax:** `List[T]`, `Vec[T, max: N]`, `Map[K, V]`, `Set[T]`, and `Array[T, N]`.

**Special types:** `Option[T]`, `Result[T, E]`, `Ref[T]`, `Channel[T]`, `Unit`

**Const generics:** `struct Array[T, const N: I64] { ... }`

```spore
struct Array[T, const N: I64] {
    data: List[T],
}

struct Matrix[T, const ROWS: I64, const COLS: I64] {
    data: Array[Array[T, COLS], ROWS],
}
```

Const-generic checking and collection invariants are specified by SEP-0002 and
the relevant standard-library SEP.

**Refinement types:** `type PositiveInt = I64 when self > 0;`

**Function types:** `fn(I64, I64) -> I64`

### Concurrency primitives

Concurrency forms:

- `parallel_scope { ... }`
- `spawn { expr }`
- `select { ... }`
- `task.await`

SEP-0007 owns the semantics of these forms.

### Hole syntax

Holes are expressions:

```spore
?
?name
?name : Type
```

SEP-0001 owns these spellings only. Partial-function status, hole typing,
pipeline inference, `@allows`, JSON output, and any `spec` metadata surfaced to
hole tooling are owned by SEP-0005.

## Complete examples

Complete semantic examples are intentionally deferred to the SEPs that own the
corresponding behavior.

```spore
type Expr =
    Literal(I64)
    | Add(left: Expr, right: Expr);

fn eval(expr: Expr) -> I64 {
    match expr {
        Literal(n) => n,
        Add(left, right) => eval(left) + eval(right),
    }
}
```

More complete examples for type checking, effects, cost, holes, concurrency,
module resolution, and standard-library APIs belong to SEP-0002 through SEP-0009.

## Human experience impact

### Readability

Spore's syntax prioritizes scannability. The fixed operator set prevents
source-local operator definitions from changing parsing rules. The pipe operator
linearizes deeply nested function calls. The `uses` clause makes side effects
visible in the function signature. Exhaustiveness requirements for `match` are
specified by SEP-0002.

### Learning curve

- **Developers from Rust/TypeScript**: Curly braces, semicolons, `let`, `match`, `fn`, and explicit generic syntax are familiar. The main additional forms are `uses`, `cost`, and `!` clauses.
- **Developers from Python/JavaScript**: Static types and explicit error sets require adjustment. F-strings, lambdas, and pipe-style composition remain familiar entry points.
- **Developers from Haskell/OCaml**: Pattern matching, ADTs, and expression-oriented syntax are familiar. Curly braces replace significant whitespace.

### Progressive disclosure

Simple functions do not require optional clauses:
`fn add(a: I64, b: I64) -> I64 { a + b }`. Effects, error sets, `cost [...]`,
and `spec { ... }` are introduced only when the function signature requires
that metadata.

## Agent experience impact

Code-generation agents are an explicit tooling audience for the syntax:

### Parsing predictability

- **Fixed operator set**: Agents never need to resolve custom operators or precedence ambiguities.
- **Regular grammar**: No significant whitespace, no optional semicolons, no implicit returns outside blocks. Every syntactic form is delimited by explicit tokens.
- **Keyword-introduced clauses**: `where`, `cost`, `uses`, `!` are unambiguous clause starters.

### Structured metadata

Function signatures are machine-readable contracts. SEP-0001 defines stable
positions and delimiters for:

- **Input/output types** from the parameter list and return type
- **Failure modes** from the `! ErrorSet`
- **Side effect profile** from `uses [...]`
- **Performance budget** from the `cost [compute, alloc, io, parallel]` clause
- **Generic requirements** from `where` clauses

How agents interpret those clauses is owned by the type, effect, cost, hole, and
compiler SEPs.

### Code generation

Agents can generate Spore code incrementally using holes (`?`). SEP-0005 owns the
hole-filling workflow and related annotations.

### Snapshot hashing

SEP-0001 defines the surface components that can participate in hashing.
Snapshot hashing, spec hashing, and approval flags are specified in SEP-0006 and
SEP-0008.

## Structured representation / protocol impact

### AST structure

The Spore AST is designed as a regular tree with strongly typed nodes. Key node types:

```text
Program
├── ImportDecl { path, alias? }
├── StructDecl { name, type_params[], fields[] }
├── ImplDecl { trait, type_params[], target_type, methods[] }
├── TypeDecl { name, type_params[], body: TypeAlias | SumType | Refinement }
├── TraitDecl { name, type_params[], items[] }
├── EffectDecl { name, type_params[], operations[] }
├── HandlerDecl { name, effect, methods[] }
├── ConstDecl { name, type, value }
└── FunctionDecl
    ├── name
    ├── type_params[]
    ├── params[]
    ├── return_type?
    ├── error_set[]
    ├── where_clauses[]
    ├── uses[]
    ├── cost?
    ├── spec?
    │   ├── examples[]
    │   └── laws[]
    └── body: Block

Expr
├── Literal { kind, value }
├── Ident { name }
├── Block { stmts[], tail_expr? }
├── If { condition, then_block, else_block? }
├── Match { scrutinee, arms[] }
├── Lambda { params[], body }
├── BinOp { op, left, right }
├── UnaryOp { op, operand }
├── Call { callee, args[] }
├── FieldAccess { object, field }
├── Index { object, index }
├── Pipe { left, right }
├── Try { expr }               (* ? operator *)
├── Spawn { body }
├── Select { arms[] }
├── ParallelScope { body }
├── Return { value? }
├── Throw { value }
├── Hole { name?, type? }
├── StructLiteral { name, fields[] }
├── ListLiteral { elements[] }
└── Range { start?, end?, inclusive }
```

### LSP integration

The regular, keyword-delimited syntax supports straightforward LSP provider implementations:

- **Go to definition**: Every identifier resolves unambiguously through module paths and lexical scoping.
- **Hover information**: Function signatures can be displayed in full because clause order is fixed.
- **Completions**: Keyword-delimited positions such as `uses [...]` and `spec { ... }` are easy to identify.
- **Diagnostics**: Parser and formatter diagnostics can point to exact clause positions; semantic diagnostics are owned by dependent SEPs.
- **Signature help**: The ordered clause structure (`where` → `cost` → `uses` → `spec`) enables progressive parameter info display.

### Serialization

The AST serializes naturally to JSON, S-expressions, or any tree-structured format. The fixed set of node types ensures forward compatibility.

## Diagnostics impact

SEP-0001 enables precise syntax diagnostics because blocks, clauses, and
operators have fixed delimiters and a fixed order. Diagnostic codes, recovery
strategy, semantic errors, `spec` failures, and JSON diagnostic shape are owned
by SEP-0006.

## Drawbacks

1. **No loops**: Developers with imperative backgrounds must express iteration
   through recursion or library functions, including simple counting patterns.

2. **Verbose error sets**: Functions that can fail in many ways produce long
   `! E1 | E2 | E3 | ...` lists. This makes failures visible but can lengthen
   signatures.

3. **`cost` clause expressiveness**: The cost expression envelope may be
   insufficient for complex algorithms. SEP-0004 owns the verification model and
   diagnostics for inaccurate bounds.

4. **No custom operators**: Domains like linear algebra or DSLs sometimes benefit from custom operators. Spore sacrifices this for predictability.

5. **Square bracket overload**: `[]` is used for generics, list literals, index access, and the `uses`/error clauses. Context resolves ambiguity, but it adds parser complexity.

6. **Keyword count**: The reserved keyword set is large (40+), which constrains identifier names and increases the language surface area.

7. **No explicit effect-property clause**: Effect attributes inferred from
   `uses` are not written at the declaration site. SEP-0003 owns how those
   attributes are reported by tooling.

## Alternatives considered

### Loop constructs

We considered including a minimal loop construct, for example Rust's `loop` or a
`foreach` form, but rejected it because:

- It would introduce a second iteration style into the core grammar.
- Recursion and library functions provide the single accepted iteration style.
- Higher-order library functions such as `map`, `fold`, and `filter` cover common iteration patterns.
- A single iteration style simplifies formatter, analyzer, and agent behavior.

### Angle brackets for generics (`List<I64>`)

Rejected because:

- Angle brackets create parsing ambiguity with comparison operators (`a < b > c`).
- Square brackets align with Python type hints (`List[int]`).
- The choice matches existing precedent in modern typed languages.

### `with` clause for explicit effect properties

The original design included `with [pure, deterministic]` for explicit effect
attribute annotation. This was removed because:

- Effect attributes are derivable from the `uses` set.
- Redundant annotations can diverge from inferred effect facts.
- The compiler can display inferred properties in IDE hover and `--explain` output.

### Significant whitespace (Python/Haskell style)

Rejected because:

- Whitespace sensitivity hinders machine generation and transformation.
- Copy-paste errors are harder to debug.
- Curly braces provide explicit, unambiguous scope boundaries.

### `do` notation for monadic composition

Rejected in favor of the `?` operator and `|>` pipes because:

- `?` is simpler for the common case of error propagation.
- `|>` provides general-purpose composition without requiring monad understanding.
- Keeping the concept count low aids learnability.

### Roc-style inline `implements` for trait implementation

The original design used Roc-style inline `implements [...]` on struct declarations. This was replaced by Rust-style `impl Trait for Type { ... }` blocks because:

- Separate `impl` blocks allow implementing third-party traits for existing types.
- Multiple implementations are visually distinct rather than packed into a single line.
- It aligns with the Rust mental model that most Spore users already know.
- The `implements` keyword is reserved for potential future use.

### Exception-based error handling

Rejected because:

- Invisible control flow violates the principle of explicit effects.
- Error sets in signatures enable static analysis and agent reasoning.
- `?` keeps the common success path concise while preserving explicit error sets.

## Prior art

### Rust

Heavy influence on: curly-brace syntax, semicolon semantics (expression vs. statement), `match` exhaustiveness, `?` error propagation, `where` clauses, `let` bindings, closure syntax (`|x| x`), pattern matching, enum/struct distinction.

Departed from: Spore removes lifetime annotations, borrowing semantics, `mut` keyword, `loop`/`for`/`while`, and trait orphan rules. Spore adopts Rust-style `impl Trait for Type` blocks.

### Roc

Influence on: expression-based design, the trait/effect split design, no-loop philosophy, the idea of making side effects visible in signatures.

### Gleam

Influence on: square brackets for generics, use of `|>` pipe operator as a core language feature, and a small fixed-operator language surface.

### Elm

Influence on: the emphasis on helpful error messages, exhaustive pattern matching as a reliability tool, the no-runtime-exception philosophy, and progressive disclosure of type system features.

### OCaml / F

Influence on: algebraic data types with `|` variant syntax, pattern matching with guards, expression-based design, the pipe operator (`|>` originates from F#).

### Haskell

Influence on: type classes (→ traits), purity by default, the idea of tracking effects in types, `where` clause syntax for constraints.

### TypeScript / Python

Influence on: f-string syntax (`f"...{expr}..."`), postfix type annotations (`name: Type`), and square brackets for generics (Python).

### Koka

Influence on: algebraic effect system design, the idea that effects should be inferred rather than manually annotated, row-polymorphic effects informing the `uses` auto-inference system.

## Backward compatibility and migration

As this is the initial root syntax specification, there are no backward compatibility concerns.

### Future compatibility considerations

1. **Keyword reservation**: The large reserved keyword set is intentional — it preserves room for future features (e.g., `async`, `unsafe`, `macro`) without breaking existing code.

2. **Signature evolution**: Future SEPs that modify signature clause syntax must
   define migration tooling and specify their interaction with signature or
   snapshot hashing.

3. **Cost model changes**: The `cost` clause semantics may evolve. Future changes should define a migration story so that cost bounds written today remain meaningful.

4. **New expression forms**: The grammar is designed to be extensible — new expression forms can be added as new `PrimaryExpr` alternatives without disturbing existing productions.

5. **Standard library stability**: Type names like `Option`, `Result`, `List`, `Map` are part of the language surface. Renaming these would require an explicit breaking-change migration.

## Unresolved questions

SEP-0001 has no unresolved questions that block accepting the root syntax
surface. The following decisions are accepted here because they affect grammar
or signature layout:

1. **`throw`** is a core expression form. SEP-0001 owns only its spelling and
   placement; SEP-0002 owns its error-channel typing and lowering.

2. **Placeholder partial application** is a general call-position form:
   `f(_, y)` creates a lambda over the placeholder argument. Pipe use such as
   `x |> f(_, y)` is a direct application of that same rule.

3. **Interpolation boundaries** are fixed for this accepted surface: both `f"..."` and `t"..."`
   embed Spore expressions. SEP-0009 owns template rendering and sanitization.

4. **String patterns** are literal patterns only. Regex, prefix, suffix, or
   other string-pattern forms require a future syntax SEP.

5. **Behavioral `spec` blocks** are accepted on ordinary function declarations,
   trait method signatures, and `impl` methods. Trait-method contract
   inheritance or merging is not part of SEP-0001.

6. **Negative examples** are not part of the accepted `spec` grammar. The only
   accepted `spec` item keywords are `example` and `law`.

### Delegated to dependent SEPs

- **Type and refinement semantics**: SEP-0002 owns primitive type meaning,
  type inference, refinement checking, method dispatch, and error-set
  canonicalization.
- **Effect composition and taxonomy**: SEP-0003 owns effect-set union,
  alias expansion, handler discharge, and future effect vocabulary changes.
- **Cost units and verification**: SEP-0004 owns cost dimensions, units,
  recursion analysis, and verification algorithms.
- **Hole reporting and partial-function status**: SEP-0005 owns HoleReport
  fields, dependency graphs, and agent workflow.
- **Compiler/runtime guarantees**: SEP-0006 owns formatter enforcement,
  diagnostics, lowering, and runtime implementation details.
- **Concurrency behavior**: SEP-0007 owns `spawn`, `await`, `select`, task
  lifetime, cancellation, and channel semantics.
- **Module resolution**: SEP-0008 owns circular dependencies, import resolution,
  package manifests, and content-addressed hashing.
- **Standard-library names and behavior**: SEP-0009 owns prelude items,
  collection APIs, string helpers, and platform-facing library modules.

## Appendix A: Delegated semantics

SEP-0001 intentionally does not define operational semantics. Evaluation order,
type preservation, effect soundness, hole runtime behavior, `spec` execution,
standard-library operations, and concurrency runtime rules are delegated to
SEP-0002 through SEP-0009.
