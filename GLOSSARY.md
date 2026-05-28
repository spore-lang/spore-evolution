# Spore Glossary

Unified terminology index for Spore. Each term links to the SEP where it is
authoritatively defined.

This file also owns the multilingual terminology table used by Spore
documentation translations. When a new user-facing term is added to Spore docs,
update both its glossary definition and its multilingual correspondence here.

## Multilingual terminology

| Term              | zh-CN        |
| ----------------- | ------------ |
| Spore             | 孢子         |
| Agent             | 智能体       |
| Signature         | 签名         |
| Base Signature    | 基础签名     |
| Intent Signature  | 意图签名     |
| Outcome           | 结果         |
| Property          | 性质         |
| Hole              | 洞           |
| Typed absence     | 有类型的缺失 |
| Realization       | 实现         |
| Evidence          | 证据         |
| Claim             | 检查主张     |
| Budget            | 预算         |
| Realization shape | 实现形态     |
| Effect surface    | 效应表面     |
| Effect            | 效应         |
| Effect context    | 效应上下文   |
| Effect handler    | 效应处理器   |
| Platform          | 平台         |
| Content-addressed | 内容寻址     |
| Content identity  | 内容身份     |
| Provenance hash   | 来源哈希     |
| Diagnostic        | 诊断         |
| HoleReport        | 洞报告       |
| Dependency        | 依赖         |
| Checker           | 检查器       |

## A

**Atomic effect** (SEP-0003): A single effect protocol declared with `effect Name { ... }`, as opposed to a reusable surface declaration.

**`await`** (SEP-0007): Expression that blocks until a `Task[T, E]` completes, extracts its success value of type `T`, and reintroduces failure type `E` at the await site.

## B

**Base Signature** (SEP-0001): The callable boundary made of function name, type parameters, parameter types, and result type (including any outcome boundary). It defines possible implementation space.

**Bidirectional inference** (SEP-0002): Type inference strategy combining synthesis from expressions and checking against expected types.

**Budget** (SEP-0004): A named integer upper bound on realization shape, written in a `budget { ... }` block.

**Budget context** (SEP-0005): The subset of enclosing budget constraints relevant to a hole or realization candidate.

## C

**Claim** (SEP-0006): Internal compiler representation derived from a source `properties` item.

**Content-addressed package** (SEP-0008): Package identified by hashes of normalized signatures, intents, properties, realizations, evidence, and dependency inputs.

## D

**Declared effects** (SEP-0003): Effect names explicitly written on a function or platform surface.

**Default literals** (SEP-0002): Unsuffixed integer literals synthesize as `I64` and float literals as `F64` unless a signature or context fixes another width.

**Diagnostic code** (SEP-0006): Structured error or warning identifier in the format `X0NNN`, where X is a category letter.

## E

**Effect** (SEP-0003): Observable interaction with the outside world that must be declared in a `uses` effect surface.

**Effect surface declaration** (SEP-0003): A named reusable surface written as `surface Name = [EffectA, EffectB]`.

**Effect context** (SEP-0005): The declared effects, expanded effect set, active handlers, and discharged effects visible at a hole or realization candidate.

**Effect handler** (SEP-0003, SEP-0008): Implementation of effect operations, often provided by a selected Platform package.

**Effect set** (SEP-0003): Unordered collection of effects associated with a function or scope.

**Effect surface** (SEP-0001, SEP-0003): The `uses` surface expression attached to an intent signature. SEP-0003 defines the accepted effect names, surface declarations, handlers, and checking rules.

**Enum** (SEP-0002): Algebraic data type with named variants, each optionally carrying data. Defined with `enum Name { Variant(T) }`.

**Evidence** (SEP-0006): Generated checked record of what held for a concrete realization.

**EvidenceRecord** (SEP-0006): Machine payload containing subject, claim, checker, result, and provenance hash data.

**Evidence hash** (SEP-0008): Hash of the evidence records selected by a package or publication policy.

**`@export`** (SEP-0001, SEP-0008): Attribute marking a public Spore function as an outbound ABI surface, for example `@export("C")`.

## F

**`@foreign`** (SEP-0001, SEP-0008): Attribute marking a function or type as externally provided. On functions it may also carry linkage metadata such as `@foreign("ssl", name = "SSL_new")`.

## G

**Generics** (SEP-0002): Parametric polymorphism using type variables in square brackets, with bounds written inline, as in `fn f[T: Eq + Hash](x: T)`.

## H

**Hole** (SEP-0005): Typed absence in source code, written as `?name`, constrained by base signature, effect context, budget context, and property context.

**Hole context** (SEP-0005): The type environment, visible bindings, effect context, budget context, property context, and dependency information associated with a typed hole.

**Hole Dependency Graph** (SEP-0005): DAG ordering typed holes by data-flow, type, effect, budget, and property dependencies for fill scheduling.

**Hole realization workflow** (SEP-0005): Agent-facing realization loop: DISCOVER -> ANALYZE -> PROPOSE -> VERIFY -> ACCEPT or REJECT.

## I

**Intent Signature** (SEP-0001): Signature metadata after the base signature: `uses`, `budget`, and `properties`.

**Intent hash** (SEP-0006, SEP-0008): Hash of canonical `uses`, `budget`, and `properties` metadata attached to a callable.

**Import resolution** (SEP-0008): Mapping import declarations to concrete module files and verifying symbol visibility.

**Index** (SEP-0002): Compile-time non-negative size kind used by indexed types such as `Array[T, N]` and `Vec[T, max: N]`.

## M

**Module** (SEP-0008): A single Spore source file whose module path is derived from its filesystem path.

## N

**NDJSON** (SEP-0006): Newline-delimited JSON output format for watch mode.

**Never** (SEP-0002): The bottom type, used for functions that never return.

**Nominal typing** (SEP-0002): Types are distinguished by name, not by structure alone.

## O

**`Option[T]`** (SEP-0009): Prelude type representing an optional value: `Some(T)` or `None`.

## P

**Platform** (SEP-0008): Package that provides effect handlers for a target environment and validates startup contracts.

**Prelude** (SEP-0009): Types, traits, and functions available in every Spore module without explicit import.

**Property** (SEP-0001, SEP-0006): Source-level validity rule written in `properties { name(params): expr }`.

**Property context** (SEP-0005): Properties from the enclosing intent signature projected into a hole report.

**Property hash** (SEP-0006, SEP-0008): Hash of normalized properties attached to a callable or contract.

## R

**Realization** (SEP-0005, SEP-0006): Property-preserving completion of typed absence. It is a process and artifact identity, not a source keyword.

**Realization hash** (SEP-0006, SEP-0008): Hash of a concrete completed body or generated artifact.

**Refinement type** (SEP-0002): Type augmented with a predicate constraint.

**Outcome** (SEP-0002): First-class result type written as `A ! E`, representing success `A` or failure `E`.

## S

**Signature** (SEP-0001): The combination of Base Signature and optional Intent Signature.

**Surface** (SEP-0003): Finite, unordered effect requirement set used by `uses` and named by `surface` declarations.

**Signature hash** (SEP-0006, SEP-0008): Hash of the normalized Base Signature that participates in dependency tracking.

**`spawn`** (SEP-0007): Expression that creates a scoped `Task[T, E]`, requiring the `Spawn` effect.

**spore** (SEP-0006, SEP-0008): Project and package workflow CLI.

**sporec** (SEP-0006, SEP-0008): Low-level explicit-input compiler CLI.

**Startup contract** (SEP-0008): Platform-defined requirement on startup function parameters, return type, and effect boundary.

**Startup function** (SEP-0008): Callable inside the selected entry module that satisfies the Platform startup contract.

**Str** (SEP-0002): UTF-8 text primitive in Spore surface syntax.

**Struct** (SEP-0002): Product type with named fields, defined as `struct Name { field: T }`.

## T

**Task[T, E]** (SEP-0007): Typed future representing an asynchronous computation with success type `T` and await-time failure type `E`.

**Typed hole** (SEP-0005): See Hole.

## U

**uses clause** (SEP-0001, SEP-0003): Signature clause declaring an effect surface expression, written as `uses [Name1, Name2]` or `uses SurfaceName`.

## V

**Visibility** (SEP-0008): Access control on module exports: `pub`, `pub(pkg)`, or private.

## W

**Watch mode** (SEP-0006): Compiler mode that monitors source files and emits diagnostics and hole events on change.

## Process terms

**SEP** (SEP-0000): **Spore Evolution Proposal** (Spore 演进提案). A design document that records and reviews language, tooling, ecosystem, and governance changes across Spore's evolution.

**Discussion** (SEP-0000): Public thread where a pitch is debated before a formal SEP draft is proposed.

**Pitch** (SEP-0000): Public discussion-stage proposal that tests whether an idea is worth turning into a repository-backed SEP.
