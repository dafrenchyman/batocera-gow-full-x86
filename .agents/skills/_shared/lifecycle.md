# Local planning lifecycle

Read this reference before generating tickets, executing work, or changing lifecycle placement. It owns locations, states, dependency rules, and authorization. Interview rules live in [interview.md](interview.md).

## Documents and ownership

- Specs: `docs/active/specs/<name>/spec.md`, with sibling `explore.md`, `tickets/<NN>-<short-name>.md`, and research when needed.
- Epics: `docs/active/epics/<name>/epic.md`, with exploration and shared research when needed. Link specs in their own spec folders; never nest them under epics. Standalone specs need no epic.
- Finished work: move the entire folder to `docs/completed/specs/<name>/` or `docs/completed/epics/<name>/`.
- Rejected, abandoned, or superseded work: move the entire folder to `docs/archived/specs/<name>/` or `docs/archived/epics/<name>/`, preserving disposition, reason, and replacement links.
- Pursued paused or blocked work stays active. An Unnecessary ticket stays in its spec.
- Implemented behavior belongs in topic documents under `docs/current/`. Definitions belong in root `GLOSSARY.md`; qualifying ADRs belong in `docs/adr/` using domain-modeling.

`explore.md` owns reasoning and accepted decisions. `spec.md` owns the approved implementation contract. Tickets own execution progress and observed evidence. `epic.md` owns shared outcomes, capability routing, and linked-spec sequencing. Do not create a parallel execution `tasks.md` or alternate tracker tree.

## Approval and state

A spec starts Draft. Only explicit user approval makes it Ready. Readiness is not execution authorization. An epic can be Planning ready while delivery is incomplete. Ticket breakdown approval authorizes file creation, not implementation.

After verified delivery and completed placement, the owning spec or epic has `Status: Completed`. Archived placement uses `Status: Archived` with its precise rejection, abandonment, or supersession disposition. Neither state can be inferred from planning readiness or terminal ticket labels.

| Ticket status | Meaning                                                                                                             |
| ------------- | ------------------------------------------------------------------------------------------------------------------- |
| Pending       | Not started; eligibility must be evaluated.                                                                         |
| In progress   | Claimed with an explicit owner/resume point; authorized work is underway.                                           |
| Blocked       | A required input, decision, or condition is missing or unresolved. Record what unblocks it.                         |
| Done          | Promised work and verification are observed, with acceptance evidence. Conclusive negative research can be Done.    |
| Unnecessary   | Work must not execute under an evidenced false condition or invalidated scope. Preserve the record and explain why. |

Assigned ticket numbers are permanent identity, not scheduling order. Never delete, reuse, or renumber them. Allocate a new unused number for added work. Keep original acceptance criteria; check boxes only for actually satisfied criteria. Unnecessary work is not implemented work, and its unmet boxes remain unchecked.

## Eligibility and dependent reassessment

`Blocked by` declares required prerequisite tickets. An optional `Proceed only if` condition is distinct from those blockers. Before starting, verify actual required inputs exist, prerequisite outcomes satisfy the dependency, and the condition permits execution. Terminal status alone does not supply a missing artifact.

- False condition: preserve the ticket as Unnecessary with the finding and evidence.
- Unresolved condition: retain Blocked; do not guess or execute.
- True condition with missing input or unsatisfied prerequisite: retain Blocked and identify the input.
- Inputs and prerequisites satisfied, condition true or absent: Pending work is eligible.

After a prerequisite changes, reassess every dependent individually. If the prerequisite is Unnecessary, a dependent may proceed with sufficient alternate inputs, become Unnecessary under its own false condition, or remain Blocked for a missing input. Do not blanket-unblock or cancel a subtree. Conclusive negative research answers its question but does not authorize the rejected implementation. Inconclusive research remains unresolved.

Contract-changing discoveries return through grill-with-docs to correct exploration before updating the spec and affected tickets. Do not quietly change the contract in an execution note.

## Execution and permission

Use the current checkout by default. Independent work may run in parallel only with disjoint edits/resources or an agreed integration owner. Sequence conflicting work. Record ownership, blockers, meaningful verified progress, and exact resume points in the existing ticket, not a new ledger.

Implementation authorization does not authorize commits, branch changes, worktrees, resets, publishing, deployment, or system activation. Obtain explicit permission for each such action. Never require hosted credentials, a tracker, or Git isolation merely to plan or execute local documents.

Before an implementation ticket is Done: exercise its changed behavior, run applicable contract checks, run `pre-commit run --all-files`, inspect fixes and rerun until stable, and resolve correctness review blockers. Report actual scope/platform limits. If the project lacks Git metadata, do not initialize it without permission; agree on or use an authorized disposable verification checkout of the actual files, and retain that limitation in evidence.

## Delivery gates

A spec completes only when every ticket is Done or Unnecessary with records and the whole promised spec outcome passes independently. Checked tickets do not waive missing acceptance.

An epic completes only when every required linked spec is completed and combined outcomes, including interactions, pass. Explain linked work made unnecessary without waiving a required epic outcome. Planning readiness, archived work, or deferred work is not delivery.

Use [complete](../complete/SKILL.md) for verified completion, archival, reference repair, and current-documentation review. Whole-folder moves must preserve exploration, tickets, research, and useful assets; repair incoming and outgoing references, including links in other specs, epics, research, and current documents. Do not overwrite an existing destination or publish a partial outcome as completed.
