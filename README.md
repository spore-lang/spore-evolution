# spore-evolution

Proposal portal for the Spore programming project.

This repository is the long-lived home for Spore Enhancement Proposals (SEPs):
process decisions, language design records, tooling protocols, package-system
design, and other cross-cutting changes that affect Spore as a whole.

## Read this first

The SEPs in this repository are design records. They are not, by themselves, the
current implementation truth, a compatibility guarantee, or a public release
contract for Spore.

For current release behavior, installation guidance, supported syntax, and
implementation status, start with the implementation repository:
`spore/README.md` and `spore/docs/DESIGN.md`.

This repository is authoritative for proposal history and accepted design
direction. During the bootstrap phase, Draft SEPs may still include target
behavior, future protocol shapes, or examples that are ahead of the compiler.

**Current surface typing baseline:** default unsuffixed literals are **`I64`**
for integers and **`F64`** for floats; UTF-8 text is **`Str`**; there is no
`Char` type. SEP-0002 owns the full type-system rules and metavariables for
other fixed widths.

## SEP status

| SEP | Title | Status | Role |
|---|---|---|---|
| [SEP-0000](seps/SEP-0000-process.md) | Spore Enhancement Proposal Process | Accepted | Repository process and lifecycle |
| [SEP-0001](seps/SEP-0001-core-syntax.md) | Core Syntax & Signatures | Accepted | Root surface grammar and signature layout |
| [SEP-0002](seps/SEP-0002-type-system.md) | Type System | Draft | Type semantics and checking |
| [SEP-0003](seps/SEP-0003-effect-system.md) | Effect System | Draft | Effect algebra, handlers, and diagnostics |
| [SEP-0004](seps/SEP-0004-cost-analysis.md) | Cost Analysis & Decidability | Draft | Four-slot cost model and verification |
| [SEP-0005](seps/SEP-0005-hole-system.md) | Hole System & Agent Protocol | Draft | Typed holes and agent-facing reports |
| [SEP-0006](seps/SEP-0006-compiler-architecture.md) | Compiler Architecture | Draft | Compiler pipeline and diagnostics |
| [SEP-0007](seps/SEP-0007-concurrency-model.md) | Concurrency Model | Draft | Structured concurrency semantics |
| [SEP-0008](seps/SEP-0008-module-package-system.md) | Module & Package System | Draft | Modules, manifests, platforms, and packages |
| [SEP-0009](seps/SEP-0009-standard-library.md) | Standard Library Surface | Draft | Prelude, core modules, and platform libraries |

The generated machine-readable index is [`seps-index.json`](seps-index.json).

## Reading path

Read [VISION.md](VISION.md) first for the design philosophy. Then use SEPs in
dependency order:

1. [SEP-0000](seps/SEP-0000-process.md) for how decisions are made.
2. [SEP-0001](seps/SEP-0001-core-syntax.md) for accepted syntax forms.
3. [SEP-0002](seps/SEP-0002-type-system.md) through [SEP-0004](seps/SEP-0004-cost-analysis.md) for core static semantics.
4. [SEP-0005](seps/SEP-0005-hole-system.md) and [SEP-0006](seps/SEP-0006-compiler-architecture.md) for tool and compiler surfaces.
5. [SEP-0007](seps/SEP-0007-concurrency-model.md) through [SEP-0009](seps/SEP-0009-standard-library.md) for larger system layers.

Use [GLOSSARY.md](GLOSSARY.md) when checking cross-SEP terminology.

## Repository layout

- `drafts/` - unnumbered proposal drafts under active discussion
- `seps/` - numbered SEP documents and historical process records
- `templates/` - authoring templates for new proposals
- `schemas/` - machine-readable rules for SEP metadata and shared contracts
- `scripts/` - repository validation and automation helpers

## Authoring

**SEP** stands for **Spore Enhancement Proposal**. An SEP records changes to
Spore semantics, standard-library surface, tooling protocols, cross-cutting
system design, or the project process itself.

For the decision threshold, lifecycle, and authoring rules, see
[SEP-0000](seps/SEP-0000-process.md). New proposals should start from the
matching template:

- [Standards Track](templates/standards-track.md)
- [Process](templates/process.md)
- [Informational](templates/informational.md)

## Validation

Run the repository checks before opening a PR:

```bash
uv run scripts/validate_sep_documents.py
uv run scripts/check_sep_index.py
uv run scripts/check_terminology_consistency.py
```

If SEP metadata changed, regenerate the committed index first:

```bash
uv run scripts/check_sep_index.py --fix
```
