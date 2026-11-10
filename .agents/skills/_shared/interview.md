# Interview rules

Read this reference before an interview or a planning review that asks the user to choose. It owns the interview method and the relevance gate. The calling skill determines whether the interview is conversational or persistent.

## One decision at a time

Map a design tree. Each consequential decision has prerequisites and may expose further decisions. Choose the highest-leverage unresolved decision whose prerequisites are settled. Ask exactly one question, explain why it matters, recommend an answer, and compare the relevant alternatives. Word the question so that an unqualified "yes" accepts the stated recommendation. Then wait for the answer.

A comparison, sketch, sample object, or code snippet belongs with the question only when it clarifies that choice. Prefer actual repository examples. Label illustrative code and proposals as such; showing them does not make them accepted requirements.

After the answer, revise the tree before choosing the next question. A consequential choice remains the user's decision. Keep assumptions separate from accepted decisions. Do not bundle independent choices into one question or treat silence as agreement.

## Find facts before asking

Inspect repository code, tests, manifests, glossary, ADRs, and relevant planning documents for facts the environment can answer. Use primary sources for external claims. Use available read/search tools directly; use a suitable research agent only when useful and supported by the host. No particular tool name or agent service is required.

Distinguish observed behavior, sourced facts, inference, and unknowns. If research is needed, treat its result as an unresolved prerequisite. You may ask one independent decision while that research runs. A missing fact is not permission to guess or ask the user to do discoverable reading.

## Relevance gate

Before adding persistent exploration text, ask: would removing this change a future specification, the resolution of an open question, or the understanding of a meaningful tradeoff? If not, omit it.

Keep requirements, constraints, accepted choices, proposals, rejected or deferred alternatives with useful reasons, meaningful assumptions, risks, and unresolved questions. Update the existing topic instead of appending duplicates. Omit transcripts, routine file changes, chronology, loaded skills, approval announcements, and cleanup narration. Approval can change artifact status; it does not need a second exploration entry celebrating the change.

Keep detailed research in a research record and bring decision-relevant findings back to exploration. A failed approach matters when it prevents repeating a mistake or changes the decision. Routine actions do not.

## Persistent mode

At intake or resumption, read the saved exploration, any existing spec and tickets, relevant research, parent epic, linked dependencies, and relevant archived alternatives. Recover accepted decisions, outstanding questions, deferred choices that still affect this work, risks, and the next discussion queue. Do not require previous chat history.

For a dense brief, preserve the actual contracts, paths, examples, sketches, data shapes, workflows, safety language, timing details, and non-goals that carry meaning. Sort them into existing topic sections rather than dumping the source. Distinguish the user's stated requirements from agent recommendations and unconfirmed assumptions. If artifacts disagree, resolve the consequential conflict as the next question rather than silently picking a version.

Save each answered choice in the appropriate exploration topic before asking the next question. Record its scope, useful rationale, affected alternatives, and any changed assumptions or risks. Remove resolved questions from the active queue or mark their disposition. If saving fails, finish saving before advancing. Save research constraints and accepted terminology changes at the same boundary.

After a tangent or research branch, capture the relevant result and return to the highest-leverage unresolved topic. Prefer choices that can change scope, architecture, data shape, or work order, then relevant deferred choices, invalidating assumptions or risks, and thin requirements needing concrete examples. End a planning turn with that one question, not an activity report, while such topics remain. A request limited to batch artifact updates may end with the requested artifact result instead.

When no meaningful topic remains, review for contradictions, unresolved prerequisites, and unaccepted risks. State the readiness or blocker and name the next planning step. This does not authorize specification approval, ticket creation, or execution.

## Conversational mode

Use the same decision tree and fact-finding method without creating or updating exploration, glossary, ADRs, or other domain documents. Keep the working decisions in the conversation. When the tree has no unresolved consequential branch, summarize the resulting position and ask the user to confirm shared understanding. Confirmation does not authorize implementation.
