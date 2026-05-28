# D10 explain boundary specification draft

This artifact defines the boundary between SEP-0005 HoleReport records and
SEP-0010 compiler-as-documentation projections. It does not edit SEP files
directly.

## Locked decision

- SEP-0005 owns hole syntax, HoleReport records, and hole dependency graphs.
- SEP-0010 owns ConceptDoc records, concept references, diagnostic teaching
  metadata, `spore explain`, and educational projections over compiler records.
- SEP-0010 may render or explain HoleReport data, but it must not define a
  second hole protocol.
- SEP-0006 remains the owner of shared compiler records and diagnostic code
  families. SEP-0010 layers teaching metadata over them.

## Evidence from current text

| Document | Current evidence | Boundary impact |
| --- | --- | --- |
| SEP-0005 | HoleReport is the collaboration boundary at `seps/SEP-0005-hole-system.md:52-54`. | SEP-0005 owns the data protocol. |
| SEP-0005 | Per-hole fields are listed at `seps/SEP-0005-hole-system.md:112-134`. | Field definitions stay in SEP-0005. |
| SEP-0005 | Single-hole queries return the same per-hole object directly at `seps/SEP-0005-hole-system.md:199-203`. | Query shape stays HoleReport-owned. |
| SEP-0005 | Educational renderings are owned by SEP-0010 at `seps/SEP-0005-hole-system.md:205-207`. | Existing text already points the teaching layer to SEP-0010. |
| SEP-0006 | Shared machine records include `Diagnostic`, `HoleReport`, `Claim`, `EvidenceRecord`, and `VerificationBundle` at `seps/SEP-0006-compiler-architecture.md:201-210`. | SEP-0010 must layer over these records, not replace them. |
| SEP-0006 | Diagnostic teaching metadata and `spore explain` behavior are owned by SEP-0010 at `seps/SEP-0006-compiler-architecture.md:228-230`. | SEP-0006 already delegates teaching metadata. |
| SEP-0010 | Summary says diagnostics and HoleReports link to concepts through stable concept references at `seps/SEP-0010-compiler-as-documentation.md:23-39`. | Concept refs are teaching metadata. |
| SEP-0010 | Motivation says SEP-0005 HoleReports are self-contained and SEP-0010 adds the teaching layer at `seps/SEP-0010-compiler-as-documentation.md:46-55`. | Clear dependency: SEP-0010 depends on SEP-0005. |
| SEP-0010 | Hole teaching projection states that HoleReports remain SEP-0005 records at `seps/SEP-0010-compiler-as-documentation.md:114-135`. | Keep this wording, but make the projection boundary sharper. |
| SEP-0010 | Reference text says the educational projection is not a second hole protocol at `seps/SEP-0010-compiler-as-documentation.md:188-194`. | This should become the central boundary sentence. |
| SEP-0010 | Agent impact says expected types come from HoleReport and concept docs explain the rules at `seps/SEP-0010-compiler-as-documentation.md:219-223`. | Agents consume HoleReport data plus ConceptDoc teaching metadata. |

## Responsibility table

| Responsibility | Owner SEP | Notes |
| --- | --- | --- |
| Hole expression syntax (`?name`, `?name: Type`) | SEP-0005 | SEP-0010 may explain it, but cannot change syntax. |
| Per-hole field names and meanings | SEP-0005 | Includes expected type, bindings, effect context, budget context, property context, candidates, dependent holes, confidence, and rejection reasons. |
| Batch and single-hole query shape | SEP-0005 | SEP-0010 may render the result, not redefine it. |
| Hole dependency graph | SEP-0005 | Concept docs may link to `holes` or `hole-dependency-graph`. |
| Candidate workflow notes | SEP-0005 informational appendix | D5 demotes workflow to guidance. SEP-0010 may teach the workflow as concept docs if needed. |
| Reference candidate ranker | SEP-0005 informational appendix | The ranker is not an explain protocol field. |
| Diagnostic code families | SEP-0006 | SEP-0010 attaches concept refs and repair metadata to diagnostics. |
| Shared record list | SEP-0006 | `Diagnostic`, `HoleReport`, `Claim`, `EvidenceRecord`, `VerificationBundle`. |
| `ConceptDoc` schema | SEP-0010 | Does not alter program identity or HoleReport schema. |
| `ConceptRegistry` schema | SEP-0010 | Later schema publication can live under `schemas/contracts`. |
| `concept_refs`, `repair`, `explanation_key` | SEP-0010 | Optional teaching metadata over diagnostics and projections. |
| `spore explain` query resolution | SEP-0010 | Query resolution maps codes, concepts, surface symbols, and aliases to teaching records. |
| Human-readable hole teaching projection | SEP-0010 | Projection over SEP-0005 data; not a second hole protocol. |
| LSP hover or terminal prose for holes | SEP-0010 projection | Renderer-specific, based on SEP-0005 data plus ConceptDoc metadata. |

## SEP-0005 cross-reference patch draft

### Keep and strengthen the existing boundary sentence

Current text at `seps/SEP-0005-hole-system.md:205-207` already says educational
renderings belong to SEP-0010. Replace it with:

```markdown
Human-facing educational renderings of HoleReport records are owned by SEP-0010.
Those renderings must stay projections over the same HoleReport data rather than
forming a separate hole protocol. SEP-0005 remains the owner of per-hole field
names, dependency graph shape, and batch/single-hole query shape.
```

### Add a reference near the normative field table

After the normative HoleReport field table introduced by `@d5-agent`, add:

```markdown
SEP-0010 may attach concept references and render these fields for teaching, but
it does not add required HoleReport fields. Optional teaching metadata is outside
the normative HoleReport schema unless a later SEP moves it here.
```

## SEP-0010 cross-reference patch draft

### Strengthen the Hole teaching projection section

Replace the first paragraph of `### Hole teaching projection` near
`seps/SEP-0010-compiler-as-documentation.md:188-194` with:

```markdown
The educational projection of a HoleReport is a rendering over SEP-0005 fields.
It should include expected type, source location, visible bindings, effect
context, budget context, property context, candidates, dependent holes, and
rejection reasons when those fields are present. SEP-0010 may choose which fields
to highlight for a user-facing explanation, but it does not define different
field names or a second hole query payload.
```

### Add a normative-owner sentence

Add after the projection paragraph:

```markdown
When SEP-0005 and SEP-0010 appear to overlap, SEP-0005 owns the data contract
and SEP-0010 owns the teaching projection over that contract.
```

### Add related SEP guidance to ConceptDoc

In the `ConceptDoc fields` table, add this explanatory paragraph:

```markdown
For hole-related concept docs, `related_seps` should include SEP-0005 when the
concept explains HoleReport data and SEP-0010 when the concept explains the
teaching or query layer.
```

## SEP-0006 cross-reference patch draft

### Keep shared-record ownership clear

Current text at `seps/SEP-0006-compiler-architecture.md:201-210` says default
text, JSON, LSP, and watch outputs render shared records, while SEP-0010 owns
the concept registry and explain protocol. Add:

```markdown
SEP-0010 teaching metadata is optional metadata over these shared records. It
does not change the identity, hash, or required fields of `Diagnostic`,
`HoleReport`, `Claim`, `EvidenceRecord`, or `VerificationBundle`.
```

## Migration candidate

One current SEP-0010 sentence can be made safer during the patch step:

- Current: `Every user-facing diagnostic should map to at least one concept id`
  at `seps/SEP-0010-compiler-as-documentation.md:291-292`.
- Suggested: `Every user-facing diagnostic produced by the compiler should have
  a path to at least one concept id, either directly or through its diagnostic
  family.`

Reason: the original wording may overconstrain early diagnostics and generated
third-party diagnostics. The revised wording preserves the teaching goal while
allowing family-level concepts.

## Non-overlap rule

Use this rule in the later patch plan:

```text
If a paragraph names fields, schemas, dependency edges, or batch/single-hole
payload shape, it belongs in SEP-0005. If a paragraph names concept ids, repair
hints, explain queries, hover prose, terminal teaching lines, or ConceptDoc
records, it belongs in SEP-0010.
```

## Routing to the patch plan

`@sep-patch-plan` should include these concrete edits:

1. SEP-0005 strengthens the existing SEP-0010 rendering boundary sentence.
2. SEP-0005 adds a note after the normative field table that teaching metadata
   is not part of required HoleReport fields.
3. SEP-0010 strengthens `### Hole teaching projection` to say it renders
   SEP-0005 fields and does not define alternate field names.
4. SEP-0010 adds the explicit owner rule: SEP-0005 owns data, SEP-0010 owns
   teaching projection.
5. SEP-0010 adds `related_seps` guidance for hole-related ConceptDocs.
6. SEP-0006 adds an optional-metadata sentence for SEP-0010 teaching fields.
7. SEP-0010 softens the `Every user-facing diagnostic` line to allow
   diagnostic-family concepts.
