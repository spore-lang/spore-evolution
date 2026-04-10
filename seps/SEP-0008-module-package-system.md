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

> **Executive Summary**: Defines a content-addressed package system (BLAKE3 dual-hash) with platform-as-package architecture, where platforms provide effect handlers via `foreign fn` declarations. Uses 1-file-=1-module mapping with dot-separated import paths (`import billing.invoice`), `spore.toml` for project configuration, and a two-layer capability ceiling (project + file level). Enforces visibility rules (pub/pub(pkg)/private) at module boundaries, supports multi-file compilation with explicit import resolution, and achieves supply-chain security through capability isolation — downloaded packages declaring `uses [Compute]` provably cannot access IO.

## Summary

This SEP specifies the complete module and package system for the Spore programming language. It defines how code is organized (one file = one module, no explicit `module` declarations), how modules are imported via dot-separated paths (`import billing.invoice`), how visibility is controlled (private / `pub(pkg)` / `pub`), how functions are content-addressed via a dual-hash scheme (signature hash + implementation AST hash using BLAKE3), how packages are structured around `spore.toml` manifests with a `spore.lock` for reproducible builds, how dependencies are resolved without semantic versioning, how IO is abstracted through the Platform system using effect handlers, and how a two-layer capability ceiling (project-wide in `spore.toml` + file-level `#![uses(...)]` pragma) secures the supply chain.

The design synthesizes ideas from Unison (content-addressing), Roc (platform/package separation), Elixir/Python (dot-separated import paths), Elm/Go (file-based modules, no circular dependencies), and Rust (three-level visibility), while introducing novel concepts such as the two-layer capability ceiling, the import/alias separation, and the dual-hash content-addressing scheme that decouples API stability from implementation pinning.

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

There is no `module` keyword — the filesystem **is** the declaration. A file-level pragma may narrow the module's capability ceiling (see [Two-layer capability ceiling](#two-layer-capability-ceiling)):

```spore
// src/billing/invoice.spore
#![uses(PaymentGateway, AuditLog)]

import billing.types
import billing.tax

pub fn generate_invoice(order: Order) -> Invoice ! TaxError | ValidationError
    cost ≤ 3000
    uses [PaymentGateway, AuditLog]
{
    let tax = tax.calculate(order.items, order.region)
    let line_items = build_line_items(order.items, tax)
    finalize(order.customer, line_items)
}

fn build_line_items(items: Vec<Item>, tax: TaxResult) -> Vec<LineItem>
    cost ≤ 500
{
    items |> map(fn(item) -> to_line_item(item, tax))
}
```

Module names use **dot-separated** paths derived from the filesystem. There is no explicit `module` declaration; the file path is the single source of truth.

### Imports

Spore uses **dot-separated** paths for module imports and for item selection:

```spore
// Module import: makes all pub items accessible via qualified name
import billing.invoice

// Module import with rename
import billing.invoice as inv

// Item alias: binds a specific function or type to a local name
alias gen = billing.invoice.generate_invoice
alias Inv = billing.types.Invoice
```

> **Note (D12):** Selective imports (`import billing.invoice.{calculate, Invoice}`) are not supported in v0.1. Use `import billing.invoice` and qualify names, or use `alias` for specific items.

Key rules:

- `import` operates on **modules** only. Dot (`.`) separates path segments.
- `alias` operates on **items** only. You cannot alias a module (use `import ... as` instead).
- No wildcard imports (`import billing.*` is not supported).
- No implicit nested imports (`import billing` does not import `billing.invoice`).

### Visibility

| Level | Keyword | Meaning |
|---|---|---|
| **Private** | *(default)* | Visible only within the defining module |
| **Package-internal** | `pub(pkg)` | Visible to any module within the same package |
| **Public** | `pub` | Visible to any importer, including external packages |

```spore
// Public: any importer can call this
pub fn generate_invoice(order: Order) -> Invoice ! TaxError { ... }

// Package-internal: accessible within this package only
pub(pkg) fn validate(order: Order) -> ValidatedOrder ! ValidationError { ... }

// Private (default): only this module can call this
fn compute_totals(order: ValidatedOrder) -> Invoice { ... }
```

Visibility applies uniformly to functions, types, and aliases.

### Packages

A **package** is a directory containing a `spore.toml` manifest:

```text
my-billing-lib/
├── spore.toml              // package manifest
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

### Script Mode

Script mode is intentionally **out of scope** for SEP-0008. Manifest-free
single-file execution, file-header metadata, and script-vs-project precedence
rules are specified by a separate script-mode SEP. SEP-0008 covers
manifest-backed packages and applications only.

### Platforms

A Platform is the **only** code in a Spore application that can perform real IO. It provides effect handlers that interpret abstract capabilities at runtime:

```spore
// Application code: pure function, emits effects
fn read_config() -> Config ! FileRead {
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

```text
module_name = path.relative_to("src/")
                  .strip_extension(".spore")
                  // path separators become '.' in the module name
```

Module name segments must be lowercase `snake_case`. Reserved names (`platform`,
`test`) may carry tooling conventions, but executable selection is
manifest-level: a module named `main` is only the default entry module by
convention, not by special module semantics.

#### Empty modules

An empty `.spore` file is a valid module. It compiles successfully, exports nothing, and has no capabilities:

```spore
// src/billing/future.spore
// This module is a placeholder for future billing features.
```

```text
$ sporec check src/billing/future.spore

[ok] billing.future
  exports: (none)
  capabilities: []
```

Use cases include namespace placeholders, future feature stubs, and organizational markers within a package directory.

#### Dependency graph construction

The compiler builds a directed acyclic graph (DAG) of module dependencies:

1. Parse all `import` declarations across all modules.
2. Verify no circular dependencies exist (standard topological sort; cycles are compile errors).
3. Determine topological build order. Modules at the same level compile in parallel.

```text
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

```text
import_decl    ::= 'import' module_path ('as' IDENT)?
                   // NOTE (D12): selective imports ('import' module_path '.' '{' IDENT (',' IDENT)* '}')
                   // are not supported in v0.1
alias_decl     ::= visibility? 'alias' IDENT '=' qualified_item
module_path    ::= IDENT ('.' IDENT)*
qualified_item ::= module_path '.' IDENT
```

#### Import ordering convention

The compiler does not enforce import order, but `sporec fmt` auto-sorts imports into four groups separated by blank lines:

```spore
// 1. Platform / standard library imports
import std.collections
import std.text

// 2. External package imports
import http.client as http
import json.parser as json

// 3. Internal package imports
import billing.invoice
import billing.types

// 4. Aliases
alias Invoice = billing.types.Invoice
alias gen = billing.invoice.generate_invoice
```

Within each group, imports are sorted alphabetically by module path.

### Content-addressed functions: dual hashing

#### Hash computation

Every function carries two BLAKE3 hashes:

**Signature hash (`sig`)**:

```text
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

```text
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

[deps."api.handler".generate_invoice]
sig  = "a3f7c2"    # interface contract
impl = "d8e1b4"    # exact implementation (None if partial)

[deps."billing.invoice".calculate]
sig  = "d91e4b"
impl = "b2c4a7"
```

Compatibility checking uses only `sig`: if `sig` is unchanged, dependents need not recompile. The `impl` field pins exact code for reproducible builds.

#### Change detection and `spore --permit`

When a signature changes, all downstream modules referencing the old `sig` are flagged:

```text
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
pub type Invoice { id: InvoiceId, total: Money }       // public type
pub(pkg) type ValidatedOrder { original: Order }        // package-internal type
type InternalCache { entries: Map<String, CacheEntry> } // private type

pub alias GenInv = billing.invoice.generate_invoice     // public alias
pub(pkg) alias Validate = billing.invoice.validate      // package-internal alias
alias Compute = billing.invoice.compute_totals          // private alias
```

#### Visibility enforcement

Attempting to access a private item from another module:

```text
[error] visibility violation at src/api/handler.spore:15
  billing.invoice.compute_totals is private
  ─── it is only visible within module billing.invoice

  help: add `pub` or `pub(pkg)` to its definition in src/billing/invoice.spore
```

Attempting to access a `pub(pkg)` item from an external package:

```text
[error] visibility violation at src/handler.spore:8
  billing.invoice.validate is pub(pkg)
  ─── it is only visible within the 'my-billing-lib' package
  ─── your module 'handler' is in the 'my-api' package
```

In a workspace, `pub(pkg)` restricts visibility to the **current package** (member) only — not to the entire workspace. For workspace member `core` exporting `pub(pkg) fn internal_helper()`, member `web` in the same workspace **cannot** access it. Use `pub` for cross-member visibility.

#### Visibility and the Hole System

Holes inherit the visibility context of their enclosing function. A HoleReport includes only candidates that are **visible** from the hole's location:

```json
{
  "hole": { "name": "payment_logic", "location": "src/api/handler.spore:15" },
  "candidates": [
    {
      "function": "billing.invoice.generate_invoice",
      "visibility": "pub",
      "accessible": true
    },
    {
      "function": "billing.invoice.validate",
      "visibility": "pub(pkg)",
      "accessible": true,
      "note": "same package"
    }
  ],
  "excluded": [
    {
      "function": "billing.invoice.compute_totals",
      "visibility": "private",
      "reason": "private to billing.invoice"
    }
  ]
}
```

This ensures agents filling holes never suggest inaccessible functions.

#### Re-exports via pub aliases

The only re-export mechanism is `pub alias`:

```spore
// src/billing/shortcuts.spore
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
alias invoice = billing.types.Invoice    // ERROR: 'invoice' conflicts with module name
```

### Platform abstraction

#### IO via effect handlers

Application code is pure—it declares capability requirements but never performs IO directly. IO operations are expressed as effects that the Platform's handlers interpret at runtime:

```spore
// Application code: pure
fn fetch_and_save(url: Url, dest: Path) -> Unit ! NetRead | FileWrite {
    let data = Http.get(url)
    File.write(dest, data)
}
```

The type system tracks all effects. Effects propagate upward: if you call a function requiring capability `C`, your function must also declare `uses [C]`.

#### Platform definition

A Platform declares three things:

1. **Capability set**: Which IO capabilities it handles.
2. **Effect handler implementations**: Runtime logic for each capability.
3. **Startup contract**: The function contract that the selected module's
   startup function must satisfy.

```spore
platform CliPlatform {
    version: "1.0.0"
    handles [FileRead, FileWrite, StdOut, StdErr, NetRead, NetWrite, Clock, Spawn, Exit]
    startup: fn(args: List[Str]) -> I32 ! Exit

    handler FileReadHandler {
        File.read(path: Path) -> Result[Bytes, IoError] {
            resume(ffi_read_file(path))
        }
    }
    // ...
}
```

Platform selection in `spore.toml`:

```toml
[platform]
git = "https://github.com/spore-platform/cli"
version = "1.0.0"
```

The compiler verifies:

- Every capability used by application code is handled by the selected Platform.
- The startup function in the selected entry module matches the Platform's startup contract.
- Test and mock Platforms may be substituted during testing, but a project binds to one Platform at a time.

#### One Platform per project

A manifest-backed project selects exactly one Platform. Different deployment
targets use different manifests, overrides, or future higher-level workspace
flows; they are not modeled as multiple concurrent Platform bindings within one
project. Multiple executable targets are modeled as project entries, not as
multiple Platforms.

#### Test Platforms for deterministic testing

Since application code is decoupled from IO implementations, a Test Platform can substitute mock handlers:

```spore
platform TestPlatform {
    handles [FileRead, FileWrite, NetRead, Clock]
    startup: fn() -> TestResult
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

```text
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

#### Two-layer capability ceiling

Capabilities are constrained through a two-layer ceiling system:

**Layer 1 — Project-wide ceiling (`spore.toml`):**

```toml
[capabilities]
allowed = ["IO", "FileRead", "FileWrite", "Net", "PaymentGateway", "AuditLog"]
```

This defines the maximum set of capabilities available to **any** file in the project. No module can exceed this ceiling.

**Layer 2 — File-level narrowing (`#![uses(...)]` pragma):**

Individual files can narrow the project ceiling to declare the maximum capabilities their functions may use:

```spore
// src/billing/invoice.spore
#![uses(PaymentGateway, AuditLog)]
```

- Any function in the module can use a subset of these capabilities.
- No function can use capabilities **not** in this set.
- The file-level pragma must be a **subset** of `spore.toml`'s `[capabilities] allowed`.
- Private functions are also bound by the ceiling.

**Example — two layers in action:**

`spore.toml` allows `IO`, `FileRead`, `FileWrite`, `Net`, `PaymentGateway`, `AuditLog`. But `src/billing/invoice.spore` only needs payment and audit:

```spore
// src/billing/invoice.spore
#![uses(PaymentGateway, AuditLog)]

import billing.types
import billing.tax

pub fn generate_invoice(order: Order) -> Invoice ! TaxError
    uses [PaymentGateway, AuditLog]
{ ... }
```

Meanwhile, `src/net/client.spore` needs only network capabilities:

```spore
// src/net/client.spore
#![uses(Net)]

pub fn fetch(url: Url) -> Result[Bytes, NetError]
    uses [Net]
{ ... }
```

If the `#![uses(...)]` pragma is omitted, the compiler **infers** the ceiling from the union of all `pub` functions' capabilities and emits an `[info]` diagnostic suggesting the explicit declaration. The `sporec --fixes` flag auto-applies the inferred pragma.

#### Capability propagation

Importing a module does **not** grant its capabilities. If you call a function that requires capability `C`, your function must also declare `uses [C]`. Capabilities propagate upward through the call graph.

#### Private functions and the ceiling

Private functions are **also** bound by the module's capability ceiling (if declared). However, they do **not** contribute to the inferred capability set:

```spore
// src/billing/invoice.spore
#![uses(PaymentGateway, AuditLog)]

pub fn generate_invoice(order: Order) -> Invoice ! TaxError
    uses [PaymentGateway, AuditLog]
{ ... }

// Private function: OK — uses subset of module ceiling
fn log_audit(action: String, id: InvoiceId) -> Unit
    uses [AuditLog]
{ ... }

// Private function: ERROR — exceeds module ceiling
fn send_email(to: Email, body: String) -> Unit ! SmtpError
    uses [EmailService]    // not in module ceiling
{ ... }
```

```text
[error] capability ceiling violation at src/billing/invoice.spore:12
  function send_email uses [EmailService]
  module billing.invoice allows [PaymentGateway, AuditLog]
  ─── EmailService is not in the module's capability set

  help: either add EmailService to the file-level pragma:
          #![uses(PaymentGateway, AuditLog, EmailService)]
        or move this function to a module that allows EmailService
```

#### Capability violation error examples and `--fixes` flow

**Ceiling violation**: The error shown above.

**Auto-fix with `sporec --fixes`**: When a module omits its capability pragma, the compiler infers it:

```text
$ sporec check src/billing/invoice.spore

[ok] billing.invoice
  exports: generate_invoice, void_invoice

  [info] inferred module capabilities: [PaymentGateway, AuditLog]
    ─── derived from union of pub function capabilities
    ─── consider adding: #![uses(PaymentGateway, AuditLog)]
```

**Full workflow**:

```bash
sporec check src/              # see [info] diagnostics suggesting capabilities
sporec --fixes src/            # auto-apply all capability declarations
sporec check src/              # clean: no more [info] suggestions
```

The `--fixes` flag writes the inferred capability pragma as the first line of the module file.

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
# Project-level capability ceiling — no file may exceed this set
allowed = ["PaymentGateway", "AuditLog"]

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

Dependencies are declared **per-project** in `spore.toml`, not per-file. The `[capabilities] allowed` list defines the project-wide ceiling; individual files narrow it with `#![uses(...)]`.

Package names are `kebab-case` and globally unique within a registry. Module paths within a package use `snake_case` segments.

### Application Entries

An application declares one or more named **entries** in `spore.toml`. Each
entry selects an **entry module**, and the selected Platform then validates the
module's **startup function** against its **startup contract**.

The default emitted executable or run target name is the selected entry name:

```toml
[package]
name = "my-tool"
type = "application"
default-entry = "my-tool"

[entries.my-tool]
path = "src/main.sp"
```

Additional entries use the same table form:

```toml
[entries.my-tool]
path = "src/main.sp"

[entries.my-tool-migrate]
path = "src/migrate.sp"
```

Each entry path must point to a `.sp` file containing a startup function that
satisfies the selected Platform's startup contract. Today that function is
usually `main`.

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

```text
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

Packages declare required capabilities in `spore.toml`. The `[capabilities] allowed` list defines the project-wide ceiling. Capabilities do **not** propagate automatically—the consuming package must explicitly grant them:

```toml
[capabilities]
# Project-level ceiling
allowed = ["IO", "FileRead", "FileWrite", "Net"]

# Fine-grained grants for dependencies (future direction)
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

A workspace uses a **single `spore.lock`** at the workspace root. Individual members do NOT have their own lock files. This ensures:

- All members share the same dependency versions (no diamond dependency conflicts).
- CI builds are reproducible from a single lock file.
- `spore update` in any member updates the shared lock.

### Dependency type classification

Spore recognizes four dependency types:

| Type | `sig` required? | `impl` required? | When needed |
|---|---|---|---|
| **Interface** (sig-only) | Yes | No | Type-checking without fetching full source |
| **Complete** (sig+impl) | Yes | Yes | Full build, linking, reproducible deployment |
| **Dev** | Yes | Yes | Testing, benchmarking; excluded from production builds |
| **Optional** | Yes | Yes (if enabled) | Controlled by feature flags |

```toml
[dependencies]
json = { sig = "b4e7d3c2a1f9e8d7" }                          # interface-only
http = { sig = "a3f9c2e1d8b7a6f5", impl = "7b8d4f2a1e9c3d5b" } # complete

[dev-dependencies]
test-framework = { sig = "f3e4d5c6b7a8f9e0", impl = "1a2b3c4d5e6f7a8b" }

[dependencies]
metrics = { sig = "e2f3a4b5c6d7e8f9", impl = "9f0a1b2c3d4e5f6a", optional = true }
```

### Dependency declaration format

**Git source** (with branch/tag/rev specifiers):

```toml
[dependencies]
mylib = {
    git = "https://github.com/user/repo",
    branch = "main",           # optional: track a branch
    tag = "v1.2.3",            # optional: pin a tag
    rev = "abc123def456",      # optional: pin a commit
    sig = "a1b2c3d4e5f6a7b8",
    impl = "e5f6a7b8c9d0e1f2"
}
```

**Local path** (development):

```toml
[dependencies]
mylib = { path = "../mylib", sig = "a1b2c3d4e5f6a7b8", impl = "e5f6a7b8c9d0e1f2" }
```

**Named alias** (stable human-readable identifier):

```toml
[dependencies]
mylib = { alias = "mylib-stable-2024", sig = "a1b2c3d4e5f6a7b8", impl = "e5f6a7b8c9d0e1f2" }
```

### Features system

Feature flags enable conditional compilation and optional dependencies:

```toml
[features]
default = ["logging"]
full = ["tls", "metrics", "compression"]
logging = ["dep:logger"]
tls = ["dep:tls-lib"]
metrics = ["dep:metrics"]
compression = []                       # code-level feature, no extra dep
```

Features interact with the hash system as follows: enabling a feature may include additional code paths, which changes the `impl` hash but not the `sig` hash (unless the feature alters the public API). The precise interaction between features and content hashes is a design direction still being refined (see Unresolved Questions).

### `.spore-lock` complete format

The `.spore-lock` file records the fully resolved dependency graph:

```toml
# Auto-generated by `spore lock`. Do not edit.
version = 1

[metadata]
generated-at = "2024-01-15T10:30:00Z"
spore-version = "0.5.2"

[[package]]
name = "web-server"
source = "local"
sig = "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2"
impl = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2"

[[package]]
name = "http"
alias = "std-http-v2"
source = { type = "git", url = "https://github.com/std/http", rev = "abc1234" }
sig = "a3f9c2e1d8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1"
impl = "7b8d4f2a1e9c3d5b6a7f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9"
location = ".spore-store/git/github.com/std/http/abc1234"

[[package]]
name = "json"
alias = "fast-json"
source = { type = "git", url = "https://github.com/std/json", rev = "def5678" }
sig = "b4e7d3c2a1f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0d9c8b7a6f5e4d3"
impl = null                             # interface-only dependency

[dependency-graph]
"web-server" = ["http", "json"]
"http" = ["io"]
"json" = []

[verification]
"http" = {
    sig-algo = "blake3",
    sig-hash = "a3f9c2e1d8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1",
    impl-algo = "blake3",
    impl-hash = "7b8d4f2a1e9c3d5b6a7f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9",
    verified-at = "2024-01-15T10:30:05Z"
}

[capabilities]
"http" = ["NetRead", "NetWrite"]
"io" = ["FileRead", "FileWrite"]

[[platform-locks]]
platform = "linux-x86_64"
packages = ["http", "json", "io"]

[[platform-locks]]
platform = "wasm32"
packages = ["json"]

[build-metadata]
compiler-version = "spore-0.5.2"
build-timestamp = "2024-01-15T10:30:10Z"
```

### Storage backend system

All fetched dependencies are cached in `.spore-store/`:

```text
.spore-store/
├── sigs/                    # Signature cache
│   ├── a3f9c2e1.../
│   │   └── interface.spore-sig
│   └── b4e7d3c2.../
│       └── interface.spore-sig
├── impls/                   # Implementation cache
│   ├── 7b8d4f2a.../
│   │   └── module.spore
│   └── 2f3e4d5c.../
│       └── module.spore
├── git/                     # Git source cache
│   └── github.com/
│       └── user/
│           └── repo/
│               └── abc1234/
│                   └── src/
├── ipfs/                    # IPFS cache
│   └── Qm.../
└── metadata/
    └── index.db             # SQLite index
```

**StorageBackend trait**: The storage system is pluggable via a trait:

```spore
pub trait StorageBackend {
    fn fetch_sig(hash: Hash) -> Result[Signature, FetchError]
    fn fetch_impl(hash: Hash) -> Result[Module, FetchError]
    fn store_sig(sig: Signature) -> Hash
    fn store_impl(module: Module) -> Hash
    fn list_cached() -> List[Hash]
    fn gc() -> Result[Unit, GcError]
}
```

**Four backend implementations**:

1. **Git Backend**: Clones bare repos, checks out specific revisions, computes and verifies hashes, symlinks to `impls/`.
2. **Local Path Backend**: Reads source directly from the local filesystem. Does **not** copy to `.spore-store`—references the original path. Hash is recomputed and verified on each build.
3. **IPFS Backend**: Fetches content by CID, verifies hash, stores locally.
4. **HTTP Registry Backend**: Queries `GET /modules/<alias>/sig/<hash>` and `GET /modules/<alias>/impl/<hash>` endpoints. Registries are index-only—they store metadata, not code. The actual source is fetched from the URL in the metadata.

**Cache strategy**:

- **Content-addressed**: Identical hashes share storage. Two packages using the same dependency version store it once.
- **Global shared**: By default `~/.spore-store` is shared across all projects. Configurable via `~/.spore/config.toml`.
- **Offline-capable**: Once cached, dependencies are available without network access.

**Garbage collection**:

```bash
spore gc               # remove unreferenced cached entries
spore gc --all         # remove all cached entries
```

GC algorithm: (1) scan all `.spore-lock` files in known project directories, (2) mark all referenced hashes, (3) delete unmarked entries from `.spore-store/`.

### Fine-grained capabilities (design direction)

For v0.1, Spore uses **coarse-grained** capability names in the language-level type system:

```spore
fn read_config() -> Config ! IoError
    uses [FileRead]
{ ... }
```

A future direction introduces **path-style fine-grained capabilities** in `spore.toml`:

```toml
[capabilities]
require = [
    "network:listen:8080",
    "filesystem:read:/data",
    "filesystem:write:/logs",
    "env:read:API_KEY",
]
```

The fine-grained capability tree:

```text
network:          filesystem:        env:            process:
  listen:<port>     read:<path>       read:<var>      spawn:<cmd>
  connect:<host>    write:<path>      write:<var>     signal:<pid>
  http:client       delete:<path>
                                    time:           random:
                                      realtime        secure
                                      monotonic       fast
```

For v0.1, the language-level `uses [FileRead]` maps to coarse categories. Fine-grained path restrictions are enforced in `spore.toml` and at runtime (`spore run --allow ...`), not in the type system. Promoting fine-grained capabilities into the type system is reserved for a future SEP.

### Publish and discovery flow

Spore has **no central registry**. Publishing a package means pushing to a Git repository and recording the hashes:

```bash
# 1. Ensure tests pass
spore test && spore audit

# 2. Commit and tag
git add . && git commit -m "Release v1.0.0"
git tag v1.0.0

# 3. Push
git push origin main --tags

# 4. Record hashes for consumers
spore hash
# Output:
#   sig:  a3f9c2e1d8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1
#   impl: 7b8d4f2a1e9c3d5b6a7f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9
```

**Discovery mechanisms**:

1. **Named aliases in README**: Publishers include `spore.toml` snippets with Git URL, alias, and hashes.
2. **Community registry aggregation**: Optional registry servers index Git repositories. They store only metadata (name, description, hashes, source URL)—not code. Queried via `spore search "http server"`.
3. **Awesome lists**: Community-curated lists of packages with hashes and descriptions.

### Subsystem interactions

#### Interaction with the Hole System

Holes respect module boundaries:

- A hole in module A can only be filled with code that respects A's capability ceiling.
- HoleReport candidates are filtered by visibility.
- Partial modules (containing holes) are valid compilation units. They export `pub` items normally, but those items have `impl = None`.
- A module calling a partial function becomes **transitively partial**.

```text
$ sporec --holes

Holes by module:

  billing.invoice (partial)
    ?invoice_logic at line 12
      type: Invoice ! TaxError
      capabilities: [PaymentGateway, AuditLog]
      budget remaining: 2400 ops

  api.handler (partial — depends on partial billing.invoice)
    (no direct holes, but transitively partial)
```

#### Interaction with the Cost Model

Cost is a per-function property (`cost ≤ N`). There are no module-level cost budgets. When a function calls an imported function, the callee's **declared** cost bound is used for estimation:

```text
$ spore cost-report billing.invoice

Module: billing.invoice

  Function costs:
    generate_invoice    cost ≤ 3000  (measured: 2800)
    void_invoice        cost ≤ 500   (measured: 320)

  Module aggregate:
    max single-call cost: 3000 ops (generate_invoice)
    total declared budget: 3500 ops
```

#### Interaction with the Snapshot System

Snapshots use `sig` hashes only at the module and package level (impl changes do not propagate):

| Level | What is hashed | When it changes |
|---|---|---|
| Function `sig` | Canonical signature | Any signature component changes |
| Function `impl` | Compiled AST | Body changes, hole filling |
| Module interface | Sorted hash of `pub` + `pub(pkg)` `sig` hashes | Any exported signature changes |
| Package API | Sorted hash of module interface hashes | Any module interface changes |

#### Interaction with the Error System

Error types follow the same visibility rules as all other types. A function's error list (`! TaxError`) must reference only error types visible from the function's module:

```spore
// src/api/handler.spore
import billing.invoice
import billing.errors

pub fn handle_create(req: Request) -> Response ! errors.BillingError | ParseError
    uses [PaymentGateway, AuditLog]
{
    let order = parse_request(req)
    let invoice = invoice.generate_invoice(order)
    Response.ok(invoice)
}
```

### Edge cases

#### Modules with only types

A module containing only type definitions is valid and pure:

```spore
// src/billing/types.spore
pub type Invoice { id: InvoiceId, total: Money, status: InvoiceStatus }
pub type InvoiceStatus { Draft, Sent, Paid, Void }
pub type LineItem { description: String, quantity: Int, unit_price: Money }
```

```text
$ sporec check src/billing/types.spore

[ok] billing.types
  exports: Invoice, InvoiceStatus, LineItem
  capabilities: []
  cost: 0 (types only)
```

#### Diamond dependencies in `.spore-lock`

Diamond dependencies use consistent hashes:

```text
       billing.types
        ↑        ↑
        │        │
  billing.invoice  billing.tax
        ↑        ↑
        │        │
       api.handler
```

The `.spore-lock` records the same `sig` and `impl` for `billing.types.Invoice` regardless of which path reached it:

```toml
[deps."billing.invoice".Invoice]
sig  = "8c3f01"
impl = "e9f3d2"

[deps."billing.tax".Invoice]
sig  = "8c3f01"
impl = "e9f3d2"
```

#### Modules with holes

Partial modules can be imported and their types used. Only function calls at runtime are blocked:

```spore
// src/billing/invoice.spore (has holes)
pub fn generate_invoice(order: Order) -> Invoice ! TaxError {
    ?invoice_logic
}

// src/api/handler.spore
import billing.invoice

// Compiles fine — handler is transitively partial
pub fn handle(req: Request) -> Response ! ApiError {
    let inv = invoice.generate_invoice(parse_order(req))
    Response.ok(inv)
}
```

```text
$ sporec check

[partial] billing.invoice.generate_invoice
  holes: ?invoice_logic

[partial] api.handler.handle
  depends on partial: billing.invoice.generate_invoice

Build: success (2 partial functions)
```

#### Alias chains are forbidden

```text
[error] alias chain detected at src/api/shortcuts.spore:3
  api_gen → billing.shortcuts.gen → billing.invoice.generate_invoice
  ─── aliases must point directly to original definitions

  help: use `pub alias api_gen = billing.invoice.generate_invoice` instead
```

### Platform details

#### Comparison with other approaches

| Approach | IO Model | Testability | Platform Independence | Example |
|---|---|---|---|---|
| **Traditional** | Built-in IO | Needs mocking | Low | C, Go, Java |
| **Monadic IO** | IO Monad | Medium | Low | Haskell |
| **Effect System** | Algebraic Effects | High | Medium | Koka, Eff |
| **Spore Platform** | Effect Handlers + Platform | **Very high** | **Very high** | Roc, Spore |

Spore and Roc share the same design philosophy: no built-in Platform; all Platforms are third-party packages.

#### Web Platform example

```spore
platform WebPlatform {
    version: "1.0.0"
    handles [HttpServer, NetRead, NetWrite, Clock, Spawn, DbQuery]
    startup: fn(req: Request) -> Response ! HttpServer | DbQuery

    handler HttpServerHandler {
        Server.listen(port: U16, handler: fn(Request) -> Response) {
            resume(ffi_listen_http(port, handler))
        }
    }
}
```

#### Lambda Platform example

```spore
platform LambdaPlatform {
    version: "1.0.0"
    handles [NetRead, NetWrite, S3Read, S3Write, DynamoRead, DynamoWrite]
    startup: fn(event: JsonValue) -> JsonValue ! S3Read | DynamoWrite

    handler S3Handler {
        S3.get(bucket: Str, key: Str) -> Result[Bytes, S3Error] {
            resume(aws_s3_get(bucket, key))
        }
    }
}
```

#### Handler dispatch modes

Effect handlers support three dispatch modes:

1. **Direct FFI**: Handler calls native code directly.

```spore
handler DirectFfi {
    File.read(path: Path) -> Result[Bytes, IoError] {
        resume(ffi_read_file(path.to_bytes()))
    }
}
```

2. **Effect composition**: Handler translates high-level effects into lower-level ones.

```spore
handler HttpClientHandler uses [NetRead, NetWrite] {
    Http.get(url: Url) -> Result[Response, HttpError] {
        let socket = TcpSocket.connect(url.host, url.port)?
        socket.write(format_http_request(url))?
        let raw = socket.read_until_eof()?
        resume(parse_http_response(raw))
    }
}
```

3. **Stateful handler**: Handler maintains mutable state across calls.

```spore
handler StatefulCache {
    var cache: Map[String, Bytes] = Map.new()

    Cache.get(key: String) -> Option[Bytes] {
        resume(cache.get(key))
    }
    Cache.set(key: String, value: Bytes) -> Unit {
        cache.insert(key, value)
        resume(())
    }
}
```

**FFI integration**: Platform handlers call native code via `foreign fn` declarations:

```spore
foreign fn ffi_read_file(path: Bytes) -> FfiResult[Bytes]
foreign fn ffi_write_file(path: Bytes, content: Bytes) -> FfiResult[Unit]
```

Corresponding Rust implementation:

```rust
#[no_mangle]
pub extern "C" fn ffi_read_file(path: SporeBytes) -> FfiResult<SporeBytes> {
    match std::fs::read(unsafe { path.to_str() }) {
        Ok(bytes) => FfiResult::ok(SporeBytes::from_vec(bytes)),
        Err(e) => FfiResult::err(e.raw_os_error().unwrap_or(-1)),
    }
}
```

#### Record/Replay testing mode

For integration tests, a **RecordingPlatform** captures IO events during real execution:

```spore
platform RecordingPlatform {
    handles [FileRead, NetRead]

    handler RecordingHandler {
        var log: List[IoEvent] = []

        File.read(path: Path) -> Result[Bytes, IoError] {
            let result = real_file_read(path)
            log.push(IoEvent.FileRead(path, result))
            resume(result)
        }
    }
}
```

A **ReplayPlatform** then replays the recorded events deterministically:

```spore
platform ReplayPlatform {
    handles [FileRead, NetRead]

    handler ReplayHandler {
        var log: List[IoEvent] = load_log("test_recording.log")
        var index: U32 = 0

        File.read(path: Path) -> Result[Bytes, IoError] {
            let event = log.get(index)
            index = index + 1
            match event {
                IoEvent.FileRead(p, result) if p == path => resume(result),
                _ => panic("Unexpected IO: expected FileRead for {}", path),
            }
        }
    }
}
```

#### Platform development guide

Creating a new Platform follows six steps:

**Step 1**: Initialize the Platform project.

```bash
spore init my-platform --type platform
```

**Step 2**: Define the Platform contract in `platform.spore`:

```spore
platform EmbeddedPlatform {
    version: "0.1.0"
    handles [GpioRead, GpioWrite, Timer, SerialRead, SerialWrite]
    startup: fn() -> Never ! GpioRead | GpioWrite | Timer

    config: {
        cpu_freq: U32,
        gpio_pins: U8,
    }
}
```

**Step 3**: Implement effect handlers:

```spore
// handlers/gpio.spore
handler GpioHandler {
    Gpio.read(pin: U8) -> Bool {
        resume(ffi_gpio_read(pin))
    }
    Gpio.write(pin: U8, value: Bool) -> Unit {
        ffi_gpio_write(pin, value)
        resume(())
    }
}
```

**Step 4**: Write FFI bindings (Rust/C):

```rust
#[no_mangle]
pub extern "C" fn ffi_gpio_read(pin: u8) -> bool {
    unsafe {
        let reg = (GPIO_BASE + pin as usize * 4) as *const u32;
        core::ptr::read_volatile(reg) != 0
    }
}
```

**Step 5**: Write documentation and examples for Platform consumers.

**Step 6**: Publish the Platform (same as any package—push to Git, record hashes).

Platforms are content-addressed packages like any other, following the same `sig`/`impl` dual-hash scheme.

#### Platform subsystem interactions

| Subsystem | Interaction |
|---|---|
| **Concurrency** | `Spawn` is an effect; the Platform provides the `SpawnHandler` (backed by a thread pool, tokio, etc.) |
| **Package management** | Platforms are ordinary Spore packages, fetched and cached via the same content-addressed system |
| **Capability system** | Platform defines the capability upper bound. `App.uses ⊆ Platform.handles` is verified at compile time |
| **Cost model** | Platform effects carry cost annotations: `File.read @cost(io=1)`. The compiler uses these for cost analysis |
| **Compiler** | Generates an effect routing table mapping each effect to its handler Platform. Embedded in compiled output |

#### Platform API reference

**CLI Platform** (complete effect definitions):

```spore
effect FileRead {
    fn read(path: Path) -> Result[Bytes, IoError]
    fn read_to_string(path: Path) -> Result[Str, IoError]
    fn exists(path: Path) -> Bool
    fn list_dir(path: Path) -> Result[List[DirEntry], IoError]
}

effect FileWrite {
    fn write(path: Path, content: Bytes) -> Result[Unit, IoError]
    fn append(path: Path, content: Bytes) -> Result[Unit, IoError]
    fn delete(path: Path) -> Result[Unit, IoError]
    fn create_dir(path: Path) -> Result[Unit, IoError]
}

effect StdOut { fn println(s: Str) -> Unit; fn print(s: Str) -> Unit }
effect StdErr { fn eprintln(s: Str) -> Unit }
effect Clock  { fn now() -> Timestamp; fn sleep(duration: Duration) -> Unit }
effect Spawn  { fn spawn[T](f: fn() -> T) -> Task[T]; fn await_task[T](task: Task[T]) -> T }
effect Exit   { fn exit(code: I32) -> Never }
```

**Comparison with Roc, Elm, and Koka**:

| Feature | Roc | Elm | Koka | Spore |
|---|---|---|---|---|
| Platform concept | ✓ | Partial (runtime) | ✗ | ✓ |
| Effect system | ✗ (tag unions) | ✗ (Cmd/Sub) | ✓ | ✓ |
| One Platform / project | ✗ | ✗ | N/A | ✓ |
| Test Platform | Mock Platform | Mock Cmd | Manual mock | Test Platform |
| Startup contract | Platform-defined | Fixed (main) | Fixed (main) | Platform-defined |
| Concurrency | Platform-provided | Built-in runtime | Effect handler | Effect handler |

### CLI command reference

#### Module and build commands

```text
sporec check [path]           Check modules for errors
sporec check --show-deps      Show dependency graph
sporec build                  Build all modules in topological order
sporec build --show-order     Show build order
sporec --holes [path]         List all holes across modules
sporec --fixes [path]         Auto-apply inferred capability declarations
sporec fmt [path]             Format source, including import ordering
```

#### Snapshot and lock commands

```text
spore snapshot                Show package/module/function hashes (sig + impl)
spore snapshot --show <mod>   Show specific module's interface hash
spore --permit <function>     Accept a sig change, update .spore-lock
spore --permit --all          Accept all pending sig changes
spore lock                    Generate or update .spore-lock
spore lock --verify           Verify .spore-lock matches current state
```

#### Package management commands

```text
spore init [name]             Initialize new project
spore add <source>            Add dependency (Git URL, local path)
  --alias <name>              Set named alias
  --tag <tag>                 Pin to Git tag
  --branch <branch>           Track Git branch
  --rev <sha>                 Pin to Git commit
  --sig-only                  Interface-only dependency
  --dev                       Add as dev dependency
  --optional                  Add as optional dependency

spore remove <name>           Remove dependency from spore.toml
spore update [name]           Update dependency hashes
  --tag <tag>                 Update to specific tag
  --recompute-hash            Recompute hashes for path dependencies

spore fetch                   Fetch all dependencies to local cache
  --jobs <N>                  Parallel fetch (default: 8)
  --sigs-only                 Fetch signatures only (for type-checking)

spore lock                    Generate .spore-lock from spore.toml
spore lock --verify           Verify .spore-lock integrity
```

#### Audit and inspection commands

```text
spore audit [package]         Audit package capability usage
spore audit --all             Full audit (capabilities, hashes, cycles, unused)
spore deps [module]           Show dependency tree
spore deps --reverse <mod>    Show what depends on a module
spore deps --depth <N>        Limit tree depth
spore deps --json             Output as JSON
spore cost-report <module>    Show cost summary for a module
spore exports <module>        List a module's public API
spore hash                    Compute current module's sig and impl hashes
spore hash --sig-only         Show signature hash only
spore gc                      Clean unused cache entries
spore gc --all                Remove all cache
```

#### Example workflow

```bash
# 1. Create a new project
spore init my-app

# 2. Add dependencies
spore add https://github.com/spore-std/http --alias std-http
spore add https://github.com/spore-std/json --sig-only

# 3. Write code, then check
sporec check src/

# 4. Auto-apply capability declarations
sporec --fixes src/

# 5. Build and test
sporec build && spore test

# 6. If a dependency's signature changed, review and accept
spore --permit billing.tax.calculate

# 7. Audit before deployment
spore audit --all
```

### End-to-end example scenarios

#### Scenario 1: Create a new project

```bash
mkdir my-app && cd my-app
spore init
spore add https://github.com/spore-std/http --alias std-http
spore add https://github.com/spore-std/json --sig-only
sporec check src/
sporec build
spore run --allow network:listen:8080
```

#### Scenario 2: Update a dependency

```bash
spore deps                      # view current dependency tree
spore update http               # update to latest commit
spore test                      # verify tests still pass
spore audit                     # check for capability changes
git add .spore-lock spore.toml
git commit -m "Update http to latest"
```

#### Scenario 3: Handle diamond dependencies

Two libraries depend on the same `utils` package with the same `sig` but different `impl`:

```text
$ spore deps
my-app
├── lib-a@sig:aaa+impl:bbb
│   └── utils@sig:v1+impl:v1
└── lib-b@sig:ccc+impl:ddd
    └── utils@sig:v1+impl:v2
```

Both versions coexist. If `my-app` directly depends on `utils`, it must choose explicitly: `spore add utils --impl v1`.

#### Scenario 4: Local monorepo development

```toml
# packages/app/spore.toml
[dependencies]
core  = { path = "../core",  sig = "...", impl = "..." }
utils = { path = "../utils", sig = "...", impl = "..." }
```

```bash
# After editing core or utils:
spore update --recompute-hash   # update hashes for path deps
sporec build
```

#### Scenario 5: Publish a package

```bash
spore test && spore audit
spore hash                      # record sig + impl hashes
git add . && git commit -m "Release v1.0.0"
git tag v1.0.0
git push origin main --tags
# Update README with spore.toml snippet including hashes
```

### Glossary

| Term | Definition |
|---|---|
| **Content-addressed** | Identifying resources by the hash of their content rather than by name or location |
| **Signature hash (`sig`)** | BLAKE3 hash of a function's public contract (params, return type, errors, capabilities, cost) |
| **Implementation hash (`impl`)** | BLAKE3 hash of a function's compiled AST; `None` for partial functions |
| **Named alias** | A human-readable identifier mapping to a specific set of content hashes |
| **Dependency graph** | DAG of module/package import relationships |
| **Capability** | A declared permission for a function to perform a specific category of operation |
| **Capability ceiling** | The maximum set of capabilities a module's functions may use |
| **Lock file (`.spore-lock`)** | Machine-generated file recording the full resolved dependency graph with hashes |
| **Diamond dependency** | When the same module is reached via multiple paths in the dependency graph |
| **Reproducible build** | A build that produces identical output from identical inputs (ensured by `impl` hashes) |
| **Platform** | A Spore package that provides effect handlers for IO capabilities |
| **Effect handler** | Runtime implementation that interprets abstract effect operations |
| **Hole** | A placeholder (`?name`) in a function body, marking incomplete code |
| **Partial function** | A function containing holes; has `impl = None` until all holes are filled |

## Human experience impact

### Readability and navigation

- **File = module** eliminates the confusion of Rust's `mod`/`use` distinction or OCaml's separate `.mli` files. Opening a `.spore` file immediately tells you the module name — no `module` keyword needed.
- **Dot-separated imports** (`import billing.invoice`) use a uniform separator for both path segments and item access, avoiding the confusion of mixing `/` and `.`. The import path mirrors the module name directly.
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
| `E4203` | Startup contract mismatch | Startup function signature doesn't match Platform requirement |

### Diagnostic structure

All diagnostics follow a consistent pattern:

```text
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

- Packages can start with inferred capabilities (no `#![uses(...)]` pragma) and add explicit declarations later via `sporec --fixes`.
- Dependencies can mix Git, local path, and registry sources.
- The `version` field in `spore.toml` remains available for human communication during the transition from semver.

## Unresolved questions

1. **Hash truncation for display**: How many hex characters should be shown in human-facing output? 8? 16? Full 64? Should there be a configurable default?

2. **~~Cross-package `pub(pkg)` boundaries in workspaces~~**: Resolved — `pub(pkg)` restricts visibility to the current package (member) only. Items must be promoted to `pub` for cross-member access.

3. **Capability granularity**: The current design uses coarse-grained capability names (e.g., `FileRead`, `NetWrite`). Should fine-grained capabilities (e.g., `filesystem:read:/data`) be part of the language-level type system or remain a tooling concern in `spore.toml`?

4. **Platform versioning**: Platforms themselves evolve. When a Platform changes its handler interface, how are downstream applications notified? Is `spore --permit` sufficient, or do Platforms need a separate compatibility mechanism?

5. **Module-level cost budgets**: The current design tracks cost per-function only. Should modules declare aggregate cost ceilings? What are the semantics when a module's total cost exceeds a declared budget?

6. **Alias chain depth**: Alias chains (alias → alias) are currently forbidden. Should single-level chains be permitted for ergonomic re-exports, or does the restriction stand?

7. **Diamond dependencies with different `impl` hashes**: When two transitive dependencies require the same module with the same `sig` but different `impl` hashes, the current design allows both to coexist. Should the linker deduplicate? Should the developer be warned? What are the binary size implications?

8. **Effect handler composition**: When an application-defined effect maps to Platform effects (e.g., `Logger` → `StdOut`/`StdErr`), how are capability requirements tracked through the composition? Is the current `uses [...]` propagation sufficient?

9. **Conditional compilation**: The `[features]` mechanism in `spore.toml` enables optional dependencies, but the interaction between features and content hashes is underspecified. Does enabling a feature change the `sig` hash?

10. **Offline-first workflows**: How should `spore add` and `spore update` behave when offline? Should the local cache be sufficient for all operations, or are some operations inherently online?

---

## Appendix A: Grammar summary

```text
// File-level capability pragma (replaces module header)
file_pragma    ::= '#![uses(' capability (',' capability)* ')]'
cap_list       ::= '[' capability (',' capability)* ']'
capability     ::= UPPER_IDENT

// Imports and aliases
import_decl    ::= 'import' module_path ('as' IDENT)?
                   // NOTE (D12): selective imports not supported in v0.1
alias_decl     ::= visibility? 'alias' IDENT '=' qualified_item
module_path    ::= IDENT ('.' IDENT)*
qualified_item ::= module_path '.' IDENT

// Visibility
visibility     ::= 'pub' | 'pub(pkg)'

// Function declarations
fn_decl        ::= visibility? 'fn' IDENT generic_params? '(' params ')' '->' type
                    error_clause? cost_clause? uses_clause?
                    block
generic_params ::= '[' IDENT (',' IDENT)* ']'
params         ::= (param (',' param)*)?
param          ::= IDENT ':' type
error_clause   ::= '!' '[' type (',' type)* ']'
cost_clause    ::= 'cost' '≤' expr
uses_clause    ::= 'uses' cap_list

// Type declarations
type_decl      ::= visibility? 'type' IDENT generic_params? '{' field_list '}'
                 | visibility? 'type' IDENT generic_params? '=' type
field_list     ::= (field (',' field)*)?
field          ::= IDENT ':' type

// Platform declarations
platform_decl  ::= 'platform' IDENT '{' platform_body '}'
platform_body  ::= ('version:' STRING)?
                   ('handles' cap_list)
                   ('startup:' type)
                   handler_decl*

// Handler declarations
handler_decl   ::= 'handler' IDENT ('uses' cap_list)? '{' handler_body '}'
handler_body   ::= (fn_decl | var_decl)*

// Effect declarations
effect_decl    ::= 'effect' IDENT '{' effect_fn* '}'
effect_fn      ::= 'fn' IDENT '(' params ')' '->' type

// spore.toml (TOML subset)
// [package]       name, version, type, description, license, authors, spore-version, default-entry
// [capabilities]  allowed
// [dependencies]  <name> = { git|path|alias, sig, impl?, optional?, branch?, tag?, rev? }
// [dev-dependencies]
// [features]      <name> = [deps/features]
// [entries.<name>] path = STRING
// [platform]      git|path, version?, handles?
// [overrides]     <name> = { sig, impl }
// [build]         script
// [metadata]      arbitrary key-value
```

## Appendix B: CLI command reference (grouped)

### Module commands

| Command | Description |
|---|---|
| `sporec check [path]` | Check modules for errors and warnings |
| `sporec build` | Compile all modules in topological order |
| `sporec --holes [path]` | List all holes in modules |
| `sporec --fixes [path]` | Auto-apply inferred capability declarations |
| `sporec fmt [path]` | Format source code (including import ordering) |

### Snapshot and hash commands

| Command | Description |
|---|---|
| `spore snapshot` | Show function, module, and package hashes |
| `spore hash` | Compute current module/function hashes |
| `spore --permit <fn>` | Accept a signature change, update `.spore-lock` |
| `spore --permit --all` | Accept all pending signature changes |
| `spore exports <module>` | List a module's public API with hashes |
| `spore cost-report <mod>` | Show cost summary for a module |

### Package management commands

| Command | Description |
|---|---|
| `spore init [name]` | Initialize new project |
| `spore add <source>` | Add a dependency |
| `spore remove <name>` | Remove a dependency |
| `spore update [name]` | Update dependency hashes |
| `spore lock` | Generate or update `.spore-lock` |
| `spore lock --verify` | Verify `.spore-lock` integrity |
| `spore fetch` | Download dependencies to local cache |

### Audit and inspection commands

| Command | Description |
|---|---|
| `spore audit` | Audit package capabilities, hashes, cycles |
| `spore deps` | Show dependency tree |
| `spore deps --reverse <m>` | Show reverse dependencies |
| `spore gc` | Clean unused cache entries |
