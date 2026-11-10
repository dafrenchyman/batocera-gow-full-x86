# Research: repository maturation baseline

## Question

What can be reused from ProjectTemplate and the working Batocera/Wolf project, what is actually missing, and which decisions must precede standards enforcement, source relocation and repeatable remote integration tests?

## Context

Owner: [repository maturation exploration](../explore.md). Source intake: [user brief](../inputs/user-brief.md). This is read-only discovery for planning, not a compliance audit or implementation authorization.

## Method

Read the copied standards and current documents, ProjectTemplate guidance/tool configuration/coverage utility, actual build/runtime/test code, retained diagnostic records and relevant completed research. Three read-only surveys covered standards/hooks, source-layout coupling and native Wolf verification. Read Yelp's primary README for hook, baseline and network-verification behavior. No Git operation, hook installation, secret scan, test, build, Docker operation or SSH operation ran during this survey. Current remote health, installed tool versions and source compliance were not exercised.

## Evidence and findings

Cutover note, 2026-10-28: the observations below retain the pre-implementation baseline, not current navigation. Guidance ticket 02 migrated [application state](../../../../current/app.md) and the [original workspace](../../../../completed/specs/gow-full-x86/spec.md) into `docs/`, preserving chronology and per-check limits. The original `planning/` paths below are historical inventory. Tooling reconciliation is recorded by [ticket 01](../../../../completed/specs/repository-guidance/tickets/01-reconcile-standards-and-tooling.md); this note does not rerun the baseline or claim application compliance.

### Guidance, documentation and tooling

- Root directory inspection found no root AGENTS.md, GLOSSARY.md, pyproject.toml, uv.lock, .python-version, .pre-commit-config.yaml, root flake, scripts, src or tests. `.agents/AGENTS.md` points to a missing root guide. The user has supplied `.agents/skills/` and copied `docs/`.
- `docs/current/tooling.md` describes ProjectTemplate's installed Python/React/Nix tooling and successful historical verification. Its referenced root configuration and web application tooling are absent here. Those statements are copied template provenance, not evidence about this application.
- Actual current application evidence remains in `planning/current/app.md`; the original full-x86 spec remains in `planning/active/specs/gow-full-x86/`. Completed transport work is now under `docs/completed/specs/`. `docs/active/specs/` was empty. No docs/archived or planning/archived directory was observed. Documentation authority and link migration need an explicit reconciliation, not a second permanent planning tree.
- Follow-up inspection found planning/completed/specs empty and gow-full-x86 still in planning/active/specs. That workspace's completion.md names a completed destination and an older pending-interactive-acceptance state, while the current application record contains later native evidence and user reports. These are historical/lifecycle inconsistencies to reconcile, not permission to declare completion or rerun reported observations. Preserve the sequence and verification limits during any documentation migration.
- `docs/standards/general.md` and `repo-layout.md` allow applicable profiles and deliberate explained substitutions. No React/TypeScript application or manifest is present. The frontend-only ESLint maintenance exception should not be imported merely to copy the template.
- Template GLOSSARY.md supplies planning vocabulary, not the application's Batocera/Wolf/input/artifact vocabulary. A project glossary must define domain terms without collecting implementation detail. Root AGENTS should route to policy and protected boundaries rather than duplicate all standards.

### Python, hooks and standards

- `docs/standards/python.md` prescribes uv/lock ownership, a real installed src package, typed boundaries, Google-style docstrings, Ruff ALL with safe fixes/formatting, strict mypy, pytest and independent 80% application line coverage with branch reporting. Current code is flat script modules plus unittest and explicit shell/container suites. `requirements.txt` contains tomlkit==0.13.3, not a complete development dependency graph.
- Representative gaps are concrete, not observed lint failures: common.ProjectPaths and helpers have incomplete type/docstring contracts; tests modify sys.path; runtime process/device helpers lack substantive API docstrings; some text I/O lacks explicit encoding. Cleanup must preserve descriptor ownership and specific failure semantics rather than mechanically replacing exception handling.
- `remote.py` embeds executable Python in REMOTE_HELPER and injects `inspect.getsource(activate_config)`. Linting the outer string does not check the remote program. Adding annotations, decorators or host-only dependencies to that extracted function can break remote execution unless its execution context is updated deliberately.
- Template hooks are Ruff check/fix, Ruff format, strict mypy, ESLint, plugin-free Prettier, Alejandra, Statix and deadnix. Python, relevant documentation/config formatting and Nix apply here; ESLint does not. Template hooks use full Git-SHA revisions, but system Node/Nix binaries are not pinned merely by those hook SHAs. Tests and coverage stay outside commit-time hooks.
- Template uses Python 3.12 and exact tool dependency pins. Reuse its configuration pattern only after verifying the host/builder/stock-image compatibility contract. The stock runtime does not obtain host uv/tomlkit/development dependencies.
- Template coverage configuration assumes src and tests. Its line-floor utility returns not-applicable when src has no Python files. Blind copying would ignore the existing real application under experiments and can create a false green. Coverage must include the actual chosen source boundary throughout any migration.
- Template pyproject is tooling-only with package=false, no build backend and project-template identity. Those package semantics do not fit this application's required installed package.
- `docs/standards/dependency-injection.md` prescribes dependency-injector at application assembly boundaries. Scope or a justified exception must be decided, particularly for stock-compatible in-image and stdlib-only remote code. Explicit dependencies and resource ownership do not imply containers for every pure helper.
- The development flake and the deployed `bridge.nix` have different responsibilities. Preserve pinned Xwayland/Mesa/utility closure inputs; adopting a development shell is not permission to replace runtime package inputs or manage the host.

### Secret prevention

Primary sources: [Yelp detect-secrets](https://github.com/Yelp/detect-secrets) and its [README](https://raw.githubusercontent.com/Yelp/detect-secrets/master/README.md).

- Yelp documents pre-commit integration, scanning tracked files, optional all-files scanning, reviewed baselines, audit and narrow false-positive allowlisting. The hook blocks findings not already accepted by a supplied baseline. Baseline creation is not credential remediation.
- The CLI exposes `--no-verify` to disable additional network verification of candidates. Offline verification behavior is a policy decision; a local hook should not silently introduce outbound candidate-secret verification.
- No configured Yelp hook, dependency or baseline was found in this repo or the template. No scan ran, so no secret-free claim is available. The README's example revision is not a newly verified release selection for this project.
- `.gitignore` excludes output, cache, local venv, bytecode and Nix result links. This does not prove all tracked source/docs/tests are clean, protect existing Git history, or prevent private evidence being force-added. Initial findings must be reviewed without echoing credential values. Real credentials require removal/rotation, not blanket baselining.
- Proposed scope is tracked first-party source, shell, docs, tests and configuration with narrowly justified fixture exceptions. Historical scans, CI enforcement, artifact scanning and baseline ownership remain decisions. Hook installation modifies local Git hooks and requires separate execution permission.

### Source layout and preservation boundaries

Three execution environments share the current directory:

1. Host build/publication/registration/SSH orchestration, including host tomlkit.
2. Disposable networkless Debian assembly/inventory tools under /scripts and /work.
3. Stock-Batocera Python runtime under /opt/gow-full-x86, plus the isolated Nix executable closure.

A maintained src layout is appropriate, but a directory rename is insufficient:

- Bare sibling imports, **file**.parents root discovery, Build.code, Nix import expressions, shell wrappers, Docker contexts/binds, fixture paths and runtime sibling subprocesses all encode the current layout.
- assemble.source_fingerprint hashes four named siblings. Extracting rules to other modules without updating the fingerprint risks stale cache reuse. working_tree_source currently hashes the entire experiments/gow-full-x86 tree, including assets/tests, relative paths, modes and contents. A src-only replacement could omit consumed assets or change provenance semantics silently.
- Builder code cannot acquire host-only imports. In-image runtime cannot acquire dependencies installed only in the development venv. Tests should import an installed package without sys.path tricks, while actual stock-image compatibility remains independently verified.
- A reasonable proposal is one maintained source/package tree with explicit host/runtime boundaries, separate build assets and root tests divided by execution environment. One or two Python packages and flat-versus-package deployment remain open. Package/data staging must be explicit, not disguised compatibility shims.
- Source names are separate from registry/app/home identities. Retiring experiments does not require renaming GHCR repositories, WolfExperimental, /opt/gow-full-x86, persistent homes, /userdata, output paths or runtime labels. Such operational migrations need a separate choice.
- Preserve all stock-path/metadata gates, root-owned non-writable additive code, ACL removal, complete FAT/SHARE, exact Docker-save layer loading and no-write content mounts. Do not format or normalize extracted upstream payloads.

### Real Wolf tests and screenshot proof

- `remote.py` provides prepare/register/inspect/log operations, not a native integration runner. The working lobby coordinators were temporary and removed. Packaged `runtime/transport_probe.py` and `runtime/emulator_probe.py` remain reusable.
- The historical coordinator used local SSH credentials, Wolf's API, owned native lobbies and the packaged image. Probes ran inside the app session using stock evmapy/hotkeygen and actual configgen/RetroArch, not mocks or a replacement compositor. The coordinator inspected identity/isolation before creating the input permission gate.
- `emulator_probe.Desktop.screenshot` authenticates to session X11, uses libX11 XGetImage on the isolated root window and saves pixels with stock Pillow. The resulting PNGs were fetched and visually reviewed. These are real server application screenshots, not Moonlight-decoded frames or proof of heard client audio.
- Machine-verifiable evidence includes exact image/source integrity, capabilities/mounts, broker/worker readiness, observed context changes, held/release/pointer behavior, stock input hashes, actual pinned emulator termination, launcher status and owned cleanup. A PNG's existence or a live emulator is not proof of visible menu/game correctness.
- Five receiver cases already cover held exit/pointer reset, pointer button, context isolation, graceful source removal/recreation and command-on-stock-release. Actual RetroArch native udev consumption must remain separate; an earlier XTEST-only pass missed that consumer-visible failure.
- The emulator probe currently needs an existing compatible ES controller profile and hardcoded existing NES ROM. Reproducibility requires legal declared content and a fixture/profile/data policy, not redistribution of private BIOS/ROM libraries.
- Current native sessions use the persistent WolfExperimental home. Read-only ROM mounts do not prevent generated config, caches, saves or installation writes to userdata. A new suite needs independently owned disposable native state or explicit existing-home permission. Do not bypass native home semantics with an arbitrary bind.
- A first combined receiver run timed out. Isolated cases passed; the unchanged image passed after the temporary coordinator enforced transport readiness and complete container removal between cases. Exact transient cause remains unproven. Preserve those barriers and failed evidence; do not add retries that turn unexplained failures into green.
- Remaining runner work includes explicit target configuration, bounded SSH/phase/cleanup waits, owned lobby/container lifecycle, result/screenshot transfer, privacy-filtered evidence, nonzero cleanup failures and interruption handling. Existing source cleanup includes some unbounded waits and report-publication risks that require targeted review.
- `tests/stock_runtime_tests.py` and `wolf_session_tests.py` require actual image/session environments and are not in test\_\*.py host discovery. Mounted-state fixtures require extra builder-only mount permissions; those must not become native app capabilities.

## Dead ends and rejected approaches

Retain the reasons already recorded in completed project and template research: single-container startup rather than a sidecar Wolf cannot launch; exact-layer Docker loading rather than metadata-losing BuildKit ADD; final-device stock udev metadata rather than per-emulator overrides or receiver-only proof; no universal overlay or upstream patches; no revival of the template's rejected mutable Alejandra integration. No new experimental failure was produced during this survey.

## Reusable artifacts

- Existing behavioral test suites under experiments/gow-full-x86/tests, including real filesystem, metadata, process/input ownership and registration failure boundaries.
- Native probes and screenshot implementation under experiments/gow-full-x86/runtime.
- output/gow-full-x86/input-transport-packaged-smoke-first.json, final smoke/frontend JSON, visual PNGs and cleanup evidence. These are generated local artifacts, not guaranteed clean-clone inputs.
- docs/completed/specs/gow-input-transport-trial and deployment; template-standards-and-workflow research for retained hook tradeoffs.
- ProjectTemplate coverage utility/tests, hook patterns and applicable standards, after correcting applicability and source measurement.

## Decision impact

Recommend staged behavior-preserving maturation. Establish a reproducible Wolf regression contract before broad runtime relocation/refactoring. Keep useful code/tests, stock boundaries and deployment identities stable unless separately approved. Reconcile copied claims before agents rely on them; do not call configured checks passing compliance. Use applicable profiles instead of importing an unrelated frontend.

## Follow-up questions

Regression-first sequencing, configurable disposable test homes, cleanup on success/failure and stable deployed registry/app/runner/home identities are accepted in the owning exploration. Remaining decisions concern package/runtime boundaries, dependency/tooling applicability, native target permissions and legal fixtures, automated versus human evidence, secret scanning/baseline policy and documentation migration. See the owner's discussion queue for sequence.
