# Independent relation declarations

This note synchronizes the Spore Spec source decision reviewed on 2026-11-15. It records the current target without changing historical SEP status or claiming bootstrap compiler support. The normative local sources are `spore-spec/spec/syntax.md` (G-relations) and `spore-spec/spec/semantics.md` (S-relation-completeness, S-orphan-relations and S-path-coherence).

## Decision

Use `impl` to declare a relation between existing types:

```text
impl A <: B;
impl A <: B { method render() -> Str { self.text } };
impl@<u>[T: Type@<u>] F[T] <: G[T];
impl B :> A;
```

The form without a body checks existing members, defaults and evidence. The body supplies missing implementations or proofs. Both forms require complete implementations, valid branch coverage and coherent paths; neither is an axiom. Completion cannot conflict with an existing implementation or silently add required storage to old values.

The current package must own at least one endpoint's outer nominal type constructor, after resolving aliases and normalizing direction. Imports, re-exports, transparent aliases and local type arguments inside foreign generic constructors do not transfer ownership. Passing this orphan rule does not bypass overlap or path-coherence checks.

`impl` distinguishes registration from use of a relation. Bounds such as `[T <: Base]`, propositions such as `(A <: B)` and family indices such as `case Nil <: Vec[A, zero]` retain their existing syntax. Membership completion `F: C { ... };` is unchanged. Reverse declarations remain supported as `impl B :> A;`.

## Application and verification boundary

CLI optional parameter types demonstrate the intended use: each role has a None / Some root, and its required type aliases Some. Explicit branch relations and a checked root relation give `Positional[T] <: OptionalPositional[T] <: Option[T]`, with the analogous named role. The parameter's declared role determines binding behavior; the two role families are unrelated and no generic covariance is assumed.

The local Spec grammar, conformance sources and highlighting consume the new keyword. Lab examples and source transport follow that syntax. Ownership, member completeness and path coherence remain separate static obligations; syntax acceptance does not verify them. The bootstrap compiler's `impl Trait for Type` remains a different implementation surface.
