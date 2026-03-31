---
sep: 8
title: "SEP-0008: Module & Package System"
status: Draft
type: Standards Track
authors:
  - Spore maintainers
created: 2026-03-31
requires:
  - 1
  - 3
discussion: "https://github.com/spore-lang/spore-evolution/discussions/8"
pr: null
superseded_by: null
---

# SEP-0008: Module & Package System

## Summary

This SEP specifies the complete module and package system for the Spore programming language. It defines how code is organized (one file = one module), how visibility is controlled (private / `pub(pkg)` / `pub`), how functions are content-addressed via a dual-hash scheme (signature hash + implementation AST hash using BLAKE3), how packages are structured around `spore.toml` manifests, how dependencies are resolved without semantic versioning, how IO is abstracted through the Platform system using effect handlers, and how a capability-based trust model secures the supply chain.

The design synthesizes ideas from Unison (content-addressing), Roc (platform/package separation), Elm/Go (file-based modules, no circular dependencies), and Rust (three-level visibility), while introducing novel concepts such as module-level capability ceilings, the import/alias separation, and the dual-hash content-addressing scheme that decouples API stability from implementation pinning.

## Motivation

### Why content-addressed functions?

Traditional package ecosystems rely on semantic versioning (semver) to communicate compatibility. In practice, semver is a social contract—not a machine-verifiable one. A "patch" release can silently break consumers; a "major" bump may change nothing relevant to a particular dependent. This ambiguity leads to:

- **Phantom breakage**: Dependents recompile or fail when nothing they actually use has changed.
- **Dependency hell**: SAT solvers struggle with conflicting version ranges.
- **Non-reproducible builds**: The same version string may resolve to different code over time.

Spore eliminates these problems by giving every function two content hashes computed via BLAKE3:

1. **Signature hash (`sig`)**: Covers the function's public contract—parameter names, parameter types, return type, error types, effects, cost bound, capabilities, and generic constraints. This hash changes **only** when the API changes.
2. **Implementation AST hash (`impl`)**: Covers the compiled AST of the function body. This hash changes whenever the implementation changes. Partial functions (those containing holes) have `impl = None`.

This dual-hash scheme provides two independent guarantees:

- **API stability** (`sig`): If `sig` is unchanged, dependents need not recompile. Hole filling and body refactoring are invisible to consumers.
- **Exact reproducibility** (`impl`): The `.spore-lock` file pins the precise implementation via `impl`, enabling bit-for-bit reproducible builds.

### Why no semantic versioning?

Content hashes make semver redundant. Instead of trusting a human to correctly label a release as "major", "minor", or "patch", the compiler can verify compatibility mechanically:

- `sig` unchanged → API compatible. No downstream action required.
- `sig` changed → Breaking change. The `spore --permit` command is required to explicitly accept the change.
- `impl` changed, `sig` unchanged → Internal refactor. `.spore-lock` updates automatically.

A human-readable `version` field remains available in `spore.toml` for documentation purposes, but it plays no role in dependency resolution. Named aliases (e.g., `"std-http-v2"`) provide stable human-readable identifiers that map to specific hashes.

### Why platforms for IO?

In traditional languages, IO operations are built into the standard library, making them impossible to substitute for testing, impossible to sandbox for security, and impossible to port across runtimes without rewriting application code. Spore's Platform system, inspired by Roc, makes IO a pluggable concern:

- **Application code is pure**: Functions declare capability requirements (`uses [FileRead, NetWrite]`) but never perform IO directly.
- **Platforms provide effect handlers**: A Platform maps abstract capabilities to concrete system calls.
- **Test Platforms enable deterministic testing**: Mock handlers return predefined data, eliminating flaky tests.
- **Supply-chain security**: A downloaded package declaring `uses [Compute]` is provably pure—it cannot access the filesystem, network, or any IO primitive.

## Guide-level explanation

### Module declaration

Every `.spore` file is exactly one module. The module name is derived from the file's path relative to the package's `src/` root:

| File Path | Module Name |
|---|---|
| `src/billing/invoice.spore` | `billing.invoice` |
| `src/auth/token.spore` | `auth.token` |
| `src/utils.spore` | `utils` |
| `src/main.spore` | `main` |

There is no separate module declaration syntax—the filesystem **is** the declaration. An optional module header may declare the module's capability ceiling:

```spore
-- src/billing/invoice.spore
module billing.invoice uses [PaymentGateway, AuditLog]

import billing.types
import billing.tax

pub fn generate_invoice(order: Order) -> Invoice ! [TaxError, ValidationError]
    with [deterministic]
    cost ≤ 3000
    uses [PaymentGateway, AuditLog]
{
    let tax = billing.tax.calculate(order.items, order.region)
    let line_items = build_line_items(order.items, tax)
    finalize(order.customer, line_items)
}

fn build_line_items(items: Vec<Item>, tax: TaxResult) -> Vec<LineItem>
    with [pure]
    cost ≤ 500
{
    items |> map(fn(item) -> to_line_item(item, tax))
}
```

If the `module` header is present, its declared name **must** match the file path (otherwise: compiler error). If omitted, the module name is inferred from the path.

### Imports

Spore provides exactly two import mechanisms with no overlap:

```spore
-- Module import: makes all pub items accessible via qualified name
import billing.invoice

-- Module import with rename
import billing.invoice as inv

-- Item alias: binds a specific function or type to a local name
alias gen = billing.invoice.generate_invoice
alias Inv = billing.types.Invoice
```

Key rules:
- `import` operates on **modules** only. You cannot import a function directly.
- `alias` operates on **items** only. You cannot alias a module.
- No wildcard imports (`import billing.*` is not supported).
- No implicit nested imports (`import billing` does not import `billing.invoice`).

### Visibility

| Level | Keyword | Meaning |
|---|---|---|
| **Private** | *(default)* | Visible only within the defining module |
| **Package-internal** | `pub(pkg)` | Visible to any module within the same package |
| **Public** | `pub` | Visible to any importer, including external packages |

```spore
-- Public: any importer can call this
pub fn generate_invoice(order: Order) -> Invoice ! [TaxError] { ... }

-- Package-internal: accessible within this package only
pub(pkg) fn validate(order: Order) -> ValidatedOrder ! [ValidationError] { ... }

-- Private (default): only this module can call this
fn compute_totals(order: ValidatedOrder) -> Invoice { ... }
```

Visibility applies uniformly to functions, types, and aliases.

### Packages

A **package** is a directory containing a `spore.toml` manifest:

```
my-billing-lib/
├── spore.toml              -- package manifest
├── src/
│   ├── billing/
│   │   ├── invoice.spore   -- module: billing.invoice
│   │   ├── tax.spore       -- module: billing.tax
│   │   └── types.spore     -- module: billing.types
│   └── utils.spore         -- module: utils
└── test/
    └── billing/
        └── invoice_test.spore
```

Three package types exist:

| Type | Has Platform? | Can do IO? | Use Case |
|---|---|---|---|
| `package` | No | No (declares capability requirements) | Libraries, reusable components |
| `application` | Yes | Yes (via Platform) | Executables, services |
| `platform` | Is the Platform | Yes (raw syscalls) | Runtime providers |

### Platforms

A Platform is the **only** code in a Spore application that can perform real IO. It provides effect handlers that interpret abstract capabilities at runtime:

```spore
// Application code: pure function, emits effects
fn read_config() -> Config ! [FileRead] {
    let content = File.read("config.toml")  // emits FileRead effect
    parse_toml(content)
}

// Platform: provides the FileRead handler
// Application code never sees this implementation
handler FileReadHandler {
    File.read(path) -> resume(os_read_file(path))
}
```

The same application code can run on different Platforms—CLI, Web, WASM, Embedded—without modification. For testing, a **Test Platform** replaces real IO with deterministic mock handlers.

## Reference-level explanation

### Module resolution

#### File-to-module mapping

The compiler maps `.spore` files to modules using the path relative to `src/`:

```
module_name = path.relative_to("src/")
                  .strip_extension(".spore")
                  .replace("/", ".")
```

Module name segments must be lowercase `snake_case`. Reserved names (`main`, `platform`, `test`) carry special semantics.

#### Dependency graph construction

The compiler builds a directed acyclic graph (DAG) of module dependencies:

1. Parse all `import` declarations across all modules.
2. Verify no circular dependencies exist (standard topological sort; cycles are compile errors).
3. Determine topological build order. Modules at the same level compile in parallel.

```
$ sporec build --show-order

Build order (topological):
  1. billing.types       (0 dependencies)
  2. billing.tax         (1 dependency: billing.types)
  3. billing.invoice     (2 dependencies: billing.types, billing.tax)
  4. billing.shortcuts   (3 dependencies: billing.types, billing.invoice, billing.tax)
  5. api.handler         (2 dependencies: billing.invoice, billing.shortcuts)
  6. main                (1 dependency: api.handler)
```

Diamond dependencies are permitted (they are not cycles). The `.spore-lock` ensures a single canonical version via matching `sig` and `impl` hashes.

#### Forward references

Within a single module, functions may reference each other regardless of declaration order—the compiler processes all declarations before resolving references. Cross-module forward references are forbidden (they would imply circular dependencies).

#### Import grammar (formal)

```
import_decl    ::= 'import' module_path ('as' IDENT)?
alias_decl     ::= visibility? 'alias' IDENT '=' qualified_item
module_path    ::= IDENT ('.' IDENT)*
qualified_item ::= module_path '.' IDENT
```

### Content-addressed functions: dual hashing

#### Hash computation

Every function carries two BLAKE3 hashes:

**Signature hash (`sig`)**:

```
sig = BLAKE3(canonicalize(
    function_name,
    parameter_names,
    parameter_types,
    return_type,
    error_types,
    effect_annotations,
    cost_bound,
    capability_requirements,
    generic_constraints
))
```

The canonicalization process removes whitespace, sorts lexicographically where order is not semantically meaningful, and expands type aliases to their canonical forms.

**Implementation AST hash (`impl`)**:

```
impl = BLAKE3(compiled_AST(function_body))
```

For partial functions (those containing holes), `impl = None`. When a hole is filled, `impl` transitions from `None` to a concrete hash while `sig` remains unchanged.

#### What changes each hash

| Change | `sig` changes? | `impl` changes? |
|---|---|---|
| Parameter name: `order` → `purchase_order` | **Yes** | **Yes** |
| Parameter type: `Order` → `OrderRequest` | **Yes** | **Yes** |
| Return type: `Invoice` → `InvoiceResult` | **Yes** | **Yes** |
| Error type set: Add `[ValidationError]` | **Yes** | **Yes** |
| Effects: `pure` → `deterministic` | **Yes** | **Yes** |
| Cost bound: `≤ 3000` → `≤ 5000` | **Yes** | **Yes** |
| Capabilities: Add `AuditLog` | **Yes** | **Yes** |
| Generic constraints: `T: Eq` → `T: Eq + Hash` | **Yes** | **Yes** |
| Function body: Refactor internals | **No** | **Yes** |
| Hole filling: Replace `?logic` with code | **No** | `None` → concrete |
| Comments: Add/remove/edit | **No** | **No** |
| Formatting: Reformat code | **No** | **No** |

Key insight: signature changes always change both hashes. Body-only changes update `impl` while leaving `sig` untouched—this prevents unnecessary downstream recompilation.

#### Hash algorithm: BLAKE3

BLAKE3 is the mandatory hash algorithm for all content addressing in Spore:

- **Speed**: 10x+ faster than SHA-256, with native parallelism support.
- **Security**: 128-bit security level (256-bit output).
- **Streaming**: Supports incremental hashing for large modules.
- **Output**: 256-bit hashes displayed as 64 hex characters; truncated forms (e.g., 16 hex chars) used in human-facing output.

#### `.spore-lock` and dependency tracking

The `.spore-lock` file records both hashes for all functions a module depends on:

```toml
# .spore-lock (auto-generated, do not edit)

[deps.api.handler.generate_invoice]
sig  = "a3f7c2"    # interface contract
impl = "d8e1b4"    # exact implementation (None if partial)

[deps.billing.invoice.calculate]
sig  = "d91e4b"
impl = "b2c4a7"
```

Compatibility checking uses only `sig`: if `sig` is unchanged, dependents need not recompile. The `impl` field pins exact code for reproducible builds.

#### Change detection and `spore --permit`

When a signature changes, all downstream modules referencing the old `sig` are flagged:

```
$ sporec check

[warning] signature changed: billing.tax.calculate
  old sig: d91e4b
  new sig: 7a2f33
  change: added error type [RegionNotSupported]

  affected modules:
    billing.invoice (depends on billing.tax.calculate sig=d91e4b)
    api.handler     (depends on billing.tax.calculate sig=d91e4b)

  run `spore --permit billing.tax.calculate` to accept this change
```

The `spore --permit` command updates `sig` entries in `.spore-lock`. Implementation-only changes update `impl` automatically—no permit required. Batch acceptance is available via `spore --permit --all`.

#### Snapshot hierarchy

Hashes cascade through three levels, all derived from `sig` only (implementation changes do not propagate):

| Level | What is hashed | When it changes |
|---|---|---|
| **Function `sig`** | Canonical signature | Any signature component changes |
| **Function `impl`** | Compiled AST | Body changes, hole filling, or signature changes |
| **Module interface** | Sorted hash of all `pub` + `pub(pkg)` `sig` hashes | Any exported function's signature changes |
| **Package API** | Sorted hash of module interface hashes | Any module's exported interface changes |

### Visibility rules

#### Three visibility levels: `pub` / `pub(pkg)` / private

- **Private** (default): Visible only within the defining module.
- **`pub(pkg)`**: Visible to any module within the same package. External packages cannot access `pub(pkg)` items.
- **`pub`**: Visible to any importer, including external packages.

Visibility applies to functions, types, and aliases:

```spore
pub type Invoice { id: InvoiceId, total: Money }       -- public type
pub(pkg) type ValidatedOrder { original: Order }        -- package-internal type
type InternalCache { entries: Map<String, CacheEntry> } -- private type

pub alias GenInv = billing.invoice.generate_invoice     -- public alias
pub(pkg) alias Validate = billing.invoice.validate      -- package-internal alias
alias Compute = billing.invoice.compute_totals          -- private alias
```

#### Visibility enforcement

Attempting to access a private item from another module:

```
[error] visibility violation at src/api/handler.spore:15
  billing.invoice.compute_totals is private
  ─── it is only visible within module billing.invoice

  help: add `pub` or `pub(pkg)` to its definition in src/billing/invoice.spore
```

Attempting to access a `pub(pkg)` item from an external package:

```
[error] visibility violation at src/handler.spore:8
  billing.invoice.validate is pub(pkg)
  ─── it is only visible within the 'my-billing-lib' package
  ─── your module 'handler' is in the 'my-api' package
```

#### Re-exports via pub aliases

The only re-export mechanism is `pub alias`:

```spore
-- src/billing/shortcuts.spore
import billing.invoice
import billing.types

pub alias generate = billing.invoice.generate_invoice
pub alias Invoice = billing.types.Invoice
```

Alias chains are **forbidden**. A `pub alias` must point to an original definition, not to another alias. This prevents unbounded indirection and keeps the dependency graph simple for both human and agent analysis.

#### Shadowing rules

Module imports and aliases cannot shadow each other. An alias cannot conflict with an imported module name:

```spore
import billing.invoice
alias invoice = billing.types.Invoice    -- ERROR: 'invoice' conflicts with module name
```

### Platform abstraction

#### IO via effect handlers

Application code is pure—it declares capability requirements but never performs IO directly. IO operations are expressed as effects that the Platform's handlers interpret at runtime:

```spore
-- Application code: pure
fn fetch_and_save(url: Url, dest: Path) -> Unit ! [NetRead, FileWrite] {
    let data = Http.get(url)
    File.write(dest, data)
}
```

The type system tracks all effects. Effects propagate upward: if you call a function requiring capability `C`, your function must also declare `uses [C]`.

#### Platform definition

A Platform declares three things:

1. **Capability set**: Which IO capabilities it handles.
2. **Effect handler implementations**: Runtime logic for each capability.
3. **Entry point type**: The type signature the application's `main` must satisfy.

```spore
platform CliPlatform {
    version: "1.0.0"
    handles [FileRead, FileWrite, StdOut, StdErr, NetRead, NetWrite, Clock, Spawn, Exit]
    entry: fn(args: List[Str]) -> I32 ! [Exit]

    handler FileReadHandler {
        File.read(path: Path) -> Result[Bytes, IoError] {
            resume(ffi_read_file(path))
        }
    }
    // ...
}
```

Platform declaration in `spore.toml`:

```toml
[platforms]
main = { git = "https://github.com/spore-platform/cli", version = "1.0.0" }
```

The compiler verifies:
- Every capability used by application code is handled by some Platform.
- The entry point type matches the Platform's requirement.
- No two Platforms handle the same capability (unless priorities are explicit).

#### Multi-Platform support

Applications may use multiple Platforms for different capability domains (e.g., CLI + GPU + S3):

```toml
[platforms]
cli = { git = "https://github.com/spore-platform/cli", priority = 1 }
gpu = { git = "https://github.com/spore-platform/cuda", priority = 2 }
s3  = { git = "https://github.com/spore-platform/aws", priority = 3 }
```

Each effect is routed to the highest-priority Platform that handles it. The compiler ensures every effect has exactly one handler.

#### Test Platforms for deterministic testing

Since application code is decoupled from IO implementations, a Test Platform can substitute mock handlers:

```spore
platform TestPlatform {
    handles [FileRead, FileWrite, NetRead, Clock]
    entry: fn() -> TestResult
}

handler MockFileSystem {
    var fs: Map[Path, Bytes] = Map.new()

    File.read(path: Path) -> Result[Bytes, IoError] {
        match fs.get(path) {
            Some(content) -> resume(Ok(content))
            None -> resume(Err(IoError.NotFound))
        }
    }
}

handler MockClock {
    var current_time: U64 = 0
    Clock.now() -> Timestamp { resume(Timestamp(current_time)) }
}
```

Running `spore test` automatically uses the Test Platform:

```bash
$ spore test
   Using test platform: spore-platform/test v1.0.0
   Running 3 tests

test fetch_weather_returns_valid_data ... ok (0.001s)
test fetch_weather_handles_network_error ... ok (0.001s)
test fetch_weather_handles_malformed_json ... ok (0.001s)

Test result: ok. 3 passed; 0 failed
```

#### Security model

1. **Pure packages cannot perform IO**. They declare capability requirements but lack handlers.
2. **Only Platforms hold `RawSyscall`**. No user package can access raw system calls.
3. **Capabilities are explicit**. An auditor can inspect any function's `uses` clause to know exactly what it can do.
4. **Supply-chain safety**: A downloaded package declaring `uses [Compute]` is provably pure.

```
$ spore audit billing-lib

Package: billing-lib
  required capabilities: [PaymentGateway, AuditLog]

  Module capability breakdown:
    billing.invoice:  [PaymentGateway, AuditLog]
    billing.tax:      []  (pure)
    billing.types:    []  (pure)

  ✓ No RawSyscall usage
  ✓ No undeclared capabilities
  ✓ All capability requirements declared in spore.toml
```

### Module capabilities

#### Capability ceiling

A module may declare the maximum set of capabilities its functions can use:

```spore
module billing.invoice uses [PaymentGateway, AuditLog]
```

- Any function in the module can use a subset of these capabilities.
- No function can use capabilities **not** in this set.
- Private functions are also bound by the ceiling.

If the `uses` declaration is omitted, the compiler **infers** the ceiling from the union of all `pub` functions' capabilities and emits an `[info]` diagnostic suggesting the explicit declaration. The `sporec --fixes` flag auto-applies the inferred declaration.

#### Capability propagation

Importing a module does **not** grant its capabilities. If you call a function that requires capability `C`, your function must also declare `uses [C]`. Capabilities propagate upward through the call graph.

### Package management

#### Package manifest (`spore.toml`)

```toml
[package]
name = "billing-lib"
version = "1.2.0"                # human-readable, not used for resolution
type = "package"                  # "package" | "application" | "platform"
description = "Invoice generation and tax calculation"
license = "MIT"
authors = ["Alice <alice@example.com>"]
spore-version = ">=0.5.0"

[capabilities]
requires = ["PaymentGateway", "AuditLog"]

[dependencies]
json-parser = {
    git = "https://github.com/spore-std/json",
    sig = "b4e7d3c2a1f9e8d7",
    impl = "2f3e4d5c6a7b8e9f"
}

[dev-dependencies]
test-framework = {
    git = "https://github.com/spore-std/test",
    alias = "spore-test-v1",
    sig = "a1b2c3d4e5f6a7b8",
    impl = "1a2b3c4d5e6f7a8b"
}
```

Package names are `kebab-case` and globally unique within a registry. Module paths within a package use `snake_case` segments.

#### Content-addressed dependencies (BLAKE3, no semver)

Dependencies are identified by content hashes, not version ranges:

```toml
[dependencies]
http = {
    git = "https://github.com/spore-std/http",
    sig = "a3f9c2e1d8b7a6f5",
    impl = "7b8d4f2a1e9c3d5b"
}
```

The `sig` hash identifies the API contract. The `impl` hash pins the exact implementation. There is no version range negotiation—no SAT solver is needed. Resolution is a simple hash lookup:

```
1. Read [dependencies] from spore.toml
2. For each dependency:
   a. Check .spore-lock for cached hash
   b. Fetch from source if not cached
   c. Compute BLAKE3 hashes and verify against declared values
3. Recursively resolve transitive dependencies
4. Build acyclic dependency graph
5. Write .spore-lock
```

Interface-only dependencies (omitting `impl`) allow type-checking without fetching full source, reducing download sizes and compile times.

#### Decentralized storage

Spore has **no central registry**. Packages are fetched from:

- **Git repositories** (primary): `git = "https://github.com/user/repo"`
- **Local paths** (development): `path = "../mylib"`
- **IPFS**: `ipfs = "Qm..."`
- **HTTP registries** (community-operated, index-only): `registry = "https://pkgs.example.com"`

Content hashes ensure integrity regardless of source. Community registries provide searchability but store only metadata—not code.

#### Capability-based trust model

Packages declare required capabilities in `spore.toml`. Capabilities do **not** propagate automatically—the consuming package must explicitly grant them:

```toml
[capabilities]
require = ["network:listen:8080", "filesystem:read:/data"]

grant = [
    "http:network:listen:*",
    "logger:filesystem:write:/var/log"
]
```

At runtime, the capability ceiling is enforced:

```bash
spore run --allow network:listen:8080 --allow filesystem:read:/data
```

The `spore audit` command reports the full capability graph, flagging any ungrantable or suspicious requirements.

#### Workspace support

Multi-package projects use a workspace `spore.toml`:

```toml
[workspace]
members = [
    "packages/billing-lib",
    "packages/billing-api",
    "apps/invoice-service",
]
```

Alternatively, `path` dependencies provide lightweight monorepo support without requiring a workspace manifest.

## Human experience impact

### Readability and navigation

- **File = module** eliminates the confusion of Rust's `mod`/`use` distinction or OCaml's separate `.mli` files. Opening a `.spore` file immediately tells you the module name.
- **Import/alias separation** removes ambiguity: `import` always means module, `alias` always means item.
- **Three visibility levels** are intuitive. The default is private; opt-in to exposure via `pub` or `pub(pkg)`.

### Workflow ergonomics

- **`sporec --fixes`** auto-applies inferred capability declarations, lowering the barrier for new users.
- **`spore --permit`** provides explicit acknowledgment of breaking changes, preventing accidental API breakage.
- **No semver** means developers never debate whether a change is "major" or "minor". The compiler decides mechanically.

### Learning curve

The dual-hash model is more conceptually complex than semver. However, the tooling hides most complexity: `spore add` computes hashes automatically, `spore update` refreshes them, and `.spore-lock` is machine-generated. Developers interact with hashes only when reviewing breaking changes via `spore --permit`.

### Error messages

Visibility violations, circular dependencies, capability ceiling breaches, and missing effect handlers all produce structured, actionable diagnostics with `help:` suggestions.

## Agent experience impact

### Machine-readable module boundaries

The module system is designed for agent-friendly navigation:

- Module names are deterministically derived from file paths.
- Dependency graphs are acyclic DAGs, trivially traversable.
- Visibility rules are encoded in the AST—an agent can enumerate a module's public API without human guidance.
- Capability requirements are explicit in `uses [...]` clauses.

### Content addressing for agents

Dual hashes give agents precise anchors:

- An agent can verify whether a dependency change is API-breaking (check `sig`) or implementation-only (check `impl`).
- Hole reports include visibility-filtered candidate lists, enabling automated hole filling.
- The `spore snapshot` and `spore exports` commands provide machine-consumable module metadata.

### Structured diagnostics

All compiler diagnostics (visibility violations, cycle detection, capability mismatches) are emitted in both human-readable and JSON formats, enabling agent tooling to parse and act on errors programmatically.

## Structured representation / protocol impact

### `.spore-lock` as the canonical dependency record

The `.spore-lock` file is a TOML document that encodes the full dependency graph with both `sig` and `impl` hashes, source locations, capability records, and verification timestamps:

```toml
[[package]]
name = "http"
alias = "std-http-v2"
source = { type = "git", url = "https://github.com/std/http", rev = "abc1234" }
sig = "a3f9c2e1d8b7a6f5"
impl = "7b8d4f2a1e9c3d5b"

[verification]
"http" = {
    sig-algo = "blake3",
    sig-hash = "a3f9c2e1d8b7a6f5",
    impl-algo = "blake3",
    impl-hash = "7b8d4f2a1e9c3d5b",
    verified-at = "2024-01-15T10:30:05Z"
}

[capabilities]
"http" = ["network:listen", "network:connect"]
```

### Module interface files (`.spore-sig`)

For interface-only dependencies, the compiler can produce `.spore-sig` files containing only the canonicalized public API. These are sufficient for type-checking without the full implementation.

### Platform capability routing tables

The compiler generates a capability routing table mapping each effect to its handler Platform. This table is embedded in the compiled output and enforced at runtime.

## Diagnostics impact

### New diagnostic categories

| Code | Category | Example |
|---|---|---|
| `E3001` | Visibility violation | Accessing a private function from another module |
| `E3002` | Circular dependency | Module A → B → A |
| `E3003` | Capability ceiling breach | Function uses capability not in module ceiling |
| `E3004` | Signature change detected | `sig` hash mismatch in `.spore-lock` |
| `E3005` | Alias chain | `pub alias` pointing to another alias |
| `E3006` | Shadowing conflict | Import alias conflicts with module name |
| `E4201` | Effect handler conflict | Multiple Platforms handle the same effect |
| `E4202` | Missing effect handler | No Platform handles a required effect |
| `E4203` | Entry point type mismatch | `main` signature doesn't match Platform requirement |

### Diagnostic structure

All diagnostics follow a consistent pattern:

```
[error|warning|info] <category> at <location>
  <primary message>
  ─── <explanation>

  help: <actionable suggestion>
```

Diagnostics are available in both human-readable (terminal) and machine-readable (JSON) formats.

## Drawbacks

1. **Conceptual complexity of dual hashing**: Developers must understand the distinction between `sig` and `impl` hashes. While tooling hides most of this, debugging hash mismatches requires understanding the model.

2. **No semver for human communication**: Content hashes are opaque. Developers cannot glance at a hash and know "how different" two versions are. Named aliases and changelogs partially mitigate this, but the loss of semver's human-readable signal is real.

3. **Platform authoring overhead**: Creating a new Platform requires implementing effect handlers and FFI bindings. Most developers will use community Platforms, but the barrier to creating novel Platforms is higher than writing a simple `main()`.

4. **No wildcard imports**: Requiring explicit imports for every module is verbose. The `pub alias` shortcut module pattern mitigates this, but some developers may find it tedious.

5. **No circular dependencies**: Occasionally forces extraction of shared types into third modules, adding structural overhead. In practice, the Elm and Go communities have found this constraint beneficial.

6. **No functors or parameterized modules**: Some patterns natural with OCaml/SML functors require more boilerplate with generics and capabilities. The trade-off is reduced conceptual surface area.

7. **Decentralized discovery**: Without a central registry, finding packages relies on community indices, search engines, and "awesome lists". This is a discoverability trade-off for resilience.

## Alternatives considered

### Single hash (Unison-style full content addressing)

Unison hashes the entire AST, including function names. This provides the strongest content-addressing guarantees but **abandons file-based tooling**: functions are identified by hash, not by name or location. Spore rejected this in favor of dual hashing, which preserves file-based workflows while still providing exact content pinning via `impl`.

### Signature-only hash (no `impl`)

An earlier design considered only tracking `sig` hashes. This preserves API compatibility checking but cannot pin exact implementations, making reproducible builds impossible without additional out-of-band mechanisms (like Git commit SHAs).

### "Last implementation" tracking

Another rejected design tracked whether the implementation had changed since the last build, without computing a deterministic hash. This was deemed too fuzzy—it depends on build ordering and mutable state. The BLAKE3 AST hash is computed directly from the compiled representation and is unambiguous.

### Semantic versioning with content hash verification

A hybrid approach: use semver for human communication but verify with content hashes. Rejected because it introduces two sources of truth. When semver and hashes disagree, which wins? The simplicity of hash-only resolution was preferred.

### Two-level visibility (Elm-style: private + public)

Elm uses only private and public visibility. The research shows most languages eventually add a third level (Go's `internal/`, Rust's `pub(crate)`). Starting with three levels avoids backward-compatible extensions later. `pub(pkg)` covers the common need for package-internal helpers.

### Four+ level visibility (Rust's `pub(super)`, `pub(in path)`)

Fine-grained visibility like `pub(in path)` is rarely used and adds cognitive load. Three levels cover the vast majority of use cases.

### Functors / parameterized modules (OCaml-style)

OCaml/SML functors are the most powerful module system in any language, but they add a separate "module language" that doubles the conceptual surface area. Spore's combination of generics (`where T: Constraint`) and capabilities (`uses [...]`) covers the same use cases with less overhead.

### Built-in Platform (standard library IO)

Most languages provide IO in the standard library. Spore rejected this in favor of Roc-style pluggable Platforms for testability, portability, and supply-chain security. The trade-off is additional complexity in Platform authoring.

## Prior art

### Unison

Unison pioneered content-addressed functions where every definition is identified by the hash of its AST. Spore's dual-hash scheme is directly inspired by Unison but splits the hash into `sig` (API contract) and `impl` (exact code), preserving file-based tooling that Unison abandons.

### Roc

Roc's platform/package separation is the primary inspiration for Spore's Platform system. Roc demonstrated that packages can be pure by default, with IO delegated entirely to the Platform. Spore extends this with algebraic effect handlers (Roc uses tag unions) and multi-Platform support.

### Elm

Elm's file-based modules, prohibition of circular dependencies, and emphasis on simplicity heavily influenced Spore's module design. Elm proves that these constraints scale to large codebases while keeping the system learnable.

### Go

Go's file-based packages, prohibition of circular imports, and `internal/` directory convention informed Spore's visibility model. Go demonstrates that cycle-free packages produce maintainable codebases at Google scale.

### Rust

Rust's `pub(crate)` visibility level and Cargo's `Cargo.lock` file informed Spore's `pub(pkg)` and `.spore-lock` designs. Spore avoids Rust's more complex visibility specifiers (`pub(super)`, `pub(in path)`) in favor of simplicity.

### Koka

Koka's algebraic effect system inspired Spore's integration of effects with module capabilities. Koka demonstrates that effects and modules should be designed together. Spore adds the Platform concept on top of Koka-style effects.

### Nix

Nix's derivation hashes demonstrate the value of content-addressing for reproducible builds. Spore's `impl` hash serves a similar role to Nix's store paths—pinning exact content for bit-for-bit reproducibility.

### Go modules (`go.sum`)

Go's `go.sum` file shows that content hashing for dependency verification is mainstream and practical. Spore takes this further by making content hashes the **primary** identifier, not just a verification mechanism.

## Backward compatibility and migration

### From semantic versioning

Existing ecosystems using semver can migrate by computing content hashes for each versioned release:

```bash
# Migration tool computes hashes from existing version tags
spore migrate --from package.json --to spore.toml
```

The tool:
1. Reads the existing manifest.
2. Resolves Git tags corresponding to version numbers.
3. Computes BLAKE3 `sig` and `impl` hashes for each dependency.
4. Generates `spore.toml` with hash-based declarations.

The human-readable `version` field is preserved for documentation but plays no role in resolution.

### Lock file versioning

The `.spore-lock` file carries a `version` field. Old tools refuse to process newer lock file versions. Migration scripts handle format upgrades:

```bash
spore lock upgrade --from 1 --to 2
```

New fields added to `.spore-lock` are ignored by older tools (forward-compatible). Removal or semantic changes to existing fields trigger a version increment (backward-incompatible).

### Incremental adoption

The module system does not require wholesale adoption:

- Packages can start with inferred capabilities (no `module` header) and add explicit declarations later via `sporec --fixes`.
- Dependencies can mix Git, local path, and registry sources.
- The `version` field in `spore.toml` remains available for human communication during the transition from semver.

## Unresolved questions

1. **Hash truncation for display**: How many hex characters should be shown in human-facing output? 8? 16? Full 64? Should there be a configurable default?

2. **Cross-package `pub(pkg)` boundaries in workspaces**: If two packages in a workspace share a `pub(pkg)` item, should the workspace boundary relax `pub(pkg)` semantics, or must items be promoted to `pub`?

3. **Capability granularity**: The current design uses coarse-grained capability names (e.g., `FileRead`, `NetWrite`). Should fine-grained capabilities (e.g., `filesystem:read:/data`) be part of the language-level type system or remain a tooling concern in `spore.toml`?

4. **Platform versioning**: Platforms themselves evolve. When a Platform changes its handler interface, how are downstream applications notified? Is `spore --permit` sufficient, or do Platforms need a separate compatibility mechanism?

5. **Module-level cost budgets**: The current design tracks cost per-function only. Should modules declare aggregate cost ceilings? What are the semantics when a module's total cost exceeds a declared budget?

6. **Alias chain depth**: Alias chains (alias → alias) are currently forbidden. Should single-level chains be permitted for ergonomic re-exports, or does the restriction stand?

7. **Diamond dependencies with different `impl` hashes**: When two transitive dependencies require the same module with the same `sig` but different `impl` hashes, the current design allows both to coexist. Should the linker deduplicate? Should the developer be warned? What are the binary size implications?

8. **Effect handler composition**: When an application-defined effect maps to Platform effects (e.g., `Logger` → `StdOut`/`StdErr`), how are capability requirements tracked through the composition? Is the current `uses [...]` propagation sufficient?

9. **Conditional compilation**: The `[features]` mechanism in `spore.toml` enables optional dependencies, but the interaction between features and content hashes is underspecified. Does enabling a feature change the `sig` hash?

10. **Offline-first workflows**: How should `spore add` and `spore update` behave when offline? Should the local cache be sufficient for all operations, or are some operations inherently online?
