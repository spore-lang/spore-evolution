---
sep: 9
title: "SEP-0009: Standard Library Surface"
status: Draft
type: Standards Track
authors:
  - Spore Contributors
created: 2026-04-01
requires: [1, 2, 3, 4]
discussion: "https://github.com/spore-lang/spore-evolution/discussions"
pr: null
superseded_by: null
---

> **Executive Summary**: Defines the standard library surface for Spore — the set of built-in types, functions, traits, and error types that every Spore program can rely on. Organizes the stdlib into a layered prelude (always-available primitives), core modules (opt-in via import), and platform-provided I/O bindings. Every function carries capability requirements and cost annotations per SEP-0003 and SEP-0004.

# SEP-0009: Standard Library Surface

## Summary

This SEP specifies the standard library that ships with every Spore implementation. It defines:

1. **Prelude** — types and functions available without import
2. **Core modules** — standard modules available via `import std.*`
3. **Error types** — a unified error hierarchy
4. **Platform bindings** — how I/O functions connect to platform effect handlers
5. **Cost contracts** — cost annotations for all stdlib functions

The stdlib is deliberately small. Spore follows the principle that the standard library should provide exactly the types and functions needed to write idiomatic Spore code, with everything else available as packages.

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
// Primitive types (compiler-intrinsic)
// Int, Float, Bool, String, Char, Unit, Never

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
import std.io         // Platform-provided I/O bindings
import std.time       // DateTime, Duration, now(), ...
import std.json       // parse_json, to_json
```

### How do I/O functions work?

I/O functions are **not** ordinary Spore functions — they are `foreign fn` declarations provided by the platform (SEP-0008). The stdlib re-exports them with Spore-visible type signatures:

```spore
// In std.io (provided by platform)
foreign fn read_file(path: String) -> Result[String, IoError]
    uses [FileRead]

foreign fn write_file(path: String, content: String) -> Result[Unit, IoError]
    uses [FileWrite]

foreign fn http_get(url: String) -> Result[String, HttpError]
    uses [NetRead]
```

The platform effect handler mechanism (SEP-0008) ensures these functions are only available when the ambient capability set includes the required capabilities.

## Reference-level explanation

### 4.1 Prelude types

The prelude is implicitly imported into every module. It contains:

#### Primitive types

| Type | Description | Default | Size |
|------|-------------|---------|------|
| `Int` | Arbitrary-precision integer | `0` | Variable |
| `Float` | 64-bit IEEE 754 | `0.0` | 8 bytes |
| `Bool` | Boolean | `false` | 1 byte |
| `String` | Immutable UTF-8 string | `""` | Variable |
| `Char` | Unicode scalar value | — | 4 bytes |
| `Unit` | Zero-valued type | `()` | 0 bytes |
| `Never` | Bottom type (uninhabited) | — | 0 bytes |

#### Algebraic types

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
    ! [PanicError]
    cost O(1)

fn unwrap_or[T](opt: Option[T], default: T) -> T
    cost O(1)

fn map[T, U](opt: Option[T], f: (T) -> U) -> Option[U]
    cost cost(f)

fn and_then[T, U](opt: Option[T], f: (T) -> Option[U]) -> Option[U]
    cost cost(f)

fn is_some[T](opt: Option[T]) -> Bool
    cost O(1)

fn is_none[T](opt: Option[T]) -> Bool
    cost O(1)
```

#### Result[T, E] methods

```spore
fn unwrap[T, E](res: Result[T, E]) -> T
    ! [PanicError]
    cost O(1)

fn unwrap_or[T, E](res: Result[T, E], default: T) -> T
    cost O(1)

fn map[T, U, E](res: Result[T, E], f: (T) -> U) -> Result[U, E]
    cost cost(f)

fn map_err[T, E, F](res: Result[T, E], f: (E) -> F) -> Result[T, F]
    cost cost(f)

fn and_then[T, U, E](res: Result[T, E], f: (T) -> Result[U, E]) -> Result[U, E]
    cost cost(f)

fn is_ok[T, E](res: Result[T, E]) -> Bool
    cost O(1)

fn is_err[T, E](res: Result[T, E]) -> Bool
    cost O(1)
```

#### List iteration (core HOFs)

These are the **primary iteration primitives** in Spore (no loops — SEP-0001):

```spore
fn map[A, B](list: List[A], f: (A) -> B) -> List[B]
    cost len(list) * cost(f) + O(len(list))

fn filter[A](list: List[A], p: (A) -> Bool) -> List[A]
    cost len(list) * cost(p) + O(len(list))

fn fold[A, B](list: List[A], init: B, f: (B, A) -> B) -> B
    cost len(list) * cost(f)

fn each[A](list: List[A], f: (A) -> Unit) -> Unit
    cost len(list) * cost(f)

fn flat_map[A, B](list: List[A], f: (A) -> List[B]) -> List[B]
    cost len(list) * cost(f) + O(total_output_len)

fn zip[A, B](a: List[A], b: List[B]) -> List[(A, B)]
    cost O(min(len(a), len(b)))

fn enumerate[A](list: List[A]) -> List[(Int, A)]
    cost O(len(list))
```

#### List query functions

```spore
fn len[A](list: List[A]) -> Int
    cost O(1)

fn is_empty[A](list: List[A]) -> Bool
    cost O(1)

fn head[A](list: List[A]) -> Option[A]
    cost O(1)

fn tail[A](list: List[A]) -> Option[List[A]]
    cost O(1)

fn last[A](list: List[A]) -> Option[A]
    cost O(len(list))

fn contains[A](list: List[A], item: A) -> Bool
    where A: Eq
    cost O(len(list))

fn find[A](list: List[A], p: (A) -> Bool) -> Option[A]
    cost O(len(list)) * cost(p)

fn any[A](list: List[A], p: (A) -> Bool) -> Bool
    cost O(len(list)) * cost(p)

fn all[A](list: List[A], p: (A) -> Bool) -> Bool
    cost O(len(list)) * cost(p)
```

#### List construction functions

```spore
fn append[A](list: List[A], item: A) -> List[A]
    cost O(len(list))

fn prepend[A](item: A, list: List[A]) -> List[A]
    cost O(1)

fn concat[A](a: List[A], b: List[A]) -> List[A]
    cost O(len(a))

fn reverse[A](list: List[A]) -> List[A]
    cost O(len(list))

fn take[A](list: List[A], n: Int) -> List[A]
    cost O(n)

fn drop[A](list: List[A], n: Int) -> List[A]
    cost O(n)

fn range(start: Int, end: Int) -> List[Int]
    cost O(end - start)
```

#### Sorting

```spore
fn sort[A](list: List[A]) -> List[A]
    where A: Ord
    cost O(len(list) * log(len(list)))

fn sort_by[A](list: List[A], cmp: (A, A) -> Ordering) -> List[A]
    cost O(len(list) * log(len(list))) * cost(cmp)
```

#### Conversion and display

```spore
fn to_string[A](value: A) -> String
    where A: Display
    cost O(1)

fn debug[A](value: A) -> String
    where A: Debug
    cost O(1)
```

### 4.3 Core modules

#### `std.math`

```spore
module std.math

fn abs(x: Int) -> Int             cost O(1)
fn abs_float(x: Float) -> Float   cost O(1)
fn min(a: Int, b: Int) -> Int     cost O(1)
fn max(a: Int, b: Int) -> Int     cost O(1)
fn clamp(x: Int, lo: Int, hi: Int) -> Int  cost O(1)

// Floating-point math
fn sqrt(x: Float) -> Float        cost O(1)
fn pow(base: Float, exp: Float) -> Float  cost O(1)
fn log(x: Float) -> Float         cost O(1)
fn log2(x: Float) -> Float        cost O(1)
fn log10(x: Float) -> Float       cost O(1)
fn exp(x: Float) -> Float         cost O(1)

// Trigonometric
fn sin(x: Float) -> Float         cost O(1)
fn cos(x: Float) -> Float         cost O(1)
fn tan(x: Float) -> Float         cost O(1)
fn asin(x: Float) -> Float        cost O(1)
fn acos(x: Float) -> Float        cost O(1)
fn atan(x: Float) -> Float        cost O(1)
fn atan2(y: Float, x: Float) -> Float  cost O(1)

// Rounding
fn floor(x: Float) -> Int         cost O(1)
fn ceil(x: Float) -> Int          cost O(1)
fn round(x: Float) -> Int         cost O(1)
fn truncate(x: Float) -> Int      cost O(1)

// Constants
let pi: Float = 3.14159265358979323846
let e: Float = 2.71828182845904523536
let infinity: Float
let neg_infinity: Float
let nan: Float
```

#### `std.string`

```spore
module std.string

fn length(s: String) -> Int                  cost O(1)
fn is_empty(s: String) -> Bool               cost O(1)
fn char_at(s: String, index: Int) -> Option[Char]  cost O(1)
fn substring(s: String, start: Int, end: Int) -> String  cost O(end - start)

fn concat(a: String, b: String) -> String    cost O(len(a) + len(b))
fn join(parts: List[String], sep: String) -> String
    cost O(total_len(parts) + len(parts) * len(sep))

fn split(s: String, sep: String) -> List[String]
    cost O(len(s))

fn trim(s: String) -> String                 cost O(len(s))
fn trim_start(s: String) -> String           cost O(len(s))
fn trim_end(s: String) -> String             cost O(len(s))

fn to_upper(s: String) -> String             cost O(len(s))
fn to_lower(s: String) -> String             cost O(len(s))

fn contains(s: String, pattern: String) -> Bool  cost O(len(s))
fn starts_with(s: String, prefix: String) -> Bool  cost O(len(prefix))
fn ends_with(s: String, suffix: String) -> Bool  cost O(len(suffix))

fn replace(s: String, from: String, to: String) -> String  cost O(len(s))

fn parse_int(s: String) -> Result[Int, ParseError]  cost O(len(s))
fn parse_float(s: String) -> Result[Float, ParseError]  cost O(len(s))
```

#### `std.collections`

```spore
module std.collections

// ── Map[K, V] ──────────────────────────────────────────────────────

type Map[K, V]  // Immutable hash map (K must implement Hash + Eq)

fn empty_map[K, V]() -> Map[K, V]
    where K: Hash + Eq
    cost O(1)

fn get[K, V](m: Map[K, V], key: K) -> Option[V]
    cost O(1)

fn insert[K, V](m: Map[K, V], key: K, value: V) -> Map[K, V]
    cost O(1)  // amortized

fn remove[K, V](m: Map[K, V], key: K) -> Map[K, V]
    cost O(1)  // amortized

fn contains_key[K, V](m: Map[K, V], key: K) -> Bool
    cost O(1)

fn keys[K, V](m: Map[K, V]) -> List[K]
    cost O(len(m))

fn values[K, V](m: Map[K, V]) -> List[V]
    cost O(len(m))

fn entries[K, V](m: Map[K, V]) -> List[(K, V)]
    cost O(len(m))

fn map_size[K, V](m: Map[K, V]) -> Int
    cost O(1)

fn from_list[K, V](pairs: List[(K, V)]) -> Map[K, V]
    where K: Hash + Eq
    cost O(len(pairs))

// ── Set[T] ─────────────────────────────────────────────────────────

type Set[T]  // Immutable hash set (T must implement Hash + Eq)

fn empty_set[T]() -> Set[T]
    where T: Hash + Eq
    cost O(1)

fn add[T](s: Set[T], item: T) -> Set[T]
    cost O(1)  // amortized

fn remove_from[T](s: Set[T], item: T) -> Set[T]
    cost O(1)  // amortized

fn member[T](s: Set[T], item: T) -> Bool
    cost O(1)

fn set_size[T](s: Set[T]) -> Int
    cost O(1)

fn union[T](a: Set[T], b: Set[T]) -> Set[T]
    cost O(len(a) + len(b))

fn intersection[T](a: Set[T], b: Set[T]) -> Set[T]
    cost O(min(len(a), len(b)))

fn difference[T](a: Set[T], b: Set[T]) -> Set[T]
    cost O(len(a))

fn to_list[T](s: Set[T]) -> List[T]
    cost O(len(s))

fn from_list[T](items: List[T]) -> Set[T]
    where T: Hash + Eq
    cost O(len(items))
```

#### `std.io` (platform-provided)

```spore
module std.io

// ── Filesystem ─────────────────────────────────────────────────────

foreign fn read_file(path: String) -> Result[String, IoError]
    uses [FileRead]
    cost O(file_size)

foreign fn read_bytes(path: String) -> Result[List[Int], IoError]
    uses [FileRead]
    cost O(file_size)

foreign fn write_file(path: String, content: String) -> Result[Unit, IoError]
    uses [FileWrite]
    cost O(len(content))

foreign fn append_file(path: String, content: String) -> Result[Unit, IoError]
    uses [FileWrite]
    cost O(len(content))

foreign fn list_dir(path: String) -> Result[List[String], IoError]
    uses [FileRead]

foreign fn create_dir(path: String) -> Result[Unit, IoError]
    uses [FileWrite]

foreign fn delete(path: String) -> Result[Unit, IoError]
    uses [FileWrite]

foreign fn file_exists(path: String) -> Result[Bool, IoError]
    uses [FileRead]
    cost O(1)

// ── Network ────────────────────────────────────────────────────────

foreign fn http_get(url: String) -> Result[String, HttpError]
    uses [NetRead]

foreign fn http_post(url: String, body: String) -> Result[String, HttpError]
    uses [NetWrite]

// ── Console ────────────────────────────────────────────────────────

foreign fn print(msg: String) -> Unit
    uses [StateWrite]
    cost O(len(msg))

foreign fn println(msg: String) -> Unit
    uses [StateWrite]
    cost O(len(msg))

foreign fn read_line() -> Result[String, IoError]
    uses [StateRead]

// ── Process ────────────────────────────────────────────────────────

foreign fn exit(code: Int) -> Never
    uses [Exit]
    cost O(1)

foreign fn env_var(name: String) -> Option[String]
    uses [StateRead]
    cost O(1)

foreign fn args() -> List[String]
    uses [StateRead]
    cost O(1)
```

#### `std.time` (platform-provided)

```spore
module std.time

type DateTime   // Opaque timestamp
type Duration   // Time interval

foreign fn now() -> DateTime
    uses [Clock]
    cost O(1)

foreign fn elapsed(start: DateTime) -> Duration
    uses [Clock]
    cost O(1)

fn duration_ms(d: Duration) -> Int
    cost O(1)

fn duration_secs(d: Duration) -> Float
    cost O(1)

foreign fn sleep(ms: Int) -> Unit
    uses [Clock]
    cost @unbounded
```

#### `std.json`

```spore
module std.json

type JsonValue {
    JsonNull,
    JsonBool(Bool),
    JsonInt(Int),
    JsonFloat(Float),
    JsonString(String),
    JsonArray(List[JsonValue]),
    JsonObject(Map[String, JsonValue]),
}

fn parse_json(s: String) -> Result[JsonValue, ParseError]
    cost O(len(s))

fn to_json[T](value: T) -> String
    where T: Serialize
    cost O(size(value))

fn from_json[T](s: String) -> Result[T, ParseError]
    where T: Deserialize
    cost O(len(s))
```

#### `std.random` (platform-provided)

```spore
module std.random

foreign fn random_float() -> Float
    uses [Random]
    cost O(1)

foreign fn random_int(min: Int, max: Int) -> Int
    uses [Random]
    cost O(1)

foreign fn uuid() -> String
    uses [Random]
    cost O(1)

fn shuffle[A](list: List[A]) -> List[A]
    uses [Random]
    cost O(len(list))

fn sample[A](list: List[A]) -> Option[A]
    uses [Random]
    cost O(1)
```

### 4.4 Error type hierarchy

All stdlib errors conform to a base capability trait:

```spore
capability Error[T] {
    fn message(self: T) -> String
}
```

The standard error types:

```spore
type PanicError { Panic(String) }

type IoError {
    NotFound(String),
    PermissionDenied(String),
    AlreadyExists(String),
    Other(String),
}

type HttpError {
    ConnectionFailed(String),
    Timeout(String),
    StatusError(Int, String),
    Other(String),
}

type ParseError {
    InvalidFormat(String),
    UnexpectedToken(String, Int),
    Other(String),
}

type JsonError {
    InvalidJson(String, Int),
    TypeMismatch(String),
    MissingField(String),
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
| `Display` | `display(self) -> String` | ❌ | Human-readable formatting |
| `Debug` | `debug(self) -> String` | ✅ | Debug formatting |
| `Hash` | `hash(self) -> Int` | ✅ | Hash computation |
| `Default` | `default() -> Self` | ✅ | Default value |
| `Serialize` | `serialize(self) -> List[Int]` | ✅ | Byte serialization |
| `Deserialize` | `deserialize(bytes: List[Int]) -> Result[Self, ParseError]` | ✅ | Byte deserialization |
| `Add` | `add(self, other) -> Self` | ❌ | `+` operator |
| `Sub` | `sub(self, other) -> Self` | ❌ | `-` operator |
| `Mul` | `mul(self, other) -> Self` | ❌ | `*` operator |
| `Div` | `div(self, other) -> Self` | ❌ | `/` operator |

### 4.6 Platform binding architecture

The stdlib I/O layer uses the platform effect handler mechanism from SEP-0008:

```text
┌─────────────────────────────────────────┐
│  User Code                              │
│  fn main() uses [FileRead] {            │
│      let content = read_file("a.txt")   │
│  }                                      │
├─────────────────────────────────────────┤
│  std.io (Spore signatures)              │
│  foreign fn read_file(path) -> Result   │
│      uses [FileRead]                    │
├─────────────────────────────────────────┤
│  Platform (effect handler)              │
│  handle FileRead {                      │
│      read_file(path) => rust_read(path) │
│  }                                      │
├─────────────────────────────────────────┤
│  Native Runtime (Rust/C)                │
│  fn rust_read(path: &str) -> ...        │
└─────────────────────────────────────────┘
```

Key properties:

1. **User code** calls stdlib functions with normal Spore syntax
2. **Stdlib** declares `foreign fn` with capability requirements
3. **Platform** provides the actual implementation via effect handlers
4. **Test platform** can mock any I/O function for deterministic testing
5. **Capability isolation** — a package declaring `uses [Compute]` cannot call any `foreign fn` that requires I/O capabilities

### 4.7 Cost expression helpers

The cost annotation language (SEP-0004) uses these stdlib-provided size functions:

| Function | Description | Returns |
|----------|-------------|---------|
| `len(list)` | Length of a list | `Int` |
| `len(s)` | Length of a string | `Int` |
| `len(m)` | Number of entries in a map | `Int` |
| `len(s)` | Number of elements in a set | `Int` |
| `size(value)` | Serialized size of a value | `Int` |
| `depth(tree)` | Depth of a tree structure | `Int` |
| `nodes(tree)` | Number of nodes in a tree | `Int` |

These functions are only valid inside cost annotations and are evaluated at compile time via the type checker's cost analysis pass.

## Human experience impact

The stdlib is designed for progressive discovery:

1. **Prelude is small**: Only essential types and iteration primitives — no import ceremony for basic programs
2. **Module names are predictable**: `std.math`, `std.string`, `std.collections` follow standard conventions
3. **Cost annotations are readable**: `cost O(len(list))` reads naturally
4. **Error types are descriptive**: Enum variants like `NotFound(String)` carry context
5. **No hidden effects**: Every I/O function explicitly declares its capability requirements

## Agent experience impact

Agents benefit from:

1. **Complete enumeration**: All stdlib functions are listed with signatures, enabling auto-completion
2. **Cost contracts**: Agents can reason about algorithmic complexity when filling holes
3. **Capability requirements**: Agents can verify that generated code satisfies capability constraints
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
      "capabilities": []
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

Rejected. I/O operations cannot be expressed in pure Spore. The platform effect handler model is the designed mechanism for I/O (SEP-0008).

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

3. **String encoding**: Should `String` expose byte-level access, or only character-level? Current spec assumes UTF-8 with character indexing.

4. **Numeric tower**: Should there be `Int8`, `Int16`, `Int32`, `Int64`, `UInt*` types for low-level use, or only `Int` and `Float`?

5. **Iterator protocol**: Should there be a lazy `Iterator[T]` trait instead of materializing `List[T]` for all operations? This would change cost signatures significantly.

6. **Error recovery**: How should `PanicError` interact with the capability system? Should `panic` require a capability?

7. **FFI type mapping**: How do Spore types map to Rust/C types across the FFI boundary? (e.g., `Int` → `i64` or `BigInt`?)
