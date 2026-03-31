---
sep: 5
title: "SEP-0005: Hole System & Agent Protocol"
status: Draft
type: Standards Track
authors:
  - Spore maintainers
created: 2026-03-31
requires:
  - 2
  - 3
  - 4
discussion: "https://github.com/spore-lang/spore-evolution/discussions/5"
pr: null
superseded_by: null
---

# SEP-0005: Hole System & Agent Protocol

## Summary

This SEP specifies Spore's **Hole System** — a first-class language mechanism that treats unfinished code as a structured, typed, compiler-mediated collaboration interface between humans and AI Agents.

A *hole* is written `?name` (optionally `?name: Type`) in any expression position within a function body. The compiler accepts programs containing holes, classifies those functions as **partial**, and produces a **HoleReport** — a self-contained JSON document that carries every piece of information an Agent needs to fill the hole: expected type, available bindings with data-flow dependencies, capability set, cost budget, candidate functions with multi-dimensional scoring vectors, confidence indicators, and error clusters.

Multiple holes form a **Hole Dependency Graph** (DAG), enabling topological ordering and parallel filling by multiple Agents. An **Agent Protocol** defines a five-state machine (DISCOVER → ANALYZE → PROPOSE → VERIFY → ACCEPT/REJECT) that governs the automated filling workflow, integrated with `spore watch --json` for incremental compilation feedback.

Key components formalized in this SEP:

- **Hole syntax and semantics** (`?name`, `?name: Type`, partial functions)
- **HoleReport v0.3** with four extensions: (A) candidate scoring vector, (B) binding dependency graph, (C) confidence & ambiguity, (D) error clusters
- **Hole Dependency Graph** with layered topological sort and parallel fill scheduling
- **Agent state machine protocol** for autonomous hole filling
- **JSON output protocol** via `--json` flag and NDJSON event stream

---

## Motivation

### The Problem with Unfinished Code

Traditional languages treat unfinished code as an error — `todo!()`, `unimplemented!()`, `???` markers all produce runtime panics or compile-time failures. This forces developers into an all-or-nothing workflow: either the function is complete or it doesn't compile. There is no structured middle ground.

This creates two problems:

1. **For humans**: Developers cannot express partial intent. They know the function's contract (signature, error types, cost bound, capability requirements) but haven't decided on the implementation yet. Traditional languages offer no way to say "this part is intentionally unfinished, here is what I need" in a way the compiler understands.

2. **For AI Agents**: Without structured information about what is missing, Agents must reverse-engineer context from error messages, heuristically guess types, and operate without compiler guidance. The quality ceiling is low and the failure rate is high.

### Why Holes Must Be First-Class

Making holes a first-class language construct enables:

- **Compiler-mediated collaboration**: The compiler produces HoleReports that are *information-self-sufficient* — an Agent reading a report needs zero additional context to attempt a fill.
- **Incremental development**: Functions transition smoothly from `partial` to `complete`. Downstream callers are not invalidated because holes are body-only — they never affect signature hashes.
- **Dependency-ordered filling**: The compiler can analyze data-flow between holes, build a DAG, and recommend an optimal filling order.
- **Cost-bounded filling**: Each hole carries a remaining cost budget inherited from the enclosing function's `cost ≤ N` clause.

### Why the Agent Protocol Matters

AI Agents are not humans reading error messages. They are stateless processes that parse structured output. Spore's hole system is designed with Agents as a *primary* consumer:

- **HoleReport v0.3** replaces human-readable strings (e.g., `match_quality: "partial"`) with machine-comparable scoring vectors.
- **Binding dependency graphs** let Agents understand data-flow without re-analyzing source code.
- **Confidence indicators** tell Agents when to auto-fill vs. when to request human guidance.
- **NDJSON event streams** allow Agents to consume compiler output in real-time, reacting to each incremental compilation result.

Without a formal protocol, every Agent tool would invent its own ad-hoc interaction pattern with the compiler. This SEP standardizes that interaction.

---

## Guide-level explanation

### Hole Syntax: `?name`

A hole is written with a `?` prefix followed by an identifier. Holes can appear anywhere an expression is expected:

```spore
fn calculate_tax(income: Money, region: Region) -> Money ! [InvalidRegion]
    uses [TaxTable]
    cost ≤ 500
{
    ?tax_logic
}
```

The function compiles successfully. It is marked `partial` — not broken.

Optionally, holes can carry a type annotation:

```spore
let body: String = ?report_body : String
```

If the annotation conflicts with the inferred type, the compiler emits a `hole-type-conflict` warning (not an error — holes are exploratory).

### Multiple Holes and Nested Holes

A function may contain any number of independently named holes:

```spore
fn reconcile(ledger: Ledger, txns: Vec<Tx>) -> Ledger ! [Mismatch]
    cost ≤ 5000
{
    let grouped     = group_by_account(txns)
    let adjustments = ?compute_adjustments
    let validated   = ?validate_adjustments
    apply(ledger, validated)
}
```

Holes can also appear nested inside expressions, function arguments, and match arms:

```spore
fn render(page: Page) -> Html ! [TemplateError]
    uses [Templates]
    cost ≤ 800
{
    let nav = render_nav(?nav_items)                 // hole as argument
    let content = match page.kind {
        Article(a)     => render_article(a),
        Gallery(g)     => ?gallery_renderer,          // hole in match arm
        _              => render_fallback(page),
    }
    compose(nav, content)
}
```

The compiler infers that `?nav_items` must have the type `render_nav` expects as its first parameter, and `?gallery_renderer` must have the same type as the other match arms.

### Partial Functions

A function containing at least one hole is **partial**. Partial functions:

| Property | Complete | Partial |
|---|---|---|
| Can be compiled | ✓ | ✓ |
| Can be called at runtime | ✓ | ✗ |
| Can be simulated | ✓ | ✓ |
| Appears in module exports | ✓ | ✓ (marked `partial`) |
| Signature hash changes on fill | if signature changes | never (holes are body) |

Partiality is transitive: a caller of a partial function is itself partial.

### Agent Workflow Example

A complete Human → Agent → Compiler interaction:

**Step 1 — Human writes a function with holes:**

```spore
fn generate_invoice(
    customer: Customer,
    items: Vec<LineItem>,
    tax_region: TaxRegion,
) -> Invoice ! [TaxCalculationError, InvalidLineItem]
    uses [TaxTable]
    cost ≤ 5000
{
    let validated_items = ?validate_items
    let subtotal = sum(validated_items.map(|i| i.price * i.quantity))
    let tax = ?compute_tax
    let total = subtotal + tax
    Invoice.new(customer, validated_items, subtotal, tax, total)
}
```

**Step 2 — Agent queries holes:**

```text
$ sporec --query-hole ?validate_items --json
```

The compiler returns a HoleReport (see §4 for the full structure) containing: expected type `Vec<LineItem>`, available bindings, candidate function `validate_line_items` with an exact type match, cost 300 within budget 5000.

**Step 3 — Agent proposes a fill:**

```spore
validate_line_items(items)
```

**Step 4 — Compiler verifies:**

```text
$ sporec check src/billing/invoice.spore

[partial] generate_invoice
  ?validate_items: filled ✓ (cost 300)
  ?compute_tax: still open
  budget for ?compute_tax: ≤4580
```

**Step 5 — Agent fills the next hole, compiler confirms completion:**

```text
[ok] generate_invoice : (...) -> Invoice ! [TaxCalculationError, InvalidLineItem]
  cost: 520 (within budget of 5000)
  all holes filled ✓
```

---

## Reference-level explanation

### Hole Syntax (Formal)

```text
hole       ::= '?' IDENT (':' type)?
IDENT      ::= [a-z_][a-zA-Z0-9_]*
```

Holes are expressions. They can appear in any expression context. They **cannot** appear in:

- Type positions (type holes `?T_Name` in uppercase are a separate concept)
- Signature positions (parameter types, return types, error lists, `with`/`cost`/`uses` clauses)
- Module-level declarations

Hole names must be unique within a module. The compiler rejects duplicate hole names in the same module.

Empty function bodies desugar to a single hole named `{function_name}_body`.

### HoleInfo Structure

The implementation (in `spore-typeck`) represents a single hole as:

```rust
pub struct HoleInfo {
    pub name: String,              // from ?name
    pub expected_type: Ty,         // inferred/expected type
    pub function: String,          // enclosing function
    pub bindings: BTreeMap<String, Ty>,  // local bindings at hole site
    pub suggestions: Vec<String>,  // candidate functions
}
```

**HoleInfo vs HoleReport:** `HoleInfo` is the **compiler-internal** representation (Rust struct in `spore-typeck`), while `HoleReport` is the **JSON output format** for machine/Agent consumption. `HoleInfo` is converted to `HoleReport` via `to_json()` with additional computed fields (scores, confidence, error clusters). They serve different purposes: HoleInfo for compiler passes, HoleReport for external tooling.

The `HoleReport` aggregates all holes in a module, with `to_json()` for machine consumption. Hand-rolled JSON serialization is used in v0.1 to minimize dependencies; serde migration is tracked as future work (see Unresolved Questions §10).

### HoleReport v0.3

HoleReport v0.3 is a **superset** of v0.2. The schema version advances from `"spore/hole-report/v1"` to `"spore/hole-report/v2"`. All v0.2 fields are preserved; four new extensions are added.

#### Base Fields (v0.2)

| Field | Description |
|---|---|
| `hole.name` | Developer-assigned name |
| `hole.location` | Source location (file, line, column) |
| `hole.dependencies` | Names of upstream holes whose output feeds into this hole's context |
| `type.expected` | The type this hole must produce, including error variants |
| `type.inferred_from` | Human-readable explanation of why this type is expected |
| `bindings` | Variables in scope with name, type, and simulated value (`symbolic` or `computed`) |
| `capabilities` | The `uses` list from the enclosing function |
| `errors_to_handle` | Error types not yet handled before the hole |
| `cost.budget_total` | The `cost ≤ N` from the enclosing function |
| `cost.cost_before_hole` | Cumulative cost of statements before the hole |
| `cost.budget_remaining` | `budget_total - cost_before_hole` |
| `candidates` | Functions in scope whose return type matches the hole's expected type |
| `dependent_holes` | Holes that become reachable when this hole is filled |
| `enclosing_function` | Full signature context of the containing function |

#### Hole Type Inference Rule

A hole's type is determined by the **intersection of all constraints** imposed by its context. Constraints flow from:

1. **Let-binding annotations:** `let x: T = ?h` constrains `?h` to type `T`
2. **Return position:** A hole in tail position inherits the function's return type
3. **Function arguments:** `f(?h)` constrains `?h` to the parameter type of `f`
4. **Match arms:** A hole in a match arm must have the same type as sibling arms
5. **Operators:** `?h + x` where `x: Int` constrains `?h` to `Int` (or a type implementing `Add<Int>`)

When multiple constraints agree, the intersection is the agreed-upon type. When constraints conflict, the compiler applies the **nearest constraint rule** (see Edge Cases §8.3) and emits a warning.

When context provides **no constraints**, the hole is *unconstrained* — reported with type `_`. The HoleReport lists available bindings so the Agent can propose a type.

#### Hole as Match Scrutinee

When the scrutinee of a `match` is a hole, the compiler infers the hole's type from the **pattern types** in the match arms:

```spore
fn classify(data: RawData) -> Category ! [ParseError]
{
    match ?parsed_data {         // hole as scrutinee
        Valid(v)   => categorize(v),
        Invalid(e) => raise ParseError(e),
    }
}
```

The compiler infers: `?parsed_data` must have a type with at least variants `Valid(_)` and `Invalid(_)`. If a type in scope matches (e.g., `Result<ValidData, ErrorInfo>`), it is reported as the inferred type. All branches are reported as **blocked** (since the scrutinee is unknown, no branch can execute during simulation).

#### Extension A: Candidate Scoring Vector

Replaces the coarse `match_quality: "exact" | "partial"` string with a four-dimensional numeric vector:

| Dimension | Field | Range | Meaning |
|---|---|---|---|
| Type match | `type_match` | `[0, 1]` | Return type + parameter type match degree |
| Cost fit | `cost_fit` | `[0, 1]` | Estimated cost vs. remaining budget fit |
| Capability fit | `capability_fit` | `{0, 1}` | All required capabilities available (boolean) |
| Error coverage | `error_coverage` | `[0, 1]` | Fraction of candidate's declared errors covered by context |

**Type match formula:**

```text
type_match(candidate, hole) =
    0.6 × type_similarity(candidate.return_type, hole.expected_type)
  + 0.4 × mean(param_scores)
```

Where `type_similarity(A, B)` returns: 1.0 (exact), 0.9 (subtype), 0.7 (known conversion), 0.5 (same constructor), 0.0 (unrelated).

**Cost fit formula:**

```text
cost_fit(candidate, hole) =
    if estimated_cost ≤ budget_remaining:
        1.0 - (estimated_cost / budget_remaining) × 0.3
    else:
        max(0, 1.0 - (estimated_cost - budget_remaining) / budget_remaining)
```

**Overall score:**

```text
overall = 0.40 × type_match + 0.20 × cost_fit + 0.25 × capability_fit + 0.15 × error_coverage
```

Weights are hard-coded in the compiler. Candidates are sorted by `overall` descending, with `type_match` as tiebreaker, then `cost_fit`, then lexicographic name for stability.

Each candidate also includes an `adjustments` array of human-readable notes (e.g., `"needs type conversion: Option<Card> → Card"`, `"cost near budget limit"`).

#### Extension B: Binding Dependency Graph

An adjacency-list representation of data-flow between bindings at the hole site:

```json
"binding_dependencies": {
  "customer": [],
  "amount": [],
  "validated_card": ["customer"],
  "order": ["customer", "amount"],
  "validated": ["order"],
  "charged": ["validated", "validated_card"]
}
```

Extracted from SSA-form data-flow analysis. Agents should prefer "terminal" bindings (high in-degree, low out-degree) as they carry the most computed information.

#### Extension C: Confidence & Ambiguity

```json
"confidence": {
  "type_inference": "certain" | "partial" | "unknown",
  "candidate_ranking": "unique_best" | "ambiguous" | "no_candidates",
  "ambiguous_count": 0,
  "recommendation": "gateway_charge is the best match with 0.91 overall score"
}
```

- `type_inference`: `"certain"` (fully determined), `"partial"` (constructor known, parameters unknown), `"unknown"` (no constraints)
- `candidate_ranking`: `"unique_best"` (gap ≥ 0.15 from second), `"ambiguous"` (gap < 0.15), `"no_candidates"` (empty list)
- `ambiguous_count`: number of candidates within ±0.15 of the best score

#### Extension D: Error Clusters

Groups errors by their source operation with handling suggestions:

```json
"error_clusters": [
  {
    "source": "gateway_charge",
    "errors": ["PaymentFailed", "GatewayTimeout"],
    "handling_suggestion": "match on error type, retry GatewayTimeout with backoff"
  },
  {
    "source": "validate_card",
    "errors": ["InvalidCard"],
    "handling_suggestion": "early return with ?"
  }
]
```

Suggestion generation rules:

| Pattern | Suggestion |
|---|---|
| Single error, propagable | `"early return with ?"` |
| Multiple errors, same source | `"match on error type"` |
| Retryable (contains `Timeout`/`Retry`) | `"retry with backoff"` |
| Error in enclosing function's `!` list | `"propagate to caller"` |

#### Error System Integration (Three-Field Model)

The enclosing function's declared error list (`! [Err1, Err2, Err3]`) is partitioned into three categories at each hole site:

| Field | Meaning |
|---|---|
| `errors_to_handle` | Errors not yet handled by code before the hole. The filling should handle or propagate these. |
| `errors_already_handled` | Errors that were caught/handled by code before the hole (e.g., via `catch` or `match`). The filling does not need to worry about these. |
| `errors_passthrough` | Errors that can propagate upward to the caller. The filling may also propagate them but does not need explicit handling. |

Example:

```spore
fn fetch_and_parse(url: Url) -> Document ! [NetworkError, ParseError, Timeout]
    uses [Http]
    cost ≤ 3000
{
    let response = http_get(url)          // may raise NetworkError, Timeout
        |> catch Timeout => retry_once(url)  // Timeout handled here
    ?parse_response
}
```

HoleReport for `?parse_response`:

```json
{
  "errors_to_handle": ["ParseError"],
  "errors_already_handled": ["Timeout"],
  "errors_passthrough": ["NetworkError"]
}
```

- `ParseError`: the filling should handle or propagate it.
- `Timeout`: handled before the hole; no action needed.
- `NetworkError`: propagates to the caller; the filling may also propagate it without explicit handling.

### Hole Dependency Graph

#### Definition

Given a module M, the Hole Dependency Graph G = (V, E) is:

- **V** = set of all unfilled holes in M
- **E** = { (h₁, h₂) | h₂'s type inference or constraint solving depends on h₁'s output }

Edges are classified into three dependency types:

| Type | Notation | Meaning |
|---|---|---|
| Type dependency | `type` | h₂'s expected type contains a type variable solvable only after h₁ is filled |
| Value dependency | `value` | h₂'s available bindings include a value whose data-flow traces back to h₁ |
| Cost dependency | `cost` | h₂'s remaining cost budget depends on h₁'s actual cost |

#### Graph Construction

```pseudocode
function build_hole_graph(module: TypedAST) -> Graph:
    holes = find_all_holes(module)
    edges = []

    for each hole h in holes:
        for each binding b in h.available_bindings:
            if trace_data_source(b) is HoleOutput(h'):
                edges.add(Edge(from=h', to=h, kind="value"))

        for each type_var tv in free_type_vars(h.expected_type):
            if trace_type_source(tv) is HoleOutput(h'):
                edges.add(Edge(from=h', to=h, kind="type"))

        if h.cost_budget depends on another hole h':
            edges.add(Edge(from=h', to=h, kind="cost"))

    return Graph(vertices=holes, edges=deduplicate(edges))
```

`trace_data_source` follows SSA data-flow edges backward. `trace_type_source` follows type inference constraint chains backward. Both are exhaustive, guaranteeing no hidden dependencies.

#### Data-Flow Tracing (`trace_data_source`)

Traces an SSA binding backward to its origin:

```pseudocode
function trace_data_source(binding: Binding) -> Source:
    match binding.origin:
        Parameter(p)       => return ParameterSource(p)
        LetBinding(expr)   => return trace_expr_source(expr)
        HoleOutput(h)      => return HoleOutput(h)
        FunctionCall(f, args) =>
            args.iter().find_map(|arg|
                match trace_data_source(arg):
                    HoleOutput(h) => Some(HoleOutput(h))
                    _             => None
            ).unwrap_or(ConcreteSource(f))
```

#### Type Constraint Tracing (`trace_type_source`)

Traces a type variable backward through the constraint graph:

```pseudocode
function trace_type_source(tv: TypeVar) -> Source:
    constraints = get_constraints_for(tv)
    constraints.iter().find_map(|c|
        match c:
            UnifyWith(HoleOutputType(h)) => Some(HoleOutput(h))
            UnifyWith(ConcreteType(t))   => Some(ConcreteSource(t))
            UnifyWith(OtherTypeVar(tv')) => Some(trace_type_source(tv'))
    ).unwrap_or(Unconstrained)
```

#### Cycle Detection

Circular hole dependencies are **compile errors**. Detection uses standard DFS coloring in O(|V| + |E|):

```text
error[H0301]: circular hole dependency detected
  --> src/order.spore
  |
  | ?validate_order depends on ?check_inventory  (value dependency)
  | ?check_inventory depends on ?validate_order  (type dependency)
  |
  = help: break the cycle by providing a concrete type annotation on one hole
```

#### Cycle Fix Strategies

When a circular dependency is detected, the compiler suggests three strategies:

1. **Add type annotation:** Place an explicit type annotation on one hole in the cycle, breaking the type dependency:
   ```text
   help: e.g., ?validate_order : ValidatedOrder
   ```

2. **Split function:** Move the holes into separate functions. Each function's signature provides concrete type information, eliminating the circular inference:
   ```text
   help: extract ?validate_order into a standalone function with an explicit signature
   ```

3. **Introduce intermediate binding:** Add a `let` binding with a concrete type between the holes, breaking the value dependency chain:
   ```text
   help: add `let intermediate: ConcreteType = ...` between the dependent holes
   ```

#### Layered Topological Sort

```pseudocode
function compute_fill_order(G: Graph) -> Result<List<Set<Hole>>, CycleError>:
    if has_cycle(G): return Err(CycleError(find_cycle(G)))

    layers = []
    remaining = copy(V)
    in_degree = compute_in_degrees(G)

    while remaining is not empty:
        ready = { h ∈ remaining | in_degree[h] == 0 }
        layers.append(ready)
        for each h in ready:
            for each successor s of h:
                in_degree[s] -= 1
            remaining = remaining - ready

    return Ok(layers)
```

- `layers[0]`: no-dependency holes — fill first (all parallelizable)
- `layers[k]`: holes whose dependencies all lie in layers 0..k-1
- Within each layer, holes are ranked by **transitive dependents count** (impact heuristic)

**Complexity:** O(|V| + |E|) for construction, cycle detection, and topological sort.

#### Completeness Theorem

**Theorem (Completeness).** If the Hole Dependency Graph G = (V, E) is a DAG, then `compute_fill_order` discovers and outputs all fillable holes.

**Proof.** By induction on layer index k.

**Base case (k = 0):** L₀ = { h ∈ V | in-degree(h) = 0 }. These holes have no predecessors — their types, bindings, and cost budgets are fully determined. They are fillable. Since we take *all* zero in-degree nodes, no fillable hole is missed.

**Inductive step (k → k+1):** Assume layers L₀ through Lₖ are correctly computed and all holes in them are filled. Let G' be the subgraph remaining after removing L₀ ∪ ... ∪ Lₖ.

Lₖ₊₁ = { h ∈ V(G') | in-degree_{G'}(h) = 0 }

For any h ∈ Lₖ₊₁: all predecessors of h in G lie in L₀ ∪ ... ∪ Lₖ (already filled), so h's constraints are fully resolved — h is fillable.

Conversely, if a fillable hole h ∉ L₀ ∪ ... ∪ Lₖ₊₁, then h has in-degree > 0 in G', meaning an unfilled predecessor exists — contradicting fillability.

Therefore Lₖ₊₁ is exactly the set of newly fillable holes at round k+1. ∎

**Corollary.** The algorithm terminates in `depth(G) + 1` rounds, filling all holes.

**Corollary.** Data-flow exhaustiveness: since `trace_data_source` and `trace_type_source` traverse all SSA edges and type constraint chains, no dependency is undetected.

#### Complexity Analysis

| Operation | Time Complexity | Notes |
|-----------|----------------|-------|
| Graph construction | O(\|V\| × B) | B = average bindings per hole |
| Topological sort (layered) | O(\|V\| + \|E\|) | Kahn's algorithm variant |
| Cycle detection | O(\|V\| + \|E\|) | DFS coloring (by-product of topo sort) |
| Incremental update (single fill) | O(\|neighbors\|) | Only the filled hole's neighbors are touched |
| Parallel scheduling | O(\|V\|) | Traverse in-degree array to find ready set |
| JSON serialization | O(\|V\| + \|E\|) | Linear scan of graph structure |

**Space complexity:** O(|V| + |E|) for the graph structure and in-degree table.

#### Parallel Fill

Independent holes within the same layer can be filled simultaneously by different Agents. Maximum parallelism equals the widest layer (Dilworth's theorem).

Scheduling protocol:

```text
Round 0: ready_set = layers[0] = {h1, h2}
         Agent A1 ← h1, Agent A2 ← h2 (parallel)

Round 1: h1, h2 verified ✓ → incremental update → new ready_set = {h3}
         Agent A1 ← h3

Round 2: h3 verified ✓ → new ready_set = {h4, h5} (parallel)
         ...

Final: all holes filled → COMMIT
```

#### Incremental Update

When a hole is filled, the graph updates incrementally in O(|neighbors|):

1. Remove the filled hole from V
2. Remove all associated edges from E
3. Update in-degrees of successors; those reaching zero enter `ready_to_fill`
4. Check for newly revealed holes (filling may expose deeper code paths)
5. Emit a `hole_graph_update` event

#### Agent Allocation Strategy

```pseudocode
function assign_agents(ready: Set<Hole>, agents: List<Agent>) -> Assignment:
    ranked = rank_within_layer(ready, G)  // sort by transitive dependents
    assignment = {}
    ranked.iter().enumerate().for_each(|(i, hole)|
        agent = agents[i % agents.len()]   // round-robin
        assignment[hole] = agent
    )
    return assignment
```

When fewer Agents are available than ready holes, round-robin assigns the highest-impact holes first.

#### Conflict Resolution

Two Agents must not simultaneously fill the same hole. Mutual exclusion uses file-level locking:

```pseudocode
function try_fill(agent: Agent, hole: Hole) -> FillResult:
    if not acquire_lock(hole.file, agent.id):
        return FillResult { status: "conflict", hole: hole.name,
                            filled_by: lock_holder(hole.file) }

    result = agent.generate_fill(hole)
    verify = sporec_check(hole.file)

    if verify.ok:
        commit_fill(hole, result)
        release_lock(hole.file, agent.id)
        return FillResult { status: "success", hole: hole.name }
    else:
        rollback_fill(hole)
        release_lock(hole.file, agent.id)
        return FillResult { status: "verify_failed", errors: verify.errors }
```

### Agent State Machine

The Agent protocol defines a five-state machine with no explicit RETRY state:

```text
                ┌────────────────────────────────────────────────┐
                │                                                │
                ▼                                                │
          ┌──────────┐                                           │
          │ DISCOVER │── spore watch --json                      │
          └────┬─────┘   receive hole list + dependency graph    │
               │                                                 │
               │ select a hole from ready_to_fill                │
               ▼                                                 │
          ┌──────────┐                                           │
          │ ANALYZE  │── sporec --query-hole ?name --json        │
          └────┬─────┘   receive full HoleReport v0.3            │
               │                                                 │
               │ generate fill code                              │
               ▼                                                 │
          ┌──────────┐                                           │
          │ PROPOSE  │── write fill code to source file          │
          └────┬─────┘   (atomic: one hole per write)            │
               │                                                 │
               │ file change triggers incremental compilation    │
               ▼                                                 │
          ┌──────────┐                                           │
          │ VERIFY   │── await compile_result event              │
          └────┬─────┘                                           │
               │                                                 │
        ┌──────┴──────┐                                          │
        │             │                                          │
        ▼             ▼                                          │
  ┌──────────┐  ┌──────────┐                                     │
  │ ACCEPT   │  │ REJECT   │─── diagnostics returned ────────────┘
  └────┬─────┘  └──────────┘    Agent reads diagnostics,
       │                        re-enters PROPOSE or ANALYZE
       │ update graph, recompute ready_to_fill
       │
       │ more unfilled holes?
       ├── yes → return to DISCOVER
       └── no  → COMMIT (all holes filled)
```

**DISCOVER**: The Agent starts `spore watch --json` and receives a `hole_graph_update` event containing the full dependency graph, `ready_to_fill` list, and `blocked` list. The Agent selects one or more holes from `ready_to_fill`.

**ANALYZE**: For each selected hole, the Agent requests its HoleReport via `sporec --query-hole ?name --json`. It examines:

- `confidence.candidate_ranking`:
  - `"unique_best"` → use the top candidate directly
  - `"ambiguous"` → compare `scores` vectors, consult `adjustments`
  - `"no_candidates"` → construct code from scratch using `type`, `bindings`, `binding_dependencies`
- `error_clusters` → determine error handling strategy
- `cost.budget_remaining` → ensure proposed fill fits within budget

**PROPOSE**: The Agent writes fill code into the source file, replacing `?name`. This is an atomic operation — one hole per write. The Agent must only reference bindings visible at the hole site (as listed in `bindings`).

**VERIFY**: The `spore watch` process detects the file change, triggers incremental compilation, and emits a `compile_result` event:

```json
{
  "type": "compile_result",
  "status": "accepted" | "rejected" | "conflict",
  "hole": "validate_input",
  "diagnostics": { ... }
}
```

**ACCEPT**: Compilation succeeded. The hole is marked `filled`. The dependency graph is recalculated, possibly unlocking blocked holes. The Agent returns to DISCOVER.

**REJECT**: Compilation failed. The `compile_result` includes structured diagnostics:

```json
{
  "diagnostics": {
    "errors": [
      {
        "code": "E0301",
        "message": "type mismatch: expected Vec<ValidItem>, found Vec<RawItem>",
        "location": { "file": "src/orders.spore", "line": 18, "column": 5 },
        "suggestion": "consider using validate_items(raw_input).map(|i| i.into())"
      }
    ],
    "root_cause": "type_mismatch",
    "fix_hints": [
      "candidate validate_items returns Vec<RawItem>, not Vec<ValidItem>",
      "try: validate_items(raw_input).map(|i| i.into())"
    ]
  }
}
```

The Agent reads diagnostics, understands the failure, and autonomously decides to re-enter PROPOSE with a corrected fill or return to ANALYZE to select a different candidate.

**Design decisions:**

- **No RETRY state**: REJECT returns full diagnostics; the Agent simply re-enters PROPOSE or ANALYZE. An explicit RETRY state would add complexity without information.
- **No ESCALATE state**: If the Agent cannot fill a hole after repeated attempts, it marks it `agent_skipped`, continues with other `ready_to_fill` holes, and reports skipped holes in the final summary.

---

### Edge Cases

#### Recursive Holes

A hole in a recursive function is valid — `?name` is just an expression of some type. It does not call itself. The compiler detects recursive calls to partial functions and terminates simulation at depth 1:

```spore
fn factorial(n: Int) -> Int ! []
    cost ≤ 1000
{
    if n <= 1 { 1 }
    else { n * ?factorial_step }
}
```

Here `?factorial_step` has type `Int`. The function is partial. If a recursive call to `factorial` occurs:

```spore
fn bad(n: Int) -> Int ! []
{
    ?self_ref + bad(n - 1)   // bad is partial; recursive call also partial
}
```

The compiler reports:

```text
[partial] bad: (Int) -> Int ! []
  holes: ?self_ref
  note: recursive call to partial function bad — simulation terminates at depth 1
```

Simulation does not recurse into partial functions; it stops and emits a HoleReport at the hole site.

#### Type Holes (`?T_Name`)

Type holes are syntactically distinct from value holes. They use `?T_name` (uppercase convention) in **type positions** and represent unknown types:

```spore
fn convert(input: ?InputType) -> ?OutputType ! []
{
    ?conversion_logic
}
```

**Semantics (experimental):**

- Type holes make the entire **signature** incomplete. Unlike value holes (body-only), type holes affect the function's public contract.
- The function **cannot** be exported (its signature hash is undefined).
- The compiler emits a `type-hole` diagnostic, distinct from value-hole diagnostics.
- Type holes are a **design-time sketching tool**, not a production feature.

**Reporting:**

```text
$ sporec --holes --type-holes

Type holes:
  ?InputType   in convert (src/convert.spore:1)  — parameter type
  ?OutputType  in convert (src/convert.spore:1)  — return type

Value holes:
  ?conversion_logic  in convert (src/convert.spore:5)  — body
```

**Intended behavior:** When both type holes and value holes are present, the compiler first attempts to infer type holes from usage context (e.g., if `convert` is called with a known argument type). If inference succeeds, the value hole's expected type becomes determined. If inference fails, the value hole is reported with type `_` (unconstrained).

> **Status:** Type holes are marked experimental. The full specification is deferred to a future SEP. This section documents the intended semantics for design continuity.

#### Conflicting Constraints

When a hole has contradictory type constraints from its context, the compiler reports the conflict without failing:

```spore
fn conflicted(flag: Bool) -> Int ! []
{
    let x: String = ?ambiguous   // constraint 1: String (from let binding)
    let y: Int = x               // constraint 2: Int (from assignment)
    y
}
```

**Resolution rule:** The compiler uses the **nearest constraint** — the one syntactically closest to the hole. In this case, the `let x: String` annotation is nearest, so `?ambiguous` is reported with type `String`.

```text
warning[H0002]: hole ?ambiguous has conflicting type constraints
  constraint 1: String (from let binding on line 4)
  constraint 2: Int    (from usage on line 5)
  note: no type satisfies both constraints simultaneously.
        The hole is reported with type `String` (nearest constraint).
        Filling this hole will likely require restructuring the surrounding code.
```

The hole still appears in `--holes` output and still receives a HoleReport. The Agent sees the conflict and can propose a restructuring.

#### Holes in Closures

Closures can contain holes. The hole's context captures both the closure's own parameters and any outer bindings captured by the closure:

```spore
fn make_processor(config: Config) -> Fn(Data) -> Result ! [ProcessError]
{
    |data: Data| -> Result ! [ProcessError] {
        ?process_with_config
    }
}
```

The HoleReport for `?process_with_config` includes both the closure parameter `data` and the captured `config`:

```json
{
  "bindings": [
    { "name": "data", "type": "Data", "simulated_value": { "kind": "symbolic", "origin": "closure parameter" } },
    { "name": "config", "type": "Config", "simulated_value": { "kind": "symbolic", "origin": "captured from make_processor" } }
  ]
}
```

The `origin` field distinguishes closure parameters from captured bindings, enabling Agents to understand the binding's provenance.

#### Holes and the `pure` Property

A hole in a function inferred as `pure` (i.e., `uses []`) is itself pure by definition — it does nothing. The compiler does not flag a purity violation for the hole's presence. However, the **filling** must satisfy the purity constraint:

**Formal rule:** If function `f` has `uses []` (and is therefore inferred as `pure`), any expression that replaces a hole `?h` in `f`'s body must also be pure — it may not call functions requiring IO or State capabilities.

```spore
fn pure_fn(x: Int) -> Int ! []
{
    ?must_be_pure   // ok: hole is inert
}
```

If the Agent fills with an impure expression:

```text
[error] pure_fn is inferred as pure (uses []) but the filling of ?must_be_pure
        calls print() which requires capability: IO
```

---

## Human experience impact

### Ergonomics

- **Named holes are mandatory**. The cost of naming is low; the benefit to communication is high. "Fill `?payment_logic`" is actionable. "Fill the hole on line 42" is fragile.
- **Holes are warnings, not errors**. Code with holes compiles. Developers can run tests on completed paths while other paths remain partial.
- **Suggested filling order** is advisory, never enforced. `spore holes --suggest-order` recommends a topological order, but developers can override freely.

### CLI interface

```text
$ sporec --holes                         # list all holes
$ sporec --holes --json                  # machine-readable
$ sporec --query-hole ?name              # full HoleReport for one hole
$ sporec --query-hole ?name --json       # JSON format
$ sporec --simulate fn_name              # multi-path simulation
$ spore holes --suggest-order            # topological ordering
$ spore holes --graph                    # dependency graph visualization
$ spore fill ?name                       # Agent workflow for one hole
$ spore fill --all                       # Agent fills all holes in order
```

### Multi-path simulation

For partial functions, the compiler simulates all paths independently. A hole in one branch does not block simulation of other branches:

```text
$ sporec --simulate route

Path 1: request.method = GET  → completes normally (cost: 450)
Path 2: request.method = POST → reaches ?handle_post (HoleReport emitted)
Path 3: request.method = PUT  → reaches ?handle_put  (HoleReport emitted)
Path 4: request.method = _    → completes normally (cost: 20)

Summary: 2/4 paths complete, 2 holes encountered
```

---

## Agent experience impact

This is the central section of SEP-0005. The hole system is designed with AI Agents as a **primary consumer**, not an afterthought.

### Information Self-Sufficiency

A HoleReport v0.3 is **self-contained**. An Agent reading a report needs zero additional context to attempt a fill. The report includes:

1. **What to produce**: `type.expected` with `type.inferred_from` explaining why
2. **What is available**: `bindings` with types, simulated values, and `binding_dependencies` showing data-flow
3. **What is permitted**: `capabilities` (what the fill can call), `cost.budget_remaining` (how expensive it can be)
4. **What errors to handle**: `errors_to_handle` flat list plus `error_clusters` with per-source grouping and handling suggestions
5. **What functions might work**: `candidates` with multi-dimensional `scores`, `overall` ranking, and `adjustments`
6. **How confident the compiler is**: `confidence.type_inference` and `confidence.candidate_ranking`
7. **What depends on this hole**: `dependent_holes` (motivating fill priority)

This design eliminates the "context gathering" phase that plagues current AI coding tools. The Agent does not need to read surrounding code, navigate imports, or guess types — the compiler has already done that work.

### Scoring Vectors Enable Principled Selection

The four-dimensional scoring vector (`type_match`, `cost_fit`, `capability_fit`, `error_coverage`) enables Agents to make decisions based on numeric comparison rather than string parsing. An Agent's selection logic becomes:

```text
if confidence.candidate_ranking == "unique_best":
    select candidates[0]
elif confidence.candidate_ranking == "ambiguous":
    for each candidate in candidates:
        if candidate.scores.capability_fit == 0:
            skip  # hard constraint
        weight type_match and cost_fit by task priority
    select best by adjusted score
elif confidence.candidate_ranking == "no_candidates":
    synthesize code from bindings + type constraints
```

### Binding Dependencies Enable Data-Flow Reasoning

Without `binding_dependencies`, an Agent sees a flat list of bindings and might reference one that logically depends on another not yet computed. With the dependency graph, Agents can:

- Prefer terminal bindings (high in-degree, low out-degree) as primary inputs
- Verify that all transitive dependencies of used bindings are fully resolved
- Construct code that follows the natural data-flow direction

### Parallel Filling Protocol

Multiple Agents can fill independent holes simultaneously. The protocol is:

1. All Agents receive the same `hole_graph_update` event
2. Each Agent claims a different hole from `ready_to_fill`
3. Agents work in parallel; the compiler validates each fill independently
4. On ACCEPT, a new `hole_graph_update` unlocks blocked holes
5. Agents re-enter DISCOVER to claim newly available holes

**Conflict handling**: If two Agents attempt the same hole, the first writer wins (file-level lock). The second receives a `CONFLICT` signal and selects another hole:

```json
{
  "type": "compile_result",
  "status": "conflict",
  "hole": "validate_input",
  "message": "hole already filled by another agent"
}
```

### Failure Recovery

On REJECT, the Agent receives structured diagnostics with `root_cause` classification (`type_mismatch`, `cost_exceeded`, `capability_violation`, `error_unhandled`) and `fix_hints`. This is richer than typical compiler errors:

- `root_cause` categorization lets the Agent choose a recovery strategy without natural-language parsing
- `fix_hints` provide specific, actionable suggestions
- The original `attempt.code` is preserved for diff analysis

If an Agent fails repeatedly on a hole, it should:

1. Record all attempts and diagnostics
2. Mark the hole as `agent_skipped`
3. Continue processing other `ready_to_fill` holes
4. Include skipped holes with full diagnostics in the final report

### Real-Time Event Stream

Agents consume the NDJSON event stream from `spore watch --json`:

```text
{"type":"hole_graph_update","hole_graph":{...}}
{"type":"hole_update","hole":"validate_input","report":{...}}
{"type":"compile_result","status":"accepted","hole":"validate_input"}
{"type":"hole_graph_update","hole_graph":{...}}
```

Event types:

| Event | Trigger | Data |
|---|---|---|
| `hole_graph_update` | Startup; after each compilation | Full dependency graph, `ready_to_fill`, `blocked` |
| `hole_update` | HoleReport changed due to compilation | Hole name + full HoleReport v0.3 |
| `compile_result` | Incremental compilation completed | Status (`accepted`/`rejected`/`conflict`) + diagnostics |

Agents should consume this stream asynchronously:

```pseudocode
while line = read_line(stdin):
    event = parse_json(line)
    match event.type:
        "hole_graph_update" => update_local_graph(event.hole_graph)
        "hole_update"       => update_hole_report(event.hole, event.report)
        "compile_result"    => handle_compile_result(event)
```

### End-to-End Example: Multi-Agent Session

```text
Timeline   Agent-1                     Agent-2                     Compiler
──────────────────────────────────────────────────────────────────────────────
t0         DISCOVER                    DISCOVER                    hole_graph_update (5 holes)
           ready: [validate_input, check_auth]

t1         ANALYZE(validate_input)     ANALYZE(check_auth)         (parallel)

t2         PROPOSE: validate_order     PROPOSE: verify_token       (parallel writes)
           (order)                     (token)

t3                                                                 incremental compile

t4         ACCEPT ✓                    ACCEPT ✓                    hole_graph_update (3 remaining)
                                                                   ready: [reserve_stock, process_payment]

t5         ANALYZE(reserve_stock)      ANALYZE(process_payment)    (parallel)

t6         PROPOSE: reserve_items      PROPOSE: charge_card        (parallel writes)
           (valid.items, warehouse_id)
           ← ERROR: undefined binding!

t7         REJECT ✗                    ACCEPT ✓                    compile_result
           diagnostics: "undefined:
           warehouse_id"

t8         PROPOSE: reserve_items                                  incremental compile
           (valid.items,
            valid.warehouse_id)

t9         ACCEPT ✓                                                hole_graph_update (1 remaining)
                                                                   ready: [send_receipt]

t10        ANALYZE(send_receipt)

t11        PROPOSE: send_email(receipt, valid.email)               incremental compile

t12        ACCEPT ✓                                                hole_graph_update (0 remaining)

t13        COMMIT ── all holes filled ─────────────────────────────  ✓ done
```

---

## Structured representation / protocol impact

### JSON Output Format

All hole-related commands support `--json` for machine consumption.

**`sporec --holes --json`:**

```json
{
  "holes": [
    {
      "name": "charge_payment",
      "location": { "file": "src/orders.spore", "line": 18, "column": 5 },
      "enclosing_function": "process_order",
      "expected_type": "Response ! [PaymentFailed]",
      "capabilities": ["Inventory", "PaymentGateway"],
      "dependencies": []
    }
  ],
  "summary": {
    "total_holes": 6,
    "functions_affected": 4
  }
}
```

**`sporec --query-hole ?name --json`:** Returns the full HoleReport v0.3 structure (see §4).

**`spore watch --json`:** Emits an NDJSON event stream with `hole_graph_update`, `hole_update`, and `compile_result` events.

### Hole Dependency Graph JSON

```json
{
  "type": "hole_graph_update",
  "timestamp": "2026-03-31T12:00:00Z",
  "graph": {
    "total_holes": 8,
    "filled_holes": 3,
    "remaining_holes": 5,
    "ready_to_fill": [
      { "name": "validate_input", "file": "src/order.spore", "line": 42 },
      { "name": "check_auth", "file": "src/auth.spore", "line": 15 }
    ],
    "blocked": [
      { "name": "process_order", "blocked_by": ["validate_input", "check_auth"] },
      { "name": "send_receipt", "blocked_by": ["process_order"] }
    ],
    "edges": [
      { "from": "validate_input", "to": "process_order", "type": "value" },
      { "from": "check_auth", "to": "process_order", "type": "value" },
      { "from": "process_order", "to": "send_receipt", "type": "type" }
    ],
    "max_parallelism": 2,
    "estimated_layers": 3
  }
}
```

### LSP Integration

The hole system integrates with Language Server Protocol:

- **Diagnostics**: Holes appear as `Information`-level diagnostics (not `Error`), with the hole name and expected type in the message.
- **Code Actions**: "Fill hole `?name`" triggers the Agent workflow. "Show HoleReport" displays the JSON in a preview panel.
- **Inlay Hints**: The expected type of each hole is shown as an inlay hint.
- **Completion**: At a hole site, the completion list includes candidate functions from the HoleReport, ranked by `overall` score.
- **Code Lens**: Partial functions display a code lens showing hole count and suggested filling order.

---

## Diagnostics impact

### Hole-specific diagnostics

| Code | Severity | Message |
|---|---|---|
| `H0001` | Info | `hole ?name: expected type T` — standard hole report |
| `H0002` | Warning | `hole-type-conflict: annotation T1 conflicts with inferred T2` |
| `H0003` | Info | `partial function F depends on partial function G` |
| `H0101` | Error | `duplicate hole name ?name in module M` |
| `H0201` | Error | `hole ?name in signature position (not allowed)` |
| `H0301` | Error | `circular hole dependency: ?A → ?B → ?A` |
| `H0401` | Info | `filling of ?name revealed new hole ?other` |

### Cost diagnostics for partial functions

```text
[partial] pipeline: (Vec<Int>) -> Vec<Int> ! []
  known cost: 200 (before hole) + ≤150 (after hole) = ≤350
  budget for ?middle_step: ≤650 (1000 - 350)
  note: ?middle_step filling must have cost ≤ 650
```

### Post-fill diagnostics

On successful fill: `?name: filled ✓ (cost N)`.
On failed fill: full diagnostic with `root_cause`, `fix_hints`, and `suggestion` per error.

---

## Drawbacks

1. **Increased compiler complexity**: The hole system adds simulated execution, HoleReport generation, dependency graph construction, and incremental update logic. This is non-trivial implementation effort.

2. **Risk of "hole proliferation"**: Developers may over-use holes as a crutch, leaving too many unfilled and degrading project quality. Mitigation: CI tools can enforce maximum hole counts or block merges with unfilled holes.

3. **HoleReport size**: For complex functions, HoleReports can be large (many bindings, many candidates). This increases compiler output size and Agent processing time.

4. **Scoring weight rigidity**: The hard-coded weights (0.40, 0.20, 0.25, 0.15) may not be optimal for all projects. However, making them configurable increases cognitive burden, and the expected variance across projects is low.

5. **Hand-rolled JSON serialization**: The current implementation hand-rolls JSON serialization for v0.1 to minimize dependencies. This is intentionally simple but acknowledged as fragile for complex nested structures. serde migration is tracked as future work (see Unresolved Questions §10).

6. **Parallel fill coordination overhead**: File-level locking for multi-Agent fills adds synchronization cost. For small projects this overhead dominates the benefit.

---

## Alternatives considered

### Alternative 1: Anonymous Holes (`?`)

Rejected. Anonymous holes create ambiguity in CLI queries (`sporec --query-hole ?` with multiple holes) and prevent clear communication between human and Agent. No mainstream language with typed holes (Agda, Idris, Lean) defaults to anonymous holes in practice — users always name them.

### Alternative 2: Holes Affect Signature Hashes

Rejected. If holes changed the signature hash, downstream dependents would need recompilation every time a hole is filled — even though the *contract* never changed. This breaks snapshot stability during development.

### Alternative 3: Explicit Priority Annotations on Holes

Rejected. No mainstream dependently-typed language includes priority annotations. The compiler's dependency analysis provides a better filling order because it reflects actual data flow. Manual priority would be redundant at best and misleading at worst.

### Alternative 4: Interactive IDE Mode Instead of JSON CLI

Rejected. Agda's hole system is powerful but tightly coupled to Emacs. GHC's typed holes produce text for humans. Spore targets stateless Agents that parse structured output. JSON CLI is the natural primary interface; IDE support is layered on top.

### Alternative 5: Configurable Scoring Weights

Rejected for now. Configurable weights increase cognitive burden, and the optimal weights are unlikely to vary significantly across projects. If strong evidence emerges, a future SEP can introduce `spore.toml` configuration.

### Alternative 6: Explicit RETRY and ESCALATE States in Agent Protocol

Rejected. RETRY adds state machine complexity without new information — REJECT already returns full diagnostics, and the Agent re-enters PROPOSE or ANALYZE naturally. ESCALATE assumes human availability; the Agent protocol is designed for full autonomy with graceful degradation (`agent_skipped`).

---

## Prior art

### Agda

Agda's holes (written `?` or `{! !}`) are the closest precedent. Agda provides typed holes with goal type, context bindings, and refinement commands. Key differences from Spore:

- Agda holes are interactive (Emacs/VS Code mode); Spore holes are CLI/JSON-first
- Agda has no cost system, capability system, or scoring vectors
- Agda has no concept of parallel Agent filling
- Agda holes can appear in type positions; Spore separates type holes from value holes

### Idris 2

Idris 2's `?name` syntax directly inspired Spore's. Idris provides type-driven development with holes, case splitting, and proof search. Differences:

- Idris's hole information is consumed interactively; Spore produces self-contained JSON reports
- Idris has no dependency graph between holes
- Idris has no Agent protocol

### GHC Typed Holes

GHC's `_` syntax produces type error messages listing the expected type and bindings in scope. Differences:

- GHC typed holes are errors (compilation fails); Spore holes are valid states
- GHC output is human-readable text; Spore output is structured JSON
- GHC has no candidate ranking or scoring

### Lean 4

Lean 4's `sorry` and `_` produce goal states with the expected type and local context. Lean's tactic mode allows interactive proof construction. Differences:

- Lean is proof-oriented; Spore is software-engineering-oriented (cost, capabilities, errors)
- Lean has no cost budget or capability constraints on holes
- Lean has no parallel fill protocol

### Rust `todo!()` / TypeScript `// TODO`

These are runtime markers with no compiler support. They provide no type information, no candidate suggestions, and no structured output. Spore's holes are the typed, compiler-aware evolution of these patterns.

---

## Backward compatibility and migration

### Schema Versioning

- HoleReport v0.3 uses schema `"spore/hole-report/v2"`
- All v0.2 fields are preserved with identical semantics
- New v0.3 fields (`binding_dependencies`, `confidence`, `error_clusters`, `candidates[].scores`, `candidates[].overall`, `candidates[].adjustments`) are additive
- Tools that do not recognize v0.3 fields can safely ignore them

### CLI Flags

- `--json` flag behavior is extended, not changed
- `spore watch --json` is a new command (no existing command replaced)
- All existing `sporec --holes`, `sporec --query-hole`, `sporec --simulate` commands continue to work

### Hole Syntax

- `?name` syntax is new to Spore; no existing syntax is displaced
- `?name: Type` annotation is optional and new
- Empty function bodies desugar to `?{fn_name}_body` — this is a new behavior but affects only empty bodies (previously a parse error)

### Migration Path

1. **Existing complete code**: Unaffected. No holes means no HoleReports, no dependency graphs, no Agent protocol activation.
2. **New code with holes**: Opt-in by writing `?name` in function bodies.
3. **Agent tooling**: Agents should check `schema` version and handle both `"spore/hole-report/v1"` and `"spore/hole-report/v2"`.

---

## Unresolved questions

1. **Cross-module hole dependencies**: The current dependency graph is scoped to a single module. How should holes that depend on partial functions in other modules be represented? The `partial` marker propagates, but the graph does not yet span modules.

2. **Type holes**: This SEP covers value holes (`?name`). Type holes (`?T_Name` in uppercase positions) are mentioned but not fully specified. Should they be part of this SEP or a separate one?

3. **Scoring weight tuning**: The hard-coded weights (0.40, 0.20, 0.25, 0.15) are based on first-principles reasoning, not empirical data. Should we run experiments before finalizing?

4. **Agent identity and coordination**: The multi-Agent protocol uses file-level locking. Should Agents have explicit identities? Should there be a coordinator process, or is the decentralized claim-and-lock protocol sufficient at scale?

5. **Hole versioning**: When a hole is filled, rejected, and re-filled, should the system maintain a history of fill attempts? This would enable better Agent learning but increases storage.

6. **Partial function exports**: The current design marks partial functions in module exports. Should importers be able to depend on partial functions (receiving symbolic values), or should partial functions be hidden from external modules?

7. **DAG visualization**: The specification includes ASCII DAG output. Should a standard visual format (DOT/Graphviz, Mermaid) be part of the protocol?

8. **Dynamic priority adjustment**: Should the filling order adapt based on Agent performance history (e.g., prioritize holes similar to ones the Agent has successfully filled before)?

9. **Cost dependency precision**: Cost dependencies currently assume sequential execution within a block. For branches, should cost dependencies be path-sensitive?

10. **serde migration**: The hand-rolled JSON serializer should eventually be replaced. When should this migration happen, and should it be a breaking change to the internal API?
