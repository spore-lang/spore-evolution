---
sep: 3
title: "SEP-0003: Effect System"
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

# SEP-0003: Effect System

> **Executive Summary**: Defines Spore's effect system as a flat effect-set model with 10 built-in intent-oriented atomic effects (Console, FileRead, FileWrite, NetConnect, NetListen, Env, Spawn, Clock, Random, Exit) plus user-defined effects. The canonical surface syntax uses explicit `effect` declarations, `perform Effect.op(...)`, top-level `handler`, and `handle { ... } with { ... }`, while semantic checking remains a subset test over effect sets. Concrete grammar is centralized in SEP-0001; this SEP specifies effect algebra, handler semantics, narrowing rules, and diagnostics.

## Summary

This SEP introduces Spore's **effect system**: a compile-time mechanism that tracks how functions interact with the outside world. Every function declares — via a `uses [...]` clause — the set of *atomic effects* it requires. The compiler verifies that a function body never exercises an effect absent from its declared set, auto-infers semantic properties (pure, deterministic, total) from that set, and uses set-inclusion as the basis for subtyping and effect narrowing.

The built-in effect vocabulary is **intent-oriented**: each built-in effect answers "What does this code intend to do with the outside world?" Pure computation is the default state — no effect declaration is needed for it. Mutable state is tracked by the language semantics, not by built-in external effect names. In compiler internals and tooling protocols, these effect names form the effect set used for subset checks, platform ceilings, and machine-readable fields such as `effects`.

The design is intentionally **flat and monomorphic**: effect sets are finite sets of atomic identifiers with no effect variables, no row types, and no effect polymorphism. Named aliases (`effect X = A | B`) provide ergonomics without adding expressiveness. Higher-order functions such as `map` accept only pure (`uses []`) closures; effectful iteration is expressed through `parallel_scope` + `spawn`.

Concrete surface syntax for `effect`, `handler`, `perform`, and `handle ... with` is defined in SEP-0001. This SEP focuses on semantics, algebra, typing, protocol fields, and diagnostics.

---

## Motivation

Modern programs interleave pure computation with diverse side effects — file I/O, networking, mutable state, concurrency, randomness, process control. Without a disciplined tracking mechanism these effects become invisible at function boundaries, making it hard for both humans and automated agents to reason about what a function *can do*.

### Problems addressed

1. **Untracked side effects.** In most mainstream languages, any function can perform arbitrary I/O. A callee that silently writes to the filesystem or spawns threads violates the caller's assumptions.

2. **Fragile purity assumptions.** Optimisations such as memoisation, common-subexpression elimination, and automatic parallelisation require proof that a function is pure. Without compiler support, purity is enforced only by convention.

3. **Opaque higher-order functions.** When `map` or `fold` accept arbitrary closures, the caller loses all guarantees about the aggregate computation. A closure that performs network I/O inside `map` is a common source of performance surprises and non-determinism.

4. **Effect escalation.** Concurrent sub-tasks should not silently acquire effects that their parent never held. Without a formal narrowing rule, library code can grant effects that the application developer never intended.

5. **Agent-unfriendly code.** LLM-based code-generation agents filling Holes need machine-readable constraints on which effects are permissible at each program point. A formal effect set provides exactly this.

### Design goals

| Goal | Mechanism |
|------|-----------|
| Explicit effect tracking | `uses [...]` clause on every function |
| Zero-cost purity | Omitting `uses` ≡ `uses []` (pure) |
| Composable aliases | `effect` keyword for named groups and aliases |
| Sound subtyping | Set inclusion on effect sets |
| Auto-inferred properties | `pure`, `deterministic`, `total` derived from `uses` |
| Agent integration | `available_effects` emitted in `HoleReport` JSON |

---

## Guide-level explanation

### Declaring effects on functions

Every Spore function may carry a `uses` clause listing the atomic effects it requires:

```spore
effect FileRead {
    fn read_file(path: Str) -> Str ! IoError
}

fn read_config(path: Str) -> Config ! IoError | ParseError
uses [FileRead]
{
    let content = perform FileRead.read_file(path)
    parse_toml(content)
}
```

A function that interacts with the terminal declares `Console`:

```spore
effect Console {
    fn println(msg: Str) -> ()
}

fn greet(name: Str) uses [Console] {
    perform Console.println("Hello, " + name)
}
```

If a function needs no effects it is *pure* and the `uses` clause may be omitted entirely:

```spore
fn add(a: Int, b: Int) -> Int {
    a + b
}
// equivalent to: fn add(a: Int, b: Int) -> Int uses [] { a + b }
```

### Built-in atomic effects

Spore ships with the following intent-oriented atomic effects. Each one answers: "What does this code intend to do with the outside world?"

| Effect | Intent | Typical operations |
|---|---|---|
| `Console` | User interaction (terminal I/O) | `println`, `eprintln`, `read_line` |
| `FileRead` | Persistent data access | `File.read`, `Dir.list` |
| `FileWrite` | Persistent data modification | `File.write`, `Dir.create`, `File.delete` |
| `NetConnect` | External communication (outbound) | `http.get`, `http.post`, `tcp.connect` |
| `NetListen` | Service provision (inbound) | `tcp.listen`, `http.serve` |
| `Env` | Configuration access | `Env.get`, `Env.vars` |
| `Spawn` | Subprocess management | `Cmd.exec`, `spawn { ... }` |
| `Clock` | Time-dependent computation | `now()`, `elapsed()` |
| `Random` | Non-deterministic computation | `random()`, `uuid()` |
| `Exit` | Process lifecycle control | `exit()`, `abort()` |

`Exit` authorizes explicit process termination. Startup contracts, runtime exit
propagation, and host exit-code conversion are Platform/runtime concerns
specified in SEP-0008 rather than in this effect SEP.

### Design rationale: intent-oriented built-in effects

The guiding principle is: **each built-in effect answers "What does this code intend to do with the outside world?"** This leads to several deliberate design choices:

1. **No `Compute` effect.** Pure computation is the default state — no effect declaration is needed. Every function can compute; effects describe what *additional* external powers a function needs beyond pure computation. A function with `uses []` (or no `uses` clause) is pure and can compute freely.

2. **No `StateRead`/`StateWrite`.** Mutable state is tracked by the language semantics, not by built-in external effect names. The built-in effects describe interactions with the *external world* — the filesystem, the network, the terminal, the clock. Internal mutable state (for example, a local cache) is an implementation detail, not an intent to interact with the outside world.

3. **`NetConnect`/`NetListen` instead of `NetRead`/`NetWrite`.** The old names described data direction, but the real intent distinction is *client vs server*. An HTTP client both reads and writes the network, but its intent is "connect to an external service." Similarly, a server both reads and writes, but its intent is "listen for incoming connections."

4. **`Console` for terminal I/O.** `println("hello")` is user interaction, not file writing, even though stdout is technically a file descriptor. Distinguishing terminal I/O from filesystem I/O reflects a real difference in intent.

5. **`Env` for environment variables.** Reading environment variables is configuration access, distinct from reading files. Separating `Env` from `FileRead` enables finer-grained control.

### Platform mapping: basic-cli

The `basic-cli` Platform currently maps its package modules to built-in effects as follows:

| Operation | Required effect |
|---|---|
| `basic_cli.stdout.print`, `basic_cli.stdout.println`, `basic_cli.stdout.eprint`, `basic_cli.stdout.eprintln` | `Console` |
| `basic_cli.stdin.read_line` | `Console` |
| `basic_cli.file.file_read`, `basic_cli.file.file_exists`, `basic_cli.file.file_stat` | `FileRead` |
| `basic_cli.file.file_write` | `FileWrite` |
| `basic_cli.dir.dir_list` | `FileRead` |
| `basic_cli.dir.dir_mkdir` | `FileWrite` |
| `basic_cli.env.env_get`, `basic_cli.env.env_set` | `Env` |
| `basic_cli.cmd.process_run`, `basic_cli.cmd.process_run_status` | `Spawn` |
| `basic_cli.cmd.exit` | `Exit` |

### Defining effect aliases

The `effect` keyword creates a **named alias** that expands into a flat set of atomic effects:

```spore
effect FileIO = FileRead | FileWrite
effect CLI = Console | FileRead | FileWrite | Env | Spawn | Exit
effect Server = NetListen | FileRead | FileWrite | Clock | Random
effect HttpClient = NetConnect | Clock
```

Aliases expand recursively and flatten:

```text
CLI → {Console, FileRead, FileWrite, Env, Spawn, Exit}
```

Aliases are purely syntactic sugar in `uses [...]`: after expansion, only atomic
effects remain. The current implementation also ships a small builtin alias
hierarchy for `IO`, `FileIO`, and `NetIO`, but **same-module declarations
shadow those builtin names**. In other words, a local `effect IO = Console` or
`effect IO { ... }` is treated as that local declaration, not as the builtin
filesystem/network bundle.

### Using effects in practice

```spore
effect HttpClient = NetConnect | Clock

fn query_api(url: Url) -> Data ! NetworkError
uses [HttpClient]
{
    let response = http.get(url)
    parse_json(response.body)
}
```

After alias expansion this is equivalent to `uses [NetConnect, Clock]`.

`perform` and inline `on Effect.op(...)` arms are stricter: they target
**declared effect interfaces**, not aliases or undeclared pseudo-effect paths.
`uses [Alias]` may cover `perform Console.println(...)` after alias expansion,
but `perform Alias.println(...)` is not the canonical surface.

### Pure closures in higher-order functions

Higher-order combinators such as `map`, `filter`, and `fold` accept **only pure closures** — closures whose effect set is empty:

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
fn fetch_all(urls: List[Url]) -> List[Response] ! NetworkError
uses [NetConnect, Spawn]
{
    parallel_scope {
        let tasks = urls.map(|url| {
            spawn {
                // spawn body uses [NetConnect], ⊆ parent {NetConnect, Spawn}  ✓
                http.get(url)
            }
        })
        tasks.collect_results()
    }
}
```

Why does this type-check?

1. `fetch_all` declares `uses [NetConnect, Spawn]`.
2. `spawn { ... }` requires `Spawn ∈ {NetConnect, Spawn}` — satisfied.
3. Inside the spawn body, `http.get` requires `NetConnect`; `{NetConnect} ⊆ {NetConnect, Spawn}` — satisfied.
4. The closure passed to `map` returns `Task[Response]`. The `spawn` expression itself is pure (it merely creates a task handle), so the closure satisfies `uses []`.

### Auto-inferred properties

The compiler automatically derives semantic properties from the declared effect set. No manual annotation is required:

| Declared `uses` | Inferred properties |
|---|---|
| `uses []` (or omitted) | pure, deterministic, total* |
| `uses [Console]` | ¬pure |
| `uses [FileRead]` | ¬pure, deterministic |
| `uses [Random]` | ¬pure, ¬deterministic |
| `uses [NetConnect, Spawn]` | ¬pure, deterministic |

(*total requires a separate termination analysis; see Reference-level explanation §5.4.)

### Incomplete functions — missing `uses` declarations

A function that calls operations requiring effects but does **not** declare a `uses` clause is an *incomplete function*. The compiler treats this as an error with a fix suggestion:

```spore
fn save_data(data: Data) -> Unit {
    write_file("out.txt", serialize(data))
}
```

```text
error[effect-violation]: function body uses undeclared effect
  --> src/storage.sp:1:1
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

### No module-level `uses` declarations

Spore does **not** currently standardize module-level `uses` ceilings or carriers. Source files declare no ambient effect budget. Effect checking happens at:

1. function signatures (`uses [...]`)
2. project / Platform boundaries

Diagnostics and tooling should therefore not synthesize or rely on `module X uses [...]` declarations.

### `@allows` — restricting Hole candidates

The `@allows` annotation constrains which functions an AI agent (or developer) may use to fill a Hole. In the shared SEP-0005 hole protocol, this shows up as a filtered `candidates` list rather than as a separate bespoke schema.

```spore
fn process_input(raw: String) -> SafeInput ! ValidationError {
    @allows[validate, sanitize]
    ?clean_input
}
```

A representative machine-readable view is:

```json
{
  "name": "clean_input",
  "display_name": "?clean_input",
  "expected_type": "SafeInput",
  "candidates": [
    {
      "name": "validate",
      "type_match": 1.0,
      "required_effects_fit": 1.0,
      "overall": 1.0
    },
    {
      "name": "sanitize",
      "type_match": 1.0,
      "required_effects_fit": 1.0,
      "overall": 1.0
    }
  ]
}
```

Without `@allows`, all functions matching the type and effect constraints may appear. With `@allows`, the candidate list is further filtered to only the named functions.

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

### 1. Atomic effect set

Let **E** be the universe of atomic effects. Each element of **E** is an indivisible identifier representing one way a program may interact with the external world.

An **effect set** *S* is a finite subset of **E**:

$$S \subseteq E, \quad |S| < \infty$$

The empty set `{}` denotes a pure function — no interaction with the outside world.

### 2. Formal effect algebra

Effect sets obey standard finite-set algebra:

| Property | Formula | Consequence |
|---|---|---|
| Commutativity | {A, B} = {B, A} | Declaration order is irrelevant |
| Idempotence | {A, A} = {A} | Duplicate declarations collapse |
| Associativity | Nested aliases flatten | `[FileIO, NetConnect]` = `[FileRead, FileWrite, NetConnect]` |
| Identity element | {} (empty set) | The identity for union: S ∪ {} = S |

#### Set operations

| Operation | Symbol | Use |
|---|---|---|
| Union | S₁ ∪ S₂ | Sequential composition, conditional branches |
| Subset | S₁ ⊆ S₂ | Subtype check, effect narrowing |
| Intersection | S₁ ∩ S₂ | Property inference |
| Difference | S₁ \ S₂ | Reserved; not currently exposed in syntax |

### 3. Effect alias definition and expansion

Given an alias definition:

$$\texttt{effect } C = A_1 \mid A_2 \mid \ldots \mid A_n$$

In any `uses` declaration:

$$\texttt{uses } [C] \equiv \texttt{uses } [A_1, A_2, \ldots, A_n]$$

Expansion is **recursive**: if any $A_i$ is itself an alias, it is expanded
until every element is an atomic effect. The result is always a flat set.

The shipped implementation also reserves builtin aliases `IO`, `FileIO`, and
`NetIO` for convenience expansion, but those names are **not global keywords**:
same-module declared effects and effect aliases with the same names shadow the
builtin hierarchy.

**No effect variables exist.** All effect sets must be fully determined at compile time. There is no `uses E` generic parameter and no effect polymorphism.

### 3.1 Declared effects, imports, and `perform`

The canonical checked path for `perform` is:

1. the current effect set must contain the named effect after alias
   expansion, and
2. the effect name must resolve to a declared effect/interface with a known
   operation signature.

That rule applies equally to inline handler arms such as
`on Console.println(msg) => ...`.

Imported `pub effect` interfaces preserve their operation signatures across
module boundaries, so cross-module `perform Effect.op(...)` is typechecked
against the imported signature rather than against an untyped name stub.
Ambiguous imported same-name effects with different signatures are rejected.

### 4. Function types and EffectSet encoding

#### 4.1 Complete function type

```text
(T₁, T₂, …, Tₙ) -> R  uses S  ! E₁ | E₂ | …
```

where:

- `T₁ … Tₙ` — parameter types
- `R` — return type
- `S` — effect set (EffectSet)
- `[E₁ …]` — error type set

#### 4.2 Internal representation

In the compiler's type IR the function type is represented as:

```rust
Ty::Fn(Vec<Ty>, Box<Ty>, EffectSet)
```

where `EffectSet = BTreeSet<String>`. A `BTreeSet` is chosen over `HashSet` for deterministic ordering in diagnostics and serialisation.

#### 4.3 Shorthand

When the effect set is empty the `uses` clause may be omitted:

$$(T_1, T_2) \to R \equiv (T_1, T_2) \to R \ \textbf{uses}\ \{\}$$

### 5. Property auto-inference

The compiler derives semantic properties from the `uses` set via the property-inference function **𝒫**:

$$\mathcal{P}(\text{pure}, S) = \begin{cases} \text{true} & \text{if } S = \emptyset \\ \text{true} & \text{if } S \subseteq \{\text{Spawn}\} \\ \text{false} & \text{otherwise} \end{cases}$$

$$\mathcal{P}(\text{deterministic}, S) = \begin{cases} \text{true} & \text{if } S \cap \{\text{Clock, Random}\} = \emptyset \\ \text{false} & \text{otherwise} \end{cases}$$

$$\mathcal{P}(\text{total}, S) = \text{determined by a separate termination analysis (see §5.4)}$$

#### 5.0 Edge cases in the `pure` formula

The complete rule: `𝒫(pure, S) = true` iff `S ⊆ {Spawn}`. Pure computation requires no declared effect — it is the default. `Spawn` is pure-compatible because `spawn` merely creates a task descriptor; the effect is deferred. All other built-in effects represent interactions with the external world and therefore make a function impure.

| Effect set S | pure? | Rationale |
|---|---|---|
| `{}` | true | No effects at all |
| `{Spawn}` | true | `spawn` merely creates a task descriptor (pure); the effect is deferred |
| `{Console}` | false | Console interacts with the terminal — an external I/O channel |
| `{Clock}` | false | Clock reads the external world (system time) |
| `{Random}` | false | Random reads external entropy |
| `{Env}` | false | Env reads the process environment — an external configuration source |
| `{Exit}` | false | `exit` terminates the process — an observable external effect |
| `{NetConnect}` | false | Outbound network access is external I/O |

#### 5.1 Implication chain

$$\text{pure} \implies \text{deterministic}$$

A pure function (`uses {}`) trivially satisfies the deterministic condition because the empty set has no intersection with `{Clock, Random}`.

#### 5.2 Properties that cannot be statically inferred

**Idempotency** cannot in general be derived from an effect set. It may be annotated via doc-comment:

```spore
/// @idempotent
fn sync_user(user_id: UserId) -> SyncResult ! NetworkError
uses [NetConnect, FileRead]
{ ... }
```

**Totality** is provable by the compiler for structurally recursive functions (the recursive argument strictly decreases). Other functions require an explicit `@unbounded` annotation:

```spore
/// @unbounded
fn event_loop() -> Never
uses [NetListen, Console]
{
    loop { handle_next_event() }
}
```

### 6. Subtyping and effect narrowing

#### 6.1 Subtype rule

Effect sets induce subtyping via set inclusion. Function types are **contravariant** in their effect parameter:

$$S_1 \subseteq S_2 \implies (\tau \to \rho \ \textbf{uses}\ S_1) <: (\tau \to \rho \ \textbf{uses}\ S_2)$$

A function that requires *fewer* effects is more general and can be used wherever a more-capable function is expected.

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

#### 6.2 Effect narrowing in `parallel_scope`

A child task's effect set must be a subset of its parent's:

$$S_{\text{child}} \subseteq S_{\text{parent}}$$

This guarantees that sub-tasks never acquire effects beyond those granted to their parent.

### 7. Typing judgement

The standard judgement form is:

$$\Gamma;\ S \vdash e : T$$

Read: "Under type context Γ and effect set S, expression e has type T."

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

### 8. Effect composition rules

When multiple expressions are combined the compiler computes the composite effect set:

| Composition form | Effect computation |
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
effects(A; B) = S_A ∪ S_B


Γ; S ⊢ c : Bool    Γ; S ⊢ A : T    Γ; S ⊢ B : T
────────────────────────────────────────────────────  [COND-CAP]
effects(if c then A else B) = S_c ∪ S_A ∪ S_B


f : (T → R uses S_f)    S_f ⊆ S_scope
──────────────────────────────────────  [CALL-CAP]
calling f in scope S_scope is allowed


Spawn ∈ S_scope    S_body ⊆ S_scope
──────────────────────────────────────  [SPAWN-CAP]
Γ; S_scope ⊢ spawn { body } : Task[T]
```

> **Note on spawn purity.** The `spawn` expression itself is **pure** — it merely creates a task descriptor (of type `Task[T]`). No side effect is executed at the point of `spawn`; the effect occurs when the task is later scheduled. This is why a closure containing only `spawn { ... }` satisfies `uses []` when passed to `map` or other pure-closure-requiring combinators.

### 9. Effect checking algorithm

The compiler performs effect checking during type-checking as a single pass:

1. **Alias expansion.** Every `uses` clause and every `effect` definition is recursively expanded to a flat set of atomic effects.

2. **Body effect collection.** For each function body, the compiler walks the expression tree and collects the union of effects required by every sub-expression (using the composition rules in §8).

3. **Subset check.** The collected set `S_body` is checked against the declared set `S_declared`:

$$S_{\text{body}} \subseteq S_{\text{declared}}$$

If the check fails, the compiler emits a `effect-violation` diagnostic listing the excess effects.

4. **Closure inference.** For closures, the compiler infers the minimal effect set from the closure body. This inferred set is used for subtype checking when the closure is passed to a higher-order function.

5. **`parallel_scope` narrowing.** Inside a `parallel_scope` block, each `spawn` body is checked to ensure its collected effects are a subset of the enclosing scope's declared set.

### 10. Closure effect capture

A closure defined within a context with effect set *S* has an inferred effect set *S'* where *S'* ⊆ *S*. The inference is determined by the effects actually exercised in the closure body:

```spore
fn example() -> Unit
uses [FileRead, NetConnect]
{
    // Inferred type: (String) -> Data uses [NetConnect]
    let fetch_fn = |url| http.get(url)

    // Inferred type: (Int) -> Int uses []  (pure)
    let double = |x| x * 2
}
```

### 11. Interaction with the Hole system

When the compiler encounters a Hole (`?name`), the shared SEP-0005 hole object includes the effect set available at that program point under the field name `available_effects`:

```json
{
  "name": "fetch_logic",
  "display_name": "?fetch_logic",
  "expected_type": "Data",
  "bindings": {
    "url": "Url",
    "timeout": "Duration"
  },
  "available_effects": ["NetConnect"],
  "cost_budget": {
    "budget_total": 5000,
    "cost_before_hole": 0,
    "budget_remaining": 5000
  },
  "candidates": [
    {
      "name": "http.get",
      "type_match": 1.0,
      "required_effects_fit": 1.0,
      "overall": 1.0
    }
  ]
}
```

Filling a Hole is subject to:

$$S_{\text{fill}} \subseteq S_{\text{available}}$$

The Hole system filters candidate functions so that only those whose `uses S` satisfies `S ⊆ S_available` appear in the suggestion list.

#### 11.1 Hole effect-violation diagnostic

When an agent or developer fills a Hole with code that exceeds the available set, the compiler emits a detailed diagnostic:

```text
ERROR [effect-violation] Hole ?fetch_logic filled code uses unauthorised effects:
  --> src/service.sp:15:5
   |
15 |     ?fetch_logic    // filled with: fetch_and_save(url)
   |     ^^^^^^^^^^^^ hole fill exceeds available effects
   |
   = available effects: [NetConnect]
   = fill code requires:     [NetConnect, FileWrite]
   = excess effects:    [FileWrite]
   = help: either add FileWrite to the enclosing function's `uses` clause,
     or choose a candidate that only requires [NetConnect]
```

### 12. Interaction with the cost model

The cost model maintains a **four-dimensional cost vector**: `(compute, alloc, io, parallel)`.

| Dimension | Abbreviation | Meaning | Unit |
|---|---|---|---|
| Compute | `C` | CPU operation steps | op (operation) |
| Allocation | `A` | Heap memory allocation | cell (abstract memory unit) |
| I/O | `W` | Side-effect / external call count | call |
| Parallelism | `P` | Parallel execution width | lane |

Effect sets provide hard upper-bound constraints on these cost dimensions:

| Condition | Cost dimension constraint |
|---|---|
| `uses {}` | `io = 0` (guaranteed no I/O overhead) |
| S ∩ {NetConnect, NetListen, FileRead, FileWrite, Console} ≠ ∅ | `io > 0` possible |
| `Spawn ∈ S` | `parallel > 0` possible |

The relationship is a **necessary condition**: if the effect set excludes all I/O effects, the cost model's I/O dimension is provably zero.

$$S \cap \{\text{NetConnect, NetListen, FileRead, FileWrite, Console}\} = \emptyset \implies \text{cost}_{\text{io}} = 0$$

### 13. Effects as typed constructs

Effects are not merely string tags — each effect is a **typed construct** whose methods define the operations available when the effect is in scope:

```spore
effect Console {
    fn println(msg: Str) -> ()
    fn eprintln(msg: Str) -> ()
    fn read_line() -> Str ! IoError
}

effect FileRead {
    fn read_file(path: Str) -> Str ! IoError
    fn list_dir(path: Str) -> List[Str] ! IoError
}

effect FileWrite {
    fn write_file(path: Str, data: Str) -> () ! IoError
    fn create_dir(path: Str) -> () ! IoError
    fn delete(path: Str) -> () ! IoError
}

effect Env {
    fn get(name: Str) -> Option[Str]
    fn vars() -> List[(Str, Str)]
}
```

Declaring `uses [FileRead]` authorizes the effect, but operations remain explicit: `perform FileRead.read_file(path)` dispatches to the active `FileRead` handler. Canonical v0.1 semantics require the corresponding `effect` interface to be declared explicitly; undeclared pseudo-effect paths are compatibility-only.

Effect aliases are part of the committed v0.1 surface:

```spore
effect FileIO = FileRead | FileWrite
```

This expands semantically to the union of the two effects and does not define a new operation surface of its own.

### 14. Effect handlers

Effect handlers provide concrete implementations for effect operations, enabling testability, mockability, and platform abstraction:

#### Handler definition

```spore
handler Console as MockConsole(output: List[Str]) {
    fn println(msg: Str) -> () { self.output.push(msg) }
    fn read_line() -> Str ! IoError { "mock input" }
}

handler FileRead as RealFileRead(root: Str) {
    fn read_file(path: Str) -> Str ! IoError {
        platform.fs.read(self.root + "/" + path)
    }
    fn list_dir(path: Str) -> List[Str] ! IoError {
        platform.fs.list(self.root + "/" + path)
    }
}
```

#### Handler binding

The canonical handler form is `handle { ... } with { ... }`. The `with` block may contain inline effect arms via `on Effect.op(...) => ...` and/or named handler installations via `use HandlerName { ... }`. The `use` payload initializes the handler instance fields declared in `handler <Effect> as <HandlerName>(...)`, and duplicate matches for the same `Effect.op` inside one `with` block are errors.

```spore
// Bind a single named handler
handle {
    greet("world")
} with {
    use MockConsole { output: [] }
}

// Bind multiple named handlers
handle {
    app.run()
} with {
    use RealFileRead { root: "/srv/app" }
    use MockConsole { output: [] }
}

// Inline handler arms remain available
handle {
    perform Console.println("hello")
} with {
    on Console.println(msg) => {}
}
```

#### User-defined effects (allowed from v1)

Users may define their own effects from the first version of Spore:

```spore
effect RateLimit {
    fn check_limit(key: Str) -> Bool
}

handler RateLimit as FixedDecisionRateLimit(allowed: Bool) {
    fn check_limit(key: Str) -> Bool {
        self.allowed
    }
}
```

---

## Human experience impact

### Readability

The `uses` clause makes a function's external interactions visible at a glance. Developers reading unfamiliar code can immediately determine whether a function touches the network, writes files, or is pure without inspecting its body.

### Learnability

- **Zero-annotation start.** Newcomers write pure functions with no annotation at all. The `uses` clause appears only when the first side effect is introduced.
- **Flat model.** There are no effect variables, row types, or higher-kinded constructs to learn. The mental model is "list the things you need."
- **Familiar concept.** The effect set is analogous to permission declarations in mobile OSes (Android manifest, iOS entitlements), a concept most developers already understand.

### Ergonomics

- Effect aliases (`effect CLI = Console | FileRead | FileWrite | ...`) reduce boilerplate for common groups.
- Auto-inferred properties eliminate the need for manual `pure` / `deterministic` annotations.
- The compiler provides actionable diagnostics when a function body exceeds its declared effects.

### Potential friction

- Developers accustomed to unrestricted side effects may find the discipline burdensome initially.
- The prohibition on effectful closures in `map`/`filter` requires learning the `parallel_scope` + `spawn` pattern.

---

## Agent experience impact

### Structured effect information in HoleReport

LLM-based agents filling Holes receive the `available_effects` field in the shared SEP-0005 hole object. This enables agents to:

1. **Constrain code generation.** The agent knows which operations are permissible and avoids generating code that would fail effect checks.
2. **Filter candidate functions.** Only functions whose `uses S` satisfies S ⊆ S_available are presented as candidates.
3. **Self-verify before submission.** The agent can compare its generated code's effect requirements against the available set before proposing a fill.

### Deterministic verification

Because effect checking is a simple set-inclusion test, agents can perform the check locally without invoking the full compiler. This enables tight generate-verify loops.

### Reduced hallucination surface

The explicit effect set narrows the space of valid completions, reducing the likelihood that an agent generates plausible-looking but effect-violating code.

---

## Structured representation / protocol impact

### Function type serialisation

The canonical serialised form of a function type includes the EffectSet:

```json
{
  "kind": "Fn",
  "params": ["Int", "Int"],
  "return": "Int",
  "effects": [],
  "errors": []
}
```

```json
{
  "kind": "Fn",
  "params": ["Url"],
  "return": "Response",
  "effects": ["NetConnect"],
  "errors": ["NetworkError"]
}
```

### Effect alias registry

All effect alias definitions are collected into a structured registry available to tooling:

```json
{
  "aliases": {
    "FileIO": ["FileRead", "FileWrite"],
    "CLI": ["Console", "FileRead", "FileWrite", "Env", "Spawn", "Exit"],
    "Server": ["NetListen", "FileRead", "FileWrite", "Clock", "Random"],
    "HttpClient": ["NetConnect", "Clock"]
  }
}
```

### LSP extensions

The language server protocol integration should expose effect information through the shared hover and diagnostics pipeline described in SEP-0006:

- Effect set in hover information for functions.
- Inferred properties (`pure`, `deterministic`, `total`) in hover tooltips.
- Quick-fix suggestions when an effect violation is detected (e.g., "Add `FileWrite` to the `uses` clause").

---

## Diagnostics impact

### New diagnostics

| Code | Severity | Message template |
|---|---|---|
| `effect-violation` | Error | Function body uses effect `{cap}` not declared in `uses` clause. Declared: `{declared}`. Required: `{required}`. Excess: `{excess}`. |
| `cap-closure-violation` | Error | Closure passed to `{fn_name}` must be pure (`uses []`), but it uses `{caps}`. |
| `cap-spawn-missing` | Error | `spawn` expression requires `Spawn` effect, but current scope declares `uses {scope_caps}`. |
| `cap-narrowing-violation` | Error | Spawn body uses `{child_caps}` which is not a subset of parent scope `{parent_caps}`. Excess: `{excess}`. |
| `cap-unknown` | Error | Unknown effect `{name}`. Did you mean `{suggestion}`? |
| `cap-alias-cycle` | Error | Effect alias `{name}` contains a cycle: `{cycle_path}`. |
| `cap-redundant` | Warning | Effect `{cap}` is declared but never used in the function body. |

### Diagnostic quality guidelines

1. **Always show the excess set.** When a subset check fails, display exactly which effects are missing from the declared set.
2. **Suggest fixes.** If the fix is to add an effect to the `uses` clause, provide a machine-applicable quick-fix.
3. **Show expansion.** When an alias is involved, show the expanded form so the user understands which atomic effect caused the violation.

Example diagnostic:

```text
error[effect-violation]: function body uses undeclared effect
  --> src/app.sp:12:5
   |
10 | fn process(data: Data) -> Result
11 | uses [FileRead]
   |       ^^^^^^^^ declared effects
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

1. **Annotation overhead.** Functions with many effects require verbose `uses` clauses. Effect aliases mitigate this but do not eliminate it entirely.

2. **No effect polymorphism.** The deliberate omission of effect variables means that generic middleware functions (e.g., `with_timeout`, `retry`) cannot abstract over arbitrary effect sets. Each concrete instantiation must list its effects explicitly. This may lead to some code duplication in highly generic library code.

3. **Pure-only closures in combinators.** Requiring `map`/`filter`/`fold` to accept only pure closures is restrictive. The `parallel_scope` + `spawn` workaround is more verbose and requires understanding structured concurrency.

4. **No effect subtraction.** Users cannot write `uses [All \ Spawn]` ("everything except Spawn"). This means that functions needing nearly all effects must enumerate them individually.

5. **Alias is expansion only.** Effect aliases do not create new abstract effects. This prevents hiding implementation details behind an alias boundary — the caller always sees the expanded set.

6. **String-based EffectSet.** Using `BTreeSet<String>` for the internal representation is simple but offers no compile-time interning or efficient bitset operations. This may need revisiting for large-scale codebases with many effects.

---

## Alternatives considered

### 1. Effect polymorphism (effect variables / row types)

Languages like Koka, Eff, and Frank support effect variables that allow abstracting over effect sets:

```text
fn with_timeout[E](f: () -> T uses E) -> T uses [E, Clock]
```

**Why rejected:** Effect polymorphism dramatically increases type-inference complexity and produces error messages that are difficult for non-experts to understand. Spore prioritises approachability and agent-friendliness over maximum expressiveness. The flat-set model covers the vast majority of practical use cases. Effect variables may be reconsidered as a future opt-in advanced feature.

### 2. Hierarchical effect model

Some systems organise effects into a hierarchy (e.g., `IO > FileIO > FileRead`). A function declaring `uses [IO]` would implicitly have all sub-effects.

**Why rejected:** Hierarchies introduce ordering disputes (is `Random` under `IO`?), make alias expansion non-trivial, and complicate subtype checks. The flat model avoids these issues entirely.

### 3. `with` clause for manual property annotation

An earlier design included a `with [pure, deterministic]` clause for manual property declaration.

**Why rejected:** Properties can be reliably inferred from the `uses` set (see §5). The `with` clause added redundancy and a maintenance burden — if the `uses` set changed, the `with` clause could become inconsistent.

### 4. Effect handlers

Algebraic effect handlers (as in Koka or OCaml 5) allow effects to be intercepted and reinterpreted at runtime.

**Why accepted:** Effect handlers provide critical benefits that outweigh their implementation cost:

1. **Testability** — Mock handlers enable deterministic testing of effectful code without special test frameworks.
2. **Mockability** — Any effect can be replaced with a mock implementation at the call site.
3. **Platform abstraction** — The same user code runs on different platforms by swapping handlers (e.g., browser vs. server filesystem).
4. **Colorless functions** — Unlike async/await, effect handlers do not bifurcate the function space.

Spore's handler model is intentionally simpler than full algebraic effects: handlers are lexical, non-resumable, and one-shot. A matching handler arm computes the value of the corresponding `perform` expression directly; there is no continuation capture or `resume()` path in canonical v0.1 semantics.

Syntax: `effect` defines operations, `handler` provides implementations, `handle ... with` binds handlers at call sites. See §13-14 for full details.

### 5. Monadic effects (Haskell IO monad)

Encoding effects in the type system via monads (e.g., `IO a`, `State s a`).

**Why rejected:** Monad transformers are notoriously difficult to compose and produce deeply nested types. The flat effect set is simpler and more intuitive for the target audience.

---

## Prior art

| System | Approach | Relation to this SEP |
|---|---|---|
| **Koka** | Algebraic effects with row-polymorphic effect types | Spore takes the same "effects in the type" philosophy with flat sets and simplified handlers (no continuations) |
| **Eff** | First-class algebraic effects and handlers | Spore adopts simplified handlers (no continuations); effects are statically checked with runtime handler dispatch |
| **Rust** | No built-in effect system; `unsafe` is the only effect marker | Spore generalises `unsafe` to a full effect vocabulary |
| **Haskell** | `IO` monad, mtl-style monad transformers | Spore replaces monadic encoding with flat set annotation |
| **OCaml 5** | Algebraic effects for concurrency | Spore's `Spawn` effect is analogous; Spore adopts simplified handlers without continuations |
| **Scala (ZIO)** | Environment type `R` in `ZIO[R, E, A]` | Similar in spirit; ZIO's `R` is an intersection type, Spore uses a flat set |
| **Unison** | Ability types (algebraic effects) | Close conceptual ancestor; Spore simplifies by removing polymorphism |
| **Android Manifest** | Permission declarations | Same "declare what you need" philosophy at the OS level |
| **Wasm Component Model** | Import/export effects | Static effect declaration before instantiation |
| **Java (checked exceptions)** | `throws` clause | Spore's `uses` is analogous but tracks effects rather than error types |

---

## Backward compatibility and migration

### This is a new language

Spore is a new language and this SEP defines a core feature of its type system. There is no pre-existing code to migrate.

### Interaction with SEP-0002

This SEP depends on SEP-0002 (Type System). The `EffectSet` is integrated into the function type representation defined there:

```rust
enum Ty {
    Int,
    Bool,
    String,
    Fn(Vec<Ty>, Box<Ty>, EffectSet),  // params, return, effects
    // ...
}
```

### Future extensibility

- **New atomic effects.** New effects (e.g., `GpuAccess`, `Audit`) can be added to the universe **E** without breaking existing code — functions that do not use them are unaffected.
- **Platform effect ceilings.** A future SEP on the platform system may define module-level effect ceilings. Functions within such modules would be required to have `uses S` where S ⊆ S_platform_ceiling.
- **Effect variables (possible future SEP).** If demand arises for effect polymorphism, it can be introduced as an opt-in feature layered on top of the flat-set foundation without invalidating existing code.

---

## Unresolved questions

### 1. Effect subtraction syntax

Should Spore support a subtraction syntax such as `uses [All \ Spawn]`? This depends on the definition of the universal set **E**, which may vary across platforms. Current decision: **not supported**. Developers must enumerate effects explicitly.

### 2. Platform effect ceilings

How does a module-level `platform [Web]` declaration interact with function-level `uses` clauses? Two options:

- **Intersection model:** The effective effect set is `S_function ∩ S_platform`.
- **Constraint model:** The compiler checks `S_function ⊆ S_platform` and rejects violations.

The constraint model (static rejection) is preferred but needs formal specification.

### 3. Effect scoping and imports

Can third-party libraries define new atomic effects? If so, how are they scoped and imported? Should there be a namespace mechanism (`mylib::MyEffect`)?

### 4. Granularity of file-system effects

Is `FileRead` / `FileWrite` the right granularity, or should effects be path-scoped (e.g., `FileRead("/etc/config")`)? Path-scoping adds expressiveness but complicates the set algebra.

### 5. Granularity of `Console` effect

Should `Console` be split further (e.g., `ConsoleRead` for stdin vs `ConsoleWrite` for stdout/stderr)? A single `Console` is simpler and covers the common case where terminal I/O is bidirectional, but finer granularity may be useful for sandboxing scenarios where a program should print output but not read input.

### 6. Effect evolution and deprecation

When an atomic effect is deprecated or split (e.g., `FileIO` split into `FileRead` + `FileWrite`), what migration tooling is needed? Should the compiler support `@deprecated` annotations on effect definitions?

### 7. Interaction with generics

How do generic type parameters interact with effect sets? For example:

```spore
fn apply[T, R](f: (T) -> R, x: T) -> R {
    f(x)
}
```

This currently works only with pure `f`. If `f` has effects, should `apply` need to declare them? Without effect polymorphism, the answer is that `apply` must be specialised for each effect set, which may require monomorphisation or overloading.

### 8. Runtime effect tokens

Should effect tokens have a runtime representation (e.g., for dependency injection in tests), or are they purely a compile-time concept? A hybrid model where effects are erased by default but can be reified for testing purposes may be desirable.

---

## Appendix A: Formal notation quick reference

| # | Notation | Meaning |
|---|----------|---------|
| 1 | **E** | Universe of atomic effects |
| 2 | S, S₁, S₂ | Effect sets (finite subsets of **E**) |
| 3 | {} or ∅ | Empty effect set (pure function) |
| 4 | S₁ ⊆ S₂ | S₁ is a subset of S₂ |
| 5 | S₁ ∪ S₂ | Union of S₁ and S₂ |
| 6 | S₁ ∩ S₂ | Intersection of S₁ and S₂ |
| 7 | (T → R uses S) | Function type: parameter T, return R, effect set S |
| 8 | Γ; S ⊢ e : T | Typing judgement: under context Γ and effect set S, expression e has type T |
| 9 | 𝒫(prop, S) | Property inference function: determines property `prop` from effect set S |
| 10 | <: | Subtype relation |
| 11 | (C, A, W, P) | Four-dimensional cost vector: compute(op), alloc(cell), io(call), parallel(lane) |
| 12 | `effect C = A₁ | A₂ | ... | Aₙ` | Named alias definition expanding to a flat set of atomic effects |
