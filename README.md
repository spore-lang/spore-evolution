# spore-evolution

Proposal portal for the Spore programming project.

This repository is the long-lived home for Spore Evolution Proposals (SEPs):
process decisions, language design records, tooling protocols, package-system
design, and cross-cutting changes that affect Spore as a whole.

## Read this first

The SEPs in this repository are design records. They define design intent; they
are not, by themselves, compatibility guarantees or public release contracts for
Spore.

For release-facing installation guidance, implementation roadmap, and shipped
tool behavior, start with the language repository: `../spore/README.md`,
`../spore/ROADMAP.md`, `../spore/SPARK.md`, and
`../spore/docs/decisions/syntax.md`.

This repository is authoritative for proposal history and accepted design
direction. During bootstrap, Draft SEPs may include target behavior, protocol
shapes, or samples that are ahead of the compiler.

**Signature v2 baseline:** Spore is organized around
`Signature -> Property -> Hole -> Realization -> Evidence`. Base signatures
carry the callable type boundary. Intent signatures add `uses`, `budget`, and
`properties` clauses for verifier, Agent, and Evidence workflows.

**Surface typing baseline:** default unsuffixed literals are **`I64`** for
integers and **`F64`** for floats; UTF-8 text is **`Str`**; the unit surface type
is **`()`**. SEP-0002 owns the full type-system rules and metavariables for
other fixed widths.

## SEP status

| SEP                                                | Title                                  | Status   | Role                                                                |
| -------------------------------------------------- | -------------------------------------- | -------- | ------------------------------------------------------------------- |
| [SEP-0000](seps/SEP-0000-process.md)               | Spore Evolution Proposal Process       | Accepted | Repository process and lifecycle                                    |
| [SEP-0001](seps/SEP-0001-core-syntax.md)           | Core Syntax & Signatures               | Accepted | Root surface grammar and Signature v2 layout                        |
| [SEP-0002](seps/SEP-0002-type-system.md)           | Type System                            | Draft    | Type semantics, inline generic bounds, and callable boundaries      |
| [SEP-0003](seps/SEP-0003-effect-system.md)         | Effect System                          | Draft    | Runtime effect capabilities inside the `uses` capability surface    |
| [SEP-0004](seps/SEP-0004-cost-analysis.md)         | Budget Constraints & Realization Shape | Draft    | Quantitative realization-shape budgets                              |
| [SEP-0005](seps/SEP-0005-hole-system.md)           | Hole System & Agent Protocol           | Draft    | Typed absence and agent-facing reports                              |
| [SEP-0006](seps/SEP-0006-compiler-architecture.md) | Compiler Architecture                  | Draft    | Compiler pipeline, properties, claims, and evidence records         |
| [SEP-0007](seps/SEP-0007-concurrency-model.md)     | Concurrency Model                      | Draft    | Structured concurrency semantics under capability and budget checks |
| [SEP-0008](seps/SEP-0008-module-package-system.md) | Module & Package System                | Draft    | Modules, manifests, platforms, packages, and provenance hashes      |
| [SEP-0009](seps/SEP-0009-standard-library.md)      | Standard Library Surface               | Draft    | Prelude, core modules, and platform libraries                       |

The generated machine-readable index is [`seps-index.json`](seps-index.json).

## Reading path

Read [Spore Language Vision](VISION.md) first for the design philosophy; a
Chinese version is available at [孢子语言愿景](VISION.zh-CN.md). Implementation
planning lives in the sibling language repository's `ROADMAP.md`. Then use SEPs
in dependency order:

1. [SEP-0000](seps/SEP-0000-process.md) for how decisions are made and the guiding
   questions used in review.
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

**SEP** stands for **Spore Evolution Proposal** (Spore 演进提案). An SEP
records and reviews changes to Spore semantics, standard-library surface,
tooling protocols, cross-cutting system design, governance, or the project
process itself.

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
uv run scripts/check_contract_schemas.py
uv run scripts/check_surface_consistency.py
```

If SEP metadata changed, regenerate the committed index first:

```bash
uv run scripts/check_sep_index.py --fix
```
