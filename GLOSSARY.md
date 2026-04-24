# Spore Glossary

Unified terminology index for Spore. Each term links to the SEP where it is authoritatively defined.

## A

**Atomic effect** (SEP-0003): One of the 10 built-in intent-oriented atomic effects in Spore's effect system: Console, FileRead, FileWrite, NetConnect, NetListen, Env, Spawn, Clock, Random, Exit. In compiler/tooling contexts, these effect names form the checked effect set.

**`Add`** (SEP-0002): Compiler-known trait for the `+` operator, enabling operator overloading on user-defined types.

**`@allow`** (SEP-0004): Annotation that locally suppresses a cost budget violation, used as a second-tier escape for cost analysis.

**`@unbounded`** (SEP-0004): Annotation declaring that a function's cost is intentionally unanalyzed, opting out of cost verification entirely.

**`await`** (SEP-0007): Expression that blocks until a `Task[T]` completes and extracts its result value of type `T`.

## B

**Bidirectional inference** (SEP-0002): Type inference strategy combining synthesis (bottom-up, infer type from expression) and checking (top-down, verify expression against expected type).

## C

**Declared effects** (SEP-0003): The effect names explicitly written on a function, module, or manifest surface.

**Effect ceiling** (SEP-0003, SEP-0008): The maximum set of effects available to a scope. Function-level `uses [...]` clauses are standardized today; broader module/project ceilings remain reserved follow-up design space.

**Effect narrowing** (SEP-0003): Restricting the available effect set when entering a nested scope, ensuring inner code cannot exceed outer permissions.

**Effect set (EffectSet)** (SEP-0003): An unordered collection of effects associated with a function or scope, written as `uses [Effect1, Effect2]`.

**`Clone`** (SEP-0002): Compiler-known trait for explicitly duplicating a value.

**`Channel[T]`** (SEP-0007): Bounded channel type for inter-task message passing, parameterized by the message type.

**Content-addressed package** (SEP-0008): Package identified by SHA-256 hash of its normalized source, enabling reproducible builds and cache deduplication.

**Cost budget** (SEP-0004): The declared cost bound on a function, verified at compile time against inferred cost of the function body.

**Cost dimension** (SEP-0004): One of four orthogonal resource axes in a CostVector: compute, alloc, io, parallel.

**Cost expression (CostExpr)** (SEP-0004): Arithmetic expression over cost variables, restricted to `+`, `×`, `^const`, `log`, `max`, `min` to ensure decidability.

**CostVector** (SEP-0004): A 4-tuple `(compute(op), alloc(cell), io(call), parallel(lane))` representing multidimensional resource usage.

## D

**`Debug`** (SEP-0002): Compiler-known trait for programmer-facing string representation, used in diagnostics and logging.

**`Default`** (SEP-0002): Compiler-known trait providing a default value for a type.

**`Deserialize`** (SEP-0002): Compiler-known trait for converting serialized data back into a typed value.

**Derivable trait** (SEP-0002): A compiler-known trait whose implementation can be auto-generated from the type's structure, using the `deriving [...]` syntax.

**`Display`** (SEP-0002): Compiler-known trait for user-facing string representation.

**`Div`** (SEP-0002): Compiler-known trait for the `/` operator, enabling operator overloading on user-defined types.

**Diagnostic code** (SEP-0006): Structured error/warning identifier in the format `X0NNN`, where X is a category letter: E (type error), C (effect), K (cost), M (module), W (warning).

**Default entry** (SEP-0008): The manifest-selected entry used when project commands omit an explicit entry name.

## E

**Entry** (SEP-0008): A manifest-selected executable target within a project. An entry resolves to an entry module.

**Entry module** (SEP-0008): The source file and derived module selected by an entry, such as `src/main.sp` → `main`.

**`Eq`** (SEP-0002): Compiler-known trait for structural equality comparison.

**Effect** (SEP-0003): An observable interaction with the outside world (I/O, mutation, randomness), tracked via the effect system.

**Effect alias** (SEP-0003): A named shorthand for a set of atomic effects, written as `effect FileIO = FileRead | FileWrite`.

**Effect handler** (SEP-0008): Platform-provided implementation of an effect's operations, connecting `foreign fn` declarations to native code.

**Enum** (SEP-0002): Algebraic data type with named variants, each optionally carrying data. Defined with `type Name { Variant1(T), Variant2 }`.

## F

**`foreign fn`** (SEP-0008): Function declaration whose implementation is provided by the platform rather than written in Spore. Used for I/O bindings.

## G

**Generics** (SEP-0002): Parametric polymorphism using type variables, written as `fn f[T](x: T)` with optional `where` clause bounds.

## H

**`Hash`** (SEP-0002): Compiler-known trait for computing hash values, often required alongside `Eq` for use in hash-based collections.

**Hole** (SEP-0005): A typed placeholder in source code written as `?name`, representing incomplete code that carries type, effect, and cost context for agent-assisted completion.

**Hole context** (SEP-0005): The full type environment, effect set, cost budget, and dependency information associated with a typed hole.

**Hole Dependency Graph** (SEP-0005): DAG ordering typed holes by data-flow, type, effect, and cost dependencies for parallel fill scheduling.

**Hole state machine** (SEP-0005): Lifecycle of a hole: Open → Filling → Filled → Accepted.

## I

**Implementation hash (impl hash)** (SEP-0006): Content hash of a function's full body, used for incremental compilation — a change in impl hash triggers recompilation.

**Import resolution** (SEP-0008): The process of mapping `import pkg.module` declarations to concrete module files and verifying symbol visibility.

## L

**Lane** (SEP-0007): The parallel cost dimension — each `spawn` creates a new lane, tracked in CostVector's `parallel` field.

## M

**`Mul`** (SEP-0002): Compiler-known trait for the `*` operator, enabling operator overloading on user-defined types.

**Module** (SEP-0008): A single Spore source file that declares its own visibility boundaries and effect requirements.

## N

**NDJSON (Newline-Delimited JSON)** (SEP-0006): Output format for watch mode, where each compiler event is a single JSON object on one line, enabling streaming IDE integration.

**Nominal typing** (SEP-0002): Types are distinguished by name, not structure. Two structs with identical fields but different names are different types.

**`Never`** (SEP-0002): The bottom type — uninhabited, used as the return type of functions that never return (e.g., `exit()`).

## O

**`Ord`** (SEP-0002): Compiler-known trait for total ordering comparison, enabling `<`, `>`, `<=`, `>=` operators.

**`Option[T]`** (SEP-0009): Prelude type representing an optional value: `Some(T)` or `None`.

## P

**Platform** (SEP-0008): A package that provides effect handlers for a target environment (e.g., CLI, Web, Embedded). Each manifest-backed project binds exactly one Platform, and each selected entry module must satisfy its startup contract.

**Prelude** (SEP-0009): The set of types and functions available in every Spore module without explicit import.

## R

**Refinement type** (SEP-0002): Type augmented with a predicate constraint. Three tiers: L0 (decidable, compile-time), L1 (abstract interpretation), L2 (proof obligation).

**`Result[T, E]`** (SEP-0009): Prelude type representing success (`Ok(T)`) or failure (`Err(E)`).

## S

**`Serialize`** (SEP-0002): Compiler-known trait for converting a typed value into a serialized format.

**`select`** (SEP-0007): Expression that awaits the first of multiple tasks to complete, enabling concurrent race patterns.

**SEP (Spore Enhancement Proposal)** (SEP-0000): A design document proposing a change or addition to Spore, following a structured review process.

**Signature hash (sig hash)** (SEP-0006): Content hash of a function's public interface (name, params, return type, required effects), used for dependency tracking — a change in sig hash invalidates all callers.

**`spawn`** (SEP-0007): Expression that creates a new `Task[T]` for concurrent execution, requiring the `Spawn` effect.

**`Sub`** (SEP-0002): Compiler-known trait for the `-` operator, enabling operator overloading on user-defined types.

**Struct** (SEP-0002): Product type with named fields, defined as `struct Name { field1: T1, field2: T2 }`.

**spore** (SEP-0006, SEP-0008): The project/package workflow CLI. It owns `build`, `check`, `test`, `run`, `fmt`, `update`, and `upgrade`.

**sporec** (SEP-0006, SEP-0008): The low-level explicit-input compiler CLI. It owns `compile`, `holes`, `query-hole`, and `explain`.

**Structured concurrency** (SEP-0007): Concurrency model where all spawned tasks are scoped to their parent block, ensuring no task outlives its creator.

**Startup contract** (SEP-0008): The Platform-defined requirement on the startup function's parameters, return type, and effect boundary.

**Startup function** (SEP-0008): The callable inside the selected entry module that satisfies the Platform's startup contract. Today this is usually `main`.

## T

**`Task[T]`** (SEP-0007): Typed future representing an asynchronous computation that will produce a value of type `T`.

**Typed hole** (SEP-0005): See **Hole**.

## U

**`uses` clause** (SEP-0003): Annotation on a function or module declaring required effects, written as `uses [Effect1, Effect2]`.

## V

**Visibility** (SEP-0008): Access control on module exports: `pub` (public to all), `pub(pkg)` (package-internal), or private (default, module-only).

## W

**Watch mode** (SEP-0006): Compiler mode that continuously monitors source files and emits NDJSON events on changes, designed for IDE integration.

**`where` clause** (SEP-0002): Constraint block on generic functions specifying trait bounds, written as `where T: Eq + Hash`.

## Process terms

**Discussion** (SEP-0000): The canonical public thread where a pitch is debated before a
formal SEP draft is proposed.

**Pitch** (SEP-0000): A public discussion-stage proposal that tests whether an idea is
worth turning into a repository-backed SEP.
