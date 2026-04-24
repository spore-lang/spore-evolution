---
sep: 1
title: "SEP-0001: Core Syntax & Signatures"
status: Draft
type: Standards Track
authors:
  - Spore maintainers
created: 2026-03-31
requires: []
discussion: "https://github.com/spore-lang/spore-evolution/discussions/1"
pr: null
superseded_by: null
---

# SEP-0001: Core Syntax & Signatures

> **Executive Summary**: Defines Spore's core syntax as an expressions-only language with no statements or loops — all iteration uses recursion and higher-order functions (map/fold/filter/each). Introduces unified function signatures with a fixed clause order (return → errors → where → uses → cost → spec → body), pattern matching as the primary control flow, and a clean separation between pure computation and effectful operations. Traits define type interfaces while effects track external operations; the compiler infers purity and determinism from the declared effect set. The `spec` clause embeds typechecked behavioral contracts (examples and properties) directly in function signatures, making intent visible to the compiler, documentation, and hole-reporting tooling.

## Summary

This proposal defines the complete core syntax and function signature system for the Spore programming language v0.1. Spore is an expression-based, statically typed language with effect tracking, explicit resource cost tracking, and guaranteed tail-call optimization. The language draws from Rust, OCaml, Roc, Gleam, and Elm, combining curly-brace block scoping with Rust-style semicolon semantics, algebraic data types, exhaustive pattern matching, and a novel function signature system that encodes generic constraints (`where`), effect requirements (`uses`), error sets (`!`), and cost bounds (`cost`) as composable clauses. Spore deliberately eliminates loops in favor of recursion and higher-order functions, uses square brackets for generics (`List[Int]`), auto-infers effect properties from the `uses` set, and provides a pipe operator (`|>`) for readable data-flow composition.

## Motivation

Modern programming languages force developers to choose between safety and ergonomics. Rust provides strong safety guarantees but with significant syntactic and cognitive overhead. Functional languages like Haskell and OCaml offer powerful type systems but often feel alien to developers from imperative backgrounds. Meanwhile, AI agents that generate and analyze code need languages whose structure is predictable and machine-parseable.

Spore aims to occupy a unique design point:

1. **Human-first readability**: Expression-based syntax with familiar curly braces and semicolons reduces the learning curve for developers coming from Rust, TypeScript, or Kotlin, while the pipe operator and pattern matching enable expressive functional composition.

2. **Agent-friendly structure**: A fixed operator set (no custom operators), regular grammar, and explicit function metadata (`uses`, `cost`, `where`) make Spore code trivially parseable by AI agents and static analysis tools. Every function signature is a structured contract.

3. **Effect safety by default**: Rather than bolting on an effect system after the fact, Spore makes effect requirements a first-class part of function signatures. The compiler infers properties like `pure` and `deterministic` from the declared `uses` set, eliminating manual annotation burden while maintaining full transparency.

4. **No loops — recursion with TCO guarantee**: By removing `for`, `while`, `loop`, `break`, and `continue`, Spore encourages a purely functional iteration style via recursion and higher-order functions (`map`, `fold`, `filter`). The compiler guarantees tail-call optimization, making recursion safe and efficient.

5. **Incremental elaboration**: The signature system is designed so that a simple pure function has zero overhead (`fn add(x: Int, y: Int) -> Int`), while complex functions progressively add clauses only as needed. This avoids the "all or nothing" annotation burden seen in many effect systems.

6. **Cost transparency**: The `cost` clause enables compile-time reasoning about resource consumption, supporting smart-contract use cases and agent-driven cost optimization.

## Guide-level explanation

This section introduces Spore's syntax from a user's perspective, building from the simplest forms to the most complex.

### Your first Spore function

The simplest Spore function looks familiar to anyone who has used Rust, Go, or TypeScript:

```spore
fn add(a: Int, b: Int) -> Int {
    a + b
}
```

Note: no `return` keyword is needed. The last expression in a block is its value. The compiler automatically infers that this function is `pure`, `deterministic`, and `total` because it uses no effects.

### Variables and immutability

All bindings are immutable by default:

```spore
let name = "Alice";
let age = 30;
let greeting = f"Hello, {name}! You are {age} years old.";
```

Shadowing is allowed — you can rebind a name in the same scope:

```spore
let x = 10;
let x = x + 5;  // shadows the previous x
```

For local mutable state, use `Ref[T]`. This is separate from the built-in external effect vocabulary standardized in SEP-0003, so it does not introduce a dedicated built-in `uses` name:

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

`match` expressions must be exhaustive — the compiler ensures all cases are covered:

```spore
type Shape =
    | Circle(radius: Float)
    | Rectangle(width: Float, height: Float)
    | Triangle(base: Float, height: Float);

fn area(shape: Shape) -> Float {
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

### No loops — recursion and HOFs

Spore has **no** `for`, `while`, `loop`, `break`, or `continue`. All iteration uses recursion (with guaranteed TCO) or higher-order functions:

```spore
// Sum a list using fold
fn sum(numbers: List[Int]) -> Int {
    numbers.fold(0, |acc, x| acc + x)
}

// Factorial using tail recursion (TCO guaranteed)
fn factorial(n: Int) -> Int {
    fn go(n: Int, acc: Int) -> Int {
        if n <= 1 { acc } else { go(n - 1, n * acc) }
    }
    go(n, 1)
}

// Filter and transform using HOFs
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
```

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
    | NotFound(path: String)
    | PermissionDenied(path: String)
    | IoError(message: String);

fn read_config(path: String) -> Config ! FileError | ParseError {
    let content = read_file(path)?;     // propagates FileError
    let config = parse_toml(content)?;  // propagates ParseError
    config
}
```

#### Error conversion

When a function's error set differs from a callee's, Spore can automatically convert errors if a conversion exists:

```spore
fn load_config(path: String) -> Config ! ConfigError {
    let content = read_file(path)?;       // FileError -> ConfigError (auto-converted)
    let config = parse_toml(content)?;    // ParseError -> ConfigError (auto-converted)
    config
}
```

The compiler looks for a `From` trait implementation (e.g., `impl From[FileError] for ConfigError`) to perform the conversion. If no conversion exists, the error type must be listed in the function's error set directly.

#### Error recovery patterns

Use `match` on `Result` to provide fallback values or retry logic:

```spore
// Default value fallback
fn get_config() -> Config {
    match load_config("config.toml") {
        Ok(config) => config,
        Err(_) => Config.default(),
    }
}

// Retry with tail recursion (TCO guaranteed)
fn fetch_with_retry(url: String, max_retries: Int) -> Data ! NetworkError {
    fn retry(url: String, attempts: Int, max: Int) -> Data ! NetworkError {
        match fetch(url) {
            Ok(data) => data,
            Err(NetworkError.Timeout) if attempts < max => {
                sleep(1000);
                retry(url, attempts + 1, max)  // tail recursion
            },
            Err(e) => throw e,
        }
    }
    retry(url, 0, max_retries)
}
```

### Generic types with square brackets

Spore uses square brackets for generics, not angle brackets:

```spore
type Option[T] =
    | Some(T)
    | None;

type Result[T, E] =
    | Ok(T)
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

The full signature order is:

```text
fn name[T](params) -> ReturnType ! ErrorSet
where T: Bound
uses [Effect1, Effect2]
cost ≤ N
spec {
    example "...": ...
    property "...": |param: Type| ...
}
{
    body
}
```

But you only write what you need:

```spore
// 1. Simple pure function — zero overhead
fn add(a: Int, b: Int) -> Int {
    a + b
}

// 2. Function with errors
fn parse_int(input: String) -> Int ! InvalidFormat {
    ...
}

// 3. With generic constraints and behavioral spec
fn serialize[T](value: T) -> Bytes ! SerializeError
where T: Serialize
cost ≤ 500
spec {
    example "empty struct": serialize(Empty {}) == Ok(b"")
}
{
    ...
}

// 4. Side-effectful function with intent examples
/// @idempotent
fn sync_user_data(user_id: UserId, source: DataSource) -> SyncReport ! NetworkTimeout | AuthExpired
uses [NetConnect, FileRead, Clock]
cost ≤ 8500
spec {
    example "returns report on success" {
        let report = sync_user_data(UserId(1), MockSource.success());
        report.is_ok() && report.unwrap().records_synced > 0
    }
    property "idempotent": |id: UserId| {
        let r1 = sync_user_data(id, MockSource.success());
        let r2 = sync_user_data(id, MockSource.success());
        r1 == r2
    }
}
{
    ...
}
```

### Traits, effects, and the `uses` clause

Spore separates type interfaces from effect tracking:

This section is the **normative surface syntax** for these forms. SEP-0002 and SEP-0003 reference the same constructs semantically rather than re-specifying their grammar.

```spore
// trait: type interface
trait Display {
    fn show(self) -> Str
}

trait Serialize {
    fn serialize(self) -> Bytes ! SerializeError
}

// effect: external world operations
effect Console {
    fn println(msg: Str) -> ()
    fn read_line() -> Str ! IoError
}

// effect alias (uses | for union)
effect HttpClient = NetConnect | Clock
effect CLI = Console | FileRead | FileWrite | Env | Spawn | Exit
```

Effect operations and handler binding are also centralized here. `perform` is a reserved keyword for effect-operation expressions. The settled handler grammar is `handler <Effect> as <HandlerName>(...) { ... }` for declarations and `handle { ... } with { ... }` for installation: the `with` block may contain inline effect arms via `on Effect.op(...) => ...` and/or named handler installations via `use HandlerName { ... }`. SEP-0003 defines the effect algebra and handler semantics; this SEP fixes the corresponding surface syntax.

The `uses` clause declares what effects a function requires. The compiler **auto-infers** effect properties from this set:

| `uses` set | Inferred properties |
|---|---|
| `uses []` (or omitted for pure) | `pure`, `deterministic`, `total` |
| `uses [FileRead]` | `deterministic` |
| Contains `Random` or `Clock` | neither `pure` nor `deterministic` |

The `idempotent` property cannot be inferred and is annotated via doc comment: `/// @idempotent`.

The `uses` clause can mix atomic effect names with named effect aliases:

```spore
fn query_database(sql: Str) -> Data ! DbError | Timeout
uses [NetConnect]
{
    ...
}

fn run_cli(config_path: Str) -> () ! Error
uses [CLI]
{
    ...
}
```

### Behavioral specification (`spec` clause)

Spore functions can include a `spec` block that expresses behavioral intent as typechecked contracts. The `spec` clause sits after `where`, `uses`, and `cost`, immediately before the function body — making intent structurally part of the signature, visible to the compiler, surfaced in documentation, and available to testing and hole-reporting tooling.

```spore
fn add(a: Int, b: Int) -> Int
spec {
    example "positive inputs": add(2, 3) == 5
    example "identity":        add(0, 42) == 42
    example "commutativity":   add(1, 2) == add(2, 1)
}
{
    a + b
}
```

**`example` items** are concrete labeled test cases. The body must evaluate to `Bool`:

```spore
// Equality form (most common)
example "parses ISO date": parse_date("2024-01-15") == Ok(Date(2024, 1, 15))

// Boolean form
example "rejects empty string": parse_date("").is_err()

// Multi-line form — last expression (without semicolon) is the result
example "handles leap year" {
    let d = parse_date("2024-02-29");
    d == Ok(Date(2024, 2, 29))
}
```

**`property` items** express universally quantified assertions using explicitly typed lambda syntax. The compiler generates random inputs for property-based testing:

```spore
fn parse_date(s: String) -> Result[Date, ParseError] ! ParseError
spec {
    example "ISO 8601":          parse_date("2024-01-15") == Ok(Date(2024, 1, 15))
    example "rejects ambiguous": parse_date("01/15/24")   == Err(AmbiguousFormat)

    property "total":      |s: String| parse_date(s).is_ok() || parse_date(s).is_err()
    property "round-trip": |d: Date| parse_date(d.to_iso_string()) == Ok(d)
}
{
    ?parse_logic
}
```

Key design properties:

- **Spec metadata survives hole bodies**: A function with `{ ?hole }` still retains its `spec` items for type checking, documentation, and HoleReport output. However, executing those spec items still calls the function body, so a hole remains a runtime error until the body is filled.
- **Current amendment scope**: This amendment defines `spec` for ordinary function declarations and `impl` methods with bodies. Trait-method `spec` syntax and inheritance semantics are deferred to a later amendment.
- **MissingSpec warning**: `pub` functions without a `spec` block emit a compiler warning (not error), encouraging behavioral documentation without forcing it.

Effect operations and handler binding are also centralized here. `perform` is a reserved keyword for effect-operation expressions. `handle` accepts one or more `with` clauses. SEP-0003 defines the effect algebra and handler semantics; this SEP only fixes the settled outer syntax. The grammar intentionally leaves each handler operand as an expression because the richer handler/`handle` model is still pending the item-3 decision.

### Struct and type definitions

```spore
// Named-field struct
struct User {
    id: Int,
    name: String,
    email: String,
}

impl Display for User {
    fn to_string(self) -> String {
        f"User({self.name}, {self.email})"
    }
}

impl Serialize for User {
    fn serialize(self) -> String ! SerializeError {
        ...
    }
}

// Tuple struct
struct Color(Int, Int, Int);

// Unit struct
struct NoData;

// Sum type (algebraic data type)
type BinaryTree[T] =
    | Leaf(T)
    | Node(left: BinaryTree[T], value: T, right: BinaryTree[T])
    | Empty;

// Refinement type
type PositiveInt = Int if |n| n > 0;
type Percentage = Float if |p| p >= 0.0 && p <= 100.0;
type I32 = Int if |n| n >= -2147483648 && n <= 2147483647;
type U8 = Int if |n| n >= 0 && n <= 255;
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

```spore
parallel_scope {
    let a = spawn { compute_a() };
    let b = spawn { compute_b() };
    [a.await, b.await]
}
```

#### Channel communication

Channels are multi-producer, single-consumer (MPSC). Senders can be cloned; receivers cannot:

```spore
let (tx, rx) = Channel.new[Int](buffer: 10);

parallel_scope {
    // Multiple producers via tx.clone()
    let tx1 = tx.clone();
    let tx2 = tx.clone();

    spawn { tx1.send(1) };
    spawn { tx2.send(2) };

    spawn {
        let a = rx.recv();
        let b = rx.recv();
        print(f"Received: {a}, {b}");
    };
}
```

#### Select and timeout

`select` multiplexes across channels. Use recursion for event loops (no `for`/`loop`):

```spore
let (tx1, rx1) = Channel.new[Int](buffer: 1);
let (tx2, rx2) = Channel.new[String](buffer: 1);

// Recursive event loop (TCO guaranteed)
fn event_loop(rx1: Channel.Receiver[Int], rx2: Channel.Receiver[String]) {
    select {
        value from rx1 => {
            print(f"Got integer: {value}");
        },
        message from rx2 => {
            print(f"Got string: {message}");
        },
        timeout 1000 => {
            print("Timed out — stopping");
            return;
        },
    }
    event_loop(rx1, rx2)  // tail recursion
}
```

### Modules and imports

```spore
// src/math.sp
pub fn add(a: Int, b: Int) -> Int { a + b }
fn helper() -> Int { 42 }  // private by default

import std.collections as collections;
import std.math as math;
```

## Reference-level explanation

### Lexical structure

#### Character set

Spore source files are UTF-8 encoded. Identifiers may contain Unicode letters, ASCII digits, and underscores. Identifiers must begin with a letter or underscore.

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
| `module` | Module definition |
| `import` | Module import |
| `alias` | Type alias |
| `where` | Generic type constraints |
| `uses` | Effect requirement declaration |
| `cost` | Cost bound clause |
| `spec` | Behavioral specification block in function declarations and `impl` methods |
| `example` | Concrete labeled example item inside a `spec` block |
| `property` | Universally quantified assertion inside a `spec` block |
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
| `async` / `await` | Async task operations |
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
| `mod` | Reserved (use `module`) |
| `true` / `false` | Boolean literals |
| `Some` / `None` | Option type constructors |
| `Ok` / `Err` | Result type constructors |
| `Result` / `Option` / `Ref` | Built-in parameterized types |

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
42i32       // typed suffix
100u64      // typed suffix
```

**Floats:**

```text
3.14
-0.001
1.0e-10
2.5e+3
1_000.5
3.14f32
```

**Booleans:** `true`, `false`

**Characters:** `'a'`, `'世'`, `'\n'`, `'\u{1F600}'`

**Strings:**

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

For effect handling, the settled grammar is `perform <expr>`, top-level `handler <Effect> as <HandlerName>(...) { ... }`, and `handle { ... } with { ... }` where each item is either `use HandlerName { ... }` or `on Effect.op(...) => ...`.

```ebnf
(* ═══════════════════════════════════════════════════ *)
(*  Spore v0.1 — Complete EBNF Grammar                *)
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

AliasDecl       = "alias" Ident "=" QualifiedIdent ";" ;

(* ─── Module ──────────────────────────────────────── *)
(* REMOVED (D7): Module names are derived from file paths (see SEP-0008).
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
                | TypeExpr "if" LambdaExpr ;   (* refinement type *)

VariantList     = [ "|" ] Variant { "|" Variant } ;
Variant         = Ident [ "(" FieldList ")" ]
                | Ident [ "(" TypeList ")" ] ;

(* ─── Trait ────────────────────────────────────────── *)

TraitDecl       = [ Visibility ] "trait" Ident [ TypeParams ]
                  [ ":" BoundList ]
                  "{" { TraitItem } "}" ;

TraitItem       = AssocType
                | FunctionDecl ;              (* may have default body *)

AssocType       = "type" Ident ";" ;

(* ─── Effect ──────────────────────────────────────── *)

EffectDecl      = [ Visibility ] "effect" Ident [ TypeParams ]
                  ( EffectBlock | "=" EffectAlias ";" ) ;

EffectBlock     = "{" { FunctionDecl } "}" ;

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

FunctionDecl    = [ DocComment ]
                  [ Visibility ] "fn" Ident [ TypeParams ]
                  "(" [ ParamList ] ")" [ "->" TypeExpr ]
                  [ ErrorClause ]
                  [ WhereClause ]
                  [ UsesClause ]
                  [ CostClause ]
                  [ SpecClause ]
                  Block ;

DocComment      = { "///" CommentText } ;

Visibility      = "pub" | "pub" "(" "pkg" ")" ;

TypeParams      = "[" TypeParam { "," TypeParam } "]" ;
TypeParam       = Ident
                | "const" Ident ":" TypeExpr ;

ParamList       = Param { "," Param } [ "," ] ;
Param           = Ident ":" TypeExpr ;

ErrorClause     = "!" TypeExpr { "|" TypeExpr } ;

WhereClause     = "where" WhereConstraint { "," WhereConstraint } ;
WhereConstraint = Ident ":" Ident ;

UsesClause      = "uses" "[" [ EffectList ] "]" ;
EffectList      = Ident { "," Ident } ;

CostClause      = "cost" "[" CostExpr "," CostExpr "," CostExpr "," CostExpr "]" ;
CostExpr        = IntLiteral
                | Ident                        (* parameter reference *)
                | CostExpr "*" CostExpr
                | CostExpr "+" CostExpr
                | FunctionCall ;               (* e.g., log2(n) *)

(* ─── Spec Clause ─────────────────────────────────── *)

SpecClause      = "spec" "{" { SpecItem } "}" ;

SpecItem        = ExampleItem
                | PropertyItem ;

ExampleItem     = "example" StringLiteral ":" Expr
                | "example" StringLiteral Block ;

PropertyItem    = "property" StringLiteral ":" PropertyLambdaExpr ;

PropertyLambdaExpr = "|" [ PropertyParamList ] "|" ( Expr | Block ) ;
PropertyParamList  = PropertyParam { "," PropertyParam } ;
PropertyParam      = Ident ":" TypeExpr ;

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
PostfixOp       = "?" | "." Ident | "." Ident "(" [ ArgList ] ")"
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
SelectArm       = Ident "from" Expr "=>" Block ","
                | "timeout" IntLiteral "=>" Block "," ;

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
                | StringLiteral | CharLiteral ;

IntLiteral      = DecimalInt | HexInt | OctalInt | BinaryInt ;
DecimalInt      = [ "-" ] Digit { Digit | "_" } [ IntSuffix ] ;
HexInt          = "0x" HexDigit { HexDigit | "_" } [ IntSuffix ] ;
OctalInt        = "0o" OctDigit { OctDigit | "_" } [ IntSuffix ] ;
BinaryInt       = "0b" BinDigit { BinDigit | "_" } [ IntSuffix ] ;
IntSuffix       = "i32" | "i64" | "u8" | "u32" | "u64" ;

FloatLiteral    = [ "-" ] Digit { Digit | "_" } "." Digit { Digit | "_" }
                  [ ( "e" | "E" ) [ "+" | "-" ] Digit { Digit } ]
                  [ FloatSuffix ] ;
FloatSuffix     = "f32" | "f64" ;

BoolLiteral     = "true" | "false" ;

StringLiteral   = '"' { StringChar } '"'
                | 'r"' { RawChar } '"'
                | 'f"' { FStringPart } '"'
                | 't"' { TStringPart } '"' ;

FStringPart     = StringChar | "{" Expr "}" ;
TStringPart     = StringChar | "{" Ident "}" ;

CharLiteral     = "'" ( Char | EscapeSeq ) "'" ;
EscapeSeq       = "\\" ( "n" | "t" | "r" | "\\" | "'" | '"' | "0"
                | "u{" HexDigit { HexDigit } "}" ) ;

(* ─── Identifier ──────────────────────────────────── *)

Ident           = ( Letter | "_" ) { Letter | Digit | "_" } ;
Letter          = "a".."z" | "A".."Z" | UnicodeLetterExceptAscii ;
Digit           = "0".."9" ;
HexDigit        = Digit | "a".."f" | "A".."F" ;
OctDigit        = "0".."7" ;
BinDigit        = "0" | "1" ;
```

### Function signature semantics

The function signature system is the heart of Spore's design. The clauses appear in this canonical order:

```text
fn <name>[<generics>](<params>) -> <ReturnType> [! <ErrorTypes>]
[where <GenericName>: <Constraint>, ...]
[uses [<Effect>, ...]]
[cost ≤ <N>]
[spec { <examples and properties> }]
{
    <body>
}
```

**Clause semantics:**

1. **`-> ReturnType`** — The return type. Omitted for functions returning `Unit`.

2. **`! ErrorTypes`** — The error set. A function with `! E1 | E2` may produce errors of type `E1` or `E2`. Absence of `!` means the function cannot fail.

3. **`where T: Bound, U: Bound`** — Generic constraints. The canonical form is a single `where` clause with comma-separated constraints. Spore does not use `+` multi-bound syntax.

4. **`uses [Effects]`** — The effect set required by this function. The compiler auto-infers effect properties:
   - `uses []` → `pure`, `deterministic`, `total`
   - `uses [FileRead]` → `deterministic`
   - If `uses` contains `Random` or `Clock` → not deterministic
   - `total` is inferred by the compiler's termination checker

   **Implication chain:** `pure` ⊃ `deterministic` — a pure function is necessarily deterministic (same inputs always produce same outputs). A deterministic function is not necessarily pure (it may perform IO that doesn't introduce non-determinism). `total` is orthogonal: a function can be total without being pure.

5. **`cost [c, a, i, p]`** — A four-slot cost vector (`compute`, `alloc`, `io`, `parallel`). Each slot may reference parameters or use the currently supported linear `O(n)` forms.

6. **`spec { ... }`** — Behavioral specification block. Contains `example` and `property` items that express the function's intended behavior as typechecked test metadata. When the enclosing function body is executable, `spore test` evaluates the `spec` block by calling the function by name. If the body still contains an unfilled hole, the `spec` block remains available to the compiler and HoleReport output, but executing it still reaches the hole and errors.

   - **`example "label": expr`** — A concrete named test case. The body expression must be `Bool`. If using `==`, both sides must have the same type. Multi-line examples use block syntax: `example "label" { ... }`.
   - **`property "label": |x: T, ...| expr`** — A universally quantified assertion. The compiler generates random inputs of the declared types and verifies the body evaluates to `true` for all trials. Type annotations on property parameters are required.

   For `pub` functions without a `spec` block, the compiler emits a `MissingSpec` warning (not error). Private functions do not trigger this warning. Suppress with `#[allow(missing_spec)]`.

   This amendment does not define trait-method `spec` inheritance or contract merging; that behavior is reserved for a future SEP.

**Clause ordering** is not enforced by the grammar but is enforced by the formatter: `where` → `uses` → `cost` → `spec`.

**`self` in trait and handler methods:** The `self` identifier is a regular parameter name used as the first parameter in trait method signatures. It is not a keyword with special scoping rules.

```spore
trait Display {
    fn to_string(self) -> String;
}

trait Collection {
    type Item;
    fn len(self) -> Int;
    fn is_empty(self) -> Bool {
        self.len() == 0
    }
}
```

### Expression forms

All control flow constructs are expressions that produce values.

**Block expressions** evaluate to their last expression (without semicolon). A block ending with a semicolon-terminated statement returns `Unit`.

**If expressions** always have a value. When used as a statement (followed by `;`), the value is discarded.

**Match expressions** are exhaustive — the compiler rejects non-exhaustive matches at compile time.

**Lambda expressions** use `|params| body` syntax. Closures capture variables from the enclosing scope.

**Pipe expressions** desugar as follows:

- `x |> f` → `f(x)`
- `x |> f(y, z)` → `f(x, y, z)`
- `x |> f(_, y)` → `f(x, y)`
- `x |> .method()` → `x.method()`

**Error propagation (`?`)**: `expr?` evaluates `expr`. If the result is `Ok(v)`, yields `v`. If `Err(e)`, immediately returns `Err(e)` from the enclosing function. The error type must be in the function's declared error set.

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

**Primitive types:** `Int` (arbitrary-precision integer), `Float` (arbitrary-precision float), `Bool`, `String`, `Char`. Specific fixed-width types (`I32`, `U64`, `F32`, etc.) are obtained via refinement types (e.g., `type I32 = Int if |n| n >= -2147483648 && n <= 2147483647`).

**Collection types:** `List[T]`, `Map[K, V]`, `Set[T]`, `Array[T, N]`

**Special types:** `Option[T]`, `Result[T, E]`, `Ref[T]`, `Channel[T]`, `Unit`

**Const generics:** `struct Array[T, const N: Int] { ... }`

```spore
// Fixed-size array
struct Array[T, const N: Int] {
    data: List[T],  // length guaranteed to be N
}

// Fixed-size matrix
struct Matrix[T, const ROWS: Int, const COLS: Int] {
    data: Array[Array[T, COLS], ROWS],
}

// Usage
let vec3: Array[Float, 3] = Array.new([1.0, 2.0, 3.0]);
let identity: Matrix[Float, 3, 3] = Matrix.identity();
```

**Refinement types:** `type PositiveInt = Int if |n| n > 0;`

**Function types:** `fn(Int, Int) -> Int`

### Concurrency primitives

Spore provides structured concurrency:

- **`parallel_scope { ... }`** — All spawned tasks must complete before the scope exits.
- **`spawn { expr }`** — Launch a concurrent task within a parallel scope.
- **`select { ... }`** — Multiplex over multiple channels.
- **`task.await`** — Wait for a spawned task's result.
- **`Channel.new[T](buffer: N)`** — Create a bounded channel.

### Hole syntax

Holes (`?`, `?name`, `?name : Type`) enable incremental development. A function with holes type-checks but cannot be compiled for real execution — only simulated. The compiler can suggest implementations based on available bindings and the `@allows` annotation.

#### `@allows` annotation

The `@allows` annotation constrains which functions the compiler (or an AI agent) may use to fill a hole:

```spore
@allows[validate, sanitize, format]
fn process_input(raw: String) -> String ! ValidationError {
    let validated = validate(raw)?;
    let sanitized = sanitize(validated);
    ?final_step  // this hole can only call validate/sanitize/format
}

@allows[add, multiply, negate]
fn arithmetic(a: Int, b: Int) -> Int {
    let x = ?step1 : Int;  // only add/multiply/negate
    let y = ?step2 : Int;  // same constraint
    x + y
}
```

#### Hole + pipeline type inference

The compiler infers hole types through pipeline chains:

```spore
fn example() {
    let list = [1, 2, 3, 4, 5];
    let result = list
        |> filter(?)        // hole: fn(Int) -> Bool
        |> map(?)           // hole: fn(Int) -> ?R
        |> fold(0, ?);     // hole: fn(Int, ?R) -> Int
}
```

#### Hole protocol reference

`sporec query-hole <file> <name> --json` returns one hole object from the shared typed-hole protocol, and `sporec holes <file> --json` returns the batch form with both `holes` and `dependency_graph`. SEP-0005 is the authoritative schema and workflow specification; SEP-0001 intentionally avoids freezing a second inline JSON shape here.

At minimum, the shared hole object includes:

- `name` / `display_name`
- `location`
- `expected_type` / `type_inferred_from`
- `function` / `enclosing_signature`
- `bindings` / `binding_dependencies`
- `effects`, `errors_to_handle`, `cost_budget`
- `candidates`, `dependent_holes`, `confidence`, `error_clusters`

When a function has both a `spec` block and a hole body, that shared hole object may surface the `spec` items as additional behavioral context for tooling. The authoritative transport and evolution rules remain in SEP-0005 so SEP-0001 does not accidentally freeze a stale field layout.

## Complete examples

### Expression parser and evaluator

This example demonstrates algebraic data types, pattern matching, recursion, error handling, and cost bounds working together:

```spore
// Expression AST
type Expr =
    | Literal(Int)
    | Variable(name: String)
    | BinOp(op: Op, left: Expr, right: Expr)
    | UnaryOp(op: UnaryOp, expr: Expr)
    | Let(name: String, value: Expr, body: Expr)
    | If(condition: Expr, then_branch: Expr, else_branch: Expr);

type Op = Add | Sub | Mul | Div | Equal | LessThan;
type UnaryOp = Negate | Not;

type Env = Map[String, Int];

type EvalError =
    | UndefinedVariable(name: String)
    | DivisionByZero
    | TypeError(message: String);

// Evaluator — pure recursion, no loops
fn eval(expr: Expr, env: Env) -> Int ! EvalError
cost ≤ expr_size(expr) * 10
{
    match expr {
        Literal(n) => n,

        Variable(name) => match env.get(name) {
            Some(value) => value,
            None => throw EvalError.UndefinedVariable(name),
        },

        BinOp(op, left, right) => {
            let left_val = eval(left, env)?;
            let right_val = eval(right, env)?;
            eval_binop(op, left_val, right_val)?
        },

        UnaryOp(op, e) => {
            let val = eval(e, env)?;
            match op {
                Negate => -val,
                Not => if val == 0 { 1 } else { 0 },
            }
        },

        Let(name, value_expr, body) => {
            let value = eval(value_expr, env)?;
            let new_env = env.insert(name, value);
            eval(body, new_env)?
        },

        If(cond, then_branch, else_branch) => {
            let cond_val = eval(cond, env)?;
            if cond_val != 0 {
                eval(then_branch, env)?
            } else {
                eval(else_branch, env)?
            }
        },
    }
}

fn eval_binop(op: Op, left: Int, right: Int) -> Int ! EvalError {
    match op {
        Add => left + right,
        Sub => left - right,
        Mul => left * right,
        Div => if right == 0 {
            throw EvalError.DivisionByZero
        } else {
            left / right
        },
        Equal => if left == right { 1 } else { 0 },
        LessThan => if left < right { 1 } else { 0 },
    }
}

// Usage
fn example() {
    // let x = 10 in let y = 20 in x + y
    let expr = Expr.Let(
        "x",
        Expr.Literal(10),
        Expr.Let(
            "y",
            Expr.Literal(20),
            Expr.BinOp(Op.Add, Expr.Variable("x"), Expr.Variable("y"))
        )
    );

    match eval(expr, Map.empty()) {
        Ok(result) => print(f"Result: {result}"),  // Result: 30
        Err(e) => print(f"Error: {e}"),
    }
}
```

### Concurrent producer-consumer

This example demonstrates channels, structured concurrency, tail-recursive message processing, and zero use of loop constructs:

```spore
type Task =
    | Process(id: Int, data: String)
    | Stop;

// Producer generates tasks and sends them to a channel
fn producer(tx: Channel.Sender[Task], task_count: Int) {
    (1..=task_count)
        .map(|i| Task.Process(i, f"Task data {i}"))
        .for_each(|task| tx.send(task));
    tx.send(Task.Stop);
}

// Consumer processes tasks via tail recursion
fn consumer(id: Int, rx: Channel.Receiver[Task], result_tx: Channel.Sender[String]) {
    fn process(id: Int, rx: Channel.Receiver[Task], result_tx: Channel.Sender[String]) {
        match rx.recv() {
            Task.Process(task_id, data) => {
                let result = f"Consumer {id} processed task {task_id}: {data}";
                result_tx.send(result);
                process(id, rx, result_tx)  // tail recursion
            },
            Task.Stop => {},
        }
    }
    process(id, rx, result_tx)
}

// Result collector using tail recursion
fn collector(rx: Channel.Receiver[String], expected: Int) {
    fn collect(rx: Channel.Receiver[String], remaining: Int) {
        if remaining <= 0 { return }
        let result = rx.recv();
        print(result);
        collect(rx, remaining - 1)  // tail recursion
    }
    collect(rx, expected)
}

fn main() {
    let task_count = 10;
    let consumer_count = 3;
    let (task_tx, task_rx) = Channel.new[Task](buffer: 5);
    let (result_tx, result_rx) = Channel.new[String](buffer: 10);

    parallel_scope {
        spawn { producer(task_tx, task_count) };

        (1..=consumer_count).for_each(|i| {
            let rx_clone = task_rx.clone();
            let tx_clone = result_tx.clone();
            spawn { consumer(i, rx_clone, tx_clone) };
        });

        spawn { collector(result_rx, task_count) };
    }

    print("All tasks completed!");
}
```

## Human experience impact

### Readability

Spore's syntax prioritizes scannability. The fixed operator set means readers never encounter unfamiliar symbols. The pipe operator linearizes deeply nested function calls. Exhaustive `match` prevents overlooked cases. The absence of loops initially surprises imperative programmers, but the combination of `map`/`fold`/`filter` with guaranteed TCO quickly becomes natural. The `uses` clause makes side effects visible at a glance in the function signature.

### Learning curve

- **Developers from Rust/TypeScript**: Very low barrier. Curly braces, semicolons, `let`, `match`, `fn`, and generic syntax are immediately familiar. The main novelty is `uses`/`cost`/`!` clauses and the no-loops philosophy.
- **Developers from Python/JavaScript**: Moderate curve. Static types and explicit error handling require adjustment, but f-strings, lambdas, and pipe operators feel comfortable.
- **Developers from Haskell/OCaml**: Low barrier. Pattern matching, ADTs, and expression-based design are familiar. Curly braces instead of significant whitespace is a stylistic shift.

### Progressive disclosure

Simple functions require zero ceremony — `fn add(a: Int, b: Int) -> Int { a + b }` has no clauses to learn. Effects, error sets, and cost bounds are introduced only when the code actually needs them.

## Agent experience impact

Spore is designed with AI code generation agents as first-class consumers:

### Parsing predictability

- **Fixed operator set**: Agents never need to resolve custom operators or precedence ambiguities.
- **Regular grammar**: No significant whitespace, no optional semicolons, no implicit returns outside blocks. Every syntactic form is delimited by explicit tokens.
- **Keyword-introduced clauses**: `where`, `uses`, `cost`, `!` are unambiguous clause starters.

### Structured metadata

Function signatures are machine-readable contracts. An agent can extract:

- **Input/output types** from the parameter list and return type
- **Failure modes** from the `! ErrorSet`
- **Side effect profile** from `uses [...]`
- **Performance budget** from `cost ≤ N`
- **Generic requirements** from `where` clauses

This enables agents to:

1. Select appropriate functions by matching effect requirements
2. Estimate execution cost before generating call sequences
3. Verify error handling completeness
4. Compose pipelines with compatible effect sets

### Code generation

Agents can generate Spore code incrementally using holes (`?`). A function can be specified by its signature alone, then filled in step by step. The `@allows` annotation restricts the search space for hole completion.

### Snapshot hashing

Any change to the following signature components produces a new snapshot hash and requires explicit `--permit` approval:

| Component | Example change |
|---|---|
| Function name | `parse_config` → `load_config` |
| Parameter names | `raw` → `input` |
| Parameter order | `(a, b)` → `(b, a)` |
| Parameter types | `String` → `Bytes` |
| Return type | `Config` → `Settings` |
| Error type set | add/remove any error type |
| Cost bound | `≤ 200` → `≤ 300` |
| Effect set | add/remove any effect |
| Generic constraints | `T: Eq` → `T: Eq + Hash` |

The `spec` block is tracked via a separate **spec hash**, independent of the snapshot hash:

| Change | Snapshot hash | Spec hash | Required approval |
|--------|--------------|-----------|------------------|
| Add a `spec` block where none existed | unchanged | new | `--permit-spec` |
| Add/modify/remove an `example` or `property` | unchanged | changed | `--permit-spec` |
| Any signature clause change (types, effects, cost, etc.) | changed | unchanged | `--permit` |

The lighter `--permit-spec` approval reflects that spec changes clarify behavioral contracts without altering calling conventions. Downstream callers need only re-run their own tests, not update call sites.

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
    │   │   ├── label: String
    │   │   └── body: Expr
    │   └── properties[]
    │       ├── label: String
    │       └── predicate: LambdaExpr
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
- **Hover information**: Function signatures (including `uses`, `cost`, `spec` summary, inferred properties) can be displayed in full. The `spec` block is surfaced as a "behavioral contract" section showing example count and property count.
- **Completions**: After `|>`, suggest functions whose first parameter matches the pipe source type. Inside `uses [...]`, suggest available effects. Inside `spec { }`, suggest `example` and `property` as the only valid item keywords.
- **Diagnostics**: Missing match arms, undeclared effects, cost violations, incomplete error handling, missing spec on public functions, and spec failures can all be reported as structured diagnostics.
- **Signature help**: The ordered clause structure (`where` → `uses` → `cost` → `spec`) enables progressive parameter info display.

### Serialization

The AST serializes naturally to JSON, S-expressions, or any tree-structured format. The fixed set of node types ensures forward compatibility.

## Diagnostics impact

### Error messages

Spore's explicit syntax enables highly specific error messages:

**Missing effect:**

```text
error[E0301]: function `fetch_data` uses effect `NetConnect` but does not declare it
  --> src/api.sp:12:5
   |
12 | fn fetch_data(url: Url) -> Data ! NetworkError {
   |    ^^^^^^^^^^ missing `uses` clause
   |
   = help: add `uses [NetConnect]` to the function signature
   = note: detected effect dependency via call to `http.get`
```

**Non-exhaustive match:**

```text
error[E0401]: non-exhaustive match expression
  --> src/main.sp:25:5
   |
25 | match color {
   |       ^^^^^ missing variant `Blue`
   |
   = help: add `Blue => ...` arm or use `_ => ...` wildcard
```

**Loop keyword used:**

```text
error[E0101]: `for` loops are not supported in Spore
  --> src/main.sp:10:5
   |
10 | for x in list {
   | ^^^ Spore uses recursion and higher-order functions instead of loops
   |
   = help: try `list.map(|x| ...)` or `list.fold(init, |acc, x| ...)`
   = help: for recursive iteration, use tail recursion (TCO is guaranteed)
```

**Spec clause in wrong position:**

```text
error[E0501]: `spec` must appear after all other signature clauses
  --> src/lib.sp:5:1
   |
 5 | spec { ... }
 6 | cost ≤ 500
   |
   = help: move `cost` before `spec`
```

**Spec example failure (runtime):**

```text
spec failure: `parse_date` — example "ISO 8601"
  --> src/dates.sp:5:5
   |
 5 |     example "ISO 8601": parse_date("2024-01-15") == Ok(Date(2024, 1, 15))
   |
   body evaluated to: false
   = note: equality-shaped examples may additionally report compared values when available
```

**Spec property counterexample (runtime):**

```text
spec counterexample: `parse_date` — property "round-trip"
  --> src/dates.sp:9:5
   |
 9 |     property "round-trip": |d: Date| parse_date(d.to_iso_string()) == Ok(d)
   |
   counterexample: d = Date { year: 2024, month: 2, day: 30 }
   body evaluated to: false
   = note: found after 47 trials
```

**Missing spec warning:**

```text
warning[W0501]: public function `parse_date` has no `spec` block
  --> src/dates.sp:3:1
   |
 3 | pub fn parse_date(s: String) -> Result[Date, ParseError] ! ParseError {
   |        ^^^^^^^^^^ no behavioral contract declared
   |
   = help: add a `spec { example "...": ... }` block before the function body
   = note: suppress with `#[allow(missing_spec)]` if intentional
```

### Recovery strategies

The parser can recover from common errors:

1. **Missing semicolon**: Insert one after a statement and continue parsing.
2. **Missing closing brace**: Match indentation heuristics to suggest where the brace should go.
3. **Unknown keyword**: Suggest the closest valid keyword (e.g., `func` → `fn`, `for` → `map`/`fold`).
4. **Angle brackets for generics**: Detect `List<Int>` and suggest `List[Int]`.
5. **Missing `!` clause**: When a function body calls a failable function without `?`, suggest adding the error type to the signature.

## Drawbacks

1. **No loops**: Developers with imperative backgrounds may find the no-loop constraint frustrating initially, especially for simple counting patterns. The learning curve for converting loop-based thinking to recursion + HOFs is non-trivial.

2. **Verbose error sets**: Functions that can fail in many ways produce long `! E1 | E2 | E3 | ...` lists. This is deliberate (errors are visible) but can clutter signatures.

3. **`cost` clause expressiveness**: The cost model is inherently limited — expressing accurate cost bounds for complex algorithms may be impractical. Wrong bounds are worse than no bounds.

4. **No custom operators**: Domains like linear algebra or DSLs sometimes benefit from custom operators. Spore sacrifices this for predictability.

5. **Square bracket overload**: `[]` is used for generics, list literals, index access, and the `uses`/error clauses. Context resolves ambiguity, but it adds parser complexity.

6. **Keyword count**: The reserved keyword set is large (40+), which constrains identifier names and increases the language surface area.

7. **`with` removal**: Auto-inferring properties from `uses` is convenient but means developers cannot see or override the inferred properties at the declaration site without inspecting compiler output.

## Alternatives considered

### Loop constructs

We considered including a minimal loop construct (e.g., Rust's `loop` or a `foreach`) but rejected it because:

- It would undermine the functional-first philosophy.
- TCO guarantee makes recursion safe and efficient.
- HOFs (`map`, `fold`, `filter`) cover the vast majority of iteration patterns.
- A single iteration paradigm reduces cognitive load once learned.

### Angle brackets for generics (`List<Int>`)

Rejected because:

- Angle brackets create parsing ambiguity with comparison operators (`a < b > c`).
- Square brackets align with Python type hints (`List[int]`) which are increasingly familiar.
- Gleam and other modern languages have validated this choice.

### `with` clause for explicit effect properties

The original design included `with [pure, deterministic]` for explicit property annotation. This was removed because:

- Properties are fully deterministic given the `uses` set — annotation is redundant.
- Redundant annotations can diverge from reality, creating false confidence.
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
- `?` provides comparable ergonomics to exceptions for the happy path.

## Prior art

### Rust

Heavy influence on: curly-brace syntax, semicolon semantics (expression vs. statement), `match` exhaustiveness, `?` error propagation, `where` clauses, `let` bindings, closure syntax (`|x| x`), pattern matching, enum/struct distinction.

Departed from: Spore removes lifetime annotations, borrowing semantics, `mut` keyword, `loop`/`for`/`while`, and trait orphan rules. Spore adopts Rust-style `impl Trait for Type` blocks.

### Roc

Influence on: expression-based design, the trait/effect split design, no-loop philosophy, the idea of making side effects visible in signatures.

### Gleam

Influence on: square brackets for generics, use of `|>` pipe operator as a core language feature, the philosophy of a small fixed-operator language that is easy for tools to process.

### Elm

Influence on: the emphasis on helpful error messages, exhaustive pattern matching as a reliability tool, the no-runtime-exception philosophy, and progressive disclosure of type system features.

### OCaml / F

Influence on: algebraic data types with `|` variant syntax, pattern matching with guards, expression-based design, the pipe operator (`|>` originates from F#).

### Haskell

Influence on: type classes (→ traits), purity by default, the idea of tracking effects in types, `where` clause syntax for constraints.

### TypeScript / Python

Influence on: f-string syntax (`f"...{expr}..."`), postfix type annotations (`name: Type`), square brackets for generics (Python), the desire for a gentle learning curve.

### Koka

Influence on: algebraic effect system design, the idea that effects should be inferred rather than manually annotated, row-polymorphic effects informing the `uses` auto-inference system.

## Backward compatibility and migration

As this is the initial v0.1 specification, there are no backward compatibility concerns.

### Future compatibility considerations

1. **Keyword reservation**: The large reserved keyword set is intentional — it preserves room for future features (e.g., `async`, `unsafe`, `macro`) without breaking existing code.

2. **Signature evolution**: The snapshot hash system means any signature change requires explicit approval. Future SEPs that modify signature clause syntax must define migration tooling.

3. **Cost model changes**: The `cost` clause semantics may evolve. Future versions should define a cost model versioning scheme so that cost bounds written today remain meaningful.

4. **New expression forms**: The grammar is designed to be extensible — new expression forms can be added as new `PrimaryExpr` alternatives without disturbing existing productions.

5. **Standard library stability**: Type names like `Option`, `Result`, `List`, `Map` are part of the language surface. Renaming these would require a major version bump and automated migration.

## Unresolved questions

1. **Exact cost model semantics**: What units does `cost` measure? CPU cycles? Abstract "work units"? How does the compiler verify cost bounds, especially for recursive functions?

2. **Effect composition rules**: When a function calls two sub-functions with different `uses` sets, is the resulting set the union? How are effect aliases expanded for comparison?

3. **Refinement type checking**: How deeply does the compiler verify refinement predicates (`type Positive = Int if |n| n > 0`)? Is this compile-time only, or does it generate runtime checks?

4. **`throw` semantics**: Is `throw` syntactic sugar for `return Err(...)`, or does it have distinct unwinding semantics? The current spec treats it as sugar but this needs formalization.

5. **Module system details**: How do circular module dependencies behave? What is the exact resolution order for qualified names?

6. **`self` method dispatch**: How does the compiler resolve method calls on `self` — is it static dispatch (monomorphized) or dynamic dispatch (vtable)? This affects performance characteristics.

7. **Format string security**: What sanitization, if any, applies to `f"..."` expressions to prevent injection attacks? How do `t"..."` template objects interact with the effect system?

8. **Tail-call optimization scope**: Is TCO guaranteed only for direct self-recursion, or for mutual recursion and continuation-passing style as well?

9. **Partial application**: The pipe operator supports `x |> f(_, y)` placeholder syntax. Should Spore support general partial application beyond pipe contexts?

10. **Pattern matching on strings**: The current spec shows string literal patterns. Should Spore support regex patterns or prefix/suffix matching in `match` arms?

11. **Standard effect taxonomy evolution**: SEP-0003 now defines the initial built-in effect vocabulary (`Console`, `FileRead`, `FileWrite`, `NetConnect`, `NetListen`, `Env`, `Spawn`, `Clock`, `Random`, `Exit`). Future SEPs may extend it, but changes should preserve the intent-oriented classification.

12. **Error type subtyping**: If function `f` declares `! NetworkError` and function `g` declares `! NetworkError | ParseError`, can `g` call `f` directly? How does error set subtyping work?

13. **`property` with `uses`**: If a property calls a function that has side effects, what effect scope applies? Current proposal: property items inherit the enclosing function's `uses` set.

14. **Future trait-level behavioral contracts**: Should a later SEP allow `spec` blocks on trait methods, and if so how should implementations inherit or refine them? This amendment leaves trait-level `spec` syntax and semantics unspecified.

15. **`example` execution order**: Should `example` items run in declaration order (default) or allow parallel execution via `--parallel-spec`?

16. **Negative examples**: Should `spec` support expressing that a call should fail at compile time (type error)? This would enable testing the type system itself but requires a different mechanism.

## Appendix A: Small-step operational semantics

This appendix formalizes the evaluation rules for core Spore expressions using small-step operational semantics. All Spore code evaluates under a **call-by-value** strategy.

### Notation

- `e ↝ e'` — expression `e` reduces to `e'` in one step
- `v` — a value (fully evaluated: literal, closure, struct/enum instance, list)
- `E[·]` — evaluation context (position where the next reduction occurs)
- `σ` — runtime environment (variable → value mapping)
- `H` — effect handler table (effect → handler mapping)
- `e[x ↦ v]` — substitute `v` for `x` in `e`

### Values

```text
v ::= n                           (integer literal)
    | f                           (float literal)
    | true | false                (boolean)
    | "s"                         (string literal)
    | 'c'                         (char literal)
    | ()                          (unit)
    | S { f₁: v₁, ..., fₙ: vₙ } (struct instance)
    | V(v₁, ..., vₙ)             (enum variant instance)
    | V                           (zero-field enum variant)
    | [v₁, ..., vₙ]              (list)
    | <closure: λ(x₁...xₙ).e, σ> (closure with captured env)
```

### Evaluation contexts

Evaluation contexts define the order of evaluation (left-to-right, call-by-value):

```text
E ::= □                                            (hole)
    | E op e₂                                      (left of binop)
    | v₁ op E                                      (right of binop)
    | f(v₁, ..., vᵢ₋₁, E, eᵢ₊₁, ..., eₙ)         (function argument)
    | let x = E; e₂                                (let initializer)
    | if E { e₁ } else { e₂ }                      (if condition)
    | match E { arms }                              (match scrutinee)
    | S { f₁: v₁, ..., fᵢ: E, ..., fₙ: eₙ }      (struct field)
    | V(v₁, ..., vᵢ₋₁, E, eᵢ₊₁, ..., eₙ)         (enum constructor arg)
    | E.field                                       (field access receiver)
    | E |> f                                        (pipe left-hand side)
    | [v₁, ..., vᵢ₋₁, E, eᵢ₊₁, ..., eₙ]          (list element)
    | E?                                            (try operator operand)
    | spawn E                                       (spawn body — eager eval)
```

### Core reduction rules

**Literals and variables:**

```text
[E-Var]
  σ(x) = v
  ──────────────
  σ ⊢ x ↝ v

(Variables resolve to their bound value in the environment.)
```

**Arithmetic and comparison:**

```text
[E-BinOp]
  v₁ op v₂ = v₃   (where op is +, -, *, /, %, ==, !=, <, >, <=, >=, &&, ||)
  ──────────────────
  v₁ op v₂ ↝ v₃

[E-StrConcat]
  "s₁" + "s₂" ↝ "s₁s₂"

[E-UnaryNeg]
  -n ↝ (-n)

[E-UnaryNot]
  !b ↝ ¬b
```

**Let binding:**

```text
[E-Let]
  σ ⊢ let x = v; e₂ ↝ σ[x ↦ v] ⊢ e₂

(Bind the value and continue evaluating the body with extended environment.)
```

**Function application (β-reduction):**

```text
[E-App]
  σ ⊢ f(v₁, ..., vₙ)
  where f is defined as fn f(x₁, ..., xₙ) { body }
  ─────────────────────────────────────────────────
  σ[x₁ ↦ v₁, ..., xₙ ↦ vₙ] ⊢ body

[E-ClosureApp]
  <closure: λ(x₁...xₙ).body, σ_captured>(v₁, ..., vₙ)
  ─────────────────────────────────────────────────────
  σ_captured[x₁ ↦ v₁, ..., xₙ ↦ vₙ] ⊢ body

(Closures evaluate in their captured environment, extended with arguments.)
```

**Lambda creation:**

```text
[E-Lambda]
  σ ⊢ |x₁, ..., xₙ| body ↝ <closure: λ(x₁...xₙ).body, σ>

(Captures the current environment.)
```

**Conditionals:**

```text
[E-IfTrue]
  if true { e₁ } else { e₂ } ↝ e₁

[E-IfFalse]
  if false { e₁ } else { e₂ } ↝ e₂
```

**Pattern matching:**

```text
[E-Match]
  match v { p₁ => e₁, ..., pₙ => eₙ }
  where pᵢ is the first pattern matching v with bindings B
  ──────────────────────────────────────────────────────
  ↝ eᵢ[B]

(Try patterns top-to-bottom. First match wins. Apply bindings to body.)
```

Pattern matching sub-rules:

```text
[Pat-Wildcard]
  _ matches any v, bindings = ∅

[Pat-Var]
  x matches any v, bindings = {x ↦ v}

[Pat-Literal]
  n matches n, bindings = ∅     (and similarly for string, bool literals)

[Pat-Constructor]
  V(p₁, ..., pₖ) matches V(v₁, ..., vₖ)
  if each pᵢ matches vᵢ with bindings Bᵢ
  bindings = B₁ ∪ ... ∪ Bₖ

[Pat-Struct]
  S { f₁: p₁, ..., fₖ: pₖ } matches S { ..., fᵢ: vᵢ, ... }
  if each pᵢ matches vᵢ with bindings Bᵢ
  bindings = B₁ ∪ ... ∪ Bₖ

[Pat-Or]
  (p₁ | p₂) matches v if p₁ matches v or p₂ matches v

[Pat-List-Empty]
  [] matches []

[Pat-List-Cons]
  [p₁, ..rest] matches [v₁, v₂, ..., vₙ]
  if p₁ matches v₁ with bindings B₁
  rest binds to [v₂, ..., vₙ]
  bindings = B₁ ∪ {rest ↦ [v₂, ..., vₙ]}

[Pat-Guard]
  p if cond => e
  p matches v with bindings B, and B ⊢ cond ↝ true
```

**Struct and enum construction:**

```text
[E-StructLit]
  S { f₁: v₁, ..., fₙ: vₙ } ↝ S { f₁: v₁, ..., fₙ: vₙ }

(Struct literals with all fields evaluated are values.)

[E-EnumConstruct]
  V(v₁, ..., vₙ) ↝ V(v₁, ..., vₙ)

(Fully evaluated variant constructors are values.)
```

**Field access:**

```text
[E-FieldAccess]
  S { ..., f: v, ... }.f ↝ v
```

**Pipe operator:**

```text
[E-Pipe]
  v |> f ↝ f(v)

(Pipe desugars to function application.)
```

**Block expressions:**

```text
[E-Block]
  { stmt₁; stmt₂; ...; stmtₙ; tail }
  ↝ evaluate stmt₁, then { stmt₂; ...; stmtₙ; tail }

[E-BlockTail]
  { v } ↝ v
```

**Try (? operator):**

```text
[E-TryOk]
  Ok(v)? ↝ v

[E-TryErr]
  Err(e)? ↝ throw Err(e)

(Unwraps Ok, propagates Err to the nearest error boundary.)
```

**Throw and error propagation:**

```text
[E-Throw]
  throw v ↝ RuntimeError(v)

(Propagates up the call stack until caught by a match or error boundary.)
```

### Effect dispatch

```text
[E-ForeignCall]
  H(effect, fn_name) = handler
  handler(v₁, ..., vₙ) ↝ᵢₒ v
  ──────────────────────────────────
  foreign_fn(v₁, ..., vₙ) ↝ v

(Foreign function calls are dispatched to the platform's effect handler table.
The handler may perform real I/O — this is the only impure reduction rule.)
```

### Concurrency (structured)

```text
[E-Spawn]
  spawn e ↝ Task(e, fresh_id)

(Creates a new task. In the PoC interpreter, evaluates synchronously.
In a production runtime, this would fork a lightweight thread.)

[E-Await]
  await Task(v, id) ↝ v

(Blocks until the task completes and extracts its value.
In PoC, this is a no-op since spawn already evaluated.)

[E-Select]
  select { task₁ => e₁, ..., taskₙ => eₙ }
  where taskᵢ is the first to complete with value v
  ────────────────────────────────────────────────
  ↝ eᵢ[result ↦ v]
```

### Hole evaluation

```text
[E-Hole]
  ?name ↝ RuntimeError("hit unfilled hole `?name`")

(Holes are compile-time constructs. Reaching one at runtime is always an error.)
```

### Spec evaluation

```text
[E-SpecExample]
  spec_example("label", body_expr)
  body_expr ↝* true
  ──────────────────────────────────
  SpecResult("label", Pass)

[E-SpecExampleFail]
  spec_example("label", body_expr)
  body_expr ↝* false
  ──────────────────────────────────
  SpecResult("label", Fail(left_value, right_value))

[E-SpecProperty]
  spec_property("label", |x₁: T₁, ..., xₙ: Tₙ| body)
  ∀ generated (v₁, ..., vₙ): body[x₁ ↦ v₁, ..., xₙ ↦ vₙ] ↝* true
  ──────────────────────────────────
  SpecResult("label", Pass)

[E-SpecPropertyCounterexample]
  spec_property("label", |x₁: T₁, ..., xₙ: Tₙ| body)
  ∃ (v₁, ..., vₙ): body[x₁ ↦ v₁, ..., xₙ ↦ vₙ] ↝* false
  ──────────────────────────────────
  SpecResult("label", Counterexample(v₁, ..., vₙ))

(Spec items are evaluated by `spore test`, not during normal program execution.
Each example/property is compiled as a standalone test case that calls the function
by name. If that function body still contains a hole, the ordinary hole runtime-error
rule applies, so the `spec` remains useful metadata but not a normal runnable path yet.)
```

### List operations (builtins)

```text
[E-ListLen]
  len([v₁, ..., vₙ]) ↝ n

[E-ListMap]
  map([v₁, ..., vₙ], f) ↝ [f(v₁), ..., f(vₙ)]

[E-ListFilter]
  filter([v₁, ..., vₙ], p) ↝ [vᵢ | p(vᵢ) = true]

[E-ListFold]
  fold([v₁, ..., vₙ], init, f) ↝ f(...f(f(init, v₁), v₂)..., vₙ)

[E-ListEach]
  each([v₁, ..., vₙ], f) ↝ f(v₁); ...; f(vₙ); ()
```

### Properties

1. **Determinism**: All pure reduction rules are deterministic. Non-determinism arises only from `select` (which task completes first) and `Random` effects.

2. **Type preservation (subject reduction)**: If `Γ; S ⊢ e : T` and `e ↝ e'`, then `Γ; S ⊢ e' : T`. (Proof sketch: by induction on the typing derivation — see SEP-0002 typing judgments.)

3. **Progress**: If `Γ; S ⊢ e : T` and `e` is not a value, then either `e ↝ e'` for some `e'`, or `e` is a `foreign fn` call awaiting I/O. (Holes are ruled out at type-check time in complete programs.)

4. **Effect soundness**: If a function has `uses []` (no effects), its evaluation never reaches an `[E-ForeignCall]` rule. (By the effect subset check in SEP-0003.)
