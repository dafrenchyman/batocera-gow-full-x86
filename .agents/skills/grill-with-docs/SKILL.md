---
name: grill-with-docs
description: Create or resume durable exploration before specification generation, capture each answered choice, and resolve consequential planning or domain questions. Use for saved design discussions, dense briefs, and corrections returned by to-spec or implementation.
---

# Grill with docs

Read [the shared interview rules](../_shared/interview.md) and use persistent mode. Read [the lifecycle reference](../_shared/lifecycle.md) before choosing artifact locations or changing lifecycle state. Use available skill discovery or read the named skill's `SKILL.md` directly. No named invocation tool is required.

## Gather and preserve context

1. Find the existing owning workspace. For a new standalone effort, derive a short kebab-case name and use `docs/active/specs/<spec_name>/explore.md`. Ask about scope only if materially different scopes remain plausible. Specs linked to epics still live under `docs/active/specs/`, not inside epic folders.
2. Read the saved artifacts and relevant repository context under the shared resumption rules. Inventory existing, partial, and absent behavior, reusable modules and tests, and gaps. Record meaningful paths and what they establish. Check relevant archived approaches before proposing them again.
3. Before creating or restructuring `explore.md`, read [the exploration template](references/explore-template.md). Preserve user edits, concrete intake, and accepted examples. Populate the existing topic sections with actual known context, not placeholders or a compressed generic brief. Update topics in place when resuming.
4. If the effort contains independent capabilities, long research tracks, or several specifications, use `wayfinder` for the epic-level exploration. Keep the bounded spec's decisions with its own exploration and link its parent and dependencies. Do not invent a parent epic or placeholder child specs.

Context gathering is complete when the next decision can be asked from the saved files without relying on previous chat.

## Explore and capture

Follow the shared one-decision interview and save boundary. This skill creates exploration, not a specification. Keep accepted requirements distinct from tentative directions and recommendations. Do not implement product code during planning.

Read and use `domain-modeling` when terminology is ambiguous, conflicts with the glossary or code, or a resolved term needs recording. Save resolved domain definitions through that skill as each choice is captured. Keep implementation detail in exploration, not the glossary. Consult its ADR selection and format rules when a decision may warrant a record; do not invent ADRs for routine choices.

When a choice depends on repository findings, external documentation, integration behavior, licensing, or an experiment, read [the research template](references/research-template.md) before creating `research/<topic>.md` in the owning workspace. Use primary sources and available research tools. Preserve methods, evidence, ambiguity, failed alternatives, reusable artifacts, and decision impact. Summarize the constraints in exploration. A conclusive negative finding resolves the research question; it does not authorize the rejected implementation. An inconclusive result remains open.

Use comparisons, snippets, sketches, and examples only when they clarify the current question. Label proposals and retain accepted decision-rich examples with their constraints. Experiments require permission for any effects outside planning and must not become an unrequested application scaffold.

## Review and hand off

After each captured answer or research result, return to the shared continuation rule. Revisit relevant optional or deferred choices, assumptions, risks, and thin requirements before declaring exploration ready. Keep exact resume points in `Open Questions` and `Next Discussion Queue`, not in a separate task ledger.

When no consequential topic remains, check scope, existing implementation, concrete flows and contracts, dependencies, observable acceptance, testability, security/privacy/licensing, and migration or data-loss risks. Record accepted risks and explicit deferrals. If blocked, name the missing input and the next question or research task.

If ready, recommend `to-spec` on the saved workspace. Read its instructions only when the user requests generation. This handoff does not create `spec.md`, mark a spec Ready, generate tickets, authorize execution, or permit Git actions.
