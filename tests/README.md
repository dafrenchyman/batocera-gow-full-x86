# Testing Batocera/Wolf integration

Maintained source uses the installed `batocera_gow` package. [Local cutover verification](#installed-cutover-local-verification) describes installed commands and builder/runtime fixtures. The recorder-free normal image passed the actual installed full qualifier and the separately authorized complete native pytest retry, with 12 passes and one Mega Drive no-media skip. Frontend, five independent receivers and all eligible emulator variants passed. The earlier Atari failure remains recorded; the retry selected different media and establishes no cause or repair. Maintained-source changes invalidate current-checkout attribution even when staged runtime bytes are unchanged. [Current verification evidence](../docs/current/tooling.md#installed-cutover-verification) owns exact evidence, final checks and limits.

This guide covers local mounted-media tools and the opt-in maintained native runner. NES/FCEUmm passed `stock-native-observed-exit-v3` in packaged native run `d0f90ed2198440ec8c8978c5c77e4d28`. Independent same-image run `1979a36a973144f180f5fe720b57a94d` passed normal ES and all five receiver assertions. Both retained required evidence and completed owned cleanup. Historical run `9b7ba15c6ff64f3782e3de9f8c0803ad` failed its stricter natural-exit gate and keeps that result and assertion version. NES success does not qualify other emulators or complete the six-backend baseline.

Ticket 04's SNES/Snes9x and Atari 2600/Stella tiers passed the native observed-exit contract on stock-verified image `sha256:128ebf123b3a78a2162e90fbcc51dbaeab29203758729d8232c0dd8596e46572`, source `worktree-sha256:baab3bf61c158ef7689575cbdeab5b5603f7665ae4803e69dca9fc39899976df`. Mega Drive/Genesis Plus GX genuinely skipped for no compatible mounted media on that same image. Original-selection NES run `c22d3a64e581484fbe53690caf5dfb36` and independent normal frontend/five-receiver run `555cba3f57a84b849854319c76f5dc0b` also passed on that image/source, preserving the common path. These separate results do not complete the six-backend baseline.

Ticket 05's ordinary maintained CLI OpenGL run `8e6ca8810b3c45ac827b89c0a044e79f` and Vulkan run `0476b65d193b4b4e906f3d5f2e209939` passed independently on stock-verified image109c14e2/source175676dc. Both used the same supported private selection, stock launch/configgen, actual renderer observations, native Guide+Start, launcher zero and owned cleanup. The disposable fixture seeds `psx.bezel=none`; MangoHUD-enabled bezels remain unqualified. Earlier failed and diagnostic-only attempts below keep their original results. These two smoke passes do not qualify a full baseline.

Ticket 06's separately selectable `xbox-smoke` passed observed native Guide+Start exit in run `7094e0cca52148729e12d458d40bb016` on the verified image/source recorded below. The unchanged stock HDD seed stayed in owned disposable userdata. This qualifies the private selected run, not the public case template or the full baseline.

## Tiers and prerequisites

| Tier                            | Current entry point                                                                                    | Prerequisites and effects                                                                                                                                              | Proof limit                                                                                              |
| ------------------------------- | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Host logic                      | Media and native pytest commands below                                                                 | Python 3.12 and pytest; temporary files, delivered stdlib helper and bounded owned subprocesses only                                                                   | Configuration, lifecycle and ownership logic; never native evidence                                      |
| Local CLI smoke                 | `tests/integration/local/media_smoke.py` and `batocera-gow-native plan`                                | Installed host environment; no content mount, target or SSH needed                                                                                                     | Actual local CLI behavior only                                                                           |
| Image/runtime fixtures          | `tests/integration/builder/` and `tests/integration/runtime/`                                          | Each suite's image, builder, native-device or container prerequisites; separately authorized                                                                           | Actual loader/session/assembly checks, not a six-case native exit gate                                   |
| Native frontend/receivers       | `batocera-gow-native run --authorize-native --tier frontend-receivers`                                 | Separately authorized target/state/input/cleanup, exact already-loaded diagnostic image, injected content sources, existing profile and qualified native prerequisites | Qualified normal ES plus five receiver cases only; no emulator exit coverage                             |
| Native NES/FCEUmm smoke         | `batocera-gow-native run --authorize-native --tier nes-smoke`                                          | Same inspected lifecycle plus existing read-only NES media and suite-owned pad/profile; exact verified packaged image/source required                                  | Qualified selected NES launch/display and observed Guide+Start exit only                                 |
| Native remaining libretro smoke | `batocera-gow-native run --authorize-native --tier snes-smoke`, `megadrive-smoke` or `atari2600-smoke` | Same lifecycle, stock-declared read-only media and exact selected core; exact verified packaged image/source required                                                  | Selected SNES/Atari observed-exit passes; Mega Drive no-media skip on the recorded image/source          |
| Native PS1/DuckStation smoke    | `batocera-gow-native run --authorize-native --tier psx-smoke` or `psx-vulkan-smoke`                    | Same inspected lifecycle, immutable image/original supported PS1 selection and read-only BIOS; independent disposable state/evidence per renderer                      | Both renderers passed observed native exit; undecorated PSX fixture, image-bound proof below             |
| Native Xbox/xemu smoke          | `batocera-gow-native run --authorize-native --tier xbox-smoke`                                         | Same lifecycle, mounted supported Xbox disc, read-only MCPX/compatible BIOS and verified stock seed copied only into owned userdata                                    | Passed selected Xbox startup/display and observed Guide+Start exit on the recorded image/source          |
| Full native regression          | `batocera-gow-native run --authorize-native --tier regression`                                         | Same protections, frontend and all five receivers, all six backend rows including separate DuckStation GL/Vulkan owners; eligible mounted inputs and firmware          | Complete old-layout gate only when its actual report and cleanup pass; skips are not exit coverage       |
| Expanded qualified selection    | `batocera-gow-native run --authorize-native --tier expanded --qualification RECORD`                    | Explicit owner-only exact-input proof and retained evidence; only selected qualified implementations execute, without directory scanning                               | Independent requested tier, not a full-regression gate; all advertised/unqualified mappings stay visible |

## Operator sequence and current verification

Complete-proof full regression `15a1f2112dad4487905100cb4a5d8615` passed on image109c14e2/source175676dc: normal frontend, all five receivers and six emulator variants passed; Mega Drive genuinely skipped absent compatible media. All83 capture digests and six reusable qualifications were independently verified. Expanded `c85e22e7deb046c58c8cce849841ee58` then replayed those six exact records successfully, with78 verified captures and all eight owned cleanups passing. Its `full_regression_gate` remains false: expanded success is not a substitute for the separate full gate. Independent target inspection confirmed all30 resource sets from the two full runs and two expanded attempts absent, no sessions/lobbies and unchanged beta configuration.

Earlier full run `9921a31c38e84c229c05776716c13c91` passed native behavior but retained lossy standalone captures that cannot authorize replay. Expanded `13c03b572dd9409d941d09a0ee1a3052` failed before emulator lease because its media reproduction used a host-only catalog default. The repaired read-only check uses the installed stock catalog and canonical mounted ROM view, then compares actual system/media identity before input. All reports remain immutable history; no validator, sanitizer, runtime image or beta profile was weakened or changed to obtain the later passes. [Current tooling](../docs/current/tooling.md) owns integrated suite/hook results; historical coverage exceptions do not authorize current application acceptance.

1. Synchronize the installed package and locked host/development dependencies with root `uv sync --locked`. Use Python 3.12.x; NixOS explicitly sets `UV_PYTHON` to its Nix-provided interpreter and `UV_PYTHON_DOWNLOADS=never`. Historical pytest 8.4.2/coverage.py 7.17.0 runs below predate this lock; current configured pins are in `pyproject.toml`.
2. Run default local-safe checks and no-effects planning. They must not contact Wolf, load native settings or launch Docker/build/native work.
3. Separately authorize builder/image checks and an explicit build. Every native session requires complete current-input provenance bound to the exact stock-verified local image, even if only host coordinator code changed.
4. Configure target/content/artifact settings, qualify idle shared-root ownership and explicitly authorize the native target and resource root.
5. Retain the report and every referenced artifact. Review the full gate, independent cleanup, actual PNGs and coverage, not merely shell exit status. Preserve failed attempts; never retry or choose another candidate to erase a failure.

### Host, builder and packaged runtime

From the repository root, after the [root environment setup](../README.md#commands):

```sh
uv sync --locked
# Defaults to tests/unit and tests/integration/local only.
uv run pytest
uv run python tests/integration/local/media_smoke.py
uv run batocera-gow-native plan --tier regression
uv run batocera-gow-native plan --tier expanded
```

No `PYTHONPATH`, adjacent requirements file or wrapper-created environment is needed. Root imports and collection do not load dotenv or validate SSH settings. Explicit native collection is also safe:

```sh
uv run pytest --collect-only tests/integration/wolf
```

The host suite uses owned temporary files, modelled transport/clock boundaries and bounded local subprocesses. SDL/ALSA/Xvfb prerequisites can cause explicit host skips; such skips do not prove a target capability. The [independent application line gate](#independent-application-line-coverage) includes the complete maintained application source. Historical spec-only coverage exceptions do not apply to this gate.

[`test_emulator_media.py`](integration/local/test_emulator_media.py) and [`test_emulator_probe_contracts.py`](integration/local/test_emulator_probe_contracts.py) launch real Python fixtures from their adjacent [`emulator_media_helpers/`](integration/local/emulator_media_helpers/) and [`emulator_probe_helpers/`](integration/local/emulator_probe_helpers/) packages. The helpers cover nested subprocesses, metadata producers, descriptor/mapping lifetimes and the interpreter-to-ELF wrapper. They work from an owned foreign working directory, retain their interpreter isolation and stay outside the final image. The [Python fixture standard](../docs/standards/python.md#executable-test-fixtures) governs source placement, checking and the distinction between executable programs and string test data.

Builder and packaged-runtime tests are not default host checks. Separately authorized examples:

```sh
sh tests/integration/runtime/run-runtime-tests.sh
tests/integration/builder/run-assembly-fixtures.sh
# Explicit build; native fixtures never invoke this for you.
uv run batocera-gow-build --working-tree
```

The mount-capable runtime fixture uses a networkless disposable builder. Its mount-only `SYS_ADMIN`/AppArmor exception is never a native application permission. Select the actual pinned archive with `GOW_STOCK_ROOT_TAR` if archive selection is ambiguous. Publication behavior belongs to local-safe pytest and grants no publication permission. Assembly fixtures exercise complete disk extraction, metadata, stock inventory and exact Docker-save/load comparison; no test installs host packages or prunes Docker storage.

`tests/integration/runtime/stock_runtime_tests.py` requires an authorized disposable exact image without content/state/source binds and tests packaged loader/library/configgen behavior, not native renderer or exit. `tests/integration/runtime/wolf_session_tests.py` requires an actual Wolf session for shared memory and negotiated display sizing. Never run destructive mount fixtures directly on the host or treat stock/GPU/session prerequisites as host-safe. See the [root build instructions](../README.md#local-image-build). The builder project interpreter is stock-aligned 3.12.8 in `/opt/batocera-gow`; Debian's OS interpreter remains untouched. Actual disposable stock Python 3.12.8 imports of Pillow 11.0.0, evdev and pyudev 0.24.3 passed during cutover provisioning. That import observation is not a new staged-runtime build or native acceptance result.

The Docker context allowlist and builder read-only mounts expose only declared source, build assets, test assets and manifests. They do not expose checkout `.env`, `.git` or caches. Private settings belong to host invocation snapshots, never builder/runtime staging.

### Full image qualification

The installed `batocera-gow-qualify` command owns one complete attempt against an already built immutable image. Set up the root locked host/dev environment first, retaining explicit `UV_PYTHON` and `UV_PYTHON_DOWNLOADS=never` on NixOS. It never installs pytest into Batocera, downloads an environment or builds an image implicitly.

Prerequisites are a successful normal current-input build with complete retained saved-image preservation provenance, its stock inventory and staged runtime, the exact local image, Docker access, and an idle authorized Wolf target with verified shared-root mapping and native capabilities. Configure the same `BATOCERA_GOW_*` native/render/content settings used by the maintained native session. `--env-file` is explicit and settings precedence remains CLI > exported environment > selected file > defaults. The file cannot authorize effects.

```sh
# Inert installed help:
uv run --frozen --no-sync batocera-gow-qualify --help
# Separately authorize this target/root and build normally before executing:
uv run --frozen --no-sync batocera-gow-qualify --env-file .env \
  --build-manifest output/gow-full-x86/build-manifest.json \
  --stock-manifest output/gow-full-x86/stock-manifest.json \
  --runtime-root output/gow-full-x86/runtime \
  --authorize-native \
  --native-authorized-target wolf-test \
  --native-authorized-root /etc/wolf
```

Replace the neutral target with the explicitly approved destination, exactly matching resolved SSH settings. `--image` may add an exact immutable ID conflict check, never a mutable-tag qualification. `--output` selects the private evidence root. Defaults select the normal build artifacts above and `output/qualification`.

The command checks canonical source/stage freshness and reuses the build's actual image-bound full preservation evidence. It then runs the configured full local-safe pytest selection with isolated fresh coverage files and calls `scripts/check_python_coverage.py` with its report, receipt and data. The complete application denominator and separate branches remain mandatory. Invalid, incomplete or lost measurement is not a numerical pass. Historical reports and native measurements are never combined into this attempt.

Packaged checks execute ordinary checked source ephemerally through stock Python in an owned exact-image networkless container, with no host-source, content, venv or development binds. They import the installed runtime and stock production dependencies, check packaged resources and run supported runtime help plus `check-runtime.sh`. No fake help masks a missing prerequisite. These checks are not GPU, client or live-session qualification.

Only after passing local and packaged checks may the maintained native session prepare/reuse the exact image once. It executes independent serial frontend, all five receivers and all seven emulator variants. Shared PSX selection, stock assertions, mounted-media eligibility, finite budgets, ownership and cleanup remain the existing service's responsibility. Permitted no-media rows retain explicit untested status, including an all-skipped matrix with no emulator exit coverage.

The new run directory and child evidence directories are mode0700; evidence files are mode0600. Retain `qualification-report.json`, `preservation-reuse.json`, `measurement/`, `packaged-check.json` and `native/<run-id>/session-report.json` with its referenced evidence. The aggregate binds source/stage/image identities, actual phase outcomes, preservation reuse, media coverage, drift and cleanup. A required failure, interruption, missing prerequisite, lost evidence or unresolved cleanup is nonzero. Later unexecuted phases remain not-run. Failed attempts are retained, without retry/fallback qualification or automatic retention cleanup.

The documented installed full invocation was exercised against newly normally built image `sha256:1709a0f90f08166bb84ff3919377e923e54bd75c9c4042e0267ddf83d43a376c`, source `62dd0aa6c3ee905969de3bb606ce84a5480ef6f01e79e57f8a3e04b9e930846f`, run `e4aedb9339b949b292548f4cfa73cceb`. It returned 0 with complete local/preservation/packaged/native phases, unchanged inputs and owned cleanup. Independent inspection verified fresh measurement hashes, 13 separate native case reports, 95 artifact hashes and all owned-container/state absences, with unchanged Wolf configuration/services. [Image-qualification evidence](../docs/current/tooling.md#installed-cutover-verification) retains final evidence. The separate ordinary pytest retry also passed; its success does not erase the earlier Atari failure. Server-side pixels and synthetic input do not prove client-decoded video, heard audio, physical-controller forwarding, gameplay, all-catalog support or universal stability.

The temporary startup-cause recorder, private relay and diagnostic-only native CLI switch are removed, together with their diagnostic-only tests. Permanent frontend capture, fixed startup observations, status/privacy and owned-cleanup checks remain. The consumed additional diagnostic attempt established no cause or repair. Ordinary pytest run `c48ba29e303349fab4fa2a17568d9357` failed Atari and remains failed. The user's one authorized unchanged complete retry, `898ec2b58225421e9f695a6ffe1eb29b`, passed 12 tests with one no-media skip in 280.14 seconds. Atari exited unforced after native Guide+Start, with launcher code zero. It selected different media from the failed attempt, so this is not exact failed-selection reproduction or a causal fix. [Cutover evidence](../docs/current/tooling.md#installed-cutover-verification) retains both outcomes.

#### Bounded installed-command proof

The qualifier worker's final serial focused invocation passed 71 tests in 14.46 seconds with outer `--no-cov`, after the measurement-resource snapshot handoff. It selected `test_image_qualification.py`, `test_build_boundaries.py` and `test_native_preparation.py` under `tests/integration/local/`, through uv frozen/no-sync with the supplied Nix Python 3.12.12 and downloads disabled. A frozen/offline project-local reinstall supplied the actual console entry point; installed help exited 0 and missing native authorization exited 1. Scoped Ruff/formatting and strict mypy passed over the six changed Python files.

The local proof runs real full configured tiny-project pytest/canonical coverage consumers, not the root complete-source measurement or stock/native environments. It covers intended-phase barriers, stale/conflicting provenance, private measurement isolation, real owned child/setsid-grandchild interruption/timeout, foreign and unresolved late-created container state, native cleanup and honest all-no-media outcomes through maintained services. Private normalized evidence at `output/modernization-qualification-command-SiAEavpG/verification.json` retains the earlier console-import exit 4/zero collection and 67-pass/4-fail discovery result as well as the corrected 71-case pass. The internal private-directory option uses `--coverage-evidence-dir=DIR`; attaching an existing external directory avoids pytest's pre-conftest false positional discovery without selecting a test subset. Full normal-image/build/native, complete root measurement, all-files and final review remain coordinator-owned and unrun by this worker.

### Independent application line coverage

Keep the Nix interpreter selection exported for every uv invocation on NixOS.
Without `UV_PYTHON`, the stock-aligned `.python-version` can make uv replace the
host environment with a managed interpreter. `UV_PYTHON_DOWNLOADS=never` prevents
an implicit download but does not select the supplied Nix interpreter.

After root environment setup, the ordinary local-safe measurement and independent
gate are:

```sh
uv sync --locked
uv run --frozen --no-sync pytest
uv run --frozen --no-sync python scripts/check_python_coverage.py
```

Pytest measures every Python module under `src/batocera_gow/`, including
unimported builder, runtime, remote-payload and native-coordinator source.
Coverage.py's subprocess patch also measures local child interpreters using the
same development environment. It does not install tools into stock Batocera,
alter the final runtime, contact Wolf or authorize optional integration effects.
The application denominator excludes tests and repository tooling, not difficult
application modules. No executable-line exclusions are configured.

`coverage.json` reports lines and branches. The separate gate reads actual line
counts and requires at least 80%, independently of Coverage.py's combined
line/branch percentage. There is no branch floor. A below-floor measurement exits
one; absent, invalid, stale or incomplete evidence exits two, including overflowing
integer percentage metadata or thresholds. Empty application source and a tool-only
test run cannot establish application success.

The root pytest adapter removes the previous `coverage-run.json` receipt before
collection. Only a successful nonempty execution can publish a replacement tied
to exact source/test/tool/configuration hashes and exact `.coverage` and JSON
bytes. Collection-only, failed tests, `--cov-append`, changed inputs, overwritten
reports and preexisting data do not pass freshness. The checker independently
reconciles every module's executable lines against current source and rejects
missing or foreign files, impossible counts and disabled branch reporting. Its
source analyzer keeps data in memory, leaving measured data, JSON and receipt
bytes unchanged so repeated gate invocations remain valid. Receipts detect
accidental stale evidence, not hostile forgery by someone able to rewrite both
files.
The input identity includes this README and other files under `tests/`, not only
Python modules. Finish test-document formatting before the fresh measurement;
editing those files afterward invalidates its receipt.

The schema2 receipt retains the fixed invocation role `pytest`, collected count,
input/report/data hashes and actual combination counts, not raw argv or private
paths. The adapter audits every candidate fragment before real combination and
reconciles its complete mapped file/line/arc/context contribution afterward.
Unreadable or malformed fragments, unfinished combination and late remaining
shards are nonpassing even when the numeric JSON exceeds the floor. Keep test
selection/scope in the separate sanitized invocation evidence; the fixed role
does not by itself establish a full-suite run. `--no-cov` can accelerate an
isolated diagnostic but cannot supply valid coverage acceptance.
For a fresh private measurement, choose an owner-only absolute evidence directory
and pair `COVERAGE_FILE=DIR/.coverage` with
`--coverage-evidence-dir=DIR --cov-report=json:DIR/coverage.json`.
Use the attached custom-option value: a separated existing directory outside the
checkout can affect pytest discovery before the root option is registered.
The independent checker accepts matching `--report`, `--receipt` and `--data`
paths; the qualifier calls that canonical interface without interpreting warnings
or substituting a numeric-only pass. Default root paths remain unchanged.
Do not manually replace the JSON or combine historical/native data into a local
receipt. Any deliberately combined environment report needs separately retained
successful contributing runs, current source identities and reviewed path mapping;
no such combined-environment acceptance is claimed here. Actual stock-library,
image-preservation and final native acceptance remain independent even when the
line floor passes.

Local boundary tests use owned temporary files, sockets, descriptors, child
processes, archives and synthetic external-service transcripts. Development-only
Pillow 11.0.0 supplies real PNG parsing for blank/content-render refusal cases.
These tests exercise maintained decisions, privacy and ownership cleanup. They
do not qualify stock libraries, GPU output, native input or the final runtime.
Neither this dependency nor the coverage tools are staged into Batocera.
Forcibly terminated standard-library-only descriptor/mmap producers and the
synthetic Docker transcript start Python with `-S`, so interrupted site hooks
cannot leave partial, unrelated coverage databases. Application payloads and SSH
adapters retain normal instrumentation; no application source is excluded.
Use a short system temporary root such as `/tmp` for local socket fixtures;
deep checkout-relative `TMPDIR` paths can exceed the kernel's Unix-socket limit.

The earlier warning-bearing measurement and unidentified empty historical fragment
are not accepted evidence. Ticket02 now retains an actual valid complete private
full local measurement and a passing independent complete-source line gate, with
all contributing fragments audited. No historical or native measurements were
merged. [Coverage evidence](../docs/current/tooling.md#installed-cutover-verification)
owns its report, counts and hashes. That result is bound to its measured inputs,
not proof of the later recorder-removal changes. Current dependencies are
Coverage.py 7.17.0, pytest 9.1.1 and pytest-cov 7.1.0. [Current verification evidence](../docs/current/tooling.md#installed-cutover-verification)
owns fresh final measurement and integration attribution after these edits.

### Installed cutover local verification

The cutover exercised all five installed entry points' help and native regression/expanded planning from a foreign working directory in the one disposable independent checkout under `output/modernization-verification-checkout`. Its noneditable installation uses copied actual declared inputs and private fixture-only Git metadata, not the original checkout's metadata or an original Batocera source tree. Media subprocess smoke covers catalog, ignored-dotenv, absence, private selection/reproduction, overwrite and changed-input refusal. Explicit Wolf collection finds 13 scenarios. Selecting a native case without `--authorize-native` fails before settings or transport. Installed owned-path, ancestor/outside/symlink, remote-root, settings, stdlib-payload and freshness consumers are exercised separately from remote effects.

The networkless declared-input builder runs installed assembly/inventory with stock-aligned Python 3.12.8; Debian's `/usr/bin/python3` remains 3.13.5. Host dotenv/tomlkit/dependency-injector and pytest are absent from the application environment. A separate builder-test environment supplies fixture prerequisites. Real GPT/FAT/ext4/zstd assembly exercises both roots, FAT/SHARE, metadata/ACL/xattr/hardlinks, unsafe-input refusals and exact Docker-load/save layer comparison. Mount-capable runtime fixtures separately exercise actual stock population, state/process ownership, frontend lifecycle and libasound configuration without network, host state or the daemon socket.

Stock-image probes use unchanged stock Python, Pillow, evdev and pyudev for staged startup/input/probe imports. Packaged executable resource modes, launcher help, prerequisite checks and root-owned nonwritable ACL-free additions are checked separately. SDL privilege-drop and Wine transitive-loader/link checks do not qualify unavailable NVIDIA hardware or injected-driver discovery. Neither host models nor fixture-only mount privileges replace these stock checks or become application permissions.

Current recorder-free verification built the normal exact image above, preserved 112,729 stock paths plus 21,813 isolated additions before promotion, and passed matching-source networkless assembly/archive/load/save fixtures and 84 mounted-runtime tests. Builder project Python is 3.12.8; Debian Python remains 3.13.5. The refreshed noneditable wheel proof verified 56 installed member hashes and exercised installed commands outside the checkout without remote effects. Fresh complete local measurement passed the canonical line gate at 9,885/12,236 lines, 80.78620464203988%, across 53 modules with zero exclusions; branches remained separately 2,891/3,780. Each contributing fragment and all three measurement hashes were checked. The full installed qualifier and subsequent complete native pytest retry passed all eligible variants, with Mega Drive explicitly untested. Independent retry checks verified 13 reports, 95 artifact hashes, all owned-container/state absences and unchanged Wolf configuration/services. Prior failed attempts retain their results and unknown causes. [Current verification evidence](../docs/current/tooling.md#installed-cutover-verification) retains receipts, scope and final-check attribution.

Local transport models exercise full aggregation, independent PSX renderer selection reuse, uncertain allocation recovery, contention, evidence failures and cleanup reservations. Actual subprocess consumers prove snapshot-selected Docker survives ambient/file changes. The delivered stdlib archive exercises activation and restart-failure metadata preservation without host parsers. These are local ownership and boundary results, not proof of native image transfer, display/input or remote cleanup.

[Current verification evidence](../docs/current/tooling.md#installed-cutover-verification) records exact commands, source/image/builder identities, relocated consumer results, fixture outcomes, image-bound native outcomes and current integration disposition. Earlier measurements remain point-in-time records and become stale after maintained input changes. Only a successful explicit build's full saved-image inventory can qualify its candidate for native setup. Publication, deployment, registration and Wolf restart are not consequences of verification. Server-side pixels and synthetic input do not qualify client video, heard audio or physical-controller forwarding. RPCS3/Xenia and unselected mappings remain unqualified.

### Opt-in pytest preparation and freshness

Build separately with `uv run batocera-gow-build --working-tree`, or use an authorized clean committed build. Session preparation uses the shared canonical fingerprint over `src/`, `build-assets/`, `tests/assets/`, `pyproject.toml`, `uv.lock`, `.python-version`, `.dockerignore` and `LICENSE`, including contents and relevant modes. It compares build-manifest `declared_inputs` and staged `runtime_inputs`, stock verification and exact local immutable image identity before any remote activity. Missing, invalid, incomplete or stale evidence is a nonpassing setup error with an explicit-build instruction, never a skip, automatic rebuild, provenance repair or fallback. Old manifests cannot be relabeled. Generated output, caches and unrelated documentation do not supply input identity.

Native pytest resolves `HostSettings` once after authorization. Explicit CLI settings override exported environment, then the selected file, then defaults. `--native-env-file` deliberately selects a file; absent it there is no discovery. Missing/unreadable selected files and invalid supplied values fail without exposing private values. Resolution preserves `os.environ` and remains fixed for that session. Settings do not grant target/resource permission.

Supply SSH and ROM/BIOS settings above plus `BATOCERA_GOW_BUILD_MANIFEST`, `BATOCERA_GOW_STOCK_MANIFEST`, `BATOCERA_GOW_RUNTIME_ROOT`, `BATOCERA_GOW_RENDER_NODE`, `BATOCERA_GOW_VIDEO_CAPS`, `BATOCERA_GOW_HOST_ROOT` and `BATOCERA_GOW_LOCAL_ROOT`. Paths to manifests/runtime staging name local build outputs; content roots name Docker-host sources. Optional overrides are `BATOCERA_GOW_WOLF_CONTAINER`, `BATOCERA_GOW_API_SOCKET`, `BATOCERA_GOW_PROFILE`, `BATOCERA_GOW_UID`, `BATOCERA_GOW_GID` and `BATOCERA_GOW_INFRASTRUCTURE_CONTAINERS`, the latter a space-separated list of inspected complete immutable IDs. Render/caps and root mappings need actual target qualification, not copied defaults.

Example authorized invocation, not exercised post-cutover evidence:

```sh
uv run pytest tests/integration/wolf/test_native_scenarios.py \
  --authorize-native \
  --native-authorized-target wolf-test \
  --native-authorized-root /srv/wolf-state \
  --native-env-file .env \
  --native-project-root "$PWD"
```

The target and root arguments must exactly match the resolved settings and the separately authorized resources. Selecting a path alone fails closed without this opt-in. For exported-environment-only use, omit `--native-env-file`. No private `.env` modification is required.

The same file exposes `::test_frontend`, `::test_receiver` with five independent receiver parameters and `::test_backend` with seven variants grouped into six backend rows. Append a node selector or `-k` to select a subset after retaining the same authorization arguments. A subset is not full migration acceptance. Native worker parallelism is refused; run serially.

After local freshness succeeds, preparation applies target capability, idle/unknown and ownership checks, then reuses the exact verified remote image or performs one bounded upload/load. The complete save, hash, upload and load sequence has a 900-second deadline. Saving and loading each have a separate ceiling of 300 seconds, also limited by the remaining whole-transfer time. Final independent idle discovery consumes that remaining time before load dispatch. Exhausted allowance refuses dispatch; a response at or beyond either load deadline cannot pass preparation. The parent gzip-compresses the configured Docker save command's exact stdout at level1 without rewriting the Docker-save tar or its layer. Raw and compressed archives are independently bounded at 32 GiB. The checked target loader accepts that gzip archive and verifies transfer integrity and the loaded immutable identity. Compression does not guarantee completion within either deadline.

The parent exclusively creates the caller-owned mode0600 archive under a private temporary directory, including when the Docker prefix uses sudo. Existing destination files are never truncated. The session owns partial-file cleanup. Preparation does not pull registry images, prune shared images/caches or grant persistent deployment permissions. Independent cases own disposable lobbies, homes and input resources; cleanup registration covers partial setup, evidence and teardown failure. Unresolved cleanup or contention stops subsequent cases. Input identity is rechecked before launch and at completion; drift prevents a passing current-checkout claim.

Transfer requests have a shared finite 64-MiB raw chunk limit, with base64 expansion to about85.3MiB plus request/process overhead. The host must have capacity for that bounded per-call memory. Each chunk and the final load still require a fresh idle/identity check; larger chunks do not extend the whole-transfer deadline or suppress contention. A failed or timed-out preparation is nonpassing even if owned cleanup succeeds and no native case has started.

Keep the aggregate `output/integration/<session-id>/session-report.json` and referenced per-case evidence. Pytest item results cannot override aggregate provenance, evidence, interruption or cleanup failures. `Skipped: no compatible mounted media` is explicitly untested, never a passing backend/native-device observation. All six rows may skip while frontend and receivers pass, but the report must still say no emulator exit coverage. Permission/mount failures, missing firmware for eligible media and actual failed attempts remain blocking.

### Full six-row native regression

First export only deliberate operator settings, for example by reviewing and explicitly sourcing an ignored `.env`:

```sh
set -a
. ./.env
set +a
uv run batocera-gow-media mounts
```

Required settings are `BATOCERA_GOW_SSH_TARGET`, `BATOCERA_GOW_ROMS_ROOT` and `BATOCERA_GOW_BIOS_ROOT`; optional `BATOCERA_GOW_SSH_IDENTITY_FILE` is a pathname, never key contents. [example.env](../example.env) has neutral examples. The content roots name Docker-host sources, not coordinator-local search paths. Their fixed native destinations are `/home/retro/userdata/roms:ro` and `/home/retro/userdata/bios:ro`. The complete effective bind observation must match before input; neither environment text nor desired TOML proves mounting.

After separately qualifying the installed target and authorizing its ephemeral native effects, use the following CLI example. Export `BATOCERA_GOW_HOST_ROOT` as the exact authorized Docker-host shared-state root first; add `--local-root` for a distinct qualified Wolf-local root. The authorization flags acknowledge that exact target/root, not merely whatever happens to be in an unreviewed file. CLI examples below use exported settings; `batocera-gow-native --env-file .env run ...` instead selects a file explicitly, while still requiring exact authorization arguments.

```sh
uv run batocera-gow-native run \
  --authorize-native --native-authorized-target "$BATOCERA_GOW_SSH_TARGET" \
  --native-authorized-root "$BATOCERA_GOW_HOST_ROOT" --host-root "$BATOCERA_GOW_HOST_ROOT" --tier regression \
  --build-manifest output/gow-full-x86/build-manifest.json \
  --stock-manifest output/gow-full-x86/stock-manifest.json \
  --render-node /dev/dri/renderD128 \
  --video-caps 'video/x-raw(memory:CUDAMemory)'
```

Those render-node/caps values describe the historically qualified NVIDIA target, not a portable default. Do not force `format=NV12`: that failed before probe startup on this pipeline. Historical verified image `sha256:109c14e2c097e3b53d8feef6afb65dfddae09c2e3cb3b7f5f3ce4423a7c76e9c`, packaged source `worktree-sha256:175676dc4cbb761031dd423ee41c88e22dfeccf63d008884cea44cefc37e768e`, remains old-layout evidence only. Installed-layout freshness rejects it as evidence for changed current inputs; rebuild explicitly and retain the resulting exact provenance before native execution.

Regression runs these independent owners sequentially:

| Backend row                           | Required executed variants or actual no-media dispositions                 |
| ------------------------------------- | -------------------------------------------------------------------------- |
| NES / libretro / fceumm               | `nes-fceumm`                                                               |
| SNES / libretro / snes9x              | `snes-snes9x`                                                              |
| Mega Drive / libretro / genesisplusgx | `megadrive-genesisplusgx`                                                  |
| Atari 2600 / libretro / stella        | `atari2600-stella`                                                         |
| PS1 / duckstation / duckstation       | `psx-duckstation` OpenGL and `psx-duckstation-vulkan`, separately required |
| Xbox / xemu / xemu                    | `xbox-xemu`                                                                |

Normal frontend plus ready transport and all five receiver assertions precede those seven emulator variants. Each has its own native lobby/home, inspected identity, input lease, finite scenario/evidence/cleanup deadlines and absence barrier. Behavioral failure remains failed even if safe cleanup permits later independent cases. Unsafe cleanup, uncertain startup ownership or discovery interruption stops later allocations and preserves all remaining `not-run` rows. There are no native assertion retries, backend fallbacks or automatic library substitutions.

For reproducibility, append repeated `--case-selection CASE=RECORD` arguments to the same full command, pointing only to exact private records already retained under owned run directories. For example:

```sh
# These variables must name existing operator-selected private records.
# Append these arguments to the complete regression invocation above:
--case-selection "nes-fceumm=$NES_SELECTION"
--case-selection "snes-snes9x=$SNES_SELECTION"
--case-selection "atari2600-stella=$ATARI_SELECTION"
--case-selection "psx-duckstation=$PSX_SELECTION"
--case-selection "xbox-xemu=$XBOX_SELECTION"
```

The same PSX record supplies both renderer variants; conflicting GL/Vulkan records are refused. Without a supplied record, a case selects once from the actual mounted stock folder. A newly selected GL record is retained and reused for Vulkan, not rerolled. Do not invent a Mega Drive record when the actual mounted folder has no compatible input. `--reproduce-selection RECORD` remains the single-emulator smoke option, not an ambiguous full-matrix input.

### Expanded exact-input selection

A successful validated emulator case writes `<case>-qualification.json` beside `report.json`, selected media record, sanitized diagnostics and real captures, with private modes, only when the whole requested run passes evidence and owned cleanup. It records the report SHA-256, actual image/source/catalog/backend/renderer/media/profile/assertion/firmware identities and observations derived from the validated final probe. Native-device consumption means the actual backend-specific observation, RetroArch devices for libretro and observed SDL/SDL3 consumption for DuckStation/xemu. A no-media case generates no qualification. A behavior pass with incomplete cleanup or a failed neighboring case remains diagnostic, not reusable qualification or qualified advertised coverage.

The final `<case>-emulator-probe.json` capture is a complete selected proof, not an arbitrary raw process report. It retains the sanitized probe plus only fixed schema-selected native consumer observations needed by the DuckStation/xemu validators: a hexadecimal SDL GUID, boolean mapping-consumption observation, fixed stock config directory and the backend's fixed HIDAPI or numeric-locale value. Values come from the actual final probe; invalid values are omitted and cannot pass replay. Arbitrary environment keys/values, argv, wrapper data and sensitive log lines remain excluded. The public/report-row summary still drops every `environment` field.

Use explicit proof paths, never scan private directories:

```sh
uv run batocera-gow-native run \
  --authorize-native --native-authorized-target "$BATOCERA_GOW_SSH_TARGET" \
  --native-authorized-root "$BATOCERA_GOW_HOST_ROOT" --host-root "$BATOCERA_GOW_HOST_ROOT" --tier expanded \
  --qualification "$PSX_OPENGL_QUALIFICATION" \
  --qualification "$PSX_VULKAN_QUALIFICATION" \
  --build-manifest output/gow-full-x86/build-manifest.json \
  --stock-manifest output/gow-full-x86/stock-manifest.json \
  --render-node /dev/dri/renderD128 \
  --video-caps 'video/x-raw(memory:CUDAMemory)'
```

The variables identify specific existing `<case>-qualification.json` files. By default all supplied current qualified implementations execute; repeat `--case CASE` to select a subset. Requested definitions lacking proof remain visible nonblocking gaps and are not executed. A malformed, duplicate, stale or incomplete supplied proof is an error, not a silent qualification skip. Expanded `plan` exposes inventory/requested selection but does not validate proof or promise emulator execution.

Before any SSH, the coordinator verifies current image/source, complete selected stock inventory, the referenced successful report, each retained artifact hash and authentic PNG structure. It loads only the exact `<case>-emulator-probe.json` named in that case's capture map, requires its sanitized form to equal the persisted case summary, then applies the unchanged native validator and derives exact identity from the complete selected proof. Missing/corrupt captures, raw/summary disagreement, stale identity and legacy standalone captures missing selected consumer environment refuse replay. No directory search, inferred environment, fallback or historical artifact rewrite repairs missing evidence. Before the emulator's lease, read-only owned inspection revalidates the exact mounted media set, suite profile and firmware against that proof. The native probe checks its selection again; mismatches fail without replacement input and post-run identities must still match. Library changes outside the container can race those checks, so keep authorized backing inputs unchanged throughout a run. Read-only exec remains inspection only; emulator/frontend/probe commands run through normal native Wolf startup.

The pre-lease read-only helper runs as the inspected app UID under isolated Python, explicitly restores `/opt/gow-full-x86` for packaged module imports and calls the existing `mounted_media.read_selection` with `/usr/share/emulationstation/es_systems.cfg`. The unchanged catalog loader enforces the pristine stock SHA-256 pin. The reader uses the canonical inspected mount destination `/home/retro/userdata/roms`, retaining no-follow path-component checks even when `/userdata` is a symlink. Both the reproduced selection digest and system must match the retained qualification, so replacing the app-owned record with a self-consistent different selection cannot authorize input. Fixed suite-template/definition and firmware checks still run before the coordinator may issue its lease. Missing or changed inputs return a nonmatch; no host-layout catalog asset, replacement media, firmware fallback or alternate launch path is used.

Qualification files are published before the immutable final report. A publication failure fails the returned gate and removes qualified claims from its advertised coverage. Any partial proof files lack a matching successful report and are rejected by expanded selection; neither a status flag nor a partial publication is reusable proof. Existing artifacts and historical reports are never overwritten to repair a failed run.

Every matrix report includes all 253 advertised systems/categories and 477 backend mappings, independent of which definitions execute. Public case templates remain `unqualified` with null identity; rights research never grants native qualification. RPCS3, Xenia and Xenia Canary remain named nonblocking gaps with fixture/firmware/backend-route caveats. No generic native scenario for them is implemented by this ticket, and a proof for one backend never authorizes another.

### Reading and retaining the baseline

The owner-only `output/integration/<run-id>/report.json` is the old-layout modernization input. `layout`, exact image/source/stock/catalog, requested tier, case/receiver dispositions, six-row `regression_matrix`, assertion expectations/observations, phase timings/deadlines, ownership/isolation, transferred capture hashes, cleanup results and complete advertised `coverage` remain machine-readable. Keep the adjacent selected-run qualifications and every referenced artifact with it. Later installed-layout modernization must repeat the actual gate on its own changed source/image.

`counts` counts nine requested component cases in a full run: frontend, receivers and seven emulator variants. `backend_counts` counts six grouped rows; `receiver_checks` retains five independent assertions. `passed` never includes `skipped-no-media`. Missing/duplicate rows, blocked/not-run cases, failed eligible inputs, evidence loss, interruption and incomplete cleanup cannot pass `full_regression_gate`. A single behavior pass cannot override run-level evidence or cleanup failure. All six backend rows can legitimately skip while frontend/receivers pass; this still says **No emulator exit coverage**, with no inferred native-device consumption.

Exit 0 means the requested tier passed its eligibility/behavior/evidence/cleanup gate; exit 1 is a nonpassing run; exit 2 is an invalid/missing prerequisite. Smoke and expanded never set `full_regression_gate`, even when every executed case passes. Visual review of server-side real PNGs is optional. Those captures do not establish physical Moonlight forwarding, decoded client video, heard client audio, gameplay, graceful shutdown, save persistence or frontend recovery. Logs' natural-exit classifications and post-exit frontend are not emulator acceptance conditions.

Preserve the [cleanup/recovery and privacy rules](#lifecycle-evidence-and-recovery) below. Never publish private media names, paths, identities, firmware bytes, raw logs, screenshots or credentials. Local ignored output is not publication permission. Removal is explicit and limited to the reviewed exact local run directory, after retaining needed baseline evidence; remote retained state requires independently proven ownership/absence and resolved startup, not a prefix-based deletion or restart.

From the repository root, the new deterministic tests are:

```sh
uv run pytest \
  tests/integration/local/test_media_catalog.py \
  tests/integration/local/test_mounted_media.py \
  tests/integration/local/test_media_qualification.py
uv run python tests/integration/local/media_smoke.py
```

Before the X11-boundary repair, coordinator host verification observed **480 tests, 2 skipped**, including version parsing and bounded incomplete-evidence regressions. Host SDL shared-library and ALSA-config prerequisites were unavailable; neither skip is native qualification. Actual configured hooks passed every generated file across tickets01–03, including untracked additions, without suppression. Mandatory all-files hooks reported user-waived failures in pre-existing files only: 50 Ruff findings, 1,682 mypy errors in 29 files and four Statix W04 warnings; all formatters passed. Maintained local media CLI smoke and NES planning passed without native effects. These historical results precede the later X11 source/tests and do not verify them. Initial host failures and their fixture corrections remain in ticket03. No worker check or TDD red/green execution is claimed. The separate host coverage measurement and its below-policy result are recorded in [current tooling](../docs/current/tooling.md#current-configuration); it is not combined native coverage. Synthetic local bytes are not ROM qualification.

The focused Desktop regressions use real Xlib requests against a fresh Xvfb server selected by `-displayfd`. Each server requires a private random MIT cookie, disables TCP, and is reaped by its owning fixture; the tests never connect to a user display. Subprocesses contain Xlib's fatal default handler and have finite deadlines. They exercise valid/missing/malformed properties, destroyed active windows, exact-request versus foreign-display/other-request errors, previous-handler restoration and cookie rejection. Only the constructor's library/connection target is adapted. Native non-root, `DISPLAY=:0` and authentication guards are unchanged.

The coordinator has executed all seven actual-X11 regressions without prerequisite skips. They skip if non-root execution, Xvfb or loadable host libX11 is unavailable. On hosts without a loader-visible libX11, supply the actual host library through `GOW_TEST_LIBX11`, never a personal store path in maintained code:

```sh
GOW_TEST_LIBX11="$HOST_LIBX11" \
  uv run pytest tests/integration/local/test_native_desktop.py
```

Here `HOST_LIBX11` is an explicitly discovered loadable host library, not the packaged target library. A provided but unloadable override fails rather than skips. Host-X11 success qualifies only the observation boundary; it cannot supply native emulator exit or stock launcher completion.

Before the classification-evidence tranche, the scoped X11 repair and callback-typing correction passed the complete coordinator host suite with **487 tests, 2 skipped** in 41.26 seconds. All seven real-X11 cases executed with the discovered host library, and the previously fatal destroyed-window smoke survived with unavailable observation. Every generated file passed actual configured hooks without suppression. Mandatory all-files hooks retained 50 Ruff findings, 1,682 mypy errors in 29 pre-existing files and four Statix W04 warnings under the recorded inherited-file-only waiver, with formatters passing. Maintained local media smoke and no-effects NES planning passed. These historical results do not verify the later classification diagnostics, establish the earlier native cause or supply native exit evidence. Controls and fresh frontend/receivers were still pending at that point; the later independent frontend/receiver pass is recorded below.

## Maintained native frontend and receivers

The executable host entry point is `batocera-gow-native`, backed by `batocera_gow.host.native_integration`. It delivers maintained stdlib remote source in an ephemeral isolated Python payload with bytecode writes disabled and no persistent installation. Host logic tests exercise injected transport/clock observations, real filesystem ownership, atomic report publication, isolated delivered helpers and bounded subprocess termination. Synthetic observations and fixture PNGs are not native evidence.

Run the new host tests and target-independent planning smoke from the repository root:

```sh
uv run pytest \
  tests/integration/local/test_native_state.py \
  tests/integration/local/test_native_roots.py \
  tests/integration/local/test_native_integration.py
uv run batocera-gow-native plan
uv run batocera-gow-native plan \
  --tier frontend-smoke
```

Final coordinator verification passed **352 tests, 1 skipped**, and every generated native file passed actual configured hooks. Maintained integrated run `089d0208a63e4836a817eb3750c9d8b5` passed normal ES, all five receiver assertions, matching real captures and both owned cleanup barriers in 25.86 seconds. Separate frontend smoke `b50a82140f6b41c8a735cccd7a95a8ec` and receiver smoke `7b1501a4bd7a4efdb542a5915fe73d3f` also passed; actual captures were visually inspected. Unclassified-activity control `5899dbb238b642488209fba9c303c3d8` refused after only preflight/snapshot, with no native allocation/create/lease. Earlier integrated runs `7d0422b5c2794949a3404062b8db4dee` and `97fcfe755fe642eda7cecc89fe02388b` remain failed at receiver startup without a receiver lease; both passed owned absence/state removal. Their cause is unknown. Bounded missing-startup observations are now exercised, but their added latency may hide that timing-sensitive failure. The later pass proves the maintained path's observed result, not causal repair or universal reliability. No emulator or physical Moonlight acceptance is implied.

### Explicit opt-in and prerequisites

For native operation, deliberately supply `BATOCERA_GOW_SSH_TARGET` as an OpenSSH alias, hostname or IP target. Existing SSH agent/config is the default; optional `BATOCERA_GOW_SSH_IDENTITY_FILE` is only a pathname. The installed CLI accepts an explicitly selected host dotenv file; it never discovers one, uses personal fallback targets, reads key contents or disables batch/host-key protections. Supply the two shared Docker-host content roots below. Authorized external content aliases resolve on the remote Docker host for effective bind/overlap comparison; owned state never permits symlinked roots or parents.

The operator must separately authorize ephemeral native lobbies, disposable shared state, synthetic server input and bounded owned cleanup. CLI `--authorize-native` plus exact target/root acknowledgments permit case effects; its direct coordinator path requires the exact image already loaded. The [opt-in pytest preparation interface](#opt-in-pytest-preparation-and-freshness) additionally permits bounded upload/load of the verified local image. Neither authorizes builds, registry pull/publication, persistent app registration/configuration, restart, pruning, host installation or production-userdata changes.

The current adapter qualifies only installed Wolf revision `ee271038da2b81c9e54c28c9daa7558692d415d6`. Its `HOST_APPS_STATE_FOLDER` is the Wolf-local root; Docker's effective bind supplies the distinct host root. Both default to `/etc/wolf` in the CLI but must pass backing device/inode checks, protection overlap checks and ownership checks. Runtime socket backing, native device rules, existing profile and exact local image are discovered read-only. Every active container other than Wolf is a refusal unless explicitly identified as non-app infrastructure by its complete immutable Docker ID. An exemption never permits a native-looking app or active API session/lobby.

Use the current approved build outputs and source-qualified installed render node/caps. Read-only qualification observed `WOLF_USE_ZERO_COPY=TRUE` and startup logs selecting `h264` encoder `nvcodec` and the zero-copy NVIDIA pipeline on `/dev/dri/renderD128`. Pinned Wolf [configTOML.cpp](https://github.com/games-on-whales/wolf/blob/ee271038da2b81c9e54c28c9daa7558692d415d6/src/moonlight-server/state/configTOML.cpp) selects `video/x-raw(memory:CUDAMemory)` for that pipeline. This qualifies the explicit caps selection, not the new runner's native acceptance:

```sh
uv run batocera-gow-native run \
  --authorize-native --native-authorized-target "$BATOCERA_GOW_SSH_TARGET" \
  --native-authorized-root "$BATOCERA_GOW_HOST_ROOT" --host-root "$BATOCERA_GOW_HOST_ROOT" --tier frontend-smoke \
  --build-manifest output/gow-full-x86/build-manifest.json \
  --stock-manifest output/gow-full-x86/stock-manifest.json \
  --render-node /dev/dri/renderD128 \
  --video-caps 'video/x-raw(memory:CUDAMemory)'
```

`--video-caps` explicitly supplies the installed API's `video_producer_buffer_caps`. It has no environment-derived default; another installed pipeline requires its own observed source qualification and explicit value. Supply repeated `--infrastructure-container <complete-64-hex-id>` only for inspected non-app infrastructure. Other explicit overrides are `--wolf-container`, `--api-socket`, `--host-root`, `--local-root`, `--profile`, `--uid`, `--gid` and `--output`; they do not register or modify the selected profile.

Keep producer caps distinct from an encoder's output format. On the qualified target, adding `format=NV12` to `video_producer_buffer_caps` reproduces pre-probe startup failure, including in the existing NES control. The same immutable image, Wolf instance, NES selection and budgets pass with `video/x-raw(memory:CUDAMemory)`. Do not force NV12 here to select an emulator renderer or encoder format. Other installed pipelines still require their own qualification.

After a separately qualified smoke, the full frontend/receiver invocation is the same command with `--tier frontend-receivers`. `--tier receiver-smoke` runs only the five stock receiver assertions. Neither smoke sets `full_frontend_receiver_gate`. NES has its separate explicit tier below and cannot satisfy that frontend/receiver gate or the six-backend gate. Exit status is 0 only for the requested tier's behavior/evidence/cleanup disposition; 1 is a nonpassing native run and 2 is invalid/missing prerequisites. The NES tier additionally allows an explicit no-media skip, never passing exit coverage. Busy/unknown preflight has no native write or input effects.

### Lifecycle, evidence and recovery

The runner exclusively allocates relative `test-runs/<suite-id>-<case>` homes below the proven shared root. A root-owned marker and pinned root, parent, home, control and evidence identities authorize only that allocation. Native Wolf supplies the automatic home/udev binds; content remains read-only and no source mount or manual home bind is added. Before a renewable input lease, effective inspection checks the immutable image, packaged supervisor/default frontend ancestry, app UID/GID and zero app capabilities, private PID/IPC/bridge networking, default seccomp, 2 GiB shared memory, approved capabilities/devices, userdata link, mounts, source/stock hashes, root ownership, modes and ACLs. Native-uinput qualification requires live actors approved by the transport's application ProcessTree, valid ancestry to the packaged runtime session under PID1 and observed read/write permission. The separate XTEST worker needs no uinput permission, but still must have the confined app credentials. Actor PID, parent, start ticks and application-root evidence are retained and required by the host gate. The only `docker exec` is fixed read-only inspection, never probe/emulator launch.

The frontend keeps its normal command and adds an owned app-UID observer. Readiness requires the active approved ES window, capability-free identity, live ES/final-source pidfds, ready worker/final source and a regular app-owned private `/tmp/emulationstation.ready`. At pinned ES revision `2c29a330e487210a7d51ad2650bb7b280ea44c86`, [main.cpp](https://github.com/batocera-linux/batocera-emulationstation/blob/2c29a330e487210a7d51ad2650bb7b280ea44c86/es-app/src/main.cpp) calls `setReadyFlag()` after preload/input/start-view setup and splash closure; [ApiSystem.cpp](https://github.com/batocera-linux/batocera-emulationstation/blob/2c29a330e487210a7d51ad2650bb7b280ea44c86/es-app/src/ApiSystem.cpp) creates that flag. A process, splash or arbitrary image alone cannot pass.

The receiver command is the packaged `transport_probe.py` in a separate native lobby. It reports these distinct real assertions, without assertion/create retries:

1. `stock_combo_exit_held_and_pointer_reset`
2. `stock_context_pointer_button`
3. `context_switch_without_semantic_leakage`
4. `held_graceful_source_removal_and_recreation`
5. `stock_command_once_per_stock_release`

Stock hotkeygen may serialize an event alias, for example `BTN_LEFT` as `BTN_MOUSE`. Initial context pinning compares their actual stock evdev codes while retaining exact context/action names, ordered chords, scalar/list distinctions and non-key command bytes. Once pinned, ownership requires the exact written inode and bytes; alias acceptance does not permit later edits or replacement. The isolated stock context regression uses the actual CLI and a fixture-owned PID/context without a daemon or input device. It does not replace the complete native receiver gate.

New unrelated activity or failed discovery interrupts the run, stops later leases/cases and attempts only identity-revalidated owned cleanup. The shared-kernel discovery-to-input race is not atomic reservation. Lease expiry/revocation makes probe input fail closed; releasing held input remains allowed. Graceful source removal is not abrupt crash recovery.

Snapshots inspect every listed container, including stopped and paused foreign state. A bulk inspect may lose only the current case's previously independently bound complete Docker ID to automatic removal. Reconciliation requires exit1 with solely that exact missing-object error, one valid row for every surviving listed ID with no extras or duplicates, revalidated pinned home/owner state and a conclusive exact-ID all-state absence query. It uses the existing invocation budget, not a retry. No-case preflight, unbound identities, foreign disappearance, unrelated errors, incomplete observations and still-present or ambiguous IDs remain failures. Absence alone does not satisfy probe, missing-media or native-evidence acceptance.

All selected phase budgets are positive finite seconds and reported with observed monotonic timings. Current unqualified defaults are call 15, create 30, startup 120, scenario 180, evidence 30, absence/cleanup 90, poll 0.5 and lease 10. Override them with the corresponding `--call-seconds`, `--create-seconds`, `--startup-seconds`, `--scenario-seconds`, `--evidence-seconds`, `--cleanup-seconds`, `--poll-seconds` and `--lease-seconds`. Each remote helper and command has a finite deadline. Cleanup revokes input first, gives evidence its own fresh deadline, attempts remaining independent safe stops despite failures, and gives absence confirmation its own fresh deadline; it never inherits an expired scenario budget.

Source-backed Wolf [lobby startup](https://github.com/games-on-whales/wolf/blob/ee271038da2b81c9e54c28c9daa7558692d415d6/src/moonlight-server/sessions/lobbies.cpp) can continue asynchronously after lobby removal. Stop success plus empty lists does not cancel an unresolved create. Without an actually observed running owned container, ambiguous startup retains potentially used state, marks cleanup incomplete and prevents a next case. Do not delete retained remote state based on a name prefix, a timeout or lobby absence; further ownership/absence and startup-barrier qualification is an explicit operator recovery prerequisite. The runner has no unsafe force-cleanup or restart fallback. Local image preflight also cannot disable stock Wolf's automatic-pull fallback if another actor removes the exact image concurrently.

Pinned Wolf's [Docker runner](https://github.com/games-on-whales/wolf/blob/ee271038da2b81c9e54c28c9daa7558692d415d6/src/moonlight-server/runners/docker.cpp) names a container with `runner.name` plus its lobby UUID, and its stop handlers compare that UUID. [Runner setup](https://github.com/games-on-whales/wolf/blob/ee271038da2b81c9e54c28c9daa7558692d415d6/src/moonlight-server/sessions/common.cpp) receives each case's explicit native home and derives Pulse names from the lobby ID. The shared suite runner name alone therefore does not establish cross-case coupling and is unchanged. Asynchronous compositor/audio/runner teardown is still a hypothesis, not an attributed failure.

When an existing selected-file `collect` finds no startup JSON, the ephemeral root helper now revalidates the complete owned container ID, immutable image, owner marker and native home before read-only diagnostics. It returns only numeric/boolean Docker state, known process-role labels with numeric PID/parent/UID, and codes for exact fixed fatal lines in the packaged startup source. For example, the runtime's fixed `Wolf session Pulse server, sink and source are required` error maps to `runtime-audio-contract`; its presence has not been observed in the failed native runs. Raw logs, process arguments, environment, exception messages and filenames are never returned or saved. Logs and process-table capture each stop at 64 KiB, with 64 log lines and 64 process rows. Reads share the existing call deadline; an observation child is killed and reaped within a separate one-second bound if necessary.

Reports retain at most 16 changed startup observations, preserving the first 15 and the latest, with an explicit truncation flag. Proven absence, unknown ownership/presence, unavailable diagnostics and truncated diagnostics are distinct. Process roles and log findings grant neither input nor cleanup authority. A recognized fatal startup code makes that case nonpassing before input; an unknown cause stays unknown and cannot pass without the original startup/isolation/assertion evidence. Existing independent teardown still runs. These diagnostics add read-only latency on the missing-startup path. Current-code forensic run `a5c38f9e89754b6c963dd256acf9a9cc` reached receiver startup under additional observation latency and was deliberately interrupted, not passed. If the additional latency hides the defect again, record that limit rather than claim it repaired the cause.

Private results are exclusively published below `output/integration/<run-id>/`: sanitized machine-readable report, selected owned diagnostic log, actual PNG checkpoints and accessible failure captures. Reports, logs, selections and PNGs publish complete final names atomically. Collection selects fixed names in the pinned evidence directory, requires private regular files owned by that directory's identity and refuses symlinks, hard links, special files and partial names. Complete captures and selected evidence transfer independently of final-report publication; malformed JSON cannot discard other accessible files before cleanup. PNG structure/CRCs are checked on retention, but only a matching authenticated diagnostic capture record can satisfy an assertion. Missing/malformed reports or unverified capture identity never pass. Capture/transfer/publication failure remains nonpassing and does not suppress cleanup. Raw requests, environment/config/session dumps and media bytes are not exported. Screenshots can still reveal content and remain private; no upload or automatic pruning occurs.

Only after evidence collection and independently observed lobby/container absence may pinned state be removed. Wolf's configured automatic removal can race explicit teardown. The helper checks the previously observed complete owned Docker ID across all container states. A successful fresh exact-ID query can establish that it is already absent, including after inspect, stop or removal loses that race. Failed queries, malformed responses, prefixes, lobby absence and stop exit status alone cannot establish absence. Reports mark an attempt `already_absent` only on observed proof; genuine failures remain incomplete and unresolved absence retains state. Global discovery of unrelated resources still fails closed.

Reports separate behavior, evidence, cleanup, ownership identities, not-run cases and limitations. Locally removing retained artifacts is a separate explicit action after reviewing the exact printed run directory, for example `rm -r -- "output/integration/$RUN_ID"` with `RUN_ID` set to that one reported 32-hex identity. This command is not remote recovery and must never target content or production state.

The authorized diagnostic build matched all 112,729 stock paths and supplied exact image `sha256:2ff829047d0d319655480a930a029c5c2ddddfa4155407eb85532e797526afbd`, with packaged-source identity `worktree-sha256:8f9061a4730ab420899c3c77994b5c901adaad32d7a85269d9e715f0edf8eb87`, transferred and loaded on the authorized target. First maintained frontend smoke `e6155ccd92b24e6e8490422b76298c47` failed before input with `Unknown native device access`; retain its report under `output/integration/`. It collected startup JSON only, not a frontend report or readiness capture. Its independent evidence polling reached the selected 30-second deadline, then owned lobby/container absence and state removal passed. This does not qualify frontend readiness, receiver behavior or timing/recovery bounds.

Pinned Wolf [`linked_devices`](https://github.com/games-on-whales/wolf/blob/ee271038da2b81c9e54c28c9daa7558692d415d6/src/moonlight-server/platforms/hw_linux.cpp) emits `/dev/nvidia-modeset`, `/dev/nvidia-uvm` and `/dev/nvidia-uvm-tools`. The host gate recognizes those exact spellings, still requires equal host/container device paths and approved permissions, and rejects malformed/unknown devices. That host-only repair reused the earlier loaded image with its original packaged-source provenance. The later application-actor repair changed packaged runtime bytes and required the corrected image recorded below. No emulator exit, libretro consumption, physical Moonlight forwarding, client-decoded video or heard audio is established here.

Second frontend smoke `bd7cacd346b6444ba0eec6dddf8b1e9d` passed effective-device validation, then failed the packaged read-only integrity inspection before input. Its report contains only `Remote operation failed closed`, not the exact cause. Owned lobby/container absence and disposable-state removal passed. Both failed runs remain retained; neither proves frontend readiness.

The host/helper wraps packaged `inspect_runtime` in an ephemeral bounded stdlib invocation. It never launches the app or probe through Docker exec. Exact fixed diagnostic messages become whitelisted `Packaged inspection failed: <code>` case errors; `app-uinput-access` means the packaged inspector rejected required app read/write access to uinput. Unknown diagnostic messages become `unknown-diagnostic`. Other exceptions expose only a fixed class category and numeric OS errno where available. Module/function stdout, stderr, arbitrary exception messages and dynamic filenames are discarded, not saved. Inspection failure remains nonpassing, keeps input closed and enters independent owned teardown. Run `c5e61b085d4d48e6bc67907a1bd8f347` qualified this channel and attributed the actual failure to `app-uinput-access`. Owned read-only forensic run `041bd487832d4ad5a8cbbb67a26b0b5a` then observed device-group access in runtime/frontend processes but no access in a restricted packaged support process. Its role whitelist did not identify that process as `input_worker.py`; source separately proves the worker's deliberate group restriction. Both runs kept input closed and passed owned cleanup.

The actor repair consumes root-controlled transport approval and rechecks live pidfds, parent/start identities and actor credentials before returning uinput authority. Empty/malformed approval, an absent live application root, a live approved actor outside that branch or a denied approved actor fails closed. Historical exited ProcessTree entries confer no authority. Host regressions run the actual inspector against real temporary proc/status/package files and controlled kernel metadata/readiness handles, then consume its observations through the real coordinator. They cover the restricted worker with qualified actors, denied actors, absent/malformed approval, capable unapproved processes, invalid ancestry, lost liveness and privilege violations. The 275-test coordinator result covers that actor repair, not the subsequent host/helper changes.

The corrected diagnostic build verified all 112,729 stock paths and supplied image `sha256:4a5c9d5b539be0c3673b2335dcea68e13adb05a138520b52a5672cb3867e7ce4` from packaged source `worktree-sha256:fc7ffa43e205a5502ee0b164b78522df4c0090863f37982f4b72702de4c105b7`, loaded on the authorized target. Smoke `375b5493544c4869b8817f4007880e3c` returned packaged integrity observations, then failed host parsing of ordinary tab-delimited `Uid`/`Gid`. No lease opened. Final lobby/container absence and state removal were observed, but a failed stop attempt kept cleanup incomplete. Its transient cause was not retained; automatic-removal contention is possible, not established. Retain that failed report.

The host accepts exactly four matching decimal IDs separated only by ASCII spaces or tabs in those two proc fields. Missing, nonstring, mixed-ID and other control-bearing observations still deny input; generic literal validation is unchanged. Those regressions and ownership-aware automatic-removal races passed in the 340-test coordinator run. Ticket 02's subsequent host/helper-only attribution changes reused the corrected image with its original packaged-source identity; the later integrated pass is recorded above. Their unknown startup cause remains unresolved. Ticket 03's runtime changes required the separately verified image/build/load recorded below. Publishing qualification metadata alone changes no native source and requires no image rebuild.

## Maintained NES/FCEUmm exit smoke

`--tier nes-smoke` selects only `nes-fceumm`. Native Wolf launches the packaged `emulator_probe.py` through the normal image entrypoint/session `Cmd`, never Docker exec. Existing idle/busy discovery, complete effective-mount validation, exact image/source/stock inspection and input lease all precede selection or synthetic input. Selection and reproduction use ticket 01's code against the native `/home/retro/userdata/roms` view and unchanged stock catalog. There is no alternate host search, extra content bind, private title constant, downloaded fixture or retry after failure.

The suite owns [the gamepad definition](assets/input/suite-gamepad.json) and [the ES mapping template](assets/input/suite-es-input.cfg). It discovers the real SDL GUID/name/counts and exercises every button, axis and hat index through that device before seeding the mapping into disposable userdata only. It checks stock configgen's actual generated buttons, axis, hat and player-device index, and the unchanged stock libretro exit context. Successful run `d0f90ed2198440ec8c8978c5c77e4d28` observed actual packaged discovery, controls and stock configgen consumption; this is not inferred from the computed GUID or host tests.

The first actual NES run, `887fced6a06c46beb4bfac7eff5e9a9c`, failed in 35.76 seconds at `actual stock SDL gamepad discovery`, before launcher execution. Image `sha256:07d9a1b8448da53d9dafc994c91e8ac086674daf6af452af1b343a27e76031c2`, source `worktree-sha256:4b2415e377b703c212e8cb40ec2a65cc2a4ab2f84b0140343403db48d4297c9f`, preserved all 112,729 stock paths and contained 21,792 verified additions. Forwarding and SDL initialization completed, but the retained report has no enumeration or pad-metadata observations. Stock hashes stayed unchanged, failure PNG/private selection were retained and both cleanup layers passed. The black PNG is not emulator output. SDL identity/control qualification, configgen/native consumption and exit remain untested.

[Pinned discovery research](../docs/completed/specs/wolf-integration/research/native-lifecycle-and-actions.md#ticket-03-stock-sdl-discovery-boundary) identifies Batocera patches removing joystick capability guessing and the preliminary manual scan. Instrumented run `fefabd72d5f84eaebf861532b8ce44ed`, source `worktree-sha256:ef7236fc9a9e49a1a37c08cecf6f9d50eb735ee81273073ebcbac376fdd144b3`, image `sha256:0f894768f4cc50a73543cc3e8e77c886e4b5e03ba97787fbd182f93a5c84d061`, failed in 22.90 seconds before launcher execution. Both observations opened the exact expected node; both app-local records were missing. SDL reported 2.32.8 and zero joysticks across 477 polls. Stock hashes, private selection identity, retained black failure PNG and both cleanup layers passed their respective observations. No emulator launch/exit did. Missing metadata is implicated, not established as the sole cause.

The conditional repair publishes only the actual stock classifier's properties for the exact suite pad created by the already admitted live packaged NES probe. Command/executable, suite name, bus/vendor/product/version, creator/sysname/dev_t and newly created node checks constrain that publication. Stock `udevadm test-builtin input_id` must actually return `ID_INPUT=1` and `ID_INPUT_JOYSTICK=1`; no joystick or keyboard flags are invented. Publication reuses the atomic no-clobber app-local record and ownership-checked removal. Final keyboard publication still requires stock key classification; source admission, privileges, stock mappings, hints/GUIDs and final-only XTEST routing are unchanged.

`pad_discovery` retains classifier properties/digest, runtime SDL version/init result, exact node/record observations and bounded first/latest enumeration counters. It also binds actual SDL/libudev function addresses to the inventoried files' mapped device/inode and file SHA-256, checked against host-inspected stock inventory. A no-load handle observes fixed stock SDL input-log branches; the prior callback and input priority are restored in `finally`. Libudev selection without fallback is required before discovery can qualify. Unknown modes, different mappings or wrong inventory digests fail closed. Udev reads remain no-follow and limited to 4,097 bytes; only fixed classification keys and normalized values survive. No raw SDL log/error bytes, unknown paths or metadata are exported. Metadata or readability still cannot replace actual SDL rdev match/open/name/control qualification, native consumer observations or the Guide+Start exit gate.

The unchanged `emulatorlauncher -system nes -emulator libretro -core fceumm` receives the selected existing media and discovered controller arguments. Acceptance requires a pinned live RetroArch process, its exact mapped FCEUmm core and active emulator window with nonblank central rendered content throughout a two-second no-exit barrier. The content predicate excludes blank/uninitialized output and window borders; it is not a title, gameplay, menu or pixel-change oracle. Actual executable/core/info hashes, RetroArch version metadata and libretro core name/version are recorded without retaining raw metadata output. The generated RetroArch input drivers, root-controlled final-source live identity, actual udev keyboard classification and emulator-opened final/pad device numbers are independent requirements, not inferred from receiver success.

Only the owned native pad's Guide+Start is assertion input: synthetic gamepad → existing adapter → unchanged stock hotkeygen. Assertion `stock-native-observed-exit-v3` requires completed press/release, the same pinned emulator ending after that chord and stock launcher completion with code zero. The shared lifecycle ends on those combined observations, without starting a replacement EmulationStation. Live/output and identity barriers, actual native-device consumption, input release, stock integrity, required evidence and successful owned cleanup remain mandatory. A sent event, process disappearance, PNG or launcher zero alone cannot pass.

`termination_observation.mechanism` is `pidfd-and-stock-launcher`. Its emulator PID/start matches the transition identity and `live` is false; its distinct launcher PID/start has observed `code: 0`. The launcher source hash still matches the inspected stock inventory. `kind`, `complete`, `classification`, private-stream flags and any `log_sha256` describe diagnostic log parsing only. Neither a missing stream nor logging errors, signaled classification or unclassified records independently veto an otherwise complete observed shortcut exit. This proves no graceful shutdown mechanism, save persistence or frontend recovery.

The private pipe consumer still drains merged stdout/stderr continuously, retains at most 8 MiB in memory and discards excess while continuing to drain. Oversize, missing EOF, read failure or incomplete records make log classification unavailable, not process observations invalid. The post-launcher EOF wait remains 250 ms; cleanup cancels and joins the consumer within one second. Raw bytes are never exported or written to disk and are cleared during owned cleanup. Reader-close failure, required evidence publication/transfer loss and unsafe or failed cleanup remain nonpassing. No tracing, extra permissions, process-wide file-size limit or stock rewrite is used.

`termination_observation.classification` distinguishes `classified`, parser `rejected` and `stream-unavailable`. A classified result supplies diagnostic `exited` or `signaled` kind. Rejected complete bytes retain only a fixed predicate category such as `logging-error`, `malformed-launcher-record` or `trailing-output`, never private text. Stream-unavailable means the classifier did not run; its reason is null and bounded byte-count/EOF/overflow/read-error/cancellation/draining flags remain visible. `complete` means a log classification exists, not that shortcut acceptance passed. Final JSON and later incomplete boundaries retain the same pre-cleanup diagnostic observation.

For a diagnostic `logging-error` rejection, `classification.logging_error` describes only the first envelope. `status` is `recognized`, `unknown` or `truncated`; `exception` is a fixed builtin category or `unknown`. `condition` is `format-arguments`, `closed-stream`, `encoding-error`, `os-error` or `unknown`. Numeric errno is retained only for recognized OS exceptions with a valid 1 through 4095 prefix. Exact exception strings, traceback text, source lines, Message/Arguments, paths, filenames and function names are never exported. Up to eight exact pinned public frame locations become fixed role/line pairs; other frames set `unknown_frames`. The first-envelope scan is capped at 8 KiB and 128 lines; exceeded bounds retain no partial categories/frames. `additional_markers` records another marker only, not another proven exception. These patterns are not authenticated runtime stack provenance or proof of cause of death, and do not authorize a logging investigation or extra native campaign.

No post-exit frontend readiness or screenshot is required for any emulator. Independent normal frontend/transport readiness and all five receiver cases remain unchanged. Direct final-key injection, exit commands, test-sent signals, pre-chord death, wrong or replaced process identity, ineffective exit, pending/nonzero launcher and forced emulator teardown cannot satisfy observed shortcut exit. A stock log saying `signaled` is not itself proof that the test sent a signal; actual test-sent termination is tracked and rejected independently.

The initial ticket03 host gate returned **401 passed, 4 failed, 1 skipped**: incomplete independent fixture integrity correctly refused before selection/input. Later hook/import/typing defects, incidental selected-log newline assertions, failure-capture retention and launcher-normalized signal false passes were repaired without weakening the production gate or sanitizer. The coordinator reproduced the unterminated-output signal-record false pass before its repair. Final **443 passed, 1 skipped** covers conservative classification, bounded draining/EOF and close-error private-buffer clearing, plus real owned capture retention/deletion. Post-verification static review found no remaining blocker in those inspected host paths. Earlier failed evidence remains in ticket03; passing host tests and hooks supply no native exit qualification.

The first conditional-publication host run observed **463 passed, 1 failed, 2 skipped** because the forged-argv fixture assumed `/bin/sleep`. The portable replacement and explicit class-variable declaration now pass the corrected host suite recorded above. The real SDL logger regression remains host-prerequisite-skipped; it cannot substitute for actual packaged discovery-mode observations. Initial hooks reformatted eight files; subsequent explicit generated-file hooks pass and mandatory all-files hooks are stable under the inherited-file-only waiver. No worker tests, hooks, builds, SSH or native actions occurred.

Changed-image run `9790d6cf41da411da10946e1fba18c62` failed in 14.74 seconds at `Actual RetroArch version metadata missing`. Source `worktree-sha256:dc78f9f694ca3c4bee775a6228dc1ade43951c9ebf0545e0eef8421ba3478212`, image `sha256:487e76ddb18a60474b5009432ebc2e6b782cf2c1aaaa4e48d016a671be59e196`, preserved 112,729 stock paths and 21,792 additions. Actual classifier properties, mapped SDL/libudev digests and effective libudev discovery matched inventory; the exact pad was discovered on the first poll and its profile/open/controls qualified. Stock configgen consumption remained false and native consumption untested. Forced owned teardown and independent probe/coordinator cleanup passed; retained failure capture is not emulator output. Selected media identity matched the original private record.

Fresh exact-image `/usr/bin/retroarch --version` inspection exited zero in an auto-removed, networkless, read-only UID/GID1000 container with no capabilities, no-new-privileges and no media/state mounts. Public stdout was `RetroArch - Frontend for libretro`, `Version: 1.22.2 May 29 2026`, `Compiler: GCC (13.3.0) 64-bit`. The old parser required a `v` prefix. The repair extracts one complete stock `Version:` record, excludes its build date and rejects missing, malformed or duplicate records. All 13 public parsing regressions pass using the observed output and nonpassing controls without process mocks. Executable/core digests and core identity/version requirements are unchanged.

Historical metadata-repair image `sha256:cb202d96f3e4d4da3e1325cc2c865459e94a5a2d25a84a4c8f2f182bd26b25cf`, source `worktree-sha256:57b623238d49a438b08459d0dddb3c8c81b72ffedc8a45954065d9b9516aa08f`, was built and loaded. Original-selection run `ac17be8db1e742d3a284f4fa41822639` retained authenticated nonblank emulator-before-exit pixels, then failed closed on a remote operation and exhausted final-evidence collection without final probe JSON/log or return/failure captures. Owned cleanup passed. Cause, chord/exit and consumer acceptance remain unproved. Later evidence-retention repairs do not relabel that failed report.

The subsequent X11-repair image `sha256:e7181d8545fad0e0459ad9f858ee9479a311d5eff1e3d7aa952bba4d1263163b`, source `worktree-sha256:4061bc3e0c42d66065b46c4e0eae7d0259adf835f4d96488ddcf602d3c432a9f`, passed independent stock verification and target load. Original-selection run `fde40f7e5c0340e1a5bda3683c757b1d` failed in 16.91 seconds at unavailable termination classification, despite native consumption passed, nonblank output, both chord phases, pinned emulator death and launcher zero. Its complete private stream retained 68,487 bytes with SHA-256 `86142e3a2b6dd5b13c5d702380a576badf5fe86352d4905c8698678105b0964f`, EOF true and overflow/read-failure/cancellation false. Final JSON, selected sanitized log and incomplete launcher/failure/cleanup boundaries survived. No frontend was started and no forced emulator teardown occurred; probe/coordinator cleanup passed. The actual stock formatter matches the parser grammar, but the rejected predicate is unknown. Raw bytes were memory-only and are unavailable after cleanup, so neither a logger mismatch nor natural exit can be inferred.

The next stock-verified image `sha256:9dbce3be5f85d09e31e5837b04c92d27238c0381d9a28bfce8a2a925cb345d42`, source `worktree-sha256:58a71a4038284ae20d842710824ac891e7931a8372b5533804ec548dde6665e8`, passed the full saved-image stock gate/build in 706.10 seconds and exact target load in 196.16 seconds. Original-selection run `b6963932800442fca1d4a7841dce622f` proves the rejection predicate was `logging-error`, not which exception produced it. Its complete stream had EOF, 68,487 bytes, SHA-256 `9b6288944c7bc25bb334d6015d8bcff9f63b6549dfea7955d0ed9ddddbdfb9e3` and no overflow/read failure/cancellation. Native consumption and both chord phases passed; emulator PID830/start181843367 was dead and launcher PID689/start181843217 returned zero. Frontend was withheld, the actual failure PNG was visually black, final/sanitized/boundary evidence survived and both cleanup gates passed without forced emulator teardown. Raw bytes are gone. The preceding host baseline was 500 passed/two prerequisite skips, all seven real-X11 cases and owned-pipe/media/planning smoke passing, generated hooks passing and stable inherited-only all-files findings of 50 Ruff, 1,683 mypy errors in 29 files and four Statix warnings. Those results do not exercise the new logging attribution.

The observed-exit cutover completed its packaged native attempt. Run `d0f90ed2198440ec8c8978c5c77e4d28` passed on image `sha256:9d4980b16df126a71a1d2522f194528c3daaafc00e44d754216671dfaadb9368`, source `worktree-sha256:b63501d5a6fa6870d1b7be94e597ac25bb9d3788a65b39d0f347f0fe6260b7b5`. The maintained build and independent saved-image inventory verified all 112,729 stock paths with 21,792 additions before exact-image target load. This run reproduced the original private selection and retained authenticated 1280×720 emulator output, actual udev backend and opened final/pad device identities, qualified profile/configgen consumption, the two-second live pre-chord barrier, native press/release, same pinned emulator exit and launcher code zero. Stock hashes remained unchanged. Probe cleanup reported no forced emulator teardown; coordinator cleanup confirmed lobby/container absence and removed owned state. The report and required evidence remain in `output/integration/d0f90ed2198440ec8c8978c5c77e4d28/`. Diagnostic `logging-error` and unavailable natural-exit classification remain visible, not fixed or asserted.

Independent run `1979a36a973144f180f5fe720b57a94d` passed `--tier frontend-receivers` on that same image/source, including normal frontend readiness, all five receiver assertions, required captures and both owned cleanups. Its `full_frontend_receiver_gate` is true; the NES smoke's is false. These are separate gates, not frontend recovery after emulator exit. At that revision, other emulator tiers were unavailable. Ticket 04's later SNES/Atari native passes and Mega Drive absence are recorded below against their own image/source. Full regression/expanded execution remains unavailable. Earlier failed reports keep their original assertions and outcomes; no logging investigation is needed to publish those records.

The following commands remain the coordinator's verification entry points, not evidence that this metadata publication ran them. The pre-native cutover host suite passed 534 tests with two SDL/stock-ALSA prerequisite skips, including all seven actual-X11 cases. Existing generated-file hooks passed, and the stable all-files gate retained only the accepted inherited-file findings. The separate application coverage shortfall remains recorded in [current tooling](../docs/current/tooling.md#current-configuration); it is not fixed or waived here. Qualification publication changes only records and this guide, not native runtime source or the verified image.

These examples select maintained behavioral tests and hooks. Historical generated-file checks also included untracked additions; an all-files invocation alone does not select those files. Include the actual changed source, assets and tests explicitly when checking a cutover.

```sh
uv run pytest \
  tests/integration/local/test_emulator_lifecycle.py::test_observed_process_exit_passes_with_logging_error_and_no_frontend
uv run pytest \
  tests/integration/local/test_emulator_lifecycle.py \
  tests/integration/local/test_emulator_media.py \
  tests/integration/local/test_duckstation_wrapper.py \
  tests/integration/local/test_native_desktop.py \
  tests/integration/local/test_native_integration.py \
  tests/integration/local/test_media_qualification.py
uv run pytest
uv run pre-commit run --files \
  src/batocera_gow/host/native_integration.py \
  src/batocera_gow/host/native_remote.py \
  src/batocera_gow/runtime/emulator_lifecycle.py \
  tests/integration/local/test_emulator_lifecycle.py \
  tests/README.md
pre-commit run --all-files

uv run batocera-gow-native plan --tier nes-smoke
nes_smoke() {
  uv run batocera-gow-native run \
    --authorize-native --native-authorized-target "$BATOCERA_GOW_SSH_TARGET" \
    --native-authorized-root "$BATOCERA_GOW_HOST_ROOT" --host-root "$BATOCERA_GOW_HOST_ROOT" --tier nes-smoke \
    --build-manifest output/gow-full-x86/build-manifest.json \
    --stock-manifest output/gow-full-x86/stock-manifest.json \
    --render-node /dev/dri/renderD128 \
    --video-caps 'video/x-raw(memory:CUDAMemory)' "$@"
}
NES_RECORD='output/integration/887fced6a06c46beb4bfac7eff5e9a9c/nes-fceumm-selection.json'
nes_smoke --reproduce-selection "$NES_RECORD"
```

The helper function is only a local shell shorthand for the same explicit command, not a retry loop. Supply any independently inspected `--infrastructure-container <complete-64-hex-id>` arguments on **each** invocation when the installed target requires them. Changed diagnostics cannot use ticket 02's image identity as current-checkout evidence. Host tests exercise deterministic transition failures plus real owned subprocess/pidfd and filesystem effects; they do not establish native acceptance.

Only actual absence/empty/unsupported-only NES media produces exactly `Skipped: no compatible mounted media`, with native consumption untested, zero passing exit cases and `No emulator exit coverage`. Selection errors, missing roots/permissions/firmware, changed members, unavailable controls/core/output/readiness, ineffective exit, capture failure and incomplete cleanup are failures. Eligible media is chosen once; no custom ROM or game-specific input oracle is required. Startup failures and earlier failed attempts remain visible.

Every eligible attempt retains `nes-fceumm-selection.json` privately in its printed owner-only run directory, even on accessible failure paths. It contains private filenames/member identities, is deliberately not sanitized into an unusable record, and is never included in the sanitized summary. The required launch capture is `nes-fceumm-emulator-before-exit.png`; retain an accessible `nes-fceumm-emulator-failure.png` on failure. There is no post-exit frontend capture. PNG decoding/CRC and exact digest checks still apply. No media bytes, raw logs, environment/config dumps or production profile are exported. The report binds media/catalog/profile/assertion/backend identities to inspected image/source and cleanup observations.

The shared selection writer publishes a complete record atomically and exclusively. Collection can retain that immutable private identity before the final probe report, so a later probe failure cannot erase an already selected attempt's reproduction input. Immediately before stock launch, ticket 01 rechecks that same identity after controller qualification. Stock launcher, executable/core/info and configgen source hashes extend the existing input-integrity checks; suite asset and backend digests must match the inspected package/inventory, not merely look like hashes.

Incomplete causal evidence is separate from final acceptance. At most seven fixed owner-only atomic JSON publications are selected: `emulator-before-chord.json`, `emulator-chord-pressed.json`, `emulator-chord-released.json`, `emulator-launcher-exit.json`, `emulator-failure.json`, `emulator-cleanup-start.json` and `emulator-cleanup-returned.json`, each prefixed locally by `nes-fceumm-`. Every record has `status: incomplete`; none replaces `emulator-probe.json`. They retain selected media/profile/consumer observations, numeric process identities/status, authenticated capture identities and bounded private-stream flags. Raw launcher bytes and arbitrary exception messages are never exported. A press/release record alone observes source injection, not successful shortcut exit; missing later records mean unavailable evidence, not inferred completion.

Cleanup collection also requests the existing bounded owned-container/process/fixed-failure-code observer when startup exists but final JSON does not. Phase-tagged results remain in `startup_observations`, including cleanup-phase observations, without widening that fixed schema or granting authority. Auto-removal may leave only proven absence, while a failed inspection remains unknown. Helper failures expose only validated category/code and numeric errno. Neither diagnostic absence nor successful independent cleanup passes a missing final report. The real-process/filesystem/helper regressions passed within the historical 480-test host suite. They exercise incomplete evidence, stream failure reasons, full-budget missing-final progression and nonpassing aggregation. Evidence writes and read-only observations add latency and are not a demonstrated repair of the earlier unknown native cause. The later successful v3 run retained its final report; it does not repair or relabel that earlier failure.

The successful v3 run reproduced the retained original run identity below. Use this same private record for a separately authorized reproduction, not a fresh random selection, and never print or publish its contents. The bounded local owner-only reader transfers it only into the newly inspected disposable control directory, before leasing input. Native ticket 01 reproduction rechecks that exact eligible entry and refuses missing/changed files; it never rerolls.

```sh
NES_RECORD='output/integration/887fced6a06c46beb4bfac7eff5e9a9c/nes-fceumm-selection.json'
nes_smoke --reproduce-selection "$NES_RECORD"
```

The following optional, explicitly authorized native controls exercise only suite-owned lobbies, processes and input, with the **same** selected media. They are not recorded as executed by the successful normal run. Each must be nonpassing for its intended observed reason and retain successful independent owned cleanup. A prerequisite refusal or no-media skip is not execution of a control. Never redirect a control to production state or count its forced teardown as exit proof.

```sh
nes_smoke --reproduce-selection "$NES_RECORD" --negative-control launcher-error
nes_smoke --reproduce-selection "$NES_RECORD" --negative-control withhold-readiness
nes_smoke --reproduce-selection "$NES_RECORD" --negative-control withhold-chord
nes_smoke --reproduce-selection "$NES_RECORD" --negative-control wrong-window
nes_smoke --reproduce-selection "$NES_RECORD" --negative-control pre-chord-death
nes_smoke --reproduce-selection "$NES_RECORD" --negative-control early-native-exit
```

`launcher-error` asks stock configgen for a deliberately absent core. `pre-chord-death` signals only the pinned owned emulator and records forced teardown. `early-native-exit` sends the native chord before the live barrier and must fail as premature exit. Other controls withhold a required observation/action; `wrong-window` withholds active-window attribution. Existing host lifecycle/process seams cover wrong PID/PID reuse, pending/nonzero launcher, ineffective exit, missing chord, capture loss and test-sent signals even when launcher status is normalized to zero. These controls do not require a logging or frontend-return campaign. No fault mode may publish a passing normal assertion.

Selected emulator deadlines are startup 40 seconds, continuous live output 2 and exit 15, with 0.05-second observations. The diagnostic retains its 240-second alarm, and the coordinator retains independently bounded lease/scenario/evidence/cleanup phases. No frontend-return budget remains. The coordinator observed the packaged NES run complete in 16.89 seconds and the independent normal frontend/receiver run in 24.93 seconds. These observations qualify the tried route, not a general performance guarantee. Gameplay, menus, other shortcuts and client/controller forwarding remain untested. Final ticket review and checks remain coordinator-owned.

## Remaining libretro exit smoke

Each tier selects exactly one stock system/backend/core. It uses the same packaged `emulator_probe.py` command and v3 observed-exit lifecycle as NES, without widening native pad admission or changing stock configgen, hotkeygen or controller mappings.

| Tier              | Report case               | Stock system folder | Exact backend/core       |
| ----------------- | ------------------------- | ------------------- | ------------------------ |
| `snes-smoke`      | `snes-snes9x`             | `snes`              | `libretro/snes9x`        |
| `megadrive-smoke` | `megadrive-genesisplusgx` | `megadrive`         | `libretro/genesisplusgx` |
| `atari2600-smoke` | `atari2600-stella`        | `atari2600`         | `libretro/stella`        |

The folder and supported extensions come from the inspected pinned stock `es_systems.cfg`, not this table or a host directory scan. SNES accepts its stock cartridge/archive formats, including `.sfc`; Mega Drive includes `.bin`, `.gen` and `.md`; Atari 2600 includes `.a26` and `.bin`. The complete declarations remain in [cases.json](assets/media/cases.json). Ordinary cartridges need no external BIOS. Special-chip/add-on or firmware-dependent selected content still needs compatible prerequisites and actual native qualification; an eligible launch failure is not media absence.

After separately authorized packaging and exact-image inspection, use the same SSH/content settings and installed render-node/video-caps arguments as the NES command. These are invocation examples; the observed dispositions below apply only to their recorded runs:

```sh
uv run batocera-gow-native plan --tier snes-smoke
uv run batocera-gow-native run \
  --authorize-native --native-authorized-target "$BATOCERA_GOW_SSH_TARGET" \
  --native-authorized-root "$BATOCERA_GOW_HOST_ROOT" --host-root "$BATOCERA_GOW_HOST_ROOT" --tier snes-smoke \
  --build-manifest output/gow-full-x86/build-manifest.json \
  --stock-manifest output/gow-full-x86/stock-manifest.json \
  --render-node /dev/dri/renderD128 \
  --video-caps "$GOW_NATIVE_VIDEO_CAPS"
```

Select `megadrive-smoke` or `atari2600-smoke` instead for those independent cases. Supply any independently inspected `--infrastructure-container` arguments on each invocation. Do not wrap attempts in a retry loop. The fixed startup/live/exit budgets are inherited from NES. The recorded SNES/Atari passes exercised them; Mega Drive has no native launch or exit qualification.

`GOW_EMULATOR_CASE` carries the selected exact case through the inspected environment while the admitted command stays unchanged. Stock launch uses that case's system and core; live observations pin `/usr/bin/retroarch`, its exact core command and mapped core, and measured executable/core/info/version identities. Actual udev backend selection, final-device keyboard classification and opened final/pad identities remain separate requirements from receiver success. The same native Guide+Start press/release, live-before-chord barrier, same-emulator exit, launcher zero, evidence and both cleanup gates apply. No natural-log classification, replacement frontend or test-sent signal can supply success.

Each case retains `<case>-selection.json`, `<case>-emulator-before-exit.png`, accessible failure captures and the existing case-prefixed final/incomplete evidence. Reproduce an attempted case with its own owner-only `--reproduce-selection output/integration/<run-id>/<case>-selection.json`, never the NES record or another case's media. Wrong-case reproduction and wrong case/system/core reports, including absence reports, fail closed. Missing/empty/unsupported-only media skips only the requested case as `Skipped: no compatible mounted media`; native consumption remains untested and the run claims no emulator exit coverage. Root/access errors, changed selected files, missing eligible prerequisites, wrong devices/core, startup/chord/launcher/evidence failures and incomplete cleanup remain nonpassing.

The existing host lifecycle and packaged-process media tests cover these bounded behaviors with synthetic non-ROM files. They establish neither native success nor native media absence. Actual qualification belongs in its private run directory, tied to the selected media, backend/profile, image/source and assertion identities. All three reusable public declarations remain unqualified/null.

### Observed ticket 04 dispositions

These results use independently stock-verified image `sha256:128ebf123b3a78a2162e90fbcc51dbaeab29203758729d8232c0dd8596e46572` and source `worktree-sha256:baab3bf61c158ef7689575cbdeab5b5603f7665ae4803e69dca9fc39899976df`. They do not qualify later runtime changes.

| Case                       | Run                                | Observed disposition                         |
| -------------------------- | ---------------------------------- | -------------------------------------------- |
| SNES/Snes9x                | `57bb80bdf7ac42e59c06c790462f0e0c` | Original-selection native observed-exit pass |
| Atari 2600/Stella          | `38c60d5067be4352b2cc6a91a4be4b9f` | Original-selection native observed-exit pass |
| Mega Drive/Genesis Plus GX | `f7f492e796bc4f99b07f96dc29e4be03` | `Skipped: no compatible mounted media`       |

For each SNES/Atari run, the coordinator independently verified stock launch and rendered output, actual native backend/device and profile consumption, the continuous two-second live pre-chord barrier, native Guide+Start press and release, termination of the same pinned emulator and stock launcher code zero. Each run retained 11 verified artifacts and unchanged stock hashes. Input release and both independent owned cleanup gates passed without forced emulator teardown. Private selected-run qualification JSON resides under each mode-0700 run directory, with mode-0600 files; strict parsing passed. Those private records qualify only their actual selections, not the public templates.

Mega Drive reached effective inspection and actual mounted-media discovery after the canonical stock metadata fix. No compatible mounted media was available. The coordinator verified its five artifact hashes, unchanged stock/core/canonical metadata and both cleanup gates. This is a permitted absence skip, not an unnecessary implementation or a removed executable row. Native launch, output, consumption, chord and exit remain untested for this case, with no emulator exit coverage claimed.

The same-image original-selection NES run `c22d3a64e581484fbe53690caf5dfb36` and independent normal frontend/five-receiver run `555cba3f57a84b849854319c76f5dc0b` passed separately. They preserve the common NES and receiver contracts, not post-exit frontend recovery. These results establish no gameplay, full-baseline or other-backend pass.

## DuckStation exit smoke

`--tier psx-smoke` selects only `psx-duckstation` with OpenGL; `--tier psx-vulkan-smoke` selects only `psx-duckstation-vulkan` with Vulkan. These are two variants of the existing DuckStation backend, not another backend. The shared `batocera_gow.runtime.media_catalog` module supplies both host and packaged probe declarations. Selection occurs after effective inspection, under the existing lease, against the stock `/userdata/roms/psx` declaration. Supported formats are `.cue .img .mdf .pbp .toc .cbn .m3u .ccd .chd .iso`; a loose `.psexe` is not a stock launch route. CUE tracks and playlist members retain their private digests and relationships. Reproduction reuses the original selected record and rejects changed/missing/symlinked members rather than choosing another disc.

The probe retains unchanged absolute `emulatorlauncher -system psx -emulator duckstation -core duckstation`. The pinned [stock generator](https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/generators/duckstation/duckstationGenerator.py) returns bare `duckstation-qt -batch -nogui -- <disc>`, allowing the scoped PATH prefix to select the project wrapper only after stock configgen has written its final settings. Stock still enables SDL, disables Evdev/XInput/RawInput, supplies `SDL_GAMECONTROLLERCONFIG` and `SDL_JOYSTICK_HIDAPI=0`, and selects the unchanged `duckstation` LeftAlt+F4 context. The test sends only native Guide+Start, never Alt+F4 directly.

Before ES reads its catalog, normal state initialization installs the root-packaged partial command from `/opt/gow-full-x86/es_systems_gow_duckstation.cfg` into `/userdata/system/configs/emulationstation/es_systems_gow_duckstation.cfg`. Its only PSX change is `PATH=/opt/gow-full-x86/emulator-wrappers:$PATH` before the stock launcher, retaining all normal ES placeholders. Descriptor-pinned/no-follow traversal and private publication prevent root operations from following substituted app paths. Expected bytes are a no-op; modified destinations, unsafe catalog files and conflicting user PSX command overlays are preserved and reported, never reordered or overwritten. The direct native launcher validates the exact installed command and absence of conflicting user commands, then derives the same PSX-only prefix; it cannot qualify a test-only route absent from ES.

`emulator-wrappers/duckstation-qt` reads final `[GPU] Renderer` after configgen. Only `OpenGL` opens live EGL/X11. The policy follows pinned [EGL config selection](https://github.com/duckstation/old-releases/blob/3a08ad18406efc1ddc4927a59bea715961bb63fa/src/util/opengl_context_egl.cpp#L478-L616) and [context ordering](https://github.com/duckstation/old-releases/blob/3a08ad18406efc1ddc4927a59bea715961bb63fa/src/util/opengl_context.cpp): WINDOW/renderable/RGBA8 candidates in driver order, first exact RGBA8 match (first candidate only if no exact match), and the pin's desktop/GLES version order with the existing GLES preference preserved. It queries the chosen config's native visual and validates that visual on the actual authenticated X11 connection's default screen, then adds Qt's supported `-visual <id>` pair. No session visual/config ID is persisted or hardcoded. Discovery/validation failure refuses the OpenGL launch: no uncorrected exec, renderer fallback, visual-environment workaround or LD rewrite. Vulkan and other renderers skip discovery and retain their original argv. Final exec is always absolute untouched `/usr/bin/duckstation-qt`, preserving environment and process identity.

Each native variant seeds its supported stock `psx.duckstation_gfxbackend` preference, `psx.bezel=none` and private INFO file/console logging in disposable userdata. The undecorated setting matches the working beta profile and excludes stock configgen's optional MangoHUD bezel insertion from this emulator/shortcut case. It does not change runtime defaults, operator userdata, `hud_support`, the wrapper or its final environment. MangoHUD-enabled bezels remain outside this qualification. Live readiness checks final generated renderer and binds a bounded no-follow regular-log descriptor actually open in the pinned emulator, without waiting for buffered activation text. Only after pinned exit and launcher-zero does the probe interpret ordered pinned-source device/context/HW-framebuffer records through that descriptor. A real buffered-writer regression verifies this sequencing. Only selected/active mode and pinned identity are retained, not raw log content. OpenGL reports desktop OpenGL or the pin's negotiated OpenGLES context; Vulkan must activate Vulkan. Software fallback, missing/ambiguous activation, wrong process or wrong Qt visual args cannot qualify. Mode evidence supplements the selected-disc, rendered-output, live input and exit gates.

Host regressions exercise startup filesystem effects and conflict preservation; wrapper exec/PID/argv/environment and refusal boundaries; controlled EGL policy calls; authenticated two-screen Xlib visual validation; interpreter-to-ELF/pidfd gates and pinned-process open-log observations; and separate renderer qualification. The startup reducer also recognizes only the wrapper's fixed refusal messages in the bounded stock stderr record. Actual wrapper-to-reducer tests and private/quoted/partial/unframed rejection controls cover that protocol. These host checks do not replace packaged NVIDIA rendering and native exit.

Firmware is operator-supplied through the existing read-only BIOS mount. The probe observes the stock generator's recognized regional/universal choices, hashes them without exporting names or bytes, and checks the generated firmware route. Recognized availability is not boot compatibility. An eligible disc with missing/unusable firmware or failed output is nonpassing, not a no-media skip. There is no acquisition, replacement firmware, copied production configuration or custom PS1 program.

Backend evidence pins the actual Qt executable and child identity. Native consumption requires the suite pad actually open in that process, the effective SDL environment consuming the suite GUID/buttons/axes/hat, generated Pad1 mapping and unchanged stock exit context. The observed discovery count and actual opened joystick identities must establish a single suite-pad topology. The report labels its player index as configured and its index basis as that observed topology, not independently logged SDL player state. RetroArch drivers/core metadata and a final-keyboard event FD are not Qt requirements.

Display acceptance combines an open member of the selected disc with an active normal fullscreen, nonmodal, nontransient game-render window and nonblank authenticated pixels. Pinned first-party [Qt window code](https://github.com/duckstation/old-releases/blob/3a08ad18406efc1ddc4927a59bea715961bb63fa/src/duckstation-qt/mainwindow.cpp) changes the render title from its application name only for a valid running system. Private titles are checked in memory, never reported. Qt settings/error dialogs, a live PID or arbitrary nonblank windows cannot supply the observation. The existing exact-request BadWindow handler also protects the bounded property reads; destroyed windows remain unavailable.

The coordinator's installed metadata observation on immutable image `9d4980b1` returned code 1 and exactly `DuckStation Version  ()`. First-party [Qt parsing](https://github.com/duckstation/old-releases/blob/3a08ad18406efc1ddc4927a59bea715961bb63fa/src/duckstation-qt/qthost.cpp) uses single-dash `-version` and returns failure for informational mode. Its placeholders are compiled tag and branch, not an independently measured commit hash. `reported_version` retains the actual installed output, code and empty tag/branch. The separate `package_source` records [Batocera's pinned recipe](https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/emulators/duckstation/duckstation.mk), `v0.1-7294` and old-releases commit `3a08ad18406efc1ddc4927a59bea715961bb63fa`. That is not a semantic version observed from the binary. The installed executable SHA-256 is `24814978c0b8cd8a0b8eea756396c0b0df2067d1fb5adb64a3c5c34fd876c1fe`; changed packaged sources still require their own inspected image identity.

Actual original-selection run `93165970d4bf4f3bb4f863ab8f60b36c` failed before the chord with a fixed-category configgen `KeyError` observation, not an identified BIOS error or exact missing-key attribution. A separate unchanged-stock consumer experiment proved the suite omitted the normal frontend's `LANG`/`LC_ALL` defaults. After correcting only that host launch environment, original-selection run `c2ab34362b2947e0a1a929236d32cb88` progressed beyond configgen and pinned DuckStation PID 798/start 186353264, then failed because that process died before the chord. Launcher PID 687 was still pending. Its single private reader was draining 44,572 bytes without EOF, overflow, read error or cancellation, so the completed-launcher-only exception diagnostic did not apply; cleanup cleared the bytes. Both cleanups passed without forced emulator teardown. Neither attempt is a missing-media skip or passing shortcut result.

Those historical attempts used stock-verified image `sha256:ac361d915f415f56ceb457f7ae0eeb55817f045a4ab567cf6011a0cd9238d519`, source `worktree-sha256:056431a4227570b5de774f5d02293100a06aa156ab2ed94d53ad612c1dea62fc`. The host-only locale correction did not change packaged inputs or require relabeling that image. The later fixed-role collector is now implemented and packaged, not a pending RED diagnostic.

Earlier image `2618f015`, source `d5e9dea8`, produced original-selection failure `ec9c5238a28d4d829d7db9a59e0701ad`, with dead pinned emulator and pending launcher. Its frozen selected stderr diagnostic was available and untruncated, 45,900 bytes / 171 complete payload lines, with no supported role. That historical result is unchanged.

Earlier image `sha256:4d1415b32fb2642f66df9e8b892228ea747edece78d5f08d8564b90cd2ef83a0`, source `worktree-sha256:5e95f793efd93fb78e4f6cd02316522caee4fda0f0d97b96fc0680e72ebeb32c`, passed the stock-preserving build and independent saved-image verification, 112,729 unchanged stock paths / 21,792 additions, and exact target load. Actual original-selection run `758aec16fd494385bd16ea467efcea0c` still failed with dead pinned emulator before chord, launcher pending and native consumption untested. Its frozen diagnostic selected 46,031 available, untruncated bytes and 171 complete stderr payload lines, with no supported role. Coordinator verified eight artifacts, owner-only 0700/0600 permissions, original selection byte identity, 24 unchanged stock hashes, frozen failure/cleanup retention, cleared private reader and both cleanups without forced emulator teardown. Four-minute bounded read-only target journals contained zero coredump records and 17 kernel records, without a DuckStation kernel fault or NVIDIA Xid. None of those absences excludes a crash or graphics cause. Raw private bytes were not retained and cannot be reclassified.

Earlier packaged image `sha256:b4e10a7fcb33a5f297e20ff1259c3dbfe99504e9ceed0391f8130ed236c745a1`, source `worktree-sha256:bd37c7c93f78e741aafa3342fabe622474d510962bafd4dc9d9a175a368b55a4`, includes the coordinator-verified graphics-role extension and passed stock-preserving build, independent saved-image verification and exact target load. Run `48109b298de1404093f054af08877cc7` matched `duckstation-gl-context-create-failed` and `duckstation-egl-display-failed` before the chord. Its first provider observation was unavailable. The corrected observer then sampled 31 times in normal original-selection run `017c73ea7bc548daa209888d878443c7`, matching native namespace PID798/start188168418. First mappings were stock GLX/glcore/glsi590.48.01; latest mappings were injected EGL/eglcore570.195.03, matching host/kernel570.195.03. Generated renderer was OpenGL and both injected GBM predicates were true. That run still died before the chord with the same two roles. All eight artifact hashes,24 stock hashes, unchanged selection, frozen diagnostics, private-reader clearing and both cleanup gates were coordinator-verified. Mixed provider selection is proved on that generation; its full causal role is not. First/latest samples do not establish simultaneous residency or successful API use.

Historical image `sha256:36adce3573a724426f0271f83a08dfc97fcd83a44c5b67fa1a2d6380dd30e6e4`, source `worktree-sha256:eae32adecd2be012b683e5c3c48e7fd4392f39bcdd95a803f03faccace0a2e9e`, includes the [GLX preload correction](../docs/completed/specs/wolf-integration/research/duckstation-startup-failure.md#observed-mixed-provider-selection-and-source-correction) and passed stock-preserving packaging, saved-image verification and target loading. CUDA stays first in its architecture-aware shim, GLX follows and external entries remain last. Original-selection `8d3697acd93642e9991966f85d84804c` and passive observation `14a89ec05cdc4df791f512bd63019a28` failed before chord. The latter's 32 samples bind native PID798/start188452504 and show OpenGL, both GBM predicates, the GLX-preload token and Qt xcb; EGL_PLATFORM/QT_XCB_GL_INTEGRATION were unset. Latest sampled providers included injected570 EGL/eglcore only. This is not continuous loader history or proof of preload effect. Original selection, 24 stock hashes, eight artifacts, reader closure and both cleanups passed. The executable was removed; private method/report and linked research retain the history.

Read-only stock `chdman info` and `verify` returned zero for the unchanged UID 1000-readable original 484,093,639-byte CHD with CD-ROM metadata. All four stock-selected BIOS files were readable and 524,288 bytes, within pinned accepted sizes; the universal PSP choice overrides regional choices. These are structure/readability/size observations, not PS1/protection or firmware compatibility and not boot. The exact-owned-container systemd-coredump metadata query returned no records, which does not prove nonsignal exit.

[Pinned-source startup research](../docs/completed/specs/wolf-integration/research/duckstation-startup-failure.md#demonstrated-nvidia-gbm-selection-failure-and-correction) has a causal EGL-X11 A/B, not a renderer switch. On unchanged image2618/source d5e9, supervised run `c90e2f5e947e41bb9cc61a828cf8909d` used ordinary non-root app startup, the stock DuckStation LD path and explicit `eglGetPlatformDisplayEXT` with `EGL_PLATFORM_X11`. Baseline failed before acquiring an EGL display with `EGL_BAD_ALLOC`,0x3003. A fresh child adding only `GBM_BACKEND=nvidia-drm` and `GBM_BACKENDS_PATH=/usr/nvidia/lib/gbm` initialized NVIDIA EGL1.5 and made a requested desktop OpenGL4.6 context current on a matching X11 window/surface. The4.6 value is requested, not a queried GL version. Only the fixed arm mapped the NVIDIA GBM allocator. Both children exited normally; all owned cleanup passed. The coordinator verified both owner-only artifacts. This explicit-platform probe is not DuckStation's display-acquisition route or Qt startup; its retained `egl-investigation.json` claims no emulator exit coverage or frontend qualification.

The [pinned NVIDIA EGL-X11 source](https://github.com/NVIDIA/egl-x11/blob/cad025e58ac53b8a6668f573b7cf7ed36c844a38/src/x11/x11-platform.c#L1106-L1122) calls `gbm_create_device` and rejects a non-NVIDIA backend. The stock GBM library searches `/usr/lib/gbm`, where only `dri_gbm.so` is present; the injected driver supplies the valid NVIDIA allocator. The packaged GBM correction shares the existing selectors between bridge and app instead of setting them only for the bridge. It did not change other graphics/LD/JSON behavior or stock default OpenGL; the later packaged GLX preload correction is described above. This does not diagnose all Docker OpenGL. The working-app database `PermissionError` is a separate generated-output prerequisite already fixed in the updated image. The user's manual Vulkan startup is not suite qualification, and Vulkan is not the selected workaround.

Historical acquisition-only run `c4d19e69488a44b180535fbb7423df19` completed in11.06 seconds under inspected normal Session as UID1000/GID1000. Direct explicit X11, pinned GLAD/client gating and child-only `EGL_PLATFORM=x11` all acquired explicit EGL-X11 without fallback. Both Duck arms advertised EXT/KHR X11 and found the EXT function. Each mapped injected570 CUDA/GLX/EGL and egl-xlib/xcb1.0.3. Children exited0 and reaped without force; cleanup, independent absence and artifact checks passed. This did not qualify Qt/DuckStation output or shortcuts, and did not justify an X11 override.

The acquisition executable and temporary admissions were removed. The later tracing/matching-window/corrected-Qt sequence remains in [startup research](../docs/completed/specs/wolf-integration/research/duckstation-startup-failure.md#corrected-qt-visual-actual-surface-success). HUD-disabled surface success did not resolve the separate HUD-enabled acquisition failure. The wrapper still preserves HUD settings and refuses failed OpenGL discovery. The maintained PSX fixture instead declares the supported no-bezel launch above, matching beta; its results cannot qualify MangoHUD-enabled decorations.

The [existing selected-stderr protocol](../docs/completed/specs/wolf-integration/research/duckstation-startup-failure.md#small-supported-role-protocol) separately adds fourteen fixed graphics/crash roles to the original five, with no schema change. It recognizes exact GPU-device errors, nested EGL/GLAD failures, specific EGL attempt failures and the Linux crash-handler SIGSEGV/SIGBUS/abort lines. It discards interpolated values, pointers and backtrace frames; source filenames do not prove loaded modules. A role is an untrusted observation, never authenticated cause or exit acceptance.

The extension preserves stock line596 stderr isolation, stops at the next logger envelope, and examines only complete selected payload lines within the latest 64 KiB / 256-line limits. It does not inspect stdout context-success messages, command/environment prelude or source echoes. The existing single 0.25-second settle only follows observed pre-chord death/completion; one frozen observation survives cleanup and the private buffer is cleared. Missing or unmatched roles cannot exclude EGL, GLAD, GPU, media, BIOS or other causes. No diagnostic vetoes valid combined shortcut observations or makes dead startup pass.

Final host verification passed **1,038 tests, 11 skipped** in 79.23 seconds; the coverage run passed in 107.46 seconds. Complete-source application line coverage is **39.46%, 3,209 of 8,132 lines across all 26 files**, under the explicit spec-only exception, not coverage compliance. Earlier authenticated two-screen selector smoke, 35 isolated startup/process controls and seven runtime tests retain their own limits. Mandatory all-files hooks retain the approved existing-file failures; [current tooling](../docs/current/tooling.md#current-configuration) records counts. Final private evidence is under `output/integration/duck-test-fix-cbc1f9f1a064439aa0a4f3f72b2f57a9/`.

Final maintained CLI runs independently passed on image `sha256:109c14e2c097e3b53d8feef6afb65dfddae09c2e3cb3b7f5f3ce4423a7c76e9c`, source `worktree-sha256:175676dc4cbb761031dd423ee41c88e22dfeccf63d008884cea44cefc37e768e`: OpenGL `8e6ca8810b3c45ac827b89c0a044e79f` used automatic live visual0x7d; Vulkan `0476b65d193b4b4e906f3d5f2e209939` performed no visual discovery/correction. Both used the original supported selection, separate disposable state and ordinary CLI without temporary seed helpers. Actual backend mode, rendered PlayStation startup, suite SDL consumption, native Guide+Start press/release, pinned exit, launcher0, 11 retained artifact hashes/modes per run and both cleanup layers passed. Independent discovery confirmed exact resource absence, zero sessions/lobbies and unchanged protected config. Private renderer-specific qualification JSON accompanies each report. Packaging preserved all 112,729 stock paths, with 21,799 isolated additions, and passed independent saved-image verification and exact-ID target load. These passes qualify the supported `psx.bezel=none` fixture, not MangoHUD-enabled bezels or gameplay. [The controlled comparison](../docs/completed/specs/wolf-integration/research/duckstation-startup-failure.md#native-regression-invocation-and-fixture-correction) explains the forced NV12 invocation and default-bezel fixture defects; earlier failed runs retain their results. Beta remains on operator-selected image15933; no profile change or restart was needed.

```sh
uv run batocera-gow-native plan --tier psx-smoke
uv run batocera-gow-native plan --tier psx-vulkan-smoke
uv run batocera-gow-native run \
  --authorize-native --native-authorized-target "$BATOCERA_GOW_SSH_TARGET" \
  --native-authorized-root "$BATOCERA_GOW_HOST_ROOT" --host-root "$BATOCERA_GOW_HOST_ROOT" --tier psx-smoke \
  --build-manifest output/gow-full-x86/build-manifest.json \
  --stock-manifest output/gow-full-x86/stock-manifest.json \
  --render-node /dev/dri/renderD128 \
  --video-caps 'video/x-raw(memory:CUDAMemory)'
```

Supply required independently inspected `--infrastructure-container` arguments on every invocation. Use the retained owner-only `--reproduce-selection output/integration/<original-run-id>/psx-duckstation-selection.json` for both modes; do not reroll failures. Repeat the illustrated OpenGL invocation with `--tier psx-vulkan-smoke` and the same verified manifests/selection; the runner allocates a separate owned run/state/report. The unchanged finite startup/live/exit budgets passed for the recorded PSX selection and image, not every disc. The same v3 live barrier, native press/release, pinned termination, launcher zero, evidence/input release and both independent cleanups apply. Gameplay, MangoHUD-enabled bezels, other shortcuts, graceful shutdown and post-exit frontend recovery remain untested. Public case templates remain unqualified/null; private qualifications distinguish `duckstation-qt/OpenGL` from `duckstation-qt/Vulkan`, while installed executable/version identity remains the unchanged stock Qt identity.

## xemu exit smoke

`--tier xbox-smoke` selects only `xbox-xemu`. It preserves all five other emulator subsets and the independent frontend/five-receiver tier. Selection uses the exact stock `/userdata/roms/xbox` folder and `.iso .squashfs` extensions under the inspected existing read-only ROM mount. Raw `.xbe`, `.xiso` and another system's disc are not eligible. Extension eligibility is not proof of XISO structure or boot compatibility. Missing/empty/unsupported-only media skips visibly without exit coverage. Eligible media with missing firmware, an unqualified HDD seed, metadata/backend/config failure or failed launch/exit remains nonpassing.

The unchanged [stock generator](https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/generators/xemu/xemuGenerator.py) runs `/usr/bin/xemu -config_path /userdata/system/configs/xemu/xemu.toml`. The [stock configuration](https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/generators/xemu/xemuConfig.py) puts the disc in `sys.files.dvd_path`, not emulator argv. The probe checks that generated path and an actual open disc FD. For squashfs it observes stock's read-only mounted selection and its loop backing; it never mounts or unpacks content itself. A stock mount failure is an attempted-case failure. No extra capability or content mount is added.

Before launch output can qualify, `mounted_media.inspect_xiso` reads only the actual resolved ISO's metadata after the selected ISO or stock squashfs backing/read-only attribution. It requires a complete 2048-byte descriptor at sector 32, both `MICROSOFT*XBOX*MEDIA` signatures at descriptor offsets `0` and `0x7ec`, little-endian unsigned root-sector and byte-length fields at `0x14` and `0x18`, and a root extent within the actual image size. Variable root locations, byte lengths, empty roots and nonzero timestamp/reserved fields are allowed. No fixed sector-264 root or 64 KiB image-size alignment is imposed. An invalid eligible selection fails execution, never becomes a no-media skip and is not rerolled.

The descriptor layout and empty-root semantics follow pinned [xdvdfs volume](https://github.com/antangelo/xdvdfs/blob/6b05af7fba79d567ef8c9698c8702b8d782248b8/xdvdfs-core/src/layout/volume.rs), [volume reader](https://github.com/antangelo/xdvdfs/blob/6b05af7fba79d567ef8c9698c8702b8d782248b8/xdvdfs-core/src/read/volume.rs) and [region](https://github.com/antangelo/xdvdfs/blob/6b05af7fba79d567ef8c9698c8702b8d782248b8/xdvdfs-core/src/layout/region.rs) sources, corroborated by [extract-xiso](https://github.com/XboxDev/extract-xiso/blob/b72e5b60d598ec6df80534cda19cdcd4361aa18c/extract-xiso.c). [Official xemu disc documentation](https://xemu.app/docs/disc-images/) requires XISO rather than conventional ISO and excludes full redump images. Pinned xemu [disc attachment](https://github.com/xemu-project/xemu/blob/fc9980d2962cbec656253106ea2e121fab1e68d4/ui/xemu.c#L1396-L1412) uses raw format and [ATAPI reads](https://github.com/xemu-project/xemu/blob/fc9980d2962cbec656253106ea2e121fab1e68d4/hw/ide/atapi.c#L92-L111) use unshifted LBA times 2048. This inspector does not scan shifted game partitions, convert images, walk their filesystem or read executables.

The final pre-chord `transition.stock_launch_display.disc_format` snapshot carries those public numeric fields and the existing selected-media identity, including for a squashfs archive's actual resolved inner ISO. The host requires complete, correctly typed and bounded evidence bound to `report.media.identity`; teardown observations cannot replace this launch snapshot. This is structure proof only. Valid metadata and an open disc FD cannot establish guest bootability, selected-title rendering or gameplay, and BIOS/HDD-dashboard pixels alone do not supply that proof.

MCPX and compatible unsigned-capable BIOS are operator inputs at `/userdata/bios/mcpx_1.0.bin` and `/userdata/bios/Complex_4627.bin`. The probe hashes only those read-only mounted files, never copies or exports their bytes. Readable files do not establish BIOS compatibility. After the existing coordinator inspection/lease establishes the owned native home, the probe exclusively seeds fresh `/userdata/saves/xbox/xbox_hdd.qcow2`. Existing HDD, EEPROM or xemu config is refused rather than adopted. Writable HDD/EEPROM/config/save/cache state remains under identity-checked disposable userdata; production state is never a source.

The sole implemented HDD route is `unchanged-stock-private-disposable-use`. It copies `/usr/share/xemu/data/xbox_hdd.qcow2`, exactly 4,521,984 bytes with SHA-256 `eb35d069715dfc0d37cfac086a0b73a89a02e8f12519cd8eda82ad479d1a4eed`. The seed is an 8 GiB virtual QCOW2 with a legacy dummy dashboard, not an empty disk. The [retained first-party research](../docs/completed/specs/wolf-integration/research/standalone-input-fixtures.md#actual-stock-hdd-follow-up-2026-10-30) establishes the stock recipe, intended origin and affirmative copyright-free/use statement. Complete release-byte correspondence and the embedded dashboard's redistribution terms remain unproved. This private disposable stock-use route makes no new public redistribution claim and adds no operator-HDD CLI, acquisition or public fixture.

The actual installed executable was observed with SHA-256 `bfc5c55c5c88e822599eb84a67497831e39f30a6c3621a3a7fa8714b469e6992`. Its early records reported `0.8.134`, commit `fc9980d2962cbec656253106ea2e121fab1e68d4` and date `Fri May 29 06:08:30 AM UTC 2026`. That isolated headless metadata operation exited1 because SDL X11 was unavailable. It is identity evidence, not a successful helper or native case. Do not replay it unchanged or substitute package metadata for missing runtime records.

Before launching the game, the maintained probe independently runs `-version` under the case's authenticated X11 with its own temporary config, because [xemu startup](https://github.com/xemu-project/xemu/blob/fc9980d2962cbec656253106ea2e121fab1e68d4/ui/xemu.c#L1307-L1336) registers settings-save even in informational mode. The [QEMU option branch](https://github.com/xemu-project/xemu/blob/fc9980d2962cbec656253106ea2e121fab1e68d4/system/vl.c#L3370-L3372) exits0 if reached after SDL initialization. The helper has a five-second wait, bounded private draining and independent teardown. Parsing accepts one unique complete version/commit/date record among bounded diagnostics; nonzero, missing, malformed, duplicate or oversize output fails without a package fallback. The successful exit0 test fixture is source-grounded, not an observed native success. Package provenance remains separate in `package_source`, naming the [Batocera recipe](https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/emulators/xemu/xemu.mk) and its v0.8.134 source.

Native consumption requires the pinned xemu process to map the inventoried 64-bit `/usr/lib/libSDL3.so.0.4.2` and actually open the suite pad. The separate SDL2 discovery/profile record is not SDL3 consumption. A bounded observer uses the [SDL3 joystick/GUID ABI](https://github.com/libsdl-org/SDL/blob/release-3.4.2/include/SDL3/SDL_joystick.h) to match the suite's real node and GUID among discovered gamepads. That GUID must be unambiguous and match the effective stock `input.bindings.port1` and SDL environment mapping. It is observed, not assumed equal to SDL2 or rewritten to force success. Stock `XDG_CONFIG_HOME`, `LC_NUMERIC`, firmware/HDD/EEPROM/DVD paths, suite button/axis/hat mapping and the unchanged xemu exit context are checked. There is no guest-input oracle, Qt assertion, RetroArch driver/core or final-keyboard-FD requirement.

Actual output combines the validated selected-disc structure and FD, active fullscreen normal nonmodal/nontransient SDL render window and nonblank authenticated server pixels. The source-defined xemu title is not a boot/gameplay oracle. The same v3 live/no-exit barrier, native Guide+Start press/release, pinned-emulator termination, stock launcher zero, released input, retained evidence and independent owned cleanup apply. Stock logging/classification stays diagnostic, not a separate gate. No direct final keyboard input, emulator exit command or signal supplies success; cleanup kills remain failures.

The host regressions cover actual stock-format selection, read-only XDVDFS descriptor/extent validation and invalid selected-media failures, strict identity-bound host format evidence, private reproduction/change refusal, bounded runtime-record parsing, real-filesystem missing/unqualified-seed and foreign-state refusal, the standalone SDL render predicate and the shared coordinator lifecycle. Synthetic nonbootable metadata and fixture process observations do not qualify native SDL3, firmware, boot or exit. The coordinator's source checks include:

```sh
uv run pytest -q \
  tests/integration/local/test_native_integration.py \
  tests/integration/local/test_mounted_media.py \
  tests/integration/local/test_emulator_media.py
GOW_TEST_LIBX11="$HOST_LIBX11" \
  uv run pytest -q \
  tests/integration/local/test_native_desktop.py
```

After separately authorized packaging and image verification, the coordinator can use the existing SSH/content settings and independently inspected infrastructure arguments:

```sh
uv run batocera-gow-native plan --tier xbox-smoke
uv run batocera-gow-native run \
  --authorize-native --native-authorized-target "$BATOCERA_GOW_SSH_TARGET" \
  --native-authorized-root "$BATOCERA_GOW_HOST_ROOT" --host-root "$BATOCERA_GOW_HOST_ROOT" --tier xbox-smoke \
  --build-manifest output/gow-full-x86/build-manifest.json \
  --stock-manifest output/gow-full-x86/stock-manifest.json \
  --render-node /dev/dri/renderD128 \
  --video-caps 'video/x-raw(memory:CUDAMemory)'
```

Supply required `--infrastructure-container` arguments exactly as for the other tiers. Once media is selected, retain and reproduce `output/integration/<run-id>/xbox-xemu-selection.json`; do not reroll a failure. The passing run below exercised the common 40-second startup, two-second live barrier and 15-second exit budgets for its selected inputs only. Before-exit and accessible failure PNGs, sanitized selected logs and private records use the same owner-only transfer/cleanup gates. No post-exit frontend is required. Public case templates remain unqualified/null even when a private selected run qualifies. Guest input, gameplay, menus, other shortcuts, graceful shutdown, save persistence and physical Moonlight forwarding remain untested.

Original-selection run `7094e0cca52148729e12d458d40bb016` passed on stock-verified image `sha256:128ebf123b3a78a2162e90fbcc51dbaeab29203758729d8232c0dd8596e46572`, packaged source `worktree-sha256:baab3bf61c158ef7689575cbdeab5b5603f7665ae4803e69dca9fc39899976df`. The coordinator inspected the real 1280×720 Xbox startup PNG and verified all 11 artifact hashes/modes and the ordered before-chord, pressed, released and launcher checkpoints. The same pinned xemu stayed live through the two-second barrier, native Guide+Start pressed and released through the suite gamepad, adapter and unchanged stock hotkeygen, its thread-group pidfd ended and the stock launcher returned zero. Actual SDL3 and stock configgen consumption, valid selected XDVDFS, read-only MCPX/BIOS, the owned stock HDD, stock integrity, released input and both independent cleanups passed without forced emulator teardown.

The private selected-run qualification is `output/integration/7094e0cca52148729e12d458d40bb016/xbox-xemu-qualification.json`. The coordinator created it through the existing qualification API and strictly parsed its JSON, mode `0600` in a `0700` run directory. Keep selected media names, paths and identities private. Earlier run `76ba8d09e6064bfb8b79fc2d73118037` remains failed with `ProcessLookupError` at `chord-released`, no passing pinned-exit/launcher result and forced emulator teardown. The later thread-group lifetime repair and successful run do not retroactively prove that failure's cause. This is observed shortcut exit, not gameplay, graceful shutdown, frontend return, physical Moonlight forwarding or a full-baseline pass.

## Explicit content configuration

`BATOCERA_GOW_ROMS_ROOT` and `BATOCERA_GOW_BIOS_ROOT` are absolute bind sources on the Docker host. They need not exist on the coordinator's local filesystem. Neither variable selects a place to search for unmounted content. Neutral values are in [example.env](../example.env).

If using an ignored operator `.env`, export it deliberately in a POSIX shell:

```sh
set -a
. ./.env
set +a
uv run batocera-gow-media mounts
```

All installed host commands, including media, load dotenv only when explicitly selected and preserve `os.environ`. `batocera-gow-media` invokes `batocera_gow.host.media`; `runtime.mounted_media` remains the shared library. For example, `uv run batocera-gow-media --env-file .env mounts` resolves one snapshot without SSH. Media `--roms-root` and `--bios-root` override exported environment, then selected-file values, then defaults. Put these host options before the subcommand. Deliberate shell sourcing above remains supported. Never put key contents in `.env`, source, reports or examples. `mounts` prints desired binds only; Wolf TOML does not expand environment variables. The shared `ContentRoots` contract constructs these fixed read-only destinations:

- `/home/retro/userdata/roms:ro`
- `/home/retro/userdata/bios:ro`

`ContentRoots.from_environment(mapping).wolf_mounts()` supplies mount construction for the native coordinator and host registration/remote tools. Before native selection, the coordinator parses the complete Docker `Mounts` observation with `EffectiveMount.from_docker(item)` and calls `roots.validate_mounts(observations)`. Missing, duplicate, non-bind, writable, source-mismatched or nested shadowing content mounts are errors. Desired TOML is not effective-mount evidence. Shared configuration adds no mounts or permission to rewrite the deployed app.

Local `catalog`, `select` and `reproduce` do not require SSH settings or connect to a target. Native execution requires `BATOCERA_GOW_SSH_TARGET` without a personal fallback; optional `BATOCERA_GOW_SSH_IDENTITY_FILE` denotes a path, never key contents. Native permissions are not granted by sourcing `.env`.

## Stock catalog and local selection

```sh
uv run batocera-gow-media catalog
uv run batocera-gow-media catalog --system psx
```

The maintained [original stock XML](assets/media/stock-es_systems.cfg) was recovered read-only from `./usr/share/emulationstation/es_systems.cfg` in the retained `output/gow-full-x86/assembly/stock-root.tar`. Its original 212,533 bytes have SHA-256 `401638d6cbc26e574456f36a4b59007b823b576b35422f519640be9bfd3efc23`, for Batocera 43.1 at revision `155c2d8d304cbb53db52e9479dcf683392821d5c`. Loading verifies that exact hash before parsing. Stock declarations remain unchanged. No ROM or firmware was extracted.

There are 253 advertised system/category IDs, 98 emulator IDs, 233 emulator/core pairs and 477 system/backend/core mappings. They are declarations, not proof that executables are installed or working. Tests reconcile exact ID/extension/mapping equality with both retained research inputs:

- [Packaged inventory](../docs/completed/epics/repository-maturation/research/artifacts/packaged-system-inventory.json)
- [Candidate catalog](../docs/completed/epics/repository-maturation/research/artifacts/fixture-candidate-catalog.json)
- [Readable research index](../docs/completed/epics/repository-maturation/research/artifacts/fixture-candidate-index.md)
- [Fixture research and licensing boundaries](../docs/completed/epics/repository-maturation/research/emulator-fixtures.md)

`media_catalog.load_catalog().system(system_id)` returns the exact stock directory, extensions, command and backend/core mappings. The `imageviewer`, `library` and `recordings` categories point outside `/userdata/roms`; they remain in the catalog but cannot authorize ROM-library selection. Utilities, ports and data-dependent categories retain their research dispositions rather than invented cartridge fixtures.

Selection requires an explicit `--roms-view` naming the existing ROM mount as seen in the executing filesystem namespace. It is not inferred from the Docker-host source variable. For example, on a separately authorized local view of that existing mount:

```sh
# Create a fresh owner-only directory outside the media mount for each attempt.
# These neutral paths must be replaced by an authorized existing mount view.
mkdir -m 700 output/integration/local-media-attempt
uv run batocera-gow-media select \
  --system nes --roms-view /mnt/existing-roms \
  --record output/integration/local-media-attempt/selection.json
uv run batocera-gow-media reproduce \
  --roms-view /mnt/existing-roms \
  --record output/integration/local-media-attempt/selection.json
```

The parent `output/integration` must already exist; each attempt directory must be new and owner-only. Do not create an extra test-only content mount to make the example work. Use the temporary synthetic-byte smoke command above when no existing authorized view is available.

`inspect_media(stock_record, roms_view)` searches only that record's actual directory below the supplied root, including its contained subfolders. Missing, empty and unsupported-only system folders return exactly `Skipped: no compatible mounted media`. Incomplete supported descriptor sets are rejected and counted. A missing root, a non-directory system path, inaccessible entry, symlink or discovery failure is an error, not media absence. Discovery and reading reject symlinks in path components and special files. Selection is read-only.

Supported relationships include CUE `FILE` tracks, M3U playlists with nested disc descriptors, GDI tracks, TOC file references, MDF/MDS pairs and CloneCD CCD/IMG with optional SUB. Directory-format entries retain all their contained regular files and must be nonempty. Referenced entries are not independently randomized as loose components. Companions must remain within the selected system directory. Relative parent references that stay inside it are supported; absolute or escaping references, cycles, empty/malformed descriptors and incomplete sets are refused. Descriptor text is UTF-8 with optional BOM and bounded to one MiB. Unsupported legacy descriptor encodings remain ineligible, not silently rewritten.

An extension match or complete companion set is only eligibility. Discovery does not unpack or internally validate compressed archives, interpret directory data as a console filesystem, or establish Xbox XISO layout. The xemu execution path separately checks bounded XDVDFS structure on the actual ISO, including stock's mounted squashfs member. Backend compatibility, firmware and actual stock launch/display still need native qualification. Missing firmware for an eligible entry, invalid selected-image structure and actual launch/exit failures must not be changed into no-media skips.

`select_media(eligibility, choose_index)` chooses exactly once, hashes every selected member and computes a stable identity over the system, relative entry, member paths, lengths and SHA-256 hashes. Callers inject deterministic choice in tests; the CLI uses `secrets.randbelow`. The selection is not retried after a read, launch or assertion failure. Keep its private record and use `reproduce`, which rechecks only that chosen eligible entry and refuses changed members/digests. It never substitutes a fresh random candidate.

This is not an atomic library snapshot. Recheck the private selection before native use, and do not mutate host content during an attempt. A read-only container bind does not prevent an authorized host process from changing its backing files.

Private selection records contain filenames and relative paths and therefore stay private, even though they contain no media bytes. `write_selection` creates an exclusive mode-0600 file under an existing owner-only directory; it refuses overwrites and symlink paths. CLI stdout exposes only status, not selected filenames, paths or digests. Do not copy these records, screenshots, private logs, ROMs or firmware into source, images, distributed bundles or public documentation. Ignored output is not permission to publish. There is no automatic upload, pruning or private-content export.

## Executable cases and qualification

[Case declarations](assets/media/cases.json) are maintained separately from historical research. Each names its stock system/backend/core/variant, route, formats, rights disposition, firmware/data prerequisites, gaps and initial qualification. These reusable media-agnostic declarations retain `qualification: {"status": "unqualified", "identity": null}`. Actual identity-bound qualification belongs in owner-restricted run storage, not the declaration. Standalone records retain the stock catalog's core label, such as `duckstation/duckstation`; it does not mean a libretro core.

The unused `research_catalog` metadata in these frozen image-bound declarations retains its original pre-completion path as historical provenance. The [preserved catalog](../docs/completed/epics/repository-maturation/research/artifacts/fixture-candidate-catalog.json) is the current research location; lifecycle completion does not rewrite qualified build inputs.

The complete old-layout baseline and subsequent expanded replay qualify NES, SNES, Atari2600, DuckStation OpenGL/Vulkan and xemu on image109c14e2/source175676dc. Six exact `<case>-qualification.json` records are retained beside `output/integration/15a1f2112dad4487905100cb4a5d8615/report.json`; expanded results are `output/integration/c85e22e7deb046c58c8cce849841ee58/report.json`. They bind actual selected media, backend/renderer, firmware, suite profile and `stock-native-observed-exit-v3` assertions; public templates remain unqualified and media-agnostic. Mega Drive remains a nonblocking no-compatible-media skip, not native exit coverage. The table retains each backend's earlier qualification and input/gap details; those earlier image-bound records do not transfer to another image. RPCS3/Xenia remain unqualified and unrun. Historical failures remain failed, and private identities/selection contents must not be published.

| System/backend/core                                          | Input route and stock format                                                                                              | Rights and firmware/data requirements                                                                                                                  | Launch/display                                                      | Observed Guide+Start exit | Qualification identity and missing work                                                                                                                                                                                                       |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------- | ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NES / libretro / fceumm                                      | Existing read-only private selection via `--tier nes-smoke`; stock NES formats; optional public lead unused               | Authorized private use only; nothing distributed; ordinary cartridge needs no external BIOS                                                            | Passed, retained 1280×720 output                                    | Passed, v3                | Run `d0f90ed2198440ec8c8978c5c77e4d28`; exact media/image/source/backend/profile/assertion in private selected-run qualification record; no gameplay or graceful-exit claim                                                                   |
| SNES / libretro / snes9x                                     | Stock `snes` folder via `--tier snes-smoke`; `.sfc` and other declared formats; optional PVSnesLib lead                   | Authorized private use; public font/SDK/build review open; ordinary cartridge needs no BIOS                                                            | Passed, retained rendered output                                    | Passed, v3                | Run `57bb80bdf7ac42e59c06c790462f0e0c`; private original-selection qualification on historical image `128ebf12` / source `baab3bf6`, as recorded above; public template remains unqualified/null                                              |
| Mega Drive / libretro / genesisplusgx                        | Stock `megadrive` folder via `--tier megadrive-smoke`; `.bin`, `.gen`, `.md` and other stock formats; optional SGDK lead  | Authorized private use; public binary/source/resource review open; base cartridge needs no Sega CD firmware                                            | Skipped, no compatible mounted media                                | Unrun, no exit coverage   | Run `f7f492e796bc4f99b07f96dc29e4be03`; actual absence skip on historical image `128ebf12` / source `baab3bf6`; native launch, consumption and exit untested; public template remains unqualified/null                                        |
| Atari 2600 / libretro / stella                               | Stock `atari2600` folder via `--tier atari2600-smoke`; `.a26`, `.bin`, `.zip`, `.7z`; optional controls.a/color-bar leads | Authorized private use; optional include/build rights unresolved; ordinary cartridge needs no BIOS                                                     | Passed, retained rendered output                                    | Passed, v3                | Run `38c60d5067be4352b2cc6a91a4be4b9f`; private original-selection qualification on historical image `128ebf12` / source `baab3bf6`, as recorded above; public template remains unqualified/null                                              |
| PS1 / duckstation / duckstation: OpenGL and Vulkan           | Stock `psx` folder via `--tier psx-smoke` and `psx-vulkan-smoke`; CUE/IMG/MDF/PBP/TOC/CBN/M3U/CHD/ISO/CCD                 | Authorized private use; public built-disc rights not cleared; external supported BIOS required; same immutable image/media, independent state          | Both passed rendered startup; actual backend independently verified | Both passed, v3           | GL `8e6ca881` and Vulkan `0476b65d`, image109c14e2/source175676dc; private variant qualifications beside reports. Supported no-bezel fixture only; MangoHUD-enabled bezels and gameplay unqualified. Public templates remain unqualified/null |
| Xbox / xemu / xemu                                           | Stock `xbox` folder via `--tier xbox-smoke`; `.iso`/`.squashfs`, not raw XBE; optional nxdk lead unused                   | Authorized private media; read-only MCPX/compatible BIOS; fingerprinted unchanged stock HDD only in private disposable userdata; no new public fixture | Passed, retained 1280×720 startup                                   | Passed, v3                | Run `7094e0cca52148729e12d458d40bb016`; exact media/image/source/backend/profile/assertion in private selected-run qualification; public template remains unqualified/null                                                                    |
| PS3 / rpcs3 / rpcs3, nonblocking expanded                    | Existing `.ps3`, `.psn`, `.iso`, `.squashfs`; PSL1GHT source-only lead                                                    | Authorized private use; mixed helper/toolchain terms unresolved; operator PS3 system software                                                          | Unrun                                                               | Unrun                     | Unqualified; build/packaging/firmware/profile gaps; guest Start self-exit is not native exit proof                                                                                                                                            |
| Xbox 360 / xenia / xenia, nonblocking expanded               | Existing `.iso`, `.xex`, `.xbox360`, `.zar`                                                                               | Authorized private use; no qualified public visual fixture; no invented firmware prerequisite                                                          | Unrun                                                               | Unrun                     | Unqualified; record packaged version and Wine/native route; CPU/log hwtests and unsupported xsdk presentation are not visual proof                                                                                                            |
| Xbox 360 / xenia-canary / xenia-canary, nonblocking expanded | Same advertised system formats, separately qualified backend                                                              | Authorized private use; no qualified public visual fixture; no invented firmware prerequisite                                                          | Unrun                                                               | Unrun                     | Unqualified; xenia results do not qualify canary                                                                                                                                                                                              |

Nine declared backend cases do not cover the other 468 advertised mappings. The other 245 system/categories have no maintained executable case declaration here. The full 253-entry research catalog remains visible; its 51 redistribution leads, 39 source leads, 111 restricted prerequisites, 41 unresolved entries and 11 non-ROM dispositions are research, not distribution clearance or passing coverage. Do not count one fixture as qualification of all of a system's cores.

`media_qualification.evaluate_qualification` separates actual use permission, applicable public distribution clearance and already-validated native observations. Private authorized media needs no public game source or redistribution permission. Distributed fixtures require complete source/binary/component/asset clearance. No public fixture is distributed by these assets.

Qualification requires exact case/system/backend/core/variant, catalog, image, source, media, firmware, suite-profile and assertion identities. Already-validated native evidence must show stock launch/output, live pinned identity before native Guide+Start press/release, that same emulator ending, launcher code zero, applicable native-device consumption, stock integrity, retained evidence and successful owned cleanup. Natural-exit log classification and post-exit frontend readiness are not qualification fields. Missing required observations fail; rights or research alone cannot qualify. Changed identities invalidate earlier claims until requalification. The aggregation API consumes validated summaries; it does not acquire or validate processes, PNGs or input causality. The native coordinator owns those observations.

The full `regression` report retains all six required backend dispositions, including independent OpenGL and Vulkan outcomes within DuckStation. The seven variant-selectable smoke tiers are not that full gate. Absent media is visibly skipped and never counted passing. If every selected emulator case skips, the report says no emulator exit coverage and infers no native consumption. Launch-only smoke is not the exit gate. Gameplay, other shortcuts, menus, rewind, save states, physical Moonlight/controller forwarding, client-decoded video and heard client audio remain untested. The independent same-image normal frontend/five-receiver pass does not qualify frontend recovery or another emulator. Changed native runtime inputs require a fresh verified packaged image and actual qualification; host-only report/guide changes do not relabel packaged source.
