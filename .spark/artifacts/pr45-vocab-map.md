# PR45 vocabulary map

This artifact maps the current PR45 SEP vocabulary to the sibling `spore`
implementation vocabulary. It is descriptive evidence for the later design patch
plan; it does not propose source changes.

## Scan scope

- PR45 design repository: `spore-evolution` at `080b97e` on
  `refine-vision-sep-process`.
- Design inputs: `seps/SEP-0000` through `seps/SEP-0010`, `GLOSSARY.md`,
  `VISION.md`, `README.md`, and `drafts/script-mode.md`.
- Sibling implementation repository: `../spore`, especially
  `crates/sporec-parser`, `crates/sporec-typeck`, `crates/sporec-driver`,
  `crates/sporec-codegen`, `crates/spore-lsp`, and `crates/spore`.

## Reproducible scans

Representative commands used for this pass:

```bash
grep -RInE '\b(properties|property|Claim|EvidenceRecord|refinement|obligation)\b' \
  GLOSSARY.md VISION.md README.md drafts seps

grep -RInE '\b(budget|realization shape|branches|nesting|recursion|parallelism|effects)\b' \
  GLOSSARY.md VISION.md README.md drafts seps

grep -RInE '\b(uses|effect surface|atomic effect|handler|handles|handle|with|use|on)\b' \
  GLOSSARY.md VISION.md README.md drafts seps

grep -RInE '\b(HoleReport|hole report|explain|compiler-as-documentation|candidate|scoring|workflow)\b' \
  GLOSSARY.md VISION.md README.md drafts seps

grep -RInE 'Spec|spec|Cost|cost|Budget|budget|Property|property' \
  ../spore/crates

grep -RInE 'Handler|handler|handles|handle|with|HoleInfo|HoleReport|candidate|score|confidence' \
  ../spore/crates
```

The table below records representative file and line evidence rather than every
match.

## Vocabulary table

| Area | PR45 vocabulary and evidence | Sibling implementation evidence | Status |
| --- | --- | --- | --- |
| Signature path | `Signature -> Property -> Hole -> Realization -> Evidence` is stated in `VISION.md:9` and `README.md:25`. | The sibling command surface still exposes `spore test` as spec execution in `spore/src/cli.rs:103-105`. | Partial mismatch: the vision path is property centered, while the implementation command names remain spec centered. |
| Intent clauses | `uses`, `budget`, and `properties` are the fixed intent-signature clause order in `seps/SEP-0001-core-syntax.md:67-83`. | Parser data structures still store `cost_clause`, `spec_clause`, and `uses_clause` in `sporec-parser/src/ast.rs:90-95`. | Mismatch: `budget` and `properties` are PR45 names; `cost` and `spec` are implementation names. |
| Property source surface | `PropertyItem = Ident "(" [ PropertyParamList ] ")" ":" Expr` is the PR45 grammar shape in `seps/SEP-0001-core-syntax.md:286-287`; `Property` is defined in `GLOSSARY.md:158-160`. | The parser owns a `SpecClause` with examples and property-based invariants in `sporec-parser/src/ast.rs:159-166`; CLI tests use `spec { ... property ... }` in `spore/src/main.rs:208-211`. | Mismatch: PR45 has a `properties { ... }` block, while implementation groups examples and properties under `spec`. |
| Property lowering | PR45 defines `Claim` in `GLOSSARY.md:64` and `EvidenceRecord` in `GLOSSARY.md:100`; SEP-0002 says undecidable refinements lower into a Claim in `seps/SEP-0002-type-system.md:209-213`. | Spec evaluation is runtime test execution through `test_specs` in `sporec-driver/src/compiler/source.rs:88-95` and interpreter enumeration in `sporec-codegen/src/interpret/mod.rs:201-205`. | Mismatch: PR45 is claim/evidence oriented; implementation is test-run oriented. |
| Budget surface | `Budget` is a named integer upper bound on realization shape in `GLOSSARY.md:58`; SEP-0004 replaces resource vectors with named shape budgets in `seps/SEP-0004-cost-analysis.md:20`. | Parser comments define `cost [compute, alloc, io, parallel]` in `sporec-parser/src/ast.rs:77-91`; JSON still exposes compute/alloc/io/parallel in `sporec-driver/src/compiler/hole_json.rs:85-90`. | Clear mismatch: PR45 uses named realization-shape budget; implementation still uses the older four-vector cost model. |
| Budget context in holes | PR45 `HoleReport` includes `budget_context` in `seps/SEP-0005-hole-system.md:126-129`, and SEP-0004 says HoleReport embeds budget constraints in `seps/SEP-0004-cost-analysis.md:213-214`. | Sibling JSON has `HoleCostBudgetJson`, `HoleCostVectorJson`, and residual cost fields in `sporec-driver/src/compiler/hole_json.rs:5-8` and `sporec-driver/src/compiler/hole_json.rs:118-129`. | Partial alignment: both expose hole budget context, but the payload vocabulary is cost-vector based in implementation. |
| Effect surface | PR45 defines `Effect surface` in `GLOSSARY.md:94` and states that every `uses` item resolves to an atomic effect or named surface in `seps/SEP-0003-effect-system.md:35-40`. | Parser has `Token::Uses` in `sporec-parser/src/lexer.rs:103-105` and a `uses_clause` field in `sporec-parser/src/ast.rs:94-95`. | Aligned at the keyword level; PR45 adds the surface/atomic taxonomy that the implementation only partly names. |
| Handler declaration | PR45 owns handlers in SEP-0003 and says handlers discharge or reinterpret effects in `seps/SEP-0003-effect-system.md:115-116`; handler method typing appears in `seps/SEP-0003-effect-system.md:143-146`. | Sibling parser has `Token::Handler` in `sporec-parser/src/lexer.rs:121-123`; interpreter stores named handlers in `sporec-codegen/src/interpret/mod.rs:33-34`; handler stack execution appears in `sporec-codegen/src/interpret/eval.rs:431-432`. | Partial alignment: both have handlers, but D3 still needs the PR45 state policy and grammar closure. |
| Handler state examples | PR45 currently shows a stateful-looking handler example around `seps/SEP-0003-effect-system.md:101-115`. | Sibling execution materializes handle bindings and pushes handler frames in `sporec-codegen/src/interpret/eval.rs:431-432`; previous parser evidence includes stateful handler tests around `sporec-parser/tests/parser_tests.rs:486-490`. | Design mismatch to resolve: PR45 D3 now selects immutable handler fields and state via primitive effects. |
| Platform-provided effects | PR45 says Platform packages supply replaceable handlers in `seps/SEP-0003-effect-system.md:43-46`; standard-library prelude text says Platform-specific effects remain in Platform packages in `seps/SEP-0009-standard-library.md:135-137`. | Sibling type checker has built-in platform effect sets including `Console`, `FileRead`, `FileWrite`, `Spawn`, `Clock`, `Random`, and `Exit` in `sporec-typeck/src/platform.rs:46-56` and `sporec-typeck/src/platform.rs:79-84`. | Partial alignment: implementation already recognizes Platform effects; PR45 needs the primitive-effect taxonomy and explicit no-default-platform stance. |
| Primitive effect candidates | PR45 currently has no `State primitive effect` term; standard-library open question asks which Platform packages ship with the standard library in `seps/SEP-0009-standard-library.md:240-241`. | Sibling already treats `Clock` and `Random` as built-in platform effects in `sporec-typeck/src/platform.rs:53-55`; no matching `Cell`, `Output`, or `Map` primitive effect was found in the collected implementation evidence. | Gap: PR45 must introduce the five-effect semantic set; implementation only partially overlaps through `Clock` and `Random`. |
| HoleReport schema | PR45 names `HoleReport` as collaboration boundary in `seps/SEP-0005-hole-system.md:53-54` and lists fields in `seps/SEP-0005-hole-system.md:112-134`. | Sibling exports `HoleInfoJson`, `HoleReportJson`, and related JSON structs through `sporec-driver/src/lib.rs:27-31` and maps type-checker data in `sporec-driver/src/compiler/hole_json.rs:94-121`. | Broadly aligned, but field names and budget vocabulary need cross-checking. |
| Candidate ranking | PR45 says Agents can rank candidates using typed context in `seps/SEP-0005-hole-system.md:179-180`; workflow text starts at `seps/SEP-0005-hole-system.md:90-99`. | Sibling maps `CandidateRanking` to JSON in `sporec-driver/src/compiler/hole_json.rs:41-46` and exposes candidate fit fields in `sporec-driver/src/compiler/hole_json.rs:138-146`. | Partial alignment: implementation has ranking data, while D5 decides that workflow and scoring are informational. |
| Explain protocol | PR45 SEP-0010 defines the explain protocol and compiler-as-documentation in `seps/SEP-0010-compiler-as-documentation.md:18-34`; `ConceptDoc` is defined in `GLOSSARY.md:68-70`. | Sibling has CLI `holes` and LSP hole hovers, for example `spore/src/cli.rs:133-138` and `spore-lsp/tests/lsp_tests.rs:287-303`; no `spore explain` implementation evidence was found in this scan. | Gap: SEP-0010 is design-forward; implementation has adjacent diagnostics and hover surfaces, not the explain protocol. |
| SEP-0005 versus SEP-0010 boundary | PR45 already states that educational renderings of HoleReport records are owned by SEP-0010 in `seps/SEP-0005-hole-system.md:205-207`; SEP-0010 says HoleReports remain SEP-0005 records in `seps/SEP-0010-compiler-as-documentation.md:114-115` and `seps/SEP-0010-compiler-as-documentation.md:189-191`. | Sibling hole JSON and LSP hovers both project from hole data, for example `sporec-driver/src/compiler/hole_json.rs:94-121` and `spore-lsp/tests/lsp_tests.rs:287-303`. | Mostly aligned conceptually; @d10-explain-boundary must make this cross-reference precise. |
| Signature hash / content identity | PR45 defines `Intent hash` in `GLOSSARY.md:130` and mentions package identity over signatures, intents, properties, realizations, evidence, and dependencies in `GLOSSARY.md:66`. | Sibling has `SigHashMap` and changed-item diffing in `sporec-typeck/src/sig_hash.rs:146-177`. | Partial alignment: both have hash identity, but handler runtime fields and primitive effects need PR45 policy before implementation follow-up. |
| Concurrency effects | PR45 SEP-0007 expresses concurrency through `uses [Spawn]` and budget `parallelism` in `seps/SEP-0007-concurrency-model.md:135-136` and `seps/SEP-0007-concurrency-model.md:195-196`. | Sibling platform includes `Spawn` in built-in effects in `sporec-typeck/src/platform.rs:53-56`; runtime uses `TaskHandle` and `ChannelEndpoint` with `RefCell` in `sporec-codegen/src/interpret/eval.rs:247-282`. | Aligned at the named-effect level; implementation has runtime mutable state below the user language surface. |
| Script/platform default | PR45 script-mode draft says standalone execution does not inherit project Platform contracts in `drafts/script-mode.md:273-279` and `drafts/script-mode.md:297-301`. | Sibling CLI resolves standalone targets in `spore/src/target.rs:170-210` and project roots in `spore/src/target.rs:42-73`. | Partial alignment: no default Platform is the selected PR45 stance, while implementation has compatibility paths to audit later. |

## Main mismatches for downstream tasks

1. **`properties` versus `spec`**: PR45 has intent-signature properties;
   sibling implementation still groups examples and properties in `spec`.
2. **`budget` versus `cost`**: PR45 has named realization-shape budgets;
   sibling implementation still serializes the older compute/alloc/io/parallel
   cost-vector payload.
3. **Hole protocol scope**: PR45 will make HoleReport the normative protocol;
   workflow and scoring become informational. Sibling implementation already has
   candidate ranking data, so later review must separate data shape from ranker
   policy.
4. **Handler state policy**: PR45 D3 selects immutable handler fields and state
   through primitive effects; sibling implementation has named handlers and
   handle frames but still needs a spec-level state policy audit.
5. **Primitive effect taxonomy**: PR45 will introduce a five-member primitive
   set (`Cell`, `Output`, `Map`, `Clock`, `Random`) with membership rules.
   Sibling implementation only shows direct overlap for `Clock` and `Random` in
   the collected evidence.
6. **SEP-0010 forward design**: PR45 now includes explain protocol design;
   sibling implementation has hole JSON and LSP hover surfaces but no observed
   `spore explain` command in this scan.

## Follow-on task routing

- `@d1-property` should use the `properties` versus `spec` rows to draft the
  PR45 property rule without inheriting implementation `spec` syntax.
- `@primitive-effects` should use the platform rows to keep primitive-effect
  membership rules in SEP-0003, concrete interfaces in SEP-0009, and Platform
  handler obligations in SEP-0008.
- `@d3-handler` should use the handler rows to distinguish accepted handler
  syntax from the newly selected immutable-state policy.
- `@d5-agent` should use the HoleReport rows to keep schema normative while
  moving workflow and scoring to informational text.
- `@d10-explain-boundary` should use the SEP-0005 versus SEP-0010 rows to keep
  HoleReport data and explain projections separate.
- `@cross-check-impl` should later expand each partial-alignment row into
  implementation follow-up categories.
