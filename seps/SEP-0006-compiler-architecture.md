---
sep: 6
title: "SEP-0006: Compiler Architecture"
status: Draft
type: Standards Track
authors:
  - Spore maintainers
created: 2026-03-31
requires:
  - 1
  - 2
  - 3
  - 4
  - 5
discussion: "https://github.com/spore-lang/spore-evolution/discussions/6"
pr: null
superseded_by: null
---

# SEP-0006: Compiler Architecture

> **Executive Summary**: Defines a 6-phase compiler pipeline (Lex → Parse → Resolve → TypeCheck → Lower → Codegen) with SEP-aligned diagnostic codes organized by category — E0xxx (type errors), C0xxx (capability violations), K0xxx (cost budget), M0xxx (module errors), W0xxx (warnings). Supports NDJSON watch mode for IDE integration, content-addressed caching via signature and implementation hashes, and a `--verbose` output mode for detailed diagnostic context.

## Summary

This SEP specifies the architecture of the Spore compiler (`sporec`), covering the
complete compilation pipeline from source text to native code. The design is
organized around three intermediate representations — **AST**, **HIR**, and
**TypedHIR** — with **Cranelift IR** serving as the low-level backend
representation. Five major passes (lex, parse, resolve+desugar,
typecheck+capcheck+costcheck, codegen) transform source programs through these
layers.

Incremental compilation is achieved through the **salsa** framework with a
two-tier content-addressed hashing strategy: **sig hash** (computed at the
Resolve layer) controls downstream recompilation, and **impl hash** (computed at
the TypeCheck layer) controls codegen caching. A **watch mode** provides
real-time diagnostics via human-readable terminal output or machine-consumable
NDJSON events.

The Proof-of-Concept (PoC) phase uses a tree-walking interpreter; Cranelift
codegen is deferred to the prototype phase.

---

## Motivation

A language that targets both human developers and AI agents as first-class users
needs a compiler whose architecture is:

1. **Transparent** — every compilation stage produces an observable, queryable
   representation so that diagnostics can pinpoint *exactly* what went wrong,
   where, and why.
2. **Incremental** — developers and agents iterate rapidly; the compiler must
   recompile only what changed, propagating invalidation no further than
   necessary.
3. **Multi-audience** — diagnostics must serve terminal users (concise, colored),
   IDE clients (LSP-compatible JSON), CI pipelines (streaming NDJSON), and agents
   (structured data with inference chains, candidate lists, and machine-applicable
   fixes).
4. **Lean** — Spore has no borrow checker, no comptime evaluation, and no
   lifetime analysis. The IR stack should reflect this simplicity: three layers
   are sufficient where Rust needs five and Zig needs four.

Existing compiler architectures either carry unnecessary complexity (Rust's MIR
for borrow checking, Zig's ZIR for comptime) or are too simplistic for Spore's
needs (Gleam's two-layer AST lacks a desugared IR). This SEP defines a pipeline
tuned precisely to Spore's feature set: algebraic types, capabilities, cost
models, holes, and content-addressed modules.

---

## Guide-level explanation

### Compiling a Spore program

A developer interacts with the toolchain through both `spore` and `sporec`:

```bash
# Project-aware build
spore build

# Check without codegen
spore check src/main.sp

# Watch mode — recompile on save, show diagnostics in real time
spore watch src/main.sp

# Watch mode with JSON output for agents / IDEs
spore watch --json src/main.sp

# Explicit-input compiler invocation
sporec compile src/main.sp

# Explain an error code
sporec explain E0301

# Query a specific hole
sporec query-hole --json src/main.sp tax_logic
```

### What the developer sees

**On success:**

```text
$ spore build
  Compiling main (src/main.sp)
  Compiling http (src/net/http.sp)
  Compiling auth (src/auth/login.sp)
    Finished build in 1.4s — 3 modules, 0 errors, 0 warnings
```

**On error (default mode):**

```text
error[E0301]: type mismatch
  --> src/billing.sp:42:22
   |
42 |     charge(card, "fifty dollars")
   |                  ^^^^^^^^^^^^^^^ expected `Money`, found `String`
   |
help: try `Money.from_string("fifty dollars")`
```

**In watch mode:**

```text
$ spore watch src/main.sp
[watch] Watching project: ./my-project (42 modules)
[watch] ✓ Initial compilation complete (1.2s), 0 errors, 2 warnings, 5 holes

[watch] Waiting for file changes...

[watch] ─── Change detected ─────────────────────
[watch] File changed: src/auth/login.sp
[watch] Recompiling: src/auth/login.sp ... OK (34ms)
[watch] sig hash unchanged → skipping downstream
  ✓ 0 errors, 2 warnings, 4 holes (was: 5)
```

### Error output modes

| Mode | Flag | Audience | Content |
|------|------|----------|---------|
| **Default** | *(none)* | Developers, agents | Rust-style concise text with color and help suggestions |
| **Verbose** | `--verbose` | Developers debugging complex errors | Default + inference chains + candidate types + capability/cost context |
| **JSON** | `--json` | CI/CD, scripts, LSP, agents | LSP-compatible JSON with Spore extensions — the superset of all information |

The relationship is: `Default ⊂ --verbose ⊂ --json`. JSON contains everything;
verbose adds analysis detail to default; default is the minimal actionable view.

---

## Reference-level explanation

### Pipeline overview

```text
Source Text (.sp files)
    │
    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Pass 1: LEX                                                            │
│  Source text → Token stream (with Span)                                 │
│  ─ Whitespace-aware, tracks file ID + byte offsets                      │
└──────────────────────────────────────────────────────────────────────────┘
    │  Token Stream
    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Pass 2: PARSE                                                          │
│  Token stream → AST (untyped, source-faithful, preserves all sugar)     │
│  ─ Pratt parser for expressions                                         │
│  ─ Every node wrapped in Spanned<T> for precise error reporting         │
└──────────────────────────────────────────────────────────────────────────┘
    │  AST
    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Pass 3: RESOLVE + DESUGAR                                              │
│  AST → HIR (desugared, names resolved)                                  │
│  ─ Name resolution: every identifier → DefId                            │
│  ─ Import resolution: module paths → concrete references                │
│  ─ Visibility checking: pub / pub(pkg) / private                        │
│  ─ Desugar: |>, ?, f"...", t"..." → canonical forms                     │
│  ─ Cycle detection in dependency graph                                  │
│  ─ Hole registration: record ?name positions and scopes                 │
│  ─ ** sig hash computed here **                                         │
└──────────────────────────────────────────────────────────────────────────┘
    │  HIR + sig hash
    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Pass 4: TYPECHECK + CAPCHECK + COSTCHECK                               │
│  HIR → TypedHIR (fully typed, capability-verified, cost-verified)       │
│  ─ Bidirectional type inference (signatures annotated, bodies inferred)  │
│  ─ Trait / Capability resolution (Capability = Trait)                    │
│  ─ Associated types + GAT instantiation                                 │
│  ─ Const generics evaluation                                            │
│  ─ Exhaustiveness checking (match expressions)                          │
│  ─ Error set propagation and consistency (! Errors)                   │
│  ─ Refinement types: L0 decidable predicates + L1 abstract propagation  │
│  ─ Capability check: body uses ⊆ declared uses, module ceiling check    │
│  ─ Cost check: abstract interpretation of 4D cost vector                 │
│  ─ Hole report generation with full context                             │
│  ─ ** impl hash computed here **                                        │
└──────────────────────────────────────────────────────────────────────────┘
    │  TypedHIR + impl hash
    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Pass 5: CODEGEN                                                        │
│  TypedHIR → Cranelift IR → Native Code                                  │
│  ─ Cranelift IR serves as LIR (no separate low-level IR)                │
│  ─ Function-level granularity (fits content-addressed caching)          │
│  ─ Tail-call optimization (TCO) applied here                            │
│  ─ Pattern matching lowered to branches/jumps                           │
│  ─ [PoC phase: tree-walking interpreter instead]                        │
└──────────────────────────────────────────────────────────────────────────┘
    │
    ▼
  Native executable / object code
```

### IR layers

#### Layer 1: AST (Abstract Syntax Tree)

**Purpose:** Source-faithful representation for error reporting, IDE support, and
formatting tools.

Properties:

- 1:1 correspondence with source text
- All nodes carry `Span` (file ID + byte offset range)
- **Preserves all syntactic sugar:** `|>`, `?`, `f"..."`, `t"..."`
- Used for: precise error location reporting, syntax highlighting, code
  formatting (`spore fmt`)

Core data structures:

```text
Spanned<T> { node: T, span: Span }
Span { file: FileId, start: u32, end: u32 }

Module { items: Vec<Spanned<Item>> }
Item = FnDef | StructDef | TypeDef | CapabilityDef | Import | ...
FnDef {
    name, params, return_type, error_set,
    where_clause, cost_clause, uses_clause,
    body
}
Expr = Literal | Ident | BinOp | UnaryOp | Call
     | Pipe | TryOp | FString | TString
     | Match | If | Lambda | Block | Hole | ...
```

#### Layer 2: HIR (High-level IR)

**Purpose:** Simplified, canonical representation with all names resolved and
all sugar removed. This is the first "semantic" representation.

The Resolve pass performs:

- **Name resolution:** every identifier bound to a unique `DefId`
- **Import resolution:** module paths → concrete module references
- **Visibility checking:** `pub` / `pub(pkg)` / `private`
- **Circular dependency detection**
- **Hole recording:** marks `?name` positions with current scope information

The Desugar pass (merged into Resolve) canonicalizes all syntactic sugar:

| Sugar | Desugared form |
|-------|---------------|
| `a \|> f(b)` | `f(a, b)` |
| `expr?` | `match expr { Ok(v) => v, Err(e) => return Err(e.into()) }` |
| `f"hello {name}"` | `format("hello {}", name)` |
| `t"hello {name}"` | `Template([Literal("hello "), Interpolation(name)])` |

**sig hash is computed at this layer.** It covers:

- Function name, parameter types, return type
- Error set declarations
- Effect / capability declarations
- Cost declarations

It does **not** cover function bodies. When sig hash is unchanged, downstream
dependent modules skip resolve and type-check entirely.

#### Layer 3: TypedHIR (Typed High-level IR)

**Purpose:** Fully type-checked, capability-verified, cost-verified IR. This is
the input to codegen.

The unified TypeCheck pass performs:

| Sub-pass | Responsibility |
|----------|---------------|
| **Type inference** | Bidirectional: signatures fully annotated, function bodies inferred |
| **Trait resolution** | Trait/Capability resolution, associated types, GAT instantiation |
| **Const generics** | Evaluation of compile-time constant generic parameters |
| **Exhaustiveness** | Verify match expressions cover all variants |
| **Error sets** | Propagation and consistency of `! ErrorType` declarations |
| **Refinement types** | L0 decidable predicates + L1 abstract interpretation propagation |
| **CapCheck** | Function body capability usage ⊆ declared `uses` set; module ceiling check |
| **CostCheck** | Abstract interpretation of 4D cost vector: `compute(op) + alloc(cell) + io(call) + parallel(lane)`; verify ≤ declared bound |
| **Hole reports** | Generate full context: type, available bindings, capability set, cost budget, candidate functions |

Capability checking is merged into TypeCheck because `Capability = Trait` in
Spore — capability resolution shares the same infrastructure as trait resolution.

Cost checking is merged into TypeCheck because cost analysis depends on resolved
types and call-graph information already computed during type checking.

**impl hash is computed at this layer.** It covers the fully type-checked HIR.
Partial functions (containing holes) have `impl hash = None`. When impl hash is
unchanged, codegen is skipped entirely — the cached Cranelift output is reused.

#### Cranelift IR as LIR

There is **no separate low-level IR**. Cranelift IR serves as the LIR:

- Cranelift operates at function-level granularity, which fits naturally with
  Spore's content-addressed caching model
- Pattern matching is lowered to branch/jump instructions during codegen
- Tail-call optimization (TCO) is applied during the TypedHIR → Cranelift
  translation
- In the PoC phase, a tree-walking interpreter replaces Cranelift; the codegen
  pass is a clean abstraction boundary

### Design rationale for IR layer count

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    Why 3 IR layers, not more?                       │
├─────────────────────┬───────────────────────────────────────────────┤
│ Rust has MIR        │ Spore has no borrow checker → no MIR needed  │
│ Zig has ZIR         │ Spore has no comptime → no flat IR needed    │
│ Rust has LLVM IR    │ Cranelift IR serves as LIR directly          │
│ Gleam has 2 layers  │ Spore needs HIR for desugaring + resolution  │
└─────────────────────┴───────────────────────────────────────────────┘
```

The 3-layer design (AST → HIR → TypedHIR) hits a sweet spot: enough structure
to support precise incremental compilation (sig hash at HIR, impl hash at
TypedHIR) without unnecessary passes that exist only to serve features Spore
does not have.

### Incremental compilation

#### salsa integration

Spore uses the [salsa](https://github.com/salsa-rs/salsa) framework for
demand-driven, memoized, incremental computation. Each compilation pass is a
salsa-tracked function:

```rust
#[salsa::input]
struct SourceFile {
    #[return_ref]
    path: PathBuf,
    #[return_ref]
    contents: String,
}

#[salsa::tracked]
fn lex(db: &dyn Db, file: SourceFile) -> TokenStream { ... }

#[salsa::tracked]
fn parse(db: &dyn Db, tokens: TokenStream) -> Ast { ... }

#[salsa::tracked]
fn resolve(db: &dyn Db, ast: Ast) -> Hir { ... }
// side product: sig_hash

#[salsa::tracked]
fn type_check(db: &dyn Db, hir: Hir) -> TypedHir { ... }
// side product: impl_hash, hole_reports, diagnostics

#[salsa::tracked]
fn codegen(db: &dyn Db, typed_hir: TypedHir) -> CompiledModule { ... }
```

#### Two-tier hash strategy

The incremental compilation strategy relies on two content-addressed hashes:

```text
                    ┌──────────────────────┐
                    │    File changed?     │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Compute impl hash   │
                    └──────────┬───────────┘
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
        impl hash unchanged           impl hash changed
                 │                           │
         Skip everything            ┌────────▼────────┐
         (content dedup)            │ Compute sig hash │
                                    └────────┬────────┘
                                             │
                              ┌──────────────┴──────────────┐
                              │                            │
                     sig hash unchanged             sig hash changed
                              │                            │
                  Recompile this module         Recompile this module
                  Skip downstream               Mark downstream for
                                                recheck (direct deps)
```

**sig hash** covers: exported type/function signatures, capability requirements,
cost annotations. It does *not* cover: function bodies, private definitions,
comments, internal hole states.

**impl hash** covers: the fully type-checked module content. Partial functions
(with holes) have `impl hash = None`.

Incremental scenarios:

| Scenario | Example | What happens |
|----------|---------|-------------|
| **A: impl hash unchanged** | Only a comment changed | Skip entirely (<1ms) |
| **B: impl only** | Changed function body, same signature | Recompile this module, skip downstream |
| **C: sig changed** | Changed function parameter type | Recompile this module + cascade to direct dependents |

#### Dependency graph traversal

When a sig hash changes, the compiler walks the dependency graph in topological
order. At each level, it recompiles affected modules in parallel, then checks
whether *their* sig hashes changed before propagating further. This ensures
minimal recompilation:

```text
fn compile_batch(modules: Set<ModuleId>, graph: DepGraph):
    let levels = topological_levels(modules, graph)
    levels.iter().for_each(|level|
        level.par_iter().for_each(|module_id|
            compile(module_id)
            update_diagnostics(module_id)
            update_hole_report(module_id)
        )
    )
```

Independent modules within the same topological level are compiled in parallel.
Default parallelism = CPU core count; override with `--jobs N`.

#### Change detection pseudocode

```pseudocode
fn on_file_changed(path: Path) -> ChangeResult:
    let source = read_file(path)
    let module_id = resolve_module(path)
    let new_impl_hash = hash_impl(source)

    if new_impl_hash == cache.get_impl_hash(module_id):
        return ChangeResult::Unchanged

    let new_sig_hash = compute_sig_hash(source)
    let old_sig_hash = cache.get_sig_hash(module_id)
    cache.update(module_id, new_impl_hash, new_sig_hash)

    if new_sig_hash == old_sig_hash:
        return ChangeResult::ImplOnly(module_id)
    else:
        return ChangeResult::SigChanged(module_id)
```

### Watch mode

#### Command and flags

```bash
spore watch src/main.sp             # Watch one entry file / project target
spore watch --json src/main.sp      # NDJSON output for IDEs / agents
```

#### Debounce strategy

File system events are coalesced before triggering recompilation:

```text
t=0ms    File A changed
t=20ms   File B changed  ─┐ debounce window (100ms)
t=80ms   File C changed   │
t=100ms  Window expires  ─┘
t=100ms  Begin incremental compile {A, B, C}
```

- **Debounce window:** 100ms (coalesce all changes within the window)
- **Maximum wait:** 500ms (cap for sustained bursts, e.g. `git checkout`)

#### NDJSON event stream

`spore watch --json` emits newline-delimited JSON. Each line is one event:

**Incremental compile event:**

```json
{
  "type": "incremental_compile",
  "timestamp": "2026-01-15T10:30:45Z",
  "trigger": {
    "file": "src/auth/login.sp",
    "change_type": "impl_only"
  },
  "recompiled": ["src/auth/login.sp"],
  "skipped_downstream": true,
  "duration_ms": 34,
  "diagnostics": [],
  "holes": {
    "total": 4,
    "filled_this_cycle": ["src/auth/login.sp:30"],
    "ready_to_fill": ["src/auth/login.sp:45"]
  }
}
```

**Diagnostic event:**

```json
{
  "type": "diagnostic",
  "file": "src/net/http.sp",
  "line": 23, "column": 5,
  "severity": "warning",
  "code": "W001",
  "message": "unused import: `Timeout`"
}
```

**Hole update event:**

```json
{
  "type": "hole_update",
  "summary": { "total": 2, "ready_to_fill": 1, "blocked": 1 },
  "changes": [
    {
      "action": "filled",
      "hole": { "file": "src/auth.sp", "line": 10, "name": "hash_password" }
    },
    {
      "action": "unblocked",
      "hole": { "file": "src/auth.sp", "line": 20, "name": "verify_password" },
      "reason": "dependency hash_password is now filled"
    }
  ]
}
```

#### Error recovery

Watch mode **never exits** (except on Ctrl+C). Recovery behavior:

| Situation | Strategy |
|-----------|----------|
| Syntax / type error | Report diagnostic, retain last successful compilation state |
| Circular dependency | Report error, interrupt affected module subtree |
| File deleted | Remove from dependency graph, mark dependents as errored |
| Compiler panic | Catch and report as internal error, continue watching |

#### Complete watch terminal output

```text
$ spore watch src/main.sp
[watch] Watching project: ./my-project (42 modules)
[watch] ✓ Initial compilation complete (1.2s), 0 errors, 2 warnings, 5 holes

  Warnings:
    src/net/http.sp:23:5  unused import: `Timeout`        [W0102]
    src/db/query.sp:45:12 unused capability: `FileSystem`  [W0105]

  Holes (5):
    ◯ src/auth/login.sp:30   authenticate     : User -> Token
    ◯ src/auth/login.sp:45   validate_token   : Token -> Bool
    ◯ src/db/query.sp:12     execute_query    : Query -> Result
    ◯ src/net/http.sp:67     handle_request   : Request -> Response
    ◯ src/net/http.sp:89     parse_headers    : Bytes -> Headers

[watch] Waiting for file changes...
```

#### Hole fill progressive watch session

```text
$ spore watch src/main.sp
[watch] ✓ Initial compilation complete, 0 errors, 3 holes

  Holes (3):
    ◯ src/auth.sp:10  hash_password     : String -> HashedPassword
    ◯ src/auth.sp:20  verify_password   : String -> HashedPassword -> Bool
    ◯ src/app.sp:50   create_user       : UserInput -> Result User Error
         ⚠ blocked: depends on hash_password, verify_password
  Ready to fill: hash_password, verify_password

// --- Developer fills hash_password ---

[watch] ─── Change detected ────────────────────────
[watch] File changed: src/auth.sp
[watch] Recompiling: src/auth.sp ... OK (28ms)
[watch] sig hash unchanged → skipping downstream
  ✓ 0 errors, 2 holes (was: 3)
    ● hash_password      [filled ✓]
    ◯ verify_password   : String -> HashedPassword -> Bool
    ◯ create_user       ⚠ blocked: depends on verify_password
  Ready to fill: verify_password

// --- Developer fills verify_password ---

[watch] ─── Change detected ────────────────────────
[watch] File changed: src/auth.sp
[watch] Recompiling: src/auth.sp ... OK (31ms)
[watch] sig hash changed → checking downstream:
         └─ src/app.sp ... OK (22ms)
  ✓ 0 errors, 1 hole
    ● verify_password    [filled ✓]
    ◯ create_user       → no longer blocked!
  Ready to fill: create_user

// --- Developer fills create_user ---

[watch] ─── Change detected ────────────────────────
[watch] File changed: src/app.sp
[watch] Recompiling: src/app.sp ... OK (35ms)
  ✓ 0 errors, 0 holes 🎉 All holes filled!
```

#### Hole status data structures

```text
type HoleReport:
    total: Nat
    filled_this_cycle: List Hole
    ready_to_fill: List Hole        // dependencies satisfied, can implement now
    blocked: List BlockedHole       // has unmet dependencies

type Hole:
    module: ModuleId
    location: SourceLocation
    name: String
    signature: Type

type BlockedHole:
    hole: Hole
    blocked_by: List ModuleId       // modules containing unfilled dependency holes
```

#### Module dependency graph structures

```text
type DepGraph:
    nodes: Map ModuleId ModuleInfo
    edges: Map ModuleId (Set ModuleId)      // module → modules it depends on
    reverse: Map ModuleId (Set ModuleId)    // module → modules depending on it

type ModuleInfo:
    id: ModuleId
    path: Path
    impl_hash: Hash
    sig_hash: Hash
    capabilities: Set Capability
    cost_annotation: CostBound
    holes: List Hole
```

#### Dependency graph incremental update

```pseudocode
fn update_dep_graph(module_id: ModuleId, old_deps: Set<ModuleId>, new_deps: Set<ModuleId>):
    // Remove stale edges
    (old_deps - new_deps).iter().for_each(|dep|
        graph.edges[module_id].remove(dep)
        graph.reverse[dep].remove(module_id)
    )
    // Add new edges
    (new_deps - old_deps).iter().for_each(|dep|
        graph.edges[module_id].insert(dep)
        graph.reverse[dep].insert(module_id)
    )
    // Cycle check
    if has_cycle(graph, module_id):
        emit_error("circular dependency", module_id)
```

#### Capability propagation watch output

```text
[watch] sig hash changed (capability set changed)
[watch] Capability change: HttpClient: {Network} → {Network, FileSystem}
[watch] Checking project capability ceiling...
         ceiling allows: {Network, FileSystem, Clock} → ✓ within bounds
[watch] Downstream capability compatibility:
         ├─ src/api/client.sp → OK
         └─ src/app.sp → propagation stops
[watch] ✓ 3 modules recompiled, 0 errors, 1 capability warning
```

When the ceiling is exceeded:

```text
[watch] ✗ Error: HttpClient added capability `Crypto`
         Project ceiling: {Network, FileSystem, Clock}
         `Crypto` not in ceiling — update ceiling or remove usage
```

#### Cost propagation watch output

```text
[watch] Cost change: sort: O(n·log n) → O(n²)
[watch] Checking downstream cost budgets:
         ├─ src/data/table.sp
         │   sort_column budget: O(n·log n) → ✗ exceeded
         └─ src/app.sp
             process_data budget: O(n²) → ✓ within bounds
[watch] ✗ 1 error
```

#### LSP Diagnostics JSON conversion + `spore/holeUpdate` schema

Watch events are converted to LSP messages by the Spore LSP server:

```json
{
  "method": "textDocument/publishDiagnostics",
  "params": {
    "uri": "file:///project/src/auth.sp",
    "diagnostics": [{
      "range": {
        "start": { "line": 22, "character": 9 },
        "end": { "line": 22, "character": 24 }
      },
      "severity": 1,
      "code": "E0301",
      "source": "spore",
      "message": "type mismatch: expected `Token`, found `String`"
    }]
  }
}
```

#### `spore/holeUpdate` custom LSP notification

```json
{
  "method": "spore/holeUpdate",
  "params": {
    "holes": [
      {
        "uri": "file:///project/src/auth.sp",
        "range": {
          "start": { "line": 29, "character": 4 },
          "end": { "line": 29, "character": 50 }
        },
        "name": "authenticate",
        "signature": "User -> Token",
        "status": "ready_to_fill"
      }
    ],
    "summary": { "total": 2, "ready": 1, "blocked": 1 }
  }
}
```

### CLI implementation stack

The `spore` binary is built on a curated set of Rust crates chosen for
correctness, minimal footprint, and future Spore self-hosting feasibility:

| Crate | Purpose | Bootstrap path |
|-------|---------|---------------|
| `bpaf` | Argument parsing (derive-based) | Parser combinator — natural fit for Spore |
| `ariadne` | Diagnostic rendering (span-based) | Thin wrapper on ANSI formatting |
| `owo-colors` | Terminal color output | Pure ANSI escape sequences |
| `notify` | File system watching (`watch` mode) | System call wrapper |
| `serde_json` | JSON serialization (`--json` flag) | Spore will need JSON support |
| `tracing` | Structured logging (`--verbose`) | Replaceable with print-based logging |

**Self-hosting consideration:** Every crate above wraps a concept that Spore
must eventually implement natively (parsing, formatting, file I/O, JSON). The
Rust CLI serves as the reference implementation; the Spore bootstrap will
reimplement these as Spore libraries using the `basic-cli` platform.

### Diagnostic output formats

#### Default format

Rust-inspired, concise, color-coded:

```text
<severity>[<code>]: <headline>
  --> <file>:<line>:<col>
   |
NN | <source line>
   |   <underline> <inline note>
   |
   = note: <additional context>
help: <suggested fix>
```

Color scheme: errors in red, warnings in yellow, notes in blue, help in green.
Colors are disabled when output is piped (not a TTY) or when `--no-color` is
passed.

Every diagnostic **always** includes a `help:` line with a concrete fix
suggestion. This is a hard design rule — no diagnostic may leave the user
without a next step.

#### Verbose format (`--verbose`)

Appends additional analysis blocks after each diagnostic:

- **Inference chain:** step-by-step type derivation
- **Candidates considered:** possible conversions, overloads, alternative
  functions
- **Capability context:** which capabilities are in scope at the error site
- **Cost context:** cost used so far vs. budget

Example:

```text
error[E0301]: type mismatch
  --> src/billing.sp:42:22
   |
42 |     charge(card, "fifty dollars")
   |                  ^^^^^^^^^^^^^^^ expected `Money`, found `String`
   |
help: try `Money.from_string("fifty dollars")`

  inference chain:
    "fifty dollars" : String       (literal, line 42)
    charge.amount : Money          (from signature, sig@b3c1e2)
    String ≠ Money                 (nominal mismatch)

  candidates considered:
    String -> Money via Money.from_string  ✓ (exact match)
    String -> Money via Money.parse        ✓ (may raise ParseError)

  capability context: [PaymentGateway]
  cost at this point: 120 / budget 500
```

#### JSON format (`--json`)

The single source of truth. Every field rendered in default or verbose mode is
derived from a JSON field. Schema:

```json
{
  "version": "0.1",
  "compiler": "sporec",
  "diagnostics": [
    {
      "severity": "error | warning | note",
      "code": "E0301",
      "message": "type mismatch: expected `Money`, found `String`",
      "location": {
        "file": "src/billing.sp",
        "range": {
          "start": { "line": 42, "col": 22 },
          "end": { "line": 42, "col": 37 }
        }
      },
      "related": [],
      "inference_chain": [],
      "candidates": [],
      "context": {
        "capabilities": ["PaymentGateway"],
        "cost_used": 120,
        "cost_budget": 500,
        "enclosing_function": "charge_customer",
        "enclosing_module": "billing.payment",
        "hole": null
      },
      "suggested_fix": {
        "description": "use Money.from_string",
        "applicability": "safe | unsafe | informational",
        "edits": [
          {
            "file": "src/billing.sp",
            "range": { "start": { "line": 42, "col": 22 }, "end": { "line": 42, "col": 37 } },
            "new_text": "Money.from_string(\"fifty dollars\")"
          }
        ]
      }
    }
  ],
  "summary": { "errors": 1, "warnings": 0, "notes": 0, "holes": 0 }
}
```

#### JSON field requirements

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `severity` | string | **required** | `"error"`, `"warning"`, or `"note"` |
| `code` | string | **required** | Error code (e.g., `"E0301"`) |
| `message` | string | **required** | Human-readable headline |
| `location` | object | **required** | Primary source location with file and range |
| `related` | array | optional | Related source locations with messages |
| `inference_chain` | array | optional | Step-by-step type derivation (populated in `--verbose` and `--json`) |
| `candidates` | array | optional | Conversions/overloads considered by the compiler |
| `context` | object | **required** | Capability, cost, and scope context |
| `context.capabilities` | string[] | **required** | Capabilities in scope at error site |
| `context.cost_used` | int | optional | Cost accumulated before error site (null if no cost clause) |
| `context.cost_budget` | int | optional | Total cost budget (null if no cost clause) |
| `context.enclosing_function` | string | **required** | Name of the containing function |
| `context.enclosing_module` | string | **required** | Module path |
| `context.hole` | string | optional | Hole name if this diagnostic is hole-related (null otherwise) |
| `suggested_fix` | object | optional | Machine-applicable fix suggestion |
| `suggested_fix.applicability` | string | **required** (if `suggested_fix` present) | `"safe"`, `"unsafe"`, or `"informational"` |
| `suggested_fix.edits` | array | **required** (if `suggested_fix` present) | List of text edits |

LSP compatibility: the JSON schema maps directly to LSP `Diagnostic` objects.
Spore extension fields (`inference_chain`, `candidates`, `context`) are placed
in the standard LSP `data.spore` namespace.

#### Error code system

All diagnostics carry categorized codes:

| Prefix | Category | Examples |
|--------|----------|----------|
| `E0xxx` | Type errors | type mismatch, missing field, arity error |
| `W0xxx` | Warnings | unused variable, redundant pattern, shadowing |
| `C0xxx` | Capability violations | undeclared capability, exceeding ceiling |
| `K0xxx` | Cost violations | budget exceeded, unbounded call |
| `H0xxx` | Hole diagnostics | hole report, partial function, type conflict |
| `M0xxx` | Module errors | circular dependency, visibility violation |

Every code is queryable: `sporec explain E0301` prints a detailed explanation
with common causes, examples, and fix strategies.

#### `sporec explain` output format

```text
$ sporec explain E0301

  E0301: type mismatch

  This error occurs when an expression has a type that is incompatible
  with the type expected by its context. Common contexts include:

  - Function arguments (actual type ≠ parameter type)
  - Return statements (expression type ≠ declared return type)
  - Variable bindings (right side type ≠ left side annotation)
  - Struct fields (value type ≠ field type)
  - Match arms (arm type ≠ sibling arm types)
  - Pipe operator (left-hand type ≠ right-hand function's first parameter)

  Example:
      fn greet(name: String) -> String { ... }
      greet(42)   // error: expected String, found Int

  Common fixes:
  - Use a conversion function (e.g. `Int.to_string(42)`)
  - Change the declaration to accept the actual type
  - Add a type annotation to guide inference

  See also: E0302 (return type mismatch), E0401 (constraint not satisfied)
```

### Performance targets

Target latencies (aspirational, not hard guarantees):

| Operation | Target | Notes |
|-----------|--------|-------|
| Single module recompilation | < 100ms | Type check + capability + cost |
| Dependency graph traversal | < 10ms | Topological sort of module DAG |
| Hash computation (single module) | < 5ms | blake3 of module content |
| Full project initial analysis (~100 modules) | < 5s | Cold start, parallel compilation |
| End-to-end latency (file save → diagnostics) | < 200ms | Including 100ms debounce |
| Hole report update | < 50ms | Incremental HoleReport regeneration |

**Cache strategy:** Watch mode maintains in-memory caches for hashes, dependency graph, compilation artifacts, and hole state. Persistence to disk is not required for v0.1 but is a future option.

**Parallelism:** Default = CPU core count. Override with `--jobs N`.

### CLI subcommand design

#### `spore check`

`spore check` performs all static analyses without code generation. It is the
primary project-aware command for verifying correctness during development.

```bash
spore check src/main.sp             # check a single entry module path
spore check src/main.sp src/net/http.sp
spore check --deny-warnings src/main.sp src/net/http.sp
```

##### Implementation strategy

`spore check` runs a **single compilation pipeline** that performs all static
analyses in one pass:

```text
Source → Parse → Name Resolution → Type Inference
                                    ├── Capability Check (inline)
                                    ├── Cost Analysis (post-typecheck)
                                    └── Lint Pass (post-typecheck)
```

All diagnostics are collected into a single `Vec<Diagnostic>` and sorted by file
position. This ensures the developer sees **all** issues in one invocation rather
than fixing types first, then capabilities, then costs.

**Cost violations** are emitted as **warnings** (severity = Warning, code prefix
`K`), not errors. They do not cause a non-zero exit code unless `--deny-warnings`
is passed.

**Lint warnings** (severity = Warning, code prefix `W`) follow the same rule.

#### `spore fmt`

`spore fmt` rewrites source files to conform to the canonical Spore style.

```bash
spore fmt src/main.sp src/net/http.sp
spore fmt --check src/main.sp src/net/http.sp
```

##### Implementation strategy

The formatter is **AST-based**: it parses source code into an AST, then
pretty-prints the AST according to canonical rules. This ensures output is always
syntactically valid and produces consistent results regardless of input formatting.

```text
Source → Parse → AST → Pretty-print → Formatted source
```

**Comment preservation** is a known challenge for AST-based formatters. The current
implementation attaches comments to adjacent AST nodes during parsing (stored as
leading/trailing trivia on `Spanned<T>`). Future work may adopt a CST
(Concrete Syntax Tree) approach for perfect fidelity.

**CI integration**: `spore fmt --check` is designed for CI pipelines. It exits
with code 1 if any file would change, without modifying files. Combined with
`spore check --deny-warnings`, these two commands form a complete CI static
analysis gate:

```yaml
# Example CI step
- run: spore fmt --check src/main.sp src/net/http.sp
- run: spore check --deny-warnings src/main.sp src/net/http.sp
```

---

## Human experience impact

### Faster iteration cycles

The incremental compilation system eliminates the most frustrating part of the
edit-compile-test loop: unnecessary waiting. When a developer changes a function
body without altering its signature, *only that module* is recompiled. Downstream
modules are untouched. In practice this means sub-100ms feedback for most edits.

### Actionable diagnostics

Every error message includes a `help:` line — no diagnostic leaves the
developer stranded. The default output is concise (5–8 lines per error) and
visually structured with Rust-style gutters and underlines, making it easy to
scan 10–20 errors without fatigue. `--verbose` mode provides inference chains
for complex type errors, letting developers understand *why* the compiler
reached its conclusion without needing to read source code in a different window.

### Watch mode as primary workflow

`spore watch` is designed to be the default development workflow. It provides:

- Real-time error/warning diagnostics on file save
- Hole progress tracking (total holes, filled this cycle, ready to fill, blocked)
- Capability and cost propagation alerts when signatures change

The watch output is designed to be "glanceable" — a developer can look at the
terminal and immediately know whether the codebase is healthy.

### Hole-driven development

Watch mode tracks hole status in real time, showing which holes are ready to
fill (all dependencies satisfied) and which are blocked. This enables a natural
top-down workflow where developers sketch function signatures, insert holes for
implementations, then fill them one by one with immediate feedback.

---

## Agent experience impact

### Structured consumption via `--json`

Agents consume `spore check --json` output directly. The structured format enables
programmatic reasoning without parsing human-readable text. Key fields:

- `diagnostics[]` — iterate over all diagnostics
- `severity` — filter by error (must fix) vs. warning (should fix) vs. note
- `code` prefix — categorize by subsystem (E/W/C/K/H/M)
- `context.hole` — if non-null, use `--query-hole` for full report
- `suggested_fix.edits` — if `applicability == "safe"`, apply directly
- `inference_chain` + `candidates` — enough context to reason about errors
  without re-reading source files

### Agent hole-filling workflow

```text
1. Start  spore watch --json src/main.sp
2. Parse initial hole list from NDJSON stream
3. Select a  ready_to_fill  hole → generate implementation → write to file
4. Wait for watch to emit compilation result
5. Success → proceed to next hole; Failure → read diagnostics, fix, retry
6. Repeat until  holes = 0
```

The NDJSON stream provides a continuous event bus: the agent subscribes to
`incremental_compile`, `diagnostic`, and `hole_update` events without polling.

#### Agent mode selection

| Scenario | Recommended Mode | Rationale |
|----------|-----------------|-----------|
| Agent filling holes | `--json` | Parse diagnostics, apply fixes programmatically |
| Agent debugging complex type error | `--json` | Use `inference_chain` and `candidates` for reasoning |
| Agent in CI pipeline | `--json --stream` | Machine-readable, earliest feedback per diagnostic |
| Human scanning build output | Default | Concise, color-coded, glanceable |
| Human debugging inference failure | `--verbose` | See inference chain in terminal |
| IDE / LSP client | `--json` | Map to LSP Diagnostics with Spore extensions in `data` |

#### Agent error recovery

When an Agent's fix introduces new errors, the diagnostic system supports iterative repair:

```text
1. Agent applies fix for E0301 (type mismatch)
2. spore check --json → new E0303 (error type mismatch introduced by fix)
3. Agent reads inference_chain for E0303 → understands the cascading error
4. Agent applies a second fix addressing E0303
5. spore check --json → 0 errors
```

The `inference_chain` and `candidates` fields are specifically designed to give Agents enough context to reason about errors **without re-reading source files**. The original diagnostic for the first error is preserved in the Agent's context, enabling diff-based reasoning.

### Future machine-applicable fix metadata

The current public CLI does **not** yet expose machine-applicable fixes, fix
flags, or a stable fix-specific JSON payload. This section records the future
design target for editor / agent integration once such a surface exists.

Fix applicability categories:

| Category | Future mode | Meaning |
|----------|-------------|---------|
| `safe` | dedicated fix mode | Preserves behavior and type safety |
| `unsafe` | dedicated unsafe-fix mode | May change behavior; apply with caution |
| `informational` | manual only | Requires judgment |

#### Fix suggestion types

| Type | Description | Example |
|------|-------------|---------|
| **Replacement** | Replace a span with new text | `"fifty dollars"` → `Money.from_string("fifty dollars")` |
| **Insertion** | Insert text at a position (zero-width range) | Adding `currency: Currency.USD` to struct literal |
| **Deletion** | Remove a span (new_text is empty string) | Removing a redundant match arm |
| **Multi-edit** | Multiple edits in one file | Adding `uses [NetRead]` clause and updating a binding |
| **Multi-file** | Edits spanning multiple files | Adding `pub` in defining module and updating import in consumer |

#### Fix suggestion JSON examples

**Safe fix — missing import (Insertion):**

```json
{
  "description": "add missing import for `DateTime`",
  "applicability": "safe",
  "edits": [
    {
      "file": "src/scheduler.sp",
      "range": { "start": { "line": 2, "col": 1 }, "end": { "line": 2, "col": 1 } },
      "new_text": "import time.DateTime\n"
    }
  ]
}
```

**Unsafe fix — remove unused variable (Deletion):**

```json
{
  "description": "remove unused variable `temp`",
  "applicability": "unsafe",
  "edits": [
    {
      "file": "src/billing.sp",
      "range": { "start": { "line": 38, "col": 5 }, "end": { "line": 38, "col": 45 } },
      "new_text": ""
    }
  ]
}
```

**Multi-file fix — make function public (Multi-file):**

```json
{
  "description": "make `helper_fn` public and update import",
  "applicability": "unsafe",
  "edits": [
    {
      "file": "src/utils.sp",
      "range": { "start": { "line": 10, "col": 1 }, "end": { "line": 10, "col": 3 } },
      "new_text": "pub fn"
    },
    {
      "file": "src/api.sp",
      "range": { "start": { "line": 3, "col": 1 }, "end": { "line": 3, "col": 1 } },
      "new_text": "import utils.helper_fn\n"
    }
  ]
}
```

---

## Structured representation / protocol impact

### LSP integration architecture

```text
┌──────────────┐   LSP Protocol   ┌──────────────┐  stdin/stdout  ┌──────────────┐
│  Editor/IDE  │ ←──────────────→ │  Spore LSP   │ ←────────────→ │ spore watch  │
│              │                   │  Server       │    (NDJSON)    │ --json       │
└──────────────┘                   └──────────────┘                └──────────────┘
```

The LSP server launches `spore watch --json <entry-file>` as a subprocess and translates the
NDJSON event stream into LSP messages:

| Watch event | LSP message |
|-------------|-------------|
| `diagnostic` | `textDocument/publishDiagnostics` |
| `incremental_compile` | Diagnostics refresh |
| `hole_update` | Custom `spore/holeUpdate` notification |

#### LSP Diagnostic field mapping (precise)

| Spore JSON | LSP `Diagnostic` | Conversion |
|------------|------------------|------------|
| `severity: "error"` | `severity: 1` | Direct: error=1, warning=2, note=3 |
| `severity: "warning"` | `severity: 2` | |
| `severity: "note"` | `severity: 3` | |
| `code` | `code` | Direct string copy |
| `message` | `message` | Direct string copy |
| `location.range.start.line` | `range.start.line` | Spore is 1-indexed; LSP is 0-indexed. Subtract 1. |
| `location.range.start.col` | `range.start.character` | Spore is 1-indexed; LSP is 0-indexed. Subtract 1. |
| `location.range.end.line` | `range.end.line` | Subtract 1 |
| `location.range.end.col` | `range.end.character` | Subtract 1 |
| `related` | `relatedInformation` | Map each entry to `DiagnosticRelatedInformation` |
| `suggested_fix` | via `codeAction` | Mapped to LSP `CodeAction` with `edit.changes` |
| `inference_chain` | `data.spore.inference_chain` | Spore extension in `data` field |
| `candidates` | `data.spore.candidates` | Spore extension in `data` field |
| `context` | `data.spore.context` | Spore extension in `data` field |

Compilation is triggered by file-system save events, not LSP `didChange` — this
avoids expensive compilation of half-edited states.

### JSON as the superset

The `--json` format is the single source of truth:

- Default mode renders a *projection* of the JSON
- Verbose mode renders a *larger projection*
- JSON mode renders *everything*

This guarantees consistency: if the default output says "expected `Money`, found
`String`", the JSON contains the same message *plus* the inference chain that
produced it.

### Streaming vs. batch

- **Batch** (default `--json`): single JSON object after compilation completes
- **Streaming** (`--json --stream`): one NDJSON line per diagnostic as
  discovered, with a `"type": "summary"` final line

Streaming is preferred for large projects and CI/CD pipelines where early
feedback matters.

---

## Diagnostics impact

### Error format specification

Every diagnostic follows the anatomy:

```text
<severity>[<code>]: <headline message>
  --> <file>:<line>:<col>
   |
NN | <source line>
   |   ^^^ <inline note>
   |
   = note: <additional context>
help: <suggested fix>
```

Severity, code, location, source context, and help are **mandatory** for every
diagnostic. The `= note:` lines and `related` locations are optional but
encouraged for complex errors.

#### Multi-line error display

When an error spans multiple lines, the gutter marks the full range:

```text
error[E0102]: struct missing required field `currency`
  --> src/billing.sp:15:5
   |
15 | /   let invoice = Invoice {
16 | |       amount: 100,
17 | |       recipient: user,
18 | |   }
   | |___^ missing field `currency`
   |
help: add the missing field: `currency: Currency.USD`
```

The `/ | |___^` format connects multi-line spans visually.

#### ANSI color scheme

| Element | Color | ANSI Code |
|---------|-------|-----------|
| `error` + error code | Red (bold) | `\x1b[1;31m` |
| `warning` + warning code | Yellow (bold) | `\x1b[1;33m` |
| `note` | Blue (bold) | `\x1b[1;34m` |
| `help` | Green (bold) | `\x1b[1;32m` |
| `hint` | Cyan (bold) | `\x1b[1;36m` |
| Line numbers | Bright blue | `\x1b[94m` |
| Source text | Default | — |
| Underline (`^^^`) | Matches severity color | — |

Colors are disabled when output is piped (not a TTY) or when `--no-color` is passed. The `--json` mode never includes ANSI codes.

### Error categories and examples

**Type error:**

```text
error[E0301]: type mismatch
  --> src/billing.sp:42:22
   |
42 |     charge(card, "fifty dollars")
   |                  ^^^^^^^^^^^^^^^ expected `Money`, found `String`
   |
help: try `Money.from_string("fifty dollars")`
```

**Capability violation:**

```text
error[C0101]: undeclared capability
  --> src/report.sp:27:5
   |
27 |     http.get(endpoint)
   |     ^^^^^^^^^^^^^^^^^^ requires `NetRead`, not declared in `uses`
   |
   = note: enclosing function `fetch_data` has `uses []`
   = note: module ceiling for `report` allows [Compute, FileRead]
help: add a `uses [NetRead]` clause to `fetch_data`
```

**Cost violation:**

```text
error[K0101]: cost budget exceeded
  --> src/analytics.sp:55:5
   |
55 |     full_table_scan(records)
   |     ^^^^^^^^^^^^^^^^^^^^^^^^ this call costs 8200 op
   |
   = note: `summarize` budget is 5000 op, already used 1200 op
   = note: remaining budget: 3800 op, shortfall: 4400 op
help: filter `records` before scanning, or increase budget to `cost ≤ 10000`
```

**Hole report:**

```text
note[H0101]: hole `tax_logic` requires filling
  --> src/tax.sp:12:5
   |
12 |     ?tax_logic
   |     ^^^^^^^^^^ expected type: `Money`, remaining cost budget: 400 op
   |
   = note: available bindings: income: Money, region: Region
   = note: available capabilities: [TaxTable]
   = note: candidate: `tax_table.lookup(region, income) -> Money`
help: run `sporec query-hole <file> tax_logic` for full HoleReport
```

### Recovery strategies

The compiler employs error recovery to report as many errors as possible per
compilation rather than stopping at the first:

| Phase | Recovery strategy |
|-------|------------------|
| Lexer | Skip to next recognizable token boundary |
| Parser | Synchronize at statement/declaration boundaries; insert synthetic nodes |
| Resolve | Mark unresolved names as `ErrorType`, continue checking |
| TypeCheck | Propagate `ErrorType` without cascading false errors |
| CapCheck | Report violation but continue checking remaining uses |
| CostCheck | Report budget exceedance but compute total cost for diagnostics |

**Deduplication policy:** when a single root cause produces multiple downstream
errors, the compiler shows the root error in full and collapses downstream
errors into `= note: N additional errors caused by this`.

### Complete Error Code Registry

All diagnostics carry a categorized code. Every code is queryable: `sporec explain CODE`.

#### E0xxx — Type Errors

| Code | Name | Description |
|------|------|-------------|
| `E0101` | missing-field | Struct literal missing a required field |
| `E0102` | unknown-field | Struct literal contains a field not in the type definition |
| `E0103` | duplicate-field | Struct literal contains the same field twice |
| `E0104` | field-type-mismatch | Struct field value type does not match declaration |
| `E0105` | tuple-length-mismatch | Tuple has wrong number of elements |
| `E0106` | missing-variant-field | Enum variant constructor missing a field |
| `E0107` | record-vs-tuple | Used record syntax where tuple expected, or vice versa |
| `E0108` | non-struct-field-access | Field access on a non-struct type |
| `E0109` | private-field-access | Accessing a private field from outside the defining module |
| `E0110` | spread-type-mismatch | Spread operator (`..base`) type does not match struct |
| `E0201` | arity-mismatch | Function called with wrong number of arguments |
| `E0202` | named-arg-mismatch | Named argument does not match any parameter |
| `E0203` | missing-required-arg | Required argument not provided |
| `E0204` | duplicate-arg | Same argument provided twice |
| `E0301` | type-mismatch | Expression type incompatible with expected type |
| `E0302` | return-type-mismatch | Function body returns wrong type |
| `E0303` | error-type-mismatch | Function raises undeclared error type |
| `E0304` | if-branch-mismatch | If/else branches have different types |
| `E0305` | match-arm-mismatch | Match arms have different types |
| `E0306` | operator-type-error | Operator applied to incompatible types |
| `E0307` | index-type-error | Non-integer used as index |
| `E0308` | not-callable | Attempt to call a non-function value |
| `E0309` | pipe-type-mismatch | Pipe operator left-hand side incompatible with right-hand function |
| `E0310` | lambda-return-mismatch | Lambda body type does not match expected return |
| `E0401` | constraint-not-satisfied | Generic type does not satisfy trait constraint |
| `E0402` | ambiguous-type | Type inference cannot determine a unique type |
| `E0403` | recursive-type | Infinitely recursive type definition |
| `E0404` | gat-mismatch | Generic associated type arguments do not match |
| `E0501` | pattern-exhaustiveness | Match does not cover all variants |
| `E0502` | pattern-type-mismatch | Pattern type does not match scrutinee type |
| `E0503` | duplicate-pattern | Same pattern appears twice in match |
| `E0504` | guard-type-error | Match guard expression is not Bool |

#### W0xxx — Warnings

| Code | Name | Description |
|------|------|-------------|
| `W0101` | unused-variable | Variable bound but never read |
| `W0102` | unused-import | Module import never referenced |
| `W0103` | unused-function | Private function never called |
| `W0104` | unused-type | Private type never referenced |
| `W0105` | unused-capability | Declared capability never exercised |
| `W0201` | redundant-pattern | Match arm unreachable due to prior arm |
| `W0202` | redundant-constraint | Generic constraint implied by another |
| `W0203` | redundant-parentheses | Unnecessary parentheses around expression |
| `W0301` | shadowing | Variable shadows binding in outer scope |
| `W0302` | implicit-discard | Expression result discarded without explicit `_` |

#### C0xxx — Capability Violations

| Code | Name | Description |
|------|------|-------------|
| `C0101` | undeclared-capability | Function uses capability not in `uses` |
| `C0102` | exceeds-ceiling | Function `uses` exceeds module ceiling |
| `C0103` | callee-capability-leak | Calling function whose `uses` exceeds caller's |
| `C0104` | transitive-capability | Transitive callee introduces undeclared capability |
| `C0201` | platform-capability-denied | Package requests capability Platform does not grant |
| `C0202` | platform-missing | No Platform provides required capability |
| `C0301` | capability-purity-conflict | `uses []` (pure) function calls impure code |

#### K0xxx — Cost Violations

| Code | Name | Description |
|------|------|-------------|
| `K0101` | budget-exceeded | Concrete cost exceeds `cost ≤ K` |
| `K0102` | symbolic-budget-exceeded | Symbolic cost may exceed bound for some inputs |
| `K0103` | cost-underflow | Remaining budget negative after prior statements |
| `K0201` | unbounded-call | Calling `unbounded` function without `with_cost_limit` |
| `K0202` | unbounded-recursion | Recursive function without structural termination proof |
| `K0301` | cost-declaration-missing | Function with cost-sensitive callees but no `cost ≤ K` |

#### H0xxx — Hole Diagnostics

| Code | Name | Description |
|------|------|-------------|
| `H0101` | hole-report | Standard hole report with type, bindings, candidates |
| `H0102` | hole-type-conflict | Explicit annotation conflicts with inferred type |
| `H0103` | hole-unconstrained | Hole has no type constraints from context |
| `H0201` | partial-function | Function contains one or more unfilled holes |
| `H0202` | hole-cost-tight | Remaining budget < 10% of total |
| `H0301` | hole-duplicate-name | Two holes share a name in the same module |
| `H0302` | hole-in-signature | Hole in signature position (not allowed for value holes) |
| `H0303` | circular-hole-dependency | Circular hole dependency detected |

#### M0xxx — Module Errors

| Code | Name | Description |
|------|------|-------------|
| `M0101` | circular-dependency | Modules form a dependency cycle |
| `M0102` | self-import | Module imports itself |
| `M0103` | duplicate-module | Two files map to the same module path |
| `M0201` | visibility-violation | Accessing private or `pub(pkg)` symbol from outside scope |
| `M0202` | re-export-visibility | Re-exporting with broader visibility than original |
| `M0203` | orphan-impl | Implementing external trait for external type |
| `M0301` | import-not-found | Imported module or symbol does not exist |
| `M0302` | ambiguous-import | Two imports bring same name into scope |
| `M0303` | wildcard-import | Wildcard imports are not allowed in Spore |
| `M0401` | snapshot-changed | Dependent signature hash changed; requires `--permit` |
| `M0402` | snapshot-missing | Referenced snapshot not found in `.spore-lock` |

### System integration

Diagnostics do not exist in isolation — they connect to every major Spore subsystem:

#### Hole System integration

- `H0101` (hole-report) is emitted as `note` severity for each unfilled hole during compilation
- `sporec query-hole <file> <name>` returns a full `HoleReport` — a superset of H0101 with candidate ranking, binding types, cost budget
- Partial functions (`H0201`) compile successfully — they produce diagnostics but not errors
- The HoleReport JSON extends the diagnostic schema with a `hole_report` field

#### Cost System integration

- `K0101` (budget exceeded) includes cost breakdown in `inference_chain`
- `K0102` (symbolic exceeded) includes the symbolic expression and concrete counterexample
- `context.cost_used` and `context.cost_budget` are populated for **all** diagnostics in functions with `cost ≤ K`, not just cost errors

#### Capability System integration

Three enforcement levels:

1. **Function level** (`C0101`): body uses operations beyond declared `uses`
2. **Module level** (`C0102`): function `uses` exceeds module ceiling
3. **Platform level** (`C0201`): package requests capabilities Platform does not grant

`context.capabilities` in every diagnostic lists capabilities in scope, enabling Agents to reason about available operations.

#### Snapshot System integration

- `M0401` (snapshot-changed) emits both expected and actual signature hashes
- The `suggested_fix` for `M0401` is always `informational` — the developer must explicitly run `spore --permit` to accept the change
- `related` field points to the changed signature's declaration

> **Note on `--permit`:** The `--permit` flag is a Codebase Manager (`spore`) command, not a compiler (`sporec`) flag. It updates `.spore-lock` to accept the new signature hash.

#### Module System integration

- `M0101` (circular dependency): `inference_chain` shows the full cycle path
- `M0201` (visibility violation): `candidates` may list public alternatives
- `M0301` (import not found): `suggested_fix` uses fuzzy matching for closest valid import

---

## Drawbacks

1. **Three output modes add maintenance burden.** Default, verbose, and JSON must
   remain consistent — a change to diagnostic content must be reflected in all
   three renderers. Mitigation: all three modes render from the same underlying
   `Diagnostic` struct; the JSON serializer is the canonical representation.

2. **salsa adds a dependency and learning curve.** salsa is a sophisticated
   framework with its own mental model (demand-driven, memoized queries).
   Contributors must understand salsa to modify the compiler pipeline.
   Mitigation: salsa is well-documented and used successfully in rust-analyzer.

3. **No MIR limits future optimization passes.** If Spore later needs
   optimization passes that operate on a control-flow graph (e.g., dead code
   elimination beyond what Cranelift does, or Spore-specific optimizations), the
   lack of a MIR-like representation would require introducing one.
   Mitigation: Cranelift already performs standard optimizations; Spore can
   introduce a MIR later if needed without changing the AST/HIR/TypedHIR layers.

4. **Cranelift is less mature than LLVM.** Cranelift produces less optimized
   code than LLVM for compute-heavy workloads. Mitigation: Cranelift's
   compilation speed aligns with Spore's emphasis on fast iteration; an LLVM
   backend can be added later for release builds.

5. **File-save-triggered compilation misses real-time feedback.** Unlike
   per-keystroke analysis (as in TypeScript's language server), Spore only
   compiles on save. This means errors from half-typed code are not shown until
   save. Mitigation: this is intentional — compiling partial edits generates
   noise; save is a natural "intent to check" signal.

---

## Alternatives considered

### 1. More IR layers (4 or 5, like Rust)

Rust uses AST → HIR → THIR → MIR → LLVM IR. We considered adding a MIR for
control-flow analysis and a separate LIR before Cranelift.

**Rejected because:** Spore has no borrow checker (the primary reason for Rust's
MIR), no lifetime analysis, and no comptime evaluation (which motivates Zig's
ZIR). Additional IR layers would add complexity without corresponding benefit.

### 2. Fewer IR layers (2, like Gleam)

Gleam uses Untyped AST → Typed AST with no separate HIR.

**Rejected because:** Spore's desugaring (`|>`, `?`, `f"..."`, `t"..."`) and
name resolution are complex enough to warrant a dedicated IR layer. Performing
desugaring inline during type-checking would complicate the type checker and make
incremental compilation boundaries less clean.

### 3. Zig-style flat IR (ZIR) for comptime

Zig uses a flattened IR (ZIR) to support compile-time evaluation.

**Rejected because:** Spore does not support comptime. Const generics +
refinement types + cost models cover Spore's compile-time reasoning needs. salsa
provides incremental caching without needing a flat IR representation.

### 4. LLVM instead of Cranelift

LLVM produces more optimized code and has a larger ecosystem.

**Rejected for initial implementation because:** Cranelift offers significantly
faster compilation, which aligns with Spore's emphasis on rapid iteration.
Cranelift's function-level granularity fits content-addressed caching naturally.
An LLVM backend remains a future option for optimized release builds.

### 5. Per-keystroke compilation (like TypeScript)

TypeScript's language server compiles on every keystroke, providing immediate
feedback.

**Rejected because:** compiling half-edited code generates noise (false errors
from incomplete expressions). File save is a natural "intent to check" signal.
The 100ms debounce window after save still provides near-instant feedback.

### 6. Separate passes for CapCheck and CostCheck

We considered making capability checking and cost checking independent passes
after type checking.

**Rejected because:** `Capability = Trait` in Spore, so capability resolution
shares trait resolution infrastructure. Cost checking depends on fully resolved
types and call graphs. Merging all three into a unified TypeCheck pass avoids
redundant tree traversals and simplifies the impl hash boundary.

### Why every diagnostic includes `help:`

A diagnostic without a suggestion is a dead end. By mandating `help:` on every diagnostic:

- Beginners always have a next step
- Agents can extract fix suggestions without additional reasoning
- The compiler team is forced to think about actionability when defining new error codes

Some `help:` lines are concrete (`try Money.from_string(...)`) and some are strategic (`extract shared types into a new module`). Both are valuable.

### Why category-based error codes

Codes like `E0301` are more useful than raw names:

- **Filterable:** `spore check --json | jq '.diagnostics[] | select(.code | startswith("K"))'` gives all cost errors
- **Discoverable:** `sporec explain E0301` opens documentation
- **Stable:** codes don't change when messages are reworded; CI can allowlist specific codes
- **Cross-referencing:** docs, forums, and issue trackers reference `E0301` unambiguously

The prefix convention (E/W/C/K/H/M) maps directly to Spore's major subsystems.

### Architectural Decision Records (ADRs)

#### ADR-001: Developer-time DX scope

**Decision:** Incremental compilation targets developer-time fast iteration, not production hot-swap.
**Rationale:** DX is the highest-ROI investment; content-addressing naturally supports incremental compilation.
**Consequence:** No runtime module replacement protocol; single-machine development scenarios only.

#### ADR-002: Three capabilities

**Decision:** "Program-as-Service" manifests as incremental compilation + real-time diagnostics + hole status tracking.
**Rationale:** These cover the core feedback needs during coding: correctness, problem location, progress tracking.
**Consequence:** `spore watch` is the unified carrier; JSON output contains all three information types.

#### ADR-003: Module-level granularity

**Decision:** The compilation unit is the module; sig hash unchanged → downstream skipped.
**Rationale:** Modules have natural compilation boundaries (explicit export interfaces). Function-level granularity has diminishing returns.
**Consequence:** Hash computation, dependency graph, and parallel compilation all operate at module granularity.

#### ADR-004: File-save trigger

**Decision:** Watch mode compiles on file-system save events, not per-keystroke.
**Rationale:** Save is a natural "intent to check" signal; per-keystroke compilation produces noise from half-edited code.
**Consequence:** Requires debounce; LSP triggers via FS events rather than `didChange`.

#### ADR-005: Dual-format output

**Decision:** Human-readable (default) + JSON (`--json`) output formats.
**Rationale:** Terminal users need readable output; IDEs and agents need structured output.
**Consequence:** Both formats derive from the same underlying `Diagnostic` struct; JSON is the superset.

---

## Prior art

| Language | Pipeline | What Spore borrows |
|----------|----------|-------------------|
| **Rust** | AST → HIR → THIR → MIR → LLVM IR | HIR/TypedHIR concepts; salsa for incremental compilation (via rust-analyzer); Rust-style diagnostic layout |
| **Zig** | AST → ZIR → AIR → Machine IR | Pratt parser for expressions; *not* the ZIR concept (no comptime) |
| **Roc** | AST → Canonical → Solved → IR | Canonical ≈ HIR concept; name resolution approach |
| **Gleam** | Untyped AST → Typed AST | Inspiration for simplicity in the 2-layer approach; confirmed that 2 layers are too few for Spore |
| **Gonidium** | AST → TypedDag | `DiagCollector` error collection pattern |
| **Elm** | AST → Canonical → Typed → Optimized | Philosophy of helpful error messages; Spore adopts the helpfulness but uses Rust's concise layout rather than Elm's paragraph style |

### salsa (Rust ecosystem)

salsa is a framework for demand-driven incremental computation, originally
developed for rust-analyzer. It provides:

- Automatic memoization of query results
- Fine-grained dependency tracking
- Automatic invalidation and recomputation on input changes
- Durability layers for optimizing frequently vs. rarely changing inputs

Spore uses salsa to make each compilation pass a tracked query, enabling
automatic incremental recomputation when source files change.

### Cranelift

Cranelift is a code generation backend designed for fast compilation. It is used
by Wasmtime and is being integrated into rustc as an alternative to LLVM for
debug builds. Key properties:

- Function-level compilation unit (fits content-addressed caching)
- Significantly faster compilation than LLVM (at the cost of less optimized
  output)
- SSA-based IR with good support for common language constructs
- Active development by the Bytecode Alliance

---

## Backward compatibility and migration

### PoC → Prototype migration

The PoC phase uses a **tree-walking interpreter** in place of Cranelift codegen.
The migration path:

1. The `codegen` pass is behind a clean abstraction boundary (it receives
   `TypedHIR` and produces an executable result)
2. Replacing the tree-walking interpreter with Cranelift codegen requires
   implementing the `TypedHIR → Cranelift IR` translation — no changes to
   passes 1–4
3. The `--json` diagnostic format is identical in both phases; tools built
   against PoC diagnostics continue to work in prototype

### Diagnostic format stability

Error codes (E0xxx, W0xxx, etc.) are considered stable once assigned. The
meaning of a code does not change, though the message text may be improved.
CI/CD pipelines and agents should filter on error codes, not message strings.

If the JSON schema needs breaking changes, the `"version"` field will be
incremented and a migration period provided where both old and new schemas are
emitted.

### Future IR additions

If Spore later needs a MIR (e.g., for advanced optimization or analysis), it
would be inserted between TypedHIR and Cranelift IR:

```text
AST → HIR → TypedHIR → [future MIR] → Cranelift IR → Native
```

This insertion would not change the AST, HIR, or TypedHIR layers, nor the sig
hash / impl hash boundaries. The impl hash would continue to be computed at the
TypedHIR layer; a new "opt hash" could gate the MIR → Cranelift translation.

---

## Unresolved questions

1. **Diagnostic deduplication granularity.** When a single root cause produces
   multiple downstream errors, how aggressively should the compiler collapse
   them? Current proposal: show the root in full, collapse downstream into
   `= note: N additional errors caused by this`. Needs user testing to find the
   right threshold.

2. **Diagnostic ordering.** Primary sort by file, secondary by line, with
   errors before warnings before notes within the same line? Or should the
   compiler attempt causal ordering (root cause first)? Needs experimentation.

3. **Persistent caching across sessions.** salsa's in-memory cache is lost
   when `spore watch` exits. Should the compiler persist the salsa database to
   disk for faster cold starts? This adds complexity (cache invalidation,
   file format stability) but could significantly improve initial compilation
   time for large projects.

4. **Parallel type-checking within a module.** The current design parallelizes
   across modules at the same topological level. Could independent functions
   within a single module be type-checked in parallel? This depends on salsa's
   granularity and the cost of synchronizing shared state (e.g., trait
   resolution caches).

5. **LLVM backend.** When should an LLVM backend be added for release-optimized
   builds? This is a significant engineering effort. Cranelift may be sufficient
   for Spore's target use cases (networked services, CLI tools) where compile
   speed matters more than runtime performance.

6. **Streaming granularity.** For `--json --stream`, should events be
   per-diagnostic (current proposal, finest granularity) or per-module (less
   noise, more batched)? Per-diagnostic gives earliest feedback but may
   overwhelm agents processing large rebuilds.

7. **Internationalization of diagnostics.** Error codes are language-independent,
   but message text is currently English-only. Should `sporec explain` support
   localized explanations in a future version? This would require a translation
   infrastructure.

8. **Cost visualization in verbose mode.** Should `--verbose` include ASCII bar
   charts showing cost distribution within a function? This could help
   developers visually identify expensive calls but adds rendering complexity.

9. **Watch mode persistence.** Should `spore watch` offer an option to write
   compilation results (diagnostics, hole reports) to a file on each cycle,
   enabling offline analysis tools to process the history?

10. **Tree-walking interpreter scope.** How much of the language should the
    PoC interpreter support? Full semantics (including capabilities and cost
    tracking at runtime) or a minimal subset for early testing? This affects
    the PoC timeline and determines how much behavior can be validated before
    Cranelift codegen is ready.

### Diagnostic suppression mechanism

Specific diagnostics can be suppressed using inline annotations:

```spore
#[allow(W0301)]
let count = filtered.len()   // shadowing is intentional here
```

Project-level suppression via `spore.toml`:

```toml
[diagnostics]
allow = ["W0302"]   # allow implicit discards project-wide
```

Suppression is limited to **warnings only** — errors and notes cannot be suppressed. The `#[allow(...)]` attribute applies to the next statement or the enclosing block.

---

## Glossary

| Term | Definition |
|------|-----------|
| **impl hash** | Hash of module implementation content; determines whether to recompile this module |
| **sig hash** | Hash of module public interface; determines whether downstream dependents need rechecking |
| **hole** | Source-code placeholder (`?name`) for unfinished implementation, carrying type information |
| **capability** | A declared system permission (e.g., `Network`, `FileSystem`) required to perform certain operations |
| **capability ceiling** | Project-level maximum capability set; no module may exceed it |
| **cost annotation** | A declared upper bound on a function's computational cost (`cost ≤ K`) |
| **debounce** | Coalescing multiple rapid file-system events into a single compilation trigger |
| **NDJSON** | Newline-Delimited JSON — each line is a complete, independent JSON object |
