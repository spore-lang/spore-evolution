# D3 handler state specification draft

This artifact turns the D3 decision into patch-ready text for SEP-0001 and
SEP-0003. It depends on the primitive-effect draft and does not edit SEP files
directly.

## Locked decision

D3 is fixed as follows:

- User-level Spore does not introduce `mut`, `mut self`, or mutable handler
  fields.
- Handler fields may exist, but they are immutable runtime configuration.
- Handler methods write the receiver explicitly as the first parameter:
  `self` or `self: Self`. The receiver is read-only.
- `self.field = expr` is not valid handler syntax.
- Stateful mock and instrumentation use cases route through state primitive
  effects (`Cell`, `Output`, `Map`, `Clock`, `Random`).
- Handler instances are task-local. A handler installed inside one task is not
  visible to sibling tasks unless installed again.
- Handler fields do not participate in signature hash or intent hash. They are
  instance payload, not callable boundary.

## Evidence from current text

| Document | Current evidence | D3 impact |
| --- | --- | --- |
| SEP-0001 | Current grammar uses `handler Ident for SurfaceExpr` and `HandlerItem = fn QualifiedIdent ...` at `seps/SEP-0001-core-syntax.md:312-316`. | Needs to align with accepted `handles`, `uses`, fields, and `impl Effect` blocks. |
| SEP-0001 | Grammar notes say handler items must name effect operations with qualified identifiers at `seps/SEP-0001-core-syntax.md:333-338`. | Replace with `impl Effect` blocks and explicit receiver method shape. |
| SEP-0003 | Current handler example mutates `self.output.push(msg)` at `seps/SEP-0003-effect-system.md:101-115`. | Replace with primitive-effect based examples. |
| SEP-0003 | Handler checking requires implementing every operation of discharged atomic effects at `seps/SEP-0003-effect-system.md:143-146`. | Keep this rule; add receiver/state policy. |
| Sibling parser AST | `Expr::Handle` owns named `use` bindings and inline `on` arms at `../spore/crates/sporec-parser/src/ast.rs:296-326`. | PR45 should acknowledge `handle ... with { use ..., on ... }` expression shape. |
| Sibling parser AST | `HandlerDef` has `fields`, `handles_clause`, optional `uses_clause`, and `impls` at `../spore/crates/sporec-parser/src/ast.rs:483-499`. | PR45 grammar should converge on this structure, with immutable-state policy added. |
| Sibling parser tests | A handler example with fields, `handles`, `uses`, and `impl Console` appears at `../spore/crates/sporec-parser/tests/parser_tests.rs:486-500`. | This is the implementation shape to document, except method receivers need PR45 policy. |
| Primitive draft | Primitive state endpoints are `Cell`, `Output`, `Map`, `Clock`, `Random` in `.spark/artifacts/primitive-effects-spec.md`. | Mock examples should use these effects instead of handler field mutation. |

## SEP-0001 grammar patch draft

### Target

Replace the handler grammar around `seps/SEP-0001-core-syntax.md:312-316`.

### Replacement grammar

```ebnf
HandlerDecl     = { Attribute } [ Visibility ] "handler" Ident
                  [ "(" [ FieldDecl { "," FieldDecl } [ "," ] ] ")" ]
                  HandlesClause [ UsesClause ]
                  "{" { HandlerImplBlock } "}" ;
HandlesClause   = "handles" SurfaceExpr ;
HandlerImplBlock = "impl" Ident [ TypeArgs ]
                  "{" { HandlerMethod } "}" ;
HandlerMethod   = "fn" Ident [ TypeParams ]
                  "(" ReceiverParam [ "," ParamList ] ")"
                  "->" TypeExpr ( Block | ";" ) ;
```

### Grammar notes update

Replace the handler grammar note with:

```markdown
Handler declarations use `handles` to name the discharged effect surface and may
use `uses` to declare effects required by handler method bodies. Handler fields
are immutable instance payload. Handler methods live inside `impl Effect { ... }`
blocks and write `self` as the first parameter. The receiver is read-only; this
SEP does not introduce `mut self` or field assignment.
```

### Handle expression syntax note

Add this note near expression forms when expression grammar is expanded:

````markdown
A `handle` expression installs named handler instances and inline arms for a
lexical scope:

```spore
handle { body } with {
    use HandlerName { field: value },
    on Effect.operation(param) => arm_body
}
```

Named `use` entries instantiate a handler payload. Inline `on` arms handle a
single effect operation directly. SEP-0003 owns the checking rules.
````

## SEP-0003 handler patch draft

### Replace the current handler example

Current example at `seps/SEP-0003-effect-system.md:101-115` uses
`self.output.push(msg)`. Replace it with:

```spore
effect Console {
    fn println(msg: Str) -> ();
}

effect Output[T] {
    fn emit(value: T) -> ();
}

handler MockConsole handles [Console] uses [Output[Str]] {
    impl Console {
        fn println(self, msg: Str) -> () {
            perform Output.emit(msg)
        }
    }
}

handle {
    greet("spore")
} with {
    use MockConsole {}
}
```

This example intentionally omits the `Output[Str]` handler. The enclosing test
or Platform scope must install it explicitly.

### New subsection: Handler state policy

Add after the guide-level handler example:

```markdown
### Handler state policy

Handler fields are immutable runtime configuration. Handler method bodies may
read `self` and fields on `self`, but they may not assign to `self.field` or
otherwise update handler instance payload. Spore does not add `mut`, `mut self`,
or mutable handler fields for stateful handlers.

Stateful handler use cases route through state primitive effects such as
`Cell`, `Output`, `Map`, `Clock`, and `Random`. A handler that needs state lists
the relevant primitive effects in its own `uses` clause and performs those
effects in method bodies.
```

### New subsection: Handler instance visibility

Add to the reference-level handler section:

```markdown
Handler instances are lexical and task-local. Installing a handler with
`handle ... with` affects only the dynamic extent of that expression within the
current task. Spawned or sibling tasks do not inherit the handler instance unless
that handler is installed in their own dynamic extent.
```

### New subsection: Handler fields and hashes

Add near structured representation or hash references:

```markdown
Handler fields are instance payload and do not participate in `signature_hash`,
`intent_hash`, or `property_hash`. Hashes cover callable boundaries and intent
metadata; handler payload values are runtime configuration for a specific
installation.
```

## Mock examples

### Console capture

```spore
effect Console {
    fn println(msg: Str) -> ();
}

effect Output[T] {
    fn emit(value: T) -> ();
}

handler CaptureConsole handles [Console] uses [Output[Str]] {
    impl Console {
        fn println(self, msg: Str) -> () {
            perform Output.emit(msg)
        }
    }
}
```

### Counter

```spore
effect Cell[T] {
    fn get() -> T;
    fn set(value: T) -> ();
}

handler CountingConsole handles [Console] uses [Cell[I64]] {
    impl Console {
        fn println(self, msg: Str) -> () {
            let n = perform Cell.get();
            perform Cell.set(n + 1)
        }
    }
}
```

### Memo table

```spore
effect Compute {
    fn run(input: Input) -> Output;
}

effect Map[K, V] {
    fn get(key: K) -> Option[V];
    fn put(key: K, value: V) -> ();
}

handler MemoCompute handles [Compute] uses [Map[Input, Output]] {
    impl Compute {
        fn run(self, input: Input) -> Output {
            match perform Map.get(input) {
                Some(value) => value,
                None => {
                    let value = expensive(input);
                    perform Map.put(input, value);
                    value
                }
            }
        }
    }
}
```

These examples use placeholder primitive method names from the primitive-effect
draft. The later patch step may choose different exact spellings.

## Sibling implementation alignment notes

| Implementation point | Alignment |
| --- | --- |
| `HandlerDef.fields` at `../spore/crates/sporec-parser/src/ast.rs:493-499` | Keep fields, but specify that they are immutable instance payload. |
| `handles_clause` and `uses_clause` at `../spore/crates/sporec-parser/src/ast.rs:493-499` | Align PR45 grammar with existing parser structure. |
| `HandlerImpl { effect, methods }` at `../spore/crates/sporec-parser/src/ast.rs:483-489` | Use `impl Effect { fn operation(self, ...) ... }` in PR45 grammar. |
| `Expr::Handle { body, handlers }` at `../spore/crates/sporec-parser/src/ast.rs:296-306` | Acknowledge `handle ... with` expression in SEP-0001/0003. |
| `HandleBinding::Use` and `HandleBinding::On` at `../spore/crates/sporec-parser/src/ast.rs:310-326` | Keep named and inline handler installation forms. |
| Parser test at `../spore/crates/sporec-parser/tests/parser_tests.rs:486-500` | Good shape for fields/handles/uses/impl; method receiver remains a future implementation follow-up. |

## Routing to the patch plan

`@sep-patch-plan` should include these concrete edits:

1. SEP-0001 replaces handler grammar with fields, `handles`, optional `uses`,
   and `impl Effect` blocks.
2. SEP-0001 updates grammar notes to say handler fields are immutable and method
   receivers are explicit read-only `self`.
3. SEP-0001 acknowledges `handle ... with { use ..., on ... }` expression shape.
4. SEP-0003 replaces the `self.output.push` example with a primitive-effect
   `Output` example.
5. SEP-0003 adds handler state policy text.
6. SEP-0003 adds task-local handler instance visibility.
7. SEP-0003 adds the handler field hash boundary.
8. GLOSSARY adds or updates handler entries for immutable fields and task-local
   instances if needed.
