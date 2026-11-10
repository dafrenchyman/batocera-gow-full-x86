---
name: wayfinder
description: Explore initiatives that need several linked specs, preserve capability and research context, and maintain an epic backlog. Use for cross-spec decisions, uncertain decomposition, or resuming epic planning, not product implementation.
---

# Wayfinder

Find the route before building the destination. An epic is a map of shared outcomes, capabilities, decisions, research, and linked specs. Its exploration holds the reasoning; its backlog names work and dependencies. A bounded standalone spec needs no epic.

Read [the lifecycle reference](../_shared/lifecycle.md) before choosing locations, changing placement, or handing off delivery. Read [the shared interview rules](../_shared/interview.md) and use persistent mode for decisions. These references own lifecycle and interview rules. Load named skills through available skill discovery or their `SKILL.md` files; no particular invocation tool, tracker, credentials, or setup command is required.

## Recover the map

1. Find the existing epic workspace or derive a short kebab-case name for a new one. Read its exploration, epic, saved inputs, research, linked specs and tickets, relevant current documents, glossary, ADRs, and archived alternatives. Preserve user edits. Recover the destination, accepted choices, open questions, dependencies, deferred work, and next discussion queue from files, not previous chat.
2. Before creating or restructuring artifacts, read [the planning reference](references/epic-planning.md) and [the epic template](references/epic-template.md). Start with useful exploration, not a fabricated tree of child files. For dense intake, preserve the source and route every heading under the planning reference.
3. Inspect actual code, tests, manifests, and existing plans. Inventory each capability as implemented, partial, or absent, with paths and evidence, gaps, and reuse or replacement implications. Separate product/domain scope from architecture. Existing behavior may satisfy part of the destination without new implementation.

Recovery is complete when the saved context supports the next consequential question and no supplied heading has disappeared from the routing inventory.

## Clear the fog

Establish the destination and scope, then map the breadth of unresolved decisions before going deep into one branch. Use the shared one-decision interview. Discuss workflows, data, integrations, failure modes, migrations, operations, verification, rollout, rollback, security, privacy, licensing, and non-goals where they matter. Resolve ambiguous terminology or qualifying ADRs through `domain-modeling`.

Keep two kinds of uncertainty distinct:

- A precise unanswered question is an open decision or research track, even if blocked. Name its required facts or prior choices.
- Fog is in-scope uncertainty that cannot yet be phrased precisely. Keep it in `Not yet specified` in exploration until an answer makes it concrete. Do not pre-slice fog into fictitious implementation tickets.

Out-of-scope work has an explicit reason, not a fog entry. Reopening rejected scope needs a new user decision. When an answer changes the map, update affected topics, capability routing, backlog dependencies, and linked exploration together. The shared persistence boundary applies before advancing to another question.

Choose the appropriate way to clear a question:

- Research can run without the user when it discovers facts. Use available local or primary-source research tools, and the supporting `research` skill where its host capabilities are available. Save the question, method, citations, findings, ambiguity, failures/dead ends, reusable assets, and decision impact under the owning research folder. Return constraints to every affected exploration and contract; a rejected option needs an explicit user override with rationale and accepted risk to remain proposed.
- A sketch, sample object, outline, or permitted disposable experiment can raise discussion fidelity. Label it as a proposal, preserve useful assets, and ask the user to react. Use existing tools rather than calling an absent prototype or design skill. Discussion artifacts do not authorize product implementation or an application scaffold.
- Human-in-the-loop decisions require the user's actual answer. Never have an agent supply or simulate it. Follow `grill-with-docs` for a child scope and the shared interview for epic choices.
- A manual prerequisite may unblock a decision without delivering the epic. Discover what is missing and record the exact action and resulting facts. Perform only authorized actions; for human-only access or permission, ask for that prerequisite, without persisting secrets. Leave the question unresolved until the needed input exists.

After research or a tangent, return to the highest-leverage unresolved topic. Do not impose an arbitrary one-decision-per-session limit; wait for each answer and save it before continuing.

## Route capabilities and child work

Maintain the capability map, complete candidate backlog, shared decisions, and research links using [the planning reference](references/epic-planning.md). Optional, conditional, deferred, blocked, and potentially rejected candidates stay visible with reasons and dependencies. A candidate row is not a Ready spec and does not require an empty spec or ticket scaffold.

When a child scope needs durable discussion, read and use `grill-with-docs` on its separate spec workspace. Bring its concrete inherited context into local exploration, including examples and contracts, and link the parent and dependencies. On requested generation, read and use `to-spec`. It owns the original seven-section Draft, review, and explicit Ready approval. The same contract applies to standalone and epic-linked specs. Do not bypass unresolved choices or manufacture child approval from epic planning readiness. Ticket breakdown and implementation use their own authorization gates.

The epic owns shared outcomes and sequencing. Child exploration owns local reasoning; an approved child spec owns its implementation contract. Link shared decisions rather than maintaining competing copies. If a shared decision changes an approved contract, route the affected child back through `grill-with-docs` before `to-spec` updates it.

## Review and hand off

Before declaring Planning ready, establish all of these from the artifacts:

- The destination, hard constraints, non-goals, and observable combined outcomes are clear.
- Every capability and source heading has an exact owner or explicit research, deferred, rejected, or accepted-risk disposition. Concrete details remain locally useful, not just linked to raw intake.
- Existing/partial/absent work, all candidates, conditions, dependencies, meaningful risks, and the next bounded child scope are recorded. Unknown prerequisites remain visible.
- Linked files exist at their actual locations. Each linked spec identifies its parent, every associated spec appears in the backlog, and names match routing targets or explain merges and splits.
- Research findings and dead ends reached affected artifacts. Contradictions are resolved or open; consequential choices and accepted risks have user or evidence provenance.
- Overlapping behavior has one owner, with explicit dependency and interaction verification in the other scopes.

Readiness means the map can guide the next planning step, not that delivery occurred or execution is authorized. Keep pursued paused or blocked work active under the lifecycle reference. Recommend the next child exploration, requested specification generation, or authorized implementation coordination. If actual delivery or a known archival disposition is requested, read and use [complete](../complete/SKILL.md); do not move folders or declare completion from backlog labels alone.
