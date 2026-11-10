---
name: implement
description: Execute one authorized local ticket, review its plan and verified implementation, and preserve acceptance evidence, blockers, and exact resume points. Use for eligible ticket implementation or resumption; use implement-spec to coordinate an entire specification.
---

# Implement

Read [the lifecycle reference](../_shared/lifecycle.md) before selecting work, claiming it, verifying it, or changing status. It owns artifact locations, eligibility, states, permission boundaries, and delivery gates. Read [the interview rules](../_shared/interview.md) before asking for a consequential choice or updating exploration. Discover named skills through the host or read their `SKILL.md` files directly. No particular invocation tool, tracker, setup service, or Git isolation is required.

## Recover the contract and eligibility

1. Resolve the requested local ticket and its owning workspace. Read the full ticket, approved `spec.md`, `explore.md`, relevant research, parent epic if present, and linked prerequisites. Recover existing progress, observed evidence, accepted risks, user edits, and the exact resume point without relying on chat history.
2. Require a Ready specification and explicit implementation authorization covering this ticket. Specification approval and ticket-creation approval do not authorize execution. If authorization is missing, request it before implementation. For an unapproved or contract-blocked source, use `grill-with-docs` and `to-spec` as appropriate rather than starting code.
3. Apply the lifecycle eligibility rules to actual inputs and outcomes, not ticket numbers or terminal status. Inspect the artifacts each dependency must supply and evaluate any separate `Proceed only if` condition. An unresolved condition or missing required input prevents a claim. A conclusive negative research result can resolve research without providing an implementation input.
4. Inspect the relevant implementation, tests, manifests, applicable standards, glossary, and ADRs. Reuse existing conventions and verified behavior. Identify the smallest complete change this ticket owns and exclude deferred, sibling, and rejected work.

Before coding, the ticket must be authorized and eligible, with a contract that can be observed. Record an evidenced eligibility disposition under the existing What to build section when a condition or input prevents execution. Preserve the original acceptance criteria and ticket identity.

## Review the plan before code

Map this ticket to coherent implementation and verification tranches. A tranche should leave a demonstrable behavior or finding, not just an edited layer. Identify the files, interfaces, required resources, verification commands or scenarios, and public test seams. Review this plan against the ticket, spec, exploration, research, parent outcomes, and dependent contracts.

Use a supported reviewer when available and useful, or perform the same critical pass directly. Check contradictions, impossible or unowned work, observable acceptance, security/privacy/licensing, migration and data-loss risks, failure modes, hidden network/browser/database/clock/filesystem coupling, and scope creep. Break overly broad implementation steps into verifiable tranches without changing the approved ticket contract or inventing another checklist.

Resolve correctness blockers before coding. Record non-blocking findings with their disposition in the affected planning topic; a consequential risk needs explicit acceptance, not an implementer's waiver. A discovery that changes the contract returns through `grill-with-docs` to correct exploration, then through `to-spec` and the affected ticket review before execution resumes.

For meaningful executable behavior, read and use [tdd](../tdd/SKILL.md) at agreed public seams. Reuse seams already approved in the specification; otherwise confirm the meaningful seam before authoring tests. Follow its red-green loop and test-quality guidance. If a referenced design or review capability is absent, inspect the actual interface and discuss its observable boundary directly, or use an available reviewer. Do not invent a mandatory invocation or skip the underlying design/review work. For prose or tooling-only work, use real workflow transitions or command entry points instead of fabricating an application or tautological wording tests.

## Claim and implement verified tranches

Apply lifecycle ownership and permission rules in the current checkout. In the ticket's existing What to build section, record the owner, bounded tranche, relevant coordination constraints, and exact resume point. Use the existing Status field for the claim. Coordinate overlapping edits and shared resources before proceeding; `implement-spec` owns whole-spec scheduling.

For each tranche:

1. Implement only its promised behavior. Update callers, tests, configuration, schemas, and substantive documentation that the change actually affects. Remove obsolete code replaced by the approved cutover. Preserve unrelated user changes and do not leave compatibility paths unless the contract requires them.
2. For non-trivial behavior, add or update tests for externally visible outcomes, invariants, boundaries, error paths, and regressions. Use approved seams, not mocks of internal wiring, copied constants, or bare execution assertions. Record a concrete applicability reason if no executable test is meaningful.
3. Run targeted tests and type checks as the tranche develops. Exercise the actual changed behavior with a real smoke scenario, including relevant failure paths. Research tickets retain sources, methods, findings, ambiguity, failed alternatives, and decision impact in their research record, with only decision-relevant conclusions propagated to exploration and the ticket.
4. Fix verification failures at their source and rerun the affected checks. Do not change the contract, suppress a warning, weaken checks, or special-case a fixture just to obtain a pass.
5. After observed verification, update the existing What to build text in the same turn with meaningful progress, changed paths, the command or scenario, actual result, limits, and the next exact resume point. Check only original acceptance items whose entire promised outcome is now observed. Partial implementation or an unexercised command remains unverified.

Keep these notes concise and current. Replace stale resume instructions rather than appending an activity log. Retain useful prior evidence, blockers, and user edits. Do not add H2 sections, a prefab evidence checklist, or a separate task ledger. A verified tranche records progress; it does not make the ticket Done before its final gates pass.

## Verify and review the finished ticket

When all promised tranches are implemented:

1. Exercise every ticket acceptance item against the actual implementation, including real smoke behavior and applicable contract checks. Run the relevant full test suite once at the end, plus repository-required suites and applicable coverage checks. Report a tooling-only or otherwise inapplicable profile honestly instead of manufacturing source or tests.
2. For frontend code or tooling changes, run the configured full TypeScript project check outside staged hooks. Use project configuration, not a compiler invocation with supplied source filenames. For affected Nix work, run declared flake checks and build affected system outputs where applicable without activation. Record actual runtime/platform and output coverage. Use manifests, scripts, and repository guidance for current commands rather than copying a stale command catalog.
3. Apply the lifecycle execution verification gate, including mandatory `pre-commit run --all-files`. Inspect hook changes, fix remaining failures, and rerun until stable and passing. Hooks do not replace smoke scenarios, tests, full frontend type checking, or other applicable contract checks. Follow the shared permission rule if Git metadata or a verification environment is missing; do not initialize Git or alter the checkout strategy automatically.
4. After verification, conduct a correctness, security, maintainability, test-quality, and spec-compliance review of the actual changes. Use a supported reviewer or a direct critical pass. The pre-code review protected the plan; this review must inspect implementation, callers, tests, and evidence. Resolve correctness blockers. Record any explicitly accepted remaining risk with its owner and effect.
5. If review requires changes, implement them and rerun affected acceptance, smoke, tests, contract checks, and the shared all-files gate until the final reviewed state is verified and stable.

Only then apply the lifecycle Done gate and record final evidence in the ticket. If research conclusively rejects an approach, preserve that finding as research evidence, not as delivered implementation. Notify the coordinator of outcomes that change dependent eligibility; each dependent still needs its own input/condition reassessment.

## Stop and resume truthfully

When blocked, preserve verified progress and unchecked unmet criteria. Record the concrete missing input or decision, what resolves it, the owner, and the precise next action or command under What to build. Apply the shared blocked-state rule. Inspect discoverable facts first; if a consequential user decision remains, use the shared one-question interview with a recommendation. Contract changes return to exploration before changing the spec or tickets.

A single ticket does not close its spec, move folders, close a tracker, commit, or activate systems. Hand whole-spec delivery to `implement-spec`; it independently verifies the promised outcome before reading `complete`.

Report changed files, actually satisfied acceptance items, observed verification and limits, remaining review risks or blockers, and the exact resume point when unfinished. Name unrun checks as unrun. Never report an unverified or Unnecessary outcome as implemented.
