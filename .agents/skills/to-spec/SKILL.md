---
name: to-spec
description: Synthesize saved exploration into a reviewed local Draft specification, preserve accepted contracts and user edits, and request explicit Ready approval. Use after grill-with-docs or for an approved exploration revision, not for chat-only planning.
---

# To spec

Read [the lifecycle reference](../_shared/lifecycle.md) for locations and approval states, and [the shared interview rules](../_shared/interview.md) before asking for a review decision. Read named skills through available host skill discovery or a file reader. No tracker, setup command, or named invocation tool is required.

## Read the source of decisions

1. Find the owning planning workspace and read its full `explore.md`, relevant research, existing `spec.md` and tickets, parent epic and linked dependencies, glossary, and relevant ADRs. Inspect current code and tests for the implementation/reuse inventory and actual test seams.
2. Require saved exploration. If the request contains only chat, a raw brief, or unrecorded decisions, use `grill-with-docs` to save and resolve them before synthesis. Keep its persistence and relevance rules authoritative.
3. Check that accepted requirements, proposals, rejected alternatives, assumptions, and unresolved questions are distinguishable. Preserve user-edited content as authoritative. A conflict between user edits and accepted exploration is a decision to resolve, not permission to overwrite either source.

Synthesis starts only when consequential source decisions are settled or explicitly accepted as risks or deferrals. Do not conduct a new design interview inside generation.

## Write a Draft

Before creating or restructuring the specification, read [the original seven-section template](references/spec-template.md). Keep its seven H2 headings in order. Use lower-level topic headings inside them when needed; do not replace them with a new generic specification structure.

Create or update the local `spec.md` as Draft. Preserve `explore.md` and research. For an existing spec, change only what the accepted source revision requires, preserving unrelated user edits and accepted examples. Do not silently demote an existing Ready contract or treat a prior approval as approval of changed requirements. Resolve its revision scope through exploration first.

Put useful context directly in the seven normal sections so the spec is locally reviewable:

- State the problem, outcome, concrete user/system flows, requirements, and non-goals without inventing scope.
- Preserve meaningful paths, interfaces, sample data, sketches, timing examples, safety language, constraints, and accepted decision-rich code. A useful example need not come from a prototype. Label illustrative material so it cannot add accidental requirements.
- Include the existing/partial/absent implementation inventory, reusable modules and tests, decisions and important rejected options, dependencies and conditional inputs, migration implications, and accepted risks under the relevant section.
- Identify observable acceptance outcomes and verification tied to them in Testing Decisions. Prefer the highest existing seam that exercises the behavior, keeping new seams few and justified. Include logic unit tests for non-trivial behavior or a specific reason they cannot apply. Review external-service, browser, filesystem, clock, and database coupling for brittle tests.
- Summarize design-relevant research findings and link their evidence; do not substitute a link or provenance-only section for known requirements. Do not create a separate execution checklist or `tasks.md`.

If generation exposes a consequential error, contradiction, or unknown, stop the affected generation. Read and use `grill-with-docs` to resolve one decision and correct exploration first, then update the Draft. Do not fabricate requirements to fill thin sections or quietly repair the contract in the spec alone.

## Review and request approval

Review the Draft against exploration, research, existing implementation, user edits, parent outcomes, and sibling dependencies. Check scope, flows and contracts, testability and observable acceptance, security, privacy, licensing, migration and data-loss risks, contradictions, and hidden implementation coupling.

Use a supported reviewer agent when available and useful, or perform the same critical pass directly. A missing reviewer, prototype, or design tool is not a reason to skip review or invent a skill invocation. Keep review findings with the affected topic. Blocking design findings return to `grill-with-docs`; accepted non-blocking risks and deferrals remain explicit.

If unresolved consequential topics remain, keep Draft and return to exploration. If none remain, summarize the contract and ask one explicit approval question: does the user approve this Draft as Ready? Wait. Set Ready only after that approval, then recommend `to-tickets` for the reviewed breakdown. Specification approval does not create tickets or authorize execution.
