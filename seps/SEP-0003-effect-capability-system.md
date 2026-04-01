---
sep: 3
title: "SEP-0003: Effect & Capability System"
status: Draft
type: Standards Track
authors:
  - Spore maintainers
created: 2026-03-31
requires:
  - 2
discussion: "https://github.com/spore-lang/spore-evolution/discussions/3"
pr: null
superseded_by: null
---

# SEP-0003: Effect & Capability System

> **Executive Summary**: Defines Spore's effect system as a capability-based model with 10 atomic capabilities (Compute, Alloc, NetRead, NetWrite, FsRead, FsWrite, EnvRead, Clock, Random, Ffi). Capabilities compose algebraically (commutative, idempotent, associative) and are checked via subset inclusion — a function requiring capabilities S can only be called from a context providing S′ ⊇ S. Module-level `uses` declarations set the ambient capability ceiling.

## Summary

This SEP introduces Spore's **capability-based effect system**: a compile-time mechanism that tracks how functions interact with the outside world. Every function declares — via a `uses [...]` clause — the set of *atomic capabilities* it requires. The compiler verifies that a function body never exercises a capability absent from its declared set, auto-infers semantic properties (pure, deterministic, total) from that set, and uses set-inclusion as the basis for subtyping and capability narrowing.

The design is intentionally **flat and monomorphic**: capabilities are finite sets of atomic identifiers with no effect variables, no row types, and no effect polymorphism. Named aliases (`capability X = [A, B]`) provide ergonomics without adding expressiveness. Higher-order functions such as `map` accept only pure (`uses []`) closures; effectful iteration is expressed through `parallel_scope` + `spawn`.

---

## Motivation

Modern programs interleave pure computation with diverse side effects — file I/O, networking, mutable state, concurrency, randomness, process control. Without a disciplined tracking mechanism these effects become invisible at function boundaries, making it hard for both humans and automated agents to reason about what a function *can do*.

### Problems addressed

1. **Untracked side effects.** In most mainstream languages, any function can perform arbitrary I/O. A callee that silently writes to the filesystem or spawns threads violates the caller's assumptions.

2. **Fragile purity assumptions.** Optimisations such as memoisation, common-subexpression elimination, and automatic parallelisation require proof that a function is pure. Without compiler support, purity is enforced only by convention.

3. **Opaque higher-order functions.** When `map` or `fold` accept arbitrary closures, the caller loses all guarantees about the aggregate computation. A closure that performs network I/O inside `map` is a common source of performance surprises and non-determinism.

4. **Capability escalation.** Concurrent sub-tasks should not silently acquire capabilities that their parent never held. Without a formal narrowing rule, library code can grant capabilities that the application developer never intended.

5. **Agent-unfriendly code.** LLM-based code-generation agents filling Holes need machine-readable constraints on which effects are permissible at each program point. A formal capability set provides exactly this.

### Design goals

| Goal | Mechanism |
|------|-----------|
| Explicit effect tracking | `uses [...]` clause on every function |
| Zero-cost purity | Omitting `uses` ≡ `uses []` (pure) |
| Composable aliases | `capability` keyword for named groups |
| Sound subtyping | Set inclusion on capability sets |
| Auto-inferred properties | `pure`, `deterministic`, `total` derived from `uses` |
| Agent integration | Capability set emitted in `HoleReport` JSON |

---

## Guide-level explanation

### Declaring capabilities on functions

Every Spore function may carry a `uses` clause listing the atomic capabilities it requires:

```spore
fn read_config(path: String) -> Config ! [IoError, ParseError]
uses [FileRead]
{
    let content = read_file(path)
    parse_toml(content)
}
```

If a function needs no capabilities it is *pure* and the `uses` clause may be omitted entirely:

```spore
fn add(a: Int, b: Int) -> Int {
    a + b
}
// equivalent to: fn add(a: Int, b: Int) -> Int uses [] { a + b }
```

### Built-in atomic capabilities

Spore ships with the following atomic capabilities:

| Capability | Semantics | Typical operations |
|---|---|---|
| `FileRead` | Read from the filesystem | `read_file`, `list_dir` |
| `FileWrite` | Write to the filesystem | `write_file`, `create_dir`, `delete` |
| `NetRead` | Read from the network | `http.get`, `tcp.recv` |
| `NetWrite` | Write to the network | `http.post`, `tcp.send` |
| `StateRead` | Read mutable state | `state.get`, `cache.lookup` |
| `StateWrite` | Write mutable state | `state.set`, `cache.insert` |
| `Spawn` | Create concurrent tasks | `spawn { ... }` |
| `Clock` | Read system clock | `now()`, `elapsed()` |
| `Random` | Generate random values | `random()`, `uuid()` |
| `Compute` | Non-trivial pure computation | Compiler-implicit |
| `Exit` | Terminate the process | `exit()`, `abort()` |

### Defining capability aliases

The `capability` keyword creates a **named alias** that expands into a flat set of atomic capabilities:

```spore
capability FileIO = [FileRead, FileWrite]
capability DatabaseAccess = [NetRead, NetWrite, StateRead, StateWrite]
capability FullIO = [FileIO, NetRead, NetWrite]
```

Aliases expand recursively and flatten:

```text
FullIO → {FileIO, NetRead, NetWrite}
       → {FileRead, FileWrite, NetRead, NetWrite}
```

Aliases are purely syntactic sugar. After expansion, only atomic capabilities remain.

### Using capabilities in practice

```spore
capability DatabaseAccess = [NetRead, NetWrite, StateRead, StateWrite]

fn query_user(id: UserId) -> User ! [DbError, NotFound]
uses [DatabaseAccess]
{
    let conn = pool.get_connection()
    conn.query("SELECT * FROM users WHERE id = ?", id)
}
```

After alias expansion this is equivalent to `uses [NetRead, NetWrite, StateRead, StateWrite]`.

### Pure closures in higher-order functions

Higher-order combinators such as `map`, `filter`, and `fold` accept **only pure closures** — closures whose capability set is empty:

```spore
fn process_scores(scores: List[Int]) -> List[String] {
    scores
        .filter(|s| s >= 60)              // pure: (Int) -> Bool
        .map(|s| format("Pass: {}", s))   // pure: (Int) -> String
}
```

Attempting to pass an effectful closure is a compile error:

```spore
fn bad_example(scores: List[Int]) -> List[Unit]
uses [FileWrite]
{
    // ❌ ERROR: map requires a pure closure, but this closure uses [FileWrite]
    scores.map(|s| write_file("log.txt", s.to_string()))
}
```

### Effectful iteration with `parallel_scope` + `spawn`

When you need side effects during iteration, use the structured concurrency pattern:

```spore
fn fetch_all(urls: List[Url]) -> List[Response] ! [NetworkError]
uses [NetRead, Spawn]
{
    parallel_scope {
        let tasks = urls.map(|url| {
            spawn {
                // spawn body uses [NetRead], ⊆ parent {NetRead, Spawn}  ✓
                http.get(url)
            }
        })
        tasks.collect_results()
    }
}
```

Why does this type-check?

1. `fetch_all` declares `uses [NetRead, Spawn]`.
2. `spawn { ... }` requires `Spawn ∈ {NetRead, Spawn}` — satisfied.
3. Inside the spawn body, `http.get` requires `NetRead`; `{NetRead} ⊆ {NetRead, Spawn}` — satisfied.
4. The closure passed to `map` returns `Task[Response]`. The `spawn` expression itself is pure (it merely creates a task handle), so the closure satisfies `uses []`.

### Auto-inferred properties

The compiler automatically derives semantic properties from the declared capability set. No manual annotation is required:

| Declared `uses` | Inferred properties |
|---|---|
| `uses []` (or omitted) | pure, deterministic, total* |
| `uses [Compute]` | deterministic |
| `uses [FileRead]` | ¬pure, deterministic |
| `uses [Random]` | ¬pure, ¬deterministic |
| `uses [NetRead, Spawn]` | ¬pure, deterministic |

(*total requires a separate termination analysis; see Reference-level explanation §5.4.)

### Incomplete functions — missing `uses` declarations

A function that calls operations requiring capabilities but does **not** declare a `uses` clause is an *incomplete function*. The compiler treats this as an error with a fix suggestion:

```spore
fn save_data(data: Data) -> Unit {
    write_file("out.txt", serialize(data))
}
```

```text
error[cap-violation]: function body uses undeclared capability
  --> src/storage.spore:1:1
   |
 1 | fn save_data(data: Data) -> Unit {
   |    ^^^^^^^^^ no `uses` clause declared
 2 |     write_file("out.txt", serialize(data))
   |     ^^^^^^^^^^ requires FileWrite
   |
   = declared: [] (pure — no `uses` clause)
   = required: [FileWrite]
   = excess:   [FileWrite]
   = help: add a `uses` clause to the function signature:
   |
 1 | fn save_data(data: Data) -> Unit
 2 | uses [FileWrite]
   |
```

Running `sporec --fixes` auto-inserts the missing `uses` clause.

### Module-level `uses` declarations

A module may declare its capability ceiling with `module X uses [...]`:

```spore
module billing uses [NetRead, NetWrite, StateRead, StateWrite]
```

All functions within the module are constrained: their `uses` sets must be subsets of the module-level set. If a function exceeds the module ceiling the compiler emits a `cap-narrowing-violation` error.

The module-level `uses` clause is **optional**. When omitted the compiler auto-infers the module's capability ceiling as the union of all its functions' capability sets. Running `sporec --fixes` inserts the inferred declaration.

### `@allows` — restricting Hole candidates

The `@allows` annotation constrains which functions an AI agent (or developer) may use to fill a Hole. It acts as a filter on `candidate_functions` in the `HoleReport`:

```spore
fn process_input(raw: String) -> SafeInput ! [ValidationError] {
    @allows[validate, sanitize]
    ?clean_input
}
```

The generated `HoleReport` includes the restriction:

```json
{
  "hole": "clean_input",
  "expected_type": "SafeInput",
  "allows": ["validate", "sanitize"],
  "candidate_functions": [
    "validate(raw: String) -> SafeInput ! [ValidationError]",
    "sanitize(raw: String) -> SafeInput ! [ValidationError]"
  ]
}
```

Without `@allows`, all functions matching the type and capability constraints appear. With `@allows`, the candidate list is further filtered to only the named functions.

### Pure recursive function example — fibonacci

A pure recursive function requires no annotations:

```spore
fn fibonacci(n: Int) -> Int {
    match n {
        0 => 0,
        1 => 1,
        n => fibonacci(n - 1) + fibonacci(n - 2),
    }
}
```

Compiler inference output:

```text
uses []
// auto-inferred: pure, deterministic
// total: structural recursion on n (decreasing) — provable
cost ≤ O(2^n)
```

---

## Reference-level explanation

### 1. Atomic capability set

Let **E** be the universe of atomic capabilities. Each element of **E** is an indivisible identifier representing one way a program may interact with the external world.

A **capability set** *S* is a finite subset of **E**:

$$S \subseteq E, \quad |S| < \infty$$

The empty set `{}` denotes a pure function — no interaction with the outside world.

### 2. Formal effect algebra

Capability sets obey standard finite-set algebra:

| Property | Formula | Consequence |
|---|---|---|
| Commutativity | {A, B} = {B, A} | Declaration order is irrelevant |
| Idempotence | {A, A} = {A} | Duplicate declarations collapse |
| Associativity | Nested aliases flatten | `[FileIO, NetRead]` = `[FileRead, FileWrite, NetRead]` |
| Identity element | {} (empty set) | The identity for union: S ∪ {} = S |

#### Set operations

| Operation | Symbol | Use |
|---|---|---|
| Union | S₁ ∪ S₂ | Sequential composition, conditional branches |
| Subset | S₁ ⊆ S₂ | Subtype check, capability narrowing |
| Intersection | S₁ ∩ S₂ | Property inference |
| Difference | S₁ \ S₂ | Reserved; not currently exposed in syntax |

### 3. Capability alias definition and expansion

Given an alias definition:

$$\texttt{capability } C = [A_1, A_2, \ldots, A_n]$$

In any `uses` declaration:

$$\texttt{uses } [C] \equiv \texttt{uses } [A_1, A_2, \ldots, A_n]$$

Expansion is **recursive**: if any $A_i$ is itself an alias, it is expanded until every element is an atomic capability. The result is always a flat set.

**No capability variables exist.** All capability sets must be fully determined at compile time. There is no `uses E` generic parameter and no effect polymorphism.

### 4. Function types and CapSet encoding

#### 4.1 Complete function type

```text
(T₁, T₂, …, Tₙ) -> R  uses S  ! [E₁, E₂, …]
```

where:

- `T₁ … Tₙ` — parameter types
- `R` — return type
- `S` — capability set (CapSet)
- `[E₁ …]` — error type set

#### 4.2 Internal representation

In the compiler's type IR the function type is represented as:

```rust
Ty::Fn(Vec<Ty>, Box<Ty>, CapSet)
```

where `CapSet = BTreeSet<String>`. A `BTreeSet` is chosen over `HashSet` for deterministic ordering in diagnostics and serialisation.

#### 4.3 Shorthand

When the capability set is empty the `uses` clause may be omitted:

$$(T_1, T_2) \to R \equiv (T_1, T_2) \to R \ \textbf{uses}\ \{\}$$

### 5. Property auto-inference

The compiler derives semantic properties from the `uses` set via the property-inference function **𝒫**:

$$\mathcal{P}(\text{pure}, S) = \begin{cases} \text{true} & \text{if } S = \emptyset \\ \text{false} & \text{if } S \cap \{\text{FileRead, FileWrite, NetRead, NetWrite, StateRead, StateWrite}\} \neq \emptyset \end{cases}$$

$$\mathcal{P}(\text{deterministic}, S) = \begin{cases} \text{true} & \text{if } S \cap \{\text{Clock, Random}\} = \emptyset \\ \text{false} & \text{otherwise} \end{cases}$$

$$\mathcal{P}(\text{total}, S) = \text{determined by a separate termination analysis (see §5.4)}$$

#### 5.0 Edge cases in the `pure` formula

The `𝒫(pure, S)` function has a gap: when `S` is non-empty but contains only capabilities outside the I/O set `{FileRead, FileWrite, NetRead, NetWrite, StateRead, StateWrite}`, neither the `true` nor the `false` case applies directly. The following clarifications apply:

| Capability set S | pure? | Rationale |
|---|---|---|
| `{}` | true | No capabilities at all |
| `{Compute}` | true | `Compute` is not an I/O capability; it marks non-trivial pure computation |
| `{Clock}` | false | Clock reads the external world (system time) |
| `{Random}` | false | Random reads external entropy |
| `{Spawn}` | true | `spawn` merely creates a task descriptor (pure); the effect is deferred |
| `{Exit}` | false | `exit` terminates the process — an observable external effect |
| `{Compute, Spawn}` | true | Neither is an I/O capability |

The complete rule: `𝒫(pure, S) = true` iff `S ⊆ {Compute, Spawn}`. All other non-empty capability sets that intersect with any capability outside this "pure-compatible" subset yield `𝒫(pure, S) = false`.

#### 5.1 Implication chain

$$\text{pure} \implies \text{deterministic}$$

A pure function (`uses {}`) trivially satisfies the deterministic condition because the empty set has no intersection with `{Clock, Random}`.

#### 5.2 Properties that cannot be statically inferred

**Idempotency** cannot in general be derived from a capability set. It may be annotated via doc-comment:

```spore
/// @idempotent
fn sync_user(user_id: UserId) -> SyncResult ! [NetworkError]
uses [NetRead, NetWrite, StateRead, StateWrite]
{ ... }
```

**Totality** is provable by the compiler for structurally recursive functions (the recursive argument strictly decreases). Other functions require an explicit `@unbounded` annotation:

```spore
/// @unbounded
fn event_loop() -> Never
uses [NetRead, NetWrite]
{
    loop { handle_next_event() }
}
```

### 6. Subtyping and capability narrowing

#### 6.1 Subtype rule

Capability sets induce subtyping via set inclusion. Function types are **contravariant** in their capability parameter:

$$S_1 \subseteq S_2 \implies (\tau \to \rho \ \textbf{uses}\ S_1) <: (\tau \to \rho \ \textbf{uses}\ S_2)$$

A function that requires *fewer* capabilities is more general and can be used wherever a more-capable function is expected.

```text
                    S₁ ⊆ S₂
─────────────────────────────────────────  [CAP-SUB]
(T → R uses S₁) <: (T → R uses S₂)
```

As a corollary, pure functions are subtypes of all function types:

```text
─────────────────────────────────────────  [CAP-PURE]
(T → R uses {}) <: (T → R uses S)     ∀ S
```

#### 6.2 Capability narrowing in `parallel_scope`

A child task's capability set must be a subset of its parent's:

$$S_{\text{child}} \subseteq S_{\text{parent}}$$

This guarantees that sub-tasks never acquire capabilities beyond those granted to their parent.

### 7. Typing judgement

The standard judgement form is:

$$\Gamma;\ S \vdash e : T$$

Read: "Under type context Γ and capability set S, expression e has type T."

#### Core rules

```text
Γ; S ⊢ e₁ : T₁    Γ; S ⊢ e₂ : T₂
────────────────────────────────────────  [SEQ]
Γ; S ⊢ (e₁; e₂) : T₂


Γ; S ⊢ f : (T → R uses S_f)    Γ; S ⊢ x : T    S_f ⊆ S
───────────────────────────────────────────────────────────  [APP]
Γ; S ⊢ f(x) : R


────────────────────────────  [PURE-LITERAL]
Γ; S ⊢ 42 : Int      ∀ S
```

### 8. Capability composition rules

When multiple expressions are combined the compiler computes the composite capability set:

| Composition form | Capability computation |
|---|---|
| `A; B` | S_A ∪ S_B |
| `if c then A else B` | S_c ∪ S_A ∪ S_B |
| `match x { p₁ => A, p₂ => B, … }` | S_x ∪ S_A ∪ S_B ∪ … |
| `f(x)` where f `uses S_f` | Requires S_f ⊆ S_scope |
| `spawn { body }` where body `uses S_b` | Requires `Spawn ∈ S_scope` and S_b ⊆ S_scope |
| `let x = e₁ in e₂` | S_e₁ ∪ S_e₂ |

Formal rules for the two most important cases:

```text
Γ; S ⊢ A : T₁    Γ; S ⊢ B : T₂
──────────────────────────────────  [SEQ-CAP]
capabilities(A; B) = S_A ∪ S_B


Γ; S ⊢ c : Bool    Γ; S ⊢ A : T    Γ; S ⊢ B : T
────────────────────────────────────────────────────  [COND-CAP]
capabilities(if c then A else B) = S_c ∪ S_A ∪ S_B


f : (T → R uses S_f)    S_f ⊆ S_scope
──────────────────────────────────────  [CALL-CAP]
calling f in scope S_scope is allowed


Spawn ∈ S_scope    S_body ⊆ S_scope
──────────────────────────────────────  [SPAWN-CAP]
Γ; S_scope ⊢ spawn { body } : Task[T]
```

> **Note on spawn purity.** The `spawn` expression itself is **pure** — it merely creates a task descriptor (of type `Task[T]`). No side effect is executed at the point of `spawn`; the effect occurs when the task is later scheduled. This is why a closure containing only `spawn { ... }` satisfies `uses []` when passed to `map` or other pure-closure-requiring combinators.

### 9. Capability checking algorithm

The compiler performs capability checking during type-checking as a single pass:

1. **Alias expansion.** Every `uses` clause and every `capability` definition is recursively expanded to a flat set of atomic capabilities.

2. **Body capability collection.** For each function body, the compiler walks the expression tree and collects the union of capabilities required by every sub-expression (using the composition rules in §8).

3. **Subset check.** The collected set `S_body` is checked against the declared set `S_declared`:

$$S_{\text{body}} \subseteq S_{\text{declared}}$$

If the check fails, the compiler emits a `cap-violation` diagnostic listing the excess capabilities.

4. **Closure inference.** For closures, the compiler infers the minimal capability set from the closure body. This inferred set is used for subtype checking when the closure is passed to a higher-order function.

5. **`parallel_scope` narrowing.** Inside a `parallel_scope` block, each `spawn` body is checked to ensure its collected capabilities are a subset of the enclosing scope's declared set.

### 10. Closure capability capture

A closure defined within a context with capability set *S* has an inferred capability set *S'* where *S'* ⊆ *S*. The inference is determined by the capabilities actually exercised in the closure body:

```spore
fn example() -> Unit
uses [FileRead, NetRead]
{
    // Inferred type: (String) -> Data uses [NetRead]
    let fetch_fn = |url| http.get(url)

    // Inferred type: (Int) -> Int uses []  (pure)
    let double = |x| x * 2
}
```

### 11. Interaction with the Hole system

When the compiler encounters a Hole (`?name`), the generated `HoleReport` includes the capability set available at that program point:

```json
{
  "hole": "fetch_logic",
  "expected_type": "Data",
  "bindings": {
    "url": "Url",
    "timeout": "Duration"
  },
  "available_capabilities": ["NetRead"],
  "cost_budget": 5000,
  "candidate_functions": [
    "http.get(url: Url) -> Data ! [NetworkError] uses [NetRead]"
  ]
}
```

Filling a Hole is subject to:

$$S_{\text{fill}} \subseteq S_{\text{available}}$$

The Hole system filters candidate functions so that only those whose `uses S` satisfies `S ⊆ S_available` appear in the suggestion list.

#### 11.1 Hole capability-violation diagnostic

When an agent or developer fills a Hole with code that exceeds the available capabilities, the compiler emits a detailed diagnostic:

```text
ERROR [cap-violation] Hole ?fetch_logic filled code uses unauthorised capabilities:
  --> src/service.spore:15:5
   |
15 |     ?fetch_logic    // filled with: fetch_and_save(url)
   |     ^^^^^^^^^^^^ hole fill exceeds available capabilities
   |
   = available capabilities: [NetRead]
   = fill code requires:     [NetRead, FileWrite]
   = excess capabilities:    [FileWrite]
   = help: either add FileWrite to the enclosing function's `uses` clause,
     or choose a candidate that only requires [NetRead]
```

### 12. Interaction with the cost model

The cost model maintains a **four-dimensional cost vector**: `(compute, alloc, io, parallel)`.

| Dimension | Abbreviation | Meaning | Unit |
|---|---|---|---|
| Compute | `C` | CPU operation steps | op (operation) |
| Allocation | `A` | Heap memory allocation | cell (abstract memory unit) |
| I/O | `W` | Side-effect / external call count | call |
| Parallelism | `P` | Parallel execution width | lane |

Capability sets provide hard upper-bound constraints on these cost dimensions:

| Condition | Cost dimension constraint |
|---|---|
| `uses {}` | `io = 0` (guaranteed no I/O overhead) |
| S ∩ {NetRead, NetWrite, FileRead, FileWrite} ≠ ∅ | `io > 0` possible |
| `Spawn ∈ S` | `parallel > 0` possible |
| `uses [Compute]` | Only `compute` and `alloc` dimensions may be non-zero |

The relationship is a **necessary condition**: if the capability set excludes all I/O capabilities, the cost model's I/O dimension is provably zero.

$$S \cap \{\text{NetRead, NetWrite, FileRead, FileWrite}\} = \emptyset \implies \text{cost}_{\text{io}} = 0$$

### 13. Capability as a trait-like construct

Capabilities are *not* merely string tags — each capability is a **trait-like construct** whose methods carry a `self` parameter representing the runtime token that grants the capability:

```spore
capability FileRead {
    fn read_file(self, path: String) -> Bytes ! [IoError]
    fn list_dir(self, path: String) -> List[String] ! [IoError]
}

capability FileWrite {
    fn write_file(self, path: String, data: Bytes) -> Unit ! [IoError]
    fn create_dir(self, path: String) -> Unit ! [IoError]
    fn delete(self, path: String) -> Unit ! [IoError]
}
```

When a function declares `uses [FileRead]`, the compiler makes the `FileRead` capability token available as an implicit `self` receiver for the methods defined in that capability. This design unifies capability tracking with method dispatch: calling `read_file(path)` is sugar for invoking the `read_file` method on the ambient `FileRead` token.

Capability aliases remain purely syntactic:

```spore
capability FileIO = [FileRead, FileWrite]
```

This expands to the union of the two trait-like capabilities and does not define a new trait.

---

## Human experience impact

### Readability

The `uses` clause makes a function's external interactions visible at a glance. Developers reading unfamiliar code can immediately determine whether a function touches the network, writes files, or is pure without inspecting its body.

### Learnability

- **Zero-annotation start.** Newcomers write pure functions with no annotation at all. The `uses` clause appears only when the first side effect is introduced.
- **Flat model.** There are no effect variables, row types, or higher-kinded constructs to learn. The mental model is "list the things you need."
- **Familiar concept.** The capability set is analogous to permission declarations in mobile OSes (Android manifest, iOS entitlements), a concept most developers already understand.

### Ergonomics

- Capability aliases (`capability DatabaseAccess = [...]`) reduce boilerplate for common groups.
- Auto-inferred properties eliminate the need for manual `pure` / `deterministic` annotations.
- The compiler provides actionable diagnostics when a function body exceeds its declared capabilities.

### Potential friction

- Developers accustomed to unrestricted side effects may find the discipline burdensome initially.
- The prohibition on effectful closures in `map`/`filter` requires learning the `parallel_scope` + `spawn` pattern.

---

## Agent experience impact

### Structured capability information in HoleReport

LLM-based agents filling Holes receive the `available_capabilities` field in the JSON `HoleReport`. This enables agents to:

1. **Constrain code generation.** The agent knows which operations are permissible and avoids generating code that would fail capability checks.
2. **Filter candidate functions.** Only functions whose `uses S` satisfies S ⊆ S_available are presented as candidates.
3. **Self-verify before submission.** The agent can compare its generated code's capability requirements against the available set before proposing a fill.

### Deterministic verification

Because capability checking is a simple set-inclusion test, agents can perform the check locally without invoking the full compiler. This enables tight generate-verify loops.

### Reduced hallucination surface

The explicit capability set narrows the space of valid completions, reducing the likelihood that an agent generates plausible-looking but capability-violating code.

---

## Structured representation / protocol impact

### Function type serialisation

The canonical serialised form of a function type includes the CapSet:

```json
{
  "kind": "Fn",
  "params": ["Int", "Int"],
  "return": "Int",
  "capabilities": [],
  "errors": []
}
```

```json
{
  "kind": "Fn",
  "params": ["Url"],
  "return": "Response",
  "capabilities": ["NetRead"],
  "errors": ["NetworkError"]
}
```

### Capability alias registry

All capability alias definitions are collected into a structured registry available to tooling:

```json
{
  "aliases": {
    "FileIO": ["FileRead", "FileWrite"],
    "DatabaseAccess": ["NetRead", "NetWrite", "StateRead", "StateWrite"]
  }
}
```

### LSP extensions

The language server protocol integration should expose:

- Capability set in hover information for functions.
- Inferred properties (`pure`, `deterministic`, `total`) in hover tooltips.
- Quick-fix suggestions when a capability violation is detected (e.g., "Add `FileWrite` to the `uses` clause").

---

## Diagnostics impact

### New diagnostics

| Code | Severity | Message template |
|---|---|---|
| `cap-violation` | Error | Function body uses capability `{cap}` not declared in `uses` clause. Declared: `{declared}`. Required: `{required}`. Excess: `{excess}`. |
| `cap-closure-violation` | Error | Closure passed to `{fn_name}` must be pure (`uses []`), but it uses `{caps}`. |
| `cap-spawn-missing` | Error | `spawn` expression requires `Spawn` capability, but current scope declares `uses {scope_caps}`. |
| `cap-narrowing-violation` | Error | Spawn body uses `{child_caps}` which is not a subset of parent scope `{parent_caps}`. Excess: `{excess}`. |
| `cap-unknown` | Error | Unknown capability `{name}`. Did you mean `{suggestion}`? |
| `cap-alias-cycle` | Error | Capability alias `{name}` contains a cycle: `{cycle_path}`. |
| `cap-redundant` | Warning | Capability `{cap}` is declared but never used in the function body. |

### Diagnostic quality guidelines

1. **Always show the excess set.** When a subset check fails, display exactly which capabilities are missing from the declared set.
2. **Suggest fixes.** If the fix is to add a capability to the `uses` clause, provide a machine-applicable quick-fix.
3. **Show expansion.** When an alias is involved, show the expanded form so the user understands which atomic capability caused the violation.

Example diagnostic:

```text
error[cap-violation]: function body uses undeclared capability
  --> src/app.spore:12:5
   |
10 | fn process(data: Data) -> Result
11 | uses [FileRead]
   |       ^^^^^^^^ declared capabilities
12 |     write_file("out.txt", transform(data))
   |     ^^^^^^^^^^ requires FileWrite
   |
   = declared: [FileRead]
   = required: [FileRead, FileWrite]
   = excess:   [FileWrite]
   = help: add `FileWrite` to the `uses` clause:
   |
11 | uses [FileRead, FileWrite]
   |               ^^^^^^^^^^^
```

---

## Drawbacks

1. **Annotation overhead.** Functions with many capabilities require verbose `uses` clauses. Capability aliases mitigate this but do not eliminate it entirely.

2. **No effect polymorphism.** The deliberate omission of effect variables means that generic middleware functions (e.g., `with_timeout`, `retry`) cannot abstract over arbitrary capability sets. Each concrete instantiation must list its capabilities explicitly. This may lead to some code duplication in highly generic library code.

3. **Pure-only closures in combinators.** Requiring `map`/`filter`/`fold` to accept only pure closures is restrictive. The `parallel_scope` + `spawn` workaround is more verbose and requires understanding structured concurrency.

4. **No capability subtraction.** Users cannot write `uses [All \ Spawn]` ("everything except Spawn"). This means that functions needing nearly all capabilities must enumerate them individually.

5. **Alias is expansion only.** Capability aliases do not create new abstract capabilities. This prevents hiding implementation details behind an alias boundary — the caller always sees the expanded set.

6. **String-based CapSet.** Using `BTreeSet<String>` for the internal representation is simple but offers no compile-time interning or efficient bitset operations. This may need revisiting for large-scale codebases with many capabilities.

---

## Alternatives considered

### 1. Effect polymorphism (effect variables / row types)

Languages like Koka, Eff, and Frank support effect variables that allow abstracting over capability sets:

```text
fn with_timeout[E](f: () -> T uses E) -> T uses [E, Clock]
```

**Why rejected:** Effect polymorphism dramatically increases type-inference complexity and produces error messages that are difficult for non-experts to understand. Spore prioritises approachability and agent-friendliness over maximum expressiveness. The flat-set model covers the vast majority of practical use cases. Effect variables may be reconsidered as a future opt-in advanced feature.

### 2. Hierarchical capability model

Some systems organise capabilities into a hierarchy (e.g., `IO > FileIO > FileRead`). A function declaring `uses [IO]` would implicitly have all sub-capabilities.

**Why rejected:** Hierarchies introduce ordering disputes (is `Random` under `IO`?), make alias expansion non-trivial, and complicate subtype checks. The flat model avoids these issues entirely.

### 3. `with` clause for manual property annotation

An earlier design included a `with [pure, deterministic]` clause for manual property declaration.

**Why rejected:** Properties can be reliably inferred from the `uses` set (see §5). The `with` clause added redundancy and a maintenance burden — if the `uses` set changed, the `with` clause could become inconsistent.

### 4. Effect handlers

Algebraic effect handlers (as in Koka or OCaml 5) allow capabilities to be intercepted and reinterpreted at runtime.

**Why rejected:** Effect handlers require significant runtime support and make compilation and optimisation considerably harder. Spore targets ahead-of-time compilation with predictable performance. Capability checking in Spore is purely static.

### 5. Monadic effects (Haskell IO monad)

Encoding effects in the type system via monads (e.g., `IO a`, `State s a`).

**Why rejected:** Monad transformers are notoriously difficult to compose and produce deeply nested types. The flat capability set is simpler and more intuitive for the target audience.

---

## Prior art

| System | Approach | Relation to this SEP |
|---|---|---|
| **Koka** | Algebraic effects with row-polymorphic effect types | Spore takes the same "effects in the type" philosophy but drops polymorphism in favour of flat sets |
| **Eff** | First-class algebraic effects and handlers | Spore omits handlers entirely; capabilities are static-only |
| **Rust** | No built-in effect system; `unsafe` is the only capability marker | Spore generalises `unsafe` to a full capability vocabulary |
| **Haskell** | `IO` monad, mtl-style monad transformers | Spore replaces monadic encoding with flat set annotation |
| **OCaml 5** | Algebraic effects for concurrency | Spore's `Spawn` capability is analogous but purely static |
| **Scala (ZIO)** | Environment type `R` in `ZIO[R, E, A]` | Similar in spirit; ZIO's `R` is an intersection type, Spore uses a flat set |
| **Unison** | Ability types (algebraic effects) | Close conceptual ancestor; Spore simplifies by removing polymorphism |
| **Android Manifest** | Permission declarations | Same "declare what you need" philosophy at the OS level |
| **Wasm Component Model** | Import/export capabilities | Static capability declaration before instantiation |
| **Java (checked exceptions)** | `throws` clause | Spore's `uses` is analogous but tracks capabilities rather than error types |

---

## Backward compatibility and migration

### This is a new language

Spore is a new language and this SEP defines a core feature of its type system. There is no pre-existing code to migrate.

### Interaction with SEP-0002

This SEP depends on SEP-0002 (Type System). The `CapSet` is integrated into the function type representation defined there:

```rust
enum Ty {
    Int,
    Bool,
    String,
    Fn(Vec<Ty>, Box<Ty>, CapSet),  // params, return, capabilities
    // ...
}
```

### Future extensibility

- **New atomic capabilities.** New capabilities (e.g., `GpuAccess`, `Audit`) can be added to the universe **E** without breaking existing code — functions that do not use them are unaffected.
- **Platform capability ceilings.** A future SEP on the platform system may define module-level capability ceilings. Functions within such modules would be required to have `uses S` where S ⊆ S_platform_ceiling.
- **Effect variables (possible future SEP).** If demand arises for effect polymorphism, it can be introduced as an opt-in feature layered on top of the flat-set foundation without invalidating existing code.

---

## Unresolved questions

### 1. Capability subtraction syntax

Should Spore support a subtraction syntax such as `uses [All \ Spawn]`? This depends on the definition of the universal set **E**, which may vary across platforms. Current decision: **not supported**. Developers must enumerate capabilities explicitly.

### 2. Platform capability ceilings

How does a module-level `platform [Web]` declaration interact with function-level `uses` clauses? Two options:

- **Intersection model:** The effective capability set is `S_function ∩ S_platform`.
- **Constraint model:** The compiler checks `S_function ⊆ S_platform` and rejects violations.

The constraint model (static rejection) is preferred but needs formal specification.

### 3. Capability scoping and imports

Can third-party libraries define new atomic capabilities? If so, how are they scoped and imported? Should there be a namespace mechanism (`mylib::MyCapability`)?

### 4. Granularity of file-system capabilities

Is `FileRead` / `FileWrite` the right granularity, or should capabilities be path-scoped (e.g., `FileRead("/etc/config")`)? Path-scoping adds expressiveness but complicates the set algebra.

### 5. Relationship between `Compute` and `uses []`

Currently `uses []` implies pure, and `uses [Compute]` allows non-trivial computation. Should `Compute` be implicit in all functions (since all functions compute), or should it be reserved for functions that perform expensive computation? The distinction matters for the cost model.

### 6. Capability evolution and deprecation

When an atomic capability is deprecated or split (e.g., `FileIO` split into `FileRead` + `FileWrite`), what migration tooling is needed? Should the compiler support `@deprecated` annotations on capability definitions?

### 7. Interaction with generics

How do generic type parameters interact with capability sets? For example:

```spore
fn apply[T, R](f: (T) -> R, x: T) -> R {
    f(x)
}
```

This currently works only with pure `f`. If `f` has capabilities, should `apply` need to declare them? Without effect polymorphism, the answer is that `apply` must be specialised for each capability set, which may require monomorphisation or overloading.

### 8. Runtime capability tokens

Should capability tokens have a runtime representation (e.g., for dependency injection in tests), or are they purely a compile-time concept? A hybrid model where capabilities are erased by default but can be reified for testing purposes may be desirable.

---

## Appendix A: Formal notation quick reference

| # | Notation | Meaning |
|---|----------|---------|
| 1 | **E** | Universe of atomic capabilities |
| 2 | S, S₁, S₂ | Capability sets (finite subsets of **E**) |
| 3 | {} or ∅ | Empty capability set (pure function) |
| 4 | S₁ ⊆ S₂ | S₁ is a subset of S₂ |
| 5 | S₁ ∪ S₂ | Union of S₁ and S₂ |
| 6 | S₁ ∩ S₂ | Intersection of S₁ and S₂ |
| 7 | (T → R uses S) | Function type: parameter T, return R, capability set S |
| 8 | Γ; S ⊢ e : T | Typing judgement: under context Γ and capability set S, expression e has type T |
| 9 | 𝒫(prop, S) | Property inference function: determines property `prop` from capability set S |
| 10 | <: | Subtype relation |
| 11 | (C, A, W, P) | Four-dimensional cost vector: compute(op), alloc(cell), io(call), parallel(lane) |
| 12 | `capability C = [A₁, ..., Aₙ]` | Named alias definition expanding to a flat set of atomic capabilities |
