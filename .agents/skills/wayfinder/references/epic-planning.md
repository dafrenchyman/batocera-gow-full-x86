# Epic planning and context routing

Read this before preserving dense intake, building the backlog, or preparing linked child exploration. [Wayfinder](../SKILL.md) owns the workflow. [The lifecycle reference](../../_shared/lifecycle.md) owns locations and states; [the interview reference](../../_shared/interview.md) owns decision capture and relevance.

## Preserve intake without losing meaning

If a headed brief, numbered plan, sketch, or other dense input has no durable repository copy, save it in the epic's `inputs/` folder. Link existing sources instead of duplicating them. Source preservation is an audit aid, not the locally reviewable plan.

Maintain an input routing inventory in epic exploration. Account for every heading and numbered section, including sections later rejected. Use source labels exactly enough to find them again.

| Source heading | Capability or topic | Owning artifact or named candidate | Disposition and unresolved input |
| -------------- | ------------------- | ---------------------------------- | -------------------------------- |

Each row routes to a shared decision, child exploration or existing spec, named backlog candidate, research track, explicit deferral/rejection, or user-accepted risk. Where a heading splits across children, name each owner; for merged scopes, name the surviving candidate. Match names with the backlog and actual files. A row is captured only when its target contains the relevant material or an explicit disposition, not merely a promise to preserve it later.

Integrate actual details into meaningful topic sections. Preserve concrete paths, interfaces, sample objects, data/state shapes, UI sketches, text/audio copy, timing and schedules, equipment or other meaningful lists, workflows, safety language, testing expectations, constraints, and non-goals. Keep accepted requirements separate from illustrative proposals and assumptions. A line saying "source sketch includes a dashboard" does not preserve the dashboard sketch.

## Exploration structure

Use the exploration structure owned by `grill-with-docs` for common topics, adding epic-specific routing and fog where useful. Keep problem and current direction, existing implementation, topic-organized decisions and alternatives, assumptions, risks, open questions, and next discussion queue. Add input routing inventory, capability routing, and `Not yet specified` for uncertainty that cannot yet become a precise question. Link the epic backlog rather than copying it into exploration.

Keep research detail in its research record. Save useful dead ends so a later session does not repeat an invalid approach. Shared research belongs to the epic; child-only research belongs to its spec workspace. Bring decision-relevant findings into every affected exploration and approved contract through the planning revision workflow. A source link alone is not a usable constraint.

## Capability and candidate backlog

Use the backlog in `epic.md` as the index. A named candidate may exist without a spec file when only its purpose, dependencies, open questions, or cut/defer condition are known. Preserve substantive known details under its topic in epic exploration until a child exploration owns them. Avoid fake child Drafts and empty execution files.

For each capability, identify existing implementation, the desired outcome, one owning candidate or shared decision, and integration points. Inventory implemented, partial, and absent work with actual paths and evidence. Decide whether partial work is reused, replaced, or still uncertain. Do not turn an inventory observation into an unrequested product decision.

For every candidate, retain:

- Its descriptive name and purpose, plus whether it is required for the approved epic outcome or optional under an explicit condition.
- Its actual planning disposition, such as next, later, blocked, conditional, optional, research-needed, deferred, proposed cut, or linked to a Draft/Ready spec. Use delivered or archived labels only from actual disposition records.
- Required inputs, upstream decisions or specs, any separate execution condition, and what unblocks it.
- Source headings and the topic holding known details, or the real child link if materialized.
- The reason for deferral or rejection and any replacement, merge, or split routing. Never silently drop an optional candidate behind the first deliverable.

Keep lifecycle status and sequence distinct. A spec can be Ready but blocked on a required input. A research answer can be conclusive without authorizing the option it disproved.

## Locally reviewable children

Create child exploration only when there is useful context to preserve or a requested decision to work through. When promoting a named candidate, move its local reasoning into the child exploration and replace the old topic with a short index link. Preserve shared epic decisions with a link plus the concrete local constraints they impose.

A reviewer must be able to understand the child scope without opening raw intake. Carry actual examples, interfaces, flows, failure behavior, constraints, test seams, dependencies, conditions, open questions, assumptions, and accepted risks into its normal exploration topics. Distinguish inherited user choices from new agent recommendations. Keep user edits intact.

Use `grill-with-docs` to resolve remaining child choices, then `to-spec` for requested synthesis and approval. Thin context remains exploration or a candidate entry; the epic does not invent requirements to fill specification headings. Concrete later or conditional context deserves preservation now, not fabricated implementation readiness.

## Consistency and sequencing

At planning review, compare every source row and capability against its target content. Match candidate names, actual links, parent backlinks, research owners, and merge/split dispositions. Every associated spec must appear in the backlog, but candidates need not all have files.

Name decision and artifact prerequisites, not just an ordered list. Recommend the first bounded child and explain why it is next. Track planning/research gates and combined delivery proof in tables or concise topic notes, not a second implementation task ledger. Record who owns research and the question it must answer. Where supported, independent research can run in parallel with disjoint edits or a named integration owner; human decisions remain sequential at the shared interview boundary.

Review research contradictions, accepted-risk provenance, and overlapping ownership. A finding against an option reaches all its dependent scopes; pursuing it anyway requires an explicit user decision and rationale. Defer or cut low-value work visibly. A required outcome stays required until the user approves a contract revision through exploration, even if its original candidate is archived or deferred.
