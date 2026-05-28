# PR45 patch plan implementation cross-check

This review maps `.spark/artifacts/sep-patch-plan.md` against the sibling
`spore` implementation. It is review-only: no source code, issues, or TODO files
are changed.

## Review categories

- **Aligned**: implementation already has a recognizable matching concept.
- **Partial**: implementation has adjacent machinery but vocabulary or semantics
  differ from the PR45 patch plan.
- **Follow-up**: implementation work is likely needed after the design patch.
- **Conflict**: implementation behavior directly contradicts the selected PR45
  design and should be tracked before release.

## Summary

| Area | Status | Evidence |
| --- | --- | --- |
| SEP-0001 property surface | Follow-up | Parser and CLI still use `spec`, not `properties`. |
| SEP-0001 handler grammar | Partial | Parser AST already has fields, handles, uses, and impl blocks; tests still omit explicit `self` receiver. |
| SEP-0002 property body typing | Follow-up | Runtime spec testing exists, but Claim/Evidence property typing is not visible in scanned implementation. |
| SEP-0003 effect surface | Aligned | `uses`, `perform`, handlers, and effect contexts exist. |
| SEP-0003 handler state policy | Conflict | Implementation accepts handler fields and materializes payloads; PR45 selects immutable fields and state via primitive effects. |
| SEP-0005 HoleReport schema | Partial | Sibling has HoleInfo/HoleReport JSON, but some field vocabulary differs. |
| SEP-0005 workflow/ranker status | Partial | Sibling has candidate ranking formula; PR45 will mark it informational. |
| SEP-0006 evidence channel | Partial | Diagnostics and hole records exist; full Claim/Evidence property channel is design-forward. |
| SEP-0008 Platform primitive handlers | Follow-up | Platform handled effects exist, but primitive host/mock conformance is not modeled. |
| SEP-0009 primitive effect set | Follow-up | `Clock` and `Random` overlap; `Cell`, `Output`, and effect-level `Map` are missing from collected evidence. |
| SEP-0010 explain protocol | Partial | Low-level `sporec explain <code>` exists; user-facing `spore explain <query>` and ConceptDoc registry are not visible. |

## Patch item cross-check

### SEP-0001 property delegation and grammar

Status: **Follow-up**.

PR45 patch plan uses `properties { name(params): expr }` and delegates typing to
SEP-0002 plus Claim/Evidence lowering to SEP-0006.

Implementation evidence:

- Lexer still has `Token::Spec` in `../spore/crates/sporec-parser/src/lexer.rs:121-123`.
- Function AST stores `spec_clause` in `../spore/crates/sporec-parser/src/ast.rs:90-95`.
- `SpecClause` is documented as examples plus property-based invariants in
  `../spore/crates/sporec-parser/src/ast.rs:159-166`.
- CLI test source uses `spec { ... property ... }` in
  `../spore/crates/spore/src/main.rs:208-211`.

Review result: design patch can proceed, but implementation follow-up should
plan a surface migration from `spec` to `properties` or a compatibility story.

### SEP-0001 handler grammar

Status: **Partial**.

Implementation evidence:

- `HandlerDef` includes `fields`, `handles_clause`, optional `uses_clause`, and
  `impls` in `../spore/crates/sporec-parser/src/ast.rs:493-499`.
- `HandlerImpl` stores `effect` plus `methods` in
  `../spore/crates/sporec-parser/src/ast.rs:483-489`.
- `handle ... with` has named `use` and inline `on` arms through
  `HandleBinding::Use` and `HandleBinding::On` in
  `../spore/crates/sporec-parser/src/ast.rs:310-326`.
- Parser test covers `handler MockConsole(output: List[Str]) handles [Console]
  uses [Clock] { impl Console { ... } }` in
  `../spore/crates/sporec-parser/tests/parser_tests.rs:486-500`.

Review result: grammar shape is close to the PR45 patch plan. The explicit
read-only `self` receiver remains a follow-up because the observed test method
uses `fn println(msg: String) -> Unit`, not `fn println(self, msg: Str) -> ()`.

### SEP-0002 property body typing

Status: **Follow-up**.

Implementation evidence:

- `test_specs` runs spec clauses in `../spore/crates/sporec-driver/src/compiler/source.rs:88-95`.
- The CLI test command is described as executing examples and properties in
  `../spore/crates/spore/src/cli.rs:103-105`.
- Runtime spec evaluation is driven from functions with spec clauses in
  `../spore/crates/sporec-codegen/src/interpret/mod.rs:201-205`.

Review result: the implementation has executable property-like tests, but the
scanned evidence does not show the selected PR45 rule: ordinary expression body,
strict `Bool`, effect-context inheritance, and lowering into Claim/Evidence.

### SEP-0003 effect surface and handlers

Status: **Aligned / Partial**.

Aligned evidence:

- `Token::Uses` exists in `../spore/crates/sporec-parser/src/lexer.rs:103-105`.
- Function AST stores `uses_clause` in `../spore/crates/sporec-parser/src/ast.rs:94-95`.
- `Expr::Perform` records effect, operation, and args in
  `../spore/crates/sporec-parser/src/ast.rs:285-294`.
- Interpreter has named handlers and a handler stack in
  `../spore/crates/sporec-codegen/src/interpret/mod.rs:33-38` and
  `../spore/crates/sporec-codegen/src/interpret/eval.rs:431-432`.

Partial evidence:

- Implementation still has legacy effect alias terminology in
  `../spore/crates/sporec-parser/tests/parser_tests.rs:470-480`, while PR45 uses
  `surface` for named effect surfaces.

Review result: core effect mechanics are present, but terminology and handler
state rules need follow-up.

### SEP-0003 handler state policy

Status: **Conflict**.

Implementation evidence:

- Handler payload initialization is modeled by `HandlerUse.payload` in
  `../spore/crates/sporec-parser/src/ast.rs:316-321`.
- Interpreter materializes handler payload values in
  `../spore/crates/sporec-codegen/src/interpret/builtins.rs:84-86`.
- Current SEP-0003 example mutates `self.output.push(msg)` in PR45 text, while
  D3 selects immutable handler fields and primitive-effect state.

Review result: the design patch should explicitly declare field immutability and
primitive-effect state. Implementation follow-up should audit whether any parser,
formatter, interpreter, or docs imply field mutation.

### SEP-0005 HoleReport schema

Status: **Partial**.

Implementation evidence:

- `HoleInfo` includes `name`, `location`, `expected_type`,
  `type_inferred_from`, `function`, `enclosing_signature`, `bindings`,
  `binding_dependencies`, `available_effects`, `errors_to_handle`,
  `effect_context`, `cost_budget`, `residual_context`, `candidates`,
  `dependent_holes`, `confidence`, and `error_clusters` in
  `../spore/crates/sporec-typeck/src/hole.rs:124-170`.
- JSON mapping happens in `hole_info_json` at
  `../spore/crates/sporec-driver/src/compiler/hole_json.rs:94-171`.

Review result: the implementation already has a rich HoleReport. Follow-up is
needed for `property_context`, budget-vocabulary migration, and per-hole versus
candidate-level rejection-reason shape.

### SEP-0005 workflow and ranker demotion

Status: **Partial**.

Implementation evidence:

- `CandidateScore::overall` implements the current formula in
  `../spore/crates/sporec-typeck/src/hole.rs:36-42`.
- Candidate JSON emits `overall`, fit fields, rejection reasons, explanation,
  adjustments, and cost check in
  `../spore/crates/sporec-driver/src/compiler/hole_json.rs:130-160`.

Review result: implementation may keep this as reference behavior, but PR45
should avoid making the formula a normative Agent protocol.

### SEP-0006 Claim/Evidence channel

Status: **Partial / Follow-up**.

Implementation evidence:

- Diagnostic and HoleReport JSON records are exported from
  `../spore/crates/sporec-driver/src/lib.rs:27-31`.
- Compile output currently exposes warnings, including cost budget warnings, in
  `../spore/crates/sporec-driver/src/compiler/mod.rs:21-23`.
- Signature hashing machinery exists in
  `../spore/crates/sporec-typeck/src/sig_hash.rs:146-177`.

Review result: shared diagnostics and hash machinery exist, but the PR45
Claim/EvidenceRecord channel for source properties is not visible in the scanned
implementation and should be a follow-up.

### SEP-0008 Platform primitive handler obligation

Status: **Follow-up**.

Implementation evidence:

- Platform model includes `handled_effects` and startup contract fields in
  `../spore/crates/sporec-typeck/src/platform.rs:12-31`.
- CLI Platform handles `Console`, `FileRead`, `FileWrite`, `NetConnect`,
  `NetListen`, `Env`, `Spawn`, `Clock`, `Random`, and `Exit` in
  `../spore/crates/sporec-typeck/src/platform.rs:46-56`.
- Web Platform handles `Console`, `NetConnect`, `Random`, and `Clock` in
  `../spore/crates/sporec-typeck/src/platform.rs:79-84`.
- Project manifests also model platform handled effects in
  `../spore/crates/sporec-driver/src/project/mod.rs:184-217`.

Review result: Platform handled effects exist. No scanned evidence shows the
new PR45 requirement that each state primitive has both a host handler family and
an in-memory mock handler family.

## Primitive effect handler mapping

| Primitive effect | Implementation status | Evidence |
| --- | --- | --- |
| `Cell[T]` | Missing as effect | `Cell` appears only as Rust `std::cell::Cell` in `../spore/crates/sporec-codegen/src/native.rs:1`; no effect-level `Cell` evidence found. |
| `Output[T]` | Missing as effect | Output is present as Rust/CLI output types, but no `Output` effect evidence found in scanned files. |
| `Map[K, V]` | Partial as value type, missing as effect | `Value::Map` exists in `../spore/crates/sporec-codegen/src/value.rs:26-27`; no effect-level `Map` evidence found. |
| `Clock` | Present as Platform handled effect | CLI and web handled effects include `Clock` in `../spore/crates/sporec-typeck/src/platform.rs:53-55` and `../spore/crates/sporec-typeck/src/platform.rs:81-84`. |
| `Random` | Present as Platform handled effect | CLI and web handled effects include `Random` in `../spore/crates/sporec-typeck/src/platform.rs:53-55` and `../spore/crates/sporec-typeck/src/platform.rs:81-84`. |

## SEP-0010 explain protocol

Status: **Partial**.

Implementation evidence:

- Low-level `sporec explain` command exists in
  `../spore/crates/sporec-driver/src/main.rs:68-74` and dispatches in
  `../spore/crates/sporec-driver/src/main.rs:93-94`.
- `exec_explain` normalizes a diagnostic code and renders explanation data in
  `../spore/crates/sporec-driver/src/main.rs:290-300`.
- Error codes expose `explain()` in `../spore/crates/sporec-typeck/src/error.rs:202-204`.
- A test covers `sporec explain E0001` in
  `../spore/crates/sporec-driver/tests/sporec_cli_tests.rs:437-442`.
- Project CLI evidence in the scan did not show a user-facing `spore explain`
  command.
- No `ConceptDoc`, `ConceptRegistry`, `concept_refs`, `repair`, or
  `explanation_key` implementation evidence was found in the scan.

Review result: the implementation has a diagnostic-code explanation seed, but
SEP-0010's concept query protocol and teaching metadata remain design-forward.

## SPARK.md and syntax decision conflicts

Status: **No direct file edits performed**.

Cross-check scope was review-only. The collected evidence from sibling code
matches prior context: user-level mutation is absent from the language surface,
while runtime internals use `RefCell` for channels and tasks. Examples:

- `TaskHandle` and `ChannelEndpoint` carry `Rc<RefCell<...>>` in
  `../spore/crates/sporec-codegen/src/interpret/eval.rs:247-282`.
- `Value::Map` exists as runtime data in
  `../spore/crates/sporec-codegen/src/value.rs:26-27`.

No implementation edit is recommended in this PR. These are follow-up
classification points only.

## Follow-up recommendations

| Priority | Recommendation | Kind |
| --- | --- | --- |
| P1 | Decide implementation migration path from `spec` to `properties`, or document compatibility. | change implementation |
| P1 | Migrate cost-vector user surface and HoleReport JSON vocabulary to realization-shape budgets when PR45 text lands. | change implementation |
| P1 | Add property context to HoleInfo/HoleReport if PR45 keeps it normative. | change implementation |
| P1 | Audit handler implementation for any field mutation semantics and align with immutable handler field policy. | change implementation |
| P2 | Add primitive-effect Platform conformance model for `Cell`, `Output`, `Map`, `Clock`, and `Random`. | write issue / change implementation |
| P2 | Extend low-level `sporec explain` into user-facing `spore explain` plus ConceptDoc registry if SEP-0010 remains in PR45. | write issue / change implementation |
| P2 | Add implementation docs clarifying no default Platform if current compatibility paths are retained. | write issue |

## Aligned samples

At least three patch-plan themes already have implementation anchors:

1. Effect declarations and `uses` are already parsed and checked at the concept
   level (`Token::Uses`, `uses_clause`, `Expr::Perform`).
2. Rich HoleReport data exists through `HoleInfo` and `hole_info_json`.
3. Platform handled effects exist and include `Clock` and `Random`.
4. Low-level diagnostic explanations exist through `sporec explain`.

## Follow-up samples

At least three patch-plan themes need implementation follow-up:

1. `properties` plus strict `Bool` body typing and Claim/Evidence lowering.
2. Named realization-shape `budget` replacing old `cost` vector vocabulary.
3. Primitive effect conformance for `Cell`, `Output`, and effect-level `Map`.
4. SEP-0010 ConceptDoc and concept-reference metadata.

## Review conclusion

The PR45 design patch can proceed without modifying sibling implementation. The
largest implementation gaps are vocabulary and protocol migrations rather than
missing parser scaffolding: handlers, effects, holes, platforms, diagnostics,
and low-level explanations all have partial anchors. The riskiest divergence is
that PR45 now selects immutable handler fields with state routed through
primitive effects, while the implementation still carries handler payloads and
older stateful examples. Track that as a P1 implementation follow-up after the
spore-evolution design patch lands.
