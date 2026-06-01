---
sep: 10
title: "SEP-0010: Compiler-as-Documentation & Explain Protocol"
status: Draft
type: Standards Track
authors:
  - Zhan Rongrui
created: 2026-05-26
requires:
  - 1
  - 5
  - 6
discussion: "https://github.com/spore-lang/spore-evolution/discussions/46"
pr: null
superseded_by: null
---

# SEP-0010: Compiler-as-Documentation & Explain Protocol

> **Executive Summary**: Defines compiler-as-documentation as a first-class Spore tooling contract. The compiler exposes concept documentation, diagnostic teaching metadata, and explain queries from the same structured facts that produce diagnostics and HoleReports. This keeps terminal feedback, JSON output, LSP surfaces, and Agent input aligned without making external tutorials the source of truth.

## Summary

Spore tooling exposes language concepts through an explain protocol:

```bash
spore explain properties
spore explain holes
spore explain uses
spore explain budget
spore explain fn
spore explain I64
spore explain E0301
spore explain --json properties
```

Each query resolves to a `ConceptDoc` from a `ConceptRegistry`. Diagnostics and
human-readable HoleReports link back to these concepts through stable concept
references, while default terminal diagnostics stay concise.

Compiler-as-documentation means that the compiler owns the facts needed to teach
the language at the point of use. External prose can reorganize those facts, but
it is not the canonical source for syntax, diagnostic meaning, or hole context.

## Motivation

Spore asks users to read signatures, properties, budgets, effects, holes, and
evidence as one semantic path. If those ideas are only explained outside the
compiler, users must leave the feedback loop exactly when they are most likely
to need guidance.

Diagnostics are already structured by SEP-0006, and HoleReports are already
self-contained by SEP-0005. SEP-0010 adds the teaching layer over those records:
short repair guidance in ordinary errors, richer explanations on demand, and
stable JSON for tools and Agents.

This reduces cognitive load without turning every diagnostic into a tutorial.
The compiler says what is wrong, shows the local repair shape, and points to the
concept node that explains why the rule exists.

## Guide-level explanation

### Explaining a concept

`spore explain properties` renders a compact concept page:

```text
properties
  summary: Validity rules attached to an intent signature.

  syntax:
    properties { name(params): expr }

  why:
    Properties make intended behavior explicit so realizations, reviews,
    Agents, and evidence all share the same checkable obligations.

  minimal Spore:
    fn sort(xs: List[I64]) -> List[I64]
    properties {
        ordered(xs: List[I64]): is_ordered(sort(xs))
    }
    {
        ?sort_body
    }

  diagnostics: P0xxx, parse-error
  see also: holes, evidence, intent-signature
```

The same query with `--json` returns the underlying `ConceptDoc`.

### Explaining a diagnostic

When a user writes a malformed property item, the terminal output should be
direct and local:

```text
error[parse-error]: property item is missing its parameter list
  --> src/main.sp:5:5
   |
 5 |     ordered: is_ordered(sort(xs))
   |     ^^^^^^^ write `ordered(xs: List[I64]): ...`
   |
   = learn: spore explain properties
```

`spore explain parse-error` may describe parser diagnostics as a family, while
`spore explain properties` explains the grammar and intent model behind the
repair.

### Explaining a hole

HoleReports remain the structured records specified by SEP-0005. The
compiler-as-documentation layer defines their human teaching projection:

```text
hole[sort_body]
  expected type: List[I64]

  known bindings:
    xs: List[I64]

  possible constructions:
    - xs
    - xs.sorted()
    - ?

  property context:
    ordered(xs: List[I64]): is_ordered(sort(xs))

  learn: spore explain holes
```

The projection highlights the missing shape, the visible facts, candidate
construction paths, and the obligations a realization must preserve.

## Reference-level explanation

### Query resolution

An explain query is resolved in this order:

1. exact diagnostic code, such as `E0301`;
2. exact concept id, such as `properties`, `budget`, or `holes`;
3. surface symbol or prelude name, such as `fn`, `I64`, `Str`, or `Result`;
4. alias listed by a `ConceptDoc`.

Ambiguous queries are diagnostics that list the matching concept ids. Unknown
queries are diagnostics that point to `spore explain --list`.

### ConceptDoc fields

Each concept entry includes:

| Field              | Meaning                                               |
| ------------------ | ----------------------------------------------------- |
| `id`               | Stable concept id used by diagnostics and tools       |
| `title`            | Human-readable title                                  |
| `summary`          | One- or two-sentence concept summary                  |
| `syntax`           | Surface forms or command forms, when applicable       |
| `rationale`        | Design intent and model explanation                   |
| `minimal_examples` | Small Spore snippets or CLI snippets                  |
| `diagnostics`      | Related diagnostic codes or code families             |
| `related_seps`     | SEP numbers that own the normative design             |
| `see_also`         | Related concept ids                                   |
| `aliases`          | Additional accepted query strings                     |

The `ConceptRegistry` contains the ordered set of `ConceptDoc` records plus
schema identity. The concrete contract can later be published under
`schemas/contracts`.

For hole-related concept docs, `related_seps` should include SEP-0005 when the
concept explains HoleReport data and SEP-0010 when the concept explains the
teaching or query layer.

### Diagnostic teaching metadata

Every user-facing diagnostic should be able to carry:

| Field             | Meaning                                                |
| ----------------- | ------------------------------------------------------ |
| `concept_refs`    | Concept ids that explain the violated rule             |
| `repair`          | Local repair hint or replacement shape, when available |
| `explanation_key` | Stable key for selecting a short explanation variant   |

The terminal renderer may use these fields to print one concise `learn:` line.
JSON, watch mode, and LSP projections should preserve the fields so tools do
not scrape prose.

### Hole teaching projection

The educational projection of a HoleReport is a rendering over SEP-0005 fields.
It should include expected type, source location, visible bindings, effect
context, budget context, property context, candidates, dependent holes, and
rejection reasons when those fields are present. SEP-0010 may choose which fields
to highlight for a user-facing explanation, but it does not define different
field names or a second hole query payload.

When SEP-0005 and SEP-0010 appear to overlap, SEP-0005 owns the data contract
and SEP-0010 owns the teaching projection over that contract.

## Human experience impact

This makes intent clearer by putting the relevant concept next to the error or
hole that revealed it. Users can learn the difference between Base Signature
syntax, Intent Signature clauses, properties, effects, budgets, holes, and
evidence in the compiler loop.

The base-vs-intent signature distinction is preserved because concept docs are
attached to the layer they explain. A malformed parameter list points to Base
Signature syntax, while malformed `uses`, `budget`, or `properties` clauses
point to Intent Signature concepts.

Diagnostics, repair, and review workflows improve because terminal output gives
the local fix while `spore explain` carries the design model. Reviewers can ask
for the same concept id that a diagnostic references instead of debating prose
from a separate guide.

## Agent experience impact

Stable concept ids reduce ambiguity for Agents. An Agent that sees
`concept_refs: ["properties"]` can fetch the same structured explanation a
human sees and does not need to infer teaching context from text.

Explain JSON is exported in a stable, machine-readable form. It allows Agents
to ground hole realization without extra conversation: expected types come from
HoleReport, obligations come from property context, and concept docs explain the
rules that make those obligations meaningful.

SEP-0010 preserves the semantic path `Signature -> Property -> Hole ->
Realization -> Evidence` by treating documentation as metadata over compiler
records. ConceptDoc changes do not alter program identity; evidence remains tied
to the signatures, properties, realizations, checkers, and dependencies that
SEP-0006 defines.

## Structured representation / protocol impact

The concept registry schema defines this top-level shape:

```text
ConceptRegistry
├── version
├── schema
├── schema_catalog
└── concepts[]
```

Each `concepts[]` item is a `ConceptDoc`:

```text
ConceptDoc
├── id
├── title
├── summary
├── syntax[]
├── rationale[]
├── minimal_examples[]
├── diagnostics[]
├── related_seps[]
├── see_also[]
└── aliases[]
```

`spore explain --json <query>` returns either a single `ConceptDoc`, a diagnostic
explanation record with concept references, or an ambiguity diagnostic. Tools
may cache registry records by schema identity and concept id.

Diagnostic JSON gains optional teaching fields:

```json
{
  "code": "P0101",
  "severity": "error",
  "message": "property item is missing its parameter list",
  "concept_refs": ["properties"],
  "repair": {
    "message": "write a property name, parameter list, colon, and Bool expression",
    "replacement": "ordered(xs: List[I64]): is_ordered(sort(xs))"
  },
  "explanation_key": "properties.item-shape"
}
```

Unknown JSON fields remain ignorable for consumers that only need the older
diagnostic shape.

## Diagnostics impact

Diagnostics keep the SEP-0006 code families. SEP-0010 adds a teaching layer over
those codes:

- primary message: what failed at the exact source span;
- repair hint: the smallest local shape that can move the user forward;
- concept reference: the `spore explain` query that teaches the rule.

Every user-facing diagnostic produced by the compiler should have a path to at
least one concept id, either directly or through its diagnostic family.
Diagnostic families may point to broad concepts, while more specific codes may
point to a subconcept through `explanation_key`.

The default text renderer should stay concise. Long rationale, multiple
snippets, prior art, and cross-topic exploration belong in `spore explain`.

## Drawbacks

Concept docs add authoring work to compiler and tooling changes. The mitigation
is that concept entries are small, structured, and tested with the same snippets
that users see.

There is a risk of noisy diagnostics if every error tries to teach the full
language model. SEP-0010 keeps normal diagnostics brief and moves the deeper
material behind explicit explain queries.

The registry adds another machine contract to maintain. The benefit is that
humans, Agents, LSP, watch mode, and terminal output share one explanation
source.

## Alternatives considered

### External manual only

Rejected because the compiler would keep detecting precise context while the
teaching surface lived elsewhere.

### Text-only explain output

Rejected because Agents, LSP clients, and tests need stable fields instead of
terminal prose.

### Long diagnostics by default

Rejected because users need fast repair loops. Detailed rationale belongs behind
`spore explain`.

### Rust attribute syntax as the standard

Rejected because a Rust macro or attribute can be a convenient producer, but the
standard should define the registry and diagnostic contract that all producers
emit.

## Prior art

Elm influenced human-centered error messages with repair guidance.

Rust influenced diagnostic codes and `rustc --explain`.

Agda, Idris, GHC, and Lean influenced typed holes that show local context.

Language Server Protocol features such as code descriptions and hover text
influenced the projection of concept docs into editor tools.

## Backward compatibility and migration

No Spore source syntax changes are required. Existing diagnostic codes remain
valid, and explain metadata is added as optional data over the existing
Diagnostic record.

JSON consumers should ignore unknown fields. Tools that want compiler-owned
documentation can begin reading `concept_refs`, `repair`, and
`explanation_key`.

`sporec explain <code>` can remain a low-level diagnostic query. The project CLI
adds `spore explain <query>` as the user-facing entry point for concepts,
diagnostic codes, and surface symbols.

## Unresolved questions

1. Should concept docs be localized by compiler output, by renderer packages, or
   by external translation catalogs?
2. Should standard-library modules publish their user-facing docs through the
   same concept registry shape?
3. Should interactive tutorial flows become a separate SEP after explain,
   diagnostics, and hole projections settle?
