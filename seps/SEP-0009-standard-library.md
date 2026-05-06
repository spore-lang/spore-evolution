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

1. **Prelude** — types and functions available without import
2. **Core modules** — standard modules available via `import std.*`
3. **Error types** — a unified error hierarchy
4. **Platform bindings** — how I/O functions connect to selected Platform package modules
5. **Cost contracts** — cost annotations for all stdlib functions

The stdlib is deliberately small. Spore follows the principle that the standard library should provide exactly the types and functions needed to write idiomatic Spore code, with everything else available as packages.

> **Target-surface note**: This SEP still contains historical `std.*` examples
> in places. For the approved compositional-semantics wave, the engineering-
> facing helper naming is expected to use `spore.combine`, `spore.merge`,
> `spore.order`, and `spore.laws`, and explicitly does **not** introduce a
> user-facing `std.algebra` surface.

## Motivation

Currently, SEPs 0001–0008 reference standard library items (e.g., `map`, `fold`, `Option[T]`, `Result[T, E]`, `List[T]`) without a single authoritative specification. This creates several problems:

1. **Ambiguity**: Function signatures are mentioned inconsistently across SEPs
2. **Missing cost contracts**: Most stdlib functions lack formal cost annotations
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

// Core iteration (higher-order functions)
fn map[A, B](list: List[A], f: (A) -> B) -> List[B]
fn filter[A](list: List[A], p: (A) -> Bool) -> List[A]
fn fold[A, B](list: List[A], init: B, f: (B, A) -> B) -> B
fn each[A](list: List[A], f: (A) -> Unit) -> Unit
```

### What needs an import?

Specialized modules require explicit imports:

```spore
import std.math       // sqrt, sin, cos, abs, pow, ...
import std.string     // split, trim, join, contains, ...
import std.collections // Map, Set, sorted, grouped, ...
// future: import std.io  // stabilized platform-neutral I/O facade
import std.time       // DateTime, Duration, now(), ...
import std.json       // parse_json, to_json
```

### How do I/O functions work?

The current implementation does **not** yet ship a stabilized `std.io`
abstraction layer. Manifest-backed projects import the selected Platform
package's modules directly, and those modules expose `foreign fn` declarations
with explicit `uses [...]` requirements.

```spore
import basic_cli.stdout
import basic_cli.cmd

fn main() -> () uses [Console, Exit] {
    println("hello")
    exit(0u8)
}
```

For `basic-cli`, the shipped surface currently lives in modules such as
`basic_cli.stdout`, `basic_cli.stdin`, `basic_cli.file`, `basic_cli.env`, and
`basic_cli.cmd`.
A future `std.io` layer may wrap or re-export a common surface above those
Platform packages, but that is not today's contract.

There is also a narrower runtime path for declared effects in interpreter-style
execution: `perform Effect.operation(...)` falls back through registered host
handlers by the **qualified** `Effect.operation` key. Today that support is
explicit rather than generic (for example, the CLI runtime supports
`Console.print`, `Console.println`, and `Console.read_line`). Platform package
modules remain the main shipped application-facing contract.

## Reference-level explanation

### 4.1 Prelude types

The prelude is implicitly imported into every module. It contains:

#### Primitive types

| Type | Description | Default | Size / notes |
|------|-------------|---------|----------------|
| `I8`…`I64`, `U8`…`U64` | Fixed-width integers | `0` for the chosen width | 1–8 bytes |
| `F32`, `F64` | IEEE-754 floats | `0.0` | 4 or 8 bytes |
| `Bool` | Boolean | `false` | 1 byte |
| `Str` | Immutable UTF-8 string | `""` | Variable |
| `Unit` | Zero-valued type | `()` | 0 bytes |
| `Never` | Bottom type (uninhabited) | — | 0 bytes |

**No `Char`.** Unicode scalars are represented as `Str` values (typically length 1). Character predicates and conversions live in `stdlib/char.sp` (`is_digit`, `char_to_int`, …). This matches `spore` PR #113.

**Literals.** In the reference type checker, unsuffixed integer literals default to **`I64`** and floating-point literals default to **`F64`**. Standard-library signatures use explicit fixed-width names; `Int` and `Float` are not standard aliases.

#### Algebraic types

Prelude **`List[T]`** is always **unbounded** and is the canonical sequence type. **`Vec[T, max: N]`** exists for the minority of APIs that require a compile-time `max` in the type (SEP-0002); omit it unless those generics truly buy you something `List` + `cost`/refinements cannot.

```spore
type Option[T] {
    Some(T),
    None,
}

type Result[T, E] {
    Ok(T),
    Err(E),
}

type List[T] {
    Cons(T, List[T]),
    Nil,
}

type Ordering { Less, Equal, Greater }
```

### 4.2 Prelude functions

#### Option[T] methods

```spore
fn unwrap[T](opt: Option[T]) -> T
    ! PanicError
    cost [1, 0, 0, 1]

fn unwrap_or[T](opt: Option[T], default: T) -> T
    cost [1, 0, 0, 1]

fn map[T, U](opt: Option[T], f: (T) -> U) -> Option[U]
    cost [cost(f), 0, 0, 1]

fn and_then[T, U](opt: Option[T], f: (T) -> Option[U]) -> Option[U]
    cost [cost(f), 0, 0, 1]

fn is_some[T](opt: Option[T]) -> Bool
    cost [1, 0, 0, 1]

fn is_none[T](opt: Option[T]) -> Bool
    cost [1, 0, 0, 1]
```

#### Result[T, E] methods

```spore
fn unwrap[T, E](res: Result[T, E]) -> T
    ! PanicError
    cost [1, 0, 0, 1]

fn unwrap_or[T, E](res: Result[T, E], default: T) -> T
    cost [1, 0, 0, 1]

fn map[T, U, E](res: Result[T, E], f: (T) -> U) -> Result[U, E]
    cost [cost(f), 0, 0, 1]

fn map_err[T, E, F](res: Result[T, E], f: (E) -> F) -> Result[T, F]
    cost [cost(f), 0, 0, 1]

fn and_then[T, U, E](res: Result[T, E], f: (T) -> Result[U, E]) -> Result[U, E]
    cost [cost(f), 0, 0, 1]

fn is_ok[T, E](res: Result[T, E]) -> Bool
    cost [1, 0, 0, 1]

fn is_err[T, E](res: Result[T, E]) -> Bool
    cost [1, 0, 0, 1]
```

#### List iteration (core HOFs)

These are the **primary iteration primitives** in Spore (no loops — SEP-0001):

```spore
fn map[A, B](list: List[A], f: (A) -> B) -> List[B]
    cost [len(list) * cost(f) + len(list), len(list), 0, 1]

fn filter[A](list: List[A], p: (A) -> Bool) -> List[A]
    cost [len(list) * cost(p) + len(list), len(list), 0, 1]

fn fold[A, B](list: List[A], init: B, f: (B, A) -> B) -> B
    cost [len(list) * cost(f), 0, 0, 1]

fn each[A](list: List[A], f: (A) -> Unit) -> Unit
    cost [len(list) * cost(f), 0, 0, 1]

fn flat_map[A, B](list: List[A], f: (A) -> List[B]) -> List[B]
    cost [len(list) * cost(f) + total_output_len, total_output_len, 0, 1]

fn zip[A, B](a: List[A], b: List[B]) -> List[(A, B)]
    cost [min(len(a), len(b)), min(len(a), len(b)), 0, 1]

fn enumerate[A](list: List[A]) -> List[(I64, A)]
    cost [len(list), len(list), 0, 1]
```

#### List query functions

```spore
fn len[A](list: List[A]) -> I64
    cost [1, 0, 0, 1]

fn is_empty[A](list: List[A]) -> Bool
    cost [1, 0, 0, 1]

fn head[A](list: List[A]) -> Option[A]
    cost [1, 0, 0, 1]

fn tail[A](list: List[A]) -> Option[List[A]]
    cost [1, 0, 0, 1]

fn last[A](list: List[A]) -> Option[A]
    cost [len(list), 0, 0, 1]

fn contains[A](list: List[A], item: A) -> Bool
    where A: Eq
    cost [len(list), 0, 0, 1]

fn find[A](list: List[A], p: (A) -> Bool) -> Option[A]
    cost [len(list) * cost(p), 0, 0, 1]

fn any[A](list: List[A], p: (A) -> Bool) -> Bool
    cost [len(list) * cost(p), 0, 0, 1]

fn all[A](list: List[A], p: (A) -> Bool) -> Bool
    cost [len(list) * cost(p), 0, 0, 1]
```

#### List construction functions

```spore
fn append[A](list: List[A], item: A) -> List[A]
    cost [len(list), len(list), 0, 1]

fn prepend[A](item: A, list: List[A]) -> List[A]
    cost [1, 1, 0, 1]

fn concat[A](a: List[A], b: List[A]) -> List[A]
    cost [len(a), len(a) + len(b), 0, 1]

fn reverse[A](list: List[A]) -> List[A]
    cost [len(list), len(list), 0, 1]

fn take[A](list: List[A], n: I64) -> List[A]
    cost [n, n, 0, 1]

fn drop[A](list: List[A], n: I64) -> List[A]
    cost [n, len(list), 0, 1]

fn range(start: I64, end: I64) -> List[I64]
    cost [end - start, end - start, 0, 1]
```

#### Sorting

```spore
fn sort[A](list: List[A]) -> List[A]
    where A: Ord
    cost [len(list) * log(len(list)), len(list), 0, 1]

fn sort_by[A](list: List[A], cmp: (A, A) -> Ordering) -> List[A]
    cost [len(list) * log(len(list)) * cost(cmp), len(list), 0, 1]
```

#### Conversion and display

```spore
fn to_string[A](value: A) -> Str
    where A: Display
    cost [1, 1, 0, 1]

fn debug[A](value: A) -> Str
    where A: Debug
    cost [1, 1, 0, 1]
```

### 4.3 Core modules

#### `std.math`

```spore
fn abs(x: I64) -> I64                 cost [1, 0, 0, 1]
fn abs_float(x: F64) -> F64           cost [1, 0, 0, 1]
fn min(a: I64, b: I64) -> I64         cost [1, 0, 0, 1]
fn max(a: I64, b: I64) -> I64         cost [1, 0, 0, 1]
fn clamp(x: I64, lo: I64, hi: I64) -> I64
    cost [1, 0, 0, 1]

// Floating-point math
fn sqrt(x: F64) -> F64                cost [1, 0, 0, 1]
fn pow(base: F64, exp: F64) -> F64    cost [1, 0, 0, 1]
fn log(x: F64) -> F64                 cost [1, 0, 0, 1]
fn log2(x: F64) -> F64                cost [1, 0, 0, 1]
fn log10(x: F64) -> F64               cost [1, 0, 0, 1]
fn exp(x: F64) -> F64                 cost [1, 0, 0, 1]

// Trigonometric
fn sin(x: F64) -> F64                 cost [1, 0, 0, 1]
fn cos(x: F64) -> F64                 cost [1, 0, 0, 1]
fn tan(x: F64) -> F64                 cost [1, 0, 0, 1]
fn asin(x: F64) -> F64                cost [1, 0, 0, 1]
fn acos(x: F64) -> F64                cost [1, 0, 0, 1]
fn atan(x: F64) -> F64                cost [1, 0, 0, 1]
fn atan2(y: F64, x: F64) -> F64       cost [1, 0, 0, 1]

// Rounding
fn floor(x: F64) -> I64                cost [1, 0, 0, 1]
fn ceil(x: F64) -> I64                 cost [1, 0, 0, 1]
fn round(x: F64) -> I64                cost [1, 0, 0, 1]
fn truncate(x: F64) -> I64             cost [1, 0, 0, 1]

// Constants
let pi: F64 = 3.14159265358979323846
let e: F64 = 2.71828182845904523536
let infinity: F64
let neg_infinity: F64
let nan: F64
```

#### `std.string`

```spore
fn length(s: Str) -> I64                    cost [1, 0, 0, 1]
fn is_empty(s: Str) -> Bool                 cost [1, 0, 0, 1]
fn char_at(s: Str, index: I64) -> Option[Str]
    cost [1, 0, 0, 1]
fn substring(s: Str, start: I64, end: I64) -> Str
    cost [end - start, end - start, 0, 1]

fn concat(a: Str, b: Str) -> Str      cost [len(a) + len(b), len(a) + len(b), 0, 1]
fn join(parts: List[Str], sep: Str) -> Str
    cost [total_len(parts) + len(parts) * len(sep), total_len(parts) + len(parts) * len(sep), 0, 1]

fn split(s: Str, sep: Str) -> List[Str]
    cost [len(s), len(s), 0, 1]

fn trim(s: Str) -> Str                   cost [len(s), len(s), 0, 1]
fn trim_start(s: Str) -> Str             cost [len(s), len(s), 0, 1]
fn trim_end(s: Str) -> Str               cost [len(s), len(s), 0, 1]

fn to_upper(s: Str) -> Str               cost [len(s), len(s), 0, 1]
fn to_lower(s: Str) -> Str               cost [len(s), len(s), 0, 1]

fn contains(s: Str, pattern: Str) -> Bool    cost [len(s), 0, 0, 1]
fn starts_with(s: Str, prefix: Str) -> Bool  cost [len(prefix), 0, 0, 1]
fn ends_with(s: Str, suffix: Str) -> Bool    cost [len(suffix), 0, 0, 1]

fn replace(s: Str, from: Str, to: Str) -> Str
    cost [len(s), len(s), 0, 1]

fn parse_int(s: Str) -> Result[I64, ParseError]    cost [len(s), 0, 0, 1]
fn parse_float(s: Str) -> Result[F64, ParseError]  cost [len(s), 0, 0, 1]
```

#### `std.collections`

```spore
// ── Map[K, V] ──────────────────────────────────────────────────────

type Map[K, V]  // Immutable hash map (K must implement Hash + Eq)

fn empty_map[K, V]() -> Map[K, V]
    where K: Hash + Eq
    cost [1, 0, 0, 1]

fn get[K, V](m: Map[K, V], key: K) -> Option[V]
    cost [1, 0, 0, 1]

fn insert[K, V](m: Map[K, V], key: K, value: V) -> Map[K, V]
    cost [1, 1, 0, 1]  // amortized

fn remove[K, V](m: Map[K, V], key: K) -> Map[K, V]
    cost [1, 1, 0, 1]  // amortized

fn contains_key[K, V](m: Map[K, V], key: K) -> Bool
    cost [1, 0, 0, 1]

fn keys[K, V](m: Map[K, V]) -> List[K]
    cost [len(m), len(m), 0, 1]

fn values[K, V](m: Map[K, V]) -> List[V]
    cost [len(m), len(m), 0, 1]

fn entries[K, V](m: Map[K, V]) -> List[(K, V)]
    cost [len(m), len(m), 0, 1]

fn map_size[K, V](m: Map[K, V]) -> I64
    cost [1, 0, 0, 1]

fn from_list[K, V](pairs: List[(K, V)]) -> Map[K, V]
    where K: Hash + Eq
    cost [len(pairs), len(pairs), 0, 1]

// ── Set[T] ─────────────────────────────────────────────────────────

type Set[T]  // Immutable hash set (T must implement Hash + Eq)

fn empty_set[T]() -> Set[T]
    where T: Hash + Eq
    cost [1, 0, 0, 1]

fn add[T](s: Set[T], item: T) -> Set[T]
    cost [1, 1, 0, 1]  // amortized

fn remove_from[T](s: Set[T], item: T) -> Set[T]
    cost [1, 1, 0, 1]  // amortized

fn member[T](s: Set[T], item: T) -> Bool
    cost [1, 0, 0, 1]

fn set_size[T](s: Set[T]) -> I64
    cost [1, 0, 0, 1]

fn union[T](a: Set[T], b: Set[T]) -> Set[T]
    cost [len(a) + len(b), len(a) + len(b), 0, 1]

fn intersection[T](a: Set[T], b: Set[T]) -> Set[T]
    cost [min(len(a), len(b)), min(len(a), len(b)), 0, 1]

fn difference[T](a: Set[T], b: Set[T]) -> Set[T]
    cost [len(a), len(a), 0, 1]

fn to_list[T](s: Set[T]) -> List[T]
    cost [len(s), len(s), 0, 1]

fn from_list[T](items: List[T]) -> Set[T]
    where T: Hash + Eq
    cost [len(items), len(items), 0, 1]
```

#### `std.io` (future standardization layer)

`std.io` is not yet the normative surface of the current implementation. Today,
manifest-backed projects import Platform package modules directly. For
`basic-cli`, the shipped modules are:

| Module | Example operations | Required effects |
|---|---|---|
| `basic_cli.stdout` | `print`, `println`, `eprint`, `eprintln` | `Console` |
| `basic_cli.stdin` | `read_line` | `Console` |
| `basic_cli.file` | `file_read`, `file_write`, `file_exists`, `file_stat` | `FileRead`, `FileWrite` |
| `basic_cli.dir` | `dir_list`, `dir_mkdir` | `FileRead`, `FileWrite` |
| `basic_cli.env` | `env_get`, `env_set` | `Env` |
| `basic_cli.cmd` | `process_run`, `process_run_status`, `exit` | `Spawn`, `Exit` |

```spore
pub foreign fn process_run(cmd: Str, args: List[Str]) -> Str ! ExecError uses [Spawn]
pub foreign fn process_run_status(cmd: Str, args: List[Str]) -> Option[U8] ! ExecError uses [Spawn]
pub foreign fn exit(code: U8) -> Never uses [Exit]
```

`basic_cli.cmd.exit(code)` is the currently shipped explicit process-termination
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
    cost [1, 0, 1, 1]

foreign fn elapsed(start: DateTime) -> Duration
    uses [Clock]
    cost [1, 0, 1, 1]

fn duration_ms(d: Duration) -> I64
    cost [1, 0, 0, 1]

fn duration_secs(d: Duration) -> F64
    cost [1, 0, 0, 1]

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

fn parse_json(s: Str) -> Result[JsonValue, ParseError]
    cost [len(s), len(s), 0, 1]

fn to_json[T](value: T) -> Str
    where T: Serialize
    cost [size(value), size(value), 0, 1]

fn from_json[T](s: Str) -> Result[T, ParseError]
    where T: Deserialize
    cost [len(s), len(s), 0, 1]
```

#### `std.random` (platform-provided)

```spore
foreign fn random_float() -> F64
    uses [Random]
    cost [1, 0, 1, 1]

foreign fn random_int(min: I64, max: I64) -> I64
    uses [Random]
    cost [1, 0, 1, 1]

foreign fn uuid() -> Str
    uses [Random]
    cost [1, 16, 1, 1]

fn shuffle[A](list: List[A]) -> List[A]
    uses [Random]
    cost [len(list), len(list), 1, 1]

fn sample[A](list: List[A]) -> Option[A]
    uses [Random]
    cost [1, 0, 1, 1]
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

| Trait | Methods | Derivable | Description |
|-------|---------|-----------|-------------|
| `Eq` | `eq(self, other) -> Bool` | ✅ | Equality comparison |
| `Ord` | `compare(self, other) -> Ordering` | ✅ | Total ordering |
| `Clone` | `clone(self) -> Self` | ✅ | Deep copy |
| `Display` | `display(self) -> Str` | ❌ | Human-readable formatting |
| `Debug` | `debug(self) -> Str` | ✅ | Debug formatting |
| `Hash` | `hash(self) -> U64` | ✅ | Hash computation |
| `Default` | `default() -> Self` | ✅ | Default value |
| `Serialize` | `serialize(self) -> List[U8]` | ✅ | Byte serialization |
| `Deserialize` | `deserialize(bytes: List[U8]) -> Result[Self, ParseError]` | ✅ | Byte deserialization |
| `Add` | `add(self, other) -> Self` | ❌ | `+` operator |
| `Sub` | `sub(self, other) -> Self` | ❌ | `-` operator |
| `Mul` | `mul(self, other) -> Self` | ❌ | `*` operator |
| `Div` | `div(self, other) -> Self` | ❌ | `/` operator |

### 4.6 Platform binding architecture

The current runtime stack for platform-backed I/O looks like this:

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
5. **Future stdlib wrappers** may layer above this, but they are not required for the current implementation.

### 4.7 Cost expression helpers

The cost annotation language (SEP-0004) uses these stdlib-provided size functions:

| Function | Description | Returns |
|----------|-------------|---------|
| `len(list)` | Length of a list | `I64` |
| `len(s)` | Length of a string | `I64` |
| `len(m)` | Number of entries in a map | `I64` |
| `len(s)` | Number of elements in a set | `I64` |
| `size(value)` | Serialized size of a value | `I64` |
| `depth(tree)` | Depth of a tree structure | `I64` |
| `nodes(tree)` | Number of nodes in a tree | `I64` |

These functions are only valid inside cost annotations and are evaluated at compile time via the type checker's cost analysis pass.

## Human experience impact

The stdlib is designed for progressive discovery:

1. **Prelude is small**: Only essential types and iteration primitives — no import ceremony for basic programs
2. **Module names are predictable**: imports like `std.math`, `std.string`, and `std.collections` follow standard conventions
3. **Cost annotations are readable**: four-slot forms like `cost [len(list), len(list), 0, 1]` stay copy-pasteable
4. **Error types are descriptive**: Enum variants like `NotFound(Str)` carry context
5. **No hidden effects**: Every I/O function explicitly declares its effect requirements

## Agent experience impact

Agents benefit from:

1. **Complete enumeration**: All stdlib functions are listed with signatures, enabling auto-completion
2. **Cost contracts**: Agents can reason about algorithmic complexity when filling holes
3. **Effect requirements**: Agents can verify that generated code satisfies effect constraints
4. **Structured errors**: Error type hierarchy enables pattern-matching on failure modes
5. **JSON protocol**: `std.json` provides the serialization layer for hole protocol (SEP-0005)

## Structured representation / protocol impact

The stdlib is represented in the module system as:

```json
{
  "module": "std.prelude",
  "functions": [
    {
      "name": "map",
      "type_params": ["A", "B"],
      "params": [{"name": "list", "type": "List[A]"}, {"name": "f", "type": "(A) -> B"}],
      "return_type": "List[B]",
      "cost": "len(list) * cost(f) + O(len(list))",
      "effects": []
    }
  ],
  "types": [
    {"name": "Option", "params": ["T"], "variants": ["Some(T)", "None"]}
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

| Code | Category | Message |
|------|----------|---------|
| `E0018` | Type error | stdlib function applied to wrong type |
| `E0019` | Type error | missing trait bound for stdlib generic |
| `W0001` | Warning | unused stdlib import |
| `W0002` | Warning | deprecated stdlib function |

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

Rejected. I/O operations cannot be expressed in pure Spore. The designed MVP
mechanism is Platform-owned package modules plus the selected Platform contract
boundary (SEP-0008).

## Prior art

| Language | Stdlib approach | Comparison |
|----------|----------------|------------|
| **Rust** | `std` + `core` (no-std) | Similar layered approach; Spore's is smaller |
| **Roc** | Platform-provided I/O | Direct inspiration for Spore's platform model |
| **Haskell** | `Prelude` + `base` | Similar prelude concept; Spore avoids Haskell's large `base` |
| **Go** | Batteries-included | Larger than Spore's approach |
| **Elm** | Small core + packages | Similar philosophy; Spore adds cost annotations |

## Backward compatibility and migration

This is a new specification — no backward compatibility concerns. However:

- Future changes to prelude types must go through the SEP process
- Deprecation of stdlib functions requires at least one release cycle with warnings
- New stdlib modules can be added without breaking changes

## Unresolved questions

1. **Mutable state API**: Should `Ref[T]` be in the prelude or `std.state`? Currently referenced in SEP-0001 but not fully specified here.

2. **Concurrency primitives**: `Task[T]`, `Chan[T]`, `select` are defined in SEP-0007 — should they be re-exported via `std.concurrent` or remain as language primitives?

3. **String encoding**: Should `Str` expose byte-level access, or only scalar-oriented indexing? Current spec assumes UTF-8; there is no `Char` type (length-1 `Str` values instead).

4. **Numeric tower**: The reference implementation exposes fixed widths (`I8`…`U64`, `F32`, `F64`). Stdlib APIs should choose explicit widths at each boundary rather than relying on abstract scalar aliases.

5. **Iterator protocol**: Should there be a lazy `Iterator[T]` trait instead of materializing `List[T]` for all operations? This would change cost signatures significantly.

6. **Error recovery**: How should `PanicError` interact with the effect system? Should `panic` require an effect?

7. **FFI type mapping**: How do Spore types map to Rust/C types across the FFI boundary? (e.g., `I64` ↔ `i64`, `Str` ↔ UTF-8 buffer)
