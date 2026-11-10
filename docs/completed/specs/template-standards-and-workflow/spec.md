# Template standards and local planning workflows

Status: Completed
Parent epic: None
Decision record: [explore.md](explore.md)

Delivered with all seven tickets Done and whole-spec acceptance verified. See [completion.md](completion.md) for observed results and limits.

## Problem Statement

A developer forking this repository needs useful Python, React, and Nix/NixOS coding standards and working development tooling, without inheriting an unwanted application architecture. The standards are mostly empty, and the copied planning skills assume an issue tracker while the documented skills use a competing local convention.

Long design discussions also lose decisions when context grows. The developer needs decisions captured during exploration, followed by a specification and reviewed tickets, without turning planning documents into transcripts or activity logs.

## Solution

Provide prescribed, optional technology profiles and one local planning workflow. A fork uses shared standards plus the profiles relevant to its code. The template includes tooling-only Python and React configuration, actual pre-commit hooks, locked dependencies, and an optional stable-Nix development shell. It includes no starter application or NixOS host.

Exploration, specification, tickets, implementation, and completion remain separate steps. Use the existing to-spec and to-tickets templates, replacing tracker publication with local documents and retaining the agreed review and execution gates.

The document locations are part of the user-facing workflow contract:

| Artifact                    | Local location                                                                                     |
| --------------------------- | -------------------------------------------------------------------------------------------------- |
| Active spec and exploration | `docs/active/specs/<spec_name>/spec.md` and sibling `explore.md`                                   |
| Ticket                      | `tickets/<NN>-<short-name>.md` inside its owning spec folder                                       |
| Research                    | `research/<topic>.md` inside the owning planning folder when needed                                |
| Active epic                 | `docs/active/epics/<epic_name>/epic.md`                                                            |
| Completed work              | Whole folders under `docs/completed/specs/` or `docs/completed/epics/`                             |
| Archived work               | Whole folders under `docs/archived/specs/` or `docs/archived/epics/`                               |
| Current behavior            | Topic-organized documents under `docs/current/`                                                    |
| Standards                   | Shared, repository-layout, Python, React, and combined Nix/NixOS documents under `docs/standards/` |
| Decisions and vocabulary    | Qualifying records under `docs/adr/` and definitions in root `GLOSSARY.md`                         |

Specs are linked to epics, never nested inside them. Standalone specs remain valid. Python configuration stays at the repository root; future importable Python code uses `src/<python_package>/` with `tests/`. React tooling and future source use `web/` and `web/src/`. Flake files stay at the root, with supporting Nix modules in `nix/` when needed. These placements do not require creating unused scaffolds or treating Python as a backend.

## User Stories

1. As a template maintainer, I want reusable shared and technology-specific standards, so that future forks have a consistent starting point.
2. As a developer, I want only applicable technology profiles to be required, so that a Python-only project does not need frontend tooling or Nix.
3. As a coding agent, I want default project guidance to describe actual contents and route me to applicable standards, so that I load relevant rules without copying them into every instruction file.
4. As a fork maintainer, I want deliberate tool substitutions documented in configuration and agent guidance, so that the project can adapt while preserving its quality checks.
5. As a Python developer, I want a conventional source layout and uv-managed development dependencies, so that tooling works without a dummy installable package.
6. As a contributor, I want runtime selections and generated lockfiles aligned across project tooling, hooks, and the optional shell, so that verification is reproducible.
7. As a Python developer, I want Ruff to handle linting, imports, and formatting with ALL rules and safe fixes, so that I have broad checks without separate Black/isort defaults.
8. As a Python developer, I want strict typing and narrow, explained exceptions for untyped dependencies, so that unrelated typing problems remain visible.
9. As an API consumer, I want Google-style docstrings to explain inputs, outputs, constraints, and relevant exceptions, so that annotations alone are not my only documentation.
10. As a React developer, I want framework-neutral npm/TypeScript tooling with strict indexed-access checks, so that missing values and cross-file type errors are found before completion.
11. As a frontend developer, I want ESLint fixes and Prettier formatting to cooperate through actual remote hooks, so that automatic fixes do not produce a formatting loop or silently skip code.
12. As a React developer, I want built-in state tools by default and external libraries only for concrete needs, so that the template does not impose unnecessary architecture.
13. As a tester, I want pytest and user-visible React component tests, with Playwright available for critical browser journeys when needed, so that tests exercise consumer behavior.
14. As a reviewer, I want meaningful behavioral tests plus independent Python/React coverage floors, so that a percentage cannot hide missing assertions or gaps in another profile.
15. As a Nix user, I want stable, locked flakes and Alejandra formatting with check-only Statix/deadnix, so that environment changes are reproducible without automatic structural rewrites.
16. As a developer, I want both system-wide tools and optional Nix-shell entry to work, so that the shell is helpful rather than mandatory.
17. As a NixOS maintainer, I want affected configurations built without activation and honest coverage limits, so that verification does not unexpectedly change a running system.
18. As a participant in a design discussion, I want one consequential question at a time with relevant tradeoffs and examples, so that I can make decisions without confronting a huge question batch.
19. As a returning participant, I want exploration updated after each answer, so that work can resume from local files without relying on chat history.
20. As a reader, I want exploration limited to requirements, decisions, constraints, useful rationale, and unresolved questions, so that routine actions do not consume valuable space.
21. As a domain owner, I want terminology challenged and resolved in the glossary, so that requirements and code use consistent vocabulary.
22. As a future maintainer, I want ADRs offered only for hard-to-reverse, surprising, genuine tradeoffs, so that decision records explain important choices rather than fill a directory.
23. As a reviewer, I want to-spec to synthesize saved exploration into a local Draft using its existing template, so that accepted decisions survive without another invented document structure.
24. As a decision maker, I want generation issues corrected in exploration first and Ready status to require my approval, so that specification generation cannot silently change the contract.
25. As a planner, I want tickets derived only from a Ready spec and the grouping discussed before file creation, so that implementation work reflects an approved split.
26. As a ticket reader, I want the existing Parent, What to build, Acceptance criteria, and Blocked by sections with acceptance checkboxes, so that local storage does not bring an unnecessary new template.
27. As an implementer, I want ticket identities retained and progress/evidence recorded in the ticket, so that unfinished and invalidated work remain understandable without a second task ledger.
28. As a researcher, I want conclusive negative findings to complete research without authorizing a rejected implementation, so that useful evidence is retained and dependents are reassessed.
29. As an implementation coordinator, I want explicit blockers and separate conditions, so that work starts only when inputs exist and conditions permit it.
30. As an implementer, I want independent non-conflicting work to run in parallel while conflicts are sequenced, so that concurrency does not corrupt the shared checkout.
31. As the repository owner, I want commits, branches, worktrees, and system activation to require explicit authorization, so that implementation and verification do not imply those permissions.
32. As a reviewer, I want actual acceptance evidence and all-files hook verification before implementation tickets are Done, so that checked boxes represent observed outcomes.
33. As a planner, I want an epic to own shared outcomes and linked spec sequencing while specs own their detailed work, so that bounded work does not require an artificial parent or nested folders.
34. As a product owner, I want spec and epic completion to verify promised outcomes, including cross-spec interactions, so that individually finished pieces are not mistaken for a working whole.
35. As a maintainer, I want completed folders moved intact and affected references repaired, so that exploration, research, and tickets remain navigable.
36. As a planner, I want rejected, abandoned, and superseded work archived with reasons while pursued blocked work stays active, so that unsuccessful work is not represented as completed.
37. As a reader, I want completion to update topic-organized current-behavior documentation and remove obsolete claims, so that I can understand what the project actually does now.
38. As a workflow user, I want one merged skill family with reachable references and accurate metadata, so that legacy trackers, paths, or missing skill calls do not compete with the new process.
39. As a security-conscious contributor, I want reviewed hook pins and truthful trust boundaries, so that reproducibility or a limited source review is not presented as proof of safety.
40. As a template maintainer, I want tooling verified through disposable meaningful fixtures rather than permanent dummy applications or tests, so that the template remains a clean starting point.

## Implementation Decisions

- Keep one workflow family with these owners:

  | Skill           | Responsibility                                                                                                                                          |
  | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
  | grilling        | General one-question-at-a-time stress-testing, without exploration or domain-document updates.                                                          |
  | grill-with-docs | Create/resume durable exploration, capture each answered choice, and use domain-modeling when relevant. Does not generate specifications.               |
  | to-spec         | Synthesize saved exploration into a reviewed local Draft using the existing template; obtain explicit Ready approval.                                   |
  | to-tickets      | Derive a proposed breakdown only from a Ready spec, review grouping/blockers/conditions, and create approved local tickets using the existing template. |
  | implement       | Execute one authorized local ticket, review its plan and implementation, verify acceptance, and persist progress/evidence.                              |
  | implement-spec  | Coordinate the permitted ticket graph, reassess conditional work, verify whole-spec acceptance, and invoke complete.                                    |
  | wayfinder       | Explore an epic, preserve its capability/backlog context, track linked specs, and distinguish planning readiness from delivery.                         |
  | complete        | Enforce completion gates, move whole folders, repair references, and review/update current-behavior documentation.                                      |

- Absorb documented-spec into grill-with-docs and to-spec, documented-spec-implementation into implement-spec, documented-epic into wayfinder, and documented-completion/current-state into complete. Migrate useful behavior, templates, callers, and metadata before removing the five obsolete skills. Keep no compatibility aliases or competing workflow authority.
- Retain domain-modeling, unslop, writing-for-agents, research, and tdd as supporting capabilities. Keep shared interview/lifecycle rules authoritative in one place and reach references explicitly. Put detailed current-documentation rules in a reference owned by complete; direct current-documentation updates remain possible without completing work.
- Align descriptions, invocation settings, agent metadata, and actual supported skill discovery. Automatically invoked skills must be reachable; human-only skills cannot be described as automatically callable. Resolve absent setup/review/prototype/design dependencies through reachable instructions without installing another unapproved skill family. Preserve review intent, not broken invocation names.
- Preserve existing implementation/reuse inventory, meaningful dense intake, research findings and failed alternatives, review gates, and resumable state. Route epic capabilities to shared decisions, named backlog work, research, explicit disposition, or accepted risk. Keep optional/conditional work visible; do not require placeholder specs for every candidate. Child specification generation follows the same exploration/to-spec contract as standalone work.
- Grill-with-docs asks one consequential question and waits. Research discoverable facts rather than ask the user. Save each answered choice before advancing and distinguish proposals from accepted requirements. Use comparisons/snippets only when useful for the current choice. Update resolved domain terms through domain-modeling without putting implementation detail in the glossary.
- Before adding exploration text, ask whether removing it would change future specification, resolution of an open question, or understanding of a meaningful tradeoff. Omit routine changes, loaded skills, chronology, approval announcements, and cleanup narration. Update the relevant topic rather than append duplicates. Keep detailed research separate and propagate design-relevant findings.
- To-spec preserves exploration and user edits. If generation exposes a consequential error, contradiction, or unknown, stop the affected generation and return to grill-with-docs; correct exploration first and then update the spec. Review scope, existing implementation, dependencies, observable behavior, testability, security/privacy/licensing, and migration/data-loss risks. Draft becomes Ready only after explicit approval.
- To-tickets rejects exploration, chat-only, Draft, incomplete, and blocked sources. Discuss requested merges, splits, deliverables, blockers, and conditions one decision at a time. Breakdown approval permits ticket creation, not execution. Keep meaningful implementation behavior independent of whether storage is local or hosted; remove tracker publication and alternate temporary ticket trees.
- Preserve the original ticket sections: Parent, What to build, Acceptance criteria, and Blocked by. Parent references the owning local spec. Retain the original local template's status field with the agreed lifecycle states. Start acceptance boxes unchecked and check them only against observed evidence. Do not generate custom Objective, Scope, Deliverable, Execution checklist, Dependency impact, Evidence to record, or Completion handoff sections. Record actual progress and evidence in the ticket during execution rather than require a second checklist or prefab reporting instructions.
- Assigned ticket numbers are permanent identifiers, not scheduling order. Never delete, reuse, or renumber them. New work gets new identifiers. Retain invalidated work as Unnecessary with reason/evidence; do not report it as implemented. Pending, in-progress, blocked, Done, and Unnecessary work remain distinguishable. No separate execution task ledger is required.
- Blockers and execution conditions are distinct. Begin only when required inputs exist, blockers are satisfied, and the condition permits work. False conditions produce evidenced Unnecessary records; unresolved conditions do not permit execution. When a prerequisite becomes Unnecessary, reassess each dependent: proceed if inputs/conditions allow it, mark Unnecessary if its condition is false, or retain Blocked if an input is missing. Decision changes return through exploration before changing the spec and tickets.
- Conclusive research answers are Done, including negative findings. Inconclusive research remains unresolved. A negative answer is not permission to implement the rejected approach or proof that a required dependent input exists. Keep sources, methods, findings, ambiguity, failed approaches, and decision impact in research records and propagate relevant outcomes.
- Implement in the current checkout by default. Independent non-conflicting work may run in parallel; conflicting edits/resources require sequencing or explicitly authorized isolation. Preserve pre-code plan review and post-verification review, resolve correctness blockers, and record relevant risks and exact resume points. Commits, branch changes, worktrees, and activation/deployment each require explicit authorization.
- A spec completes only when every ticket is Done or Unnecessary with records and every whole-spec acceptance criterion passes. An epic completes only when every required linked spec is completed and combined outcomes, including interactions, are verified. Retain and explain a linked spec made unnecessary without waiving an unmet epic outcome.
- Complete moves the whole workspace, preserves exploration/research/tickets, and repairs incoming/outgoing references, spec/ticket links, epic backlogs and parent links, research links, and current-documentation backlinks. Record delivered behavior, combined verification, approved deviations/remaining gaps, and current-topic links concisely. Never file partial or disproven outcomes as completed.
- Review added, changed, and removed impacts on behavior, architecture/tooling, persistence, user workflows, and developer operations. Current documentation describes verified implementation, replaces obsolete claims, and excludes planned/rejected/Unnecessary work. Create topic documents only for substantive content. An explicit no-change disposition is enough when no substantive current-documentation impact exists. Epic completion reviews the combined outcome without copying child updates.
- Archive rejected, abandoned, or superseded work with disposition, reason, and replacement link when relevant, repairing affected references. Paused/blocked work stays active while pursued. An Unnecessary ticket stays with its spec and does not itself archive the spec.
- Populate shared, Python, React, combined Nix/NixOS, and existing layout standards with actual coding/review guidance, not merely tool lists. Shared rules apply to all work; profile rules apply to affected technologies. Default agent guidance describes actual contents and routes applicable standards, including layout guidance for organization changes. Confirm applicability from manifests/source, update pointers when technologies change, and leave versions/commands in configuration rather than copy them into guidance.
- Forks may replace prescribed tools through configuration and a concise reason/replacement in agent guidance, preserving relevant checks and consistent workflow instructions. Use domain-modeling's ADR format and create a record only when the choice is hard to reverse, surprising without context, and a real tradeoff. Do not manufacture ADRs or duplicate their selection/format rules across skills. Glossary entries remain concise domain definitions.
- Use a tooling-only uv Python baseline with development dependencies for Ruff, strict mypy, pytest, pre-commit, and coverage support. No runtime dependencies, starter package, build backend, or installation of this repository as a package. Select one supported Python minor through compatibility checks; align interpreter selection, shell, Ruff target, and mypy. Allow patches and deliberately review minor upgrades. Fork libraries declare/verify their own supported interpreter range.
- Ruff handles all Python linting, import sorting, and formatting with ALL enabled. Keep preview and unsafe fixes disabled, apply safe lint fixes before formatting, configure documented formatter-incompatible exclusions, and review new rules on upgrades. Permit S101 only in the test area for pytest assertions; other rules remain. Strict mypy must see project dependencies/stubs and use individual error-code-specific, explained untyped-import exceptions rather than blanket missing-import suppression.
- Use Google-style docstrings describing arguments, meaningful returns, relevant caller-facing exceptions, constraints, and side effects. Annotations do not replace descriptions and linting cannot prove factual accuracy. Pytest is the default and remains outside commit-time hooks.
- Use npm and a tooling-only React baseline with React/types, TypeScript, type-aware ESLint plus Hook/accessibility rules, Prettier, Vitest, React Testing Library, DOM-test configuration, and coverage support. Choose one supported Node LTS major through compatibility verification; align project/hooks/shell, allow patches/minors, and deliberately review major upgrades. Provide lint, lint:fix, format, format:check, typecheck, and one-shot test scripts.
- Enable TypeScript strict and noUncheckedIndexedAccess. Handle missing indexed values explicitly rather than routinely assert non-null values. Require configured project-wide type checking before frontend code/tooling tickets are Done, outside staged hooks. Passing filenames to the compiler must not bypass project configuration. Keep React framework-neutral, use built-in state tools where justified, and treat server-data caching separately. No framework-specific dev/build scripts or global state library is prescribed.
- ESLint handles code rules and Prettier formatting. Place eslint-config-prettier after other flat configs, keep canonical plugin names, and check relevant overrides with its compatibility helper. Run Prettier separately rather than through eslint-plugin-prettier. Apply ESLint rule-provided fixes, report remaining violations, review the diff, and prove stability. Hook order alone cannot fix incompatible rules.
- Use a reviewed remote ESLint hook and prove intended JavaScript/TypeScript inputs, plugins, flat configuration, type-aware checks, and project dependency resolution. Isolated environments do not inherit project npm packages automatically. Do not silently replace it with a local hook, omit plugins, or weaken type-aware checking if integration fails; record evidence and return to exploration before changing policy.
- Use ESLint 9 temporarily with an explicit end-of-life exception because the official accessibility plugin does not declare compatibility with maintained ESLint 10. Preserve type-aware, Hook, and accessibility checks without peer overrides. Record the exception in configuration/guidance and reassess it during dependency updates; migrate to maintained ESLint when a reviewed integration preserves the contract.
- Use the plugin-free rbubley/mirrors-prettier baseline at reviewed revision 331f33fa4dfbcbca7c3da3620c137fde0faab273, corresponding to Prettier 3.9.10. Align project/hook formatter versions and review updates. Do not use the archived original mirror. Additional plugins require separate resolution and trust review; plugin-only hook installation did not resolve project-relative configuration in the existing experiment.
- Prefer suitable remote hooks; local hooks remain an option only within agreed policy. Hook environments are not sandboxes. Executable configuration, plugins, dependencies, and install scripts are trust boundaries. Git pins and registry metadata do not independently establish safety or absence of compromise. Review version changes and do not overstate the inspected evidence.
- Use stable, locked flakes and an optional shell supplying Python/uv, Node/npm, pre-commit, Alejandra, Statix, and deadnix. Keep uv/npm responsible for project dependencies. Document and prove system-wide and shell-provided entry without hidden shell-only setup. Select a supported stable Nixpkgs release during compatibility checks; a justified unstable override follows the normal override policy. No host configuration is needed merely for a shell.
- Alejandra is the sole Nix formatter. Statix/deadnix are check-only and do not automatically rewrite structure or remove bindings. Document narrow limitations such as argument forwarding. Run declared flake checks for relevant Nix changes outside commit-time hooks and report actual outputs/platform coverage. Forks managing hosts additionally build affected system outputs without activation. Builds do not establish service runtime correctness; activation, boot changes, and remote deployment require authorization.
- Keep Python, frontend, and flake lockfiles in version control, including development dependencies. Update them deliberately, review dependency changes, and keep project/hook versions aligned. Generating locks does not authorize commits.
- Commit-time hooks receive applicable staged files. Include Ruff fix/format, strict mypy, remote ESLint fixes, approved remote Prettier, Alejandra, and check-only Statix/deadnix. Mypy receives supplied filenames as explicit targets, not a whole-project substitute or disabled filename passing; following needed imports does not promise zero unstaged dependency analysis. All-files checks must cover intended source and stubs.
- Apply unslop and writing-for-agents to affected prose and instruction structure. Use no em dashes, transcript filler, duplicate policy authority, or skill-loading narration. Preserve behavioral requirements during wording cleanup.

## Testing Decisions

Use the highest observable seams already present: the planning workflows' real document/state transitions and the configured development tools' actual command/hook entry points. No application test seam or product framework is introduced merely to verify this template.

Good tests verify external outcomes, errors, boundaries, invariants, transitions, and regressions. Do not test Markdown wording, configuration copies, forwarding mocks, or bare execution without meaningful assertions. Use actual workflow exercises and observed command output. Permanent regression tests are appropriate for consumer-visible executable behavior; disposable fixtures prove the tooling-only baseline and are removed afterward.

The workflow owners, runtime/profile configuration, hook integration, completion/reference repair, and current-documentation updates are the surfaces to verify. Prior art consists of the existing local Prettier hook experiment, which formatted representative frontend/document files and passed a second run. It also established a plugin-resolution failure, not blanket plugin support. There is no existing application suite or NixOS host to claim as tested.

Every implementation ticket runs pre-commit across all applicable tracked files in addition to acceptance verification. Review modifications and rerun until stable and passing. Required checks must pass; exceptions are narrow and explained, not global disabling to obtain a passing result.

Require at least 80% line coverage separately for Python and React application profiles, with branch reporting and explained exclusions. Measure application source, including unexecuted applicable code, not tests or generated code. Meeting the floor does not replace behavior/acceptance assertions. A tooling-only profile with no application source has no application coverage to measure; report applicability honestly and do not add dummy tests or source to manufacture a passing result.

Whole-spec acceptance requires these observed outcomes:

| Surface                  | Required external proof                                                                                                                                                                             |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Local planning           | Exploration and spec generation work without hosted remotes or tracker credentials; no tracker is called.                                                                                           |
| Exploration              | Resume without prior chat, ask one question, persist its answer, and distinguish it from a proposal. Omit irrelevant routine-action/loaded-skill narration.                                         |
| Specification            | Preserve exploration, route unresolved decisions back for correction, and withhold Ready without explicit approval.                                                                                 |
| Ticket generation        | Reject non-Ready/exploration inputs; discuss grouping and create files only after approval. Preserve the original section structure and acceptance boxes.                                           |
| Graph execution          | Exercise independent work, blocker edges, false and unresolved conditions, negative research, and per-dependent reassessment after Unnecessary work. Preserve IDs and records.                      |
| Completion               | Refuse a ticket-closed spec with unmet acceptance. Move verified fixture folders intact and repair references. Refuse epic completion until combined outcomes pass.                                 |
| Current behavior/archive | Update affected current topics and replace stale claims. Archive with reason/replacement links, without claiming success; pursued blocked work stays active.                                        |
| Skill cutover            | Roles have one owner, old definitions/callers/metadata are migrated, invocations are reachable, and no automatic Git action or alternate tracker workflow remains.                                  |
| Standards routing        | Reach shared and applicable profile rules; a single-profile fork does not require unused tooling and an explained override preserves checks.                                                        |
| Python tools             | uv installs tools without packaging the template. Ruff fixes/formats stably; strict mypy rejects a genuine type error, sees dependencies, and preserves staged targets.                             |
| Frontend tools           | Locked npm installation and actual scripts/hooks load intended configuration, reject type/Hook/accessibility violations, apply fixes, and remain stable with Prettier. Ignored files are not proof. |
| Tests/coverage           | Meaningful Python and rendered React fixtures run with the configured runners. Independent line floors pass/fail appropriately, branch reports exist, and exclusions do not hide meaningful source. |
| Nix/environment          | Actual shell entry, declared flake checks, and representative formatter/linter inputs succeed on the recorded platform; system-wide entry works and no activation occurs.                           |
| Documentation            | Rewritten prose has no em dashes or competing authority; glossary entries are definitions, ADRs meet all three criteria, and safety claims match evidence.                                          |

Record actual results against the relevant ticket acceptance items as execution proceeds. Keep research detail in research records, not duplicated transcripts. Report runtime/platform limits rather than claim all systems or outputs were tested.

## Out of Scope

- GitHub issues/PRs, tracker setup, publishing, or a hosted-repository requirement.
- A Python starter package, application runtime dependencies, React application, rendering framework, routing, or deployment architecture.
- Mandatory external React state-management libraries or a fabricated browser application for tests.
- CI pipelines, a NixOS host scaffold, or system activation/deployment.
- Automatic commits, branch changes, or worktrees.
- Unrelated IDE configuration or supporting-skill redesign.
- Placeholder planning documents, permanent disposable fixtures, dummy tests, duplicate execution ledgers, or a new spec/ticket template.

## Further Notes

The existing shared/Python/CI standards are empty; the layout standard already records the accepted organization. Root agent guidance has initial routing, while repository guidance still describes legacy planning and nested specs. The glossary has introductory text without defined terms. The five documented skills coexist with copied tracker-oriented workflows. No Python/frontend manifests, hook configuration, or flake have been implemented.

The [Prettier assessment](research/prettier-remote-hook.md) contains limited source review and runtime evidence. Remote ESLint integration still needs proof in the intended frontend layout. The [package-manager comparison](research/frontend-package-manager.md) provides alternatives; npm is the accepted default.

Select concrete supported Python, Node, and stable Nixpkgs versions, package pins, other hook revisions, and provisioning through compatibility verification. These are constrained implementation choices, not permission to silently reopen defaults. Remote ESLint and mypy dependency visibility must be proven. If an integration cannot meet the contract, return to exploration before changing policy; do not report partial coverage as complete.

Completion must account for incoming and outgoing references, not only the parent backlog. Do not invent migrations from legacy directories where no content exists. Historical exploration descriptions are not operational callers and must not be mechanically rewritten as target instructions.

The approved ticket identities and dependency graph remain:

| Ticket                                                                               | Blockers   |
| ------------------------------------------------------------------------------------ | ---------- |
| [01: Tooling compatibility](tickets/01-tooling-compatibility.md)                     | None       |
| [02: Working tooling baseline](tickets/02-tooling-baseline.md)                       | 01         |
| [03: Planning workflows](tickets/03-planning-workflows.md)                           | 02         |
| [04: Execution and lifecycle workflows](tickets/04-execution-lifecycle-workflows.md) | 03         |
| [05: Coding standards](tickets/05-coding-standards.md)                               | 02         |
| [06: Repository guidance and cutover](tickets/06-repository-cutover.md)              | 03, 04, 05 |
| [07: Whole-spec verification](tickets/07-whole-spec-verification.md)                 | 06         |

Ticket 01 is first. Its conclusive negative result may be Done research but cannot supply a missing compatible input to required downstream work. Initial tooling and hooks stay together in 02 so the required all-files verification exists before later implementation tickets need it. After 02, 03 and 05 can proceed in parallel without conflicting edits. Complete the real spec only after 07 and every other ticket are Done or Unnecessary and whole-spec acceptance passes.
