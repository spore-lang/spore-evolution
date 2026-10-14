---
name: spore-add-proposal
description: Research, draft, materially revise, or review a Spore Enhancement Proposal using spore-evolution governance, templates, terminology, and local checks. Use for SEP authoring or unresolved language and process design choices; not for routine compiler implementation, editorial maintenance, or treating accepted proposals as shipped behavior.
---

# SEP authoring

Prepare a reviewable design record within the user's requested scope. A request
to assess or review produces findings; a requested draft authorizes the document,
not its acceptance, implementation, or public discussion posts.

## Establish the local process

Read [SEP-0000](../../../seps/SEP-0000-process.md), the
[authoring entry](../../../README.md#authoring), related SEPs, and the
[glossary](../../../GLOSSARY.md). Use current implementation sources and tests
to check claims about working behavior. Accepted design and implementation
maturity are different facts.

Apply SEP-0000's distinction between an exploratory pitch and a substantial
formal proposal. Routine fixes restoring intended behavior and implementation
of settled decisions do not acquire a new SEP merely because work is extensive.
Identify any genuinely new choice and its human and agent impact.

## Research before deciding

Compare viable alternatives with evidence from source, tests, primary
documentation, or papers; record applicable versions and distinguish inference
from observation. Explain the recommendation and costs in semantics, protocols,
compatibility, diagnostics, and contributor workflow where relevant.

Actually ask about unresolved choices that affect scope, semantics, ownership,
authority, or migration before selecting a direction. Reuse explicit user
choices and existing applicable decisions; record the basis. An explicit
delegation allows a choice within its constraints, while a drafting request alone
does not. Resolve routine reversible details independently. While waiting,
continue independent research and unaffected prose; silence leaves the choice
unresolved and does not authorize dependent implementation.

## Preserve SEP conventions

Choose the existing Standards Track, Process, or Informational template from the
authoring entry. Check the [schema](../../../schemas/sep-frontmatter.schema.json)
and [document validator](../../../scripts/validate_sep_documents.py) before
filling metadata. New unnumbered drafts belong in drafts with `sep: null` and
`status: Draft`; maintainers assign permanent numbers. Preserve existing
numbered records when revising them.

Use actual author identities, dates, and discussion/PR links. All SEP types need
the canonical public discussion required by SEP-0000. Search existing linked
material first; if it is missing, report the unmet requirement and keep the
document incomplete rather than inventing a URL or claiming it is valid.
Creating or sending an external discussion requires the user's authorization.

Follow the current template and checker for headings and metadata; a review
stage in process prose is not automatically a permitted `status` value.
If governance, template, and checker conflict, report the exact conflict and
continue unaffected work without silently changing the process.

## Make the design understandable

Place problem evidence, alternatives, decision sources, drawbacks, and observable
acceptance criteria in the template's existing sections. For Standards Track
work, connect the guide-level explanation to the reference-level rules and show
the relevant human, agent, representation, and diagnostics consequences.

Reuse glossary terms and distinguish examples from normative rules. Make actors,
condition scope, quantifiers, ordering, exceptions, and failure behavior explicit.
Do not replace uncertainty with invented semantics or omit premises to shorten
a proof or explanation. Use connected prose for reasoning and steps for actions.

Preserve identifiers and history. Apply SEP-0000's amendment and supersession
rules for changed decisions rather than silently rewriting accepted meaning.

## Validate and deliver

Run the authoring entry's document, index, and terminology checks. Regenerate the
index only when proposal metadata requires it, inspect the complete diff, and
rerun the checks. Use this repository's scripts rather than assuming it uses the
current Zendev proposal checker.

Report the chosen route, document or findings, sources of key decisions, checks
actually run, and remaining discussion or evidence gaps. Keep schema validity,
design acceptance, implementation, and release distinct. Follow the user's
delivery endpoint and existing PR workflow without changing decision authority.
