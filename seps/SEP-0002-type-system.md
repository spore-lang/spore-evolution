---
sep: 2
title: "SEP-0002: Type System"
status: Draft
type: Standards Track
authors:
  - Spore maintainers
created: 2026-03-31
requires:
  - 1
discussion: "https://github.com/spore-lang/spore-evolution/discussions/2"
pr: null
superseded_by: null
---

# SEP-0002: Type System

> **Executive Summary**: Defines Spore's nominal-primary type system with bidirectional inference, separating traits (type interfaces) from effects (external operations). Features three-tier refinement types (L0 decidable constraints → L1 abstract-interpretation → L2 proof obligations), 13 compiler-known traits, generics with where-clause bounds, and enum/struct/trait/effect as the core type constructors. Includes formal typing judgments for the core language.

## Summary

This SEP specifies the type system for the Spore programming language. Spore's type system is a **nominal-primary, bidirectionally-inferred** system that sits between Rust and Haskell on the expressiveness spectrum — more targeted than full dependent types, yet richer than a Hindley–Milner core alone.

The concrete type representation is the `Ty` enum:

Implementation note: **`EffectSet`** stores effect names as strings in current compiler internals (`BTreeSet<String>` in Rust). Surface syntax references those names as literal identifiers.

```text
Ty ::= I8 | I16 | I32 | I64 | U8 | U16 | U32 | U64 | F32 | F64
      | Bool | Str | Unit | Never
      | Tuple([Ty, …])
      | Refined(Ty, var, predicate)
      | Named(name)
      | App(name, [Ty])
      | Record([(name, Ty)])
      | Fn([Ty], Ty, EffectSet)
      | Var(u32)
      | Hole(name)
      | Error
```

**Reference compiler:** This matches the `Ty` enum shipped in `sporec-typeck` (see `crates/sporec-typeck/src/types.rs`): fixed-width numerics, no `Char`, plus `Tuple` and `Refined`. Single-quoted character literals are rejected in the lexer (**no `Char` type or literals**, `spore` PR #113). **Unsuffixed integer literals infer as `I64` and float literals as `F64`** unless a context forces another fixed width. Many examples in this SEP still write `Int` / `Float`; treat them as informal names for those defaults (`I64` / `F64`) until rewritten.

**Platform-specific integers (e.g. process exit status).** The core type system does **not** fix a single machine type for exit codes or other host ABI surfaces. Those contracts live in the **Platform package** metadata and startup/exit specifications (see SEP-0008); this SEP only requires that the Spore signature matches whatever that Platform declares.

**Formal judgments (mixed style).** Core rules in §4 use concrete `I64` / `F64` where they describe default scalar behavior. Where a rule must range over **all** integer or float widths, this SEP uses **ι** ∈ {`I8`, …, `U64`} and **φ** ∈ {`F32`, `F64`} as metavariables, with the default literal case still **ι = `I64`**, **φ = `F64`** unless stated otherwise.

Key design decisions:

- **Signatures are gravity centers** — function signatures must be richly typed and fully explicit; bodies are inferred.
- **EffectSet** is encoded directly in function types (see implementation note above), making effect tracking a first-class part of the type.
- **Current implementation note**: the checker currently carries error sets with a
  similarly plain set-backed internal representation. This wave specifies the
  target canonicalization-first semantics layered on top of that representation,
  without requiring a new dedicated `error` declaration surface.
- **Bidirectional type inference** — top-down checking from signatures, bottom-up synthesis from expressions.
- **Two-pass module checking** — `register_item` (collect all signatures) then `check_fn` (verify bodies).
- **Generics via square-bracket application** — `List[I64]`, `Result[T, E]`.
- **Type unification** with `Var` binding and substitution maps.
- **Refinement types** — L0 decidable predicates ship in `sporec-typeck` (`Ty::Refined`); richer L1 abstract interpretation without an SMT solver remains future work.

## Motivation

### Why a type system specification?

Spore is being co-developed by humans and AI Agents. Both audiences need precise, unambiguous rules for:

1. **What programs are well-typed.** Agents generate code that must type-check. Vague rules produce vague code.
2. **What information flows through signatures.** Signatures are the primary communication channel between components, between humans and Agents, and between Agents. They must encode types, effects, the four-slot cost clause, and error sets.
3. **What the compiler guarantees.** Typed holes, structured diagnostics, and fill-suggestions all depend on a well-defined type lattice.
4. **Where inference ends and annotation begins.** Signatures explicit, bodies inferred — but the boundary must be razor-sharp.

### Problems with the status quo

Without a specification:

- Contributors cannot reason about whether a type-checking change is correct.
- Agent-generated code has no formal target to satisfy.
- Diagnostics cannot explain *why* a type error exists — only *that* one exists.
- Future features (refinements, traits, const generics) have no foundation to build on.

### Design philosophy

| Principle | Implication |
|---|---|
| **Signatures are gravity centers** | Signatures must be richly typed and explicit; bodies are inferred |
| **Nominal-primary, structural escape** | Named types are nominal; anonymous records are structural; traits and effects are always nominal |
| **Traits ≠ Effects** | Separate abstractions — `trait` defines type interfaces, `effect` defines external operations; they are not unified |
| **Decidable checking** | No SMT solver; refinements limited to decidable predicates and abstract interpretation |
| **Agent-friendly** | Richer types help Agents more than they hurt humans; Agents absorb annotation complexity |
| **Predictable** | No implicit conversions, no type-level computation, no SFINAE-style surprises |

## Guide-level explanation

This section introduces Spore's type system from a user's perspective, with code examples showing type annotations, inference, and generics.

### 3.1 Primitive types

Spore provides a small, fixed set of built-in **numeric widths**, text, and logical primitives:

| Type | Description | Notes |
|---|---|---|
| `I8`, `I16`, `I32`, `I64` | Signed integers | Unsuffixed literals default to **`I64`** in `sporec-typeck` |
| `U8`, `U16`, `U32`, `U64` | Unsigned integers | |
| `F32`, `F64` | IEEE-754 binary floats | Literals default to `F64` in the reference checker |
| `Bool` | Boolean | `true`, `false` |
| `Str` | UTF-8 string | Use `"x"` even for a single Unicode scalar; there is **no** `Char` type |
| `Unit` | Zero-information type (like Rust `()`) | `()` |
| `Never` | Bottom type — uninhabited, no values exist | (no literal) |

```spore
let x: I64 = 42              // default integer literal type (I64)
let y: F64 = 3.14            // default float literal type (F64)
let b: Bool = true           // boolean
let s: Str = "hello"         // UTF-8 string
let grapheme: Str = "世"     // still `Str`, not a separate character type
let u: () = ()               // unit (zero-information type)
```

Distinct numeric widths are **not** interchangeable without an explicit conversion story (still evolving). `Str` is unrelated to any numeric width.

**Narrower domains via refinement.** Bounds and lightweight predicates attach to a fixed-width base type (the reference compiler supports this for aliases such as `alias Port = I64 when …`):

```spore
alias NonNegativeI64 = I64 when self >= 0
alias Port = I64 when self >= 1 && self <= 65535
```

Platform code generation maps these types to machine representations; refinements are checked in the decidable fragment described later in this SEP.

**Informal `Int` / `Float` in examples.** Older text may still write `Int` or `Float` for ergonomics. Until those examples are rewritten, read them as referring to the default scalar widths **`I64` / `F64`** in the reference toolchain.

### 3.2 Type annotations on functions

Function signatures **must** be fully annotated. Parameters, return type, error set, effect set, and `cost [c, a, i, p]` clause are all declared:

```spore
fn add(a: I64, b: I64) -> I64 {
    a + b
}

fn fetch_page(url: Str) -> Str ! NetworkError
uses [NetConnect]
cost [5000, 200, 5000, 2]
{
    http_get(url)
}
```

Local variables inside bodies do **not** need annotations — they are inferred:

```spore
fn process(x: I64) -> I64 {
    let doubled = x * 2          // inferred: I64
    let message = "result"       // inferred: Str
    doubled + 1                  // inferred: I64, checked against return type
}
```

### 3.3 Struct and enum types

**Structs** (`struct`) are nominal product types. **`type`** with variants defines sealed sums (ADTs).

```spore
struct Point {
    x: F64,
    y: F64,
}

let p = Point { x: 1.0, y: 2.0 }
let dist = sqrt(p.x * p.x + p.y * p.y)

type Shape =
    Circle { radius: F64 }
    | Rectangle { width: F64, height: F64 }
    | Triangle { a: F64, b: F64, c: F64 }

fn area(shape: Shape) -> F64 {
    match shape {
        Circle { radius }           => 3.14159 * radius * radius,
        Rectangle { width, height } => width * height,
        Triangle { a, b, c } => {
            let sper = (a + b + c) / 2.0;
            sqrt(sper * (sper - a) * (sper - b) * (sper - c))
        },
    }
}
```

### 3.4 Anonymous records (structural)

Anonymous records are the structural escape hatch. They have no declared name and are compatible by field shape, not by declaration site.

```spore
fn greet(person: { name: Str, age: I64 }) -> Str {
    "Hello, " ++ person.name ++ " (age " ++ show(person.age) ++ ")"
}

// Any value with matching fields satisfies this:
let alice = { name: "Alice", age: 30, role: "Engineer" }
greet(alice)   // OK: alice has name: Str and age: I64 (extra fields ignored)
```

**Rules for anonymous records**:

1. **Width subtyping**: A record with extra fields satisfies a type expecting fewer fields.
2. **Exact field matching**: Field names and types must match exactly (no implicit conversion).
3. **No trait implementation**: Anonymous records cannot implement traits or effects — nominal types are required for that.
4. **Nominal types do NOT satisfy anonymous record types**: `struct Stats { count: I64 }` is nominal and is NOT compatible with `{ count: I64 }`.

```spore
// Named types do NOT satisfy anonymous record types:
struct Stats { count: I64, total: F64 }
let named = Stats { count: 10, total: 95.5 }
// summarize(data: named)  // ERROR: Stats is nominal, not { count: I64, total: F64 }

// Explicit conversion required:
summarize(data: { count: named.count, total: named.total })   // OK
```

### 3.5 Function types with effects

Function types carry a **EffectSet** — the set of effects the function requires:

```spore
type Logger = Fn(msg: Str) -> () uses [FileWrite]

fn with_logging(f: Fn(x: I64) -> I64, x: I64) -> I64
uses [FileWrite]
{
    log("calling f")
    let result = f(x)
    log("result: " ++ show(result))
    result
}
```

### 3.6 Generics

Generic functions declare type parameters in square brackets and constrain them in `where` clauses:

```spore
fn identity[T](x: T) -> T {
    x
}

fn map[A, B](list: List[A], f: Fn(item: A) -> B) -> List[B] {
    // implementation
}

fn sort[T](list: List[T]) -> List[T]
where T: Ord
{
    // implementation
}
```

At call sites, type arguments are inferred from the actual argument types:

```spore
let nums: List[I64] = [1, 2, 3]
let result = identity(42)          // T inferred as I64
let strings = map(nums, show)      // A=I64, B=Str inferred
```

### 3.7 Generic type application

Named generic types use square-bracket application in type position:

```spore
struct Pair[A, B] {
    first: A,
    second: B,
}

let p: Pair[I64, Str] = Pair { first: 1, second: "hello" }

type Result[T, E] =
    Ok { value: T }
    | Err { error: E }
```

### 3.8 Newtypes and type aliases

**Newtypes** create zero-cost nominal wrappers. The new type is distinct from its underlying type:

```spore
type UserId = Str       // nominal wrapper: UserId ≠ Str
type Email = Str        // nominal: Email ≠ UserId ≠ Str
type Celsius = F64       // nominal: Celsius ≠ Fahrenheit
type Fahrenheit = F64

fn format_temp(temp: Celsius) -> Str {
    show(temp) ++ "°C"
}

let c: Celsius = 100.0
let f: Fahrenheit = 212.0
format_temp(temp: c)    // OK
format_temp(temp: f)    // ERROR: expected Celsius, got Fahrenheit
format_temp(temp: 98.6) // ERROR: expected Celsius, got F64
```

Newtypes may have refinements:

```spore
type Port = I64 when 1 <= self <= 65535
type NonEmptyStr = Str when self.len() > 0
type Latitude = F64 when -90.0 <= self <= 90.0
```

**Type aliases** are transparent — interchangeable with their definition:

```spore
alias TextList = List[Str]
alias Callback[T] = Fn(event: T) -> Unit
alias Result[T] = T ! GenericError

type SessionId = Str       // newtype: SessionId ≠ Str (nominal)
alias Label = Str    // alias: Label == Str (transparent)
```

### 3.9 Trait system

#### Trait definition

Traits define named interfaces. Spore uses the `trait` keyword for type interfaces. Traits are nominal — a type satisfies a trait only through an explicit `impl` declaration.

```spore
trait Eq {
    fn eq(self, other: Self) -> Bool
}

trait Ord: Eq {
    fn compare(self, other: Self) -> Ordering
}

trait Display {
    fn display(self) -> Str
}

trait Serialize {
    fn serialize(self) -> Bytes ! SerializeError
        cost [100, 20, 0, 1]
}
```

Trait inheritance uses `:` — `Ord: Eq` means every type implementing `Ord` must also implement `Eq`.

#### Trait implementation

Spore uses Rust-style `impl Trait for Type` syntax:

```spore
impl Eq for Point {
    fn eq(self, other: Point) -> Bool {
        self.x == other.x && self.y == other.y
    }
}

impl Ord for Point {
    fn compare(self, other: Point) -> Ordering {
        let dx = self.x.compare(other.x)
        if dx != Equal { dx } else { self.y.compare(other.y) }
    }
}

impl Display for Shape {
    fn display(self) -> Str {
        match self {
            Circle { radius }           => "Circle(r=" ++ show(radius) ++ ")",
            Rectangle { width, height } => "Rect(" ++ show(width) ++ "x" ++ show(height) ++ ")",
            Triangle { a, b, c }        => "Tri(" ++ show(a) ++ "," ++ show(b) ++ "," ++ show(c) ++ ")",
        }
    }
}
```

Default method implementations are supported:

```spore
trait Collection {
    type Item
    fn len(self) -> I64
    fn is_empty(self) -> Bool { self.len() == 0 }   // default method
}
```

#### Trait bounds

Trait bounds constrain generic type parameters in `where` clauses:

```spore
fn sort[T](list: List[T]) -> List[T]
where T: Ord
cost [500, 100, 0, 1]
{
    // implementation
}

fn serialize_all[T](items: List[T]) -> List[Bytes] ! SerializeError
where T: Serialize + Display
{
    items |> map(|item| item.serialize())
}
```

Multiple bounds use `+`:

```spore
fn dedup_and_display[T](items: List[T]) -> Str
where T: Eq + Hash + Display
{
    items |> unique() |> map(|x| x.display()) |> join(", ")
}
```

#### Trait vs. Effect (separated)

This is one of Spore's central design decisions. **Traits** and **effects** are separate constructs:

- **`trait`** defines type interfaces. Used with `where T: Trait` bounds.
- **`effect`** defines external operations and named effect aliases. Used with `uses [Effect]` declarations.
- **`handler`** provides concrete implementations for effect operations; handler semantics are specified in SEP-0003.

These two systems are never mixed: `where` is for traits, `uses` is for effects.

Concrete surface syntax for `trait`, `effect`, `handler`, and `handle ... with` is centralized in SEP-0001 (§"Traits, effects, and the `uses` clause" and the EBNF grammar). This SEP only depends on the semantic split:

```spore
trait Serialize {
    fn serialize(self) -> Bytes ! SerializeError
}

effect HttpClient = NetConnect | Clock

fn fetch_page(url: Url) -> Response ! NetworkError
uses [HttpClient]
{
    ...
}
```

`where` constrains trait obligations; `uses` constrains effect requirements. Effect algebra and handler installation are specified in SEP-0003.

#### Associated types

Traits may declare associated types — types determined by the implementing type:

```spore
trait Iterator {
    type Item
    fn next(self) -> Option[Self.Item]
        cost [10, 80, 0, 1]
}

impl Iterator for LineReader {
    type Item = Str
    fn next(self) -> Option[Str] {
        self.read_line()
    }
}

trait Collection {
    type Item
    type Iter: Iterator where Iter.Item == Self.Item

    fn iter(self) -> Self.Iter
    fn len(self) -> I64
    fn is_empty(self) -> Bool { self.len() == 0 }
}
```

Associated types eliminate extra type parameters on trait users:

```spore
// Clean — associated types:
fn sum_all[C](collection: C) -> I64
where
    C: Collection,
    C.Item: Add[Output = I64]
{
    collection.iter() |> fold(0, |acc, item| acc + item)
}
```

#### Generic Associated Types (GATs)

GATs allow associated types to have their own generic parameters, enabling patterns like lending iterators and self-referential collections:

```spore
trait LendingIterator {
    type Item[lifetime]
    fn next[lifetime](self) -> Option[Self.Item[lifetime]]
}

trait Container {
    type Elem[T]
    fn wrap[T](value: T) -> Self.Elem[T]
    fn unwrap[T](wrapped: Self.Elem[T]) -> T
}

impl Container for OptionContainer {
    type Elem[T] = Option[T]
    fn wrap[T](value: T) -> Option[T] { Some(value) }
    fn unwrap[T](wrapped: Option[T]) -> T {
        match wrapped {
            Some(v) => v,
            None    => panic("unwrap of None"),
        }
    }
}
```

GATs cover the most common use cases that HKTs would serve without introducing full higher-kinded polymorphism.

#### Built-in traits and deriving

Spore provides compiler-known traits for common operations:

| Trait | Purpose | Derivable |
|---|---|---|
| `Eq` | Equality comparison | Yes |
| `Ord` | Ordering | Yes |
| `Clone` | Value duplication | Yes |
| `Display` | Human-readable formatting | No |
| `Debug` | Debug formatting | Yes |
| `Hash` | Hash computation | Yes |
| `Default` | Default value construction | Yes |
| `Serialize` | Serialization to bytes | Yes |
| `Deserialize` | Deserialization from bytes | Yes |
| `Add`, `Sub`, `Mul`, `Div` | Arithmetic operators | No |

Derivable traits can be auto-implemented by the compiler for types whose fields all implement the trait:

```spore
struct Point {
    x: F64,
    y: F64,
} deriving [Eq, Clone, Debug, Hash]
```

#### Coherence and orphan rules

You can only implement a trait for a type if you own either the trait or the type:

```spore
// OK: you own Point, so you can implement any trait for it
impl Display for Point { ... }

// OK: you own MyTrait, so you can implement it for any type
impl MyTrait for Str { ... }

// ERROR: you own neither Display nor Str
impl Display for Str { ... }   // orphan rule violation
```

**Adapter escape mechanism** for implementing foreign traits on foreign types:

```spore
adapter ExternalType as Printable {
    fn display(self) -> Str { ... }
}

fn use_external(x: ExternalType) -> Str
where adapter: ExternalType as Printable
{
    x.display()
}
```

Adapters are always scoped and explicit — they cannot cause global coherence violations.

### 3.10 Const generics

#### Const generic parameters

### List vs `Vec`

**Naming invariant:** **`List[T]` is always unbounded** — the `List` constructor never carries a `max:` parameter. **`Vec[T, max: N]` is always bounded** — every `Vec` declares a compile-time cap `N` (const-generic), useful when the **type system** must know a fixed capacity (e.g. small matrices, SIMD lanes, rare “cap in the type” APIs).

**Style rule:** **`List[T]` is the default** for almost all APIs, examples, and iteration. Model sizes and budgets with `cost [...]`, refinements, and runtime checks on `len` as usual—**do not** sprinkle `Vec[..., max: N]` unless you genuinely need `N` in the type.

**`Vec`** is for const-generic layouts (see below)—not for everyday collections.

Const generics allow value-level parameters in type position. Spore commonly uses them for **`Matrix`**, **`Array[T, N]`**, and the optional **`Vec[T, max: N]`** packed buffer type:

```spore
struct Vec[T, max: I64] {
    data: Array[T],
    len: I64,
}

// Typical slicing stays on List — no Vec required:
fn take[T](list: List[T], n: I64) -> List[T]
{
    // prefix of length ≤ n (empty if n ≤ 0); cost keyed off n and list.len()
}

struct Matrix[T, rows: I64, cols: I64] {
    data: Array[Array[T]],
}
```

#### Type-level arithmetic

Const generic parameters support arithmetic in type-level expressions, enabling compile-time dimensional checking (mostly for **`Matrix`** / **`Array`**, not for ordinary `List` code):

```spore
fn transpose[T, R: I64, C: I64](
    matrix: Matrix[T, rows: R, cols: C],
) -> Matrix[T, rows: C, cols: R] {
    // implementation
}

// Optional: only when Vec's max must appear in the type (buffers with static M+N):
fn concat_vec[T, M: I64, N: I64](
    a: Vec[T, max: M],
    b: Vec[T, max: N],
) -> Vec[T, max: M + N] {
    // implementation
}
```

Supported arithmetic operations in type position: `+`, `-`, `*`, `/`, `%`, `min`, `max`. All arithmetic is evaluated at compile time. Division by zero and overflow are compile-time errors.

#### Interaction with cost

Cost clauses usually refer to **runtime** sizes (`items.len`, parameters, refinements). **`List[T]`** is enough for those budgets—**no `Vec` required**:

```spore
fn linear_search[T](items: List[T], target: T) -> Option[I64]
where T: Eq
cost [items.len * 5, items.len, 0, 1]
{
    // O(n) search; n = items.len
}

fn sort_list[T](items: List[T]) -> List[T]
where T: Ord
cost [items.len * items.len * 2, items.len, 0, 1]
{
    // worst-case O(n²); n = items.len
}
```

When you **do** use `Vec[T, max: N]`, the declared `N` can appear directly in `cost [...]` (parametric verification). That pattern is specialized; prefer `List` + len-indexed cost for most functions.

### 3.11 Pattern matching

Spore requires **full, exhaustive pattern matching** on all enums. The compiler enforces that every possible variant is handled.

#### Exhaustiveness checking

```spore
fn describe(shape: Shape) -> Str {
    match shape {
        Circle { radius }           => "circle with radius " ++ show(radius),
        Rectangle { width, height } => show(width) ++ "x" ++ show(height) ++ " rectangle",
        Triangle { a, b, c }        => "triangle with sides " ++ show(a) ++ ", " ++ show(b) ++ ", " ++ show(c),
    }
}
```

Missing a variant is a compile-time error:

```text
Error: Non-exhaustive match

12 |    match shape {
   |    ^^^^^
   Missing variant: Triangle { a, b, c }

   All Shape variants must be handled because Shape is a sealed enum.
```

#### Nested patterns

Patterns can be nested to match deeply into data structures:

```spore
type Expr =
    Literal { value: I64 }
    | BinOp { op: Op, left: Expr, right: Expr }
    | UnaryOp { op: Op, operand: Expr }

fn simplify(expr: Expr) -> Expr {
    match expr {
        BinOp { op: Add, left: Literal { value: 0 }, right: e } => simplify(e),
        BinOp { op: Mul, left: Literal { value: 1 }, right: e } => simplify(e),
        BinOp { op: Mul, left: Literal { value: 0 }, right: _ } => Literal { value: 0 },
        BinOp { op, left, right } => BinOp {
            op: op,
            left: simplify(left),
            right: simplify(right),
        },
        other => other,
    }
}
```

Nested Option/Result matching:

```spore
fn handle(value: Option[Result[I64, Str]]) -> I64 {
    match value {
        Some(Ok(n))    => n,
        Some(Err(msg)) => panic("error: " ++ msg),
        None           => 0,
    }
}
```

#### Guard clauses

Guards add boolean conditions to pattern branches:

```spore
fn classify_temperature(temp: F64) -> Str {
    match temp {
        t if t < -40.0  => "extreme cold",
        t if t < 0.0    => "freezing",
        t if t < 20.0   => "cool",
        t if t < 35.0   => "warm",
        t if t < 50.0   => "hot",
        _               => "extreme heat",
    }
}
```

**Important**: Guards weaken exhaustiveness guarantees. The compiler requires a catch-all (`_` or variable) arm when guards are used, because it cannot generally prove that guards cover all cases.

#### Or-patterns

Or-patterns match multiple alternatives with the same arm:

```spore
fn is_weekend(day: Day) -> Bool {
    match day {
        Saturday | Sunday => true,
        _                 => false,
    }
}

fn is_simple_shape(shape: Shape) -> Bool {
    match shape {
        Circle { .. } | Rectangle { .. } => true,
        _                                 => false,
    }
}
```

#### Destructuring in let bindings

Pattern matching works in `let` bindings:

```spore
fn distance(a: Point, b: Point) -> F64 {
    let Point { x: x1, y: y1 } = a
    let Point { x: x2, y: y2 } = b
    sqrt((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1))
}
```

#### Wildcard and rest patterns

- `_` matches any single value (discarded).
- `..` in struct patterns matches remaining fields.

```spore
fn get_name(person: Person) -> Str {
    let Person { name, .. } = person
    name
}
```

#### Pattern matching on error types

Pattern matching integrates with Spore's closed error sets for exhaustive error
handling:

```spore
fn handle_result(result: Invoice ! TaxError | ValidationError) -> Str {
    match result {
        Ok(invoice) => "Invoice #" ++ show(invoice.id),
        Err(TaxError { region, reason }) => "Tax error in " ++ show(region) ++ ": " ++ reason,
        Err(ValidationError { field, message }) => "Validation failed on " ++ field ++ ": " ++ message,
    }
}
```

### 3.12 @allows constraint

`@allows` is a hole-level constraint that limits which functions an Agent may use to fill a specific hole. It provides fine-grained control over Agent behavior without affecting the type system's soundness.

```spore
fn process_payment(amount: Money, card: Card) -> Receipt ! PaymentFailed
uses [PaymentGateway, AuditLog]
cost [2000, 400, 200, 2]
{
    let validated = validate_card(card)
    @allows[charge, charge_with_retry]
    ?payment_logic
}
```

**Semantics of @allows**:

- `@allows[f1, f2, ...]` annotates the immediately following hole.
- The Agent, when filling this hole, may only call the listed functions (plus pure helper functions that require no effects).
- The compiler verifies that the filling respects the `@allows` constraint.
- `@allows` is **not** a type — it is a **synthesis constraint** that restricts the search space for hole-filling.

**Use case — architectural intent**:

```spore
fn build_dashboard(org: Org) -> Dashboard ! DataError
uses [Database, Cache, Analytics]
cost [20000, 2000, 1000, 8]
{
    @allows[fetch_cached_metrics, compute_summary]
    let metrics = ?gather_metrics

    @allows[render_chart, render_table]
    let charts = ?render_visualizations

    Dashboard.new(org, metrics, charts)
}
```

If an Agent proposes a filling for `?gather_metrics` that calls `raw_sql_query`, the compiler rejects it:

```text
Error: @allows violation

  Hole ?gather_metrics is constrained by @allows[fetch_cached_metrics, compute_summary]
  but the proposed filling calls `raw_sql_query`, which is not in the allowed set.
```

### 3.13 Never bottom type

`Never` is the bottom type — it has no values and is a subtype of every type. It is the return type of functions that do not return (diverging functions).

```spore
fn abort(msg: Str) -> Never {
    panic(msg)
}

fn safe_divide(a: I64, b: I64) -> I64 {
    if b == 0 {
        abort("division by zero")   // Never coerces to I64
    } else {
        a / b
    }
}
```

**Use in exhaustive matching** — a branch returning `Never` is compatible with any arm type:

```spore
fn safe_unwrap[T](opt: Option[T]) -> T {
    match opt {
        Some(v) => v,
        None    => panic("unwrap of None"),   // panic returns Never, coerces to T
    }
}
```

`Never` is the natural type for:

- `panic(...)` and `abort(...)` calls
- Diverging expressions (non-terminating recursion)
- Exhaustive match arms that provably never execute
- Error-only functions that always raise

### 3.14 Canonicalized error sets

Spore's `! Err1 | Err2` is a **closed error set** written in surface form but
checked with **canonicalization-first semantics**. Error types are nominal ADTs;
the checker resolves each written item to a canonical identity, removes
duplicates, and compares sets using that canonical form across call chains.

Current implementation note: the shipping checker already supports the
`! E1 | E2` surface and stores propagated error requirements in a plain set-like
internal form. This section defines the **target behavior of this wave**:
canonical subset/equivalence checks, redundancy diagnostics, and conservative
hashing. It does **not** require a new top-level `error Alias = ...` syntax.

```text
canonicalize(E_written):
  1. resolve each written error item to its canonical nominal identity
  2. drop duplicates and canonically equivalent spellings
  3. order the result by a stable canonical key for comparison / diagnostics
```

Two written error clauses are **equivalent** when their canonicalized sets are
equal, even if their source spelling differs. A caller is **compatible** with a
callee when `canonicalize(E_callee) ⊆ canonicalize(E_caller)`.

```spore
alias ParseFailure = config.errors.ParseError

fn parse(input: Str) -> Ast ! config.errors.ParseError
fn parse_again(input: Str) -> Ast ! ParseFailure | config.errors.ParseError
```

`parse_again` is semantically equivalent to `! config.errors.ParseError`; the
second item is redundant and should be diagnosed as such.

Error sets still compose automatically via `?` propagation:

```spore
fn parse(input: Str) -> Ast ! SyntaxError | EncodingError
fn validate(ast: Ast) -> ValidAst ! TypeError | RangeError

// Error sets union automatically via `?` propagation:
fn compile(input: Str) -> ValidAst ! SyntaxError | EncodingError | TypeError | RangeError {
    let ast = parse(input)?
    validate(ast)?
}
```

Each error type carries structured data:

```spore
struct SyntaxError {
    line: I64,
    column: I64,
    message: Str,
    snippet: Str,
}
```

**Canonical subset rule**: A function with error set `! A` can be called where
`! A | B` is expected when `canonicalize({A}) ⊆ canonicalize({A, B})`.

**`?` operator**: Propagates errors by canonical subset check. If `f()` returns
`T ! E1` and `g()` returns `T ! E2`, calling both with `?` in the same function
requires the enclosing function to declare a canonical superset of
`canonicalize({E1, E2})`.

**Redundancy diagnostics**: If a declaration writes duplicate or canonically
equivalent error items, the compiler should keep checking against the
canonicalized set but emit a structured redundancy diagnostic. User-facing text
should stay engineering-oriented, e.g. "redundant error item `ParseFailure`:
already covered by `config.errors.ParseError`".

### 3.15 Recursive types

Enums and structs may be recursive. The compiler detects and supports this:

```spore
type Expr =
    Literal { value: I64 }
    | BinOp { op: Op, left: Expr, right: Expr }
    | UnaryOp { op: Op, operand: Expr }
    | IfExpr { cond: Expr, then_branch: Expr, else_branch: Expr }

type JsonValue =
    JsonNull
    | JsonBool { value: Bool }
    | JsonNumber { value: F64 }
    | JsonString { value: Str }
    | JsonArray { elements: List[JsonValue] }
    | JsonObject { fields: List[{ key: Str, value: JsonValue }] }
```

**Infinite-size check**: The compiler rejects types that would require infinite memory without indirection:

```spore
// ERROR: infinite-size type (struct directly contains itself)
struct Bad {
    next: Bad,   // Bad contains Bad with no indirection
}

// OK: indirection via List breaks the cycle
struct Tree[T] {
    value: T,
    children: List[Tree[T]],   // List provides indirection
}
```

### 3.16 Nominal vs structural rules

| Context | Typing Discipline | Rationale |
|---|---|---|
| Named types (`struct` / `type` with variants) | **Nominal** | `UserId ≠ Str` even if same representation |
| Enums | **Nominal** | Sealed, exhaustiveness-checked |
| Traits / effects | **Nominal** | Explicit `impl` required |
| Effects | **Nominal** (always) | Security boundary — no structural coincidence |
| Anonymous records `{ ... }` | **Structural** | Flexibility for intermediate values |
| Hole-filling search (internal) | **Structural** | Agent searches by shape, compiler enforces nominal at boundaries |
| Function call boundaries | **Nominal** | Callee specifies named types, caller must provide them |

### 3.17 Type inference annotation requirements

| Element | Must Annotate? | Why |
|---|---|---|
| Function parameter types | **Yes** | Gravity center — the signature IS the API |
| Function return type | **Yes** | Agent reads signatures for synthesis; human reads for understanding |
| Error sets (`! ...`) | **Yes** | Error contract — must be visible |
| Effect sets (`uses [...]`) | **Yes** | Security boundary — must be visible |
| Cost clause (`cost [c, a, i, p]`) | **Yes** | Performance contract — must be visible |
| Struct/type field types | **Yes** | Data definition — must be explicit |
| Trait method signatures | **Yes** | Interface contract |
| Public constants | **Yes** | API surface |
| Local variable types | No | Inferred from RHS: `let x = compute(...)` |
| Generic type params at call sites | No | Inferred from arguments: `sort(my_list)` — T inferred from `my_list` |
| Closure parameter types (in context) | No | Inferred: `.map(\|x\| x + 1)` — x inferred from Iterator.Item |
| Intermediate expression types | No | Standard local inference |

### 3.18 Typed holes

Holes are unfilled positions in code. The type checker infers their expected type from context and reports it:

```spore
fn example(x: I64, y: Str) -> Bool {
    let a: I64 = ?h1          // hole ?h1 must produce I64
    let b = if a > 0 {
        ?h2                   // hole ?h2 must produce Bool (from return type)
    } else {
        false
    }
    b
}
```

The compiler reports:

```text
Hole ?h1: expected type I64
Hole ?h2: expected type Bool
```

## Reference-level explanation

### 4.1 Type grammar

The internal type representation is the `Ty` enum, defined in `crates/sporec-typeck/src/types.rs`:

```text
τ ::= I8 | I16 | I32 | I64 | U8 | U16 | U32 | U64 | F32 | F64
    | Bool                         // boolean primitive
    | Str                          // UTF-8 string (`Str` in surface syntax)
    | Unit                         // unit type (also `()`); empty tuple syntax normalizes here
    | Never                        // bottom type (uninhabited)
    | Tuple([τ₁, …, τₙ])          // tuple type (n ≥ 2; empty tuple is Unit)
    | Refined(τ, var, predicate) // refinement (decidable fragment)
    | Named(n)                     // named type / type parameter
    | App(n, [τ₁, …, τₖ])         // generic type application
    | Record([(f₁, τ₁), …])       // anonymous record (structural)
    | Fn([τ₁, …, τₙ], τᵣ, C)     // function type with effect set
    | Var(id)                      // unification variable
    | Hole(name)                   // typed hole placeholder
    | Error                        // error sentinel (recovery)
```

Where:

- `n` ranges over identifiers (strings).
- `id` ranges over `u32` (unique unification variable IDs).
- `C` is a **EffectSet** = `BTreeSet<String>`, the set of effect names the function requires.
- `f` ranges over field names (strings) in anonymous records.

**Never type.** `Ty::Never` is the bottom type — a subtype of all types. It is produced by diverging expressions (`panic`, non-terminating recursion). During unification, `unify(τ, Never) = ok` for all `τ`.

**Record type.** `Ty::Record` represents anonymous structural records. Width subtyping applies: `Record([(a, I64), (b, Str), (c, Bool)])` is a subtype of `Record([(a, I64), (b, Str)])`.

**Error sentinel.** `Ty::Error` is produced when type resolution fails (e.g., unknown type name). It unifies with anything, allowing the checker to continue after errors and report multiple diagnostics.

**Hole type.** `Ty::Hole(name)` represents an unfilled hole. During unification, holes are compatible with anything — the checker records the expected type for diagnostic purposes without blocking further checking.

### 4.2 Effect sets (EffectSet)

```rust
pub type EffectSet = BTreeSet<String>;
```

A `EffectSet` is a sorted set of effect names. It appears as the third component of `Ty::Fn`:

```text
Fn([τ₁, …, τₙ], τᵣ, { cap₁, cap₂, … })
```

**EffectSet rules:**

1. A function may only call another function whose EffectSet is a **subset** of its own.
2. A pure function has `EffectSet = ∅`.
3. EffectSets propagate through higher-order calls: passing a `Fn(...) uses [NetConnect]` to a higher-order function requires the caller to declare `NetConnect`.
4. `uses [Effect1, Effect2]` in source syntax maps directly to `EffectSet = {"Effect1", "Effect2"}`.

**Formal effect checking rule:**

```text
Γ ⊢ f : Fn([σ₁, …, σₙ], τᵣ, C_f)
C_caller ⊇ C_f
─────────────────────────────────────────
Γ; C_caller ⊢ f(e₁, …, eₙ) : τᵣ
```

If `C_f ⊄ C_caller`, the checker emits:

```text
missing effects [X, Y]: caller does not declare them
```

### Formal typing judgments

The core type system uses bidirectional typing with effect context.

**Notation:**

- `Γ` — type environment (variable → type mapping)
- `S` — effect set (subset of all effects)
- `e` — expression
- `T` — type
- `⊢` — "entails" / judgment turnstile
- `⇒` — type synthesis (infer)
- `⇐` — type checking (against expected)

**Core judgments:**

```text
Γ; S ⊢ e ⇒ T        (synthesis: infer type of e)
Γ; S ⊢ e ⇐ T        (checking: check e against T)
```

**Rules:**

```text
[Var]
  x : T ∈ Γ
  ─────────────────
  Γ; S ⊢ x ⇒ T

[Literal-I64]
  ─────────────────
  Γ; S ⊢ n ⇒ I64

  (Default unsuffixed integer literal per §3.1; a checking context may instead fix another **ι** ∈ {`I8`, …, `U64`}.)

[Literal-F64]
  ─────────────────
  Γ; S ⊢ c ⇒ F64

  (Default unsuffixed float literal per §3.1; a checking context may instead fix another **φ** ∈ {`F32`, `F64`}.)

[Literal-Str]
  ─────────────────
  Γ; S ⊢ s ⇒ Str

[Literal-Bool]
  ─────────────────
  Γ; S ⊢ b ⇒ Bool

[Lambda]
  Γ, x : T₁ ; S ⊢ body ⇐ T₂
  ─────────────────────────────
  Γ; S ⊢ (fn(x: T₁) -> T₂ { body }) ⇒ T₁ → T₂ uses S

[App]
  Γ; S ⊢ f ⇒ T₁ → T₂ uses S_f
  Γ; S ⊢ arg ⇐ T₁
  S_f ⊆ S
  ─────────────────────────────
  Γ; S ⊢ f(arg) ⇒ T₂

[Let]
  Γ; S ⊢ e₁ ⇒ T₁
  Γ, x : T₁ ; S ⊢ e₂ ⇒ T₂
  ─────────────────────────────
  Γ; S ⊢ (let x = e₁; e₂) ⇒ T₂

[If]
  Γ; S ⊢ cond ⇐ Bool
  Γ; S ⊢ then_branch ⇒ T
  Γ; S ⊢ else_branch ⇐ T
  ─────────────────────────────
  Γ; S ⊢ (if cond { then } else { else }) ⇒ T

[Match]
  Γ; S ⊢ scrutinee ⇒ T_s
  ∀i: pattern_i exhaustive over T_s
  ∀i: Γ, bindings(pattern_i) ; S ⊢ body_i ⇒ T
  ─────────────────────────────────────────────
  Γ; S ⊢ (match scrutinee { pattern_i => body_i }) ⇒ T

[StructConstruct]
  struct S { f₁: T₁, ..., fₙ: Tₙ } ∈ Γ
  ∀i: Γ; S_cap ⊢ eᵢ ⇐ Tᵢ
  ─────────────────────────────
  Γ; S_cap ⊢ S { f₁: e₁, ..., fₙ: eₙ } ⇒ S

[FieldAccess]
  Γ; S ⊢ e ⇒ T_struct
  T_struct has field f : T_f
  ─────────────────────────────
  Γ; S ⊢ e.f ⇒ T_f

[EnumConstruct]
  type E { ..., V(T₁, ..., Tₙ), ... } ∈ Γ
  ∀i: Γ; S ⊢ eᵢ ⇐ Tᵢ
  ─────────────────────────────
  Γ; S ⊢ V(e₁, ..., eₙ) ⇒ E

[Spawn]
  Γ; S ⊢ e ⇒ T uses S_e
  Spawn ∈ S
  ─────────────────────────────
  Γ; S ⊢ spawn e ⇒ Task[T]

[Await]
  Γ; S ⊢ e ⇒ Task[T]
  ─────────────────────────────
  Γ; S ⊢ await e ⇒ T

[EffectCheck]
  Γ; S ⊢ e ⇒ T uses S_required
  S_required ⊆ S
  ─────────────────────────────
  (e is valid in effect context S)

[Sub]
  Γ; S ⊢ e ⇒ T₁
  T₁ <: T₂
  ─────────────────────────────
  Γ; S ⊢ e ⇐ T₂
```

**Subtyping rules:**

```text
[Sub-Refl]
  T <: T

[Sub-Fn]
  T₁' <: T₁    T₂ <: T₂'    S ⊆ S'
  ─────────────────────────────
  (T₁ → T₂ uses S) <: (T₁' → T₂' uses S')
  (contravariant params, covariant return, covariant effects)

[Sub-Task]
  T <: T'
  ─────────────────────────────
  Task[T] <: Task[T']
```

### 4.3 Bidirectional type inference

Spore uses **bidirectional type checking** with two modes:

- **Check mode (⇐):** An expected type is pushed down from the context (function return type, let-binding annotation, argument position).
- **Synth mode (⇒):** A type is synthesized bottom-up from the expression structure.

#### Inference rules (core subset)

**Literals (synthesis):** default widths are §3.1 (`I64`, `F64`). For a non-default fixed width, read those conclusions as **ι** / **φ** when a context, annotation, or suffix fixes another member of the same families.

```text
─────────────────
Γ ⊢ n ⇒ I64          (integer literal)

─────────────────
Γ ⊢ c ⇒ F64        (float literal)

─────────────────
Γ ⊢ s ⇒ Str          (string literal)

─────────────────
Γ ⊢ b ⇒ Bool         (boolean literal)
```

**Variable lookup (synthesis):**

```text
x : τ ∈ Γ
──────────────
Γ ⊢ x ⇒ τ
```

**Function application (synthesis):**

```text
Γ ⊢ f ⇒ Fn([σ₁, …, σₙ], τᵣ, C)
Γ ⊢ eᵢ ⇐ σᵢ   for i ∈ 1..n
C ⊆ C_current
──────────────────────────────────
Γ; C_current ⊢ f(e₁, …, eₙ) ⇒ τᵣ
```

**Let binding (synthesis):**

```text
Γ ⊢ e₁ ⇒ τ₁
Γ, x : τ₁ ⊢ e₂ ⇒ τ₂
────────────────────────
Γ ⊢ let x = e₁; e₂ ⇒ τ₂
```

**If-else (synthesis):**

```text
Γ ⊢ cond ⇐ Bool
Γ ⊢ e_then ⇒ τ
Γ ⊢ e_else ⇒ τ
────────────────────────────
Γ ⊢ if cond { e_then } else { e_else } ⇒ τ
```

**Function body checking (check mode):**

```text
fn f(x₁: σ₁, …, xₙ: σₙ) -> τᵣ uses [C] { body }

Γ' = Γ, x₁ : σ₁, …, xₙ : σₙ
Γ'; C ⊢ body ⇒ τ_body
unify(τᵣ, τ_body)
───────────────────────────────
Γ ⊢ f ok
```

This matches the implementation in `check_fn`:

```rust
fn check_fn(&mut self, f: &FnDef) {
    // bind parameters
    for param in &f.params {
        let ty = self.resolve_type(&param.ty);
        self.env.define(param.name.clone(), ty);
    }
    // synthesize body type
    let body_ty = self.check_expr(body);
    let body_ty = self.apply_subst(&body_ty);
    let declared_ret = self.apply_subst(&declared_ret);
    // unify return type with body type
    self.unify(&declared_ret, &body_ty, &format!("function `{}`", f.name));
}
```

### 4.4 Generics — type variables, substitution, and unification

#### Type variables

A fresh type variable is created with a unique `u32` ID:

```rust
fn fresh_var(&mut self) -> Ty {
    let id = self.next_var_id;
    self.next_var_id += 1;
    Ty::Var(id)
}
```

When a generic function is called, each type parameter is replaced by a fresh `Ty::Var`. The unifier then resolves these variables by matching against actual argument types.

#### Substitution

A substitution `σ : u32 → Ty` is a partial map from variable IDs to resolved types. Applying a substitution walks the type recursively:

```text
apply_subst(Var(id))               = σ(id)            if id ∈ dom(σ)
apply_subst(Var(id))               = Var(id)          otherwise
apply_subst(Fn(ps, r, C))         = Fn(apply_subst(ps), apply_subst(r), C)
apply_subst(App(n, args))         = App(n, apply_subst(args))
apply_subst(Record(fields))       = Record([(f, apply_subst(τ)) for (f, τ) in fields])
apply_subst(τ)                    = τ                  for all other τ
```

Note that `EffectSet` is **not** subject to substitution — effects are always concrete strings, never type variables.

#### Unification algorithm

The `unify` function is the heart of type inference. Given two types `expected` and `actual`, it either succeeds (possibly binding type variables) or emits an error:

```text
unify(τ, τ) = ok                                        (reflexivity)
unify(Never, _) = ok                                    (bottom type: Never <: τ)
unify(_, Never) = ok                                    (bottom type: Never <: τ)
unify(Error, _) = ok                                    (error recovery)
unify(_, Error) = ok                                    (error recovery)
unify(Hole(_), _) = ok                                  (hole compatibility)
unify(_, Hole(_)) = ok                                  (hole compatibility)
unify(Var(id), τ) = σ[id ↦ τ]  if occurs_check(id, τ)  (variable binding)
unify(τ, Var(id)) = σ[id ↦ τ]  if occurs_check(id, τ)  (variable binding, symmetric)
unify(Fn(ps₁, r₁, _), Fn(ps₂, r₂, _))                  (structural: function)
    = unify(ps₁[i], ps₂[i]) for all i; unify(r₁, r₂)
unify(App(n, as₁), App(n, as₂))                         (structural: application)
    = unify(as₁[i], as₂[i]) for all i
unify(Record(fs₁), Record(fs₂))                         (structural: record, width subtyping)
    = for each (f, τ) in fs₂: require f in fs₁ and unify(fs₁[f], τ)
unify(τ₁, τ₂)                                           (mismatch)
    = error "type mismatch: expected τ₁, got τ₂"
```

**Occurs check.** The unifier performs an occurs check to prevent cyclic substitutions (e.g., `Var(0) ↦ List[Var(0)]`). If `Var(id)` occurs within `τ`, binding fails with an error rather than creating an infinite type.

**Never in unification.** `Never` unifies with any type, implementing the bottom-type subtyping rule `Never <: τ` directly within the unifier. This enables diverging expressions (e.g., `panic(...)`) to appear in any expression position.

### 4.5 Two-pass module checking

Module checking proceeds in two passes, implemented in `check_module`:

```rust
pub fn check_module(&mut self, module: &Module) {
    // Pass 1: register all top-level declarations
    for item in &module.items {
        self.register_item(item);
    }
    // Pass 2: check function bodies
    for item in &module.items {
        self.check_item(item);
    }
}
```

**Pass 1 — `register_item`:** Iterates over all top-level items (functions, structs, type definitions) and registers their signatures in the `TypeRegistry`:

- **Functions:** Parameter types are resolved, return type is resolved (default `Unit`), EffectSet is extracted from `uses` clause, and type parameters from `where` clause are recorded.
- **Structs:** Field names and types are resolved and stored.
- **Type defs (enums):** Variant names and field types are resolved and stored.
- **Effects and imports:** Deferred (no registration needed).

**Pass 2 — `check_fn`:** For each function with a body:

1. Set the current EffectSet from the function's `uses` clause.
2. Push a new scope in the environment.
3. Bind each parameter to its declared type.
4. Synthesize the body type via `check_expr`.
5. Apply the current substitution to both the body type and declared return type.
6. Unify the declared return type with the body type.
7. Pop the scope and restore the previous context.

This two-pass design allows **forward references** — a function can call another function defined later in the same module.

### 4.6 Struct types

Struct types are registered as a list of `(field_name, Ty)` pairs. Field access is checked by looking up the struct name in the registry and finding the named field:

```text
Γ ⊢ e ⇒ Named(S)
S.fields contains (f, τ_f)
────────────────────────────
Γ ⊢ e.f ⇒ τ_f
```

Struct construction checks that all fields are present and each expression matches the declared field type:

```text
S.fields = [(f₁, τ₁), …, (fₙ, τₙ)]
Γ ⊢ eᵢ ⇐ τᵢ  for all i ∈ 1..n
────────────────────────────────────
Γ ⊢ S { f₁: e₁, …, fₙ: eₙ } ⇒ Named(S)
```

### 4.7 Anonymous record types

Anonymous records are represented as `Ty::Record(Vec<(InternedFieldName, Ty)>)` (field labels stored as interned UTF-8 identifiers in the implementation). Record construction synthesizes the type from field expressions:

```text
Γ ⊢ e₁ ⇒ τ₁  …  Γ ⊢ eₖ ⇒ τₖ
─────────────────────────────────────────────
Γ ⊢ { f₁: e₁, …, fₖ: eₖ } ⇒ Record([(f₁, τ₁), …, (fₖ, τₖ)])
```

Field access on anonymous records:

```text
Γ ⊢ e ⇒ Record(fields)
(f, τ_f) ∈ fields
────────────────────────
Γ ⊢ e.f ⇒ τ_f
```

**Width subtyping rule**: An anonymous record with more fields is a subtype of one with fewer fields:

```text
fields₁ ⊇ fields₂  (by field name)
∀ (f, τ) ∈ fields₂ : unify(fields₁[f], τ) = ok
─────────────────────────────────────────────────
Record(fields₁) <: Record(fields₂)
```

**Nominal types do NOT satisfy anonymous record types.** `Named("Point")` and `Record([(x, F64), (y, F64)])` are distinct types even if `Point` has the same fields.

### 4.8 Function types

Function types are `Ty::Fn(params, ret, EffectSet)`:

```text
Fn([σ₁, …, σₙ], τᵣ, C)
```

A function value is a first-class value. Looking up a function name in the registry when it appears as a bare expression produces its function type:

```rust
Expr::Var(name) => {
    if let Some(ty) = self.env.lookup(name) {
        ty.clone()
    } else if let Some((params, ret, caps)) = self.registry.functions.get(name) {
        Ty::Fn(params.clone(), Box::new(ret.clone()), caps.clone())
    } else {
        self.err(format!("undefined variable `{name}`"));
        Ty::Error
    }
}
```

**Display format for function types:**

```text
(I64, Str) -> Bool
(I64) -> I64 uses [FileRead, NetConnect]
```

### 4.9 Subtyping

Spore primarily uses **equality-based** type compatibility via unification, with targeted subtyping for specific cases:

- `I64 ≠ F64` — no implicit numeric widening.
- `Named("UserId") ≠ Named("Str")` — newtypes are distinct.
- `Ty::Error` unifies with anything (error recovery only).
- `Ty::Hole(name)` unifies with anything (hole placeholder only).
- `Ty::Never` unifies with anything (`Never <: τ` for all `τ`).
- Width subtyping for anonymous records: `{ a: I64, b: Str, c: Bool } <: { a: I64, b: Str }`.
- Effect set subtyping: `C₁ ⊆ C₂ ⟹ Fn(ps, r, C₁) <: Fn(ps, r, C₂)` (a function needing fewer effects is more general).

### 4.10 Binary and unary operator typing

**Reading guide.** §3.1 fixes **default** literal widths (**`I64`**, **`F64`**). The first rules below state operator typing for those defaults explicitly. **Width metavariables** reuse the Summary: **ι** ∈ {`I8`, `I16`, `I32`, `I64`, `U8`, `U16`, `U32`, `U64`} and **φ** ∈ {`F32`, `F64`}. Family rules apply to every fixed width; defaults remain the special case **ι = `I64`**, **φ = `F64`** when no other constraint fixes a width.

**Arithmetic operators** (`+`, `-`, `*`, `/`, `%`) — default scalar widths (§3.1):

```text
Γ ⊢ e₁ ⇒ τ    Γ ⊢ e₂ ⇒ τ
τ ∈ {I64, F64}
────────────────────────────
Γ ⊢ e₁ ⊕ e₂ ⇒ τ
```

**Arithmetic — all fixed integer and float widths:**

```text
Γ ⊢ e₁ ⇒ ι    Γ ⊢ e₂ ⇒ ι    ⊕ ∈ {+, -, *, /, %}
────────────────────────────
Γ ⊢ e₁ ⊕ e₂ ⇒ ι

Γ ⊢ e₁ ⇒ φ    Γ ⊢ e₂ ⇒ φ    ⊕ ∈ {+, -, *, /, %}
────────────────────────────
Γ ⊢ e₁ ⊕ e₂ ⇒ φ
```

(Both operands unify to the **same** `Ty`; there is no implicit widening between widths—see §4.9.)

**String concatenation** (`+` only):

```text
Γ ⊢ e₁ ⇒ Str    Γ ⊢ e₂ ⇒ Str
────────────────────────────
Γ ⊢ e₁ + e₂ ⇒ Str
```

**Comparison operators** (`==`, `!=`, `<`, `<=`, `>`, `>=`):

```text
Γ ⊢ e₁ ⇒ τ    Γ ⊢ e₂ ⇒ τ
────────────────────────────
Γ ⊢ e₁ ⊗ e₂ ⇒ Bool
```

(Relational operators require comparable operands; the reference checker unifies the two operand types. For documentation-only emphasis, **numeric** comparisons are exactly the instances where `τ = ι` or `τ = φ`.)

**Boolean operators** (`&&`, `||`):

```text
Γ ⊢ e₁ ⇐ Bool    Γ ⊢ e₂ ⇐ Bool
──────────────────────────────────
Γ ⊢ e₁ ∧∨ e₂ ⇒ Bool
```

**Unary negation** (`-`) — default scalars:

```text
Γ ⊢ e ⇒ τ    τ ∈ {I64, F64}
───────────────────────────────
Γ ⊢ -e ⇒ τ
```

**Unary negation — all numeric widths:**

```text
Γ ⊢ e ⇒ τ    τ = ι  or  τ = φ
───────────────────────────────
Γ ⊢ -e ⇒ τ
```

**Bitwise operators** (surface: `&`, `|`, `^`, `<<`, `>>`, and unary `~`; integers only):

```text
Γ ⊢ e₁ ⇒ ι    Γ ⊢ e₂ ⇒ ι    ⊙ ∈ {&, |, ^, <<, >>}
────────────────────────────
Γ ⊢ e₁ ⊙ e₂ ⇒ ι

Γ ⊢ e ⇒ ι
──────────────
Γ ⊢ ~e ⇒ ι
```

**Logical not** (`!`):

```text
Γ ⊢ e ⇐ Bool
──────────────
Γ ⊢ !e ⇒ Bool
```

### 4.11 Refinement types — future vision

Refinement types are not yet implemented but are a planned extension organized into two levels.

#### L0 — Decidable predicates

L0 refinements are predicates the compiler can fully evaluate at compile time:

```spore
type Port = I64 when 1 <= self <= 65535
type Percentage = F64 when 0.0 <= self <= 100.0
type NonEmptyString = Str when self.len() > 0
```

The decidable predicate language includes:

- Numeric comparisons: `<`, `<=`, `==`, `!=`, `>=`, `>`
- Arithmetic on constants: `self + 1 <= 100`
- **Str** / collection length: `self.len() > 0`
- Boolean connectives: `&&`, `||`, `!`
- Const equality: `self == "production" || self == "staging"`

**L0 checking rule:**

```text
Γ ⊢ e ⇒ base_type
eval(predicate[self ↦ e]) = true
────────────────────────────────
Γ ⊢ e ⇐ base_type when predicate
```

When the compiler cannot statically evaluate the predicate (e.g., value comes from runtime input), it requires an explicit runtime check via control flow.

#### L1 — Abstract interpretation propagation

L1 uses flow-sensitive abstract interpretation to propagate refinement information:

```spore
fn process_port(raw: I64) -> Port ! InvalidPort {
    if raw < 1 || raw > 65535 {
        raise InvalidPort { value: raw }
    }
    // After the guard, the compiler knows: 1 <= raw <= 65535
    // raw is automatically narrowed to Port
    raw
}
```

The abstract domain tracks **interval constraints** on integer and float values. At each branch point, the domain is split:

- True branch: constraints from the condition added.
- False branch: negated constraints added.

L1 explicitly excludes: arbitrary quantifiers, aliasing analysis, heap reasoning, and SMT-level theorem proving. This keeps checking decidable and error messages predictable.

### 4.12 Trait resolution

#### Trait registry

Traits are registered in a `TraitRegistry` alongside the `TypeRegistry`. Each trait records:

- Trait name
- Supertrait requirements (e.g., `Ord: Eq`)
- Method signatures (name, parameter types, return type, EffectSet)
- Associated type declarations
- Default method implementations (if any)

#### Trait implementation checking

When an `impl Trait for Type` block is encountered:

1. Verify that all required methods are provided (or have defaults).
2. For each method, check that the signature matches the trait declaration (after substituting `Self` with the implementing type).
3. Type-check each method body against its declared signature.
4. Verify supertrait implementations exist.

```text
trait T { fn m(self, x: σ) -> τ }
impl T for S { fn m(self, x: σ') -> τ' { body } }
────────────────────────────────────────────────
require: σ' = σ[Self ↦ S] and τ' = τ[Self ↦ S]
check: Γ, self: S, x: σ' ⊢ body ⇐ τ'
```

#### Coherence checking

The compiler enforces the orphan rule at module registration time:

- `impl T for S` is allowed only if the current module defines `T` or `S`.
- Adapter declarations are scoped: `adapter S as T { ... }` is usable only where explicitly imported via `where adapter: S as T`.

### 4.13 Pattern matching exhaustiveness

The exhaustiveness checker operates on the `TypedHIR` after type inference. For each `match` expression:

1. Collect all variants of the matched enum type.
2. For each arm, compute the set of variants it covers (including nested patterns).
3. Compute the uncovered set = all variants − covered variants.
4. If uncovered set is non-empty and no wildcard arm exists, emit a compile error listing missing variants.

```text
match e : T where T is enum with variants [V₁, …, Vₙ]
arms cover variants S ⊆ {V₁, …, Vₙ}
S = {V₁, …, Vₙ}  ∨  wildcard arm present
─────────────────────────────────────────
match is exhaustive
```

Guards weaken exhaustiveness: when guards are present, the compiler conservatively requires a catch-all arm.

### 4.14 Const generic evaluation

Const generic arithmetic is evaluated at compile time during type checking. The compiler maintains a simple evaluator for type-level integer expressions:

```text
eval(N)           = N                    (literal)
eval(A + B)       = eval(A) + eval(B)    (addition)
eval(A * B)       = eval(A) * eval(B)    (multiplication)
eval(A - B)       = eval(A) - eval(B)    (subtraction)
eval(A / B)       = eval(A) / eval(B)    (division, B ≠ 0)
eval(min(A, B))   = min(eval(A), eval(B))
eval(max(A, B))   = max(eval(A), eval(B))
```

Division by zero and integer overflow in type-level arithmetic are compile-time errors.

When a const generic function is instantiated, the compiler substitutes concrete values and evaluates:

```text
concat_vec[I64, 3, 5](a, b) → Vec[I64, max: eval(3 + 5)] = Vec[I64, max: 8]
```

### 4.15 Error set typing

Error sets are tracked as part of function types. The `!` syntax represents a closed union of error types:

```text
Fn([σ₁, …, σₙ], τᵣ, C, E)    where E = {Err₁, …, Errₖ}
```

**Error propagation via `?`**:

```text
Γ ⊢ e ⇒ Fn([…], τ, C, E_callee)
canonicalize(E_callee) ⊆ canonicalize(E_caller)
──────────────────────────────────
Γ; E_caller ⊢ e(…)? ⇒ τ
```

If `canonicalize(E_callee) ⊄ canonicalize(E_caller)`, the checker emits:

```text
error: function may raise [Err1] which is not in the declared error set
```

**Canonical error union**: When multiple `?` calls appear in a function body,
the function's error set must be a superset of the canonical union of all
callees' error sets.

### 4.16 Never type in the type system

`Never` participates in the type system as follows:

1. **Unification**: `unify(τ, Never) = ok` and `unify(Never, τ) = ok` for all `τ`.
2. **If-else branches**: If one branch returns `Never`, the result type is the other branch's type.
3. **Match arms**: A `Never`-typed arm is compatible with all other arm types.
4. **Function return**: `fn f() -> Never` means `f` never returns normally.

```text
Γ ⊢ e_then ⇒ τ
Γ ⊢ e_else ⇒ Never
────────────────────
Γ ⊢ if cond { e_then } else { e_else } ⇒ τ
```

### 4.17 Recursive type validation

The compiler validates recursive types during registration:

1. Build a dependency graph of type definitions.
2. For each cycle in the graph, verify that at least one edge passes through an indirection type (`List`, `Option`, `Box`, etc.).
3. If a cycle has no indirection, emit an infinite-size error.

```text
struct A { field: B }
struct B { field: A }    // ERROR: infinite size (A → B → A with no indirection)

struct A { field: List[B] }
struct B { field: A }    // OK: List provides indirection
```

## Human experience impact

### Positive

- **Clear error messages.** Because types are nominal and simple, error messages can say "expected `Celsius`, got `Fahrenheit`" rather than showing structural type dumps.
- **Minimal annotation burden.** Only function signatures require full annotation; local variables and closures are inferred. Humans write types where they matter (API boundaries) and skip them where they don't (implementation details).
- **Predictable behavior.** No implicit conversions, no SFINAE, no surprising type-level computation. If it compiles, the types mean what they say.
- **Refinement types (future) catch bugs early.** `Port` being `I64 if 1 <= self <= 65535` means invalid values are caught at compile time, not at runtime.

### Negative

- **Explicit annotation requirement.** Requiring full function signatures is more annotation than TypeScript or Python. However, this is a deliberate trade-off — signatures are the gravity center for both humans and Agents.
- **Nominal strictness.** Newtypes like `Celsius ≠ F64` require explicit conversions. This prevents accidental misuse but adds ceremony for simple cases.

### Cognitive model

The mental model for Spore's type system is: **"Types are contracts. Write them on the outside, let the compiler figure out the inside."**

## Agent experience impact

### Type-directed synthesis

Rich type signatures give Agents strong guidance for code generation:

- Parameter types constrain what values are available.
- Return types constrain what the body must produce.
- EffectSet constrains which side-effectful functions may be called.
- Hole types (`Ty::Hole`) tell the Agent exactly what type to produce.

### Structured type information

The `Ty` enum and `TypeRegistry` are designed for programmatic access:

- `registry.functions` maps function names to `(param_types, return_type, cap_set)`.
- `registry.structs` maps struct names to field lists.
- `registry.types` maps enum names to variant lists.

Agents can query this registry to discover available functions, match types, and plan synthesis strategies.

### Error recovery

`Ty::Error` allows the checker to continue after errors, producing multiple diagnostics in a single pass. This is critical for Agents — a single check run reveals all type errors, not just the first one.

### Hole reporting

The checker feeds the shared typed-hole protocol defined in SEP-0005. In practice, `sporec holes FILE --json` returns a batch object with `holes` plus `dependency_graph`, and `sporec query-hole FILE ?name --json` returns one hole object with the same inferred type, scope, and candidate information. This structured output is the primary input for Agent hole-filling strategies.

## Structured representation / protocol impact

### Type representation in diagnostics

All types implement `Display` with a canonical format:

| Type | Display |
|---|---|
| `Ty::I32` (etc.) | `I32`, `I64`, … |
| `Ty::F64` (etc.) | `F64`, `F32`, … |
| `Ty::Bool` | `Bool` |
| `Ty::Str` | `Str` |
| `Ty::Unit` | `()` |
| `Ty::Never` | `Never` |
| `Ty::Tuple([τ₁, τ₂])` | `(...)` / tuple spelling used by printer |
| `Ty::Refined(τ, …)` | surface refinement form |
| `Ty::Named("Foo")` | `Foo` |
| `Ty::App("List", [I64])` | `List[I64]` |
| `Ty::Record([(x, I64), (y, F64)])` | `{ x: I64, y: F64 }` |
| `Ty::Fn([I64], Bool, {})` | `(I64) -> Bool` |
| `Ty::Fn([I64], Bool, {"Net"})` | `(I64) -> Bool uses [Net]` |
| `Ty::Var(3)` | `?T3` |
| `Ty::Hole("h1")` | `?h1` |
| `Ty::Error` | `<error>` |

### Snapshot hashes

Function signatures (parameter types, return type, error set, EffectSet, cost
bound, generic constraints) are included in snapshot hashes. Body changes and
`@allows` annotations are excluded. For error sets, the hash policy is
intentionally conservative: written surface spelling still participates even when
two clauses are canonically equivalent. This ensures:

- API-breaking changes require explicit `--permit`.
- Implementation refactoring does not break downstream consumers.

### Machine-readable output

Type diagnostics participate in the shared diagnostics protocol described in SEP-0006. This SEP relies on the canonical type rendering, stable codes, severities, and spans provided by that protocol rather than defining a competing JSON schema.

```json
{
  "code": "E0301",
  "severity": "error",
  "message": "type mismatch: expected `I64`, found `Str`",
  "primary_span": {
    "file": "main.sp",
    "range": {
      "start": { "line": 5, "col": 12 },
      "end": { "line": 5, "col": 18 }
    }
  }
}
```

## Diagnostics impact

### Error categories produced by the type checker

| Category | Example message |
|---|---|
| Type mismatch | `type mismatch in function 'add': expected 'I64', got 'Str'` |
| Undefined variable | `undefined variable 'x'` |
| Arity mismatch | `function 'add' expects 2 arguments, got 3` |
| Missing effect | `missing effects [NetConnect]: caller does not declare them` |
| Missing propagated error | `function may raise [ParseError] which is not in the declared error set` |
| Redundant error item | `redundant error item 'ParseFailure': already covered by 'config.errors.ParseError'` |
| Non-exhaustive match | `non-exhaustive match: missing variant 'Triangle'` |
| Cannot negate type | `cannot negate type 'Str'` |
| Cannot apply `!` | `cannot apply '!' to type 'I64'` |
| Unknown field | `struct 'Point' has no field 'z'` |

### Dual-channel diagnostics

Every diagnostic is emitted as human-readable and machine-readable projections over the shared diagnostic objects described in SEP-0006. For the type system, those projections must preserve:

- The **expected type** (from check mode / declared return type).
- The **actual type** (from synth mode / expression).
- The **context** (function name, expression location).
- **Suggestions** — functions in scope whose return type matches the expected type.

### Hole diagnostics

For each hole, the checker reports the type-system facts that feed the shared SEP-0005 hole object rather than inventing a second hole-specific schema in this SEP.

```text
Hole ?h1 in function `example`:
  expected type: I64
  available bindings: x: I64, y: Str
  suggested fills: compute_value, default_int
```

## Drawbacks

1. **Nominal rigidity.** The nominal-primary design means newtypes require explicit wrap/unwrap. This adds verbosity for simple delegation patterns. Anonymous records provide a structural escape hatch, but they cannot implement traits.

2. **EffectSet as BTreeSet\<String\>.** String-based effect names lack static verification at the `Ty` level — a misspelled effect name is only caught when matching against registered effects, not during type construction.

3. **No higher-kinded types.** GATs + associated types cover most use cases, but abstracting over container kinds generically (functor-map over any container) requires either code generation or per-container implementations.

4. **Refinement types are only partially implemented.** L0-style aliases (`alias Port = I64 when …`) work in the reference compiler, but the full refinement vision in later sections (flow-sensitive narrowing, transitive proof obligations) is not complete.

5. **Annotation overhead.** Requiring full function signatures is more annotation than TypeScript or Python. This is a deliberate trade-off — signatures are the gravity center for both humans and Agents.

## Alternatives considered

### Alternative 1: Structural typing as default (TypeScript / Go style)

**Rejected.** Structural typing makes effect safety impossible — two structurally identical types could accidentally satisfy each other's effect requirements. It also produces confusing error messages when two semantically different types happen to share the same shape.

**Decision:** Nominal-primary with anonymous structural records as an escape hatch.

### Alternative 2: Hindley–Milner global inference

**Rejected.** Full H-M inference infers function signatures, but this conflicts with Spore's "signatures are gravity centers" principle. Inferred signatures are:

- Not visible to Agents reading code.
- Unstable under refactoring (adding a statement can change the inferred type).
- Hard to explain when inference fails.

**Decision:** Bidirectional checking — signatures annotated, bodies inferred.

### Alternative 3: Higher-kinded types

**Rejected.** HKTs would allow abstracting over `Option`, `List`, `Result`, etc. generically. However:

- Effects replace the primary HKT use case (monad-based effect sequencing).
- GATs cover 80% of the remaining use cases.
- HKT error messages are notoriously difficult to understand.
- Can be added later as an opt-in extension without breaking changes.

**Decision:** No HKT. Use GATs + associated types for container abstraction.

### Alternative 4: SMT-backed refinement types (Liquid Haskell style)

**Rejected.** SMT solvers are:

- Unpredictable (slight code changes can cause timeouts).
- Inscrutable (error messages say "could not prove P" with no guidance).
- Heavy (Z3 is a large dependency).

**Decision:** L0 decidable predicates + L1 abstract interpretation. Covers practical needs (numeric bounds, null tracking, range narrowing) without solver unpredictability.

### Alternative 5: Effect system via monads or algebraic effects

**Rejected as primary mechanism.** Spore separates traits and effects instead of unifying them via monads or algebraic effects. This provides:

- Clear distinction between "what does this type support" (traits) and "what does this context require" (effects).
- Reuse of the trait resolver and coherence checker for type interfaces.
- Simpler mental model for users.

**Decision:** Traits ≠ Effects. `trait` defines type interfaces, `effect` defines external operations, `uses [Effect]` declares effect requirements.

### Alternative 6: Row-polymorphic effect sets

**Considered for future.** Making EffectSets row-polymorphic would allow:

```spore
fn apply[C](f: Fn(x: I64) -> I64 uses C, x: I64) -> I64 uses C
```

This is compatible with the current design but not yet implemented. The string-based `BTreeSet` representation would need to be extended with effect variables.

## Prior art

### Rust

Spore's type system is most directly influenced by Rust:

- Nominal types with trait bounds.
- Associated types and GATs.
- Sealed enums with exhaustive pattern matching.
- No implicit conversions.

**Differences from Rust:** No lifetime system (Spore currently targets Perceus-style reference counting with region optimization rather than a borrow checker), no borrow checker, effects replace `unsafe` blocks, refinement types replace some `debug_assert!` patterns.

### Haskell / GHC

- Bidirectional type inference with explicit signatures was pioneered in GHC's `OutsideIn(X)` solver.
- Type holes (`_` in GHC) directly inspired Spore's `?hole` syntax.
- Spore explicitly rejects HKT and typeclasses-as-module-system in favor of simpler nominal traits.

### Liquid Haskell

- Refinement types attached to base types.
- Spore adopts the refinement syntax (`alias Port = I64 when ...` / `type Port = I64 when ...`) but replaces the SMT backend with decidable predicates (L0) and abstract interpretation (L1).

### TypeScript

- Structural typing for anonymous records (Spore borrows this for the structural escape hatch).
- Spore rejects structural typing as the default due to effect safety concerns.

### Elm

- Elm-style error messages are the target for Spore's human-readable diagnostic channel.
- Elm's enforced exhaustive matching directly influenced Spore's sealed-enum design.

### Bidirectional type checking literature

- Pierce & Turner, "Local Type Inference" (2000).
- Dunfield & Krishnaswami, "Complete and Easy Bidirectional Typechecking for Higher-Rank Polymorphism" (2013).

Spore implements a simplified version: no higher-rank polymorphism, no impredicativity. Signatures provide the "check" direction; expressions provide the "synth" direction.

## Backward compatibility and migration

### This is the initial type system specification

Since this is the first formal type system specification (implemented by `sporec-typeck`), there is no older SEP to be backward-compatible with. The `Ty` enum in the reference compiler is the de facto baseline documented in §§3.1–4.1 above.

### Compatibility commitments

1. **Ty enum stability.** The variants `I8`…`U64`, `F32`, `F64`, `Bool`, `Str`, `Unit`, `Never`, `Tuple`, `Refined`, `Named`, `App`, `Record`, `Fn`, `Var`, `Hole`, `Error` are stable in the reference implementation. New variants may be added but existing variants will not be removed or renamed without a new SEP. (`Char` was removed from the language and toolchain in `spore` PR #113.)

2. **EffectSet representation.** `BTreeSet<String>` is the current representation. Future SEPs may introduce effect variables for row-polymorphic effects, but the concrete string-based API will remain supported.

3. **Two-pass checking.** The `register_item` → `check_fn` architecture is stable. Future passes (e.g., trait resolution, cost checking) will be added after these two, not replace them.

4. **Display format.** The canonical type display format (`I64`, `List[I64]`, `(I64) -> Bool uses [Net]`, `{ x: I64, y: F64 }`, etc.) is stable and may be relied upon by tools and diagnostics.

### Migration path for future features

| Feature | Migration strategy |
|---|---|
| Refinement types (L0) | `Ty::Refined` exists in `sporec-typeck`; extend semantics/predicate classes as needed |
| Const generics | Add `Ty::Const(value)` variant; extend `App` to accept const args |
| Row-polymorphic effects | Extend EffectSet with effect variables alongside concrete strings |

## Unresolved questions

1. **EffectSet in unification.** Currently, function type unification ignores EffectSets (the `_` in `Fn(p1, r1, _), Fn(p2, r2, _)`). Should EffectSets participate in unification, or remain checked separately? Separate checking is simpler but could miss effect mismatches in higher-order function arguments.

2. **Generic syntax: square brackets vs angle brackets.** The implemented `Ty::App` uses parenthesized syntax in the AST (`List[I64]`), but some spec examples use angle brackets (`List<T>`). This SEP uses square brackets as the intended syntax; a separate SEP should finalize the concrete syntax.

3. **Refinement type representation.** Where do refinement predicates live in the `Ty` enum? Options:
   - (a) `Ty::Refined(Box<Ty>, Predicate)` — a wrapper around any base type.
   - (b) Store refinements in the `TypeRegistry` alongside the base type, not in `Ty` itself.
   - (c) Treat refined types as named types (`Port = Named("Port")`) with predicates stored separately.

4. **Trait method type checking.** The two-pass architecture registers function signatures but does not yet handle trait method signatures, default methods, or `impl` blocks. How should these be integrated into `register_item` and `check_fn`? (See §4.12 for the specified approach.)

5. **Row-polymorphic effects.** Should effect sets support variables (e.g., `uses [C]` where `C` is an effect set variable)? This would enable generic higher-order functions that preserve their argument's effect requirements.

6. **Variance.** Generic type parameters need variance annotations (covariant, contravariant, invariant) for soundness when subtyping is introduced. Should variance be inferred or declared?

### Resolved questions

The following questions from earlier drafts are now resolved by this specification:

1. **Occurs check.** ✅ Resolved — the unifier includes an occurs check (§4.4). Cyclic substitutions like `Var(0) ↦ List[Var(0)]` are rejected.

2. **Never type semantics.** ✅ Resolved — `unify(τ, Never) = ok` for all `τ` (§4.16). Never is handled as a bottom type directly within the unifier.

3. **Error type representation.** ✅ Resolved — error sets are a component of
`Ty::Fn`, making it `Fn(params, ret, EffectSet, ErrorSet)` (§4.15). `?`
propagation uses canonical subset/union semantics, while signature hashing stays
conservative over the written error clause.
