# Explore: repository guidance and documentation

Parent epic: [repository maturation](../../../completed/epics/repository-maturation/epic.md). This exploration preserves the accepted first detailed-planning scope; [spec.md](spec.md) and [delivery](completion.md) record its completed disposition.

## Current Direction

### Goal and boundaries

Make this repository understandable to a fresh AI development session without relying on chat history, personal SSH settings or copied template claims. Establish project-specific root guidance and vocabulary, applicable standards, truthful current documentation and one planning root under docs/.

The [user brief](../../../completed/epics/repository-maturation/inputs/user-brief.md) and [shared exploration](../../../completed/epics/repository-maturation/explore.md) own the original intake and cross-scope decisions. This bounded exploration owns guidance content, documentation routing and migration details. Quality/tool installation, native integration implementation and source relocation remain separate epic capabilities.

Only planning artifacts change during this exploration. Do not create root AGENTS.md or GLOSSARY.md, edit standards/current documentation, move legacy records, install hooks, run application scripts, connect to Wolf or change code as a side effect of detailing this scope. The accepted future cleanup includes legacy-document migration, but detailed-planning approval is not general execution approval. Existing prematurely created environment files remain undisturbed.

### Implementation and reuse inventory

[Baseline research](../../../completed/epics/repository-maturation/research/repository-baseline.md) records the broader survey. Read-only inspection for this scope establishes:

| Evidence                                                                                                         | What it establishes                                                                                                                                                                                                                                                                          |
| ---------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| .agents/AGENTS.md                                                                                                | Routes to a root guide that is absent and to shared workflow references. Repair that discovery path through the requested root guide rather than invent a second workflow authority.                                                                                                         |
| /path/to/ProjectTemplate/AGENTS.md                                                                               | Reusable short project-scope and conditional standards/skill routing pattern. Its tooling-only project description and React routing do not describe this application.                                                                                                                       |
| /path/to/ProjectTemplate/GLOSSARY.md                                                                             | Reusable concise glossary format; its contents describe template planning vocabulary, not Batocera/Wolf runtime distinctions.                                                                                                                                                                |
| docs/standards/general.md, dependency-injection.md, repo-layout.md, python.md, nix-nixos.md and react.md         | Standards exist but include template-only scope/tooling claims, inactive React sections and a DI library prescription requiring the accepted runtime exception.                                                                                                                              |
| [Current planning workflow](../../../current/planning-workflow.md)                                               | Existing workflow ownership and discovery guidance. Its historical fixture verification belongs to the template and must not be reported as this application's verification.                                                                                                                 |
| [Existing ADR 0001](../../../adr/0001-local-planning-contract.md)                                                | A numbered local-documents planning decision already exists. Preserve its identity and distinguish its template evidence from this repository's adoption.                                                                                                                                    |
| [Copied tooling topic](../../../current/tooling.md)                                                              | Claims root Python/frontend/flake configuration and passing checks absent from this repository; requires reconciliation, not application scaffolding to make the claims true.                                                                                                                |
| [README](../../../../README.md)                                                                                  | Actual build/activation instructions, pinned published image, app TOML and Mermaid runtime/input/build flows exist. The prose following the app TOML incorrectly calls the registry reference a local image ID.                                                                              |
| [Application state](../../../current/app.md)                                                                     | Actual recorded image/native-test evidence and proof limits, including the operator's successful emulator/shortcut report. Originally inventoried under the legacy root; now migrated.                                                                                                       |
| [Original workspace](../gow-full-x86/spec.md) and its [initial completion record](../gow-full-x86/completion.md) | Legacy lifecycle/location claims were inconsistent. The initial completion record predates later runtime evidence and cannot establish final acceptance. Links now follow the consolidated historical workspace.                                                                             |
| Local handoff.md, not intended for commit                                                                        | Dated continuation snapshot with older image identity, personal SSH details and links into planning/. It explicitly says the original spec remains active. Preserve useful nonsecret knowledge in committed guidance/current records without making a clean clone depend on this local file. |

No root AGENTS.md or GLOSSARY.md, installed src package, root Python manifest/lock or root flake was observed. Existing operational code remains under experiments/gow-full-x86. The intended installed src/batocera_gow/{host,builder,runtime} layout is an accepted later migration, not current behavior. The root .env and example.env now exist; application code still uses its hardcoded SSH settings and does not automatically load them.

### Root agent guidance

Use the template's routing pattern, not its application description. The root guide should contain:

- Actual repository purpose: complete official x86 Batocera packaging with additive GoW/Wolf startup and input integration.
- Compact protected boundaries: preserve stock Batocera/Wolf/GoW sources and mappings, the unrelated original checkout and services, deployed registry/app/runner/home identities and operator content. Link detailed operational/current records rather than repeat their values everywhere.
- Conditional pointers: shared standards for changes, layout for file moves, Python for Python/tests/tooling, Nix for Nix expressions/build environments, DI for configuration/service/resource assembly, glossary for domain language, and writing guidance for agent instructions.
- Workflow routing to the existing .agents/skills/ owners and shared lifecycle/interview references. Planning approvals, verification requirements and execution permissions must remain distinguishable.
- Current-state navigation to docs/current/ and the owning active exploration/spec, without selecting historical handoff prose over later evidence.
- Promote durable constraints from the local handoff into this guide: protect the original Batocera checkout and unrelated services/state, preserve the stock-payload/additive integration boundary, require owned and authorized remote actions, and avoid destructive global cleanup. Link the current operational contract for details rather than copy dated image identities, private connection settings or the full snapshot.

Keep one authority for each policy. Exact dependency pins, commands and tool settings belong in their actual configuration when implemented; current guidance must not pretend those configurations already exist. Preserve host-supported discovery and direct skill-file loading. Do not add a new skill family or duplicate guides for hypothetical agent hosts.

### Applicable standards reconciliation

These are inherited decisions, not a new tooling adoption request:

- Retain shared, layout, DI and Python standards. Remove the unused React profile and active React/npm/frontend scaffolding instructions and routing references in the other retained documents.
- Retain Nix guidance scoped to actual Nix expressions, pinned runtime closure inputs and applicable optional development environments. Remove unused NixOS host-management instructions and unsupported root-flake/output claims. bridge.nix already selects Xwayland, xauth, util-linux and Mesa; a development shell must not replace that runtime closure's inputs.
- State explicit configured-dependency injection throughout. Permit dependency-injector outside Batocera, but exclude it and its transitive requirements from the Batocera runtime/final-image staging. Do not turn this into a blanket stdlib-only rule; the remotely delivered SSH helper has its own stdlib-only contract.
- Preserve accepted Python typing/docstring/test policies, including Google-style contracts, Ruff/strict mypy and meaningful application line coverage. Document them as standards and later implementation obligations, not claims that existing code passed.
- Distinguish the current source layout from the accepted later installed package. Do not use absent src files to declare existing application coverage not applicable, or publish commands for absent tooling as current working commands.
- Preserve Batocera-led Python alignment: host 3.12.x, including Nix-provided 3.12.12, is allowed; builder/default full-version pinning and native verification remain stock-aligned. Source defines 3.12.8, pending actual stock runtime-version confirmation. uv owns project environments/dependencies, not the OS interpreter.
- Hook configuration, dependency installation, initial secret-baseline review and actual standards compliance belong to Quality and secret gates. This documentation scope neither installs those tools nor fabricates their verification.

### Glossary scope

Use one root GLOSSARY.md for project-domain language. Keep definitions concise and free of file paths, command recipes, image hashes, implementation details and policy checklists. Existing lifecycle/interview references remain the authority for planning states and permissions.

Vocabulary to distinguish from source and existing records, without importing template-only definitions wholesale:

| Concept cluster                     | Distinctions the glossary must preserve                                                                                                    |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Stock payload and project additions | Official Batocera userspace versus the additive packaging/startup/input integration.                                                       |
| Guide, menu and hotkeys             | Controller Guide button versus an emulator menu action; a configured Guide combination is not a promise that every emulator has a menu.    |
| Input integration                   | Physical/client input, session-owned synthetic gamepad input, stock shortcut processing and final output are different observation points. |
| Wolf application and native session | Configured application/runner identity versus a particular lobby/container lifetime.                                                       |
| Userdata and test ownership         | Persistent production application state versus independently owned disposable test state.                                                  |
| Image identity and source identity  | Docker image ID, registry manifest digest, movable tag and source revision/content fingerprint are not interchangeable.                    |
| Verification evidence               | Server-side rendering/input evidence versus client-decoded video, heard audio and physical-controller forwarding.                          |

This table is coverage for the future glossary, not an approved new glossary or permission to create one during planning. Resolve any genuine naming conflict against source/records before recording a canonical definition. Use the domain-modeling format and avoid per-subpackage glossaries unless actual separate contexts justify them.

### Documentation authority and legacy migration

The epic owns the accepted single-root choice. This scope owns its safe documentation cutover:

1. Make docs/current/ the current-behavior authority. Migrate planning/current/app.md without losing image identities, observed checks, user reports, accepted risks or limitations. Rewrite copied tooling/workflow current topics to distinguish actual project capabilities from attributed template evidence.
2. The user clarifies that the work under planning/ is finished. Treat the original effort as completed history for consolidation rather than reopen its old acceptance questions. Plan to move the complete gow-full-x86 workspace, including research, assets and its legacy tasks.md, to docs/completed/specs/gow-full-x86/ during the authorized documentation cutover. Preserve older pending-status notes as dated records alongside the latest operator completion report. This does not claim every previously untested emulator or shortcut was tested, convert historical ledgers into new execution evidence, or move/change lifecycle state now.
3. Preserve template-derived completed records as attributed provenance where useful. A recorded template test is not a run against this application. Keep the existing ADR identity and repair its references without inventing historical rationale or approval dates.
4. Inventory incoming and outgoing links, anchors and destinations before moves. Refuse destination collisions rather than overwrite. Repair committed README, planning/current, completed-record and agent-navigation references together. Do not make committed navigation depend on local handoff.md; its historical old-path references are not a second current authority. Live committed navigation must resolve to the actual new locations.
5. Remove the obsolete planning/ tree only after its records and live references are migrated. Do not leave permanent alias documents or duplicate current-state authorities.
6. Sanitize personal SSH targets/key filenames in maintained instructions and examples, while preserving the nonsecret meaning of historical evidence. Do not read key contents, rewrite Git history, copy private runtime data or claim redaction is a credential scan.
7. Retire experiment wording from maintained project description where appropriate, but retain real deployed identifiers such as the GHCR repository and WolfExperimental runner. Do not change images, app settings, runtime /opt paths or state merely to match new prose.
8. Preserve README's source-reviewed runtime/input/build diagrams and operational TOML. Repair inaccurate prose and navigation without silently changing their contracts. A documentation edit is not a new build, deployment or native test result.

### Accepted local handoff disposition

Keep the existing handoff.md at the repository root as a local, untracked file. That is the required end state, not a claim that Git already excludes it. Do not delete it, move its full contents into published history or convert it into a committed navigation document. During the authorized documentation cutover, ensure it is excluded from normal Git inclusion; an ignore entry alone does not untrack an already tracked file. Determine actual tracked status at that time and handle any required index change under explicit Git authorization, preserving the local file and without rewriting history. No ignore/index mutation is performed during planning.

Promote important durable project guidance into root AGENTS.md. Preserve one authority per kind of knowledge: concise invariant/permission/routing guidance in AGENTS.md, definitions in GLOSSARY.md, current application/tooling facts in docs/current/, and relevant nonsecret historical evidence in the owning planning records. Root guidance should point to those owners rather than absorb the entire handoff. Remove personal SSH details from material promoted into committed documentation. A clean clone must be fully usable without the local handoff.

### Observable documentation acceptance

- A fresh session starting at root AGENTS.md or .agents/AGENTS.md reaches actual scope, applicable standards, glossary, current facts and workflow owners through existing local paths.
- Active guidance does not prescribe absent frontend tooling, NixOS host management or runtime dependency-injector. Standards do not claim their future checks or source layout are implemented.
- GLOSSARY.md preserves the domain distinctions above without turning into an implementation guide or copying workflow policy.
- docs/current/ distinguishes implementation, configuration, historical execution evidence, user-reported observations and pending acceptance. It does not claim all emulators/shortcuts work or repeat template verification as project proof.
- The legacy workspace and application-state record migrate intact, with lifecycle discrepancies explicitly reconciled, no destination overwrite and no active links left pointing at removed paths.
- Root README operational flows and image identity meanings remain accurate; actual image/app/home identities and protected upstream data stay unchanged.
- Maintained docs/examples contain no personal key filename or private-key material. Generated private local configuration and test evidence remain outside normal Git inclusion.
- Local handoff.md remains available to the operator but is excluded from normal Git inclusion. Committed guidance contains its important durable constraints and links to supporting current/history records, without linking to or requiring the local file.
- Verification uses local link/anchor/claim review and available documentation checks within authorized scope. Do not add permanent source-text tests, install tools, run application suites or contact Wolf just to validate documentation.

## Decisions

Inherited from the [epic exploration](../../../completed/epics/repository-maturation/explore.md):

- Guidance and documentation is the first detailed-planning scope; native regression precedes the combined quality/layout migration.
- docs/ is the sole planning/current-documentation root; preserve evidence and repair references during legacy migration.
- Root AGENTS.md and GLOSSARY.md are requested outcomes. Reuse applicable template conventions, not template-specific application claims.
- Remove inactive React guidance; retain trimmed applicable Nix guidance and the accepted DI/runtime/interpreter boundaries.
- Keep stock upstream projects and operational identities intact. No application changes or runtime/remote operations are authorized by this planning step.
- SSH settings are external operator configuration. Retained test screenshots/results are gitignored local evidence, not mandatory manual acceptance.

The user subsequently requested all necessary child Drafts from the epic and has now explicitly approved [this specification](spec.md) as Ready. No new domain definitions, ADRs, tickets or application implementation were created. Existing ADR 0001 is not renumbered or replaced by a duplicate.

## Options Considered

- Copy the template unchanged: rejected at epic level because its frontend/tooling-only scope, absent configuration and verification claims do not describe this application.
- Retain planning/ as a separate historical authority: rejected in favor of a single docs/ root with preserved history and repaired links.
- Combine documentation planning with application/tool installation or broad source migration: outside this scope and contrary to the planning-only boundary.
- Keep handoff.md local and uncommitted while promoting its durable knowledge: accepted. This preserves the user's existing file without publishing its personal details or letting its dated snapshot become current authority.
- Convert the root handoff into a committed thin router, publish its full dated snapshot, or remove it now: not selected.

## Open Questions

No consequential user choice remains for this bounded documentation scope. The local-handoff disposition is accepted above.

The user's completion clarification resolves the intended legacy disposition. Migration/link checks remain documentation implementation work, not a reason to reopen the completed effort or rerun user-reported observations. Fixture qualification, interpreter setup verification and native permissions remain owned by their other epic capabilities.

## Next Discussion Queue

No documentation-policy decision remains. The three original tickets are Done; [delivery](completion.md) reconciles the whole-spec discovery, migration and vocabulary outcomes. Preserve their historical checks and owner-approved ticket-specific hook exceptions; later modernization supplies application compliance, not retroactive passing hooks for this documentation-only work.

## Assumptions

- Existing workflow skills and their shared references remain the lifecycle authorities; no host-specific discovery rewrite is requested.
- Recorded image/native evidence remains useful provenance even where generated output is unavailable to a clean clone. Unavailable output cannot become a new passing-verification claim.
- The user considers the original planning effort finished. Preserve that completion clarification separately from the scope of historical observations; this cleanup does not add old QA obligations or grant remote/Git permissions.

## Risks

- Duplicated instructions or stale handoff facts can send an agent to the wrong image, source path or permission boundary. Use one current-state authority and strong conditional navigation.
- Deleting inactive guidance without repairing historical/current links can break discovery. Preserve the meaning of historical references without presenting removed files as current targets.
- Lifecycle cleanup can erase chronology or overstate verification. Preserve the operator's completion clarification and older pending-status records without converting them into claims that every emulator/shortcut passed.
- Personal SSH details can appear in historical documentation as well as source. Sanitize published instructions without claiming key rotation, secret scanning or history rewriting occurred.
- Documentation can accidentally promise planned configuration or clone portability that current path guards do not support. Ground current claims in source and label future policy as future.
- This documentation scope adds no runtime dependency, ROM/firmware asset or repository-wide license choice. Existing component obligations and attributed template provenance remain unchanged; do not treat a documentation migration as license clearance.

## Notes

Scope, source evidence, concrete documentation flows, ownership, permissions, privacy and migration/data-loss risks have dispositions. The original Ready approval was followed by separately authorized implementation and all three tickets are Done. [Delivery](completion.md) records whole-spec acceptance without granting new Git, application, build, deployment or remote permission.
