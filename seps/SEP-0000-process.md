---
sep: 0
title: "SEP-0000: Spore Enhancement Proposal Process"
status: Draft
type: Process
authors:
  - Spore maintainers
created: 2026-03-31
requires: []
discussion: null
pr: null
superseded_by: null
---

# SEP-0000: Spore Enhancement Proposal Process

> **Executive Summary**: Defines the governance process for evolving Spore through structured proposals (SEPs). Establishes a Draft → Review → Accepted lifecycle, required sections by proposal type, machine-verifiable metadata (YAML front matter + JSON index), and dual review criteria for both human and agent experience impact.

## Summary

This document defines the initial process for proposing, discussing, reviewing, accepting, and evolving substantial changes to Spore.

It is the process document for the `spore-evolution` repository and the starting point for all future SEP work.

## Motivation

Spore is attempting to design a language and toolchain around a fairly ambitious set of ideas:

- intent-first APIs
- structured collaboration between humans and Agents
- holes as first-class collaboration points
- explicit effect and cost models
- machine-readable diagnostics and language protocols

These changes have broad, long-term consequences. Normal implementation pull requests are not enough to capture:

- design rationale
- alternatives considered
- tradeoffs and dissent
- the relationship between human UX and Agent UX
- migration and compatibility implications

Spore therefore needs a durable, versioned, reviewable design archive.

## Goals

The SEP process aims to:

1. create a stable archive of significant Spore design decisions
2. separate implementation work from language and process design discussion
3. give substantial proposals a consistent path from idea to accepted design
4. require authors to explain both human-facing and Agent-facing consequences
5. make it easier to revisit, amend, or supersede past decisions

## Non-goals

This process does not aim to:

1. require formal proposals for every small change
2. block ordinary bug fixes, refactors, tests, docs, or optimizations
3. settle all governance questions up front
4. require that an accepted SEP be implemented immediately

## Proposal

This SEP proposes that `spore-evolution` become the canonical repository for substantial design and process changes in Spore.

The initial model is intentionally simple:

- pitches start in a public discussion venue
- substantial proposals move into repository-backed draft documents
- proposal quality is enforced through templates, metadata, and CI
- accepted decisions remain historically visible and amendable through later SEPs

## What requires an SEP

An SEP is expected for substantial changes to any of the following:

- language syntax
- language semantics or typing rules
- module, package, content-addressing, effect, or cost systems
- standard library or core tooling surface
- compiler output and machine-readable protocol design
- hole protocol, diagnostics protocol, or other human/Agent interface contracts
- the SEP process itself

Spore intentionally uses a **wide pitch threshold** but a **stricter SEP threshold**:

- if an idea may affect language or project direction, opening a pitch is cheap and encouraged
- a formal SEP is reserved for proposals that are substantial, user-visible, cross-cutting, or governance-relevant

## What usually does not require an SEP

The normal pull request workflow is usually enough for:

- bug fixes that do not change intended language behavior
- refactors that preserve external behavior
- internal implementation changes not visible to users
- test-only changes
- editorial documentation improvements
- performance improvements that do not alter semantics

When in doubt, start with a pitch. Escalate to a formal SEP once the proposal clearly crosses the "substantial change" line.

## SEP types

There are three SEP types:

### Standards Track

Describes changes to the language, standard library, diagnostics model, language-facing protocols, or other user-visible technical behavior.

### Process

Describes changes to governance, proposal workflow, review rules, release process, or project-wide development policy.

### Informational

Describes design explorations, architectural context, prior art, or guidance that may influence Spore without itself proposing a normative change.

## Lifecycle and transition rules

The default lifecycle is:

`Pitch -> Draft SEP -> Review -> Accepted / Rejected / Withdrawn`

### Pitch

A proposal should generally begin as a pitch in a public, linkable venue.

For Spore, the default split is:

- **GitHub Discussions** for language design, syntax, semantics, architecture, and other exploratory design questions
- **GitHub Issues** for implementation tracking, rollout follow-up, and narrower execution-oriented questions

If a proposal starts in one place and grows beyond that venue's strengths, maintainers may redirect it. The important thing is to preserve a public, searchable trail.

The pitch should focus on:

- the problem being solved
- why current Spore design is insufficient
- rough direction and tradeoffs

The goal of the pitch is not final wording. The goal is to determine whether the idea is worth turning into an SEP.

### Draft SEP

If the idea is worth pursuing, the author opens a pull request adding a draft SEP document to this repository.

A draft SEP should be:

- focused on one main proposal
- technically coherent
- honest about drawbacks and alternatives
- concrete enough to review

### Review

When maintainers believe a draft is ready, it moves into review.

For Spore, review is expected to use **both**:

- a proposal pull request, which carries the evolving canonical text
- a linked public discussion thread, which supports broader review and design debate

Neither surface is sufficient alone:

- PR comments are good for document-specific feedback and merge-time decisions
- linked discussions are better for broader arguments, alternative designs, and community participation

Important conclusions from the linked discussion should be summarized back into the PR before merge so that the proposal record remains reconstructable from the repository itself.

For Spore, a linked public discussion thread is required for **all** SEP types.

Review should emphasize:

- problem/solution fit
- conceptual coherence with Spore
- migration and compatibility
- whether the proposal makes human intent clearer
- whether the proposal makes Agent-facing structure clearer and more stable

Review is not a vote. The goal is informed judgment, not comment-counting.

### Accepted

An accepted SEP becomes the design record for that change. Acceptance means the proposal is directionally approved, but not necessarily implemented or scheduled.

### Rejected

A rejected SEP is closed with rationale preserved in the historical record.

### Withdrawn

The author or maintainers may withdraw a proposal that is no longer being pursued.

### Superseded

If a later SEP replaces a previous one, the older document should remain in the repository and be marked `Superseded`.

## Merge requirements

Before an SEP is merged, Spore expects all of the following:

1. a champion is identified
2. a linked public discussion thread exists
3. the proposal uses the correct template for its SEP type
4. required front matter is present and valid
5. required sections are present

Maintainers may still add merge-summary comments when useful, but Spore does not currently treat such comments as an automated merge gate.

## Proposal status vs implementation maturity

SEP status should describe the **decision state of the proposal**, not the rollout or maturity state of its implementation.

SEPs are design records for language, tooling, and process discussion. They are
not, by themselves, the current implementation truth, a compatibility guarantee,
or a public release contract. Public readers who need current release behavior
should start with the implementation repository, especially
[`spore/README.md`](https://github.com/spore-lang/spore/blob/main/README.md)
and
[`spore/docs/DESIGN.md`](https://github.com/spore-lang/spore/blob/main/docs/DESIGN.md).

In particular:

- `Accepted` means the design direction is approved
- it does **not** mean the proposal is fully implemented
- it does **not** mean the implementation is production-ready
- it does **not** imply a binary jump from "experimental" to "stable"

Implementation maturity is typically gradual and should be tracked elsewhere, for example in:

- implementation issues
- release notes
- feature flags
- compiler/tooling status pages
- repository-level planning documents

This separation keeps SEP status focused on design governance rather than release management.

### Draft status during the bootstrap phase

During Spore's bootstrap phase, maintainers may keep repository-defining SEPs in `Draft`
while the process, terminology, and review mechanics are still settling. In this phase,
`Draft` means "still revisable as process text," not "released behavior." Repository
planning, templates, and follow-on SEPs may still treat these draft SEPs as the working
design baseline until they are explicitly superseded or replaced, but external release
expectations should come from implementation docs, release notes, and shipped artifacts.

## Roles and responsibilities

### Author / champion

Each SEP should have a champion responsible for:

- writing the proposal
- revising it in response to feedback
- summarizing open questions and tradeoffs
- helping build consensus

### Maintainers

For now, `spore-lang` maintainers are responsible for:

- deciding when a proposal is ready for review
- deciding whether it is accepted, rejected, or withdrawn
- assigning SEP numbers at merge time
- keeping status metadata up to date

Future governance may refine or replace this arrangement through a Process SEP.

## Numbering and file layout

### Numbering

- `SEP-0000` is reserved for the process document
- later SEPs use sequential four-digit numbers
- maintainers assign the final number at merge time
- draft proposals should use descriptive temporary filenames before acceptance

### File layout

Documents should generally live at:

```text
seps/SEP-0000-process.md
drafts/intent-first-signature.md
seps/SEP-0001-short-name.md
templates/standards-track.md
templates/process.md
templates/informational.md
```

## Required sections by SEP type

All SEP types require an **Executive Summary** — a blockquote of 2–4 sentences placed immediately after the YAML front matter, before the first heading. The executive summary should concisely state the core contribution, key design decisions, and expected impact.

### Standards Track

Standards Track SEPs should include:

1. Executive Summary (blockquote before first heading)
2. Summary
3. Motivation
4. Guide-level explanation
5. Reference-level explanation
6. Human experience impact
7. Agent experience impact
8. Structured representation / protocol impact
9. Diagnostics impact
10. Drawbacks
11. Alternatives considered
12. Prior art
13. Backward compatibility and migration
14. Unresolved questions

### Process

Process SEPs should include:

1. Executive Summary (blockquote before first heading)
2. Summary
3. Motivation
4. Goals
5. Non-goals
6. Proposal
7. Lifecycle and transition rules
8. Roles and responsibilities
9. Drawbacks
10. Alternatives considered
11. Migration or rollout impact
12. Unresolved questions

### Informational

Informational SEPs should include:

1. Executive Summary (blockquote before first heading)
2. Summary
3. Motivation
4. Discussion
5. Prior art or references
6. Implications for Spore
7. Unresolved questions or future directions

Not every proposal needs identical depth in every section, but omission of required sections should be exceptional and explicit.

## Spore-specific review expectations

Because Spore explicitly targets human/Agent collaboration, SEP review should ask these questions:

1. Does this proposal make user intent clearer or more obscure?
2. Does it reduce or increase ambiguity for Agents?
3. Can the key semantics be exported in a stable machine-readable form?
4. Does it improve or degrade diagnostics and repair workflows?
5. Does it preserve conceptual coherence with the rest of Spore?

If a proposal introduces new structure for humans but not for tools, or vice versa, that mismatch should be made explicit.

## Amendments and follow-up changes

Accepted SEPs should not be silently rewritten to mean something substantially different.

- small clarifications may be merged as ordinary edits
- significant semantic changes should go through a new SEP
- superseding SEPs should link to the older document they replace

## Drawbacks

This process adds overhead compared with a repository that only uses issues and pull requests.

In particular:

- authors must learn proposal structure and metadata rules
- maintainers must curate proposal history more actively
- the project may initially feel process-heavy relative to its current size

We accept this cost because Spore is making design decisions that are unusually cross-cutting and difficult to reconstruct after the fact.

## Alternatives considered

The main alternatives were:

1. keep all design discussion inside ordinary PRs in the main repository
2. use issues only, without proposal documents
3. postpone a formal process until the language and tooling are more mature

These options reduce short-term overhead, but they perform worse on durable rationale capture, historical traceability, and cross-cutting design review.

## Migration or rollout impact

The first rollout should focus on process adoption rather than large-scale migration:

- `SEP-0000` defines the workflow
- future substantial changes should start using draft SEP documents
- repository automation should gradually move from advisory to required

Older design discussions do not need to be backfilled immediately. Important historical decisions can be reconstructed into Informational or Standards Track SEPs later when useful.

## Template and metadata

Each SEP should begin with front matter similar to:

```yaml
---
sep: XXXX
title: "SEP-XXXX: Title"
status: Draft
type: Standards Track
authors:
  - Your Name
created: YYYY-MM-DD
requires: []
discussion: "https://github.com/spore-lang/spore-evolution/discussions/123"
pr: "https://github.com/spore-lang/spore-evolution/pull/45"
superseded_by: null
---
```

This metadata is intended to support later automation and quality checks.

For Spore, the required front matter keys are:

- `sep`
- `title`
- `status`
- `type`
- `authors`
- `created`
- `requires`
- `discussion`
- `pr`
- `superseded_by`

Drafts may use `sep: null` before a permanent number is assigned at merge time.

Spore also maintains a committed machine-readable index at `seps-index.json`.

That index is generated from proposal front matter and checked for drift in local hooks and CI rather than maintained by hand.

## Repository automation

The initial repository automation stack is:

- `prek` as the shared local and CI hook runner
- `rumdl` for Markdown linting
- `Vale` for small terminology and prose rules
- `lychee` for link checking
- `typos` for spelling checks
- `check-jsonschema` for front matter schema validation
- `seps-index.json`, generated from front matter and checked for drift
- minimal repo-local Python checks for:
  - front matter extraction
  - required section presence
  - filename/title consistency
  - unique SEP number validation
  - status transition validation
  - PR checklist validation

The static site stack is intentionally **deferred** for now. Site generation should be decided separately after the core proposal workflow and quality checks settle.

## Unresolved questions

This initial process leaves several questions intentionally open:

1. How strict should automatic status-transition checks become over time?
2. How should the future publishing stack integrate with SEP metadata and index generation?
3. Should future proposal repositories extract more of this automation into shared tooling such as `zendev`?

These can be refined in follow-up process changes or amendments to this SEP.
