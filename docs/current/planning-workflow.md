# Local planning workflow

This repository uses local Markdown planning artifacts and the workflow skills in [`.agents/skills/`](../../.agents/skills/). These are developer workflows, not Batocera or Wolf runtime capabilities. The skills and their shared references define the current procedure; the template-derived records below retain historical exercises, not verification runs against this application.

## Artifacts and responsibilities

[The lifecycle reference](../../.agents/skills/_shared/lifecycle.md) owns paths, states, permission boundaries, and delivery gates. Specs and epics have separate workspaces under `docs/active/`; completed and archived folders retain their records and assets. The table routes work to its existing owner rather than defining another workflow policy.

| Owner                                                            | Current behavior                                                                                                                                                        |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [grilling](../../.agents/skills/grilling/SKILL.md)               | General one-question-at-a-time stress-testing without document updates.                                                                                                 |
| [grill-with-docs](../../.agents/skills/grill-with-docs/SKILL.md) | Resume/create exploration, persist answered decisions before advancing, and resolve domain terminology. Does not generate the spec.                                     |
| [to-spec](../../.agents/skills/to-spec/SKILL.md)                 | Synthesize saved exploration into the original seven-section Draft; explicit approval is required for Ready.                                                            |
| [to-tickets](../../.agents/skills/to-tickets/SKILL.md)           | Require a Ready spec, review grouping/blockers/conditions, and create approved local tickets using Parent, What to build, checkbox Acceptance criteria, and Blocked by. |
| [implement](../../.agents/skills/implement/SKILL.md)             | Execute one authorized eligible ticket with plan review, actual acceptance verification, and implementation review.                                                     |
| [implement-spec](../../.agents/skills/implement-spec/SKILL.md)   | Coordinate eligible work, reassess each dependent, verify the whole contract, and hand off accepted delivery.                                                           |
| [wayfinder](../../.agents/skills/wayfinder/SKILL.md)             | Own shared epic outcomes and linked-spec context without nesting children or treating planning readiness as delivery.                                                   |
| [complete](../../.agents/skills/complete/SKILL.md)               | Independently enforce delivery, move intact folders, repair references, archive known dispositions, and maintain factual current topics.                                |

The shared [interview reference](../../.agents/skills/_shared/interview.md) requires one consequential question, useful comparisons only when relevant, and saved answers before the next question. Discoverable facts come from research, not user interrogation. Exploration captures requirements, decisions, rationale, constraints, and unresolved choices, not loading narration or routine activity. Generation issues return to exploration first; corrected decisions then propagate into the spec and tickets.

## Execution and delivery boundaries

Use the [lifecycle reference](../../.agents/skills/_shared/lifecycle.md) for permanent ticket identities, input and condition eligibility, per-dependent reassessment, parallel ownership, and permission boundaries. Use [implement](../../.agents/skills/implement/SKILL.md) for ticket execution and [implement-spec](../../.agents/skills/implement-spec/SKILL.md) for whole-spec acceptance. A terminal ticket label does not establish whole-spec or combined epic delivery.

[Complete](../../.agents/skills/complete/SKILL.md) owns completed/archived placement, destination collision refusal, intact moves, and reference repair. Historical records can retain legacy ledgers and dated status notes; they do not establish a second current execution procedure.

[Current-state maintenance](../../.agents/skills/complete/references/current-state.md) describes verified behavior by topic and replaces obsolete claims. Direct updates need no completion record or lifecycle move. Completion reviews added, changed, and removed impacts and links the affected topics. [Domain modeling](../../.agents/skills/domain-modeling/SKILL.md) owns glossary and ADR format/selection; records are offered only when all three decision criteria hold.

## Existing-repository documentation

[docs-baseline](../../.agents/skills/docs-baseline/SKILL.md) establishes or reconciles shared standards and qualifying ADRs without changing application behavior or importing unrelated template tooling. Its bundled recipes support use without an external template checkout. Existing equivalent standards retain ownership; conflicting policy requires a one-question review before replacement. ADR selection and format remain owned by domain-modeling.

Default shared and dependency injection guidance describes policy for new or changed code, not verified compliance of existing code. Unknown rationale stays unknown. Documentation bootstrap does not require specs, tickets, a populated ADR directory, or unrelated technology profiles.

## Template-derived evidence and limits

The retained [template delivery record](../completed/specs/template-standards-and-workflow/completion.md) and [whole-spec acceptance ticket](../completed/specs/template-standards-and-workflow/tickets/07-whole-spec-verification.md) describe exercises performed for ProjectTemplate. They are attributed historical evidence for the inherited workflow design. They do not prove that this application's checks, deployments, emulator behavior, or shortcuts passed.

Those records report fresh-context exercises for saved-answer resumption, withheld Ready, approved grouping, and refusal of invalid ticket sources without tracker calls. A nine-ticket graph covered negative research, false/unresolved conditions, missing inputs, independently eligible work, and per-dependent reassessment. Real fixture outputs gated Done and whole outcomes.

The template completion fixtures covered unmet-acceptance refusal, intact child moves and repaired sibling/parent/research/current links, combined epic acceptance, destination collision refusal, known-disposition archival, and direct current updates removing unsupported claims. Wayfinder exercises retained dense intake and shared contracts without requiring placeholder specs.

The template's docs-baseline fixtures used a Python repository without docs and a React repository with conflicting policy. They report preservation of original files, no invented ADR rationale or unrelated tooling defaults, and a partial outcome for deferred policy conflicts. The repeatability check reused the same agent context, not a fresh session.

The template record also reports session-cached native skill discovery. Current instructions permit direct `SKILL.md` loading without a named invocation tool. Skill source availability is not evidence that a particular host session has refreshed its discovery list.
