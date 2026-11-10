---
name: to-tickets
description: Propose and review a ticket breakdown from an explicitly Ready local specification, then create approved single-file tickets. Use for grouping, merges, splits, blockers, and execution conditions after specification approval.
---

# To tickets

Read [the lifecycle reference](../_shared/lifecycle.md) before evaluating the source, dependencies, ticket identities, statuses, and approval boundaries. Read [the shared interview rules](../_shared/interview.md) before discussing the breakdown. Use available host skill discovery or read a named skill's `SKILL.md`; no tracker or setup service is required.

## Require a Ready source

Find and read the complete owning `spec.md`, saved exploration, relevant research, parent epic and linked dependencies, and any existing tickets. Accept only a complete local specification explicitly approved as Ready. Exploration, chat-only plans, raw briefs, Draft or incomplete specifications, and blocked sources cannot generate tickets.

For unsaved planning or consequential missing decisions, use `grill-with-docs` first. For settled saved exploration awaiting synthesis or approval, use `to-spec`. Name the missing gate rather than treating a request for tickets as implicit specification approval. A Ready spec may contain conditional work with a defined decision mechanism; that differs from a blocked or unapproved source.

Inspect code, tests, glossary, and relevant ADRs to understand existing implementation and reusable behavior. Preserve meaningful paths and accepted decision-rich examples when they clarify a ticket's contract. Do not add refactors or an application architecture merely to make a familiar breakdown.

## Propose verifiable slices

Draft the breakdown in the conversation before writing ticket files. For each candidate show its proposed identity or existing number, title, end-to-end deliverable, observable acceptance, required inputs and blockers, and any distinct execution condition.

Prefer narrow but complete vertical slices through the layers the actual behavior needs. Each slice must be independently demonstrable or verifiable, with its tests and relevant documentation included. Research and tooling changes should deliver their actual findings or usable configuration, not pretend to require schema/API/UI layers. Keep slices bounded enough for an independent implementation session without turning a layer or activity into a fake user outcome.

A wide mechanical refactor may need a coordinated cutover instead of independently working vertical slices. State its shared contracts, callsite migration, integration owner, and verification point. Sequence conflicting edits and permit independent non-conflicting slices. Use the current checkout by default; do not assume an integration branch, worktree, CI pipeline, or temporary compatibility API. Retain obsolete paths only when the approved spec explicitly requires staged compatibility.

Make blocker edges reflect genuine required inputs, not numbering or a preference for serial work. Describe an optional `Proceed only if` condition separately. A research ticket needs a conclusive question and evidence expectations; its negative answer may resolve research without supplying the input for a dependent implementation.

## Review one decision at a time

Present the proposed breakdown, then discuss the most consequential unresolved grouping, merge, split, deliverable, blocker, or condition using the shared interview method. Ask exactly one decision and wait. Revise the proposal after each answer and review all remaining choices before the final approval question.

If a proposed change alters the Ready specification's contract, return to `grill-with-docs` to correct exploration, then `to-spec` for review and approval before continuing. Do not hide a scope change inside ticket text.

Once the breakdown is settled, ask explicitly whether the user approves this breakdown for local ticket creation. Wait for approval. This permits files only, not execution.

## Create the approved files

Before creation, read [the original ticket template](references/ticket-template.md). Create one file per approved ticket in the owning spec's `tickets/` folder. Preserve its original Parent, What to build, Acceptance criteria, and Blocked by H2 sections plus Status metadata. Use unchecked acceptance boxes. Put any distinct optional condition in What to build, not in a new H2 section.

Apply the lifecycle reference's permanent-number and status rules. Inventory existing identities before allocating new numbers. Preserve existing ticket records, user edits, observed evidence, and checked criteria; update approved affected content surgically rather than regenerating completed or in-progress work. Retain invalidated tickets with their disposition instead of deleting or reusing them. Do not create a second execution ledger or alternate ticket tree.

Link Parent to the owning local spec and blockers to their actual ticket files. Set new eligible tickets Pending; set tickets with missing prerequisites or unresolved conditions Blocked and state what resolves the block. For an approved false condition or invalidated slice, retain its evidenced Unnecessary disposition according to the lifecycle rules. Required input availability must remain explicit even when a prerequisite has a terminal status.

Before handing off, ensure every approved deliverable is represented, the graph has no cycles, links and conditions are unambiguous, and the files match the approved proposal. Return the ticket paths and next authorized planning step. Do not execute work, publish issues, or modify the parent specification's approval as a side effect.
