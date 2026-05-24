---
sep: 0
title: "SEP-0000: Spore Evolution Proposal Process"
status: Accepted
type: Process
authors:
  - Zhan Rongrui
created: 2026-03-31
requires: []
discussion: "https://github.com/spore-lang/spore-evolution/discussions/41"
pr: "https://github.com/spore-lang/spore-evolution/pull/42"
superseded_by: null
---

# SEP-0000: Spore Evolution Proposal Process

> **Executive Summary**: Defines the governance process for evolving Spore through structured proposals (SEPs). It establishes the Pitch -> Draft -> Review -> Accepted lifecycle, machine-verifiable metadata, required sections by SEP type, and repository automation. It also makes SEP-0000 the canonical home for the guiding questions that operationalize [VISION.md](../VISION.md) for human and Agent review.

## Summary

**SEP** stands for **Spore Evolution Proposal** (Spore 演进提案).

> A SEP is a Spore Evolution Proposal: a design document that records and
> reviews language, tooling, ecosystem, and governance changes across Spore's
> evolution.

The term _evolution_ is intentional. SEPs cover syntax refactoring, semantic
reordering, breaking changes, deprecations, standard-library conventions,
toolchain protocols, and governance updates—not only incremental feature
additions. _Enhancement_ may describe the character of a particular change in
proposal text, but it is not the E in SEP.

This document defines the process for proposing, discussing, reviewing,
accepting, and evolving substantial changes to Spore.

It is the process document for the `spore-evolution` repository and the
starting point for all future SEP work. It also owns the canonical
**guiding questions for every design decision**, which translate the principles
in [VISION.md](../VISION.md) into reviewable prompts.

The responsibility split is deliberate: `VISION.md` states the design
philosophy, the implementation roadmap plans rollout work, and numbered SEPs
record reviewed decisions. Process mechanics, including the guiding questions,
live here rather than in the vision.

## Motivation

Spore designs a language and toolchain around an unusually cross-cutting set of
ideas:

- intent-first signatures and properties
- structured collaboration between humans and Agents
- holes as first-class collaboration points
- explicit effect and budget surfaces
- evidence-backed, machine-readable diagnostics and protocols

These changes have broad, long-term consequences. Ordinary implementation pull
requests are not sufficient to capture:

- design rationale
- alternatives considered
- tradeoffs and dissent
- the relationship between human UX and Agent UX
- migration and compatibility implications

Spore therefore needs a durable, reviewable design archive whose review
criteria stay tied to the vision rather than to whoever happens to comment
first.

## Goals

The SEP process aims to:

1. create a stable archive of significant Spore design decisions
2. separate implementation work from language and process design discussion
3. give substantial proposals a consistent path from idea to accepted design
4. require authors to explain both human-facing and Agent-facing consequences
5. anchor every review to the vision through a shared, canonical set of
   guiding questions
6. make it easier to revisit, amend, or supersede past decisions

## Non-goals

This process does not aim to:

1. require formal proposals for every small change
2. block ordinary bug fixes, refactors, tests, docs, or optimizations
3. settle all governance questions up front
4. require that an accepted SEP be rolled out immediately
5. duplicate vision content; [VISION.md](../VISION.md) owns the principles,
   and SEP-0000 owns the operational questions derived from them

## Proposal

This SEP proposes that `spore-evolution` become the canonical repository for
substantial design and process changes in Spore.

The model is intentionally simple:

- pitches start in a public discussion venue
- substantial proposals move into repository-backed draft documents
- proposal quality is enforced through templates, metadata, and CI
- review is anchored to a shared set of guiding questions derived from
  [VISION.md](../VISION.md)
- accepted decisions remain historically visible and amendable through later
  SEPs

## What requires an SEP

An SEP is expected for substantial changes to any of the following:

- language syntax
- language semantics or typing rules
- module, package, content-addressing, effect, or budget systems
- standard library or core tooling surface
- compiler output and machine-readable protocol design
- hole protocol, diagnostics protocol, or other human/Agent interface contracts
- the SEP process itself, including changes to the canonical guiding questions,
  their templates, or the checks that enforce them

Spore intentionally uses a **wide pitch threshold** but a **stricter SEP threshold**:

- if an idea may affect language or project direction, opening a pitch is cheap and encouraged
- a formal SEP is reserved for proposals that are substantial, user-visible, cross-cutting, or governance-relevant

## What usually does not require an SEP

The normal pull request workflow is usually enough for:

- bug fixes that do not change intended language behavior
- refactors that preserve external behavior
- internal code changes not visible to users
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
- **GitHub Issues** for rollout follow-up and narrower execution-oriented questions

If a proposal starts in one place and grows beyond that venue's strengths, maintainers may redirect it. The important thing is to preserve a public, searchable trail.

The pitch should focus on:

- the problem being solved
- why the existing Spore design is insufficient
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
- the [guiding questions for every design decision](#guiding-questions-for-every-design-decision),
  which translate [VISION.md](../VISION.md) into reviewable prompts
- migration and compatibility

Review is not a vote. The goal is informed judgment, not comment-counting.

### Accepted

An accepted SEP becomes the design record for that change. Acceptance means the proposal is directionally approved, but not necessarily scheduled for rollout.

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
6. the PR checklist confirms that the SEP-0000 guiding questions were considered

Maintainers may still add merge-summary comments when useful, but Spore does
not treat such comments as an automated merge gate.

## Proposal Status

SEP status describes the **decision state of the proposal**.

SEPs are design records for language, tooling, and process discussion. They are
not, by themselves, compatibility guarantees or public release contracts.

In particular:

- `Accepted` means the design direction is approved
- it does **not** mean the proposal is shipped
- it does **not** mean the release surface is production-ready
- it does **not** imply a binary jump from "experimental" to "stable"

Release readiness and rollout state should be tracked elsewhere, for example in:

- rollout issues
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

The first listed author is the champion unless the SEP explicitly names a
different champion in its text.

### Maintainers

During the bootstrap phase, the `spore-lang` organization owner acts as sole maintainer and
exercises final decision authority for accepting, rejecting, or withdrawing SEPs.

As the project grows, this role may be distributed to a maintainer team.
Any change to the decision model described in this section requires a Process SEP.

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

All SEP types require an **Executive Summary** — a blockquote of 2–4
sentences placed immediately below the H1 title heading. The executive summary
should concisely state the core contribution, key design decisions, and expected
impact.

### Standards Track

Standards Track SEPs should include:

1. Executive Summary (blockquote immediately below the H1 title heading)
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

1. Executive Summary (blockquote immediately below the H1 title heading)
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

SEP-0000 itself also carries the canonical
[Guiding questions for every design decision](#guiding-questions-for-every-design-decision)
section. Other Process SEPs do **not** duplicate that heading; they link to it
and, if they alter the question set, amend SEP-0000 directly.

### Informational

Informational SEPs should include:

1. Executive Summary (blockquote immediately below the H1 title heading)
2. Summary
3. Motivation
4. Discussion
5. Prior art or references
6. Implications for Spore
7. Unresolved questions or future directions

Not every proposal needs identical depth in every section, but omission of required sections should be exceptional and explicit.

## Guiding questions for every design decision

These questions are the operational form of [VISION.md](../VISION.md). They
translate the vision principles into reviewable prompts and anchor SEP review
to those principles rather than to ad-hoc preference.

SEP-0000 is the **only** canonical home of this section. Other SEPs and
authoring templates link to this heading instead of duplicating it.

The semantic path that the questions protect is:

```text
Signature -> Property -> Hole -> Realization -> Evidence
```

| #   | Question                                                                      | Vision principle it operationalizes                         |
| --- | ----------------------------------------------------------------------------- | ----------------------------------------------------------- |
| 1   | Does this make intent clearer?                                                | Signatures are gravity centers; properties specify intent   |
| 2   | Does this reduce ambiguity for Agents?                                        | Holes are typed absence; realization implements the missing |
| 3   | Does it preserve the distinction between base signature and intent signature? | Signatures are gravity centers                              |
| 4   | Can the semantics be exported in a stable, machine-readable form?             | Holes are typed absence; evidence records what was checked  |
| 5   | Can a hole be realized without extra conversation?                            | Holes are typed absence                                     |
| 6   | Can every check produce evidence?                                             | Evidence records what was checked                           |
| 7   | Can evidence be tied to content hashes and invalidated precisely?             | Evidence records what was checked                           |
| 8   | Does it improve diagnostics, repair, and review workflows?                    | Holes are typed absence; evidence records what was checked  |
| 9   | Does it preserve the semantic path?                                           | All principles in composition                               |

Authors should answer these questions in the proposal sections where they are
useful, not as a rote checklist. If a question is irrelevant to a proposal, the
SEP should say why rather than silently dropping the concern.

If a proposal introduces new structure for humans but not for tools, or vice
versa, that mismatch should be made explicit in the proposal.

### How each SEP type applies the questions

These questions apply to every SEP type, but the surface where they are
addressed differs:

- **Standards Track** SEPs address them in the Human experience impact and
  Agent experience impact sections where applicable.
- **Process** SEPs consider them when changing review criteria, automation, or
  any check that might create or weaken evidence flow. A Process SEP that
  alters the canonical question set must also amend this section directly.
- **Informational** SEPs consider them in their Implications for Spore section
  when describing prior art or design direction that could influence later
  normative proposals.

## Amendments and follow-up changes

Accepted SEPs should not be silently rewritten to mean something substantially different.

- small clarifications may be merged as ordinary edits
- significant semantic changes should go through a new SEP
- superseding SEPs should link to the older document they replace

### Amending this document

Non-semantic clarification edits to SEP-0000 itself may be merged directly by the
maintainer. Substantive changes that alter the decision model, the lifecycle, the
SEP type taxonomy, or the required section templates must go through a new Process
SEP that supersedes or amends this document.

## Drawbacks

This process adds coordination overhead compared with a repository that only uses issues and pull requests.

In particular:

- authors must learn proposal structure and metadata rules
- maintainers must curate proposal history more actively
- the project may initially feel process-heavy relative to its size

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
discussion: "https://github.com/spore-lang/spore-evolution/discussions"
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

The repository automation stack is:

- `prek` as the shared local and CI hook runner
- `rumdl` for Markdown linting
- `Vale` for small terminology and prose rules
- `lychee` for link checking
- `typos` for spelling checks
- `check-jsonschema` for front matter schema validation
- `seps-index.json`, generated from front matter and checked for drift
- repo-local Python checks for:
  - front matter extraction and parsing
  - executive-summary placement and sentence count
  - required section presence by SEP type
  - filename/title consistency
  - unique SEP number validation
  - status transition validation
  - SEP-0000 guiding-question completeness (heading and content markers)
  - duplicate guiding-question sections outside SEP-0000
  - template references to the canonical guiding-question section
  - VISION.md staying principle-level instead of carrying syntax or review
    mechanics
  - surface-terminology consistency across the repo and sibling docs
  - PR checklist validation

The static site stack is intentionally **deferred**. Site generation should be
decided separately after the core proposal workflow and quality checks settle.

## Unresolved questions

This process leaves several questions intentionally open:

1. How strict should automatic status-transition checks become over time?
2. How should the future publishing stack integrate with SEP metadata and index generation?
3. Should future proposal repositories extract more of this automation into shared tooling such as `zendev`?

These can be refined in follow-up process changes or amendments to this SEP.
