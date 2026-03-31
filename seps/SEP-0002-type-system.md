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

## Summary

This SEP specifies the type system for the Spore programming language. Spore's type system is a **nominal-primary, bidirectionally-inferred** system that sits between Rust and Haskell on the expressiveness spectrum — more targeted than full dependent types, yet richer than a Hindley–Milner core alone.

The concrete type representation is the `Ty` enum:

```text
Ty ::= Int | Float | Bool | Str | Unit
      | Named(name)
      | App(name, [Ty])
      | Tuple([Ty])
      | Fn([Ty], Ty, CapSet)
      | Var(u32)
      | Hole(name)
      | Error
```

Key design decisions:

- **Signatures are gravity centers** — function signatures must be richly typed and fully explicit; bodies are inferred.
- **CapSet = BTreeSet\<String\>** is encoded directly in function types, making effect tracking a first-class part of the type.
- **Bidirectional type inference** — top-down checking from signatures, bottom-up synthesis from expressions.
- **Two-pass module checking** — `register_item` (collect all signatures) then `check_fn` (verify bodies).
- **Generics via square-bracket application** — `List[Int]`, `Result[T, E]`.
- **Type unification** with `Var` binding and substitution maps.
- **Refinement types (future)** — L0 decidable predicates + L1 abstract interpretation without an SMT solver.

## Motivation

### Why a type system specification?

Spore is being co-developed by humans and AI Agents. Both audiences need precise, unambiguous rules for:

1. **What programs are well-typed.** Agents generate code that must type-check. Vague rules produce vague code.
2. **What information flows through signatures.** Signatures are the primary communication channel between components, between humans and Agents, and between Agents. They must encode types, capabilities, cost bounds, and error sets.
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
| **Nominal-primary, structural escape** | Named types are nominal; anonymous records are structural; capabilities are always nominal |
| **Capabilities = Traits** | Unified abstraction — `capability` is syntactic sugar for a trait on execution context |
| **Decidable checking** | No SMT solver; refinements limited to decidable predicates and abstract interpretation |
| **Agent-friendly** | Richer types help Agents more than they hurt humans; Agents absorb annotation complexity |
| **Predictable** | No implicit conversions, no type-level computation, no SFINAE-style surprises |

## Guide-level explanation

This section introduces Spore's type system from a user's perspective, with code examples showing type annotations, inference, and generics.

### 3.1 Primitive types

Spore provides a small set of built-in primitive types:

```spore
let x: Int = 42              -- arbitrary-precision integer
let y: Float = 3.14          -- 64-bit IEEE 754
let b: Bool = true           -- boolean
let s: String = "hello"      -- UTF-8 string
let u: () = ()               -- unit (zero-information type)
```

All primitives are nominal — `Int` ≠ `Float` even when their bit patterns coincide.

### 3.2 Type annotations on functions

Function signatures **must** be fully annotated. Parameters, return type, error set, capability set, and cost bound are all declared:

```spore
fn add(a: Int, b: Int) -> Int {
    a + b
}

fn fetch_page(url: String) -> String ! [NetworkError]
uses [NetRead]
cost <= 5000
{
    http_get(url)
}
```

Local variables inside bodies do **not** need annotations — they are inferred:

```spore
fn process(x: Int) -> Int {
    let doubled = x * 2          -- inferred: Int
    let message = "result"       -- inferred: String
    doubled + 1                  -- inferred: Int, checked against return type
}
```

### 3.3 Struct and enum types

Structs are nominal product types:

```spore
type Point = {
    x: Float,
    y: Float,
}

let p = Point { x: 1.0, y: 2.0 }
let dist = sqrt(p.x * p.x + p.y * p.y)
```

Enums are sealed sum types with exhaustive pattern matching:

```spore
type Shape =
    | Circle { radius: Float }
    | Rectangle { width: Float, height: Float }

fn area(shape: Shape) -> Float {
    match shape {
        Circle { radius }           => 3.14159 * radius * radius,
        Rectangle { width, height } => width * height,
    }
}
```

### 3.4 Tuple types

Tuple types group unnamed fields positionally:

```spore
fn swap(pair: (Int, String)) -> (String, Int) {
    let (a, b) = pair
    (b, a)
}
```

### 3.5 Function types with capabilities

Function types carry a **CapSet** — the set of capabilities (effects) the function requires:

```spore
type Logger = Fn(msg: String) -> () uses [FileWrite]

fn with_logging(f: Fn(x: Int) -> Int, x: Int) -> Int
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
    -- implementation
}

fn sort[T](list: List[T]) -> List[T]
where T: Ord
{
    -- implementation
}
```

At call sites, type arguments are inferred from the actual argument types:

```spore
let nums: List[Int] = [1, 2, 3]
let result = identity(42)          -- T inferred as Int
let strings = map(nums, show)      -- A=Int, B=String inferred
```

### 3.7 Generic type application

Named generic types use square-bracket application in type position:

```spore
type Pair[A, B] = {
    first: A,
    second: B,
}

let p: Pair[Int, String] = Pair { first: 1, second: "hello" }

type Result[T, E] =
    | Ok { value: T }
    | Err { error: E }
```

### 3.8 Typed holes

Holes are unfilled positions in code. The type checker infers their expected type from context and reports it:

```spore
fn example(x: Int, y: String) -> Bool {
    let a: Int = ?h1          -- hole ?h1 must produce Int
    let b = if a > 0 {
        ?h2                   -- hole ?h2 must produce Bool (from return type)
    } else {
        false
    }
    b
}
```

The compiler reports:

```text
Hole ?h1: expected type Int
Hole ?h2: expected type Bool
```

## Reference-level explanation

### 4.1 Type grammar

The internal type representation is the `Ty` enum, defined in `spore-typeck/src/types.rs`:

```text
τ ::= Int                          -- integer primitive
    | Float                        -- floating-point primitive
    | Bool                         -- boolean primitive
    | Str                          -- string primitive
    | Unit                         -- unit type (empty tuple)
    | Named(n)                     -- named type / type parameter
    | App(n, [τ₁, …, τₖ])         -- generic type application
    | Tuple([τ₁, …, τₖ])          -- tuple type
    | Fn([τ₁, …, τₙ], τᵣ, C)     -- function type with capability set
    | Var(id)                      -- unification variable
    | Hole(name)                   -- typed hole placeholder
    | Error                        -- error sentinel (recovery)
```

Where:

- `n` ranges over identifiers (strings).
- `id` ranges over `u32` (unique unification variable IDs).
- `C` is a **CapSet** = `BTreeSet<String>`, the set of capability names the function requires.

**Error sentinel.** `Ty::Error` is produced when type resolution fails (e.g., unknown type name). It unifies with anything, allowing the checker to continue after errors and report multiple diagnostics.

**Hole type.** `Ty::Hole(name)` represents an unfilled hole. During unification, holes are compatible with anything — the checker records the expected type for diagnostic purposes without blocking further checking.

### 4.2 Capability sets (CapSet)

```rust
pub type CapSet = BTreeSet<String>;
```

A `CapSet` is a sorted set of capability names. It appears as the third component of `Ty::Fn`:

```text
Fn([τ₁, …, τₙ], τᵣ, { cap₁, cap₂, … })
```

**CapSet rules:**

1. A function may only call another function whose CapSet is a **subset** of its own.
2. A pure function has `CapSet = ∅`.
3. CapSets propagate through higher-order calls: passing a `Fn(...) uses [NetRead]` to a higher-order function requires the caller to declare `NetRead`.
4. `uses [Cap1, Cap2]` in source syntax maps directly to `CapSet = {"Cap1", "Cap2"}`.

**Formal capability checking rule:**

```text
Γ ⊢ f : Fn([σ₁, …, σₙ], τᵣ, C_f)
C_caller ⊇ C_f
─────────────────────────────────────────
Γ; C_caller ⊢ f(e₁, …, eₙ) : τᵣ
```

If `C_f ⊄ C_caller`, the checker emits:

```text
missing capabilities [X, Y]: caller does not declare them
```

### 4.3 Bidirectional type inference

Spore uses **bidirectional type checking** with two modes:

- **Check mode (⇐):** An expected type is pushed down from the context (function return type, let-binding annotation, argument position).
- **Synth mode (⇒):** A type is synthesized bottom-up from the expression structure.

#### Inference rules (core subset)

**Literals (synthesis):**

```text
─────────────────
Γ ⊢ n ⇒ Int          (integer literal)

─────────────────
Γ ⊢ f ⇒ Float        (float literal)

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
apply_subst(Tuple(ts))            = Tuple(apply_subst(ts))
apply_subst(τ)                    = τ                  for all other τ
```

Note that `CapSet` is **not** subject to substitution — capabilities are always concrete strings, never type variables.

#### Unification algorithm

The `unify` function is the heart of type inference. Given two types `expected` and `actual`, it either succeeds (possibly binding type variables) or emits an error:

```text
unify(τ, τ) = ok                                        (reflexivity)
unify(Error, _) = ok                                    (error recovery)
unify(_, Error) = ok                                    (error recovery)
unify(Hole(_), _) = ok                                  (hole compatibility)
unify(_, Hole(_)) = ok                                  (hole compatibility)
unify(Var(id), τ) = σ[id ↦ τ]                           (variable binding)
unify(τ, Var(id)) = σ[id ↦ τ]                           (variable binding, symmetric)
unify(Fn(ps₁, r₁, _), Fn(ps₂, r₂, _))                  (structural: function)
    = unify(ps₁[i], ps₂[i]) for all i; unify(r₁, r₂)
unify(App(n, as₁), App(n, as₂))                         (structural: application)
    = unify(as₁[i], as₂[i]) for all i
unify(Tuple(ts₁), Tuple(ts₂))                           (structural: tuple)
    = unify(ts₁[i], ts₂[i]) for all i
unify(τ₁, τ₂)                                           (mismatch)
    = error "type mismatch: expected τ₁, got τ₂"
```

**Implementation note:** The current unifier does **not** perform an occurs check. This is acceptable because Spore does not support recursive type variable bindings in user-visible code. If this changes (e.g., for recursive anonymous types), an occurs check must be added.

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

- **Functions:** Parameter types are resolved, return type is resolved (default `Unit`), CapSet is extracted from `uses` clause, and type parameters from `where` clause are recorded.
- **Structs:** Field names and types are resolved and stored.
- **Type defs (enums):** Variant names and field types are resolved and stored.
- **Capabilities and imports:** Deferred (no registration needed).

**Pass 2 — `check_fn`:** For each function with a body:

1. Set the current CapSet from the function's `uses` clause.
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

### 4.7 Tuple types

Tuple types are represented as `Ty::Tuple(Vec<Ty>)`. Tuple construction synthesizes the type from its elements:

```text
Γ ⊢ e₁ ⇒ τ₁  …  Γ ⊢ eₖ ⇒ τₖ
──────────────────────────────────
Γ ⊢ (e₁, …, eₖ) ⇒ Tuple([τ₁, …, τₖ])
```

Tuple indexing extracts the type at a given position:

```text
Γ ⊢ e ⇒ Tuple([τ₀, …, τₖ₋₁])
0 ≤ i < k
────────────────────────────────
Γ ⊢ e.i ⇒ τᵢ
```

### 4.8 Function types

Function types are `Ty::Fn(params, ret, CapSet)`:

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
(Int, String) -> Bool
(Int) -> Int uses [FileRead, NetWrite]
```

### 4.9 Subtyping

The current implementation uses **equality-based** type compatibility (no subtyping lattice). Two types are compatible if and only if they unify. This means:

- `Int ≠ Float` — no implicit numeric widening.
- `Named("UserId") ≠ Named("String")` — newtypes are distinct.
- `Ty::Error` unifies with anything (error recovery only).
- `Ty::Hole(name)` unifies with anything (hole placeholder only).

**Future extensions (not yet implemented):**

- `Never` as the bottom type (subtype of all types): `Never <: τ` for all `τ`.
- Width subtyping for anonymous records: `{ a: Int, b: String, c: Bool } <: { a: Int, b: String }`.
- Capability set subtyping: `C₁ ⊆ C₂ ⟹ Fn(ps, r, C₁) <: Fn(ps, r, C₂)`.

### 4.10 Binary and unary operator typing

**Arithmetic operators** (`+`, `-`, `*`, `/`):

```text
Γ ⊢ e₁ ⇒ τ    Γ ⊢ e₂ ⇒ τ
τ ∈ {Int, Float}
────────────────────────────
Γ ⊢ e₁ ⊕ e₂ ⇒ τ
```

**Comparison operators** (`==`, `!=`, `<`, `<=`, `>`, `>=`):

```text
Γ ⊢ e₁ ⇒ τ    Γ ⊢ e₂ ⇒ τ
────────────────────────────
Γ ⊢ e₁ ⊗ e₂ ⇒ Bool
```

**Boolean operators** (`&&`, `||`):

```text
Γ ⊢ e₁ ⇐ Bool    Γ ⊢ e₂ ⇐ Bool
──────────────────────────────────
Γ ⊢ e₁ ∧∨ e₂ ⇒ Bool
```

**Unary negation** (`-`):

```text
Γ ⊢ e ⇒ τ    τ ∈ {Int, Float}
───────────────────────────────
Γ ⊢ -e ⇒ τ
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
type Port = Int if 1 <= self <= 65535
type Percentage = Float if 0.0 <= self <= 100.0
type NonEmptyString = String if self.len() > 0
```

The decidable predicate language includes:

- Numeric comparisons: `<`, `<=`, `==`, `!=`, `>=`, `>`
- Arithmetic on constants: `self + 1 <= 100`
- String / collection length: `self.len() > 0`
- Boolean connectives: `&&`, `||`, `!`
- Const equality: `self == "production" || self == "staging"`

**L0 checking rule:**

```text
Γ ⊢ e ⇒ base_type
eval(predicate[self ↦ e]) = true
────────────────────────────────
Γ ⊢ e ⇐ base_type if predicate
```

When the compiler cannot statically evaluate the predicate (e.g., value comes from runtime input), it requires an explicit runtime check via control flow.

#### L1 — Abstract interpretation propagation

L1 uses flow-sensitive abstract interpretation to propagate refinement information:

```spore
fn process_port(raw: Int) -> Port ! [InvalidPort] {
    if raw < 1 || raw > 65535 {
        raise InvalidPort { value: raw }
    }
    -- After the guard, the compiler knows: 1 <= raw <= 65535
    -- raw is automatically narrowed to Port
    raw
}
```

The abstract domain tracks **interval constraints** on integer and float values. At each branch point, the domain is split:

- True branch: constraints from the condition added.
- False branch: negated constraints added.

L1 explicitly excludes: arbitrary quantifiers, aliasing analysis, heap reasoning, and SMT-level theorem proving. This keeps checking decidable and error messages predictable.

## Human experience impact

### Positive

- **Clear error messages.** Because types are nominal and simple, error messages can say "expected `Celsius`, got `Fahrenheit`" rather than showing structural type dumps.
- **Minimal annotation burden.** Only function signatures require full annotation; local variables and closures are inferred. Humans write types where they matter (API boundaries) and skip them where they don't (implementation details).
- **Predictable behavior.** No implicit conversions, no SFINAE, no surprising type-level computation. If it compiles, the types mean what they say.
- **Refinement types (future) catch bugs early.** `Port` being `Int if 1 <= self <= 65535` means invalid values are caught at compile time, not at runtime.

### Negative

- **Explicit annotation requirement.** Requiring full function signatures is more annotation than TypeScript or Python. However, this is a deliberate trade-off — signatures are the gravity center for both humans and Agents.
- **Nominal strictness.** Newtypes like `Celsius ≠ Float` require explicit conversions. This prevents accidental misuse but adds ceremony for simple cases.

### Cognitive model

The mental model for Spore's type system is: **"Types are contracts. Write them on the outside, let the compiler figure out the inside."**

## Agent experience impact

### Type-directed synthesis

Rich type signatures give Agents strong guidance for code generation:

- Parameter types constrain what values are available.
- Return types constrain what the body must produce.
- CapSet constrains which side-effectful functions may be called.
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

The checker tracks `HoleReport` — a map from hole names to their inferred expected types, available variables in scope, and suggested fill functions. This structured output is the primary input for Agent hole-filling strategies.

## Structured representation / protocol impact

### Type representation in diagnostics

All types implement `Display` with a canonical format:

| Type | Display |
|---|---|
| `Ty::Int` | `Int` |
| `Ty::Float` | `Float` |
| `Ty::Bool` | `Bool` |
| `Ty::Str` | `String` |
| `Ty::Unit` | `()` |
| `Ty::Named("Foo")` | `Foo` |
| `Ty::App("List", [Int])` | `List[Int]` |
| `Ty::Tuple([Int, Str])` | `(Int, String)` |
| `Ty::Fn([Int], Bool, {})` | `(Int) -> Bool` |
| `Ty::Fn([Int], Bool, {"Net"})` | `(Int) -> Bool uses [Net]` |
| `Ty::Var(3)` | `?T3` |
| `Ty::Hole("h1")` | `?h1` |
| `Ty::Error` | `<error>` |

### Snapshot hashes

Function signatures (parameter types, return type, error set, CapSet, cost bound, generic constraints) are included in snapshot hashes. Body changes and `@allows` annotations are excluded. This ensures:

- API-breaking changes require explicit `--permit`.
- Implementation refactoring does not break downstream consumers.

### Machine-readable output

Type errors are emitted as structured JSON for Agent consumption:

```json
{"error": "type_mismatch", "context": "function `add`",
 "expected": "Int", "actual": "String",
 "location": "main.spore:5:12"}
```

## Diagnostics impact

### Error categories produced by the type checker

| Category | Example message |
|---|---|
| Type mismatch | `type mismatch in function 'add': expected 'Int', got 'String'` |
| Undefined variable | `undefined variable 'x'` |
| Arity mismatch | `function 'add' expects 2 arguments, got 3` |
| Missing capability | `missing capabilities [NetRead]: caller does not declare them` |
| Non-exhaustive match | `non-exhaustive match: missing variant 'Triangle'` |
| Cannot negate type | `cannot negate type 'String'` |
| Cannot apply `!` | `cannot apply '!' to type 'Int'` |
| Unknown field | `struct 'Point' has no field 'z'` |

### Dual-channel diagnostics

Every diagnostic is emitted in both machine-readable (JSON v0) and human-readable (Elm-style v2) formats. The type system provides:

- The **expected type** (from check mode / declared return type).
- The **actual type** (from synth mode / expression).
- The **context** (function name, expression location).
- **Suggestions** — functions in scope whose return type matches the expected type.

### Hole diagnostics

For each hole, the checker reports:

```text
Hole ?h1 in function `example`:
  expected type: Int
  available bindings: x: Int, y: String
  suggested fills: compute_value, default_int
```

## Drawbacks

1. **No subtyping lattice yet.** The lack of `Never <: τ` means diverging expressions in branches require special handling (currently unimplemented). Adding a proper bottom type will require modifying the unifier.

2. **No occurs check.** The unifier does not check for cyclic substitutions (`Var(0) ↦ List[Var(0)]`). This is safe given current usage patterns but would need to be added before supporting recursive anonymous types.

3. **Nominal rigidity.** The nominal-primary design means newtypes require explicit wrap/unwrap. This adds verbosity for simple delegation patterns. Anonymous records provide a structural escape hatch, but they cannot implement traits.

4. **CapSet as BTreeSet\<String\>.** String-based capability names lack static verification at the `Ty` level — a misspelled capability name is only caught when matching against registered capabilities, not during type construction.

5. **No higher-kinded types.** GATs + associated types cover most use cases, but abstracting over container kinds generically (functor-map over any container) requires either code generation or per-container implementations.

6. **Refinement types are unimplemented.** The L0 + L1 refinement vision is specified but not yet in the compiler. Users cannot currently express bounded numeric types or flow-sensitive narrowing.

## Alternatives considered

### Alternative 1: Structural typing as default (TypeScript / Go style)

**Rejected.** Structural typing makes capability safety impossible — two structurally identical types could accidentally satisfy each other's capability requirements. It also produces confusing error messages when two semantically different types happen to share the same shape.

**Decision:** Nominal-primary with anonymous structural records as an escape hatch.

### Alternative 2: Hindley–Milner global inference

**Rejected.** Full H-M inference infers function signatures, but this conflicts with Spore's "signatures are gravity centers" principle. Inferred signatures are:

- Not visible to Agents reading code.
- Unstable under refactoring (adding a statement can change the inferred type).
- Hard to explain when inference fails.

**Decision:** Bidirectional checking — signatures annotated, bodies inferred.

### Alternative 3: Higher-kinded types

**Rejected.** HKTs would allow abstracting over `Option`, `List`, `Result`, etc. generically. However:

- Capabilities replace the primary HKT use case (monad-based effect sequencing).
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

**Rejected as primary mechanism.** Spore unifies capabilities and traits instead of using a separate effect system. This provides:

- One mechanism for both "what does this type support" and "what does this context provide."
- Reuse of the trait resolver and coherence checker.
- Simpler mental model for users.

**Decision:** Capabilities = Traits. `uses [Cap]` is syntactic sugar for a trait bound on execution context.

### Alternative 6: Row-polymorphic capability sets

**Considered for future.** Making CapSets row-polymorphic would allow:

```spore
fn apply[C](f: Fn(x: Int) -> Int uses C, x: Int) -> Int uses C
```

This is compatible with the current design but not yet implemented. The string-based `BTreeSet` representation would need to be extended with capability variables.

## Prior art

### Rust

Spore's type system is most directly influenced by Rust:

- Nominal types with trait bounds.
- Associated types and GATs.
- Sealed enums with exhaustive pattern matching.
- No implicit conversions.

**Differences from Rust:** No lifetime system (Spore uses GC or region-based memory), no borrow checker, capabilities replace `unsafe` blocks, refinement types replace some `debug_assert!` patterns.

### Haskell / GHC

- Bidirectional type inference with explicit signatures was pioneered in GHC's `OutsideIn(X)` solver.
- Type holes (`_` in GHC) directly inspired Spore's `?hole` syntax.
- Spore explicitly rejects HKT and typeclasses-as-module-system in favor of simpler nominal traits.

### Liquid Haskell

- Refinement types attached to base types.
- Spore adopts the refinement syntax (`type Port = Int if ...`) but replaces the SMT backend with decidable predicates (L0) and abstract interpretation (L1).

### TypeScript

- Structural typing for anonymous records (Spore borrows this for the structural escape hatch).
- Spore rejects structural typing as the default due to capability safety concerns.

### Elm

- Elm-style error messages are the target for Spore's human-readable diagnostic channel.
- Elm's enforced exhaustive matching directly influenced Spore's sealed-enum design.

### Bidirectional type checking literature

- Pierce & Turner, "Local Type Inference" (2000).
- Dunfield & Krishnaswami, "Complete and Easy Bidirectional Typechecking for Higher-Rank Polymorphism" (2013).

Spore implements a simplified version: no higher-rank polymorphism, no impredicativity. Signatures provide the "check" direction; expressions provide the "synth" direction.

## Backward compatibility and migration

### This is the initial type system specification

Since this is the first formal type system specification (v0.1 → SEP), there is no prior specification to be backward-compatible with. The implemented `Ty` enum and checker in `spore-typeck` serve as the de facto baseline.

### Compatibility commitments

1. **Ty enum stability.** The variants `Int`, `Float`, `Bool`, `Str`, `Unit`, `Named`, `App`, `Tuple`, `Fn`, `Var`, `Hole`, `Error` are stable. New variants may be added (e.g., `Never`, `Record`) but existing variants will not be removed or renamed without a new SEP.

2. **CapSet representation.** `BTreeSet<String>` is the current representation. Future SEPs may introduce capability variables for row-polymorphic effects, but the concrete string-based API will remain supported.

3. **Two-pass checking.** The `register_item` → `check_fn` architecture is stable. Future passes (e.g., trait resolution, cost checking) will be added after these two, not replace them.

4. **Display format.** The canonical type display format (`Int`, `List[Int]`, `(Int) -> Bool uses [Net]`) is stable and may be relied upon by tools and diagnostics.

### Migration path for future features

| Feature | Migration strategy |
|---|---|
| `Never` type | Add `Ty::Never` variant; modify unifier to treat it as bottom type |
| Refinement types (L0) | Add `Ty::Refined(Box<Ty>, Predicate)` variant; extend `resolve_type` |
| Traits | Add trait registry and constraint solver; extend `register_item` |
| Const generics | Add `Ty::Const(value)` variant; extend `App` to accept const args |
| Anonymous records | Add `Ty::Record(BTreeMap<String, Ty>)` with width subtyping |

## Unresolved questions

1. **Occurs check.** Should the unifier include an occurs check now, or defer until recursive anonymous types are needed? The current approach is safe for non-recursive types but would loop on `Var(0) ↦ Tuple([Var(0)])`.

2. **CapSet in unification.** Currently, function type unification ignores CapSets (the `_` in `Fn(p1, r1, _), Fn(p2, r2, _)`). Should CapSets participate in unification, or remain checked separately? Separate checking is simpler but could miss capability mismatches in higher-order function arguments.

3. **Never type semantics.** When `Never` is added, how should it interact with unification? Options:
   - (a) `unify(τ, Never) = ok` for all `τ` (subtyping via unification).
   - (b) Separate subtype check before unification.
   - (c) Coercion insertion during checking.

4. **Generic syntax: square brackets vs angle brackets.** The implemented `Ty::App` uses parenthesized syntax in the AST (`List[Int]`), but the design document uses angle brackets (`List<T>`). Which surface syntax should be canonical? This SEP uses square brackets as the intended syntax; a separate SEP should finalize the concrete syntax.

5. **Refinement type representation.** Where do refinement predicates live in the `Ty` enum? Options:
   - (a) `Ty::Refined(Box<Ty>, Predicate)` — a wrapper around any base type.
   - (b) Store refinements in the `TypeRegistry` alongside the base type, not in `Ty` itself.
   - (c) Treat refined types as named types (`Port = Named("Port")`) with predicates stored separately.

6. **Trait method type checking.** The two-pass architecture registers function signatures but does not yet handle trait method signatures, default methods, or `impl` blocks. How should these be integrated into `register_item` and `check_fn`?

7. **Row-polymorphic capabilities.** Should capability sets support variables (e.g., `uses [C]` where `C` is a capability set variable)? This would enable generic higher-order functions that preserve their argument's capability requirements.

8. **Error type representation.** Error sets (`! [Err1, Err2]`) are not yet represented in the `Ty` enum. Should they be:
   - (a) A component of `Ty::Fn` (making it `Fn(params, ret, CapSet, ErrorSet)`).
   - (b) A separate `Ty::Fallible(Box<Ty>, ErrorSet)` wrapper.
   - (c) Tracked outside the type system in a parallel error-set registry.

9. **Variance.** Generic type parameters need variance annotations (covariant, contravariant, invariant) for soundness when subtyping is introduced. Should variance be inferred or declared?
