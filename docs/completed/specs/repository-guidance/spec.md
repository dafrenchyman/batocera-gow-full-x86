# Repository guidance and documentation

Status: Completed
Parent epic: [Repository maturation](../../../completed/epics/repository-maturation/epic.md)
Decision record: [explore.md](explore.md)
Delivery: [completion.md](completion.md). The contract below preserves the original approved scope; later modernization supplies application compliance separately.

## Problem Statement

A fresh development session cannot find reliable project guidance. The existing `.agents/AGENTS.md` points to an absent root guide; the copied standards/current topics describe parts of ProjectTemplate that this application does not have. Actual application evidence and its original active workspace still live under `planning/`, while newer records live under `docs/`.

This split can cause an agent to invent tooling, mistake template checks for application verification, change protected upstream/state boundaries, or treat dated completion prose as current acceptance. The local handoff contains useful constraints but also dated image identities and personal connection metadata; a clean clone must not depend on it.

## Solution

Establish project-specific root `AGENTS.md` and `GLOSSARY.md`, applicable standards and truthful current documentation. Make `docs/` the sole planning/current-documentation root without losing legacy evidence or fabricating completion.

A fresh session follows root guidance to the relevant standards, domain vocabulary, current application/tooling facts and existing workflow owners. It can distinguish stock Batocera from project additions, policy from configured tools, recorded runs from new verification, and planning approval from execution permission.

The documentation cutover preserves README's runtime/input/build flows and operational app configuration, repairs the registry-digest explanation and uses neutral operator examples. The operator keeps the local `handoff.md`, excluded from normal Git inclusion; its durable constraints go into the appropriate committed knowledge owners rather than publishing the snapshot.

## User Stories

1. As an automated coding agent, I want concise project scope, protected boundaries and conditional standards/workflow routing so that I can work without previous chat history.
2. As a maintainer, I want one domain glossary distinguishing Guide input, stock actions, session ownership and artifact identities so that instructions and evidence are unambiguous.
3. As a contributor, I want standards applicable to this Python/Nix packaging application rather than inactive frontend or host-management profiles so that I know which rules apply.
4. As an operator, I want current build/runtime facts and historical evidence clearly separated so that I do not deploy an old image or mistake unverified behavior for acceptance.
5. As a maintainer, I want intact legacy records under `docs/` and working navigation so that consolidation preserves chronology and pending acceptance.
6. As the repository owner, I want useful handoff knowledge retained without publishing personal connection metadata or requiring my local handoff in a clean clone.

## Implementation Decisions

### Ownership and existing material

| Material                                                                                                                | Existing behavior or gap                                                                                                    | Reuse or change                                                                                             |
| ----------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `.agents/AGENTS.md` and `.agents/skills/`                                                                               | Agent entry point and lifecycle/interview/workflow owners exist; root guide is absent                                       | Satisfy existing discovery with root guidance, not a second workflow family                                 |
| ProjectTemplate root guide/glossary                                                                                     | Short conditional routing and glossary conventions exist outside this repo                                                  | Adapt their structure, not their tooling-only application claims or template-only vocabulary                |
| `docs/standards/{general,repo-layout,dependency-injection,python,nix-nixos,react}.md`                                   | Copied policy includes inactive frontend sections, host-management instructions and an overly broad DI-library prescription | Reconcile applicability while preserving accepted Python/DI principles                                      |
| [Planning workflow](../../../current/planning-workflow.md) and [ADR 0001](../../../adr/0001-local-planning-contract.md) | Existing workflow routing and local-document decision                                                                       | Preserve ownership and ADR identity; attribute template exercises rather than claiming new application runs |
| [README](../../../../README.md)                                                                                         | Build commands, deployed TOML and runtime/input/build diagrams exist                                                        | Preserve real operational contracts; fix current claims/navigation without changing deployment              |
| [Copied tooling topic](../../../current/tooling.md)                                                                     | References absent configuration and template verification                                                                   | Describe actual configuration and limits; planned tooling is not installed tooling                          |
| [Application record](../../../current/app.md) and [original workspace](../gow-full-x86/spec.md)                         | Actual application evidence was inventoried in the legacy root                                                              | Migrate intact and repair references; do not infer completion from the older `completion.md`                |
| Local `handoff.md`                                                                                                      | Useful invariants mixed with dated/private operator metadata                                                                | Keep local; promote only durable, sanitized knowledge to its proper owner                                   |

The [baseline research](../../../completed/epics/repository-maturation/research/repository-baseline.md) establishes these observations, not compliance or current server health. The local template is reference material for implementation, not a required clean-clone dependency.

### Root guidance contract

Keep root `AGENTS.md` a compact scope/routing document:

- State the purpose: complete official x86 Batocera packaging with additive Wolf/GoW startup and input integration.
- Preserve unchanged Batocera/Wolf/GoW sources, stock mappings/configgen, complete stock payload/metadata, the original Batocera checkout, operator content and unrelated services. Remote actions must be authorized and restricted to proven owned resources; no destructive global cleanup.
- Preserve current registry/app/runner/home identities and point to current operational records for exact values instead of copying those values into multiple policy documents.
- Route every change to shared standards and conditionally to repository layout, Python, Nix and DI standards. Route terminology to the glossary and agent-instruction changes to writing-for-agents.
- Link the existing workflow owners and shared lifecycle/interview references. Spec approval, ticket generation, implementation, Git operations, publishing, deployment and service interruption remain distinct permissions.
- Link actual `docs/current/` topics and owning planning records. Do not require the local handoff or claim future `src`/tool configuration exists before its cutover.

Use host-supported skill discovery or direct skill-file loading. Do not invent new agent-host adapters or duplicate the shared workflow rules. Follow [writing-for-agents](../../../../.agents/skills/writing-for-agents/SKILL.md) when creating guidance.

### Glossary contract

Use one root glossary following [domain-modeling](../../../../.agents/skills/domain-modeling/SKILL.md). Define domain concepts, not recipes, paths, hashes or tool policy. Preserve these distinctions:

- Official stock payload versus additive project integration.
- Controller **Guide** button versus an emulator **menu** action; a configured Guide combination does not imply every emulator has a menu.
- Client/physical input, session-owned synthetic gamepad, stock shortcut processing and consumer-visible output as different observation points.
- Configured Wolf application/runner identity versus an individual native session/lobby/container lifetime.
- Persistent production userdata versus independently owned disposable test userdata.
- Docker image ID, registry manifest digest, movable tag and source revision/content fingerprint.
- Server-side input/render evidence versus physical-controller forwarding, client-decoded video and heard client audio.

Resolve genuine naming conflicts against existing source/records before recording definitions. Keep lifecycle states and approval rules owned by their existing shared reference. Do not copy ProjectTemplate's vocabulary wholesale or create an ADR merely for routine documentation/tool adaptation.

### Applicable standards and truthful state

Retain shared, repository-layout, DI and Python guidance. Remove `docs/standards/react.md` and inactive React/npm/ESLint/Vitest routing and instructions from retained active guidance. Repair references, including historical references where removal would leave a broken live link; retain their attributed historical meaning.

Retain a trimmed Nix profile for actual Nix expressions, pinned runtime closure and applicable optional development environments. Remove unused NixOS host-management instructions and absent-root-flake claims. No flake or host configuration is required just to match copied prose. The existing `bridge.nix` runtime closure is not replaced by a developer shell.

Document these accepted policies without claiming existing compliance:

- Explicit configured-dependency injection and deterministic resource ownership in every environment. `dependency-injector` may be used outside Batocera, but is excluded from final-runtime staging/imports. Existing stock third-party libraries remain valid; the stdlib-only ephemeral SSH helper has its own delivery boundary.
- Typed Python boundaries, meaningful Google-style docstrings, Ruff ALL with appropriate documented formatter compatibility, strict mypy, pytest and independent application **line** coverage of at least 80%, with branch reporting rather than a separate branch floor.
- Batocera-led interpreter compatibility: host 3.12.x is allowed, including the user's reported Nix-provided 3.12.12; builder/default full-version pinning follows actual confirmed stock. Pinned source defines 3.12.8; it has not been confirmed by a new runtime execution. uv owns project environments/dependencies, not OS Python.
- Current code remains under `experiments/gow-full-x86/` until the later combined modernization. Its accepted installed-package layout is future policy, not grounds to declare existing source/coverage inapplicable.

`docs/current/` must distinguish implemented behavior, configured tools, historical execution, user-reported observations and pending acceptance. Existing emulator/hotkey success reports remain reports about emulators tried, not all backends/actions. New tests, hook installation, initial secret-baseline review and substantive code compliance belong to the other specs.

### Legacy documentation cutover

Use this migration flow under later implementation authorization:

1. Inventory the whole legacy tree, destinations and incoming/outgoing links/anchors. Refuse collisions; do not overwrite a destination or omit research/assets/history.
2. Migrate `planning/current/app.md` to `docs/current/app.md`, preserving image identities, actual observations, user reports, accepted risks and limits. Reconcile copied tooling/workflow topics against actual capabilities and attributed template provenance.
3. The user clarifies that the original work under `planning/` is finished. Move the complete `gow-full-x86` workspace to `docs/completed/specs/gow-full-x86/` during the authorized documentation cutover. Preserve its legacy `tasks.md`, research and completion snapshot as historical records, with the latest operator completion clarification distinguished from older pending-status notes. Do not reopen old QA, invent new numbered-ticket evidence or claim that completion means every emulator/shortcut was tested.
4. Preserve existing completed transport/template records and ADR numbering. Repair README, current topics, owning specs/research and agent navigation together, including newly generated sibling-spec references that point into `planning/`.
5. Remove the obsolete `planning/` tree only when all records and live references have migrated. No permanent alias pages, duplicate current authorities or accidental compatibility routers.
6. Sanitize personal SSH targets/key filenames in maintained documentation and promoted material without reading keys, rewriting Git history or claiming a credential scan. Preserve nonsecret historical meaning.

Retire internal experiment wording from the maintained project description where appropriate, but keep real deployed identifiers, including `ghcr.io/dafrenchyman/batocera-gow-full-experiment` and `WolfExperimental`. Fix README's statement calling the digest-pinned registry reference a local image ID; these identities are not interchangeable. Source-sensitive commands/diagrams receive later updates from modernization when their actual paths change, not speculative edits in this cutover.

### Local handoff and privacy

Keep `handoff.md` at the repository root locally and untracked; do not delete it or move it into committed documentation. This is the required end state, not a claim that Git already excludes it. An ignore entry does not untrack a tracked file: determine actual status during authorized implementation and obtain explicit Git authorization for any index change, preserving the local file and history.

Promote concise invariants/permissions/routing into root guidance, definitions into the glossary, current facts into `docs/current/`, and useful sanitized historical evidence into its owning records. Do not publish the full handoff snapshot or link committed navigation to it. Keep existing real `.env` contents private and undisturbed; no automatic dotenv loader, key copying or private evidence publication belongs to this scope.

## Testing Decisions

Documentation acceptance is local; runtime execution would not prove navigation or claim accuracy and is not required here.

| Acceptance outcome                                                              | Verification seam                                                                                                                                                                                                                        |
| ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Fresh-session discovery works without the handoff or external template checkout | Follow root and `.agents/AGENTS.md` routes through actual local standards, glossary, current topics and workflow owners                                                                                                                  |
| Guidance matches actual applicability and accepted exceptions                   | Review source/config inventory against active routing; no frontend/host-management/runtime-DI-library prescription or false installed-tool claims                                                                                        |
| Vocabulary preserves the specified distinctions                                 | Review glossary against domain usage and the observable Guide/menu, ownership and identity examples                                                                                                                                      |
| Legacy material migrates intact without overstating verification                | Compare pre-move inventory with destinations and retained chronology/assets; completed placement reflects the latest operator completion report, while individual historical checks retain their original limits; no collision overwrite |
| Live navigation resolves after consolidation                                    | Check local file/heading references across changed and incoming documents; no links to removed `planning/` paths or the local handoff                                                                                                    |
| README and current facts remain accurate                                        | Compare documented commands/TOML/diagrams and identity meanings with maintained source and existing recorded evidence; label limits rather than rerun historical reports                                                                 |
| Private local handoff survives without becoming a clone dependency              | Verify local preservation, appropriate Git exclusion under granted permissions and promoted durable constraints; no private metadata in maintained examples                                                                              |

Use available documentation-format/link checks within execution scope. Do not install tools, run application tests or contact Wolf solely to validate this documentation. No permanent tests of Markdown wording/source text or new application unit tests: this spec changes documentation contracts, not executable logic. Tool output from later implementation belongs in its tickets, not as a new historical claim in this specification.

## Out of Scope

- Application refactoring, source relocation, packaging/tool/hook installation, secret scanning/baseline creation or establishing measured code compliance.
- Implementing the native coordinator, qualifying/running ROMs, BIOS acquisition or mandatory client/manual QA.
- Batocera/Wolf/GoW changes, per-emulator mappings, overlays, deployment, service interruption or identity/userdata migration.
- Git initialization/history rewriting, commits/publication or treating Ready approval as permission for index mutation.
- Publishing/deleting the full local handoff, creating redundant agent guides or selecting a new repository-wide license.

## Further Notes

[Wolf integration](../wolf-integration/spec.md) owns the reproducible remote test suite, fixture qualification, automated evidence and testing README. [Repository modernization](../repository-modernization/spec.md) owns executable tooling/secret prevention and the combined source-layout/full-standards cutover after the native baseline. These are linked Drafts, not prerequisites for creating truthful root documentation.

The latest operator clarification treats the legacy effort as finished for consolidation. Preserve older status/evidence records without reopening old QA or claiming broader emulator coverage. Guidance remains usable when personal local files and old generated artifacts are absent. No consequential documentation-policy question remains. The user explicitly approved this specification as Ready; ticket breakdown approval and execution authorization remain separate.
