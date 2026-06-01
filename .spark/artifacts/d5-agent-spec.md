# D5 HoleReport protocol boundary draft

This artifact turns the D5 decision into patch-ready text for SEP-0005. It does
not edit the SEP files directly.

## Locked decision

D5 is fixed as follows:

- SEP-0005 normatively defines the HoleReport schema and the hole dependency
  graph.
- The Agent realization workflow is informational guidance, not a required
  protocol state machine.
- Candidate ranking and scoring are informational reference behavior, not a
  required scoring contract.
- Human-facing teaching projections of HoleReport data belong to SEP-0010.
- The SEP should be renamed from `Hole System & Agent Protocol` to
  `Hole System & HoleReport Protocol`.
- The file should be renamed from `seps/SEP-0005-hole-system.md` to
  `seps/SEP-0005-hole-report-protocol.md` during the later patch step.

## Evidence from current text

| Document | Current evidence | D5 impact |
| --- | --- | --- |
| SEP-0005 front matter | Title is `SEP-0005: Hole System & Agent Protocol` at `seps/SEP-0005-hole-system.md:2-3`. | Rename to put the normative protocol in the title. |
| SEP-0005 heading | Main heading repeats `Hole System & Agent Protocol` at `seps/SEP-0005-hole-system.md:18`. | Rename the heading with the front matter. |
| SEP-0005 motivation | HoleReport is named as the collaboration boundary at `seps/SEP-0005-hole-system.md:52-54`. | This should become the normative center. |
| SEP-0005 workflow | Agent workflow states `DISCOVER -> ANALYZE -> PROPOSE -> VERIFY -> ACCEPT or REJECT` at `seps/SEP-0005-hole-system.md:90-99`. | Move to an informational appendix. |
| SEP-0005 fields | Per-hole fields are listed at `seps/SEP-0005-hole-system.md:112-134`. | Keep and strengthen as the normative core. |
| SEP-0005 / SEP-0010 | Educational renderings are owned by SEP-0010 at `seps/SEP-0005-hole-system.md:205-207`. | Keep as the boundary sentence and cross-link it in the rename patch. |
| Sibling type checker | `CandidateScore::overall` uses `0.40`, `0.20`, `0.25`, `0.15` in `../spore/crates/sporec-typeck/src/hole.rs:20-47`. | Treat as reference ranker, not required protocol. |
| Sibling type checker | `HoleInfo` fields appear in `../spore/crates/sporec-typeck/src/hole.rs:124-170`. | Use this as an implementation comparison for the HoleReport field table. |
| Sibling JSON projection | `hole_info_json` maps type-checker data to JSON in `../spore/crates/sporec-driver/src/compiler/hole_json.rs:94-171`. | Use this as evidence that HoleReport schema should stay self-contained. |

## Rename draft

### File and index changes for the later patch step

- Rename `seps/SEP-0005-hole-system.md` to
  `seps/SEP-0005-hole-report-protocol.md`.
- Update `seps-index.json` path for SEP 5.
- Update `README.md` links that mention `seps/SEP-0005-hole-system.md`.
- Update any cross-references from other SEP files to the old file path.

### Front matter and heading

Replace the front matter title and H1 with:

```markdown
title: "SEP-0005: Hole System & HoleReport Protocol"
```

```markdown
# SEP-0005: Hole System & HoleReport Protocol
```

### Executive summary replacement

Replace the current executive summary with:

```markdown
> **Executive Summary**: Defines holes as typed absence constrained by Base
> Signature and Intent Signature context, and normatively specifies the
> HoleReport records emitted for those holes. HoleReport exposes expected type,
> visible bindings, effect context, budget context, property context,
> candidates, dependencies, and confidence data. Agent workflows and candidate
> rankers are informative projections over this data rather than a required
> protocol state machine.
```

## Normative scope banner

Add this after the summary paragraph:

```markdown
This SEP normatively defines hole syntax, HoleReport records, and the hole
dependency graph. It does not normatively define an Agent workflow state
machine, candidate scoring formula, or human teaching projection. Those topics
are informative guidance here or belong to SEP-0010 when they teach users how to
read HoleReport data.
```

## HoleReport core draft

### Keep the existing field list

Keep the field table at `seps/SEP-0005-hole-system.md:112-134`, but retitle it
from `### HoleReport fields` to:

```markdown
### Normative HoleReport fields
```

### Add JSON-shape language

Add this text after the field table:

```markdown
The per-hole object is the normative schema boundary for tools. JSON producers
may add versioned optional fields, but they must preserve the meaning of these
fields when present. A batch response wraps per-hole objects in a `holes` array
and may include a `dependency_graph` object. A single-hole query returns one
per-hole object directly.
```

### Field mapping against the sibling implementation

| SEP-0005 field | Sibling evidence | Notes |
| --- | --- | --- |
| `name` | `HoleInfo.name` at `../spore/crates/sporec-typeck/src/hole.rs:126-127`; JSON mapping at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:95-97`. | Aligned. |
| `display_name` | JSON derives display name in `../spore/crates/sporec-driver/src/compiler/hole_json.rs:25-31` and maps it at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:95-97`. | Aligned in JSON, not stored in type-checker `HoleInfo`. |
| `location` | `SourceLocation` and `HoleInfo.location` at `../spore/crates/sporec-typeck/src/hole.rs:10-18` and `../spore/crates/sporec-typeck/src/hole.rs:128-131`. | Aligned. |
| `expected_type` | `HoleInfo.expected_type` at `../spore/crates/sporec-typeck/src/hole.rs:132-133`; JSON mapping at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:99-100`. | Aligned. |
| `type_inferred_from` | `HoleInfo.type_inferred_from` at `../spore/crates/sporec-typeck/src/hole.rs:134-135`; JSON mapping at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:100-101`. | Aligned. |
| `function` | `HoleInfo.function` at `../spore/crates/sporec-typeck/src/hole.rs:136-137`; JSON mapping at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:101-102`. | Aligned. |
| `enclosing_signature` | `HoleInfo.enclosing_signature` at `../spore/crates/sporec-typeck/src/hole.rs:138-139`; JSON mapping at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:102-103`. | Aligned. |
| `bindings` | `HoleInfo.bindings` at `../spore/crates/sporec-typeck/src/hole.rs:140-141`; JSON mapping at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:103-108`. | Aligned. |
| `binding_dependencies` | `HoleInfo.binding_dependencies` at `../spore/crates/sporec-typeck/src/hole.rs:142-143`; JSON mapping at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:109`. | Aligned. |
| `effect_context` | `EffectContext` and `HoleInfo.effect_context` at `../spore/crates/sporec-typeck/src/hole.rs:103-107` and `../spore/crates/sporec-typeck/src/hole.rs:146-149`; JSON mapping at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:111-117`. | Partially aligned; SEP uses declared/expanded/active/discharged vocabulary, implementation uses discharged/surviving vocabulary. |
| `budget_context` | `CostBudget`, `ResidualContext`, and `HoleInfo.cost_budget`/`residual_context` at `../spore/crates/sporec-typeck/src/hole.rs:86-101` and `../spore/crates/sporec-typeck/src/hole.rs:150-153`; JSON mapping at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:118-129`. | Mismatch vocabulary: implementation still uses cost-vector terms. |
| `property_context` | No direct field in the scanned `HoleInfo` struct. | Gap for later implementation review. |
| `errors_to_handle` | `HoleInfo.errors_to_handle` at `../spore/crates/sporec-typeck/src/hole.rs:144-145`; JSON mapping at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:110`. | Aligned. |
| `candidates` | `HoleInfo.candidates` at `../spore/crates/sporec-typeck/src/hole.rs:154-155`; JSON mapping at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:130-160`. | Aligned as data. Ranking policy stays informative. |
| `dependent_holes` | `HoleInfo.dependent_holes` at `../spore/crates/sporec-typeck/src/hole.rs:156-157`; JSON mapping at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:162`. | Aligned. |
| `confidence` | `Confidence` and `HoleInfo.confidence` at `../spore/crates/sporec-typeck/src/hole.rs:52-73` and `../spore/crates/sporec-typeck/src/hole.rs:158-159`; JSON mapping at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:163-171`. | Aligned as data. |
| `rejection_reasons` | Candidate-level rejection reasons are in `CandidateScore.rejection_reasons` at `../spore/crates/sporec-typeck/src/hole.rs:20-35`; JSON maps them at `../spore/crates/sporec-driver/src/compiler/hole_json.rs:138-145`. | Shape differs: PR45 field is per-hole; implementation stores reasons per candidate and error cluster. |

## Workflow demotion draft

Move the `### Realization workflow` section at
`seps/SEP-0005-hole-system.md:90-99` to an appendix named:

```markdown
## Informational appendix: Realization workflow notes
```

Use this introduction:

```markdown
This workflow is an informative reference loop for Agents and tools. A conforming
HoleReport producer is not required to expose these states, and a conforming
Agent is not required to use this exact state machine.
```

Keep the existing state text, but replace the acceptance sentence with:

```markdown
A proposed fill is reviewable when it is checked against type, effect, budget,
and property context from the HoleReport and either passes those checks or
produces evidence states that the selected policy accepts.
```

## Candidate ranker demotion draft

Add an appendix after the workflow appendix:

```markdown
## Informational appendix: Reference candidate ranker

Implementations may rank candidates using the fields exposed by HoleReport. One
reference ranker combines type match, budget fit, required-effect fit, and error
coverage. This ranker is informative. Tools may use a different ranker when they
preserve the normative HoleReport data.
```

If the current sibling formula is mentioned, present it only as an example:

```text
overall = 0.40 * type_match
        + 0.20 * budget_fit
        + 0.25 * required_effects_fit
        + 0.15 * error_coverage
```

The formula corresponds to `CandidateScore::overall` in
`../spore/crates/sporec-typeck/src/hole.rs:36-42`, but PR45 should name the
budget dimension `budget_fit` rather than inherit the implementation's
`cost_fit` spelling.

## SEP-0010 boundary note

Do not expand this task into explain-protocol design. Keep the existing boundary
sentence at `seps/SEP-0005-hole-system.md:205-207` and let
`@d10-explain-boundary` refine cross-references. SEP-0005 owns the data record;
SEP-0010 owns educational rendering and explain queries.

## Routing to the patch plan

`@sep-patch-plan` should include these concrete edits:

1. Rename SEP-0005 file path and update `seps-index.json`.
2. Rename SEP-0005 title and H1.
3. Replace the executive summary.
4. Add the normative scope banner.
5. Retitle `HoleReport fields` as normative.
6. Add JSON-shape text after the field table.
7. Move `Realization workflow` to an informational appendix.
8. Add `Reference candidate ranker` as an informational appendix.
9. Keep SEP-0010 rendering boundary text and let `@d10-explain-boundary` refine
   cross-references.
