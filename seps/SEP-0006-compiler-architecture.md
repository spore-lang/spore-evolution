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
discussion: "https://github.com/spore-lang/spore-evolution/discussions/6"
pr: null
superseded_by: null
---

# SEP-0006: Compiler Architecture

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

A developer interacts with the compiler through the `sporec` CLI:

```bash
# One-shot compilation
sporec build src/main.spore

# Check without codegen
sporec check src/main.spore

# Watch mode — recompile on save, show diagnostics in real time
spore watch

# Watch mode with JSON output for agents / IDEs
spore watch --json

# Explain an error code
sporec --explain E0301

# Query a specific hole
sporec --query-hole tax_logic --json
```

### What the developer sees

**On success:**

```
$ sporec build src/main.spore
  Compiling main (src/main.spore)
  Compiling http (src/net/http.spore)
  Compiling auth (src/auth/login.spore)
    Finished build in 1.4s — 3 modules, 0 errors, 0 warnings
```

**On error (default mode):**

```
error[E0301]: type mismatch
  --> src/billing.spore:42:22
   |
42 |     charge(card, "fifty dollars")
   |                  ^^^^^^^^^^^^^^^ expected `Money`, found `String`
   |
help: try `Money.from_string("fifty dollars")`
```

**In watch mode:**

```
$ spore watch
[watch] Watching project: ./my-project (42 modules)
[watch] ✓ Initial compilation complete (1.2s), 0 errors, 2 warnings, 5 holes

[watch] Waiting for file changes...

[watch] ─── Change detected ─────────────────────
[watch] File changed: src/auth/login.spore
[watch] Recompiling: src/auth/login.spore ... OK (34ms)
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

```
Source Text (.spore files)
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
│  ─ Error set propagation and consistency (! [Errors])                   │
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

```
Spanned<T> { node: T, span: Span }
Span { file: FileId, start: u32, end: u32 }

Module { items: Vec<Spanned<Item>> }
Item = FnDef | StructDef | TypeDef | CapabilityDef | Import | ...
FnDef {
    name, params, return_type, error_set,
    where_clause, with_clause, cost_clause, uses_clause,
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
| **Error sets** | Propagation and consistency of `! [ErrorType]` declarations |
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

```
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

```
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

```
fn compile_batch(modules: Set<ModuleId>, graph: DepGraph):
    let levels = topological_levels(modules, graph)
    for level in levels:
        parallel_for module_id in level:
            compile(module_id)
            update_diagnostics(module_id)
            update_hole_report(module_id)
```

Independent modules within the same topological level are compiled in parallel.
Default parallelism = CPU core count; override with `--jobs N`.

### Watch mode

#### Command and flags

```bash
spore watch                        # Watch current project
spore watch --json                 # NDJSON output for IDEs / agents
spore watch --project ./my-proj    # Specify project path
spore watch --quiet                # Only show errors
spore watch --jobs 4               # Specify parallelism
```

#### Debounce strategy

File system events are coalesced before triggering recompilation:

```
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
    "file": "src/auth/login.spore",
    "change_type": "impl_only"
  },
  "recompiled": ["src/auth/login.spore"],
  "skipped_downstream": true,
  "duration_ms": 34,
  "diagnostics": [],
  "holes": {
    "total": 4,
    "filled_this_cycle": ["src/auth/login.spore:30"],
    "ready_to_fill": ["src/auth/login.spore:45"]
  }
}
```

**Diagnostic event:**

```json
{
  "type": "diagnostic",
  "file": "src/net/http.spore",
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
      "hole": { "file": "src/auth.spore", "line": 10, "name": "hash_password" }
    },
    {
      "action": "unblocked",
      "hole": { "file": "src/auth.spore", "line": 20, "name": "verify_password" },
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

### Diagnostic output formats

#### Default format

Rust-inspired, concise, color-coded:

```
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

```
error[E0301]: type mismatch
  --> src/billing.spore:42:22
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
        "file": "src/billing.spore",
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
            "file": "src/billing.spore",
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

Every code is queryable: `sporec --explain E0301` prints a detailed explanation
with common causes, examples, and fix strategies.

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

Agents consume `sporec --json` output directly. The structured format enables
programmatic reasoning without parsing human-readable text. Key fields:

- `diagnostics[]` — iterate over all diagnostics
- `severity` — filter by error (must fix) vs. warning (should fix) vs. note
- `code` prefix — categorize by subsystem (E/W/C/K/H/M)
- `context.hole` — if non-null, use `--query-hole` for full report
- `suggested_fix.edits` — if `applicability == "safe"`, apply directly
- `inference_chain` + `candidates` — enough context to reason about errors
  without re-reading source files

### Agent hole-filling workflow

```
1. Start  spore watch --json
2. Parse initial hole list from NDJSON stream
3. Select a  ready_to_fill  hole → generate implementation → write to file
4. Wait for watch to emit compilation result
5. Success → proceed to next hole; Failure → read diagnostics, fix, retry
6. Repeat until  holes = 0
```

The NDJSON stream provides a continuous event bus: the agent subscribes to
`incremental_compile`, `diagnostic`, and `hole_update` events without polling.

### Auto-fix integration

Agents can apply machine-applicable fixes automatically:

```bash
# Apply all safe fixes
sporec --fix src/billing.spore

# Preview fixes without applying
sporec --fix --dry-run src/billing.spore
```

Fix applicability categories:

| Category | Flag | Meaning |
|----------|------|---------|
| `safe` | `--fix` | Preserves behavior and type safety |
| `unsafe` | `--unsafe-fix` | May change behavior; apply with caution |
| `informational` | *(manual)* | Requires judgment |

---

## Structured representation / protocol impact

### LSP integration architecture

```
┌──────────────┐   LSP Protocol   ┌──────────────┐  stdin/stdout  ┌──────────────┐
│  Editor/IDE  │ ←──────────────→ │  Spore LSP   │ ←────────────→ │ spore watch  │
│              │                   │  Server       │    (NDJSON)    │ --json       │
└──────────────┘                   └──────────────┘                └──────────────┘
```

The LSP server launches `spore watch --json` as a subprocess and translates the
NDJSON event stream into LSP messages:

| Watch event | LSP message |
|-------------|-------------|
| `diagnostic` | `textDocument/publishDiagnostics` |
| `incremental_compile` | Diagnostics refresh |
| `hole_update` | Custom `spore/holeUpdate` notification |

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

```
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

### Error categories and examples

**Type error:**

```
error[E0301]: type mismatch
  --> src/billing.spore:42:22
   |
42 |     charge(card, "fifty dollars")
   |                  ^^^^^^^^^^^^^^^ expected `Money`, found `String`
   |
help: try `Money.from_string("fifty dollars")`
```

**Capability violation:**

```
error[C0101]: undeclared capability
  --> src/report.spore:27:5
   |
27 |     http.get(endpoint)
   |     ^^^^^^^^^^^^^^^^^^ requires `NetRead`, not declared in `uses`
   |
   = note: enclosing function `fetch_data` has `uses []`
   = note: module ceiling for `report` allows [Compute, FileRead]
help: add a `uses [NetRead]` clause to `fetch_data`
```

**Cost violation:**

```
error[K0101]: cost budget exceeded
  --> src/analytics.spore:55:5
   |
55 |     full_table_scan(records)
   |     ^^^^^^^^^^^^^^^^^^^^^^^^ this call costs 8200 op
   |
   = note: `summarize` budget is 5000 op, already used 1200 op
   = note: remaining budget: 3800 op, shortfall: 4400 op
help: filter `records` before scanning, or increase budget to `cost ≤ 10000`
```

**Hole report:**

```
note[H0101]: hole `tax_logic` requires filling
  --> src/tax.spore:12:5
   |
12 |     ?tax_logic
   |     ^^^^^^^^^^ expected type: `Money`, remaining cost budget: 400 op
   |
   = note: available bindings: income: Money, region: Region
   = note: available capabilities: [TaxTable]
   = note: candidate: `tax_table.lookup(region, income) -> Money`
help: run `sporec --query-hole tax_logic` for full HoleReport
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

```
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
   but message text is currently English-only. Should `sporec --explain` support
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
