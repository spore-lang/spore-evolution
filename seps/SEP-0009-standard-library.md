---
sep: 9
title: "SEP-0009: Standard Library Surface"
status: Draft
type: Standards Track
authors:
  - Spore Contributors
created: 2026-04-01
requires: [1, 2, 3, 4, 7, 8]
discussion: "https://github.com/spore-lang/spore-evolution/discussions"
pr: null
superseded_by: null
---

> **Executive Summary**: Defines the standard library surface for Spore — the set of built-in types, functions, traits, and error types that every Spore program can rely on. Organizes the stdlib into a layered prelude (always-available primitives), core modules (opt-in via import), and platform-provided I/O bindings. Every function carries effect requirements and cost annotations per SEP-0003 and SEP-0004.

# SEP-0009: Standard Library Surface

## Summary

This SEP specifies the standard library that ships with every Spore implementation. It defines:

1. **Prelude** — types, traits, and functions available without import
2. **Core modules** — standard modules available via `import std.*`
3. **Error types** — a unified error hierarchy
4. **Platform bindings** — how I/O functions connect to selected Platform package modules
5. **Cost contracts** — verified cost annotations for indexed stdlib functions

Shared operation names such as `map`, `len`, `unwrap`, `contains`, and
`from_list` are trait or inherent methods, not overloaded free functions.
Method resolution is Rust-like: the receiver type or type namespace selects the
implementation, and ambiguous cases use trait-qualified syntax.

The stdlib is deliberately small. Spore follows the principle that the standard library should provide exactly the types and functions needed to write idiomatic Spore code, with everything else available as packages.

The standard-library naming uses `std.*` for core modules and `spore.*` for
algebraic helper surfaces (for example, `spore.combine`, `spore.merge`,
`spore.order`, and `spore.laws`). No `std.algebra` surface is introduced.

## Motivation

Currently, SEPs 0001–0008 reference standard library items (e.g.,
`map`, `fold`, `Option[T]`, `Result[T, E]`, `List[T]`) without a
single authoritative specification. This creates several problems:

1. **Ambiguity**: Function signatures are mentioned inconsistently across SEPs
2. **Cost-contract ambiguity**: Dynamic APIs and indexed APIs need different cost-contract rules
3. **No error type hierarchy**: `IoError`, `HttpError`, `ParseError` are referenced but never defined
4. **FFI boundary unclear**: Which functions are implemented natively vs. in Spore is unspecified
5. **Agent tooling gap**: Agents cannot enumerate available functions or their contracts

## Guide-level explanation

### What's in the prelude?

Every Spore file implicitly has access to:

```spore
// Primitive types: I8..U64, F32, F64, Bool, Str, Unit, Never (see SEP-0002)

// Algebraic types
type Option[T] { Some(T), None }
type Result[T, E] { Ok(T), Err(E) }
type List[T] { Cons(T, List[T]), Nil }
type Ordering { Less, Equal, Greater }

// Index-admitted count
type Count[N: Index] = I64 when self >= 0
```

The prelude intentionally does **not** export duplicate free functions or
signature-union overloads. Shared names are trait or inherent methods:
`xs.map(f)`, `opt.map(f)`, `s.len()`, and `Map.from_list(pairs)` are distinct
method resolutions, not overloaded free functions.

### What needs an import?

Specialized modules require explicit imports:

```spore
import std.index       // Count helpers: add, span, ...
import std.array       // Array[T, N] and fixed-length operations
import std.vec         // Vec[T, max: N] and verified size-parametric operations
import std.list        // Dynamic List operations
import std.math        // f64_sqrt, f64_sin, i64_abs, f64_pow, ...
import std.string      // split, trim, join, contains, ...
import std.collections // Map, Set, Map.from_list, Set.from_list, ...
// future: import std.io  // stabilized platform-neutral I/O facade
import std.time        // DateTime, Duration, now(), ...
import std.json        // json_parse, json_to_string
```

### How do I/O functions work?

Manifest-backed projects import the selected Platform
package's modules directly. Those modules expose `foreign fn` declarations
with explicit `uses [...]` requirements.

```spore
import basic_cli.stdout
import basic_cli.cmd

fn main() -> () uses [Console, Exit] {
    println("hello")
    exit(0u8)
}
```

For `basic-cli`, the surface lives in modules such as
`basic_cli.stdout`, `basic_cli.stdin`, `basic_cli.file`, `basic_cli.env`, and
`basic_cli.cmd`.
A future `std.io` layer may wrap or re-export a common surface above those
Platform packages.

For declared effects in interpreter-style
execution, `perform Effect.operation(...)` falls back through registered host
handlers by the **qualified** `Effect.operation` key. Platform package
modules remain the primary application-facing contract.

## Reference-level explanation

### 4.1 Prelude types

The prelude is implicitly imported into every module. It contains:

#### Primitive types

| Type                   | Description               | Default                  | Size / notes |
| ---------------------- | ------------------------- | ------------------------ | ------------ |
| `I8`…`I64`, `U8`…`U64` | Fixed-width integers      | `0` for the chosen width | 1–8 bytes    |
| `F32`, `F64`           | IEEE-754 floats           | `0.0`                    | 4 or 8 bytes |
| `Bool`                 | Boolean                   | `false`                  | 1 byte       |
| `Str`                  | Immutable UTF-8 string    | `""`                     | Variable     |
| `Unit`                 | Zero-valued type          | `()`                     | 0 bytes      |
| `Never`                | Bottom type (uninhabited) | —                        | 0 bytes      |

**No `Char`.** Unicode scalars are represented as `Str` values (typically length 1). Character predicates and conversions live in `stdlib/char.sp` (`is_digit`, `char_to_int`, …). This matches the language specification.

**Literals.** In the reference type checker, unsuffixed integer literals default to **`I64`** and floating-point literals default to **`F64`**. Standard-library signatures use explicit fixed-width names; `Int` and `Float` are not standard aliases.

#### Algebraic and index-admitted types

Prelude **`List[T]`** is dynamic and unbounded. It is the canonical sequence
type for ordinary programs, but its runtime length is not a CostExpr variable.
Use `Count[N]`, `Array[T, N]`, or `Vec[T, max: N]` when a static Index must
participate in verified cost.

```spore
type Option[T] { Some(T), None }
type Result[T, E] { Ok(T), Err(E) }
type List[T] { Cons(T, List[T]), Nil }
type Ordering { Less, Equal, Greater }
type Count[N: Index] = I64 when self >= 0
```

### 4.2 Prelude traits and functions

The prelude does not export duplicate free functions. Similar operations use
trait or inherent methods:

- `opt.map(f)`, `res.map(f)`, `list.map(f)`, and `vec.map(f)` are method calls.
- `s.len()`, `list.len()`, `map.len()`, and `set.len()` are `Len` trait calls.
- `opt.unwrap()` and `res.unwrap()` are `Unwrap` trait calls.
- `Map.from_list(pairs)` and `Set.from_list(items)` are type-qualified
  associated functions.

If method resolution is ambiguous after type inference, the programmer uses
trait-qualified syntax. The standard library does not use `A | B` parameter
signatures to simulate overloads.

```spore
trait Mappable {
    type Item
    type Mapped[U]
    fn map[U](self, f: (Self.Item) -> U) -> Self.Mapped[U]
}

trait Len {
    fn len(self) -> I64
    fn is_empty(self) -> Bool { self.len() == 0 }
}

trait Unwrap {
    type Output
    fn unwrap(self) -> Self.Output ! PanicError
    fn unwrap_or(self, default: Self.Output) -> Self.Output
}

trait Contains[Needle] {
    fn contains(self, needle: Needle) -> Bool
}

impl[T] Mappable for Option[T] {
    type Item = T
    type Mapped[U] = Option[U]
    fn map[U](self, f: (T) -> U) -> Option[U] cost [cost(f), 0, 0, 0]
}

impl[T] Unwrap for Option[T] {
    type Output = T
    fn unwrap(self) -> T ! PanicError cost [1, 0, 0, 0]
    fn unwrap_or(self, default: T) -> T cost [1, 0, 0, 0]
}

impl[T] Option[T] {
    fn and_then[U](self, f: (T) -> Option[U]) -> Option[U] cost [cost(f), 0, 0, 0]
    fn is_some(self) -> Bool cost [1, 0, 0, 0]
    fn is_none(self) -> Bool cost [1, 0, 0, 0]
}

impl[T, E] Mappable for Result[T, E] {
    type Item = T
    type Mapped[U] = Result[U, E]
    fn map[U](self, f: (T) -> U) -> Result[U, E] cost [cost(f), 0, 0, 0]
}

impl[T, E] Unwrap for Result[T, E] {
    type Output = T
    fn unwrap(self) -> T ! PanicError cost [1, 0, 0, 0]
    fn unwrap_or(self, default: T) -> T cost [1, 0, 0, 0]
}

impl[T, E] Result[T, E] {
    fn map_err[F](self, f: (E) -> F) -> Result[T, F] cost [cost(f), 0, 0, 0]
    fn and_then[U](self, f: (T) -> Result[U, E]) -> Result[U, E] cost [cost(f), 0, 0, 0]
    fn is_ok(self) -> Bool cost [1, 0, 0, 0]
    fn is_err(self) -> Bool cost [1, 0, 0, 0]
}

fn to_string[A](value: A) -> Str where A: Display cost [1, 1, 0, 0]
fn to_debug_string[A](value: A) -> Str where A: Debug cost [1, 1, 0, 0]
```

Dynamic `List[T]` operations live in `std.list` rather than the prelude. They
are stable APIs, but they do not publish verified costs that depend on runtime
length. Use `std.vec` or `std.array` for statically indexed cost.

### 4.3 Core modules

#### `std.index`

```spore
fn count_zero() -> Count[0] cost [1, 0, 0, 0]
fn count_one() -> Count[1] cost [1, 0, 0, 0]
fn count_add[N: Index, M: Index](a: Count[N], b: Count[M]) -> Count[N + M] cost [1, 0, 0, 0]
fn count_mul[N: Index, M: Index](a: Count[N], b: Count[M]) -> Count[N * M] cost [1, 0, 0, 0]
fn count_max[N: Index, M: Index](a: Count[N], b: Count[M]) -> Count[max(N, M)] cost [1, 0, 0, 0]
fn count_min[N: Index, M: Index](a: Count[N], b: Count[M]) -> Count[min(N, M)] cost [1, 0, 0, 0]
fn count_span[Hi: Index, Lo: Index](hi: Count[Hi], lo: Count[Lo]) -> Count[span(Hi, Lo)] cost [1, 0, 0, 0]
fn count_to_i64[N: Index](count: Count[N]) -> I64 cost [1, 0, 0, 0]
```

#### `std.array` and `std.vec`

```spore
type Array[T, N: Index]
type Vec[T, max: N] where N: Index

impl[A, N: Index] Mappable for Array[A, N] {
    type Item = A
    type Mapped[B] = Array[B, N]
    fn map[B](self, f: (A) -> B) -> Array[B, N]
        cost [N * cost(f) + N, N, 0, 0]
}

impl[A, N: Index] Array[A, N] {
    fn fold[B](self, init: B, f: (B, A) -> B) -> B
        cost [N * cost(f), 0, 0, 0]
}

impl[A, N: Index] Mappable for Vec[A, max: N] {
    type Item = A
    type Mapped[B] = Vec[B, max: N]
    fn map[B](self, f: (A) -> B) -> Vec[B, max: N]
        cost [N * cost(f) + N, N, 0, 0]
}

impl[A, N: Index] Vec[A, max: N] {
    fn take[K: Index](self, count: Count[K]) -> Vec[A, max: min(N, K)]
        cost [min(N, K), min(N, K), 0, 0]

    fn concat[M: Index](self, other: Vec[A, max: M]) -> Vec[A, max: N + M]
        cost [N + M, N + M, 0, 0]
}

fn range_count[N: Index](start: I64, count: Count[N]) -> Vec[I64, max: N]
    cost [N, N, 0, 0]
```

#### `std.list`

```spore
impl[A] Mappable for List[A] {
    type Item = A
    type Mapped[B] = List[B]
    fn map[B](self, f: (A) -> B) -> List[B]
}

impl[A] Len for List[A] {
    fn len(self) -> I64
}

impl[A] Contains[A] for List[A] where A: Eq {
    fn contains(self, item: A) -> Bool
}

impl[A] List[A] {
    fn filter(self, p: (A) -> Bool) -> List[A]
    fn fold[B](self, init: B, f: (B, A) -> B) -> B
    fn each(self, f: (A) -> Unit) -> Unit
    fn flat_map[B](self, f: (A) -> List[B]) -> List[B]
    fn zip[B](self, other: List[B]) -> List[(A, B)]
    fn enumerate(self) -> List[(I64, A)]
    fn head(self) -> Option[A]
    fn tail(self) -> Option[List[A]]
    fn last(self) -> Option[A]
    fn find(self, p: (A) -> Bool) -> Option[A]
    fn any(self, p: (A) -> Bool) -> Bool
    fn all(self, p: (A) -> Bool) -> Bool
    fn append(self, item: A) -> List[A]
    fn prepend(self, item: A) -> List[A]
    fn concat(self, other: List[A]) -> List[A]
    fn reverse(self) -> List[A]
    fn take(self, n: I64) -> List[A]
    fn drop(self, n: I64) -> List[A]
    fn sort(self) -> List[A] where A: Ord
    fn sort_by(self, cmp: (A, A) -> Ordering) -> List[A]
}

impl List[I64] {
    fn range(start: I64, end: I64) -> List[I64]
}
```

#### `std.math`

```spore
fn i64_abs(x: I64) -> I64 cost [1, 0, 0, 0]
fn f64_abs(x: F64) -> F64 cost [1, 0, 0, 0]
fn i64_min(a: I64, b: I64) -> I64 cost [1, 0, 0, 0]
fn i64_max(a: I64, b: I64) -> I64 cost [1, 0, 0, 0]
fn i64_clamp(x: I64, lo: I64, hi: I64) -> I64 cost [1, 0, 0, 0]
fn f64_sqrt(x: F64) -> F64 cost [1, 0, 0, 0]
fn f64_pow(base: F64, exp: F64) -> F64 cost [1, 0, 0, 0]
fn f64_log(x: F64) -> F64 cost [1, 0, 0, 0]
fn f64_log2(x: F64) -> F64 cost [1, 0, 0, 0]
fn f64_log10(x: F64) -> F64 cost [1, 0, 0, 0]
fn f64_exp(x: F64) -> F64 cost [1, 0, 0, 0]
fn f64_sin(x: F64) -> F64 cost [1, 0, 0, 0]
fn f64_cos(x: F64) -> F64 cost [1, 0, 0, 0]
fn f64_tan(x: F64) -> F64 cost [1, 0, 0, 0]
fn f64_asin(x: F64) -> F64 cost [1, 0, 0, 0]
fn f64_acos(x: F64) -> F64 cost [1, 0, 0, 0]
fn f64_atan(x: F64) -> F64 cost [1, 0, 0, 0]
fn f64_atan2(y: F64, x: F64) -> F64 cost [1, 0, 0, 0]
fn f64_floor(x: F64) -> I64 cost [1, 0, 0, 0]
fn f64_ceil(x: F64) -> I64 cost [1, 0, 0, 0]
fn f64_round(x: F64) -> I64 cost [1, 0, 0, 0]
fn f64_truncate(x: F64) -> I64 cost [1, 0, 0, 0]
```

#### `std.string`

```spore
impl Len for Str {
    fn len(self) -> I64
}

impl Contains[Str] for Str {
    fn contains(self, pattern: Str) -> Bool
}

impl Str {
    fn char_at(self, index: I64) -> Option[Str]
    fn substring(self, start: I64, end: I64) -> Str
    fn substring_count[N: Index](self, start: I64, count: Count[N]) -> Str
        cost [N, N, 0, 0]
    fn concat(self, other: Str) -> Str
    fn join(parts: List[Str], sep: Str) -> Str
    fn split(self, sep: Str) -> List[Str]
    fn trim(self) -> Str
    fn trim_start(self) -> Str
    fn trim_end(self) -> Str
    fn to_upper(self) -> Str
    fn to_lower(self) -> Str
    fn starts_with(self, prefix: Str) -> Bool
    fn ends_with(self, suffix: Str) -> Bool
    fn replace(self, from: Str, to: Str) -> Str
    fn parse_i64(self) -> Result[I64, ParseError]
    fn parse_f64(self) -> Result[F64, ParseError]
}
```

#### `std.collections`

```spore
type Map[K, V]  // Immutable hash map (K must implement Hash + Eq)
type Set[T]     // Immutable hash set (T must implement Hash + Eq)

impl[K, V] Len for Map[K, V] {
    fn len(self) -> I64
}

impl[K, V] Map[K, V] where K: Hash + Eq {
    fn empty() -> Map[K, V] cost [1, 0, 0, 0]
    fn from_list(pairs: List[(K, V)]) -> Map[K, V]
    fn get(self, key: K) -> Option[V] cost [1, 0, 0, 0]
    fn insert(self, key: K, value: V) -> Map[K, V]
    fn remove(self, key: K) -> Map[K, V]
    fn contains_key(self, key: K) -> Bool cost [1, 0, 0, 0]
    fn keys(self) -> List[K]
    fn values(self) -> List[V]
    fn entries(self) -> List[(K, V)]
}

impl[T] Len for Set[T] {
    fn len(self) -> I64
}

impl[T] Contains[T] for Set[T] where T: Hash + Eq {
    fn contains(self, item: T) -> Bool cost [1, 0, 0, 0]
}

impl[T] Set[T] where T: Hash + Eq {
    fn empty() -> Set[T] cost [1, 0, 0, 0]
    fn from_list(items: List[T]) -> Set[T]
    fn add(self, item: T) -> Set[T]
    fn remove(self, item: T) -> Set[T]
    fn union(self, other: Set[T]) -> Set[T]
    fn intersection(self, other: Set[T]) -> Set[T]
    fn difference(self, other: Set[T]) -> Set[T]
    fn to_list(self) -> List[T]
}
```

#### `std.io` (platform I/O)

`std.io` is a future standardization layer. Manifest-backed projects import Platform package modules directly. For `basic-cli`, the platform modules are:

| Module             | Example operations                                    | Required effects        |
| ------------------ | ----------------------------------------------------- | ----------------------- |
| `basic_cli.stdout` | `print`, `println`, `eprint`, `eprintln`              | `Console`               |
| `basic_cli.stdin`  | `read_line`                                           | `Console`               |
| `basic_cli.file`   | `file_read`, `file_write`, `file_exists`, `file_stat` | `FileRead`, `FileWrite` |
| `basic_cli.dir`    | `dir_list`, `dir_mkdir`                               | `FileRead`, `FileWrite` |
| `basic_cli.env`    | `env_get`, `env_set`                                  | `Env`                   |
| `basic_cli.cmd`    | `process_run`, `process_run_status`, `exit`           | `Spawn`, `Exit`         |

```spore
pub foreign fn process_run(cmd: Str, args: List[Str]) -> Str ! ExecError uses [Spawn]
pub foreign fn process_run_status(cmd: Str, args: List[Str]) -> Option[U8] ! ExecError uses [Spawn]
pub foreign fn exit(code: U8) -> Never uses [Exit]
```

`basic_cli.cmd.exit(code)` is the explicit process-termination
surface. In project mode it works together with SEP-0008's startup contract
(`main() -> ()`), and the runtime converts the resulting structured outcome into
a host exit status.

A future `std.io` module may standardize a portable wrapper above these Platform
packages. Until that lands, signatures in this section should be read as future
design sketches rather than as the current contract.

#### `std.time` (platform-provided)

```spore
type DateTime   // Opaque timestamp
type Duration   // Time interval

foreign fn now() -> DateTime
    uses [Clock]
    cost [1, 0, 1, 0]

foreign fn elapsed(start: DateTime) -> Duration
    uses [Clock]
    cost [1, 0, 1, 0]

fn duration_ms(d: Duration) -> I64
    cost [1, 0, 0, 0]

fn duration_secs(d: Duration) -> F64
    cost [1, 0, 0, 0]

foreign fn sleep(ms: I64) -> Unit
    uses [Clock]
    cost @unbounded
```

#### `std.json`

```spore
type JsonValue {
    JsonNull,
    JsonBool(Bool),
    JsonInt(I64),
    JsonFloat(F64),
    JsonString(Str),
    JsonArray(List[JsonValue]),
    JsonObject(Map[Str, JsonValue]),
}

fn json_parse(s: Str) -> Result[JsonValue, ParseError]

fn json_to_string[T](value: T) -> Str
    where T: Serialize

fn json_from_string[T](s: Str) -> Result[T, ParseError]
    where T: Deserialize
```

These JSON APIs operate on dynamic `Str` and dynamic serialized values, so this
SEP does not publish verified `cost [...]` clauses for them. Indexed wrappers
may be added later if a platform needs static payload-size budgets.

#### `std.random` (platform-provided)

```spore
foreign fn random_float() -> F64
    uses [Random]
    cost [1, 0, 1, 0]

foreign fn random_int(min: I64, max: I64) -> I64
    uses [Random]
    cost [1, 0, 1, 0]

foreign fn uuid() -> Str
    uses [Random]
    cost [1, 16, 1, 0]

fn random_shuffle[A](list: List[A]) -> List[A]
    uses [Random]

fn random_sample[A](list: List[A]) -> Option[A]
    uses [Random]
    cost [1, 0, 1, 0]
```

### 4.4 Error type hierarchy

All stdlib errors conform to a base trait:

```spore
trait Error[T] {
    fn message(self: T) -> Str
}
```

The standard error types:

```spore
type PanicError { Panic(Str) }

type IoError {
    NotFound(Str),
    PermissionDenied(Str),
    AlreadyExists(Str),
    Other(Str),
}

type HttpError {
    ConnectionFailed(Str),
    Timeout(Str),
    StatusError(U16, Str),
    Other(Str),
}

type ParseError {
    InvalidFormat(Str),
    UnexpectedToken(Str, I64),
    Other(Str),
}

type JsonError {
    InvalidJson(Str, I64),
    TypeMismatch(Str),
    MissingField(Str),
}
```

All error types implement `Error`, `Display`, and `Debug`.

### 4.5 Compiler-known traits

These 13 traits have special compiler support (SEP-0002). The stdlib provides their definitions:

| Trait         | Methods                                                    | Derivable | Description               |
| ------------- | ---------------------------------------------------------- | --------- | ------------------------- |
| `Eq`          | `eq(self, other) -> Bool`                                  | ✅        | Equality comparison       |
| `Ord`         | `compare(self, other) -> Ordering`                         | ✅        | Total ordering            |
| `Clone`       | `clone(self) -> Self`                                      | ✅        | Deep copy                 |
| `Display`     | `display(self) -> Str`                                     | ❌        | Human-readable formatting |
| `Debug`       | `debug(self) -> Str`                                       | ✅        | Debug formatting          |
| `Hash`        | `hash(self) -> U64`                                        | ✅        | Hash computation          |
| `Default`     | `default() -> Self`                                        | ✅        | Default value             |
| `Serialize`   | `serialize(self) -> List[U8]`                              | ✅        | Byte serialization        |
| `Deserialize` | `deserialize(bytes: List[U8]) -> Result[Self, ParseError]` | ✅        | Byte deserialization      |
| `Add`         | `add(self, other) -> Self`                                 | ❌        | `+` operator              |
| `Sub`         | `sub(self, other) -> Self`                                 | ❌        | `-` operator              |
| `Mul`         | `mul(self, other) -> Self`                                 | ❌        | `*` operator              |
| `Div`         | `div(self, other) -> Self`                                 | ❌        | `/` operator              |

### 4.6 Platform binding architecture

The platform-backed I/O stack looks like this:

```text
┌──────────────────────────────────────────────┐
│ User Code                                    │
│ fn main() -> () uses [Console, Exit] {       │
│   println("done")                            │
│   exit(0u8)                                  │
│ }                                            │
├──────────────────────────────────────────────┤
│ Platform package modules                     │
│ basic_cli.stdout / basic_cli.stdin /         │
│ basic_cli.file / basic_cli.env /             │
│ basic_cli.cmd                                │
├──────────────────────────────────────────────┤
│ Selected Platform contract + metadata        │
│ [project].platform = "basic-cli"             │
│ startup-contract = "main"                    │
│ adapter-function = "main_for_host"           │
│ handled-effects = [..., "Exit"]              │
├──────────────────────────────────────────────┤
│ Native Runtime (Rust/C/host embedding)       │
└──────────────────────────────────────────────┘
```

Key properties:

1. **User code** imports Platform package modules directly today.
2. **Each foreign surface** declares explicit effect requirements.
3. **The selected Platform package** owns startup contracts and handled-effect metadata.
4. **Some operations** may propagate structured runtime outcomes before host conversion (for example `Exit` in project mode).
5. **Future stdlib wrappers** may layer above this.

### 4.7 Cost expression inputs

The cost annotation language (SEP-0004) does not call ordinary stdlib functions
inside `cost [...]`. Verified costs mention only Index parameters and
`cost(f)` summaries:

| Source            | Example                                  | Notes                                             |
| ----------------- | ---------------------------------------- | ------------------------------------------------- |
| Index parameter   | `N: Index`                               | Compile-time non-negative size symbol             |
| Indexed count     | `Count[N]`                               | Runtime count whose static Index is `N`           |
| Indexed container | `Array[T, N]`, `Vec[T, max: N]`          | Exposes `N` to CostExpr                           |
| Index operation   | `max(N, M)`, `min(N, M)`, `span(Hi, Lo)` | Pure IndexExpr, not runtime function calls        |
| Function summary  | `cost(f)`                                | Substituted when `f` is concrete at the call site |

Dynamic methods such as `list.len()`, `s.len()`, `map.len()`, or `set.len()`
return runtime integers. They are useful program APIs, but they are not
CostExpr variables.

## Human experience impact

The stdlib is designed for progressive discovery:

1. **Prelude is small**: Only essential types and iteration primitives — no import ceremony for basic programs
2. **Module names are predictable**: imports like `std.math`, `std.string`, and `std.collections` follow standard conventions
3. **Cost annotations are readable**: four-slot forms like `cost [N * cost(f) + N, N, 0, 0]` stay copy-pasteable
4. **Error types are descriptive**: Enum variants like `NotFound(Str)` carry context
5. **No hidden effects**: Every I/O function explicitly declares its effect requirements

## Agent experience impact

Agents benefit from:

1. **Complete enumeration**: All stdlib functions and methods are listed with signatures, enabling auto-completion
2. **Cost contracts**: Agents can reason about algorithmic complexity when filling holes
3. **Effect requirements**: Agents can verify that generated code satisfies effect constraints
4. **Structured errors**: Error type hierarchy enables pattern-matching on failure modes
5. **JSON protocol**: `std.json` provides the serialization layer for hole protocol (SEP-0005)

## Structured representation / protocol impact

The stdlib is represented in the module system as:

```json
{
  "module": "std.prelude",
  "methods": [
    {
      "owner": "Vec[A, max: N]",
      "trait": "Mappable",
      "name": "map",
      "type_params": ["A", "B", "N: Index"],
      "params": [
        { "name": "self", "type": "Vec[A, max: N]" },
        { "name": "f", "type": "(A) -> B" }
      ],
      "return_type": "Vec[B, max: N]",
      "cost": "N * cost(f) + N",
      "effects": []
    }
  ],
  "types": [
    { "name": "Option", "params": ["T"], "variants": ["Some(T)", "None"] }
  ]
}
```

This structured representation enables:

- IDE auto-complete with full type information
- Agent enumeration of available functions
- Cost analysis tool integration
- Documentation generation

## Diagnostics impact

New diagnostic codes for stdlib-related errors:

| Code    | Category   | Message                                |
| ------- | ---------- | -------------------------------------- |
| `E0018` | Type error | stdlib function applied to wrong type  |
| `E0019` | Type error | missing trait bound for stdlib generic |
| `W0001` | Warning    | unused stdlib import                   |
| `W0002` | Warning    | deprecated stdlib function             |

## Drawbacks

1. **Larger language surface**: More functions to learn and document
2. **Stability commitment**: Once standardized, stdlib changes require backward compatibility
3. **Platform burden**: Every platform must implement all `foreign fn` declarations
4. **Cost annotation maintenance**: Cost contracts must be verified against implementations

## Alternatives considered

### Minimal stdlib (only primitives)

Rejected. Without at least `Option`, `Result`, and `List`, idiomatic Spore code requires third-party packages for basic operations, hurting ergonomics and fragmenting the ecosystem.

### Batteries-included stdlib (Python-style)

Rejected. A large stdlib creates maintenance burden and version coupling. Spore's content-addressed package system (SEP-0008) makes third-party packages cheap to depend on.

### No foreign fn (pure Spore stdlib)

Rejected. I/O operations cannot be expressed in pure Spore. The designed
mechanism is Platform-owned package modules plus the selected Platform contract
boundary (SEP-0008).

## Prior art

| Language    | Stdlib approach         | Comparison                                                   |
| ----------- | ----------------------- | ------------------------------------------------------------ |
| **Rust**    | `std` + `core` (no-std) | Similar layered approach; Spore's is smaller                 |
| **Roc**     | Platform-provided I/O   | Direct inspiration for Spore's platform model                |
| **Haskell** | `Prelude` + `base`      | Similar prelude concept; Spore avoids Haskell's large `base` |
| **Go**      | Batteries-included      | Larger than Spore's approach                                 |
| **Elm**     | Small core + packages   | Similar philosophy; Spore adds cost annotations              |

## Backward compatibility and migration

This is a new specification — no backward compatibility concerns. However:

- Future changes to prelude types must go through the SEP process
- Deprecation of stdlib functions requires at least one release cycle with warnings
- New stdlib modules can be added without breaking changes

## Unresolved questions

1. **Mutable state API**: Should `Ref[T]` be in the prelude or `std.state`? Currently referenced in SEP-0001 but not fully specified here.

2. **Concurrency primitives**: `Task[T]`, `Channel[T]`, and `select` are defined in SEP-0007 — should they be re-exported via `std.concurrent` or remain as language primitives?

3. **String encoding**: Should `Str` expose byte-level access, or only scalar-oriented indexing? Current spec assumes UTF-8; there is no `Char` type (length-1 `Str` values instead).

4. **Iterator protocol**: Should there be a lazy `Iterator[T]` trait instead of materializing `List[T]` for all operations? This would change cost signatures significantly.

5. **Error recovery**: How should `PanicError` interact with the effect system? Should `panic` require an effect?

6. **FFI type mapping**: How do Spore types map to Rust/C types across the FFI boundary? (e.g., `I64` ↔ `i64`, `Str` ↔ UTF-8 buffer)

### Resolved questions

1. **Numeric tower**: Resolved by SEP-0002 and SEP-0001. The language surface
   uses fixed-width numeric types (`I8` through `U64`, plus `F32` and `F64`),
   and stdlib APIs should choose explicit widths at each boundary rather than
   relying on abstract scalar aliases.
