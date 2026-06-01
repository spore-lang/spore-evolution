# State primitive effects specification draft

This artifact turns the primitive-effect decision into patch-ready text for
SEP-0003, SEP-0008, and SEP-0009. It does not edit the SEP files directly.

## Locked decision

The state primitive effect set is fixed to five semantic members:

- `Cell[T]`
- `Output[T]`
- `Map[K, V]`
- `Clock`
- `Random`

The draft freezes semantics, not final method spelling. Names such as `get`,
`set`, `emit`, `now`, `next_u64`, and `remove` are placeholders for the later
patch step.

The default Platform decision is P1: there is no default Platform. Primitive
interfaces live in the standard library surface, but handlers are supplied by an
explicitly selected Platform package or an explicit local handler.

## Why the split belongs in three SEPs

The split follows dependency direction:

```text
SEP-0003 effect taxonomy
    -> SEP-0008 Platform obligations
    -> SEP-0009 standard-library surface
```

- SEP-0003 owns the membership rule because it defines atomic effects,
  surfaces, handlers, and effect checking.
- SEP-0008 owns the Platform obligation because Platform packages provide
  runtime handlers and startup contracts.
- SEP-0009 owns the concrete standard-library surface because it lists standard
  modules, types, and effects available as stable APIs.

Putting all text in SEP-0009 would leave SEP-0003 without the taxonomy rule.
Putting all text in SEP-0003 would make the effect-system SEP own concrete
standard-library signatures. The three-way split keeps each SEP at its natural
contract boundary.

## Evidence from current text

| Document | Current evidence | Primitive-effect impact |
| --- | --- | --- |
| SEP-0003 | Every `uses` item resolves to an atomic effect or named surface at `seps/SEP-0003-effect-system.md:35-40`. | The primitive membership rule belongs to the atomic-effect taxonomy. |
| SEP-0003 | Handler checking requires implementing every operation of the discharged atomic effects at `seps/SEP-0003-effect-system.md:143-146`. | Primitive effects are just atomic effects with extra membership rules. |
| SEP-0003 | HoleReport exposes effect context at `seps/SEP-0003-effect-system.md:161-177`. | Primitive effects will appear in the same effect context projection. |
| SEP-0008 | Platform packages provide effect handlers and validate startup contracts at `seps/SEP-0008-module-package-system.md:52-60`. | Host and mock handlers belong to Platform package conformance. |
| SEP-0008 | A selected Platform declares runtime handlers and host adapter at `seps/SEP-0008-module-package-system.md:111-115`. | Add the primitive handler obligation near this contract. |
| SEP-0009 | Standard-library prelude excludes Platform-specific effects at `seps/SEP-0009-standard-library.md:133-137`. | Primitive effect interfaces can be standard while handlers remain Platform-provided. |
| SEP-0009 | Effects are shown through `@foreign` functions with `uses` at `seps/SEP-0009-standard-library.md:154-161`. | Add the primitive effect surface near this section. |
| SEP-0009 | Open question asks which Platform packages ship with stdlib at `seps/SEP-0009-standard-library.md:240-241`. | Primitive effects do not create a default Platform. |
| Sibling implementation | `Clock` and `Random` already appear in CLI and web Platform handled effects at `../spore/crates/sporec-typeck/src/platform.rs:46-56` and `../spore/crates/sporec-typeck/src/platform.rs:79-84`. | Implementation partially overlaps the chosen primitive set. |

## SEP-0003 patch draft

### Target

Add a subsection after `### Declaring effects` and before `### Using effects`.

### New subsection

```markdown
### State primitive effects

A state primitive effect is a standard atomic effect whose purpose is to carry a
minimal state or event boundary without exposing user-level mutation. State
primitive effects are still ordinary atomic effects for `uses` resolution,
handler checking, and HoleReport effect context.

An effect belongs to the state primitive set only when it satisfies all of these
membership rules:

1. It cannot be defined as a composition of other effects.
2. It carries one minimal state or event responsibility.
3. It is broadly useful across application, test, and tooling contexts.
4. A Platform package can provide a host handler and an in-memory mock handler.
5. Its operation set is small and stable enough to be part of the standard
   effect surface.

The initial state primitive set is defined by SEP-0009. Adding a new state
primitive effect requires a separate SEP because it changes the standard effect
taxonomy and the Platform conformance surface.
```

### Reference-level addition

Add this sentence to `### Surface resolution` near
`seps/SEP-0003-effect-system.md:132-139`:

```markdown
State primitive effects resolve as atomic effects. Their primitive status affects
standard-library and Platform obligations, not the surface-expansion algorithm.
```

## SEP-0008 patch draft

### Target

Add text to `### Platform startup contract` around
`seps/SEP-0008-module-package-system.md:111-115`.

### New paragraph

```markdown
A conforming Platform package that claims support for the standard state
primitive effect set provides two handler families for each supported primitive:
a host handler backed by the target environment and an in-memory mock handler
usable by tests and local handler scopes. This requirement does not create a
default Platform. Programs still select a Platform explicitly.
```

### Diagnostics addition

Add a diagnostic note near the `M050x` Platform diagnostics table:

```markdown
Missing required state primitive handlers are reported as Platform binding
violations, not as missing standard-library functions.
```

## SEP-0009 patch draft

### Target

Add a new section after `### Effects` around
`seps/SEP-0009-standard-library.md:154-161`.

### New section

````markdown
### State primitive effects

SEP-0003 defines membership rules for state primitive effects. The standard
library defines the initial primitive surface by semantic contract. Method names
below are placeholders until the final surface patch chooses exact spelling.

```spore
effect Cell[T] {
    fn get() -> T;
    fn set(value: T) -> ();
}

effect Output[T] {
    fn emit(value: T) -> ();
}

effect Map[K, V] {
    fn get(key: K) -> Option[V];
    fn put(key: K, value: V) -> ();
    fn remove(key: K) -> ();
}

effect Clock {
    fn now() -> Instant;
}

effect Random {
    fn next_u64() -> U64;
    fn next_f64() -> F64;
}
```

These effects are the standard state and event endpoints used by handler-local
mocking and test instrumentation. Their interfaces are standard-library surface;
their handlers are supplied by the selected Platform package or by explicit
local handlers.
````

### Prelude note

Add to `### Prelude` near `seps/SEP-0009-standard-library.md:133-137`:

```markdown
State primitive effect names are standard names, but their host handlers remain
Platform-provided. Importing the prelude does not implicitly select a Platform.
```

## Excluded candidates

The membership rules intentionally exclude common derived effects:

| Candidate | Exclusion reason |
| --- | --- |
| `Counter` | It is derivable from `Cell[I64]` plus helper functions, so it fails the non-composition rule. |
| `Cache[K, V]` | It is a policy-shaped key/value service derivable from map-like state plus eviction policy, so it is not a minimal primitive. |
| `Logger` | It is a behavior contract over `Output[LogEvent]` or `Output[Str]`, so it is not a minimal event endpoint. |
| `Tracer` | It is a domain-specific event stream over `Output[TraceEvent]`, so it is not primitive. |
| `Source[T]` | It is useful, but not needed for the selected D3 mock use cases. It can remain a normal standard-library or Platform effect until a later SEP proves primitive status. |
| `FileRead` / `FileWrite` | These are Platform I/O effects, not minimal state primitives. |
| `Spawn` / `Channel` | These are concurrency effects owned by SEP-0007. |

## Relationship to D3 handler state

D3 selects immutable handler fields and no user-level mutation. Stateful handler
use cases route through these primitives:

| Use case | Primitive effect route |
| --- | --- |
| Console capture | `Output[Str]` |
| Counter | `Cell[I64]` |
| Memo table | `Map[K, V]` |
| Time-dependent checks | `Clock` |
| Fuzzing or randomized tests | `Random` |

Handler fields remain runtime configuration and do not become mutable state.

## Implementation comparison notes

The sibling implementation already includes `Clock` and `Random` in built-in
Platform effect sets for CLI and web Platforms at
`../spore/crates/sporec-typeck/src/platform.rs:46-56` and
`../spore/crates/sporec-typeck/src/platform.rs:79-84`. It does not expose the
chosen `Cell`, `Output`, and `Map` primitive effects in the collected evidence.
That gap should become a follow-up item in `@cross-check-impl`, not a source
change in this design-only pass.

## Routing to the patch plan

`@sep-patch-plan` should include these concrete edits:

1. SEP-0003 adds the membership-rule subsection.
2. SEP-0003 states that primitive effects resolve as atomic effects.
3. SEP-0008 adds Platform host and mock handler obligations.
4. SEP-0008 adds Platform diagnostic wording for missing primitive handlers.
5. SEP-0009 adds the five-effect semantic interface table.
6. SEP-0009 adds a prelude note that primitive names do not select a Platform.
7. GLOSSARY adds `State primitive effect` and references SEP-0003/0009.
8. VISION adds a short sentence that state is explicit through effects rather
   than user-level mutation.
