# <Specification title>

Status: Draft
Parent epic: <relative link or None>
Decision record: [explore.md](explore.md)

## Problem Statement

Describe the problem from the user's perspective, its context, and the consequences of leaving it unresolved.

## Solution

Describe the user-visible outcome, accepted approach, and concrete user/system flow. Include boundaries and failure behavior when they clarify the contract.

## User Stories

Use a numbered list of substantive stories that covers the accepted behavior and relevant actors. Do not pad the list or introduce scope not accepted in exploration.

1. As an <actor>, I want <behavior>, so that <benefit>.

## Implementation Decisions

Capture accepted modules, boundaries, interfaces, technical clarifications, architecture, data/state contracts, and specific interactions. Include dependencies, execution conditions, relevant alternatives and reasons, migration constraints, and accepted risks.

Include the implementation/reuse inventory: existing behavior and tests, partial behavior and gaps, absent behavior, and conventions to reuse. Keep meaningful file paths and actual accepted sketches, sample data, interfaces, timing examples, and decision-rich snippets where they define the contract. Label illustrative examples and unaccepted proposals. Summarize relevant research constraints and link their evidence.

Use topic-level H3 headings as needed; keep these details within the original section structure.

## Testing Decisions

Identify the observable acceptance outcomes for the whole spec and how each will be verified. Describe good tests of external behavior, errors, boundaries, invariants, and transitions rather than implementation details.

Name the modules or consumer seams to test and existing test prior art. Prefer the highest meaningful existing seams. State any necessary new seam and its reason. Include unit tests for non-trivial logic or explain why they do not apply. Identify brittle external coupling and honest verification limits. Avoid broad rituals that do not prove the changed behavior.

Keep implementation progress and observed evidence in tickets, not a separate execution checklist here.

## Out of Scope

State accepted non-goals, deferred behavior, and conditions for later consideration. Do not count a deferred or conditional outcome as delivered.

## Further Notes

Include remaining decision-relevant context, linked research, parent or sibling coordination, and explicitly accepted risks or deferrals not already covered. Consequential unanswered questions must return to exploration before Ready approval. The spec must remain understandable without reading its parent or raw intake.
