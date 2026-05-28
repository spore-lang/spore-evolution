# D1 property expression specification draft

This artifact turns the D1 decision into patch-ready text for SEP-0001,
SEP-0002, and SEP-0006. It does not edit the SEP files directly.

## Locked decision

D1 is fixed as follows:

- A source property body is an ordinary Spore expression.
- The property body result type is strictly `Bool`.
- The property body is checked in the enclosing callable's effect context.
- The property body can perform only effects included by the enclosing
  `uses` surface or discharged by a local handler context.
- A non-`Bool` property body is a compile-time typing error.
- A property body that the checker cannot decide lowers to an evidence claim
  with result `unknown`; this state does not by itself reject compilation.
- Source properties and refinement obligations share the SEP-0006 `Claim` and
  `EvidenceRecord` projection.

## Evidence from current text

| Document | Current evidence | D1 impact |
| --- | --- | --- |
| SEP-0001 | `properties` follows `uses` and `budget` in fixed intent-signature order at `seps/SEP-0001-core-syntax.md:67-83`. | The fixed order stays unchanged. |
| SEP-0001 | The reference layout says `[properties { <name>(<params>): <expr>, ... }]` at `seps/SEP-0001-core-syntax.md:227-230`. | The grammar already allows an arbitrary expression after `:`. |
| SEP-0001 | `PropertyItem = Ident "(" [ PropertyParamList ] ")" ":" Expr` at `seps/SEP-0001-core-syntax.md:286-287`. | The syntax stays, but the semantic result type must be specified as `Bool`. |
| SEP-0002 | Refinement obligations lower into a Claim when not decidable immediately at `seps/SEP-0002-type-system.md:209-213`. | Property obligations should use the same claim/evidence channel. |
| SEP-0006 | Source properties lower into Claims at `seps/SEP-0006-compiler-architecture.md:64-77`. | This is the owner of source property lowering. |
| SEP-0006 | EvidenceRecord includes `passed`, `failed`, `unknown`, and `skipped` under result at `seps/SEP-0006-compiler-architecture.md:128-160`. | D1 uses `unknown` for undecided property checks. |
| SEP-0006 | Diagnostics include property and claim diagnostics at `seps/SEP-0006-compiler-architecture.md:219-227`. | Non-`Bool` properties produce type diagnostics; failed checks produce property diagnostics. |

## SEP-0001 patch draft

### Target

Patch the EBNF area around `seps/SEP-0001-core-syntax.md:286-290`.

### Keep

Keep the source grammar shape:

```ebnf
PropertiesBlock = "properties" "{" { PropertyItem } "}" ;
PropertyItem    = Ident "(" [ PropertyParamList ] ")" ":" Expr ;
PropertyParamList = PropertyParam { "," PropertyParam } [ "," ] ;
PropertyParam   = Ident ":" TypeExpr ;
```

### Add after the grammar block

```markdown
`PropertyItem` syntax accepts an ordinary expression after `:`. SEP-0002 owns
its typing rule and SEP-0006 owns its lowering into claims and evidence. The
expression is not a separate proof sublanguage.
```

### Add to the delegation paragraph

Current text at `seps/SEP-0001-core-syntax.md:82-83` delegates property
semantics to SEP-0006. Replace it with:

```markdown
Clause semantics are delegated: `uses` -> SEP-0003, `budget` -> SEP-0004,
and `properties` -> SEP-0002 for expression typing plus SEP-0006 for
claim/evidence lowering.
```

### Remove or replace unresolved wording

SEP-0001 currently asks which property expression subset is accepted at
`seps/SEP-0001-core-syntax.md:435`. Replace that question with:

```markdown
How should the compiler present `unknown` property evidence when a checker cannot
decide an otherwise well-typed `Bool` property body?
```

Reason: the expression subset is no longer open. D1 allows ordinary Spore
expressions and relies on type, effect, and evidence checks.

## SEP-0002 patch draft

### Target

Add a subsection after `### Outcome typing` and before `### Refinement
obligations`, near `seps/SEP-0002-type-system.md:191-213`.

### New subsection

```markdown
### Property body typing

A source property body is an ordinary Spore expression checked under the
surrounding callable's type environment.

If a property item is written as:

```spore
properties {
    name(params...): body
}
```

then `body` must check against `Bool`. A body with any other result type is a
type error. Property parameters introduce local bindings with the declared types
for the property body only; they do not change the callable's Base Signature.

The property body inherits the enclosing callable's effect context. It may only
perform effects included in the enclosing `uses` surface or effects discharged
by a narrower local handler context. A property body that requires an unavailable
effect is an effect-checking error.

The type checker does not need to decide whether every well-typed property is
true. It only establishes that the property is a `Bool` expression in the right
type and effect context. Decidable failures may become immediate diagnostics;
undecidable obligations lower into SEP-0006 claims.
```

### Link refinement obligations to the same channel

Current text at `seps/SEP-0002-type-system.md:209-213` says undecidable
refinements lower into a Claim. Extend the paragraph with:

```markdown
This is the same claim/evidence channel used for source properties. Source
properties and refinement obligations differ in where they come from, not in the
shape of the downstream claim record.
```

## SEP-0006 patch draft

### Target

Patch `### Properties become claims` around
`seps/SEP-0006-compiler-architecture.md:64-77` and `### EvidenceRecord
structure` around `seps/SEP-0006-compiler-architecture.md:128-160`.

### Replace the lowering paragraph

Current text says the parser records a source property and the compiler lowers
it into an internal Claim. Replace the paragraph with:

```markdown
The parser records a source property. SEP-0002 first checks the property body as
an ordinary Spore expression whose result type must be `Bool` and whose required
effects must fit inside the enclosing effect context. After that check, the
compiler lowers the property into an internal `Claim` with normalized subject,
parameters, predicate expression, effect context, and source span.
```

### Add a shared-origin paragraph

Add after the lowering paragraph:

```markdown
A `Claim` may originate from a source `properties` item, a refinement obligation,
a budget check, an effect check, or a validator. Source properties and refinement
obligations share the same `Claim` and `EvidenceRecord` structure so tools do
not need a separate property protocol.
```

### Add result semantics

Add after the `EvidenceRecord` tree near `seps/SEP-0006-compiler-architecture.md:128-160`:

```markdown
For property claims, `result.passed` means the checker established the property
for the checked subject. `result.failed` means the checker produced a failing
case, counter-witness, or direct contradiction. `result.unknown` means the
property was well typed but the checker could not decide it with the available
analysis or evidence. `result.skipped` means the checker did not run.

A well-typed property with `unknown` evidence remains visible to tools and
reviewers. It is not the same as a type error and does not by itself reject
compilation. Release gates and package policies may choose stricter treatment
for unknown evidence.
```

### Diagnostics split

Add to the diagnostics impact section near `seps/SEP-0006-compiler-architecture.md:219-227`:

```markdown
A property body that does not check as `Bool` is reported as a type diagnostic
because the source expression is ill typed. A property body that checks as
`Bool` but fails or remains unknown is reported as a property or claim diagnostic
because the source shape is valid and the evidence result is the issue.
```

## Open questions removed by D1

D1 closes these previous ambiguities:

- Property bodies are not restricted to a verifier-only expression subset.
- Property bodies are not assumed to be pure unless the enclosing effect context
  is pure.
- Non-`Bool` property bodies are not interpreted as truthy values.
- Unknown evidence is not a compile-time type failure.

## Compatibility notes for the sibling implementation

The sibling implementation currently groups examples and properties under
`spec`, for example `sporec-parser/src/ast.rs:159-166` and
`spore/src/main.rs:208-211`. This artifact does not ask the implementation to
rename that surface. It only records that PR45's design vocabulary is
`properties` plus `Claim`/`EvidenceRecord`.

## Routing to the patch plan

`@sep-patch-plan` should include these concrete edits:

1. SEP-0001 delegation paragraph update.
2. SEP-0001 note that `PropertyItem` body is ordinary `Expr`, not a proof
   sublanguage.
3. SEP-0001 unresolved question replacement.
4. SEP-0002 new `Property body typing` subsection.
5. SEP-0002 refinement-obligation paragraph extension.
6. SEP-0006 property-to-claim lowering replacement.
7. SEP-0006 shared-origin paragraph.
8. SEP-0006 property evidence result semantics.
9. SEP-0006 diagnostics split for non-`Bool` versus failed or unknown property
   evidence.
