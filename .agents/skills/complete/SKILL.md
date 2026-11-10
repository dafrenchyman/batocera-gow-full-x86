---
name: complete
description: Enforce verified spec or epic delivery before whole-folder completion, archive known rejected/abandoned/superseded work, repair references, and maintain factual current documentation. Use automatically after whole-spec or epic acceptance, or for direct current-documentation updates.
---

# Complete

Record delivered outcomes, preserve their evidence, and keep references and current documentation truthful. This skill does not implement product code or turn planning readiness into delivery.

Read [the lifecycle reference](../_shared/lifecycle.md) first. It owns canonical placement, states, permission, and spec/epic delivery gates. Read [the current-state reference](references/current-state.md) for every completion review or direct current-documentation request. That reference is the sole detailed current-documentation procedure. Load named skills through available skill discovery or their `SKILL.md` files; no named invocation tool is required.

## Select the operation

- For a direct current-documentation update, follow the current-state reference using actual implementation and verification sources. No completed folder, completion record, or lifecycle move is required.
- For requested archival, establish the known rejected, abandoned, or superseded disposition and reason, plus a replacement link when relevant. Follow the archival branch below. Being blocked or paused is not an archival decision.
- For delivery after `implement-spec`, epic coordination, or a user request, read the full owning contract, exploration, tickets, research, verification and review evidence, parent epic, and linked dependencies. Follow the delivery branch. Standalone specs are valid; do not invent a parent.

An ambiguous disposition is a decision, not permission to guess. Read [the interview reference](../_shared/interview.md) before asking the one unresolved choice. Keep pursued work active and preserve exact blockers in its existing records.

## Establish delivery independently

Evaluate the relevant gate in the lifecycle reference against observed evidence, not status labels or unchecked assumptions. Treat ticket reconciliation and whole-outcome acceptance as separate obligations.

For a spec, reconcile every existing ticket and acceptance record. Done needs promised work and observed verification; Unnecessary needs its actual reason and evidence, with unfulfilled work still distinguishable. Verify the complete approved spec contract separately, including behavior spanning tickets, dependencies, conditions, and accepted revisions. Ticket completion does not supply missing whole-spec proof. A negative research result is evidence for its question, not delivery of the rejected implementation.

For an epic, resolve every required backlog link to the actual completed spec and its delivery evidence. Evaluate the combined epic contract separately, including interfaces, shared resources, end-to-end flows, and cross-spec interactions. Individual child verification is insufficient when it does not exercise the combination. Explain linked work made unnecessary and identify how its required outcome is actually satisfied; archived or deferred candidates cannot substitute for delivery. Contract revisions must have explicit user approval through exploration, not a completion-time scope cut.

Inspect whether recorded verification and reviews cover the actual final state and applicable platforms. Run authorized missing acceptance verification when this invocation includes that responsibility; otherwise keep active and return the exact missing scenario or evidence to the implementation owner. Record observed results and limits only. Unverified promised outcomes refuse completed placement, even with every ticket terminal. Accepted non-blocking limitations may be recorded; unmet acceptance is not a limitation to disguise.

Before moving anything, perform the current-documentation impact review in [current-state.md](references/current-state.md). Determine the affected topics or an explicit no-impact disposition. Readiness to move requires passed delivery evidence, a known destination, and the reference inventory below. No Git initialization, commit, branch, worktree, tracker action, publishing, deployment, or activation is implied.

## Inventory, move, and repair

Use this procedure for both completed and archived placement:

1. Inspect the entire source folder, including exploration, tickets, research, inputs, assets, and existing disposition/completion records. Inventory all contents that must survive. Resolve source and destination from the lifecycle reference. Check that the destination path does not exist, even as an empty folder or file. Refuse an existing destination; do not merge, overwrite, or choose a new identity silently.
2. Before moving, inventory incoming references throughout repository documents and metadata, and outgoing references from every affected file. Include Markdown links, plain-text paths, root-relative paths, fragments, parent/backlog links, spec/ticket links, research/assets, linked dependencies, current-topic backlinks, and sibling references. Record each referring file, actual old target, new target, and affected anchor. Distinguish historical statements from operational references so useful history is not rewritten into fiction.
3. Make a path mapping for the whole folder and for referring files that also move. Create only the destination's parent directories. Move the source folder as one intact unit with available filesystem tools; preserve every inventoried asset. Keep linked specs in their separate folders when moving an epic.
4. Apply the mapping to incoming and outgoing references. Recalculate relative links from each file's final location, including files outside the moved folder. Repair active parent epic backlog/capability routing and associated spec parent links; update ticket/spec, research, assets, dependent specs/epics, completion records, and current-documentation backlinks. Preserve fragments only when their real target heading remains valid. Update current lifecycle pointers while retaining explicitly labeled original locations as history.
5. Inspect final inventory and resolve every affected local reference to its actual file or directory and heading anchor. Confirm that parent/backlog and child links agree, all preserved assets exist, and the moved source is no longer the active workspace. Do not claim successful repair from string replacement alone. Finish any failed move or repair step before reporting the operation complete; never leave a second active authority or a partial success report.
6. Update the owning spec or epic to its final status under the lifecycle reference after successful placement and repair. Do not leave a completed document labelled Ready or an archived document labelled delivered.

A child spec move updates the parent but does not complete the parent automatically. Only evaluate parent delivery after its own gate and combined verification are available.

## Record delivered facts

Write or update `completion.md` in the moved folder after successful delivery. Keep it concise; link ticket and verification detail rather than copying it. Use only actual facts:

```markdown
# Completion: <name>

State: Complete
Source before completion: <historical active path>
Delivered location: <actual completed path>
Parent: <actual epic link, or none>

## Delivered behavior

Summarize outcomes actually accepted. For an epic, describe the combined result rather than repeating children.

## Verification

Name exercised commands/scenarios, observed results, and evidence links, including whole-outcome or interaction proof. Include resolved review findings only when material.

## Deviations and limits

Record approved deviations and known non-blocking limits with their provenance. Say none when applicable. An unmet required outcome refuses completion instead of becoming a Partial record here.

## Current documentation

Link the actual current topics updated, or state the reviewed no-impact disposition and reason.
```

Apply the current-state reference to added, changed, and removed impacts, then finish the cross-links and actual-target validation. For epic completion review aggregate behavior and interactions without duplicating child topic updates. Completion bookkeeping is finished only when the delivery record, parent disposition, preserved workspace, references, and current-documentation review agree.

## Archive a known disposition

Before moving, preserve the rejection, abandonment, or supersession decision in the existing exploration and owning spec/epic record. Include the reason, decision provenance, and replacement or merged/split destination where relevant. Retain useful research and unsuccessful approaches. Do not create a delivery record for unimplemented work or mark its acceptance as passed.

Use the same inventory, intact move, destination-refusal, repair, and actual-target procedure. Update parent backlog and affected dependencies with the archived disposition and replacement, not a delivered label. An Unnecessary ticket stays in its owning spec and does not archive that spec. If archival exposes a current-documentation claim unsupported by actual implementation, correct it under the current-state reference; the archive itself adds no implemented behavior.
