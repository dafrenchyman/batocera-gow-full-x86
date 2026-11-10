---
name: implement-spec
description: Coordinate authorized implementation of a Ready local specification through a fresh subagent per ticket, schedule its eligible ticket graph, reassess dependent inputs and conditions, and verify the whole promised outcome before completion. Use for whole-spec execution or resumption, not ticket generation or approval.
---

# Implement spec

Read [the lifecycle reference](../_shared/lifecycle.md) before graph scheduling, claims, status changes, or delivery. It owns paths, approval states, eligibility, permissions, and completion gates. Read [the interview rules](../_shared/interview.md) before asking for a consequential decision or updating exploration. Use available host skill discovery or read a named skill's `SKILL.md` directly. This workflow needs local documents, not a tracker, setup service, integration branch, or particular invocation tool.

## Recover and review the approved work

1. Resolve the owning spec folder from the requested artifact. Read the complete `spec.md`, `explore.md`, all tickets, relevant research, linked dependencies, parent epic if present, applicable standards, glossary, and ADRs. Recover accepted decisions, observed progress, review risks, blockers, owners, and resume points from files without requiring prior chat.
2. Require a Ready spec and explicit implementation authorization for the work to execute. Neither Ready approval nor ticket creation is execution permission. If tickets are missing, use `to-tickets` for the reviewed breakdown and creation approval, then obtain execution authorization. If the contract is unresolved, use `grill-with-docs` and `to-spec`; do not manufacture tickets or code to bypass a planning gate.
3. Inventory existing, partial, and absent implementation and reusable tests. Review the whole implementation plan before code, including scope, dependent interfaces, test seams, whole-spec acceptance, security/privacy/licensing, migration and data-loss risks, hidden external coupling, failure modes, and integration ownership. Use a supported reviewer when useful or perform the same critical pass directly.
4. Resolve correctness blockers before dispatch. Record accepted non-blocking risks with the affected topic and preserve user edits. Any contract-changing discovery returns through `grill-with-docs` to correct exploration before the spec and affected tickets change. An execution note cannot redefine the promised outcome.

This review complements each ticket's pre-code review in `implement`; it does not replace it. Read [implement](../implement/SKILL.md) before dispatching any eligible ticket.

## Map the graph and real inputs

Build a working graph from actual ticket links, not numerical order. For every ticket identify its permanent identity, status, required prerequisite outcomes and artifacts, distinct execution condition, current owner/resume point, edits/resources, and observable acceptance. Read linked external-spec inputs rather than assuming another workspace's status supplies them. Keep the graph in working context and authoritative ticket fields; do not create a second ledger or new ticket sections.

Check for missing or ambiguous links, absent required inputs, contradictory conditions, cycles, and unowned deliverables. A cycle has no executable frontier: retain the affected blockers and resolve the approved breakdown rather than inventing a scheduling order or erasing an edge. Report the cycle and the required decision. Other authorized, genuinely independent eligible work may proceed if it does not depend on that resolution.

Apply the lifecycle eligibility rules for each candidate using inspected input artifacts and prerequisite evidence. A closed-looking prerequisite does not supply a missing interface, finding, file, or configuration. Evaluate `Proceed only if` separately from `Blocked by`. Persist an evidenced false-condition disposition or an explicit unresolved/missing-input blocker under the ticket's existing What to build section. Leave original unmet acceptance boxes unchecked.

Conclusive negative research can be Done because its question is answered. It does not provide a rejected implementation, a compatible dependency, or authorization for that approach. Inconclusive findings remain unresolved. Link detailed methods and findings from their research record rather than duplicating them across tickets.

## Claim the eligible frontier

Select authorized tickets whose actual inputs and conditions permit execution. Claim each selected ticket in its existing Status and What to build fields before work begins. Record the owner, bounded work, affected resources, relevant integration constraint, and exact resume point. If an earlier claim remains, recover or explicitly reassign it before dispatch so two agents do not execute the same ticket.

Use the current checkout and apply shared permission boundaries. Parallel execution is suitable only for disjoint edits and resources. A shared generated file, dependency lock, fixture namespace, service port, database, or formatter run can conflict even when source files differ. Sequence conflicting work or assign an agreed integration owner with explicit handoff boundaries; do not permit competing writes merely because tickets have no graph edge. Any separately requested isolation still needs its own permission.

Implement every eligible ticket in its own newly created subagent, including when only one ticket is eligible or tickets must run sequentially. Start each worker without inherited coordinator conversation, prior worker messages, or prior-ticket context. A fresh context still includes required system/project instructions and the bounded assignment below. Assign exactly one ticket per worker; never reuse a worker for another ticket. On resumption after a worker ends, create a new worker that recovers the same ticket's state from files.

Give each worker pointers to the actual spec, exploration, its ticket, relevant research and prerequisite artifacts, shared rules, and `implement`. Include explicit implementation authorization and its limits, ownership, allowed edit/resource boundaries, integration constraints, and required acceptance evidence. The worker reads those sources itself; pass neither conversation transcripts nor copied whole contracts as a substitute.

The coordinator owns scheduling, claims, dependent reassessment, shared integration verification, and whole-spec review, not ticket implementation. Route ticket fixes discovered during integration or review back to that ticket's worker, or a fresh replacement if it has ended. If the host cannot create fresh-context subagents, preserve the resume state and report that missing capability; do not fall back to coordinator implementation.

For parallel slices, let workers implement and preserve truthful resume state, but keep shared integration checks under one owner. Workers must not mark a ticket Done until its actual final verification and review gates have passed. Run shared all-files hooks and whole-project checks after the participating edits land, not concurrently against another worker's half-written files. Attribute final evidence to the affected tickets only after the integrated files actually pass.

## Execute and reassess after outcomes

Each ticket worker uses `implement` for its ticket's reviewed tranches, agreed meaningful TDD seams, real smoke behavior, applicable contract checks, post-verification correctness/security/maintainability review, and durable evidence. Preserve its final all-files and stable-rerun gates. Targeted tranche verification and final integration verification have different purposes; neither replaces the other.

After any prerequisite outcome, changed input, or condition finding:

1. Read the actual resulting artifact and ticket evidence. Ensure a reported result is present in the shared checkout and satisfies the promised input contract before relying on it.
2. Reassess every affected dependent individually under the lifecycle rules. In particular, after Unnecessary work, inspect each dependent's own condition and whether valid alternate inputs meet its contract. One may proceed, another may become Unnecessary under an evidenced false condition, and another may remain Blocked for a missing input. Do not cancel or unblock a subtree in bulk.
3. Update each affected ticket's existing status and What to build text with the finding, evidence or missing input, and exact next action. Retain identities, original criteria, useful prior progress, and unchecked unmet outcomes. Do not treat alternate inputs as a license to change the approved contract.
4. Recompute the eligible frontier and edit/resource conflicts before claiming more work. Dispatch only newly eligible authorized work.

Continue until all authorized in-scope work has a verified terminal disposition or no eligible work remains. If blocked, preserve pursued work in its active workspace and report each concrete missing input or decision, owner, and resume action. Research discoverable facts first; route a contract-changing decision through exploration using the shared interview method. Partial progress, unresolved conditions, and missing verification are not completion.

## Verify the spec independently

Terminal tickets are necessary but not sufficient. Before reading `complete` for a delivery handoff:

1. Account for every spec ticket as Done or Unnecessary with observed evidence or an evidenced disposition. Check that records are consistent with the actual implementation. An Unnecessary ticket's original unmet criteria stay unchecked and its work is not described as delivered.
2. Map every whole-spec acceptance outcome to an actual integrated scenario or check. Run those scenarios against the complete result, including cross-ticket interfaces, error/boundary behavior, applicable external contracts, and real smoke paths. Do not substitute ticket checkboxes, compilation, or isolated component success for the promised user outcome.
3. Run the relevant full suites and repository-required checks on the integrated files. For frontend code/tooling, run the configured full TypeScript project check outside staged hooks. For applicable Nix changes, check declared outputs and build affected systems without activation. Apply coverage requirements only to actual applicable source and record platform/environment limits honestly.
4. Apply the lifecycle mandatory all-files verification gate after integration. Inspect fixes and rerun until stable. If a fix or integration finding changes behavior, repeat the affected acceptance, smoke, tests, and contract checks. Use the shared authorized-verification-checkout rule when Git metadata is unavailable, not automatic repository initialization.
5. Review the verified integrated implementation for correctness, security, maintainability, test quality, and spec compliance with a supported reviewer or direct critical pass. Resolve blockers, repeat affected verification after fixes, and retain explicitly accepted remaining risks. Reconcile any stale progress/resume notes with the actual observed outcome.

If any whole-spec criterion fails or required work remains blocked, keep the spec active even when all ticket statuses appear terminal. Name the unmet outcome and return to the responsible ticket. If the contract needs revision, return through exploration instead of weakening the completion gate.

Only after the independent spec gate passes, read and use [complete](../complete/SKILL.md). It owns completion placement, whole-folder preservation, reference repair, and mandatory review of current-behavior documentation. Do not move the folder, create a competing completion record, or close a legacy tracker here. A linked epic remains subject to its own combined-outcome gate; a delivered child spec cannot complete the epic by itself.

Report changed files, verified ticket dispositions, whole-spec evidence and limits, review risks or blockers, the completed location and current-topic updates if `complete` finished, or exact resume actions if work remains active. Claim only checks and outcomes actually observed. Implementation authorization does not permit commits, branch changes, publishing, or activation.
