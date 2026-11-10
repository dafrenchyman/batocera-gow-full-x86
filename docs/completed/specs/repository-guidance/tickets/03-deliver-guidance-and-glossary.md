# 03: Deliver fresh-session guidance and domain vocabulary

**Status:** Done

## Parent

[Repository guidance and documentation](../spec.md)

## What to build

Create compact project-specific root `AGENTS.md` and `GLOSSARY.md` so a fresh session can discover actual project scope, protected boundaries, applicable standards, current facts and existing workflow owners without prior chat, local handoff or an external ProjectTemplate checkout.

Required inputs are the Ready specification and [saved exploration](../explore.md), the reconciled standards/current tooling facts from ticket 01, and the final migrated destinations/current records from ticket 02. Both input sets must actually exist and satisfy their contracts before this ticket becomes eligible; a prerequisite's terminal label alone is insufficient. Review actual source/domain usage and the applicable writing-for-agents, skill-mechanics, unslop and domain-modeling guidance before creating their respective documents. Reuse local conventions without importing template-only vocabulary or adding a new workflow family, host adapter or redundant guide.

Root guidance must describe complete official x86 Batocera packaging with additive Wolf/GoW startup and input integration. Preserve stock Batocera/Wolf/GoW sources, mappings/configgen, complete payload/metadata, the original Batocera checkout, operator content and unrelated services. Require explicit authorization and proven ownership for remote actions, with no destructive global cleanup. Preserve registry/app/runner/home identities and link current operational records for exact values instead of duplicating them in policy.

Route every change to shared standards and conditionally to layout, Python, Nix and DI standards. Route terminology to the glossary and agent-instruction work to writing-for-agents. Link actual current topics, owning planning records and existing workflow owners/shared lifecycle and interview references through host-supported discovery or direct skill-file loading. Preserve distinct permissions for spec approval, ticket creation, implementation, Git operations, publication, deployment and interruption. Do not require the handoff, claim future source/tool configuration exists, or duplicate workflow rules.

Use one concise root glossary for domain definitions, not paths, hashes, recipes, tool policy or lifecycle states. Preserve all specified distinctions: official stock payload versus additive integration; physical Guide button versus emulator menu action; client/physical input versus session-owned synthetic gamepad, stock shortcut processing and consumer-visible output; configured Wolf app/runner identity versus native session/lobby/container lifetime; persistent production userdata versus independently owned disposable test state; Docker image ID versus registry manifest digest, movable tag and source revision/content fingerprint; server-side input/render evidence versus physical-controller forwarding, client-decoded video and heard client audio. A configured Guide combination does not promise a menu in every emulator.

Promote durable sanitized handoff constraints into concise guidance, definitions into the glossary, and any remaining useful current/history facts into their proper existing owners. Do not copy the handoff snapshot, publish personal connection metadata or create an ADR for routine documentation adaptation. Preserve existing ADR identity and ownership.

Verify the integrated discovery outcome from both root `AGENTS.md` and `.agents/AGENTS.md` through actual local standards, glossary, current topics and workflow owners, including heading links. Review claim accuracy against the reconciled source/records and all parent acceptance outcomes. This check does not waive tickets 01 and 02's own acceptance evidence. Use local navigation/claim review and available documentation-format checks, not application tests, Wolf contact, new tool installation or permanent Markdown wording/source-text tests. Use the current checkout.

Owner: omp coding assistant. The user's implement invocation authorizes this ticket in the current checkout. Eligibility is satisfied: the specification is Ready; ticket 01 supplies all five reconciled standards and truthful tooling inventory; ticket 02 supplies the current application topic, workflow topic and complete six-file historical workspace. The obsolete planning tree is absent. `git check-ignore -v handoff.md` selects `.gitignore:9:/handoff.md`; `git ls-files -- handoff.md` returns no tracked entry. No index operation is required.

Pre-code review selected one documentation tranche: create the root scope/router and domain glossary, then exercise discovery from both entry points, review claims against source and prerequisite records, and run explicit Markdown formatting plus the all-files gate. Existing standards, current topics and workflow skills retain policy ownership. No executable behavior changes, so application tests and TDD are inapplicable; local file/heading navigation and domain/claim review are the approved observable seams. No shared edit is in flight. Prior ticket-only hook exceptions do not waive this ticket's gate.

Delivered `AGENTS.md` and `GLOSSARY.md`. Root guidance owns compact project boundaries and conditional routing; `.agents/AGENTS.md` now reaches the actual root guide without needing another edit. The glossary distinguishes stock/additive integration, Guide/menu, all input observation points, configured application/runner versus session/lobby/container, production/test state, artifact identities and server/client evidence. Existing current/history owners retain sanitized fixed-checkout, native-user, home-selection and prior-evidence constraints. No operational identity, application source, private configuration, handoff, workflow family or ADR changed.

Observed on x64 Linux: an in-memory local discovery smoke traversed both entry points, reaching 79 Markdown documents and inspecting 422 local references. All 419 concrete file/heading references resolved. The remaining three are intentional generated-document examples in the existing ticket/spec templates, resolved relative to future generated documents rather than their template source directory. All five standards, glossary, three current topics, owning guidance spec/parent epic and workflow/lifecycle/interview owners were reached. Claim/domain review compared the Ready contract and prerequisite records with README and source usage in publication, common identity constants, runtime transport and native probes. No naming conflict or documentation-contract defect remained.

Explicit `prettier --check AGENTS.md GLOSSARY.md .agents/AGENTS.md docs/active/specs/repository-guidance/tickets/03-deliver-guidance-and-glossary.md` passed. This explicit check covers the new files that Git-selected hooks may omit. `pre-commit run --all-files` exited 1: Ruff reported 53 errors; strict mypy reported 1,584 errors in 29 files; Statix reported four W04 warnings. Ruff format, Prettier, Alejandra and deadnix passed; ESLint had no matching files. Before/after content fingerprints found no hook mutations to the inventoried application, documentation, skill or hook files.

Direct post-implementation correctness, security, maintainability, domain and spec review found all six original documentation acceptance outcomes satisfied. Exact identities stay with operational owners; no personal connection metadata or private snapshot was promoted. No permanent wording tests, temporary files, application suite, TypeScript project check, Nix build/flake check, runtime execution, tool installation or Wolf contact was introduced. Application/TypeScript/Nix execution is inapplicable to this documentation-only change. Existing prerequisite acceptance is retained, not newly claimed or rerun.

The repository owner explicitly approved a ticket-03-only exception to the passing all-files gate after reviewing the observed failures and passing documentation checks. The recorded Ruff, mypy and Statix failures remain assigned to separately authorized modernization; this exception does not change hooks or claim application compliance. All six original documentation acceptance outcomes are observed, final review found no documentation blocker, and no work remains in this ticket. Whole-spec verification, completion and folder moves remain with implement-spec, not this ticket.

## Acceptance criteria

- [x] Root `AGENTS.md` states the actual project scope, stock/additive and ownership boundaries, protected upstream/operator resources and distinct authorization gates without duplicating operational identities or workflow rules.
- [x] Root and `.agents/AGENTS.md` discovery reach applicable shared/layout/Python/Nix/DI standards, glossary, truthful current topics, owning planning records and existing workflow owners through actual local file/heading references.
- [x] A fresh session needs neither local `handoff.md`, prior chat, generated private artifacts nor an external template checkout; guidance makes no false claims about future source layout, installed tools or measured compliance.
- [x] Root `GLOSSARY.md` preserves every required stock/input/Guide/menu/session/userdata/artifact/evidence distinction using concise source-grounded domain definitions, without recipes, hashes, path inventories or copied lifecycle policy.
- [x] Durable sanitized handoff knowledge is retained in the correct guidance, glossary, current or historical owner without publishing its full snapshot or personal connection metadata; no redundant guide, workflow family or routine-adaptation ADR was introduced.
- [x] Integrated navigation and claim review covers the Ready specification's discovery and vocabulary outcomes alongside the prerequisite artifacts. File/heading-link and available formatting checks have recorded results and actual limits, without application/runtime verification or permanent wording tests.

## Blocked by

- [01: Reconcile applicable standards and tooling facts](01-reconcile-standards-and-tooling.md). Requires the final reconciled policy and truthful tooling topic, not just a terminal status.
- [02: Consolidate legacy documentation and preserve the local handoff](02-consolidate-documentation-and-handoff.md). Requires migrated current/history destinations, repaired references and completed handoff disposition, not just a terminal status.

Reassess each required input before changing this ticket to Pending. Approval of these ticket files does not authorize implementation.
