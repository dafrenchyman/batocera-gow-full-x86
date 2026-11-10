# Explore: repository maturation

Parent epic: None. This is the epic-level exploration for [repository maturation](epic.md), not an approved implementation spec.

## Current Direction

### Accepted intake and boundaries

The user wants a maintained, AI-friendly repository instead of an experiment-shaped script collection. They report committing the current changes and copying ProjectTemplate's docs here. [The preserved brief](inputs/user-brief.md) captures each requested outcome.

Required outcomes from the brief:

- Project-specific root AGENTS.md and GLOSSARY.md, informed by `/path/to/ProjectTemplate`.
- Code organization, typing/style and proper docstrings aligned with the applicable copied docs/standards.
- Applicable template pre-commit checks plus Yelp detect-secrets to reduce accidental secret commits.
- A recommendation and deliberate cutover away from experiments/gow-full-x86, potentially to src.
- Maintained real Wolf integration tests that reproduce SSH-driven execution and screenshot evidence.
- A testing README explaining how the remote tests and screenshots work, how to run them and what they prove.

**Delivered scope and authorization:** guidance's three tickets, Wolf integration's seven tickets and modernization's five tickets are Done. Their completed workspaces preserve the accepted observed shortcut-exit contract, actual verification and execution history. The [epic](epic.md) owns the separate combined-outcome gate. Completion supplies no new runtime, deployment or Git permission.

**Sibling delivery boundary for synthesis:** native integration must first establish the regression gate against the existing operational layout, allowing only the necessary maintained test coordinator, diagnostic/fixture additions and test-owned state. The combined modernization then relocates and checks all project source, including that coordinator, and reruns the same native gate. Avoid a cycle in which native baseline delivery requires the broad source migration it must protect. Native integration consumes the accepted external SSH target/optional key-path interface; modernization owns removal of hardcoded connection values from existing host tools and extraction of their embedded remote programs. Guidance owns standards/documentation policy, while the later specs own executable tools and actual compliance. These are ownership boundaries, not implementation authorization.

Planning may create these exploration/research artifacts. It does not authorize application edits, formatting, package installation, source moves, hooks installation, Git changes, publishing, SSH tests, service interruption or deployment. Prior rollout permissions are not standing test-suite permissions.

Preserve earlier product constraints: complete stock Batocera userspace, unchanged Batocera/Wolf/GoW source and mappings, no per-emulator rewrite, universal overlay or host-installed runtime helper. Protect original Batocera checkout/state, content libraries, unrelated apps and the working deployment. The operator reports the current shortcut changes work in the emulators tried; do not reinterpret cleanup as fixing a known failing runtime.

### Historical implementation and reuse inventory

[The detailed baseline](research/repository-baseline.md) owns evidence and limitations.
These are pre-delivery observations, not the current source/tooling inventory. The completed child records and [current tooling](../../../current/tooling.md) describe the delivered installed package, tests, hooks and standards.

- **Implemented:** official image assembly, complete stock metadata inventory, exact single-layer Docker loading, isolated Nix closure, startup/input adapter, immutable publication, owned app registration and sanitized SSH inspection. Source is under experiments/gow-full-x86. The deployed/published transport image c0cf25d69864 is the historical working reference.
- **Implemented:** meaningful host unittest cases; real disk/archive/ACL fixtures; mounted-state/process fixtures; stock image loader and actual Wolf display/shared-memory checks. Preserve their behavior and distinct prerequisites rather than replace them with forwarding-only tests.
- **Partial:** real native transport/emulator probes and X11 screenshot capture are packaged, and successful/failing runs are recorded. The SSH/lobby coordinators were temporary and deleted. There is no maintained clean-clone end-to-end integration command.
- **Documentation baseline:** copied standards and tooling claims were the original input. Guidance ticket 01 reconciled applicability and tooling provenance; ticket 02 migrated [application state](../../../current/app.md) and the [original full-x86 workspace](../../../completed/specs/gow-full-x86/spec.md) into `docs/`. The linked baseline retains pre-cutover observations; no application run is implied by this reconciliation.
- **Absent in observed root:** AGENTS.md, GLOSSARY.md, pyproject.toml, uv.lock, Python version selection, pre-commit configuration, installed src package, root tests layout and a testing README. No detect-secrets integration/baseline was found. Local hooks installation status and secret cleanliness were not checked.
- **Reusable template pieces:** applicable hook definitions, standards, coverage utility and its regression cases, planning vocabulary and optional development-shell patterns. Its tooling-only package settings and React checks do not fit this application unchanged.

### Repository guidance and documentation

The bounded [Guidance and documentation exploration](../../../completed/specs/repository-guidance/explore.md) owns root guidance, glossary coverage, applicable standards reconciliation, truthful current-state topics, legacy migration details and documentation acceptance.

**Shared accepted authority:** docs/ is the sole planning/current-documentation root. Legacy planning/ content may migrate during the cleanup with preserved evidence/provenance, reconciled lifecycle states and repaired links; retaining two permanent roots was not selected. The bounded exploration captures the original workspace's inconsistent lifecycle claims, the dated root handoff and copied template verification limits. No legacy move or application implementation occurred while capturing this decision.

The user clarifies that the legacy planning/ work is finished. Guidance should consolidate it as completed history during the authorized documentation move, preserving the latest operator report, older status notes and individual evidence limits instead of reopening old QA. Keep handoff.md at the repository root locally, untracked; actual file moves and ignore/index changes are not performed during this planning correction.

### Standards, hooks and secret prevention

The Python policy prescribes uv, a real installed src package, typed boundaries, Google-style public/non-obvious docstrings, Ruff ALL, strict mypy, pytest and independently measured 80% application line coverage. Current untyped flat modules, sys.path test loaders and embedded remote source require real work, not just configuration copying. The user requires the project's Python version to follow the selected Batocera release. Retained inventory establishes Python 3.12; the pinned source defines 3.12.8. Current builder packages report 3.13.5, so alignment is required work, not an existing capability. Exact image-version confirmation, compiled-extension compatibility and enforcement rollout remain verification/design obligations.

Use relevant Python/document checks and Nix checks for actual Nix source. There is no observed React/TypeScript application to justify ESLint/Vitest/frontend scaffolding. A development Nix shell must remain distinct from the pinned runtime closure.

**Accepted documentation scope:** remove the unused docs/standards/react.md profile and repair its routing references during the documentation cutover. Omit React/ESLint/Vitest tooling from future configuration. Retain shared standards, repository layout, dependency injection and Python guidance. Copied current-state claims must become truthful; preserve meaningful historical provenance rather than treating template checks as this project's verification. This planning choice does not authorize deleting files now.

**Accepted Nix scope:** retain a repository-specific Nix profile, but trim unused NixOS host-management guidance and template-only claims during the documentation cutover. experiments/gow-full-x86/bridge.nix selects pinned x86_64-linux Nixpkgs packages for Xwayland, xauth, util-linux and Mesa. Nix expression quality and runtime-closure preservation apply independently of the developer's host OS. Retain applicable optional development-shell guidance for the accepted Nix-provided Python/uv policy. Remove unsupported claims about an existing root flake and unused host activation/build instructions. This does not require NixOS, authorize host management or require a flake merely to satisfy copied documentation. Removing the entire profile was not selected because real Nix build source needs guidance.

**Accepted remote-source checking boundary:** maintain remotely executed Python as ordinary source included in formatting, linting, typing and meaningful behavior checks, not a long embedded program string. Package the needed standard-library-only code into a self-contained payload for each SSH invocation, without a persistent server installation or host-only dependencies. Replace the current REMOTE_HELPER/inspect.getsource assembly without duplicating shared activation behavior. Preserve JSON request/response boundaries, ownership checks and non-persistence of private requests. Retaining embedded programs with separate extraction/checking machinery was not selected. This authorizes a planning requirement, not a source refactor or SSH execution.

**Accepted combined quality/layout migration:** after the maintained native regression baseline passes against the existing layout, source relocation and project-wide standards adoption share one bounded cutover and acceptance gate. Work may proceed in small steps, but the migration is not complete until all applicable host, builder, runtime and remote source passes the declared checks, meaningful coverage and required native regressions. Do not exclude legacy source or defer style/typing cleanup to claim the new layout complete. A separately accepted layout-only migration followed by a later standards migration was not selected. Baseline reconstruction remains earlier work; this does not require one large edit or authorize implementation.

The user accepted dependency-injector only outside the Batocera runtime. Do not stage it into the final Batocera image or introduce direct/transitive runtime imports. Use the library at appropriate external application assembly boundaries; permission to use it does not require containers for pure helpers. All environments must still inject configured dependencies explicitly and retain deterministic resource ownership. This is a deliberate runtime exception to the copied library prescription, not an exception to dependency-injection principles. Existing stock third-party libraries remain valid; this decision does not impose a standard-library-only rule. The stdlib-only SSH helper retains its separate delivery contract.

The user selected the ordinary Yelp detect-secrets system-language hook with args: ["--baseline", ".secrets.baseline"], without additional verification flags or a custom scanning workflow. Use the latest published stable release when implementing and keep its hook revision and managed executable aligned. GitHub's latest release, tag listing and PyPI metadata checked on 2026-10-28 all identify v1.5.0, so the selected example needs no version change on current evidence. Review the initial baseline rather than silently accepting real credentials. No scan, baseline or hook installation has occurred; do not claim offline-only verification or secret cleanliness.

### Operator SSH configuration

**User requirement:** externalize the SSH target and identity-file selection rather than committing personal connection details or key filenames in source. remote.py currently hardcodes both. A key path is not the private key, but it is operator-specific metadata and is not suitable as a shared default. Remove operator-specific values from maintained source and examples during the authorized cleanup; use neutral examples. Secret detection does not replace this configuration boundary or guarantee detection of personal filenames. Do not read, copy or place private-key contents into environment variables, images, requests or evidence.

**Accepted interface:** require BATOCERA_GOW_SSH_TARGET for remote commands, accepting user@IP-address, user@hostname or a normal OpenSSH host alias, without an operator-specific fallback. For example, BATOCERA_GOW_SSH_TARGET=tester@192.0.2.10 uses the IP directly; 192.0.2.10 is a documentation address, not this operator's server. An alias such as wolf-test instead obtains its real HostName, user, port and identity settings from the operator's local ~/.ssh/config. An alias is optional. Let OpenSSH use existing config/agent authentication by default. Offer BATOCERA_GOW_SSH_IDENTITY_FILE as an optional path override, never key contents. Resolve these settings at the host entry point and inject configured transport dependencies. Preserve argument-vector subprocess calls, batch mode and host-key verification; do not accept an arbitrary shell command as connection configuration. Local-only commands must not require SSH configuration. Use neutral documentation examples. [Modernization's settings decision](../../../completed/specs/repository-modernization/explore.md#ssh-configuration-and-local-environment-files) adds explicitly selected host dotenv parsing and typed configuration loaded once per invocation/session; implicit discovery remains excluded. No host SSH configuration edit or history rewrite is authorized.

**Planning-only boundary and existing local files:** creating .env, example.env and its ignore rule is a planned requirement, not authorization to implement it during exploration. The user clarified this after the assistant prematurely created them; no undo was requested. Leave the existing files undisturbed and keep further changes limited to planning artifacts until explicit implementation authorization. Current observed state: root .env contains the existing SSH destination and identity-file path with mode 0600; .gitignore contains /.env; sanitized example.env provides neutral settings and usage guidance. Shell syntax/loading checks passed without SSH, a credential scan, reading key contents or Git operations. Application code still uses its constants and does not automatically load .env. Update the example's temporary limitation note when the authorized configuration cutover occurs. The later selected-file loader is approved for modernization planning, not implemented by these existing files or authorized for execution by their presence.

### Maintained source layout

The user accepted one installed Python project with host, builder and runtime subpackages, a dedicated build-assets directory and root tests organized by execution environment. Use the proposed src/batocera_gow/{host,builder,runtime} spelling in the Draft, with build-assets/ and tests/. This is an internal package-name choice, not a deployed identity rename. It replaces the experiments source location after the maintained Wolf regression baseline is established.

Preserve environment boundaries inside this single project. Host tomlkit/development dependencies must not leak into the image or stdlib remote helper. Stage only the appropriate code/assets for each environment and exercise stock runtime imports independently. Separately packaged distributions and a separately maintained flat runtime were not selected; the accepted layout avoids independent distribution/versioning machinery for components shipped together.

The cutover must update bare imports, entrypoints, root discovery, /scripts bindings, Nix paths, runtime sibling scripts/assets, fixture paths, executable modes and source/cache fingerprint inputs together. Source hashing must still cover consumed build assets after splitting directories. Keep stock preservation/security gates intact. Remove obsolete callers in the eventual cutover rather than retain accidental compatibility shims.

The user accepted preserving the published GHCR repository, existing Wolf app/title and runner, and associated working native-home identity during this cleanup. Retire the internal experiments source location and update project documentation without silently renaming those deployed identities. This avoids registry/config/state migration unrelated to code organization. Internal relocation does not authorize changes to /opt paths, output/cache locations or state markers.

### Reproducible real Wolf integration and testing README

Existing Remote offers prepare/register/inspect/log operations, not test-lobby lifecycle. The proposed suite should compose existing probes behind a small maintained opt-in coordinator, not replace Wolf or build a generic deployment framework.

The earlier method was SSH to the real server, native owned Wolf lobbies, image/isolation inspection, permission-gate release, packaged synthetic input and actual stock emulator execution. Desktop.screenshot uses authenticated libX11 XGetImage inside the diagnostic Xwayland session and Pillow to save PNGs. Images are then transferred for review. This proves rendered server-side pixels, not Moonlight transport, physical controller handling or client audio.

Keep automated assertions and optional human review separate. [Wolf integration's observed shortcut-exit contract](../../../completed/specs/wolf-integration/spec.md#shared-emulator-exit-contract-and-ticket-boundaries) owns emulator acceptance for both baseline and migration. Preserve real emulator-before-exit and accessible failure captures. The separate normal-frontend case retains its own readiness capture; no emulator requires a post-exit frontend screenshot. A PNG alone cannot prove the shortcut path.

**Accepted evidence revision:** the user narrowed observed shortcut exit for every emulator, not only NES. Keep stock launch/output, live pre-chord pinned identity, native Guide+Start press/release through the suite gamepad, adapter and unchanged hotkeygen, that same emulator ending, launcher code zero, released input, evidence and safe cleanup. Drop natural-exit log classification and post-exit frontend qualification. This does not cancel later backends or claim graceful shutdown, save persistence, frontend recovery or physical Moonlight forwarding. Direct final keys/exit commands, pre-chord death and forced cleanup cannot pass. Historical failed reports retain their original result.

Retain normal frontend/transport and five receiver checks, plus actual RetroArch native-device consumption for eligible libretro cases. Six backend rows remain in every regression report. Existing receiver success does not prove native emulator consumption. Absent mounted media is a nonblocking untested skip, including no emulator coverage if all rows skip. Complete catalog discovery is research provenance, not execution of every advertised combination; RPCS3/Xenia remain expanded nonblocking targets.

The user accepted independently owned disposable native test homes under a configurable Wolf state root, defaulting to /etc/wolf, with cleanup on both successful and failed runs and selected evidence retained locally. Remaining safety choices include target/profile access, legal fixtures, host busy-state behavior, shared-kernel device risk and evidence privacy/retention details. Read-only ROM mounts do not prevent userdata/config/cache/save writes. Tests must not silently register/restart Wolf, stop unrelated apps or reuse production state.

The earlier /tmp proposal was evaluated in [pinned Wolf source research](research/temporary-test-homes.md). Wolf creates local state/udev data and separately supplies Docker-host bind paths, so literal /tmp requires shared backing storage that is not established. The accepted direction is temporary lifetime under Wolf's existing shared state tree, not a requirement for literal /tmp.

The host-side Wolf state root must be configurable, with /etc/wolf as its default, rather than tied to this operator's installation. Derive test homes as <wolf-state-root>/test-runs/<run-id>; keep runner_state_folder relative and run-owned. Distinguish the configured Docker-host root from Wolf's in-container local root and validate that both refer to the same shared state. A setting change does not reconfigure Wolf or authorize new mounts. Preserve automatic /home/retro and udev bindings. Temporary state can span a test's own fresh lobbies for persistence scenarios. Exact configuration syntax remains open; [the accepted cleanup policy](#cleanup-and-failure-evidence) governs its final removal.

**Accepted controller fixture:** maintain a suite-owned synthetic gamepad and matching ES mapping seeded only into disposable userdata. Do not copy personal profiles or change production mappings, stock configgen or Wolf behavior. Qualify actual device identity, GUID and button/axis indices and native Guide+Start exit delivery. This replaces the older demand for a separate guest-button oracle; existing receiver and native-device checks remain.

Retain both observed lifecycle barriers: transport ready before ending the frontend case, and complete owned container/lobby removal before another case. Preserve the initial receiver timeout as unexplained historical evidence. Use bounded waits, explicit failed/skipped/visual-review outcomes and cleanup failure reporting, not retries that hide uncertainty.

The testing README needs a test-tier/prerequisite matrix, actual maintained commands, credential-free target configuration, exact image provenance, expected writes, legal fixture setup, screenshot mechanism, automated/manual proof boundaries, artifact handling and troubleshooting. Pre-commit must not unexpectedly connect to Wolf or run heavy integration tests.

## Decisions

### User-stated requirements

The seven outcome groups above are in scope for exploration. ProjectTemplate is the reference; applicable docs/standards are the desired style policy. Yelp detect-secrets and formal real-server tests are explicit requests, not optional substitutions with generic local smoke tests.

### Preserved product boundaries

Reuse the successful stock-preserving runtime and its meaningful tests. No user authorization exists here to change upstream projects, install a runtime host helper, publish another image or interrupt the working Wolf server.

### Regression-first sequencing

The user accepted formalizing the existing real Wolf checks against the current implementation before moving source or broadly refactoring the runtime/style. Use the maintained checks as a regression gate for the later cleanup. This establishes a sequencing dependency, not permission to implement the suite, connect to Wolf or change its configuration.

The single-project host/builder/runtime layout and dependency-injector runtime exclusion are accepted. Operational registry/app/runner/home identities remain stable. Guidance is the accepted first bounded documentation scope; secret-policy setup can be sequenced within modernization without making heavy/native tests commit-time hooks or requiring the broad migration before the native baseline.

**Accepted first bounded scope:** detail Guidance and documentation first, so root agent routing, vocabulary, applicable standards and truthful current-state documentation are available before later development. Native Wolf integration remains the prerequisite for the combined source-layout/standards migration. Secret prevention remains owned by the combined modernization spec. Planning the native suite first was not selected. The user has now separately requested all child Drafts; no implementation is authorized.

### Disposable test homes and configurable root

The user accepted temporary per-run homes under the existing Wolf-shared state tree, conditional on making its root configurable for other installations. Default the host-side state root to /etc/wolf; derive test-runs/<run-id> beneath the configured value instead of embedding an operator-specific absolute path. The working WolfExperimental home is not the integration test's writable state.

The harness must preserve Wolf's local-versus-host path translation and validate the configured root against the actual shared state before writing or cleaning up. This is a configuration requirement, not permission to change Wolf's mounts, run tests or delete state.

The user accepted refusing to begin native tests while unrelated Wolf sessions are active. Report the target as busy, not as passing or verified. Do not stop another session or restart Wolf to make room. Concurrent testing without qualified input/session isolation was not selected. Disposable homes isolate writable userdata but do not establish isolation of shared kernel input resources. Reliable session discovery still requires implementation qualification; an idle preflight is not an atomic exclusivity guarantee.

**Accepted mid-run contention policy:** if an unrelated Wolf session is detected after the suite starts, stop further test input and scenarios, release owned inputs, and perform bounded cleanup of only the run's owned resources. Report the run as interrupted/non-passing; do not stop the unrelated session, restart Wolf, automatically retry or claim complete coverage from partial results. If session discovery becomes unavailable, stop further test activity and report the isolation check as incomplete rather than assuming the target remains idle. Detection cannot eliminate the interval between a new session starting and its discovery; this is not atomic exclusivity or protection of every shared-kernel input path. Continuing tests while someone plays was not selected.

### Cleanup and failure evidence

The user accepted automatic cleanup as the default on both success and failure, with selected logs, screenshots and test results retained locally rather than preserving the full failed userdata home. Collect accessible evidence, stop/remove only the run's owned lobbies and containers, verify their absence, then remove only its verified disposable userdata. This trades deeper postmortem state for predictable cleanup, privacy and bounded remote storage.

Cleanup must be attempted even when a test or evidence collection fails. Bounded cleanup failure, lost access or uncertain ownership must be reported as a failed/incomplete cleanup, never as a passing run or permission to delete active/foreign state. No default failed-home retention was selected. Artifact selection and redaction remain implementation contracts; retention is settled below.

**Accepted local evidence retention:** store each run's selected screenshots, sanitized logs and machine-readable results in a separate local output/integration/<run-id>/ directory, gitignored by the existing /output/ rule. Keep evidence from passing and failing runs until the operator explicitly removes it; do not automatically prune or overwrite earlier runs. Restrict access to run artifacts and collect only the owned test session's evidence, not environment/key dumps or unrelated sessions. Do not automatically upload or commit evidence. Gitignore controls normal Git inclusion, not filesystem access or guaranteed confidentiality; preserve the separate privacy controls. Automatic age/count pruning was not selected because it can remove screenshots before optional review. This accepts local disk growth, not preservation of disposable remote state. Capture checkpoints, bounded transfer and explicit unavailable-artifact reporting still need concrete specification.

### Operational identity stability

The user accepted retaining ghcr.io/dafrenchyman/batocera-gow-full-experiment, the existing Wolf app/title and WolfExperimental runner, and its associated working userdata home while modernizing the source layout. Internal source and project documentation should no longer describe the maintained project as an experiment, but documentation must still show the real deployed identifiers. No registry rename, app rename or userdata migration is part of this cleanup.

### Single-project source layout

The user accepted the proposed src/batocera_gow tree with host/, builder/ and runtime/ subpackages, root build-assets/ for non-Python image/build inputs, and root tests/ separated by execution environment. Keep one installed Python project rather than separately versioned packages. Host-only dependencies must not become runtime requirements; environment-specific staging remains necessary.

The migration is gated on maintained Wolf regression tests against the existing implementation. Update all affected imports, commands, build contexts, assets, tests and provenance inputs in the eventual cutover, without old-layout shims or changes to deployed registry/app/home identities. The Draft uses batocera_gow; interpreter supply follows the accepted uv/Nix policy below, with exact stock version and artifact availability still requiring actual verification. This structure does not authorize implementation.

### Batocera-led Python version

The user accepted host Python patch differences within Batocera's major/minor version. For the selected baseline, host development may use Python 3.12.x, including the reported NixOS 3.12.12. The default full-version pin and project-owned builder interpreter remain tied to the confirmed stock version; source currently defines 3.12.8, pending actual runtime-version confirmation. Native checks run with Batocera's unchanged stock Python. Its major/minor drives package/tool/hook targets. The builder's unrelated Debian 3.13.5 interpreter is not the project interpreter. Preserve OS interpreters and review this alignment on Batocera upgrades.

The user accepted uv-based interpreter/environment management with a NixOS host exception. uv owns project environments and locked dependencies while using the Nix-provided host interpreter; it provisions the builder's matching interpreter separately. The user reports NixOS Python 3.12.12 already installed. Do not rerun checks to confirm that observation. No NixOS configuration change or additional global Python installation is required by this policy.

Select Nix-provided host Python 3.12.x explicitly through UV_PYTHON and disable managed downloads there with UV_PYTHON_DOWNLOADS=never. A project development shell can supply these settings without changing the OS. Keep the default .python-version aligned to confirmed stock for builder provisioning; the Nix host's explicit interpreter selection permits a different 3.12 patch. Project metadata must allow that host patch while retaining stock as a dependency-compatibility target. Provision the builder interpreter and dependencies before networkless assembly. Interpreter availability and actual imports remain implementation verification, not established capabilities.

Exact host patch matching was not selected. Keep OS and Batocera interpreters intact; do not copy the host virtualenv/native extensions or add uv/development environments to the final runtime. Host patch tolerance does not prove native-extension or stock-runtime compatibility. [The interpreter research](research/runtime-python-dependencies.md#nixos-and-patch-level-compatibility) records the primary-source limits and the reason for using a Nix-provided host interpreter.

Python version/provider and dependency policy are settled. The remaining work is applying that policy to the temporary Docker build container and checking the resulting commands/imports after source relocation. Recording stock's exact patch version is a routine build/setup check, not a new user decision. The user's reported host 3.12.12 remains accepted without rechecking it.

### Dependency-injection boundary

The user permits dependency-injector in code that executes outside Batocera, but excludes the library from the Batocera runtime and final-image dependency staging. They judged the packaging/native-compatibility risk unnecessary for this cleanup. Research established a plausible wheel, not a tested image import; runtime adoption was considered and not selected.

Apply explicit dependency injection across host, builder and runtime code, independently of the library. The entry point chooses configuration sources, validates settings and assembles dependencies. Services receive configured collaborators and the settings they need rather than loading configuration or silently constructing production defaults themselves. Preserve the user's accepted example:

```python
class ReportService:
    def __init__(self, client: ApiClient, config: ReportConfig) -> None:
        self._client = client
        self._config = config
```

Keep business logic independent of containers and wiring markers. Injected resources are borrowed unless the contract transfers ownership; the owner arranges deterministic cleanup. Pure functions do not need container machinery or an interface merely to satisfy this rule. Record the runtime-specific library exception in project guidance/standards during the authorized documentation cutover.

### Standard detect-secrets hook

The user selected this simple configuration, with permission to use a newer published stable version if available. Upstream release/tag metadata and PyPI still identify 1.5.0 as latest on 2026-10-28:

```yaml
- repo: https://github.com/Yelp/detect-secrets
  rev: v1.5.0
  hooks:
    - id: detect-secrets
      language: system
      args: ["--baseline", ".secrets.baseline"]
```

Use this hook without adding --no-verify or other verification-policy overrides. Resolve the latest published stable version during implementation and pin the hook revision and available system-language executable consistently; do not use a floating latest or unreleased branch. Current [GitHub release metadata](https://api.github.com/repos/Yelp/detect-secrets/releases/latest), [tags](https://api.github.com/repos/Yelp/detect-secrets/tags?per_page=8) and [PyPI metadata](https://pypi.org/pypi/detect-secrets/json) agree on v1.5.0. Preserve ordinary reviewed baseline handling; do not baseline real credentials as a way to make the hook green. Custom scanners, historical scans and new CI enforcement are not requested. The user selected the ordinary hook, not a separately accepted network-verification policy.

### Available multi-backend test content

The user now requires existing content only, without custom console programs, source adaptations or project-owned ROM development. Public redistributable fixtures remain useful where permitted and available. Explicit operator-owned per-system media folders can also supply required launch/display and Guide+Start cases without distributing private ROMs/disc images. This supersedes the earlier public-only fixture preference, not the six-backend matrix or rights boundary. Scope remains the pinned full-x86 release.

The [retained catalog inventory](research/artifacts/packaged-system-inventory.json) was statically extracted from the packaged /usr/share/emulationstation/es_systems.cfg. It records every advertised system, emulator, core and extension with source provenance, including ports, utilities and non-ROM categories. An advertised entry is not proof an executable is present or successfully runs. The test unit must distinguish system, emulator and core; a successful RetroArch/NES case does not establish SNES, Genesis or Atari coverage.

Initial discovery now covers every advertised entry in the [readable fixture index](research/artifacts/fixture-candidate-index.md), backed by the [structured evidence catalog](research/artifacts/fixture-candidate-catalog.json) and [research report](research/emulator-fixtures.md). All 253 system IDs match the packaged inventory exactly, with no duplicates. Each row preserves all advertised backend/core alternatives, but the candidate is a per-system lead, not a qualified fixture for every combination. Useful open classic-system, computer and engine fixtures exist; source-build, firmware/data, asset-license and compatibility gaps remain explicit, including the unresolved Xenia visual/input fixture. No row is approved for redistribution or verified by execution.

Check actual distribution terms for public content the project distributes, including binaries, linked resources and assets. Private operator media instead requires authorized use, supported stock format and privately recorded selected identity; unpublished source and public redistribution permission are not prerequisites for that route. Filter per-system folders by supported extensions and preserve multi-file relationships. Random selection is permitted but must be reproducible from locally retained identity, not rerolled after failure for green. Public docs and evidence exports contain no private media bytes or library paths. Firmware and generated userdata remain separate. No media is downloaded, built or run during planning.

Preserve Batocera's existing component licenses and redistribution obligations. Its [official policy](https://www.wiki.batocera.org/license) documents mixed licenses, with LGPL v3 generally applying to Batocera-team code rather than the whole distribution. Added test code and artwork require their own rights; firmware remains separately provisioned. This does not force every fixture or original repository file to use LGPL v3. The user's licensing clarification did not select a new repository-wide license. Prefer suitable already-bundled stock games where they provide the required checks, without mistaking inclusion for open-source or asset-license clearance.

The user accepted explicitly configured, operator-supplied BIOS/firmware for firmware-dependent integration cases. Keep those files outside source, images and distributed fixture bundles. Do not automatically acquire proprietary firmware or report missing prerequisites as successful verification. Restricting all cases to fully redistributable firmware was not selected because it would prevent qualification of requested backends while open replacements remain unresolved. This is a test-design decision, not permission to read or stage files on a live host.

Two native levels remain accepted: a maintained six-row regression gate before broad migration and explicitly selected expanded qualified cases. Execute every eligible regression case; only evidenced absence of compatible mounted media is skipped nonblocking. No minimum number of media-backed cases is imposed and no unexecuted row is passing coverage. Actual attempted failures, other prerequisites and safety/evidence/cleanup errors still block. Running every advertised combination on every invocation is not required.

**Accepted required cases and nonblocking expanded targets:**

| System             | Emulator/core                                      | Planning disposition                                                  |
| ------------------ | -------------------------------------------------- | --------------------------------------------------------------------- |
| NES                | RetroArch / FCEUmm                                 | Accepted required regression                                          |
| SNES               | RetroArch / Snes9x                                 | Accepted required regression                                          |
| Genesis/Mega Drive | RetroArch / Genesis Plus GX                        | Accepted required regression                                          |
| Atari 2600         | RetroArch / Stella                                 | Accepted required regression                                          |
| PlayStation        | DuckStation                                        | Accepted required regression                                          |
| Xbox               | xemu                                               | Accepted required regression                                          |
| PlayStation 3      | RPCS3                                              | Accepted nonblocking expanded target; fixture qualification pending   |
| Xbox 360           | Xenia, with the selected packaged variant recorded | Accepted nonblocking expanded target; visual/input fixture unresolved |

All six rows use the same sibling-owned observed shortcut-exit acceptance when media is eligible. Private media uses existing mounted libraries, stock directories/extensions and shared environment-configured sources. Absent media is explicitly skipped and nonblocking, including all-six absence disclosed as no emulator exit coverage. Eligible firmware gaps, attempted failures and unsafe/incomplete evidence or cleanup still block. Keep actual input routes, pass/skip/failure counts and gaps visible. No natural-exit classifier, post-exit frontend, guest-input, state/time or custom-ROM oracle is required.

The user requested that PS3/RPCS3 not block cleanup, like Xbox 360/Xenia. Keep both as named, nonblocking expanded-suite targets while their fixture gaps remain unresolved. Neither must pass before the initial source/style cutover, and neither may be counted as verified without actual qualification and passing evidence. Original Xbox/xemu is a distinct backend and is required; the Xbox 360/Xenia deferral does not defer xemu. Making RPCS3 and Xenia mandatory cutover blockers was not selected.

The earlier mandatory guest-input, exhaustive Guide-action, natural-exit log-classification and post-exit frontend predicates are superseded by the accepted observed-exit decision. A running emulator, sent chord or receiver echo alone remains insufficient. Follow the [owning decision](../../../completed/specs/wolf-integration/explore.md#observed-shortcut-exit-acceptance) rather than duplicate a broader gate here.

Guide-hotkey handling remains the purpose of this regression, but exit is the selected representative behavior, not proof every shortcut always works. No menu, gameplay-button, save-state, rewind, fast-forward, disc-change or translation-feature matrix is required. No custom ROM/ISO implementation is needed to manufacture guest observations.

Human screenshot or Moonlight/controller review remains optional. Native server injection and captured pixels do not prove physical client forwarding, decoded client video or heard audio. Required evidence/privacy, ownership, contention refusal/interruption, finite deadlines and owned cleanup stay unchanged.

## Options Considered

- **Accepted regression-first constraint:** formalize repeatable Wolf checks against the current layout before broad source/runtime/style changes. Establish the reference behavior before changing several failure-producing boundaries at once. Guidance is the first bounded documentation scope; independent secret-policy setup stays within modernization and does not require remote tests at commit time.
- **Not selected for broad migration:** combine source relocation, runtime refactoring and reconstruction of the native test workflow in one cutover. This would make failures harder to attribute and native regressions harder to isolate.
- **Unselected template copy:** copy all configs/claims unchanged. Evidence contradicts its applicability: wrong package semantics, missing real-source coverage, unrelated frontend checks and absent tooling claims. Reuse applicable pieces rather than this approach.
- **Out of scope absent a new decision:** per-emulator rewrites, upstream modifications, universal overlay, generic deployment framework, automatic production restarts or application scaffolding solely to satisfy template tooling.
- **Resolved /tmp alternative:** the user accepted disposable homes under the existing shared state root, with a configurable host root and /etc/wolf default. Literal /tmp is not required. Private temporary scratch remains possible; no live mount or home-creation check has run.
- **Accepted failure default:** clean owned native resources and disposable userdata on successful and failed runs, retaining selected diagnostics locally. Preserving the full failed home is not the default; cleanup failures remain visible rather than being hidden.
- **Accepted operational stability:** retire the internal experiment layout without renaming deployed registry/app/runner/home identities. Renaming those identities now was not selected because it would add configuration and persistent-state migration.
- **Accepted source organization:** one installed project with host/builder/runtime subpackages, separate build-assets and environment-specific root tests. Independently packaged components and an independently maintained flat runtime were not selected.
- **Accepted dependency-injection compromise:** retain explicit configured-dependency injection everywhere, permit the library outside Batocera and exclude it from the runtime. Private runtime installation was feasible enough to investigate but not selected because its additional packaging/compatibility work is not justified for this cleanup.

## Input routing inventory

| Source request                                                                | Owner                                                                                 | Current disposition                                                                                                                                                                                         |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ProjectTemplate, copied docs, AI-friendly repo, AGENTS.md and GLOSSARY.md     | [Repository guidance](../../../completed/specs/repository-guidance/spec.md)           | Root routing, vocabulary, standards reconciliation, single docs root and local-only handoff disposition captured                                                                                            |
| Messy style and proper docstrings under docs/standards                        | [Repository modernization](../../../completed/specs/repository-modernization/spec.md) | All real source, explicit DI, accepted interpreter policy and full quality/layout acceptance gate                                                                                                           |
| Template pre-commit hooks                                                     | Repository modernization                                                              | Applicable Python/Nix/document/config checks; no frontend or surprise native test hooks                                                                                                                     |
| Yelp detect-secrets                                                           | Repository modernization                                                              | Ordinary system-language baseline hook; latest stable pinned consistently, reviewed baseline, no extra verification flags/custom workflow                                                                   |
| Move experiments/gow-full-x86 into src or another maintained layout           | Repository modernization                                                              | Single installed project and full imports/assets/provenance cutover after native baseline, stable deployed identities                                                                                       |
| Real Wolf SSH tests and screenshot proof                                      | [Wolf integration](../../../completed/specs/wolf-integration/spec.md)                 | Six backend rows using the shared observed shortcut-exit contract; independent frontend/receivers, applicable native-device checks, owned cleanup, readable gaps and mounted media; RPCS3/Xenia nonblocking |
| Explain testing and capture in README                                         | Wolf integration                                                                      | Maintained testing README, actual capture mechanism, local evidence and honest client/manual proof limits                                                                                                   |
| External SSH configuration instead of committed personal target/key filenames | Wolf integration consumes; repository modernization migrates existing host tools      | Required target and optional key-path environment interface, normal OpenSSH config/agent, no personal fallback or automatic dotenv loader                                                                   |

The delivered child-spec set is indexed in [epic.md](epic.md#child-spec-backlog). Preserve all three guidance, seven integration and five modernization ticket identities and original acceptance evidence. The complete old-layout baseline supplied modernization's actual prerequisite; modernization then repeated the native gate on its own installed source/image. No child remains blocked on the superseded NES-only resume state.

## Open Questions

No consequential native-policy question remains. The complete old-layout baseline and expanded replay are delivered in [Wolf integration](../../../completed/specs/wolf-integration/completion.md); its actual image-bound media/controller/lifecycle/shared-root/cleanup observations are not future work. Newly changed source/images still require their own authorized qualification. Python/layout, standards, cleanup, coverage and security requirements remain unchanged.

The [mounted-media contract](../../../completed/specs/wolf-integration/explore.md#fixture-and-controller-contracts) is settled: use the app's existing read-only ROM/BIOS mounts, shared environment-configured host sources and stock system-folder/extension eligibility. Missing media is explicitly skipped, untested and nonblocking for baseline and modernization, including an all-skipped matrix with no emulator exit coverage. Execute and assert every eligible case; actual attempted failures and unsafe lifecycle/evidence/cleanup still block. Media-dependent native consumption can be skipped for absent media, but normal frontend/transport and five receiver checks remain required.

## Next Discussion Queue

No epic implementation or planning decision remains. Preserve the completed guidance, native baseline and installed-modernization workspaces and their image-bound qualifications. Newly changed source/images still need their own separately authorized qualification; historical passing runs do not qualify later beta changes. Missing-media and unqualified-feature limits remain explicit, and completion grants no further Git, build, SSH, deployment or service-interruption permission.

## Assumptions

- The user wants maintenance rather than a functional redesign. Regression-first sequencing is accepted; any intentional behavior change still requires its own contract.
- Current published image and retained generated artifacts are useful reference evidence, not guaranteed forever-present clean-clone fixtures.
- A future test target can support the same stock runtime features; this is unverified until an explicitly authorized target check.

## Risks

Source moves can invalidate source/cache identity, builder imports, modes or runtime asset adjacency. Type/docstring refactors can break remotely extracted source. Broad strict-tool adoption can hide real gaps through exclusions or incorrectly report no applicable source. Host dependency adoption can contaminate stock runtime compatibility.

Native tests can write persistent state, expose private screenshots/logs, leave held inputs or owned lobbies behind, or contend with human sessions. Existing device-number reuse exposure remains disclosed, not solved by moving files or adding hooks. Secret scanners and redaction heuristics cannot promise no leaks; baselines require review and real credentials require remediation.

Copied template evidence and mixed planning roots can mislead future agents about what exists or passed. Preserve historical provenance while making one current authority.

## Not yet specified

The six required backend rows and nonblocking expanded targets have their accepted dispositions in the completed children. Eligible native cases passed; Mega Drive remains an explicit no-media skip, not tested coverage. CI beyond local hooks, RPCS3/Xenia qualification and physical-client acceptance remain outside the delivered contract. Do not reduce historical coverage to NES, count skipped media as passing, or extend old proof to a changed image.

## Notes

No ticket resume remains in this epic. The completed children preserve actual source/image, coverage, stock-preservation, native and cleanup evidence, including unsuccessful attempts and their limits. Completion and current-documentation review belong to [epic.md](epic.md); subsequent feature or deployment work retains its own authorization and verification boundaries.
