# 03: Rewrite the local planning workflows

**Status:** Done

## Parent

[Template standards and local planning workflows](../spec.md)

## What to build

Make plain grilling, durable exploration, specification generation, and reviewed local ticket creation work as separate, reachable workflows. Plain grilling does not update exploration or domain documents. Grill-with-docs saves one answered choice before the next question, resumes from local decisions, applies the relevance gate, and uses domain-modeling for relevant terminology/ADR decisions. Share interview rules without competing authority.

To-spec synthesizes saved exploration/research and existing implementation into a local Draft using its existing template, preserves meaningful contracts/examples and user edits, and requires explicit approval for Ready. Consequential errors return to exploration first. To-tickets accepts only Ready specifications, discusses grouping/blockers/conditions, and creates approved single-file tickets using the original Parent, What to build, Acceptance criteria, and Blocked by sections plus status. Remove tracker publication, exploration/chat-only ticket sources, temporary alternate ticket trees, and a separate task ledger.

Migrate useful templates, references, descriptions, and metadata, applying unslop and writing-for-agents. Invocations must be supported by the host rather than assume an unavailable mandatory tool. Exercise actual generation/refusal/resumption behavior on disposable artifacts without tracker credentials. Preserve legacy sources until remaining responsibilities/callers migrate in ticket 06; run the required all-files hooks and remove fixtures.

Implemented four planning owners, progressive original spec/ticket templates, exploration/research references, matching model-callable metadata, and shared interview rules. Shared lifecycle rules define permanent identities and distinct state/condition semantics; execution/completion integration remains ticket 04's responsibility.

Actual controlled workflow exercises used fresh agent contexts and disposable local files with supplied user answers. Resumption asked one question, retained an inclusion proposal as unaccepted, then saved the answered policy and opaque-ID contract before generating a seven-heading Draft. Domain modeling wrote only the resolved receipt definition. The generated Draft preserved the exports path, JSON shape, and IDs and withheld Ready. Explicit approval changed Ready; grouping review created no tickets. Separate creation approval produced one Pending ticket with the original four sections and seven unchecked criteria, without execution. Exploration-only, Draft, and labelled-Ready-but-blocked sources were refused. An unresolved generation decision returned to exploration without modifying the Draft; plain grilling asked one question and changed no documents.

The actual template copy passed all eight hooks with pre-commit run --all-files after reviewed table alignment. No tracker credentials or operations were used. Disposable workflow artifacts were inspected and removed.

## Acceptance criteria

- [x] The four skills implement their spec-defined roles without competing authority, multi-question rounds, hidden approval bypasses, or tracker publication.
- [x] A resumed interview can recover decisions from local files. It updates exploration before advancing and performs relevant domain-modeling updates without inventing ADRs.
- [x] Draft/Ready and ticket-breakdown gates are demonstrated through actual workflow exercises. Meaningful file paths and examples survive specification generation.
- [x] Tickets have permanent identities and one execution ledger. Status distinguishes pending, in-progress, blocked, Done, and Unnecessary work without treating number order as scheduling.
- [x] Descriptions, metadata, templates, and cross-skill references agree with the new behavior. Rewritten prose has no em dashes or session filler.

## Blocked by

- [02: Build the working tooling baseline](02-tooling-baseline.md)
