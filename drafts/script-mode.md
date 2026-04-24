---
sep: null
title: "Draft SEP: Script Mode & Inline Script Metadata"
status: Draft
type: Standards Track
authors:
  - Spore maintainers
created: 2026-04-12
requires:
  - 1
  - 6
  - 8
discussion: "https://github.com/spore-lang/spore-evolution/discussions"
pr: null
superseded_by: null
---

# Draft SEP: Script Mode & Inline Script Metadata

> **Executive Summary**: This proposal adds a first-class script workflow to `spore` without weakening the manifest-backed project model. Scripts use a dedicated file-header block comment with TOML-like metadata, and the target CLI shape separates script mode from project mode instead of borrowing nearby project configuration. Current shipped `spore run <file>` behavior still includes a compatibility path where files under a project's `src/` tree resolve as project-backed entries; this draft defines the stricter future split. The result is a reproducible single-file workflow that remains compatible with named project entries, one-project/one-Platform semantics, and future agent tooling.

## Summary

This SEP defines **script mode** for Spore: a way to execute an explicit `.sp`
file without requiring that file to be a named manifest entry.

The proposal introduces:

- a dedicated file-header block comment for script metadata
- TOML-like script metadata with the initial fields:
  - `requires-spore`
  - `[platform]`
  - `[dependencies]`
- a strict mode split:
  - **proposed**: `spore run <file>` is script mode
  - **proposed**: bare `spore run` and `spore run --entry <name>` are project mode
- explicit project-control flags:
  - `--project <path>`
  - `--no-project`
  - `--entry <name>`
  - `--` to separate CLI arguments from script or entry arguments
- deterministic precedence rules inside each mode

This SEP does **not** decide execution-engine policy (`interp`, `jit`, `aot`,
`auto`). That remains deferred.

## Motivation

Spore already has a strong manifest-backed project model, but it still needs a
small, explicit workflow for:

- one-off automation scripts
- examples embedded in docs or issue discussions
- small reproducers for compiler bugs
- agent-generated helper programs
- gradual migration from a single file into a full project

Requiring `spore.toml` for every runnable file makes these workflows heavier
than necessary. At the same time, a script workflow must not reintroduce the
kind of implicit, environment-shaped behavior that makes builds hard to reason
about.

The goal is therefore **not** "just run any file somehow." The goal is:

- explicit script intent
- reproducible metadata
- clean separation between scripts and projects
- a clean boundary between project entries and free-standing scripts

## Guide-level explanation

### Two ways to run code

Current implementations route **`spore run <file>`** through one of two runtime
paths:

1. **Project mode**
   - `spore run src/main.sp` when that file lives under a manifest-backed
     project's `src/` tree
   - Attaches a project and derives the corresponding entry path from that file's
     location under `src/`.
2. **Standalone file mode**
   - `spore run tools/repro.sp`
   - Runs one explicit source file when it is **not** resolved as a project
     entry under `src/`.

An explicit file path therefore does **not** always force standalone mode.
Files inside a discovered project's `src/` tree are currently routed through
project mode.

### Example: standalone file

```spore
fn main() -> () {
    println("hello")
    return
}
```

Running the file today:

```bash
spore run tools/hello.sp
hello
```

Current standalone-file execution still permits compatibility cases like
`fn main() -> I32`, but `spore run` no longer gives the completion value any
default host meaning. It is not printed automatically, and it does **not**
become the host process exit status.

### Example: explicit file inside a project tree

```bash
spore run tools/migrate.sp
```

Even if `tools/migrate.sp` lives under a directory that also contains
`spore.toml`, the command currently stays in standalone file mode because
project auto-detection only maps files inside the project's `src/` tree to
project entries.

By contrast, `spore run src/main.sp` is currently resolved through project mode,
because the file path can be mapped to a manifest-backed entry under `src/`.

### Future example: project mode with an explicit project root

```bash
spore run .
spore run ../apps/billing
```

This is **proposed CLI surface**, not current shipped behavior. Today `spore run`
expects a file path, not a project directory.

### Future example: run the discovered project entry

```bash
spore run
spore run .
spore run ../apps/billing
```

This is also **proposed CLI surface**, not current shipped behavior. In the
current implementation, project mode is only reached when the explicit file path
passed to `spore run` resolves to a manifest-backed entry under `src/`. When
that happens, the selected entry must satisfy both the Platform startup
signature and the selected Platform package's `[platform].handled-effects` effect
contract.

### Future example: passing script or entry arguments

```bash
spore run tools/repro.sp -- --verbose --limit 10
spore run . -- --queue invoices
```

This argument-passthrough form is **proposed**, not current shipped behavior.

## Reference-level explanation

The sections below include **future script-mode design space** (for example
script headers and richer CLI flags) in addition to the current shipped mode
resolution documented above.

### Terminology

- **standalone file mode**: `spore run <file>` when the explicit file does not
  resolve to a project entry under `src/`
- **project-backed file resolution**: current shipped behavior where
  `spore run <file>` attaches a manifest-backed project only when that explicit
  file resolves to an entry under `src/`
- **project mode**: proposed broader CLI surface such as `spore run`,
  `spore run .`, or `spore run <project-dir>`
- **script header**: a proposed dedicated file-header block comment recognized
  as structured script metadata
- **effective run configuration**: the final configuration after applying CLI
  inputs plus the metadata relevant to the active mode

### Script header format

The script header is recognized only when all of the following are true:

1. it is the first non-whitespace token in the file
2. it is a block comment
3. its opening line starts with `/* spore-script`

Example:

```spore
/* spore-script
requires-spore = ">=0.1.0"

[platform]
path = "../platforms/cli"

[dependencies]
json = { git = "https://github.com/spore-lang/json", sig = "sig:abcd1234" }
*/
```

This header is tooling metadata. It does not become part of the module AST, and
ordinary block comments remain ordinary comments.

If the tool sees a `spore-script` header but cannot parse its body, that is an
error. It must not silently ignore malformed structured metadata.

### Metadata shape

V1 script metadata contains:

- `requires-spore = "<version-range>"`
- `[platform]` carrying script-local platform selection metadata that parallels
  manifest platform configuration, without requiring the exact same table shape
- `[dependencies]` using the same dependency-entry shape as manifest
  `[dependencies]`

The header body is TOML-like so script metadata stays close to `spore.toml`
instead of inventing a parallel configuration language.

### CLI surface

The current public `spore run` surface discussed in this draft is:

```text
spore run FILE
```

Rules today:

- `FILE` may resolve as a project-backed entry only when it maps to a file under a
  discovered project's `src/` tree
- otherwise `spore run FILE` falls back to standalone file mode
- bare `spore run`, `spore run .`, and `spore run <project-dir>` belong to the
  proposed project-mode surface, not the shipped baseline described here
- separate `--project`, `--entry`, and `--no-project` switches are future CLI
  design, not the shipped surface described here

### Project discovery

Project discovery currently happens only when the explicit file path maps into a
discovered project's `src/` tree:

1. **`PATH` is a file under a discovered project's `src/` tree**
   - walk upward from the file's directory
   - attach that project and derive the entry path from the file's path under
     `src/`

If the explicit file path does not map into a discovered project's `src/` tree,
the command falls back to standalone file mode.

### Project mode semantics

In project mode:

- the attached project is manifest-backed
- a file path under `src/` maps to the corresponding project entry path
- bare `spore run` or `spore run <dir>` remains proposed future CLI surface for
  selecting the manifest's inferred/default entry
- if no project can be found, the command fails with an explicit error

Project mode is the path that uses Platform contracts such as `basic-cli`'s
`main() -> ()` startup requirement.

### Script mode semantics

In standalone file mode:

- the explicit file is the execution target
- the file does not need to be a named manifest entry
- files outside any project's `src/` tree run this way, even if they live
  elsewhere under a project root (for example `tools/migrate.sp`)
- standalone execution does **not** use a Platform contract module
- compatibility forms like `fn main() -> I32` are still accepted, but
  standalone execution does **not** print completion values automatically
- standalone execution does **not** convert return values into the host
  process exit status

The explicit `Exit` effect path is currently a project-mode Platform feature,
not a standalone-file return convention.

### Effective configuration and precedence

Current `spore run` precedence is simpler than the future CLI sketched earlier
in this draft because it is still file-selected.

#### Project-backed file resolution

1. start from the explicit file path
2. walk upward from that file's directory looking for a manifest-backed project
3. if the file lands under the discovered project's `src/` tree, derive the
   entry path from that relative location
4. otherwise stay in standalone file mode

#### Standalone file mode

1. the explicit file path
2. no manifest-backed Platform contract
3. no script-header metadata contract yet

In particular, current standalone file mode does not inherit project Platform
contracts just because the file lives somewhere under the same repository root.

### Relationship to named project entries

This SEP does not weaken the named-entry design from the manifest model.

- project entries remain the canonical way to define durable, reviewable,
  reusable executable targets
- script mode is for explicit, file-selected execution
- a script can graduate into a named entry later, but the two concepts are not
  the same

### Formatter, parser, and tooling expectations

- the formatter must preserve the script header as a structured leading block
  comment
- comment-preserving tooling must not reorder or delete the header
- tooling that inspects run configuration should surface both:
  - the raw script metadata
  - the effective run configuration after precedence rules are applied

## Human experience impact

This proposal gives users a lightweight path for running a single file while
keeping behavior explicit.

Benefits:

- easier sharing of examples and reproducers
- less ceremony for small automation tasks
- fewer surprising cwd-shaped behaviors when a file path is explicit
- a clear distinction between "script I am running now" and "entry I maintain as
  part of a project"

Costs:

- more run-mode concepts to learn
- more precedence rules when scripts and projects interact

## Agent experience impact

Structured script headers make it easier for agents to:

- generate runnable reproducers
- infer missing run context from the file itself
- rewrite a script into a manifest entry or a full project later

The deterministic precedence rules also reduce hidden environment dependence,
which is especially valuable when agents run commands from different working
directories or from inside larger monorepos.

## Structured representation / protocol impact

Tools should be able to expose script-mode configuration as structured data.
One possible normalized shape is:

```json
{
  "mode": "script",
  "file": "tools/repro.sp",
  "scriptMetadata": {
    "requiresSpore": ">=0.1.0",
    "platform": { "path": "../platforms/cli" },
    "dependenciesSource": "header"
  },
  "effectiveConfiguration": {
    "platformSource": "script-header",
    "dependencySource": "script-header",
    "projectConfigUsed": false
  }
}
```

The exact JSON or protocol shape can evolve, but the information content should
remain available to CLI JSON output, agents, and future editor integrations.

## Diagnostics impact

Script mode adds several new diagnostics classes:

- malformed `spore-script` header
- unsupported or invalid script metadata keys
- invalid `[platform]` or `[dependencies]` payloads
- conflicting flags (`FILE` with `--entry`, `FILE` with `--project`)
- missing project when project mode is requested
- unresolved `--project` path in project mode
- unmet `requires-spore`

These failures should be reported as first-class diagnostics, not hidden as
generic string errors or silently ignored configuration drift.

## Drawbacks

- introduces a second runnable workflow beside named project entries
- requires tooling to preserve and parse a structured leading comment
- adds precedence rules that must stay stable across CLI, docs, and editor
  tooling

## Alternatives considered

### Require `spore.toml` for every runnable file

Rejected because it makes short-lived scripts, examples, and reproducers too
heavyweight.

### Reuse nearby project configuration for scripts

Rejected because script mode should stay independent from project mode. A file
run as `spore run path/to/file.sp` should not silently inherit dependencies,
entries, or platform choices from whichever project happens to contain it in the
target CLI shape, even though the current shipped implementation still has a
compatibility path for files discovered under a project's `src/` tree.

### Store script metadata in a sidecar file

Rejected because a separate metadata file makes scripts harder to copy, embed,
and generate. The metadata should travel with the script.

### Treat explicit files as project-aware entry paths

Rejected as the long-term default because explicit files are the script-mode
surface in this design. Durable project execution should remain manifest-based
through default entries and named entries, even though the current shipped
implementation still accepts some explicit `src/...` file paths as
project-backed entry resolution.

## Prior art

- **`uv run` and inline script metadata**
  - strong prior art for self-describing scripts
  - useful source for explicit `--no-project`-style control
- **`cargo run`**
  - strong prior art for bare project execution from the current working
    directory
- **single-file runners in Python and JavaScript ecosystems**
  - show the value of copyable, low-ceremony scripts

Spore differs by combining these ideas with a stronger project model,
effect-gated Platform execution, and agent-oriented reproducibility.

## Backward compatibility and migration

- Existing manifest-backed project workflows stay valid.
- Existing explicit-file workflows become a stricter, more explicit script-mode
  surface.
- Files without a `spore-script` header remain ordinary Spore files.
- Ordinary block comments remain valid and unchanged.
- Named manifest entries remain the canonical durable execution surface.

Migration path:

1. start with `spore run tools/repro.sp`
2. add a `spore-script` header when the file needs explicit dependencies or
   platform control
3. promote the script to a named manifest entry if it becomes part of the
   project's durable surface

## Unresolved questions

- Should script mode eventually gain its own lock/caching artifact, or always
  use script-specific cache machinery?
- Should future header metadata add fields for environment variables, dev-only
  tools, or execution hints?
- What should script-mode defaults be when `[platform]` or `[dependencies]` are
  omitted?
- What should the long-term execution-engine policy be (`interp`, `jit`, `aot`,
  `auto`)?
