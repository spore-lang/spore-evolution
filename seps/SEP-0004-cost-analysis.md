---
sep: 4
title: "SEP-0004: Cost Analysis & Decidability"
status: Draft
type: Standards Track
authors:
  - Spore maintainers
created: 2026-03-31
requires:
  - 2
  - 3
discussion: "https://github.com/spore-lang/spore-evolution/discussions/4"
pr: null
superseded_by: null
---

# SEP-0004: Cost Analysis & Decidability

> **Executive Summary**: Introduces 4-dimensional cost analysis with CostVector(compute, alloc, io, parallel), where cost expressions are restricted to a decidable grammar (+, ×, ^const, log, max, min). Provides a three-tier escape mechanism (@unbounded for opt-out, @allow for local override, advisory warnings for gradual adoption) and formal cost inference rules for higher-order function propagation. Targets O(n⁵) verification complexity.

## Summary

This SEP specifies Spore's compile-time cost analysis system — a three-tier mechanism that statically determines or verifies upper bounds on resource consumption for every function. The system operates along four cost dimensions — **compute(op)**, **alloc(cell)**, **io(call)**, **parallel(lane)** — and leverages the fact that Spore has **no loops** (all iteration is expressed via recursion and higher-order functions) to make cost analysis equivalent to recursion analysis.

> **Release-safety note**: This is a `Draft` design record, not the current
> implementation contract. Some examples below intentionally preserve older
> proposal syntax such as `cost ≤ expr` and `@unbounded`. For current release
> behavior and active cost syntax, start with the implementation repository's
> `spore/README.md`, which documents the four-slot
> `cost [compute, alloc, io, parallel]` form used by implementation-facing
> examples.

The three tiers are:

1. **Tier 1 — Automatic structural recursion detection** (~70% of functions): the compiler detects that one argument strictly decreases along a well-founded relation on every recursive call and automatically infers a cost bound.
2. **Tier 2 — Declarative verification** (~20%): the developer writes `cost ≤ expr` in the function signature; the compiler verifies it.
3. **Tier 3 — `@unbounded` escape hatch** (~10%): the developer explicitly opts out of cost checking; the annotation is *contagious* — callers inherit `@unbounded` unless they isolate it with `with_cost_limit`.

Cost expressions (`CostExpr`) are drawn from a restricted grammar — `+`, `*`, `^const`, `log`, `max`, `min` — deliberately excluding division, subtraction, and conditionals. This restriction guarantees that the verification problem "`C(n̄) ≤ B(n̄)` for all valid inputs" is **decidable in polynomial time**, specifically **O(n⁵)** where n is the combined AST size of the two expressions.

---

## Motivation

### The problem with runtime profiling

Traditional performance analysis relies on runtime profiling: run the program, measure timings, hope the workload is representative. This is machine-dependent, non-reproducible, and fundamentally reactive — you discover performance regressions *after* they ship.

### Why Spore can do better

Spore's language design creates a unique opportunity for compile-time cost analysis:

1. **No loops.** All iteration is expressed through recursion and higher-order functions (`map`, `fold`, `filter`). This means cost analysis reduces entirely to recursion analysis — there is no separate "loop analysis" pass.
2. **Algebraic data types.** The vast majority of recursive functions naturally follow the structure of their data (structural recursion), which is automatically detectable and provably terminating.
3. **Pure functions.** In the absence of side effects, a function's cost is determined entirely by its parameters, enabling symbolic cost propagation.
4. **Effect system.** The `uses [...]` declarations cross-validate with cost dimensions — a function declared `uses []` (pure) must have zero io(call) cost.

### Design goals

| Goal | Description |
|------|-------------|
| High coverage | ~90% of real-world recursive code gets a cost bound automatically or semi-automatically |
| Zero burden | Simple cases require no manual annotation |
| Escapable | Unanalyzable code does not block compilation — it produces a warning |
| Composable | Recursive cost and higher-order function cost compose seamlessly |
| Decidable | The verification algorithm always terminates in polynomial time |

### The core equation

```text
Compile-time cost analysis = Abstract Interpretation + Deterministic Cost Table
```

The compiler does not run real code. It walks the program on an abstract machine, accumulating deterministic cost at every step. The result is an exact value (for non-recursive functions) or a symbolic upper bound (for recursive functions).

---

## Guide-level explanation

This section explains how developers interact with the cost system in daily use.

### Automatic cost inference — you write nothing

For the vast majority of functions, the compiler infers cost automatically. You do not need to write any annotation:

```spore
fn factorial(n: Int) -> Int {
    match n {
        0 => 1,
        n => n * factorial(n - 1),
    }
}
```

The compiler detects structural recursion on `n` (decreasing by 1 on each call) and infers:

```text
✓ structural recursion detected: n decreases by 1 on each call
  cost = n × 4 op  (1[*] + 3[call overhead])
  → O(n)
```

Tree traversals work the same way:

```spore
fn tree_sum(tree: Tree<Int>) -> Int {
    match tree {
        Leaf(v) => v,
        Node(left, val, right) => tree_sum(left) + val + tree_sum(right),
    }
}
```

```text
✓ structural recursion detected: tree decreases to subtrees (binary)
  cost = nodes(tree) × 9 op
  → O(n)
```

### Declaring cost — `cost ≤ expr`

When the compiler cannot automatically detect structural recursion but you know the cost is bounded, declare it:

```spore
fn merge_sort[T](list: List[T]) -> List[T]
    where T: Ord
    decreases len(list)
    cost ≤ len(list) * log(len(list)) * 5 + len(list)
{
    match list {
        [] => [],
        [x] => [x],
        _ => {
            (left, right) = split_at(list, len(list) / 2)
            merge(merge_sort(left), merge_sort(right))
        },
    }
}
```

The compiler verifies the declared bound against the inferred cost using abstract interpretation and the asymptotic comparison algorithm defined in the reference section. The optional `decreases` clause provides a termination measure when the compiler needs help.

### Escaping — `@unbounded`

Some functions have costs that are mathematically unknown or unprovable (e.g., the Collatz conjecture). Mark them explicitly:

```spore
@unbounded
fn collatz_steps(n: Int) -> Int {
    match n {
        1 => 0,
        n if n % 2 == 0 => 1 + collatz_steps(n / 2),
        n => 1 + collatz_steps(3 * n + 1),
    }
}
```

`@unbounded` functions cannot be called directly from `cost ≤ K` functions. To bridge the boundary, use a runtime cost limiter:

```spore
fn safe_collatz(n: Int) -> Int ! CostExceeded
    cost ≤ 10000
{
    with_cost_limit(10000) {
        collatz_steps(n)
    }
}
```

### Querying cost

```bash
$ sporec --query-cost merge_sort
{
  "function": "merge_sort",
  "cost_symbolic": "n * log(n) * 5 + n",
  "cost_declared": "≤ n * log(n) * 5 + n",
  "dimensions": {
    "compute": "n * log(n) * 4 + n",
    "alloc": "n * log(n)",
    "io": "0",
    "parallel": "1"
  },
  "status": "verified"
}
```

### Summary of the three tiers

```text
          Coverage
  ┌────────────────────────────────────────────┐
  │  Tier 1: Structural recursion       ~70%   │  ← Fully automatic
  ├────────────────────────────────────────────┤
  │  Tier 2: cost ≤ expr declaration    ~20%   │  ← Developer writes bound, compiler verifies
  ├────────────────────────────────────────────┤
  │  Tier 3: @unbounded escape          ~10%   │  ← Explicit opt-out
  └────────────────────────────────────────────┘
```

Design principle: **What can be inferred automatically shall never require manual annotation. What cannot be inferred shall never block compilation.**

---

## Reference-level explanation

### 4.1 Cost dimensions

The abstract machine maintains four independent cost dimensions:

| Dimension | Abbreviation | Meaning | Unit |
|-----------|-------------|---------|------|
| Compute | `C` | CPU operation steps | op (operation) |
| Allocation | `A` | Heap memory allocation | cell (abstract memory unit) |
| I/O | `W` | Side-effect / external call count | call |
| Parallelism | `P` | Parallel execution width | lane |

**Scalar reduction**: for signature-level `cost ≤ K`, dimensions are folded into a single scalar:

```text
cost = C × 1 + A × α + W × β
```

where `α` and `β` are project-configurable weights (default α = 2, β = 100). The `P` dimension is reported independently for resource planning and does not participate in the default scalar sum.

> **Note on P dimension.** The default scalar formula excludes `P` because parallel lane count represents a resource-width metric rather than a cost-per-invocation metric. However, projects that need to account for parallelism in the scalar may define a custom weight scheme in `spore.toml` that includes a `γ` weight for P: `cost = C×1 + A×α + W×β + P×γ`. This is an opt-in extension; the default remains `γ = 0` (P excluded).

### 4.2 Primitive cost table

#### Compute (C dimension)

| Operation | Cost (op) | Notes |
|-----------|----------|-------|
| Integer `+`, `-`, `*` | 1 | |
| Integer `/`, `%` | 2 | Division is slightly more expensive |
| Float `+`, `-`, `*` | 2 | |
| Float `/` | 3 | |
| Comparison `==`, `!=`, `<`, `>` | 1 | |
| Logical `&&`, `\|\|`, `!` | 1 | Max-path (short-circuit does not reduce cost) |
| Bitwise `&`, `\|`, `^`, `<<`, `>>` | 1 | |
| Variable read | 0 | Already in scope |
| `let` binding | 1 | |
| Pattern arm | 1 | Per arm matched |
| Function call overhead | 3 | Fixed, excludes callee body |
| Closure creation (N captures) | N + 2 | |
| Pipe `\|>` | 0 | Syntactic sugar |

#### Allocation (A dimension)

| Operation | Cost (cell) |
|-----------|------------|
| Struct creation | field count |
| List creation | element count + 1 header |
| String creation | ⌈len / 8⌉ |
| String concatenation | ⌈(len_a + len_b) / 8⌉ (new allocation) |
| Enum / union | 1 (tag + max variant size) |
| Deep copy | original cell count |
| Borrow / reference | 0 |

#### I/O (W dimension)

Every system call (file read/write, network request, stdio, random number generation, clock read, mutable state access) costs 1 call.

### 4.3 Composition rules

| Form | Cost rule |
|------|-----------|
| Sequential `A; B` | `cost(A) + cost(B)` |
| Conditional `if c then A else B` | `cost(c) + max(cost(A), cost(B))` |
| Pattern match `match x { p₁ => A, p₂ => B, ... }` | `cost(x) + max(cost(A), cost(B), ...) + arms × 1` |
| Function call `f(args)` | `Σ cost(argᵢ) + 3 + cost(f.body)` |
| Pipe chain `x \|> f \|> g` | `cost(x) + cost(f) + cost(g)` |
| Parallel `parallel { A, B }` | C, A, W: `max(cost(A), cost(B)) + sync_overhead`; P: `sum(P(A), P(B))` |

> **Concurrent sync overhead.** The `sync_overhead` is a configurable constant (default: 0) representing the synchronisation cost of joining parallel branches. It can be set in `spore.toml` as `[cost] sync_overhead = 10`. When set to 0 (the default), the parallel cost reduces to a simple `max`. Projects requiring precise modelling of fork/join overhead should configure this parameter.

### Formal cost judgments

**Notation:**

- `K(e)` — cost of expression e as a CostVector
- `⊕` — pointwise CostVector addition
- `⊗` — CostVector scaling
- `≤` — pointwise CostVector comparison (each dimension ≤)

**Cost inference rules:**

```text
[Cost-Literal]
  K(literal) = (0, 0, 0, 0)

[Cost-Var]
  K(x) = (0, 0, 0, 0)

[Cost-BinOp]
  K(a op b) = K(a) ⊕ K(b) ⊕ (1, 0, 0, 0)

[Cost-Alloc]
  K(S { ... }) = K(field_exprs) ⊕ (0, 1, 0, 0)

[Cost-App]
  f has declared cost C_f(args)
  K(f(args)) = K(args) ⊕ C_f(args)

[Cost-If]
  K(if c { t } else { e }) = K(c) ⊕ max(K(t), K(e))

[Cost-Match]
  K(match s { pᵢ => eᵢ }) = K(s) ⊕ max(K(e₁), ..., K(eₙ))

[Cost-Let]
  K(let x = e₁; e₂) = K(e₁) ⊕ K(e₂)

[Cost-Spawn]
  K(spawn e) = (1, 1, 0, 1) ⊕ K(e) projected onto parallel dimension
  (parallel dimension tracks spawned lanes)

[Cost-HOF-Map]
  K(map(f, xs)) = |xs| ⊗ K_body(f) ⊕ (0, |xs|, 0, 0)

[Cost-HOF-Fold]
  K(fold(f, init, xs)) = |xs| ⊗ K_body(f)

[Cost-HOF-Filter]
  K(filter(p, xs)) = |xs| ⊗ K_body(p) ⊕ (0, |xs|, 0, 0)
```

**Verification judgment:**

```text
[Cost-Verify]
  fn f(x₁: T₁, ..., xₙ: Tₙ) -> R cost C_declared
  K_inferred = infer_cost(body)
  K_inferred ≤ C_declared  (pointwise, asymptotically)
  ─────────────────────────────────────────────────────
  f is cost-valid

[Cost-Unbounded]
  fn f(...) -> R cost @unbounded
  ─────────────────────────────────────────────────────
  f is cost-valid  (trivially, no verification needed)

[Cost-Propagation]
  fn f(...) -> R cost C_f
  fn g(...) -> R' = ... f(args) ...
  g has no cost annotation
  ─────────────────────────────────────────────────────
  inferred cost of g includes C_f(args) at each call site
```

**Decidability of cost comparison:**

The cost expression language is intentionally restricted to ensure decidability:

- Allowed operations: `+`, `×`, `^c` (constant exponent), `log`, `max`, `min`
- Disallowed: arbitrary exponentiation, division, subtraction
- Comparison `C₁ ≤ C₂` is decidable for this restricted grammar via:
  1. Normalize both expressions to canonical form
  2. Apply asymptotic dominance rules (e.g., `n² + n ≤ n²` simplifies to `n ≤ 0` for large n)
  3. Verify each CostVector dimension independently

### 4.4 CostExpr grammar

The cost expression language is deliberately restricted to maintain decidability.

#### BNF definition

```bnf
CostExpr ::= Literal                              (* Positive integer constant *)
           | Var                                   (* Variable from parameter size *)
           | CostExpr '+' CostExpr                 (* Addition *)
           | CostExpr '*' CostExpr                 (* Multiplication *)
           | CostExpr '^' Literal                  (* Power — exponent must be constant *)
           | 'log' '(' CostExpr ')'                (* Logarithm — base 2, ceiling *)
           | 'max' '(' CostExpr ',' CostExpr ')'   (* Maximum *)
           | 'min' '(' CostExpr ',' CostExpr ')'   (* Minimum *)

Literal  ::= [1-9][0-9]*                           (* Positive integer, no zero *)
Var      ::= [a-z][a-z0-9_]*                       (* Lowercase identifier *)
```

#### Explicitly forbidden constructs

| Construct | Reason |
|-----------|--------|
| Division `/` | Avoids division-by-zero and rational expressions; keeps expressions closed over ℕ⁺ |
| Subtraction `-` | Cost is always non-negative; subtraction may produce negative values, breaking monotonicity |
| Conditionals `if...then...else` | Introduces undecidable branching — conditionals can encode arbitrary predicates |
| Recursive cost definitions | Avoids fixpoint computation; recursion analysis is handled at a separate layer |
| Negative numbers | Cost domain is ℕ (non-negative integers) |
| Variable exponents `n^m` | Pushes comparison into the exponential polynomial domain, losing polynomial decidability |

> **Note on subtraction discrepancy.** The cost-model spec (§6) includes subtraction in its symbolic cost operators (e.g., `(len(list) - 1) × cost(f)` for `reduce`). However, the decidability analysis forbids subtraction in CostExpr to maintain monotonicity and non-negativity. This SEP follows the decidability spec: **subtraction is not a valid CostExpr operator**. Where subtraction appears naturally (e.g., `n - 1`), the compiler uses the conservative upper bound (e.g., `n` instead of `n - 1`). Cost formulas in the HOF table that use subtraction (e.g., `reduce`) are computed internally by the compiler but are presented to the CostExpr verifier in their upper-bound form.

#### Implementation (Rust)

The `CostExpr` type is implemented in `spore-typeck/src/cost.rs`:

```rust
pub enum CostExpr {
    Const(u64),
    Var(String),
    Add(Box<CostExpr>, Box<CostExpr>),
    Mul(Box<CostExpr>, Box<CostExpr>),
    Pow(Box<CostExpr>, u32),    // exponent is a constant
    Log(Box<CostExpr>),
    Max(Box<CostExpr>, Box<CostExpr>),
    Min(Box<CostExpr>, Box<CostExpr>),
}
```

### 4.5 Semantics

CostExpr evaluates over **ℕ⁺ = {1, 2, 3, ...}** (positive natural numbers).

Let σ: Var → ℕ⁺ be an assignment environment. The semantic function ⟦·⟧: CostExpr → (Var → ℕ⁺) → ℕ⁺ is defined as:

```text
⟦ c ⟧σ           = c                              (c ∈ ℕ⁺)
⟦ x ⟧σ           = σ(x)                           (x ∈ Var)
⟦ e₁ + e₂ ⟧σ    = ⟦e₁⟧σ + ⟦e₂⟧σ
⟦ e₁ * e₂ ⟧σ    = ⟦e₁⟧σ × ⟦e₂⟧σ
⟦ e ^ k ⟧σ      = (⟦e⟧σ)ᵏ                        (k ∈ ℕ⁺)
⟦ log(e) ⟧σ     = max(⌈log₂(⟦e⟧σ)⌉, 1)          (min value 1 to avoid ×0)
⟦ max(e₁,e₂) ⟧σ = max(⟦e₁⟧σ, ⟦e₂⟧σ)
⟦ min(e₁,e₂) ⟧σ = min(⟦e₁⟧σ, ⟦e₂⟧σ)
```

> **Convention**: `log` always means `log₂` (binary logarithm), following standard computer science convention.

**Theorem 4.1 (Monotonicity).** For any CostExpr `e`, if σ₁(x) ≤ σ₂(x) for all variables x, then ⟦e⟧σ₁ ≤ ⟦e⟧σ₂.

*Proof.* By structural induction on `e`. All operations (`+`, `×`, `(·)ᵏ`, `⌈log₂(·)⌉`, `max`, `min`) are monotone non-decreasing on ℕ⁺. ∎

Monotonicity guarantees: **if the inequality holds for "sufficiently large" inputs, it holds for all inputs** (after adjusting constants). This is the theoretical foundation of the asymptotic comparison algorithm.

### 4.6 Three-tier analysis

#### Tier 1: Structural recursion auto-detection

**Definition.** A function f(x₁, ..., xₙ) is *structurally recursive* if there exists i ∈ {1, ..., n} such that for every recursive call f(y₁, ..., yₙ):

```text
yᵢ ≺ xᵢ   (where ≺ is a well-founded relation on type Tᵢ)
```

The compiler recognizes the following decreasing patterns:

| Pattern | Source → Recursive arg | Well-founded relation | Typical cost |
|---------|----------------------|----------------------|-------------|
| Natural number decrement | `n → n - 1` (with `n > 0` guard) | `<` on ℕ | O(n) |
| List tail | `list → list.tail` | Sublist relation | O(n) |
| Tree child (unary) | `tree → tree.left` or `tree → tree.right` | Subtree relation | O(log n) balanced / O(n) worst |
| Tree child (binary) | `tree → tree.left` and `tree → tree.right` | Subtree relation | O(n) |
| Enum destructuring | `match x { Variant(inner) => f(inner) }` | Structural subterm | O(depth) |
| Tuple projection | `(a, b) → a` or `(a, b) → b` (strictly smaller) | Structural subterm | Depends on projected component |
| Integer halving | `n → n / 2` (with `n > 0` guard) | `<` on ℕ | O(log n) |

**Detection algorithm** (implemented in `spore-typeck/src/cost.rs`):

```text
algorithm detect_structural_recursion(f):
    1. Extract all recursive call sites {call₁, call₂, ..., callₖ}
    2. For each callⱼ:
        a. Classify each argument as Same(param), Decreasing, or Other
        b. Check if yᵢ ≺ xᵢ holds (via syntactic pattern matching)
    3. If ALL recursive calls have at least one parameter
       strictly decreasing in ALL paths:
        → f is structurally recursive
        → Derive cost bound from the decreasing pattern
    4. Otherwise:
        → Proceed to Tier 2 or Tier 3
```

Detection complexity: O(|call_graph|), performed during type checking.

**Cost derivation rules:**

- Linear recursion (single recursive call, decrement by constant): `cost(f, n) = n × cost_per_step → O(n)`
- Halving recursion (single recursive call, argument halved): `cost(f, n) = log(n) × cost_per_step → O(log n)`
- Binary tree recursion (two calls on subtrees): `cost(f, tree) = nodes(tree) × cost_per_step → O(n)`
- Binary exponential recursion (e.g., `f(n-1) + f(n-2)`): `cost(f, n) = 2ⁿ × cost_per_step` — compiler emits a warning suggesting memoization or tail recursion

where `cost_per_step` is the four-dimensional cost of the function body excluding recursive calls, computed from the primitive cost table.

#### Tier 2: Declarative verification

When the compiler cannot auto-detect structural recursion but the developer knows the function terminates with a bounded cost, they declare it:

```spore
fn gcd(a: Int, b: Int) -> Int
    decreases a + b
    cost ≤ log(max(a, b))
{
    match b {
        0 => a,
        _ => gcd(b, a % b),
    }
}
```

**Verification method.** The compiler attempts verification in priority order:

1. **Call-tree induction**: If `cost(recursive_call) < cost(current_call)` and the base case cost is bounded, the bound holds. Formally, given declared bound B(x) and recursive call with argument x':

   ```text
   Verify: cost_body(x) + B(x') ≤ B(x)
   ```

   where `cost_body(x)` is the cost of the function body excluding recursive calls, and `B(x')` is the bound applied to the recursive call's arguments (inductive hypothesis).

2. **Monotonicity analysis**: If the bound expression is monotonically decreasing in the decreasing parameter and the base case satisfies the bound.

3. **Arithmetic verification**: Unfold the recursion k steps, substitute parameter values, verify `cost(unfolded) ≤ expr(original_params)`.

**Verification failure** produces a **warning** (not an error) — the program still compiles. This ensures gradual adoption.

```text
WARNING [unverified-cost-bound] gcd's cost bound cannot be automatically verified.
  Declared: cost ≤ log(max(a, b))
  Reason: compiler cannot prove log(max(b, a % b)) < log(max(a, b))

  Options:
  (a) Provide a `decreases` clause to help the compiler
  (b) Mark as @unbounded
  (c) Add @trust_cost to suppress this warning if you are confident
```

#### Tier 3: @unbounded escape

**Syntax:**

```spore
@unbounded
fn collatz_steps(n: Int) -> Int {
    match n {
        1 => 0,
        n if n % 2 == 0 => 1 + collatz_steps(n / 2),
        n => 1 + collatz_steps(3 * n + 1),
    }
}
```

**Rules:**

| Rule | Description |
|------|-------------|
| Warning, not error | `@unbounded` produces a compiler warning, does not block compilation |
| Contagious | Calling an `@unbounded` function makes the caller `@unbounded` too (unless wrapped in `with_cost_limit`) |
| Context restriction | `@unbounded` functions cannot be called directly in `cost ≤ K` contexts |
| Hole interaction | Holes inside `@unbounded` functions report `cost_budget: unbounded` |

**Impact scope tracking.** When a function is marked `@unbounded`, its unbounded status propagates through the call chain:

- **Direct callers**: any function that calls an `@unbounded` function becomes `@unbounded` itself (unless the call is wrapped in `with_cost_limit`).
- **Indirect callers**: if function A is `@unbounded` and B calls A, then B is also `@unbounded`. If C calls B, C is also `@unbounded`, and so on up the call chain.
- **Isolation**: wrapping an `@unbounded` call in `with_cost_limit` halts the propagation. The wrapping function can declare `cost ≤ K` normally.

The compiler tracks this propagation and reports the full impact scope in its diagnostic:

```text
WARNING [unbounded-function] collatz_steps is marked @unbounded.
  Impact scope:
    → analyze (direct caller)
    → run_batch (calls analyze)
    → main (calls run_batch)
  Suggestion: wrap with `with_cost_limit` in `analyze` to contain the propagation.
```

### 4.7 Higher-order function cost formulas

Since Spore has no loops, higher-order functions are the *only* iteration mechanism besides recursion. The standard library has built-in cost formulas:

| Function | Cost formula |
|----------|-------------|
| `map(list, f)` | `len(list) × cost(f) + len(list)` |
| `fold(list, init, f)` | `len(list) × cost(f)` |
| `filter(list, pred)` | `len(list) × cost(pred) + len(list)` |
| `flat_map(list, f)` | `len(list) × cost(f) + total_output_len` |
| `zip(a, b)` | `min(len(a), len(b))` |
| `take(list, n)` | `n` |
| `reduce(list, f)` | `(len(list) - 1) × cost(f)` |

Since higher-order function arguments `f` in Spore must be pure (no effect variables), `cost(f)` is always statically determinable. Substituting `cost(f)` into the formula yields a valid CostExpr.

#### Nested higher-order function derivation example

The following example demonstrates step-by-step cost derivation for nested higher-order functions:

```spore
fn matrix_sum(matrix: List[List[Int]]) -> Int {
    matrix
        |> map(|row| row |> fold(0, |a, b| a + b))
        |> fold(0, |a, b| a + b)
}
```

**Six-step derivation** (let `m = len(matrix)`, `n = len(row)` for a typical row):

```text
Step 1: inner closure cost
  cost(|a, b| a + b) = 1 op                           // single addition

Step 2: inner fold cost
  cost(fold(row, 0, |a, b| a + b)) = n × cost(+) = n × 1 = n

Step 3: map step cost (applying inner fold to each row)
  map_step_cost = cost(inner_fold) = n

Step 4: outer map cost
  cost(map(matrix, inner_fold)) = m × map_step_cost + m
                                = m × n + m

Step 5: outer fold cost
  cost(fold(mapped, 0, |a, b| a + b)) = m × 1 = m

Step 6: total cost
  total = cost(outer_map) + cost(outer_fold)
        = (m × n + m) + m
        = m × n + 2 × m
        → O(m × n)
```

### 4.8 Mutual recursion

Detected via **strongly connected components** (SCC) of the call graph (Tarjan's algorithm, O(V + E)):

```spore
fn is_even(n: Int) -> Bool {
    match n {
        0 => true,
        n => is_odd(n - 1),
    }
}

fn is_odd(n: Int) -> Bool {
    match n {
        0 => false,
        n => is_even(n - 1),
    }
}
```

Analysis: SCC = {is_even, is_odd}. Combined call pattern: `is_even(n) → is_odd(n-1) → is_even(n-2) → ...`. Parameter n decreases by 2 every two calls → structural recursion, cost = O(n).

| Scenario | Handling |
|----------|----------|
| SCC satisfies structural recursion | Automatic cost derivation |
| SCC does not satisfy structural recursion | All functions in SCC need `cost ≤` or `@unbounded` |
| Any function in SCC is `@unbounded` | Entire SCC treated as `@unbounded` |

### 4.9 Decidability proof sketch

**Verification problem.** Given inferred cost C(n̄) and declared bound B(n̄) as CostExprs, and variable set V = {n₁, ..., nₖ}, determine: does there exist N₀ ∈ ℕ⁺ such that for all n̄ ∈ (ℕ⁺)ᵏ with nᵢ ≥ N₀, we have ⟦C⟧σ_n̄ ≤ ⟦B⟧σ_n̄?

**Step 1: max/min lifting.** Lift max/min to the top level using distribution rules:

```text
e₁ + max(e₂, e₃) → max(e₁ + e₂, e₁ + e₃)
e₁ * max(e₂, e₃) → max(e₁ * e₂, e₁ * e₃)    (valid since e₁ ≥ 1 on ℕ⁺)
```

With nesting depth d bounded by a constant (default ≤ 8), this produces at most 2^d = O(1) sub-expression pairs, each of size O(n).

Verification rules for max/min at the top level:

| Form | Rule | Condition |
|------|------|-----------|
| `max(A, B) ≤ C` | Verify A ≤ C **and** B ≤ C | Necessary and sufficient |
| `min(A, B) ≤ C` | Verify A ≤ C **or** B ≤ C | Sufficient (conservative) |
| `C ≤ max(A, B)` | Verify C ≤ A **or** C ≤ B | Sufficient (conservative) |
| `C ≤ min(A, B)` | Verify C ≤ A **and** C ≤ B | Necessary and sufficient |

**Step 2: Normal form conversion.** A *poly-log monomial* has the form:

```text
t = c × n₁^a₁ × ... × nₖ^aₖ × log(n₁)^b₁ × ... × log(nₖ)^bₖ
```

where c ∈ ℕ⁺, aᵢ ∈ ℕ, bᵢ ∈ ℕ. We write this as the triple **(c, ā, b̄)**.

The *normal form* of a CostExpr is a finite sum of poly-log monomials. Conversion algorithm NF:

```text
NF(c)           = {(c, 0̄, 0̄)}
NF(nᵢ)         = {(1, eᵢ, 0̄)}                              (eᵢ = i-th unit vector)
NF(e₁ + e₂)    = NF(e₁) ∪ NF(e₂)
NF(e₁ * e₂)    = {(c₁c₂, ā₁+ā₂, b̄₁+b̄₂) |
                   (c₁,ā₁,b̄₁) ∈ NF(e₁), (c₂,ā₂,b̄₂) ∈ NF(e₂)}
NF(e ^ k)       = NF(e ×ᵏ e)                                  (expand to k multiplications)
NF(log(nᵢ))    = {(1, 0̄, eᵢ)}
```

Logarithm simplification (asymptotically equivalent):

```text
log(e₁ * e₂) ≈ log(e₁) + log(e₂)
log(e ^ k)   ≈ k × log(e)
log(e₁ + e₂) ≈ log(max(e₁, e₂))
log(c)       = ⌈log₂(c)⌉
```

After conversion, merge like terms: monomials with the same (ā, b̄) have their coefficients summed.

**Step 3: Asymptotic dominance check.**

**Definition 4.2 (Asymptotic dominance).** Monomial t₁ = (c₁, ā₁, b̄₁) is *dominated* by t₂ = (c₂, ā₂, b̄₂), written t₁ ≼ t₂, iff:

```text
t₁ ≼ t₂  ⟺  ā₁ < ā₂  (componentwise ≤ and ≠)
           ∨  (ā₁ = ā₂ ∧ b̄₁ < b̄₂)
           ∨  (ā₁ = ā₂ ∧ b̄₁ = b̄₂ ∧ c₁ ≤ c₂)
```

**Algorithm COMPARE(NF(C), NF(B)):**

```text
1. Merge like terms in NF(C) and NF(B)
2. For each monomial sⱼ in NF(C):
     Find the highest-growth matching term tₖ in NF(B) such that sⱼ ≼ tₖ
     "Absorption" rules:
       a. If sⱼ's (ā, b̄) is strictly less than some tₖ's (ā, b̄),
          then sⱼ is asymptotically dominated (regardless of coefficients)
       b. If sⱼ's (ā, b̄) equals some tₖ's (ā, b̄), check coefficient cⱼ ≤ cₖ
3. If all sⱼ are absorbed → return PASS
4. Otherwise → return FAIL
```

**Step 4: Small-input enumeration.** For inputs n̄ < N₀ (where N₀ is computed from the dominance analysis, typically ≤ 100), the compiler enumerates all values and checks C(n̄) ≤ B(n̄) directly. Enumeration space is N₀ᵏ, feasible for k ≤ 5.

### 4.10 Verification complexity

**Theorem 4.2 (Polynomial-time decidability).** The asymptotic comparison of CostExprs is decidable in O(n⁵) time, where n = |C| + |B|.

*Proof.* Let n = |C| + |B| (total AST nodes) and k = |V| (variable count).

1. **max/min lifting**: O(n) with d bounded by a constant.
2. **Normal form conversion**: Multiplication distributes monomials (Cartesian product). An expression of size n yields at most O(n²) monomials. Logarithm simplification: O(n) substitutions. Like-term merging: sort in O(n² log n).
   - Subtotal: O(n² log n)
3. **Dominance check**: NF(C) has p ≤ O(n²) monomials, NF(B) has q ≤ O(n²) monomials. Comparing one pair: O(k) (componentwise vector comparison).
   - Subtotal: O(p × q × k) = O(n⁴ × k)
4. **Total**: O(n² log n) + O(n⁴ × k). Since k ≤ n, total is **O(n⁵)**.

This is in **P** (polynomial-time complexity class). ∎

### 4.11 Soundness

**Theorem 4.3 (Soundness).** If the algorithm outputs PASS, then there exists N₀ ∈ ℕ⁺ such that for all n̄ ∈ (ℕ⁺)ᵏ with min(n̄) ≥ N₀, we have C(n̄) ≤ B(n̄).

*Proof sketch.*

1. Normal form conversion preserves asymptotic equivalence (logarithm simplifications introduce only constant-factor errors).
2. If every monomial in NF(C) is dominated by some monomial in NF(B):
   - When dominance is strict (polynomial exponent strictly less), there exists N₁ beyond which the higher-order term covers the lower-order one.
   - When dominance is exact (exponents equal, coefficient ≤), the inequality holds for all inputs.
3. Take N₀ = max(all per-pair Nᵢ). ∎

**Conservatism.** The algorithm may return FAIL when the inequality actually holds (e.g., due to cancellation effects between terms). Mitigation:

1. Sum unabsorbed terms from NF(C) and check if the aggregate is dominated by the leading term of NF(B).
2. If still failing, attempt numerical sampling at several large values.

These fallback steps only convert FAIL → PASS, never the reverse.

### 4.12 Four-dimensional verification

Four-dimensional cost declarations are verified **independently per dimension**:

```spore
fn sort[T](items: List[T, max: n]) -> List[T, max: n]
    where T: Ord
    cost ≤ {compute: n * log(n) * 3, alloc: n, io: 0, parallel: 1}
```

This is equivalent to four independent verification problems, each using the same asymptotic comparison algorithm.

When using scalar `cost ≤ K`, the compiler first computes symbolic cost per dimension, then forms the scalar expression `C(n̄) + α × A(n̄) + β × W(n̄)`. Since α and β are constants, the result is still a valid CostExpr.

### 4.13 Interaction with the Hole system

Partially-defined functions participate in cost analysis:

```spore
fn process(data: Data) -> Result ! ProcessError
    cost ≤ 1000
{
    parsed = parser.parse(data)     // cost: 600
    ?process_logic                  // hole: remaining budget 400
}
```

The HoleReport includes the remaining cost budget, providing the AI agent (or developer) with a precise performance constraint:

```json
{
  "hole": "process_logic",
  "cost_consumed": 600,
  "cost_budget_remaining": 400,
  "note": "Implementation cost must not exceed 400 op"
}
```

For holes inside recursive functions, the per-iteration budget is `total_budget / iterations - recursive_overhead`.

### 4.14 Compile-time cost analysis pipeline

The full cost analysis pipeline executes as part of the compilation process:

```text
Source Code
  ↓
[1] Parse to AST
  ↓
[2] Type Check + Effect Check
  ↓
[3] Abstract Interpretation (Cost Inference)
    ├── Build control flow graph (CFG)
    ├── Compute cost per basic block (from primitive cost table)
    ├── Take max across branches
    ├── Analyse recursion / iteration upper bounds
    └── Generate symbolic CostExpr per function
  ↓
[4] Cost Verification
    ├── Compare inferred CostExpr against declared `cost ≤ expr`
    ├── PASS → compilation succeeds
    ├── FAIL → compile error with four-dimensional breakdown
    └── UNKNOWN → warning with suggestions
  ↓
[5] Cost metadata written to compilation output (JSON / binary)
```

### 4.15 Bounded type semantics

Bounded types provide compile-time size information for cost verification:

```spore
fn process_batch(items: List[Order, max: 500]) -> BatchResult ! TooLarge
    cost ≤ 25000
{
    items |> map(|order| validate(order)) |> fold(BatchResult.empty(), merge)
}
```

`List[Order, max: 500]` means:

1. **Compile-time**: the compiler uses 500 as the upper bound for `len(items)` in cost verification. It substitutes `n = 500` into the symbolic cost expression to verify `cost ≤ 25000`.
2. **Runtime**: if a list exceeding 500 elements is passed, the call produces a `TooLarge` error at the call site. The function body itself never sees more than 500 elements.
3. **Error propagation**: the `TooLarge` error must appear in the function's error set (`! TooLarge`) or in the caller's error handling.

When no `max` constraint is present, the cost remains a symbolic expression in terms of `len(items)`.

### 4.16 FFI extern function cost declarations

Foreign functions have no Spore body for the compiler to analyse. They **must** declare their cost explicitly at the binding site:

```spore
extern fn c_sort[T](data: List[T]) -> List[T]
    cost ≤ n * log(n)    // declared, not computed; n = len(data)
```

```spore
extern fn openssl_encrypt(data: Bytes, key: Key) -> Bytes ! CryptoError
    cost ≤ len(data) * 3 + 500
```

**Rules for extern fn cost:**

| Rule | Description |
|------|-------------|
| Required declaration | `extern fn` without a `cost` clause is treated as `@unbounded` |
| No body analysis | The compiler trusts the declared cost — no verification is possible |
| Contagious unbounded | An `@unbounded` extern fn follows the same contagion rules as any `@unbounded` function |
| Variable binding | Cost variables (`n`, `len(data)`) bind to parameter sizes at the call site |

This ensures FFI boundaries maintain cost transparency — external code cannot silently introduce cost black holes.

### 4.17 Polymorphic function cost resolution

For generic functions like `map(f, list)`, cost depends on the concrete function `f`. Spore resolves this at the **call site**:

```spore
fn map[T, U](list: List[T], f: (T) -> U) -> List[U]
    cost ≤ len(list) * cost(f) + len(list)
{
    // ...
}
```

At each call site, `f` is concrete and `cost(f)` is known:

```spore
let result = map(items, |x| x * 2)
// cost(|x| x * 2) = 1 op
// total cost = len(items) * 1 + len(items) = 2 * len(items)
```

**Resolution rules:**

1. `cost(f)` in a signature is a **meta-variable** that is substituted with the concrete function's cost at each call site.
2. Since higher-order function arguments must be pure in Spore, `cost(f)` is always statically determinable at the call site.
3. After substitution, the result is a standard CostExpr that can be verified normally.
4. The compiler does **not** attempt abstract cost reasoning over uninstantiated type parameters — this keeps the system simple and deterministic.

---

## Human experience impact

### Positive

- **Zero-cost annotations for most code.** ~70% of functions are structurally recursive and get cost bounds automatically. Developers write ordinary code and the compiler silently tracks cost.
- **Performance regressions caught at compile time.** If a refactoring changes O(n) to O(n²), the `cost ≤` declaration fails immediately — not after a production outage.
- **Precise diagnostics.** The compiler does not just say "cost exceeded"; it provides a four-dimensional breakdown showing exactly where the budget went.
- **Gradual adoption.** The three-tier design means developers can start with `@unbounded` everywhere and progressively tighten bounds as the codebase matures.

### Negative

- **Learning curve.** Developers must understand asymptotic cost notation to write Tier 2 declarations. The `CostExpr` grammar (no subtraction, no division) requires adjustment.
- **False positives.** Conservative analysis may reject programs whose actual cost is within bounds (e.g., amortized O(1) operations reported as O(n)).
- **Annotation burden for non-structural recursion.** The ~20% of functions in Tier 2 require explicit `cost ≤` and possibly `decreases` clauses.

### Mitigation

- The compiler suggests fixes: "change `cost ≤ n` to `cost ≤ n * log(n)` to match inferred cost."
- `@trust_cost` suppresses unverified-bound warnings for cases where the developer is confident.
- IDE integration shows cost inline as code lens annotations.

---

## Agent experience impact

### Cost budgets as constraints for hole-filling

When an AI agent fills a Hole (see SEP-0003), it receives not just the type signature but also the **remaining cost budget**. This fundamentally changes code generation:

```json
{
  "hole": "combine_results",
  "expected_type": "Result[T]",
  "cost_budget_remaining": 34,
  "recursion_context": {
    "pattern": "structural_binary_tree",
    "per_node_budget": "500 / nodes(tree) - 6"
  }
}
```

The agent knows:

1. **What** to produce (the type)
2. **How much** it can spend (the cost budget)
3. **How often** the code runs (recursion context)

This enables cost-aware code generation: the agent can reject an O(n) algorithm in favor of an O(1) one if the budget demands it.

### Cost verification as feedback signal

After generating code, the agent can invoke `sporec --query-cost` to verify its solution meets the budget. Failed verification provides a precise error signal ("inferred cost n² exceeds budget n × log(n) by factor n / log(n)") that can drive iterative refinement.

### `@unbounded` as a risk signal

An agent encountering an `@unbounded` function in its context knows to exercise caution — calling it may introduce unbounded resource consumption. The agent can proactively suggest `with_cost_limit` wrapping.

---

## Structured representation / protocol impact

### Cost metadata in compilation output

The compiler emits structured cost information as part of the compilation artifact:

```json
{
  "functions": {
    "merge_sort": {
      "cost_declared": "n * log(n) * 5 + n",
      "cost_inferred": "n * log(n) * 4 + n",
      "cost_status": "verified",
      "cost_dimensions": {
        "compute": "n * log(n) * 4",
        "alloc": "n",
        "io": "0",
        "parallel": "1"
      },
      "tier": 2,
      "decreases": "len(list)"
    },
    "factorial": {
      "cost_inferred": "n * 4",
      "cost_status": "auto",
      "tier": 1,
      "recursion_pattern": "structural_linear"
    }
  }
}
```

### CostExpr serialization

CostExpr is serialized as a JSON AST for tool consumption:

```json
{
  "type": "Mul",
  "left": { "type": "Var", "name": "n" },
  "right": { "type": "Log", "arg": { "type": "Var", "name": "n" } }
}
```

### LSP extensions

The Language Server Protocol exposes:

- `sporec/queryCost`: returns cost metadata for a function
- `sporec/costBreakdown`: returns a per-expression cost tree for a function body
- `sporec/costBudget`: for a Hole, returns the remaining cost budget

---

## Diagnostics impact

### New diagnostic categories

| Code | Severity | Trigger |
|------|----------|---------|
| `cost-exceeded` | Error | Inferred cost exceeds declared bound |
| `unbounded-cost` | Warning | Recursive function with no detectable cost bound and no `@unbounded` annotation |
| `unbounded-function` | Warning | Function marked `@unbounded` |
| `unbounded-in-bounded-context` | Error | `@unbounded` function called from `cost ≤ K` context without `with_cost_limit` |
| `unverified-cost-bound` | Warning | `cost ≤ expr` declared but compiler cannot verify it |
| `cost-effect-conflict` | Error | `uses []` (pure) declared but W > 0 inferred |

### Example diagnostics

**cost-exceeded:**

```text
ERROR [cost-exceeded] bad_search's inferred cost exceeds declared bound.
  Inferred: n * log(n)
  Declared: ≤ n
  Excess factor: log(n)

  Suggestions:
  (a) Change declaration to `cost ≤ n * log(n)` to match actual cost
  (b) Optimize implementation to eliminate the log(n) factor
  (c) Check for unnecessary nested iteration
```

**unbounded-cost:**

```text
WARNING [unbounded-cost] fibonacci's cost cannot be statically determined.
  Recursion pattern: non-structural (exponential)
  Inferred complexity: O(2^n)

  Options:
  (a) Add `cost ≤ K` with parameter constraint `n: Int if n ≤ 30`
  (b) Mark as `@unbounded` (relinquish cost constraint)
  (c) Rewrite using structural recursion or tail recursion + iteration bound
```

### Cross-validation with effects

The cost system and effect system form a cross-validation network. If a function declares `uses []` (pure, no effects) but cost analysis discovers W > 0 (I/O operations), the compiler emits `cost-effect-conflict`. Conversely, a function declared `uses [NetConnect]` must have W ≥ 1 in at least one code path.

---

## Drawbacks

1. **Compile-time overhead.** The O(n⁵) worst-case verification, while polynomial, can be slow for deeply nested expressions. In practice, expressions are small (n ≤ 50) and the actual time is negligible, but pathological cases are possible.

2. **Expressiveness limitations.** The CostExpr grammar cannot express:
   - Conditional cost (`if sorted then O(n) else O(n²)`)
   - Amortized cost (`O(1) amortized`)
   - Probabilistic cost (`O(n log n) expected`)
   - Exact formulas requiring subtraction or division (`n*(n-1)/2`)

   The workaround is always conservative upper bounds (e.g., `n^2` instead of `n*(n-1)/2`).

3. **False positives (FAIL when should PASS).** The asymptotic comparison is conservative. Cancellation effects between terms can cause false FAIL results. Example: `n² + n ≤ 2 * n²` holds, but if the algorithm cannot find a per-monomial match for the `n` term, it reports FAIL.

4. **`@unbounded` contagion.** One `@unbounded` function deep in the call chain can force many callers to also become `@unbounded`, potentially undermining the cost system's value. Mitigation: `with_cost_limit` isolation.

5. **No runtime validation (yet).** The system currently has no mechanism to verify that compile-time cost predictions match actual runtime performance. Cost drift detection is deferred to future work.

6. **Multi-variable partial order.** With multiple variables, some monomials are incomparable (e.g., `n*m` vs `n²`), leading to conservative FAIL. Developers must restructure declarations.

---

## Alternatives considered

### Alternative 1: Full dependent types (Agda/Coq style)

Use a full dependent type system to encode cost bounds as types, enabling machine-checked proofs.

**Rejected because:**

- Requires every function to carry a termination proof — too much burden for general-purpose programming.
- 100% coverage means rejecting legitimate programs (e.g., Collatz-like functions).
- Dramatically steeper learning curve.

### Alternative 2: No static cost analysis (Rust/Go style)

Rely entirely on runtime profiling and benchmarks.

**Rejected because:**

- Misses Spore's unique opportunity (no loops, ADTs, purity).
- Performance regressions discovered too late.
- No cost information for AI agents during hole-filling.

### Alternative 3: Two-tier only (auto + unbounded, no declarations)

Skip Tier 2 — either the compiler infers the cost automatically or the function is unbounded.

**Rejected because:**

- Would leave ~20% of practically-bounded functions as `@unbounded`, significantly reducing the system's value.
- Merge sort, quicksort, GCD, and many other well-known algorithms would lack cost bounds.

### Alternative 4: Allow division and subtraction in CostExpr

Extend the grammar to support `n*(n-1)/2` and similar expressions.

**Rejected because:**

- Division introduces non-integer results and division-by-zero.
- Subtraction breaks monotonicity (expressions can decrease as inputs grow).
- The comparison problem becomes undecidable in general.
- The conservative upper-bound approach (`n^2` instead of `n*(n-1)/2`) is acceptable in practice.

### Alternative 5: SMT-based verification

Use an SMT solver (e.g., Z3) to verify `∀ n̄. C(n̄) ≤ B(n̄)`.

**Rejected as the primary approach because:**

- SMT solving is NP-complete in general — no polynomial-time guarantee.
- Solver behavior is non-deterministic (different versions may give different results).
- However, this remains a potential fallback for the compiler's "extra effort" phase after the main algorithm returns FAIL.

---

## Prior art

### Dependent type systems: Agda, Coq, Lean 4

These proof assistants enforce termination of all functions. Agda and Coq use structural recursion checking by default; Lean 4 adds `decreasing_by` tactics and `partial` escape. Spore's Tier 1 is directly inspired by structural recursion checking in these systems, but Spore's Tier 3 (`@unbounded`) is a deliberate departure — we accept non-terminating programs rather than rejecting them.

### Resource-aware type systems: AARA (Automatic Amortized Resource Analysis)

Hoffmann et al.'s AARA system (implemented in Resource Aware ML) automatically infers polynomial resource bounds using linear programming over type annotations. AARA can handle amortized analysis, which Spore currently cannot. However, AARA's approach requires sophisticated LP solving and is less transparent to developers. Spore opts for a simpler, more transparent system at the cost of not supporting amortized analysis.

### Complexity analysis tools: COSTA, AProVE

COSTA (COSt and Termination Analyzer for Java) and AProVE (Automated Program Verification Environment) perform automatic complexity analysis on Java and term rewriting systems respectively. These tools demonstrate that automatic cost analysis is feasible for real languages. Spore's advantage is that its language design (no loops, pure functions, ADTs) makes the analysis significantly more tractable.

### Gas metering: Ethereum/Solidity

Smart contract languages assign deterministic gas costs to every operation. Spore's primitive cost table is inspired by this approach but extends it to symbolic expressions (Solidity's gas is always concrete). Spore's four-dimensional model also goes beyond Solidity's single gas dimension.

### Abstract interpretation: Cousot & Cousot

Spore's cost inference uses abstract interpretation — executing the program on an abstract domain (CostExpr) rather than concrete values. This is a well-established technique (Cousot & Cousot, 1977) applied here specifically to cost propagation.

### Sized types: Hughes, Pareto, Sabry

Sized types annotate data types with size information (e.g., `List[T, max: n]`) to enable termination checking and complexity analysis. Spore's bounded types are directly inspired by this line of work.

---

## Backward compatibility and migration

### This is a new feature

Cost analysis is introduced as a new compiler effect. No existing Spore code is broken by this SEP.

### Migration path

1. **Phase 1 (initial release):** All functions without cost annotations are implicitly treated as if cost analysis is not enabled. The compiler performs Tier 1 analysis silently and reports results only when explicitly queried (`sporec --query-cost`).

2. **Phase 2 (opt-in):** Projects opt into cost checking via `spore.toml`:

   ```toml
   [cost]
   enabled = true
   alloc_weight = 2
   io_weight = 100
   ```

   Functions without cost bounds but with non-structural recursion receive warnings.

3. **Phase 3 (default-on):** Cost analysis is enabled by default. Functions with unresolvable cost receive `unbounded-cost` warnings. Projects can silence with `[cost] enabled = false`.

### Interaction with existing SEPs

- **SEP-0002 (Type System):** CostExpr types integrate with the type checker. Bounded types (`List[T, max: n]`) provide size information for cost analysis.
- **SEP-0003 (Hole System):** Cost budgets are propagated to HoleReports, enriching the constraint environment for hole-filling.

---

## Edge cases and limitations

### Pure constant expressions

When both C and B contain no variables, the comparison degenerates to numeric comparison:

```text
C = 42, B = 100
Verification: 42 ≤ 100 → PASS
```

No asymptotic analysis is needed; the compiler computes directly.

### Single-variable expressions

With a single variable `n`, comparison reduces to standard Big-O notation comparison. Each normal-form monomial is `c × n^a × log(n)^b`, with the ordering:

```text
(c₁, a₁, b₁) ≼ (c₂, a₂, b₂) ⟺ a₁ < a₂
                                  ∨ (a₁ = a₂ ∧ b₁ < b₂)
                                  ∨ (a₁ = a₂ ∧ b₁ = b₂ ∧ c₁ ≤ c₂)
```

This is consistent with classical asymptotic order comparison.

### Multi-variable partial order

With k > 1 variables, the comparison uses componentwise partial ordering on exponent vectors. Two monomials may be **incomparable** (e.g., `n*m` vs. `n²`). Incomparable cases produce FAIL (conservative). Developers must restructure declarations to make them comparable, e.g., using `max(n*m, n^2)`.

### Limitations

| Limitation | Description | Workaround |
|---|---|---|
| No conditional cost | Cannot express "if sorted then O(n), else O(n²)" | Use `max(n, n^2) = n^2` (conservative) |
| No amortized analysis | Cannot express "amortized O(1)" | Use worst-case cost |
| No probabilistic analysis | Cannot express "expected O(n log n)" | Use worst-case cost |
| No subtraction / division | Cannot exactly express `n*(n-1)/2` | Use `n^2` upper bound |
| max/min nesting depth bounded | Deep nesting causes expression blowup | Compiler limits depth (default 8) |
| Multi-variable incomparability | Partial order on exponent vectors can be inconclusive | Restructure declaration or use `max` |

---

## Cost drift detection

Cost drift detection monitors divergence between compile-time cost predictions and actual runtime performance. While full implementation is deferred to a future SEP, the mechanism is specified here.

**Tolerance threshold.** The configurable parameter `cost_drift_tolerance` defines the maximum allowed ratio of actual-to-predicted cost:

```toml
[cost]
cost_drift_tolerance = 1.2   # allow 20% deviation
```

**Detection mechanism:**

1. **Instrumentation**: when cost drift detection is enabled (`sporec --cost-instrument`), the compiler inserts lightweight counters at function entry/exit that track actual op/cell/call counts.
2. **Sampling**: the runtime samples cost at configurable frequency (default: every 100th invocation) to minimize overhead.
3. **Comparison**: at runtime, if `actual_cost / predicted_cost > cost_drift_tolerance`, a `CostDrift` warning is logged.
4. **CI integration**: a post-test step `sporec --cost-drift-report` compares sampled costs against compile-time predictions and fails the build if drift exceeds the threshold.

**Diagnostic format:**

```text
WARNING [cost-drift] function merge_sort: actual cost exceeds prediction.
  Predicted: 1200 op
  Actual (sampled): 1500 op
  Drift ratio: 1.25 (threshold: 1.2)
  Suggestion: review recent changes to merge_sort or update cost ≤ declaration
```

---

## Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Recursion analysis tiers | 3 tiers (auto + declarative + escape) | Balances automation with expressiveness; ~90% coverage |
| Structural recursion detection | Syntactic parameter-decreasing check | Simple, reliable, O(\|call_graph\|) complexity |
| Verification failure handling | Warning, not error | Gradual adoption; does not block development |
| `@unbounded` semantics | Contagious + isolatable via `with_cost_limit` | Ensures cost information propagates while providing an escape path |
| `decreases` clause | Optional | Compiler auto-derives in most cases; manual only when needed |
| Mutual recursion | SCC-based whole-group analysis | Natural fit with call-graph analysis |
| Higher-order function cost | Compiler built-in formulas | No loops → HOFs are the only iteration mechanism; must be built-in |

---

## Unresolved questions

1. **Tail-call optimization and cost.** TCO changes stack space consumption but not computation cost. Should the cost model distinguish a "stack depth" dimension? Current decision: no — TCO is a codegen optimization that does not affect cost analysis.

2. **Memoization and cost.** Should the compiler auto-detect memoizable recursion and adjust cost (e.g., `fibonacci` from O(2ⁿ) to O(n))? Current leaning: no auto-memoization, but the compiler suggests it in warnings.

3. **Cost drift detection.** The mechanism, tolerance threshold, and CI integration are specified in the "Cost drift detection" section above. The remaining unresolved question is the design of a full runtime cost sampling framework — specifically, how to keep instrumentation overhead below 1% in production builds.

4. **Probabilistic cost bounds.** Randomized algorithms (e.g., QuickSort with random pivot) have expected rather than worst-case cost. Should Spore support `cost ≤ O(n log n) expected`? Deferred to future work.

5. **Polymorphic cost (partially resolved).** The call-site instantiation approach is now specified in §4.17: `cost(f)` is substituted at each call site where `f` is concrete. The remaining open question is whether the signature-level notation `cost ≤ N × cost(f) + N` should be a first-class part of the CostExpr grammar, or remain an informal convention that the compiler resolves during monomorphisation.

6. **Recursion depth limits.** Should the compiler enforce a compile-time recursion depth ceiling? Current decision: only `@unbounded` functions use runtime `with_cost_limit`. Whether to add a compile-time depth annotation (e.g., `max_depth ≤ 1000`) is unresolved.

7. **Interaction with concurrency.** The parallel dimension `P` (lane) is defined but its interaction with async/await and structured concurrency needs further specification. In particular, how does `with_cost_limit` behave across spawn boundaries?

8. **Amortized analysis.** Operations like dynamic array append are O(1) amortized but O(n) worst-case. The current system can only express worst-case bounds. Whether to extend CostExpr with amortized semantics (potentially through a separate annotation `cost_amortized ≤ expr`) is deferred.

9. **Standard library cost annotations.** The standard library must be annotated with cost bounds for the system to be useful. What is the process for auditing and annotating existing library functions? Should the compiler ship with a built-in cost database for the standard library?

10. **max/min nesting depth limit.** The current default is 8 levels. Is this sufficient for all practical use cases? Should the limit be configurable, and what is the impact on compilation time when it is raised?
