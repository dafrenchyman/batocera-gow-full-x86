# Current-state documentation

Read this for every completion review and whenever the user requests a direct current-documentation update. [Complete](../SKILL.md) owns invocation and lifecycle operations; [the lifecycle reference](../../_shared/lifecycle.md) owns document locations. This reference owns the procedure for maintaining the topic-organized description of what the project actually does now.

Direct updates follow the same procedure without completing or moving work. Do not require a spec, epic, completion record, or application runtime for a documentation-only request. Tooling and developer workflows can be the substantive current behavior of a template repository.

## Gather actual sources

Read the relevant current documents before editing. Locate the real implementation, configuration, tests, observed verification and reviews, and any relevant delivered records. Read exploration and approved contracts only to identify intended impacts or explain approved deviations; a plan is not proof of implemented behavior.

Ground each material current claim in actual implementation and appropriate verified evidence. Record source paths, relevant completion links when available, observed results, and platform or scenario limits. Existing current documents may be stale and do not independently prove their own claims. When evidence is missing, retain the uncertainty explicitly and seek the needed facts instead of promoting the plan. Done negative research and Unnecessary implementation records explain exclusions, not implemented capability.

If no completion exists, link the actual code/configuration or verification sources that support the update. Do not fabricate delivery provenance. Versions and runnable commands remain authoritative in their owning configuration; link them where possible instead of maintaining a second copied inventory.

## Classify impact by topic

For each affected topic, review what was added, changed, or removed across:

- User- or system-visible behavior and capabilities.
- Architecture, runtime boundaries, integrations, build, and tooling.
- Data contracts, storage, migrations, persistence, and synchronization.
- User workflows, failure handling, safety constraints, and access boundaries.
- Developer and operations behavior, including setup, verification, maintenance, deployment, and recovery where present.

No user-visible change does not mean no documentation impact. An internal configuration or workflow change can alter developer operations. Conversely, a small implementation detail with no durable effect does not justify a new topic file.

For completion, retain the review disposition in `completion.md`: topics updated with links, or no substantive current-documentation impact with a specific reason. Direct updates may report that disposition in the requested result. Do not create a blank topic or an activity log solely to prove the review occurred.

## Update the current description

Reuse the existing topic organization under `docs/current/`. Create a topic document only when there is substantive implemented behavior or an actual constraint to describe. Use descriptive names suited to the project, such as tooling, planning workflow, persistence, or a user capability. An application-oriented `app.md` index is optional, not required for a tooling-only repository. Keep an existing index concise and link topics when that helps navigation; avoid a second copy of each topic's facts.

For each affected topic:

1. State the behavior that exists now and its useful boundaries, including configuration, failure behavior, platform support, privacy, or operational constraints that affect readers.
2. Replace changed descriptions and remove obsolete claims when implementation removed, superseded, or contradicted them. Inspect other topics and index summaries for the same stale claim so deletion is reflected everywhere it is authoritative.
3. Keep relevant source and delivery links close to the claims they support. Use only verification actually observed, with scope and limits. A narrow successful scenario does not prove a broader capability.
4. Keep planned, rejected, deferred, and Unnecessary work out of implemented sections. A concise known limitation can prevent readers from assuming absent behavior exists, but it is a present constraint, not a roadmap or promise.
5. Preserve unaffected user edits and useful current detail. Do not paste specs, ticket checklists, raw intake, research transcripts, completion histories, or future tasks into the current description.

A substantive topic may use these sections where applicable, not an empty required template:

- Current behavior and workflows.
- Architecture, tooling, and operational boundaries.
- Data and persistence.
- Verification evidence and actual limits.
- Source and completion references.

## Completion and epic review

A spec completion updates all affected current topics or records the no-impact disposition. Link the current topics from the completion record and use relevant completion backlinks for material changes. If several deliveries changed a topic, retain the sources that explain the present behavior rather than an exhaustive chronology. Repair those backlinks when a referenced folder moves.

Epic completion reviews the aggregate result: cross-spec interactions, shared configuration, end-to-end workflows, and constraints visible only when children are combined. Read existing child updates and revise only missing, changed, contradictory, or removed aggregate claims. Link child and epic evidence where relevant without copying each child's current-documentation update into a new epic topic.

## Finish on truthful claims and links

Resolve affected links from their final locations to actual targets, including any moved completion records and relevant anchors. Every added or revised claim must be implemented now and supported by its cited source/evidence. Every removed impact must leave no contradictory authoritative current claim. Completion's recorded topic links or no-impact disposition must match the result.

If implementation or verification cannot support a requested claim, state the exact missing evidence. Keep the current description factual rather than making an unsupported update to satisfy a documentation request.
