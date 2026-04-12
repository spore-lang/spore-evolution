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

> **Executive Summary**: This proposal adds a first-class script workflow to `spore` without weakening the manifest-backed project model. Scripts use a dedicated file-header block comment with TOML-like metadata, and script mode is explicitly separated from project mode rather than borrowing nearby project configuration. The result is a reproducible single-file workflow that remains compatible with named project entries, one-project/one-Platform semantics, and future agent tooling.

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
  - `spore run <file>` is script mode
  - bare `spore run` and `spore run --entry <name>` are project mode
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

After this SEP, `spore run` has two user-facing modes:

1. **Project mode**
   - `spore run`
   - `spore run --entry api`
   - `spore run --project ../apps/billing --entry api`
   - Runs a named project entry from an attached project.
2. **Script mode**
   - `spore run tools/repro.sp`
   - Runs one explicit source file as a script, independent of project config.

An explicit `<file>` means script mode. `--entry <name>` means project mode.
They are mutually exclusive.

### Example: standalone script

```spore
/* spore-script
requires-spore = ">=0.1.0"

[platform]
path = "../platforms/cli"

[dependencies]
json = { git = "https://github.com/spore-lang/json", sig = "sig:abcd1234" }
*/

fn main() -> () {
    println("hello from script mode")
    return
}
```

Running the file:

```bash
spore run tools/hello.sp
```

The header makes the script self-describing: the tool can validate the required
Spore version, choose the script's platform, and resolve its external
dependencies even when no `spore.toml` exists nearby.

### Example: script inside a project tree

```bash
spore run tools/migrate.sp
```

Even if `tools/migrate.sp` lives under a directory that also contains
`spore.toml`, the command still stays in script mode. Nearby project manifests,
entries, dependencies, and platforms are ignored. The script runs from its own
header metadata plus script-mode defaults only.

### Example: project mode with an explicit project root

```bash
spore run --project ../apps/billing
spore run --project ../apps/billing --entry worker
```

`--project <path>` belongs to project mode. It selects the project whose default
entry or named entry should run.

### Example: run a project entry

```bash
spore run
spore run --entry worker
spore run --project ../apps/billing --entry worker
```

Bare `spore run` is project mode: it finds a project from the current working
directory and runs its default entry. `--entry <name>` selects a named manifest
entry instead. `--project <path>` replaces cwd-based project discovery.

### Passing script or entry arguments

```bash
spore run tools/repro.sp -- --verbose --limit 10
spore run --entry worker -- --queue invoices
```

`--` separates `spore run` flags from the arguments passed through to the script
or selected entry.

## Reference-level explanation

### Terminology

- **script mode**: `spore run <file>` with one explicit source file
- **project mode**: `spore run` or `spore run --entry <name>`
- **script header**: the dedicated file-header block comment recognized as
  structured script metadata
- **effective run configuration**: the final configuration after applying CLI
  flags plus the metadata relevant to the active mode

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
- `[platform]` using the same schema as manifest `[platform]`
- `[dependencies]` using the same dependency-entry shape as manifest
  `[dependencies]`

The header body is TOML-like so script metadata stays close to `spore.toml`
instead of inventing a parallel configuration language.

### CLI surface

The intended `spore run` surface is:

```text
spore run [--project PATH] [--entry NAME] [-- ARGS...]
spore run FILE [--no-project] [-- ARGS...]
```

Rules:

- `FILE` and `--entry` are mutually exclusive
- `FILE` and `--project` are mutually exclusive
- bare `spore run` is valid only in project mode
- `spore run <file>` is script mode
- `--no-project` is allowed only in script mode; it is an explicit assertion,
  not a request to detach from a project after project discovery

### Project discovery

Project discovery exists only in project mode:

1. **If `--project <path>` is present**
   - attach exactly that project
2. **Else**
   - discover a project by walking upward from the current working directory

Script mode performs no project discovery.

### Project mode semantics

In project mode:

- the attached project is required
- `--entry <name>` selects a named manifest entry
- without `--entry`, the manifest's `default-entry` is used
- if no project can be found, the command fails with an explicit error

Project mode is manifest-backed. It does not consult script headers because no
explicit script file is being selected.

### Script mode semantics

In script mode:

- the explicit `FILE` is the execution target
- the file does not need to be a named manifest entry
- the file may live inside or outside a project tree
- project manifests, project dependencies, project entries, project platforms,
  and `default-entry` are ignored
- the effective run configuration is derived only from:
  - CLI script-mode flags
  - the script header, if present
  - script-mode defaults

If a file lives inside a project tree but is invoked as `spore run <file>`, it
still remains script mode.

### Effective configuration and precedence

Project mode and script mode have different precedence rules.

#### Project mode

1. `--project <path>` if present
2. cwd-based project discovery otherwise
3. `--entry <name>` if present
4. manifest `default-entry` otherwise

#### Script mode

1. script-mode CLI assertions such as `--no-project`
2. script header metadata
3. script-mode defaults

The resulting precedence is:

| Concern | Highest precedence | Fallback |
|---|---|---|
| Entry selection | `--entry` | manifest `default-entry` |
| Project root (project mode only) | `--project` | cwd discovery |
| External dependencies (script mode) | script `[dependencies]` | script-mode defaults |
| Platform (script mode) | script `[platform]` | script-mode defaults |
| Spore version requirement (script mode) | script `requires-spore` | active tool defaults only |

In particular, script mode never inherits project dependencies or platform.

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
entries, or platform choices from whichever project happens to contain it.

### Store script metadata in a sidecar file

Rejected because a separate metadata file makes scripts harder to copy, embed,
and generate. The metadata should travel with the script.

### Treat explicit files as project-aware entry paths

Rejected because explicit files are the script-mode surface in this design.
Durable project execution should remain manifest-based through default entries
and named entries.

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
capability-gated Platform execution, and agent-oriented reproducibility.

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
