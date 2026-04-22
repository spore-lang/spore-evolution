---
sep: 7
title: "SEP-0007: Concurrency Model"
status: Draft
type: Standards Track
authors:
  - Spore maintainers
created: 2026-03-31
requires:
  - 1
  - 3
  - 4
discussion: "https://github.com/spore-lang/spore-evolution/discussions/7"
pr: null
superseded_by: null
---

# SEP-0007: Concurrency Model

> **Executive Summary**: Defines structured concurrency with `spawn`/`await`/`select` primitives, where `Task[T]` serves as a typed future representing an asynchronous computation. Introduces Lanes as the parallel cost dimension (tracked in CostVector), hierarchical cancellation scoping tied to lexical blocks, and channel-based communication (Channel[T]) with bounded buffers for inter-task messaging.

## Summary

This proposal defines the concurrency model for the Spore programming language. The model is built on four pillars:

1. **Structured concurrency** — all concurrent tasks form a tree rooted in `parallel_scope`; no raw thread spawning, no `GlobalScope` escape hatches.
2. **Effect handlers** — `Spawn` is a standard effect, not a keyword. Different handlers provide real parallelism, sequential testing execution, or compile-time cost simulation—without changing user code.
3. **Effect narrowing** — a child task's effect set must be a subset of its parent's (`child.uses ⊆ parent.uses`), enforced at compile time.
4. **Cost budgets with a parallel dimension** — the cost model gains a fourth dimension `parallel(lane)` that the compiler statically tracks and verifies.

The core formula is:

```text
Spore Concurrency = Koka Effects + Kotlin Structured Scoping
                  + Zig Explicit Resources + Spore Cost Budgets
```

The design unifies five properties that no existing language achieves simultaneously:

| Property | Meaning | Beneficiary |
|----------|---------|-------------|
| **Colorless functions** | Concurrency does not introduce `async`/`await` syntax bifurcation | All developers |
| **Structured lifetimes** | Child tasks cannot escape the parent scope | Resource management, debugging |
| **Explicit effects** | Concurrent tasks may only use declared effects | Security audits |
| **Bounded cost** | Compiler statically verifies `cost ≤ N` and `parallel(lane)` | Performance predictability |
| **Simulatable execution** | Handlers are replaceable—same code compiles to simulation / deterministic test / production parallel | Agents, CI |

---

## Motivation

### Why structured concurrency

Traditional concurrency models—raw threads, unbounded `goroutine` spawning, `GlobalScope.launch`—share a common flaw: **concurrent tasks form an arbitrary directed graph whose lifetime is unmanageable at compile time**. This leads to:

- **Resource leaks**: A spawned task outlives its creator, holding file handles or network connections the parent assumed were released.
- **Unanalyzable cost**: Fire-and-forget tasks are invisible to the compiler's cost model. If `cost ≤ N` is declared in the function signature but the function spawns background work that escapes the scope, the declared bound is meaningless.
- **Debugging nightmares**: Stack traces of escaped tasks lose the causal chain to their spawning point, making production incidents harder to diagnose.

Structured concurrency, as articulated by Nathaniel J. Smith (*"Go statement considered harmful"*, 2018), solves these problems by enforcing **tree-shaped task lifetimes**: every child task is nested inside a scope that does not exit until all children have completed (or been cancelled). In Spore this means:

1. **Nursery rule** — all concurrent tasks must be spawned inside a `parallel_scope`.
2. **Parent waits for children** — `parallel_scope` does not return until every child task has completed.
3. **Cancellation propagates downward** — cancelling a parent recursively cancels all its children.
4. **Errors propagate upward** — a child exception bubbles to the parent scope and cancels remaining siblings.
5. **Resource safety** — because children always finish before the scope exits, `defer` cleanup is always effective.

### Why no raw threads

Raw threads are excluded for fundamental reasons:

- They bypass the effect system: any thread can perform any operation.
- They make cost analysis intractable: the compiler cannot statically enumerate an unbounded thread graph.
- They conflict with Spore's philosophy of *"the compiler sees everything"*.

### Why not async/await

Bob Nystrom's *"What Color is Your Function?"* (2015) identified how `async` splits functions into two colors—red (async) and blue (sync)—where red can only be called from red contexts, causing a viral coloring of the entire call chain. Spore takes a different path: **concurrency is an effect declared in the `uses` clause**. Effect-polymorphic functions are naturally colorless.

```spore
// No async annotation needed—concurrency declared via the Spawn effect
fn fetch_all(urls: List[Url]) -> List[Response] ! NetError
cost ≤ urls.len * per_fetch
uses [Spawn, NetConnect]
{
    parallel_scope {
        urls.map(|url| spawn { fetch(url) })
            .map(|task| task.await)
    }
}

// Pure function: no Spawn, no IO—compiler guarantees single-threaded
fn transform(data: List[Item]) -> List[Item]
cost ≤ data.len * 3
{
    data.map(|item| item.process())
}
```

Both functions use identical call syntax—no red/blue distinction. The concurrency behavior of `fetch_all` is determined entirely by the handler bound at the call site.

---

## Guide-level explanation

This section introduces the concurrency primitives through progressive examples.

Concrete surface syntax for `parallel_scope`, `spawn`, `select`, and `handle ... with` is centralized in SEP-0001. This SEP uses examples to explain concurrency behavior, but the grammar itself should be read there.

### 3.1 `parallel_scope` — the concurrency entry point

`parallel_scope` is the **only** way to introduce concurrency in Spore. There is no `GlobalScope`, no `thread::spawn`, no detached background tasks in user code.

```spore
// Basic form: spawn two computations in parallel
parallel_scope {
    let a = spawn { compute_part1() }
    let b = spawn { compute_part2() }
    (a.await, b.await)
}
```

The block is an expression; its value is the last expression in the body. When the block exits, every spawned task has either completed or been cancelled.

Because `parallel_scope` is an expression, it can return structured results assembled from spawned tasks:

```spore
fn load_dashboard(user_id: UserId) -> Dashboard ! DbError | NetError
uses [Spawn, NetConnect, DbRead]
{
    // parallel_scope returns the Dashboard struct directly
    parallel_scope {
        let profile = spawn { db.get_profile(user_id) }
        let feed    = spawn { api.get_feed(user_id) }
        let notifs  = spawn { api.get_notifications(user_id) }
        Dashboard {
            profile: profile.await,
            feed: feed.await,
            notifications: notifs.await,
        }
    }
}
```

An optional `lanes` parameter limits the degree of parallelism:

```spore
parallel_scope(lanes: 4) {
    data.chunks(4).each(|chunk| {
        spawn { process_chunk(chunk) }
    })
}
```

### 3.2 `spawn` — creating child tasks

`spawn` launches a child task inside the current `parallel_scope` and returns a `Task[T]`:

```spore
let task: Task[Response] = spawn { fetch(url) }
let response: Response = task.await
```

`spawn` is **not** a standalone statement—it is always bound to an enclosing `parallel_scope`. Any `Task` not awaited when the scope exits is automatically cancelled.

Effect narrowing is available at the spawn site:

```spore
let task = spawn uses [NetConnect] { fetch(url) }
// The spawned task can only use NetConnect; it cannot itself spawn.
```

### 3.3 `Task[T]` — task handle API

`spawn` returns a `Task[T]` handle. The complete API:

| Method/Property | Type | Description |
|-----------------|------|-------------|
| `task.await` | `T ! child errors` | Block until the task completes and return its result |
| `task.cancel()` | `Unit` | Request cooperative cancellation of the task |
| `task.is_done` | `Bool` | `true` if the task has completed (successfully or with error) |
| `task.is_cancelled` | `Bool` | `true` if the task was cancelled |

Usage examples:

```spore
fn selective_fetch(urls: List[Url]) -> Response ! NetError
uses [Spawn, NetConnect]
{
    parallel_scope {
        let primary   = spawn { fetch(urls.head()) }
        let secondary = spawn { fetch(urls.get(1)) }

        // Wait for the primary; cancel secondary if primary succeeds
        let result = primary.await
        if !secondary.is_done {
            secondary.cancel()
        }
        result
    }
}
```

> **Note:** `task.cancel()` is rarely needed in user code—the structured scope automatically cancels unawaited tasks on exit. Explicit cancellation is useful for "first result wins" patterns.

### 3.4 Channels — communication between tasks

Channels implement CSP-style message passing: *"Don't communicate by sharing memory; share memory by communicating."*

```spore
// Buffered channel
let (tx, rx) = Channel.new[Message](buffer: 10)

// Unbuffered (synchronous) channel
let (tx, rx) = Channel.new[Message](buffer: 0)
```

`Channel.new` returns a pair `(Sender[T], Receiver[T])`:

| Type | Operation | Blocking behavior |
|------|-----------|-------------------|
| `Sender[T]` | `tx.send(value)` | Suspends when buffer is full |
| `Receiver[T]` | `rx.recv()` | Suspends when buffer is empty |

The `select` expression waits on multiple channels simultaneously:

```spore
select {
    msg from rx1 => handle_message(msg),
    msg from rx2 => handle_command(msg),
    timeout(5.seconds) => handle_timeout(),
}
```

### 3.4 Effect handlers for concurrency control

Because `Spawn` is an effect, different handlers give the same code different runtime behavior:

```spore
// Production: real parallel execution on a thread pool
handle {
    concurrent_work()
} with {
    use ParallelHandler { pool: thread_pool }
}

// Testing: deterministic sequential execution
handle {
    concurrent_work()
} with {
    use SequentialHandler {}
}

// Compile-time simulation: abstract interpretation for cost analysis
handle {
    concurrent_work()
} with {
    use CostAnalysisHandler {}
}
```

A test can replace the `Spawn` handler with `SequentialHandler` and a `NetConnect` handler with a mock—**no async test framework needed**:

```spore
test "fetch_and_merge produces correct results" {
    let mock_net = MockNetHandler {
        responses: Map.from([
            (url1, response1),
            (url2, response2),
        ])
    }

    let result = handle {
        fetch_and_merge([url1, url2])
    } with {
        use SequentialHandler {}
        use mock_net
    }

    assert_eq(result, expected_merged)
}
```

### 3.5 `map` and pure closures

`map` only accepts **pure** closures (capture list `[]`). This ensures that mapping over a collection never accidentally introduces side effects. For effectful parallel iteration, use `parallel_scope + spawn`:

```spore
// Pure: map with a pure closure (no effects, no captures)
let doubled = numbers.map(|x| x * 2)

// Effectful parallel: use parallel_scope + spawn
let responses = parallel_scope {
    urls.map(|url| spawn { fetch(url) })
        .map(|task| task.await)
}
```

### 3.6 Recursive patterns instead of loops

Spore has no imperative loops. Concurrency patterns that traditionally use loops are expressed through recursion and higher-order functions:

```spore
fn event_loop(
    commands: Receiver[Command],
    events: Receiver[Event],
    shutdown: Receiver[Unit],
) -> Unit ! ChannelClosed
uses [ChanRecv[Command], ChanRecv[Event], ChanRecv[Unit], Spawn]
{
    select {
        cmd from commands => {
            execute(cmd)
            event_loop(commands, events, shutdown)  // tail-recursive
        },
        evt from events => {
            log_event(evt)
            event_loop(commands, events, shutdown)
        },
        _ from shutdown => {
            Unit  // base case
        },
        timeout(30.seconds) => {
            heartbeat()
            event_loop(commands, events, shutdown)
        },
    }
}
```

### 3.7 Complete example: HTTP request handler

Server entrypoints that accept inbound connections declare `NetListen`; the inner request handler below only needs outbound `NetConnect` plus domain-specific effects.

```spore
effect HttpHandler = Spawn | NetConnect | DbRead | Clock

fn handle_request(req: Request) -> Response ! DbError | Timeout
cost ≤ 5000
uses [HttpHandler]
{
    with_timeout(10.seconds) {
        parallel_scope(lanes: 3) {
            let auth   = spawn uses [DbRead]  { verify_token(req.token) }
            let user   = spawn uses [DbRead]  { load_user(req.user_id) }
            let config = spawn uses [NetConnect]  { fetch_remote_config() }

            let auth_result = auth.await
            if !auth_result.valid {
                return Response.unauthorized()
            }

            Response.ok(
                render_page(user.await, config.await)
            )
        }
    }
}
```

### 3.8 Complete example: ETL pipeline

```spore
fn etl_pipeline(
    source: DataSource,
    sink: DataSink,
    batch_size: Int,
) -> EtlReport ! ExtractError | TransformError | LoadError
cost ≤ batch_size * 200
uses [Spawn, NetConnect, DbRead, DbWrite]
{
    let (raw_tx, raw_rx)     = Channel.new[RawRecord](buffer: batch_size)
    let (clean_tx, clean_rx) = Channel.new[CleanRecord](buffer: batch_size)

    parallel_scope(lanes: 6) {
        // Extract: 1 lane
        let extractor = spawn uses [NetConnect] {
            source.stream().each(|record| raw_tx.send(record))
            raw_tx.close()
        }

        // Transform: 4 lanes (fan-out)
        (0..4).each(|_| {
            spawn {
                raw_rx.each(|raw| {
                    match transform(raw) {
                        Ok(clean) => clean_tx.send(clean),
                        Err(e)    => log_error(e),
                    }
                })
            }
        })

        // Load: 1 lane (fan-in)
        let loader = spawn uses [DbWrite] {
            clean_rx.fold(0, |count, record| {
                sink.write(record)
                count + 1
            })
        }

        extractor.await
        clean_tx.close()
        let loaded = loader.await

        EtlReport { records_loaded: loaded }
    }
}
```

---

## Reference-level explanation

### 4.1 Structured concurrency model

#### Task tree

Every `parallel_scope` creates a nursery node; every `spawn` attaches a leaf:

```text
main()
 └─ parallel_scope            ← nursery A
     ├─ spawn { fetch(url1) }     ← task A1
     ├─ spawn { fetch(url2) }     ← task A2
     └─ spawn {                   ← task A3
           parallel_scope         ← nursery B (nested)
            ├─ spawn { parse(d1) }    ← task B1
            └─ spawn { parse(d2) }    ← task B2
         }
```

The compiler builds this static task tree at compile time and uses it for:

- Cost budget allocation verification
- Effect set inheritance checking
- Lane consumption calculation

#### `parallel_scope` formal semantics

```text
⟦parallel_scope { e }⟧ =
    let nursery = Nursery.new()
    let result = ⟦e⟧ with nursery
    nursery.await_all()
    result

⟦parallel_scope(lanes: K) { e }⟧ =
    let nursery = Nursery.new(max_lanes: K)
    let result = ⟦e⟧ with nursery
    nursery.await_all()
    result
```

Invariants:

- `parallel_scope` is an expression; its type is the type of its body's last expression.
- The scope blocks until all children complete or are cancelled.
- Nested `parallel_scope` blocks form a tree; the inner scope consumes lanes from the outer scope's budget.

#### `spawn` formal semantics

```text
⟦spawn { e }⟧ =
    let task = nursery.register(thunk: λ(). ⟦e⟧)
    nursery.schedule(task)
    task : Task[T]   where e : T
```

Constraints:

- `spawn` may only appear lexically inside a `parallel_scope`.
- The enclosing function must declare `uses [Spawn]`.
- Effect narrowing: `spawn uses [C₁, C₂] { e }` requires `{C₁, C₂} ⊆ parent.uses`.

#### Error propagation

Two modes are supported:

| Mode | On child failure | Return type | Use case |
|------|-----------------|-------------|----------|
| `fail_fast` (default) | Cancel siblings, propagate error | `T ! E` | All child results are required |
| `collect` | Do not cancel siblings; collect results | `Result[T, E]` per task | Partial results are meaningful |

```spore
// fail_fast (default)
parallel_scope {
    let a = spawn { fetch(url1) }  // if this throws NetError…
    let b = spawn { fetch(url2) }  // …b is cancelled
    (a.await, b.await)  // scope propagates NetError upward
}

// collect (supervisor mode)
parallel_scope(on_error: .collect) {
    let a = spawn { fetch(url1) }
    let b = spawn { fetch(url2) }
    match (a.await, b.await) {
        (Ok(r1), Ok(r2)) => (r1, r2),
        (Err(e), _) | (_, Err(e)) => handle_partial_failure(e),
    }
}
```

### 4.2 Effect handlers for concurrency

#### `Spawn` as an effect

`Spawn` is defined as a standard effect, not compiler magic:

```spore
// Built-in effect definition (conceptual; provided by Platform)
effect Spawn {
    fn spawn[T](task: () -> T) -> Task[T]
}
```

Functions declare the effect via `uses [Spawn]`. Without this declaration, the compiler **statically rejects** any call to `spawn`.

#### Handler mechanism

An effect handler is a concrete interpretation of an effect's operations:

```spore
handle {
    concurrent_work()
} with {
    use ParallelHandler { pool: thread_pool }
}
```

#### Built-in handlers

The Platform provides the following `Spawn` handlers:

| Handler | Behavior | Use case |
|---------|----------|----------|
| `ParallelHandler(pool)` | Real OS thread / green thread parallelism | Production |
| `SequentialHandler` | Executes spawned tasks sequentially in spawn order | Unit testing |
| `DeterministicHandler(seed)` | Fixed scheduling order, replayable | Regression testing, CI |
| `CostAnalysisHandler` | Abstract execution, computes cost | Compile-time simulation |
| `TracingHandler(inner)` | Wraps any handler, records event timeline | Debugging, profiling |

#### Custom effects and handlers

Users may define their own concurrency-related effects:

```spore
effect RateLimit {
    fn acquire_permit() -> () ! RateLimitExceeded
    fn release_permit() -> ()
}

handler RateLimit as token_bucket_handler(rate: Int, per: Duration) {
    fn acquire_permit() -> () ! RateLimitExceeded {
        if self.tokens > 0 {
            self.tokens -= 1;
            ()
        } else {
            throw RateLimitExceeded
        }
    }
    fn release_permit() -> () {
        self.tokens += 1;
        ()
    }
}
```

#### Relationship between effects and the `uses` clause

| Dimension | `uses [...]` clause | `effect` definition |
|-----------|--------------------------|----------------------|
| Definition layer | Signature metadata, compiler-verified | Declares operations interceptable by a handler |
| Semantics | "What effects this function may perform" | "What operations this effect provides" |
| Verification | Compile-time effect set check | Compile-time + handler binding time |
| Example | `uses [Spawn]` permits calling `spawn` | `effect Spawn { fn spawn... }` defines the operation |

Declaring `uses [Spawn]` means "this function may perform the `Spawn` effect". The `effect` keyword defines both the operations and makes the effect available for use in `uses` clauses.

### 4.3 Channel types

#### `Channel[T]`

```spore
// Buffered
let (tx, rx) = Channel.new[Message](buffer: 10)

// Unbuffered (synchronous handoff)
let (tx, rx) = Channel.new[Message](buffer: 0)
```

#### Channel operations as effects

```spore
effect ChanSend[T] {
    fn send(value: T) -> Unit ! ChannelClosed
}

effect ChanRecv[T] {
    fn recv() -> T ! ChannelClosed
}
```

Functions using channels must declare the corresponding effects:

```spore
fn producer(tx: Sender[Int]) -> Unit ! ChannelClosed
uses [ChanSend[Int]]
{
    (0..100).each(|i| tx.send(i))
}

fn consumer(rx: Receiver[Int]) -> List[Int] ! ChannelClosed
uses [ChanRecv[Int]]
{
    rx.collect()
}
```

#### `select` expression

```spore
select {
    msg from rx1 => handle_message(msg),
    msg from rx2 => handle_command(msg),
    timeout(5.seconds) => handle_timeout(),
}
```

Semantics:

- `select` waits on all branches simultaneously.
- When multiple branches are ready, the scheduler picks one (non-deterministic).
- `timeout` is a built-in special branch that fires after the given duration.
- `select` is an expression—all branches must return the same type.

#### Channel closure semantics

| Operation | Behavior when channel is closed |
|-----------|---------------------------------|
| `tx.send(value)` | Returns `Err(ChannelClosed)` |
| `rx.recv()` | Returns buffered value if available; otherwise `Err(ChannelClosed)` |
| `tx.close()` | Marks the sender end as closed |
| `rx.each(\|msg\| ...)` | Iterates until channel is closed and buffer is drained |

#### Fan-out / Fan-in patterns

`tx.clone()` creates an additional sender for the same channel. When all senders are closed, the channel closes automatically (reference-counted semantics).

### 4.4 Cost budgets for parallel work

#### The `parallel(lane)` dimension

The cost model (SEP-0004) defines four dimensions. This SEP defines the semantics of the fourth:

| Dimension | Abbreviation | Unit | Meaning |
|-----------|-------------|------|---------|
| Compute | `C` | op | CPU operation steps |
| Allocation | `A` | cell | Heap memory allocations |
| IO | `W` | call | External call count |
| **Parallel** | **`P`** | **lane** | **Concurrent execution channels** |

`lane` is a logical concept—it does not directly equal an OS thread or CPU core. It is a unit of concurrency that the compiler can statically track.

#### Cost combination rules

**Sequential execution:**

```text
cost(A ; B) = cost(A) + cost(B)         -- C, A, W dimensions: sum
parallel(A ; B) = max(A.P, B.P)         -- P dimension: peak
```

**Parallel execution (inside `parallel_scope`):**

```text
cost(parallel { A, B }) = max(cost(A), cost(B))   -- C, A, W: max (wall-clock)
parallel(parallel { A, B }) = A.P + B.P            -- P: sum (concurrent resources)
```

Intuition: wall-clock time of parallel tasks is determined by the slowest branch (`max`), but the concurrent resources consumed are the sum across branches.

**Spawn overhead:**

```text
cost(spawn { body }) = spawn_overhead + cost(body)
    where spawn_overhead = 5 op + 1 cell    -- constant, configurable in spore.toml
```

#### Lane inference rules

The compiler infers lane requirements automatically:

1. No `Spawn` → `P = 0` (purely sequential)
2. `parallel_scope { spawn × N }` → `P = N` (all N spawns execute in parallel)
3. `parallel_scope(lanes: K) { spawn × N }` → `P = min(K, N)` (upper bound applied)
4. Sequential scopes: `P = max(P_scope₁, P_scope₂)` (peak across sequential phases)
5. Nested parallel children: `P = sum(P_children)` (sum within a single parallel scope)

Developers need not manually allocate lanes. The compiler infers from the task tree and function signatures. An optional `lanes: K` parameter on `parallel_scope` sets a hard upper limit; excess spawns queue.

#### Lane budget allocation across nested scopes

```spore
fn pipeline(data: Data) -> Result
cost ≤ 5000
uses [Spawn, FileRead, NetConnect]
{
    // Phase 1: 4 lanes
    let prepared = parallel_scope(lanes: 4) {
        let a = spawn { parse_part1(data) }
        let b = spawn { parse_part2(data) }
        let c = spawn { parse_part3(data) }
        let d = spawn { validate(data) }
        merge(a.await, b.await, c.await, d.await)
    }
    // Phase 1 exits; 4 lanes released

    // Phase 2: 2 lanes
    parallel_scope(lanes: 2) {
        let uploaded = spawn { upload(prepared) }
        let logged   = spawn { log_result(prepared) }
        (uploaded.await, logged.await)
    }

    // Compiler infers: peak lanes = max(4, 2) = 4
}
```

#### Symbolic cost expressions for dynamic lanes

When the number of spawned tasks depends on runtime values, the compiler uses **symbolic cost expressions**:

```spore
fn fetch_all(urls: List[Url]) -> List[Response] ! NetError
cost ≤ urls.len * per_fetch
uses [Spawn, NetConnect]
{
    parallel_scope {
        urls.map(|url| spawn { fetch(url) })
            .map(|task| task.await)
    }
}
```

```bash
$ sporec --query-cost fetch_all
{
  "function": "fetch_all",
  "cost_symbolic": "urls.len × (5 + per_fetch) + urls.len",
  "parallel_lanes": "urls.len",
  "note": "lane count depends on runtime urls.len; no static upper bound"
}
```

To make the cost statically verifiable, use a **refinement type** to limit the input size:

```spore
fn bounded_fetch(urls: List[Url, max: 100]) -> List[Response] ! NetError
cost ≤ 100 * per_fetch + 500
uses [Spawn, NetConnect]
{
    parallel_scope(lanes: 10) {
        // At most 10 parallel tasks; remaining queue
        urls.each(|url| spawn { fetch(url) })
    }
}
```

```bash
$ sporec --query-cost bounded_fetch
{
  "function": "bounded_fetch",
  "cost_upper": "100 × per_fetch + 500",
  "cost_declared": "≤ 100 * per_fetch + 500",
  "status": "within_bound",
  "parallel_lanes_peak": 10,
  "note": "urls.len ≤ 100 (refinement); lanes capped at 10"
}
```

#### Cost query output

```bash
$ sporec --query-cost pipeline
{
  "function": "pipeline",
  "cost_scalar": 4200,
  "cost_declared": "≤ 5000",
  "status": "within_bound",
  "dimensions": {
    "compute": 3800,
    "alloc": 45,
    "io": 3,
    "parallel_lanes_peak": 4
  },
  "breakdown": [
    {
      "scope": "parallel_scope#1",
      "lanes": 4,
      "wall_cost": 1200,
      "children": [
        { "task": "parse_part1", "cost": 1000 },
        { "task": "parse_part2", "cost": 1200 },
        { "task": "parse_part3", "cost": 900 },
        { "task": "validate",    "cost": 800 }
      ]
    },
    {
      "scope": "parallel_scope#2",
      "lanes": 2,
      "wall_cost": 2600,
      "children": [
        { "task": "upload",     "cost": 2600 },
        { "task": "log_result", "cost": 400 }
      ]
    }
  ]
}
```

#### Interaction with the hole system

Holes in concurrent functions participate in cost budget analysis:

```spore
fn concurrent_pipeline(data: Data) -> Result
cost ≤ 3000
uses [Spawn, NetConnect]
{
    parallel_scope(lanes: 2) {
        let a = spawn { fetch(data.url) }  // cost: 800
        let b = spawn { ?process_logic }  // hole: remaining budget
        merge(a.await, b.await)
    }
}
```

The compiler reports:

```json
{
  "hole": "process_logic",
  "cost_consumed": 800,
  "cost_budget_remaining": 2200,
  "parallel_context": {
    "scope_lanes": 2,
    "lane_index": 1,
    "sibling_costs": [800]
  },
  "note": "This hole runs in lane 1 of a 2-lane parallel_scope; cost must not exceed 2200"
}
```

### 4.5 Cancellation semantics

#### Propagation direction

Cancellation flows **top-down** through the task tree, complementing the **bottom-up** direction of error propagation:

```text
Error propagation:       child → parent  (bubbles up)
Cancellation propagation: parent → child  (cascades down)
```

**Nested scope cancel propagation example:**

```spore
parallel_scope {                              // scope A
    let a = spawn { long_running_1() }        // task A1
    let b = spawn {                           // task A2
        parallel_scope {                      // scope B (nested)
            let c = spawn { subtask_1() }     // task B1
            let d = spawn { subtask_2() }     // task B2
            (c.await, d.await)
        }
    }
    (a.await, b.await)
}
```

When scope A is cancelled, the 4-step propagation:

| Step | Action | Result |
|------|--------|--------|
| 1 | Scope A receives cancel signal | Sets cancel flag on A1 and A2 |
| 2 | Task A1 checks cancel at next effect call | A1 raises `Cancelled`, begins cleanup (`defer` blocks run) |
| 3 | Task A2 propagates cancel to nested scope B | Scope B sets cancel flag on B1 and B2 |
| 4 | Tasks B1 and B2 check cancel at next effect call | B1, B2 raise `Cancelled`; scope B exits; scope A exits |

All `defer` blocks execute in reverse order at each level. The entire tree unwinds deterministically.

#### Cooperative cancellation

Spore uses **cooperative** cancellation. Tasks are never forcibly terminated. Instead, they check for cancellation at two kinds of points:

1. **Effect operation sites** — every effect call (`fetch`, `send`, `recv`, etc.) passes through a handler that checks the cancellation flag before resuming. This is a zero-cost interception point.
2. **Explicit checkpoints** — CPU-bound code without effect calls must manually insert `check_cancelled()`:

```spore
fn cpu_bound_work(data: List[Item]) -> List[Item]
uses [Spawn]
{
    data.enumerate().fold([], |results, (i, item)| {
        // CPU-bound code needs manual cancellation checkpoints
        if i % 100 == 0 {
            check_cancelled()  // throws Cancelled if cancellation was requested
        }
        results.push(transform(item))
        results
    })
}
```

The compiler may emit a warning when it detects a long iterative computation with no cancellation checkpoint.

#### `defer` and cancellation

`defer` blocks execute even during cancellation, guaranteeing resource cleanup:

```spore
fn with_temp_file() -> Data ! IoError | Cancelled
uses [Spawn, FileRead, FileWrite]
{
    let file = create_temp_file()
    defer { delete_file(file) }  // executes on cancellation too

    write_data(file, generate_large_data())
    read_and_process(file)
}
```

#### Timeout as cancellation

`with_timeout` is syntactic sugar over cancellation:

```spore
fn fetch_with_timeout(url: Url, limit: Duration) -> Response ! NetError | Timeout
uses [Spawn, NetConnect, Clock]
{
    with_timeout(limit) {
        fetch(url)
    }
}
```

Internally, `with_timeout` spawns a timer task and the main task in a scope; whichever completes first wins—if the timer fires first, the main task is cancelled.

#### Cancellation semantics summary

| Scenario | Behavior |
|----------|----------|
| Parent scope is cancelled | All child tasks receive cancellation signal |
| Child task at an IO effect point | Handler checks cancellation flag, throws `Cancelled` |
| Child task in pure computation | Must manually call `check_cancelled()` in loops |
| `defer` blocks | Execute normally during cancellation for resource cleanup |
| Already-completed task is "cancelled" | No-op; result is already available |
| `select` waiting when cancelled | All branches are abandoned; `Cancelled` is thrown |

---

## Human experience impact

### Simplified mental model

Developers only need to learn one concurrency pattern: **`parallel_scope` + `spawn`**. There is no zoo of primitives (`Thread`, `ExecutorService`, `async`/`await`, `Future`, `Promise`, `Task.Run`, `go`, `select`, `WaitGroup`, etc.). The structured tree model mirrors the already-familiar function call tree.

### No function coloring

In languages with `async`/`await`, developers must decide at every function boundary whether the function is async or sync—and refactoring between the two modes is a breaking change that propagates through the call graph. In Spore, a function that uses concurrency simply declares `uses [Spawn]` in its signature. Callers do not need to be "async" themselves; they just need to provide a `Spawn` handler (which is typically provided at the application boundary).

### Testability

The replaceable handler model means concurrent code can be tested with `SequentialHandler` for fully deterministic execution. No special async test framework or runtime is required. Mock handlers for IO effects combine naturally with sequential spawn handlers.

### Readable error messages

Because the task tree mirrors the lexical scope tree, error messages and stack traces preserve the full causal chain from the spawning point to the failure point. This eliminates the "lost context" problem common in fire-and-forget concurrency.

### Explicit effects as documentation

When a function signature says `uses [Spawn, NetConnect]`, a human reader immediately knows the function is concurrent and performs outbound network access. This serves as machine-checked documentation.

---

## Agent experience impact

### Deterministic simulation

AI agents benefit enormously from being able to run concurrent code in a deterministic mode. `DeterministicHandler(seed)` replays the exact same scheduling order, enabling agents to:

- Predict outputs of concurrent functions.
- Build reliable test expectations.
- Reproduce and diagnose failures.

### Structured cost budgets

Agents can use `sporec --query-cost` to obtain the parallel lane usage and total cost of any function. This structured JSON output is directly consumable and enables agents to:

- Verify that concurrent code stays within budget before deployment.
- Suggest lane count optimizations.
- Identify bottleneck tasks in a parallel scope.

### Code generation

The constrained concurrency model (`parallel_scope` + `spawn` only, no raw threads) makes it significantly easier for agents to generate correct concurrent code. The structured scoping rules eliminate entire classes of concurrency bugs (leaked tasks, use-after-free in concurrent contexts) that agents are otherwise prone to producing.

### Effect narrowing for safe delegation

When an agent generates a spawned task, it can narrow the effect set (`spawn uses [NetConnect] { ... }`), providing a compile-time guarantee that the generated subtask cannot exceed its intended permissions—a form of least-privilege that is checkable at compile time.

---

## Structured representation / protocol impact

### Task tree as data

The static task tree is available as a structured query:

```bash
$ sporec --query-task-tree handle_request
{
  "root": "handle_request",
  "scopes": [
    {
      "id": "parallel_scope#1",
      "lanes": 3,
      "children": [
        { "task": "verify_token", "uses": ["DbRead"], "cost": 600 },
        { "task": "load_user",    "uses": ["DbRead"], "cost": 800 },
        { "task": "fetch_remote_config", "uses": ["NetConnect"], "cost": 1200 }
      ]
    }
  ]
}
```

### Handler binding as protocol

At the application boundary (the `main` function or service entry point), handler binding forms a protocol specification: *"this application uses real parallelism with a pool of N threads, real network IO, and PostgreSQL for database"*. This binding can be serialized and versioned as part of the deployment configuration.

### Integration with Spore subsystems

| Spore subsystem | Interaction with the concurrency model |
|-----------------|---------------------------------------|
| Signature syntax | `uses [Spawn, ...]` declares concurrency effect; `cost ≤ N` bounds total cost |
| Cost model | Fourth dimension `parallel(lane)` defined by this SEP |
| Effect system | `Spawn` is a built-in effect; child task effects ⊆ parent |
| Effect annotations | `pure` excludes `Spawn`; `deterministic` + `Spawn` requires schedule-independent results |
| Hole system | Concurrent holes participate in cost budget analysis |
| Platform | Platform provides production `Spawn` handler implementations |

---

## Diagnostics impact

### Compile-time diagnostics

The compiler reports the following concurrency-related diagnostics:

| Diagnostic | Severity | Example |
|------------|----------|---------|
| `spawn` outside `parallel_scope` | Error | `spawn { ... }` at top level |
| Missing `Spawn` effect | Error | Function calls `spawn` but does not declare `uses [Spawn]` |
| Lane budget exceeded | Error | `parallel_scope(lanes: 2)` with 5 spawns that cannot queue |
| Cost budget exceeded due to parallelism | Error | Inferred parallel cost exceeds declared `cost ≤ N` |
| Long recursion/iteration without cancellation checkpoint | Warning | CPU-bound computation > 100 iterations without `check_cancelled()` |
| Effect widening in spawn | Error | `spawn uses [NetConnect] { ... }` when parent lacks `NetConnect` |
| Unused `Task` (never awaited, never cancelled) | Warning | Task result is silently discarded |

### Runtime diagnostics

The `TracingHandler` wraps any spawn handler and records a structured event timeline:

```json
[
  { "event": "scope_enter", "id": "ps#1", "lanes": 4, "time_ns": 0 },
  { "event": "spawn", "task": "parse_part1", "parent": "ps#1", "time_ns": 12 },
  { "event": "spawn", "task": "parse_part2", "parent": "ps#1", "time_ns": 15 },
  { "event": "complete", "task": "parse_part1", "cost": 1000, "time_ns": 5200 },
  { "event": "complete", "task": "parse_part2", "cost": 1200, "time_ns": 6100 },
  { "event": "scope_exit", "id": "ps#1", "time_ns": 6105 }
]
```

This timeline can be rendered as a Gantt chart, flame graph, or task dependency graph for performance analysis.

---

## Drawbacks

1. **No escape hatch for long-lived background tasks.** Structured concurrency requires all tasks to complete within their scope. Long-lived background tasks (e.g., a metrics reporter, a heartbeat sender) must be managed through the Platform layer rather than user-level `spawn`. This adds complexity to the Platform interface.

2. **Cooperative cancellation has latency.** CPU-bound tasks that forget to insert `check_cancelled()` will not respond to cancellation promptly. While the compiler warns about this, the warning is heuristic-based and may produce false negatives.

3. **No shared-memory primitives.** The absence of `Mutex`/`RwLock`/atomics means certain high-performance patterns (lock-free data structures, atomic counters) are not directly expressible. These must be provided as `unsafe` Platform primitives if needed.

4. **Effect handler overhead.** Algebraic effect handlers, particularly those involving continuations, may have non-trivial runtime overhead compared to direct `async`/`await` compilation. The Platform must optimize hot paths aggressively.

5. **Learning curve for effect-based concurrency.** Developers coming from `async`/`await` languages will need to learn the effect/handler model. While conceptually simpler, the initial unfamiliarity may slow adoption.

6. **Channel-only communication may be verbose.** Some patterns (e.g., a shared accumulator) are more naturally expressed with a shared mutable variable than with a channel. The channel-based workaround requires an extra task acting as the accumulator's owner.

---

## Alternatives considered

### Alternative 1: async/await (Rust, JavaScript, Python)

**Rejected.** Introduces function coloring that virally propagates through the codebase. Incompatible with Spore's "signature is the complete spec" philosophy. Also makes handler replacement (and thus simulatable execution) significantly harder.

**Consequences of rejection:** Spore requires effect handlers for concurrency, which adds implementation complexity in the compiler. However, users never deal with colored functions, and testing concurrent code requires zero special infrastructure.

### Alternative 2: Green threads (Go, Java Loom)

**Rejected.** Green threads are colorless (good) but lack effect tracking (bad). Any goroutine can perform any operation, violating Spore's effect constraint model. Additionally, goroutine leaks (Go's well-known problem) directly violate the resource safety guarantee.

**Consequences of rejection:** Spore cannot easily adopt existing Go-style runtime implementations. The effect handler approach requires a custom runtime that understands continuations.

### Alternative 3: Actor model (Erlang, Akka)

**Rejected.** Actor mailboxes use untyped message protocols, conflicting with Spore's type system philosophy. Message copying overhead makes cost modeling unpredictable. The isolation model is also heavier than needed for Spore's structured concurrency goals.

**Consequences of rejection:** Spore lacks built-in location-transparent distribution (actors excel here). Distributed systems require explicit Platform-level support.

### Alternative 4: Software Transactional Memory (Haskell STM)

**Rejected.** STM's retry mechanism has unbounded cost—the number of retries depends on runtime contention, making static cost analysis intractable.

**Consequences of rejection:** Certain concurrent data structure patterns are more verbose with channels than with STM. Accepted as a worthwhile trade-off for cost predictability.

### Alternative 5: Mutex/RwLock as primary synchronization

**Rejected.** Lock contention cost is unpredictable (spin/retry count depends on runtime scheduling). Deadlock detection in the presence of shared memory and locks is NP-hard. The effect handler + continuation model does not compose cleanly with lock semantics.

**Consequences of rejection:** Performance-critical lock-free patterns (e.g., atomic counters) are unavailable in safe Spore. A future `unsafe_shared` extension point is reserved but not in v0.1.

### Alternative 6: Unstructured spawning with optional scoping

**Rejected.** Providing both structured and unstructured spawning (as in Kotlin's `GlobalScope` vs. `coroutineScope`) creates an escape hatch that undermines cost analysis. If untracked concurrent tasks exist, the compiler cannot verify `cost ≤ N` or `parallel(lane)` bounds.

**Consequences of rejection:** Long-lived background tasks (daemon processes, connection pools) must be managed at the Platform level rather than in user code. This pushes certain patterns to Platform authors.

---

## Prior art

### Koka — Algebraic effects for concurrency

Koka (Daan Leijen, Microsoft Research) pioneered the use of algebraic effect handlers as a general mechanism for side effects, including concurrency. Spore adopts Koka's core insight—concurrency operations are effects that can be intercepted by handlers—and extends it with structured scoping and cost budgets.

**Reference:** Leijen, Daan. *"Algebraic Effects for Functional Programming"*. Microsoft Research, 2016.

### Kotlin Coroutines — Structured concurrency

Kotlin's `coroutineScope` + `launch`/`async` model demonstrated that structured concurrency is practical in a production language. Spore's `parallel_scope` + `spawn` is directly inspired by Kotlin's design, but replaces the coroutine machinery with effect handlers to eliminate function coloring.

**Reference:** Kotlin Coroutines documentation. <https://kotlinlang.org/docs/coroutines-basics.html>

### Python Trio — Nurseries

Trio (Nathaniel J. Smith) coined the "nursery" metaphor for structured concurrency scopes and wrote the seminal *"Go statement considered harmful"* essay. Spore's nursery semantics (parent waits for all children, cancellation cascades downward) directly follow Trio's model.

**Reference:** Smith, Nathaniel J. *"Notes on structured concurrency, or: Go statement considered harmful"*. 2018.

### Swift Structured Concurrency — Task groups

Swift 5.5 introduced `TaskGroup` as a structured concurrency primitive with cancellation propagation and child-task scoping. Spore draws from Swift's approach of making the scope the lifetime boundary for all child tasks.

### OCaml 5 — Effect handlers in a systems language

OCaml 5 added native support for algebraic effect handlers, proving that the mechanism can be implemented efficiently in a compiled language. Spore's handler compilation strategy will draw from OCaml 5's implementation experience.

**Reference:** OCaml 5 Effects. <https://ocaml.org/manual/5.2/effects.html>

### Go — CSP channels

Go's channel-based communication model (*"Don't communicate by sharing memory; share memory by communicating"*) directly inspires Spore's `Channel[T]`. Spore adds type safety (typed channels with effect declarations) and static cost analysis on top of Go's runtime model.

**Reference:** Go Concurrency. <https://go.dev/wiki/LearnConcurrency>

### Bob Nystrom — "What Color is Your Function?"

This 2015 blog post identified the function coloring problem that `async`/`await` introduces. Spore's colorless function design is a direct response to this critique.

**Reference:** Nystrom, Bob. *"What Color is Your Function?"*. 2015.

---

## Backward compatibility and migration

### This is a new feature

The concurrency model is introduced as a new language feature. There is no existing Spore code that uses concurrency, so there are no backward compatibility concerns at the language level.

### Interaction with existing SEPs

- **SEP-0001 (Core Syntax, extended by SEP-0003 for effects):** The `uses [Spawn, ...]` clause and `cost ≤ N` declarations are extensions to the signature syntax defined in SEP-0001, with effect annotations from SEP-0003. No breaking changes to existing signatures are required; `uses` and `cost` are additive clauses.
- **SEP-0004 (Cost Model):** This SEP adds the fourth dimension `parallel(lane)` to the cost model. Existing cost annotations (which only use `C`, `A`, `W`) remain valid; the `P` dimension defaults to `0` for functions without `Spawn`.

### Migration path for developers from other languages

| Source language | Key mental model shift |
|----------------|----------------------|
| Rust (`async`/`await`, `tokio`) | Replace `async fn` with `uses [Spawn]`; replace `tokio::spawn` with `parallel_scope` + `spawn`; no `.await` coloring |
| Go (goroutines) | Replace `go func()` with `parallel_scope` + `spawn`; all goroutines must be scoped; channels work similarly |
| Kotlin (coroutines) | Replace `coroutineScope` with `parallel_scope`; replace `launch`/`async` with `spawn`; effect handlers replace `Dispatchers` |
| JavaScript (`async`/`await`, `Promise`) | Replace `async`/`await` with effect-based concurrency; replace `Promise.all` with `parallel_scope` |

---

## Unresolved questions

1. **Exact runtime representation of `Task[T]`.** Should `Task[T]` be a zero-cost wrapper around a future, or should it carry metadata (spawn location, cost estimate) for runtime introspection? The former is more efficient; the latter enables richer diagnostics.

2. **`select` fairness guarantees.** When multiple branches are simultaneously ready, should `select` be fair (round-robin) or biased (first-listed wins)? Fair selection prevents starvation but adds overhead. The default behavior and whether it is configurable need further design.

3. **Channel backpressure strategies.** The current design offers only buffer-size-based backpressure (block when full). Should we support additional strategies such as dropping oldest, dropping newest, or raising an error? These would be expressible as effect handler variations.

4. **`unsafe_shared` escape hatch.** For extreme performance scenarios (lock-free counters, concurrent hash maps), should Spore provide an `unsafe_shared` primitive that bypasses the channel-only constraint? If so, what static checks should surround its use?

5. **Dynamic lane adjustment.** The current model uses static lane counts (`lanes: K`). Should the runtime be able to dynamically adjust the actual parallelism based on system load, and if so, how does this interact with compile-time cost verification?

6. **Effect handler composition order.** When multiple handlers appear in one binding block (for example `with { use handler_a {}, use handler_b {} }`), the composition order matters. The precise semantics of handler ordering for concurrency effects (especially when `Spawn` interacts with IO effects) need formal specification.

7. **Distributed concurrency.** This SEP covers single-machine concurrency. Extending the model to distributed settings (multi-node `parallel_scope`, remote channels) is a future concern but should not be foreclosed by current design decisions.

8. **Compiler warning heuristics for missing `check_cancelled()`.** What constitutes "long iteration" that should trigger a warning? Should this be configurable (e.g., estimated iteration count > N), and should it be suppressible with an annotation?

9. **Interaction between `deterministic` property and `Spawn`.** A function inferred as `deterministic` (from `uses`) with `uses [Spawn]` must produce schedule-independent results. The compiler verification strategy for this property (e.g., requiring commutative merge operations) needs further design.

10. **Channel type variance.** Should `Sender[T]` be contravariant in `T` and `Receiver[T]` covariant? This affects composability with generic code and needs alignment with the broader type system design.

---

## Appendix A: Syntax quick-reference

### A.1 `parallel_scope`

```spore
// Basic form
parallel_scope { <body> }

// With lane limit
parallel_scope(lanes: <N>) { <body> }

// Supervisor mode (collect errors instead of fail-fast)
parallel_scope(on_error: .collect) { <body> }

// Combined
parallel_scope(lanes: 4, on_error: .collect) { <body> }
```

### A.2 `spawn`

```spore
// Returns Task[T]
let task = spawn { <expr> }

// Direct await
let result = spawn { <expr> }.await

// With effect narrowing
let task = spawn uses [NetConnect] { <expr> }
```

### A.3 `Task[T]`

```spore
let value: T = task.await       // Wait for result
task.cancel()                    // Request cooperative cancellation
task.is_done                     // Bool: has the task completed?
task.is_cancelled                // Bool: was the task cancelled?
```

### A.4 Channel

```spore
// Create
let (tx, rx) = Channel.new[T](buffer: N)

// Send / receive
tx.send(value)          // ! ChannelClosed
let value = rx.recv()   // ! ChannelClosed

// Close and clone
tx.close()
let tx2 = tx.clone()

// Iterate (HOF, no for loops)
rx.each(|msg| handle(msg))
rx.collect()
```

### A.5 `select`

```spore
select {
    <binding> from <receiver> => <expr>,
    timeout(<duration>) => <expr>,
}
```

### A.6 Cancellation

```spore
// Timeout
with_timeout(duration) { <body> }

// Explicit cancellation checkpoint
check_cancelled()

// Cleanup (runs even on cancel)
defer { <cleanup> }
```

### A.7 Effect and handler

Concrete syntax for `effect`, `handler`, and `handle ... with` is defined in SEP-0001. The effect algebra and handler model that concurrency relies on are specified in SEP-0003.

### A.8 Function signature with concurrency

```spore
fn name(params) -> ReturnType ! Errors
where T: Constraints
cost ≤ <N>
uses [Spawn, Channel, ...]
{
    <body>
}
```

### A.9 Complete example: HTTP handler

```spore
effect HttpHandler = Spawn | NetConnect | DbRead | Clock

fn handle_request(req: Request) -> Response ! DbError | Timeout
cost ≤ 5000
uses [HttpHandler]
{
    with_timeout(10.seconds) {
        parallel_scope(lanes: 3) {
            let auth   = spawn uses [DbRead]  { verify_token(req.token) }
            let user   = spawn uses [DbRead]  { load_user(req.user_id) }
            let config = spawn uses [NetConnect]  { fetch_remote_config() }

            let auth_result = auth.await
            if !auth_result.valid {
                return Response.unauthorized()
            }

            Response.ok(render_page(user.await, config.await))
        }
    }
}
```

### A.10 Complete example: ETL pipeline

```spore
fn etl_pipeline(
    source: DataSource,
    sink: DataSink,
    batch_size: Int,
) -> EtlReport ! ExtractError | TransformError | LoadError
cost ≤ batch_size * 200
uses [Spawn, NetConnect, DbRead, DbWrite]
{
    let (raw_tx, raw_rx)     = Channel.new[RawRecord](buffer: batch_size)
    let (clean_tx, clean_rx) = Channel.new[CleanRecord](buffer: batch_size)

    parallel_scope(lanes: 6) {
        // Extract: 1 lane
        let extractor = spawn uses [NetConnect] {
            source.stream().each(|record| raw_tx.send(record))
            raw_tx.close()
        }

        // Transform: 4 lanes (fan-out)
        (0..4).each(|_| {
            spawn {
                raw_rx.each(|raw| {
                    match transform(raw) {
                        Ok(clean) => clean_tx.send(clean),
                        Err(e)    => log_error(e),
                    }
                })
            }
        })

        // Load: 1 lane (fan-in)
        let loader = spawn uses [DbWrite] {
            clean_rx.fold(0, |count, record| {
                sink.write(record)
                count + 1
            })
        }

        // Collect and report
        extractor.await
        clean_tx.close()
        let loaded = loader.await
        EtlReport { records_loaded: loaded }
    }
}
```
