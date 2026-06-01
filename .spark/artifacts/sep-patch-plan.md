# PR45 SEP patch plan

This artifact merges the five design drafts into a file-level patch plan. It is
a checklist for the later document-editing pass and does not edit SEP files.

## Inputs

- `.spark/artifacts/pr45-vocab-map.md`
- `.spark/artifacts/d1-property-spec.md`
- `.spark/artifacts/d3-handler-spec.md`
- `.spark/artifacts/d5-agent-spec.md`
- `.spark/artifacts/primitive-effects-spec.md`
- `.spark/artifacts/d10-explain-boundary-spec.md`

## Global constraints

- Scope is design-only in `spore-evolution`; do not modify the sibling `spore`
  implementation repository.
- Do not introduce a new SEP number.
- Keep the no-default-Platform decision.
- Keep primitive-effect method spellings semantic until the final text pass.
- Keep workflow and candidate ranker text informational.
- Preserve SEP-0010 as the compiler-as-documentation layer over SEP-0005 and
  SEP-0006 records.
- Run the full validation suite after the actual edits:
  `uvx --from git+https://github.com/j178/prek prek run -a`.

## Validation gates

The final edit pass must keep these hooks green:

| Hook | Expected impact |
| --- | --- |
| `terminology-consistency` | New terms must be added to `GLOSSARY.md` when they enter SEP text. |
| `contract-schemas` | No schema changes are planned; this hook should remain unchanged. |
| `surface-consistency` | `README.md`, `VISION.md`, `GLOSSARY.md`, and SEP links must remain aligned. |
| `sep-index` | Required because SEP-0005 is renamed and `seps-index.json` path/title change. |
| `sep-documents` | Required for front matter, title, requires, and template shape after renaming. |

## File plan summary

| File | Action | Source artifacts |
| --- | --- | --- |
| `seps/SEP-0001-core-syntax.md` | Patch property delegation and handler grammar. | D1, D3 |
| `seps/SEP-0002-type-system.md` | Add property body typing and connect refinements to claims. | D1 |
| `seps/SEP-0003-effect-system.md` | Add primitive membership rules, replace handler example, add handler state policy. | Primitive, D3 |
| `seps/SEP-0005-hole-system.md` | Rename file, title, and scope; strengthen HoleReport schema; demote workflow/ranker. | D5, D10 |
| `seps/SEP-0006-compiler-architecture.md` | Clarify property claims, evidence result semantics, and SEP-0010 metadata layering. | D1, D10 |
| `seps/SEP-0008-module-package-system.md` | Add Platform obligation for primitive host and mock handlers. | Primitive |
| `seps/SEP-0009-standard-library.md` | Add state primitive effect semantic surface. | Primitive |
| `seps/SEP-0010-compiler-as-documentation.md` | Sharpen HoleReport projection boundary and ConceptDoc related-SEP guidance. | D10 |
| `GLOSSARY.md` | Add/update terms. | All |
| `VISION.md` | Add small state/effect and explain-boundary clarifications. | Primitive, D10 |
| `README.md` | Update SEP-0005 link after rename. | D5 |
| `seps-index.json` | Update SEP-0005 path/title after rename. | D5 |
| `schemas/` | No planned changes. | None |

## SEP-0001 patch plan

Affected areas:

- Intent Signature delegation at `seps/SEP-0001-core-syntax.md:67-83`.
- Reference signature layout at `seps/SEP-0001-core-syntax.md:220-230`.
- Property grammar at `seps/SEP-0001-core-syntax.md:286-290`.
- Handler grammar at `seps/SEP-0001-core-syntax.md:312-316`.
- Handler grammar notes at `seps/SEP-0001-core-syntax.md:333-338`.
- Unresolved property subset question at `seps/SEP-0001-core-syntax.md:435`.

Edits:

1. Replace the clause delegation sentence so `properties` delegates expression
   typing to SEP-0002 and claim/evidence lowering to SEP-0006.
2. Keep `PropertyItem = ... ":" Expr`, then add a note that this is ordinary
   Spore expression syntax and not a separate proof sublanguage.
3. Replace the handler grammar with fields, `handles`, optional `uses`, and
   `impl Effect { fn operation(self, ...) ... }` blocks.
4. Add a grammar note that handler fields are immutable instance payload and the
   handler receiver is explicit read-only `self`.
5. Add an expression-shape note for `handle ... with { use ..., on ... }`.
6. Replace the unresolved property-expression-subset question with an unknown
   evidence presentation question.

## SEP-0002 patch plan

Affected areas:

- Reference-level typing section after outcome typing and before refinement
  obligations, near `seps/SEP-0002-type-system.md:191-213`.

Edits:

1. Add `### Property body typing`.
2. State that a property body is an ordinary Spore expression checked against
   `Bool`.
3. State that property parameters are local to the property body.
4. State that property bodies inherit the enclosing effect context and may use
   only available or locally discharged effects.
5. State that non-`Bool` property bodies are type errors.
6. Extend refinement obligations to say they share the same Claim and
   EvidenceRecord channel as source properties.

## SEP-0003 patch plan

Affected areas:

- `### Declaring effects` / `### Using effects`, around
  `seps/SEP-0003-effect-system.md:54-76`.
- `### Handlers`, around `seps/SEP-0003-effect-system.md:101-116`.
- `### Surface resolution`, around `seps/SEP-0003-effect-system.md:132-139`.
- `### Handler checking`, around `seps/SEP-0003-effect-system.md:143-146`.
- Structured effect context section around `seps/SEP-0003-effect-system.md:161-177`.

Edits:

1. Add `### State primitive effects` with the five membership rules.
2. State that state primitive effects resolve as ordinary atomic effects.
3. Replace the stateful `self.output.push` handler example with an `Output[Str]`
   primitive-effect example.
4. Add `### Handler state policy` describing immutable fields and no `mut`.
5. Add handler method receiver rules: first parameter is explicit read-only
   `self`.
6. Add task-local handler instance visibility.
7. Add handler payload hash boundary: fields do not enter signature, intent, or
   property hash.
8. Cross-reference SEP-0009 for the concrete primitive set and SEP-0008 for
   Platform handlers.

## SEP-0005 patch plan

Rename:

- Move `seps/SEP-0005-hole-system.md` to
  `seps/SEP-0005-hole-report-protocol.md`.

Affected areas after rename:

- Front matter title and H1.
- Executive summary.
- Motivation and normative scope near `HoleReport is the collaboration boundary`.
- `### Realization workflow` at old lines `90-99`.
- `### HoleReport fields` at old lines `112-134`.
- Structured representation section around old lines `190-207`.

Edits:

1. Change title and H1 to `SEP-0005: Hole System & HoleReport Protocol`.
2. Replace the executive summary to emphasize normative HoleReport schema.
3. Add a normative scope banner: hole syntax, HoleReport records, and dependency
   graph are normative; Agent workflow, ranker, and teaching projections are not.
4. Retitle `### HoleReport fields` to `### Normative HoleReport fields`.
5. Add JSON-shape language after the field table.
6. Add a note that SEP-0010 may attach concept refs and render fields but does
   not add required HoleReport fields.
7. Move `### Realization workflow` to an informational appendix.
8. Add `## Informational appendix: Reference candidate ranker` with the formula
   as an example only.
9. Strengthen the SEP-0010 rendering boundary sentence.

## SEP-0006 patch plan

Affected areas:

- `### Properties become claims`, around
  `seps/SEP-0006-compiler-architecture.md:64-77`.
- `### EvidenceRecord structure`, around
  `seps/SEP-0006-compiler-architecture.md:128-160`.
- Shared records and SEP-0010 handoff around
  `seps/SEP-0006-compiler-architecture.md:201-210`.
- Diagnostics around `seps/SEP-0006-compiler-architecture.md:219-230`.

Edits:

1. Update property-to-claim lowering to mention SEP-0002 Bool typing and effect
   context checks.
2. Add shared-origin text: source properties, refinements, budget checks, effect
   checks, and validators lower into compatible Claim/EvidenceRecord structures.
3. Add property evidence result semantics for `passed`, `failed`, `unknown`, and
   `skipped`.
4. Split diagnostics: non-`Bool` property bodies are type diagnostics; failed or
   unknown checks are property/claim diagnostics.
5. Add that SEP-0010 teaching metadata is optional metadata over shared records
   and does not change identity, hash, or required fields.

## SEP-0008 patch plan

Affected areas:

- `### Platform startup contract`, around
  `seps/SEP-0008-module-package-system.md:111-115`.
- Platform diagnostics table around `M050x` entries.

Edits:

1. Add the primitive handler obligation: a conforming Platform package claiming
   primitive support provides host and in-memory mock handler families for each
   supported primitive.
2. State that this does not create a default Platform.
3. Add a diagnostic note that missing primitive handlers are Platform binding
   violations, not missing stdlib functions.

## SEP-0009 patch plan

Affected areas:

- `### Prelude`, around `seps/SEP-0009-standard-library.md:133-137`.
- `### Effects`, around `seps/SEP-0009-standard-library.md:154-161`.
- Unresolved Platform package question around
  `seps/SEP-0009-standard-library.md:240-241`.

Edits:

1. Add a prelude note: state primitive names are standard names, but host
   handlers remain Platform-provided.
2. Add `### State primitive effects` with semantic interfaces for `Cell`,
   `Output`, `Map`, `Clock`, and `Random`.
3. Mark method names as final-patch spelling choices if the final edit keeps the
   placeholder stance.
4. Add a short exclusion note for `Counter`, `Cache`, `Logger`, `FileRead`,
   `FileWrite`, `Spawn`, and `Channel`.
5. Update the open Platform package question so it does not imply a default
   Platform.

## SEP-0010 patch plan

Affected areas:

- `### Hole teaching projection`, around
  `seps/SEP-0010-compiler-as-documentation.md:188-194`.
- `### ConceptDoc fields`, around
  `seps/SEP-0010-compiler-as-documentation.md:160-170`.
- Diagnostics impact around `seps/SEP-0010-compiler-as-documentation.md:291-296`.

Edits:

1. Strengthen the hole teaching projection paragraph to say it renders SEP-0005
   fields and does not define alternate field names.
2. Add the owner rule: SEP-0005 owns data contracts; SEP-0010 owns teaching
   projection.
3. Add `related_seps` guidance for hole-related ConceptDocs.
4. Soften `Every user-facing diagnostic should map to at least one concept id`
   to allow direct or diagnostic-family concept paths.

## GLOSSARY.md patch plan

Add or update terms:

| Term | Action |
| --- | --- |
| `State primitive effect` | Add under S, reference SEP-0003 and SEP-0009. |
| `Handler instance` | Add or expand under H, mention lexical and task-local visibility. |
| `Handler field` | Add or expand under H, mention immutable instance payload. |
| `HoleReport Protocol` | Add or update near HoleReport after SEP-0005 rename. |
| `Concept projection` | Add under C if SEP-0010 text uses the term prominently. |
| `Property body` | Add if SEP-0002 uses the term as a heading. |

Update the multilingual table for any new user-facing term added to the body.

## VISION.md patch plan

Affected areas:

- Intent Signature explanation around `VISION.md:27-30`.
- Holes and reports around `VISION.md:47-53`.
- Evidence and structured data around `VISION.md:70-76`.
- Prior-art table if needed.

Edits:

1. Add one sentence that stateful testing and instrumentation use explicit
   effects rather than user-level mutation.
2. Add one sentence that HoleReport data and compiler explain projections share
   the same compiler facts but are different contracts.
3. Do not add implementation or migration detail to VISION.

## README.md patch plan

Affected area:

- SEP dependency list around `README.md:49-53`.

Edits:

1. Update the SEP-0005 link target from `seps/SEP-0005-hole-system.md` to
   `seps/SEP-0005-hole-report-protocol.md`.
2. Keep the current grouping with SEP-0006 and SEP-0010.

## SEP index JSON patch plan

Affected area:

- SEP 5 entry currently points to `seps/SEP-0005-hole-system.md` and title
  `SEP-0005: Hole System & Agent Protocol`.

Edits:

1. Update `path` to `seps/SEP-0005-hole-report-protocol.md`.
2. Update `title` to `SEP-0005: Hole System & HoleReport Protocol`.
3. Leave `sep`, `status`, `type`, `authors`, `created`, `requires`,
   `discussion`, `pr`, and `superseded_by` unchanged.

## schemas plan

No schema changes are planned in this patch. SEP-0010 may later publish
ConceptRegistry schemas under `schemas/contracts`, but this PR should not add
that surface.

## Cross-reference checklist

After the actual file edit pass, run these checks manually before `prek`:

```bash
grep -RIn "SEP-0005-hole-system" README.md GLOSSARY.md VISION.md seps seps-index.json
grep -RIn "Hole System & Agent Protocol" README.md GLOSSARY.md VISION.md seps seps-index.json
grep -RIn "self.output.push" seps
```

Expected result: no matches after the patch except historical discussion text if
intentionally retained.

## Implementation follow-up seeds

These are not PR45 edits, but `@cross-check-impl` should classify them:

1. Sibling implementation still uses `spec` where PR45 uses `properties`.
2. Sibling implementation still uses `cost [compute, alloc, io, parallel]` where
   PR45 uses named realization-shape budgets.
3. Sibling implementation lacks direct `property_context` evidence in scanned
   `HoleInfo`.
4. Sibling implementation has `Clock` and `Random`, but not `Cell`, `Output`, or
   primitive-effect `Map` in the collected Platform evidence.
5. Sibling implementation has hole JSON and LSP hovers, but no observed
   `spore explain` command in the collected evidence.

## Final edit order

Use this order for the actual SEP editing pass:

1. Rename SEP-0005 file and update `seps-index.json` plus `README.md` link.
2. Patch SEP-0005 and SEP-0010 boundary text together.
3. Patch SEP-0001, SEP-0002, and SEP-0006 for D1 properties.
4. Patch SEP-0003, SEP-0008, and SEP-0009 for primitive effects and handler
   state.
5. Patch `GLOSSARY.md`.
6. Patch `VISION.md`.
7. Run the grep checklist.
8. Run `uvx --from git+https://github.com/j178/prek prek run -a`.
