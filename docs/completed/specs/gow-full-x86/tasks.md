# Implementation tasks

Historical ledger, consolidated 2026-10-28. The operator considers this effort finished. Earlier reopened, blocked and pending notes below retain the chronology of the original delivery and the 2026-10-26 runtime continuation; they do not reopen QA. See the [completed spec disposition](spec.md) and [current application evidence](../../../current/app.md) for later transport work and sampled operator acceptance. Original checkboxes and evidence limits are preserved.

- [x] Create independent project and verify separate Git metadata.
- [x] Implement complete release assembly, metadata inventory, isolated builder and fixtures.
- [x] Implement Nix bridge closure and runtime initialization/session/frontend with regression checks.
- [x] Implement path guards, immutable SHA/latest publication, and idle-gated profile-aware remote registration.
- [x] Run deterministic tests and smoke checks.
- [x] Commit adapter source in the independent repository.
- [x] Run real release build with full stock inventory proof.
- [x] Publish SHA and latest to GHCR and verify shared digest.
- [x] Pull and check image on remote Wolf host.
- [x] Register the new app only when idle and verify API health.
- [x] Collect available runtime evidence; record interactive QA pending when no client is accessible.

The original checkout and existing Wolf Batocera app/state are out of bounds. No backups or preservation commits. Spec approved for implementation. Each item requires observed verification before checkoff.

Initial delivery reached registration and available diagnostics, but the first real launch failed. The spec is reopened for the runtime correction below. Interactive Moonlight/controller/heard-audio/gameplay/persistence checks remain unverified. Earlier sections preserve initial delivery and resolved blocker evidence.

## Verified evidence

- Unit discovery: 47 tests, one host ALSA prerequisite skip. The same audio test ran successfully inside the builder, seven runtime unit tests with no skips.
- Disposable mounted-state and process fixtures: 19 passed, using actual stock S12populateshare and read-only ROM/BIOS children.
- Publisher fixtures: 10 passed. No registry mutation.
- GPT/FAT/ext4/zstd fixtures passed, including complete secondary content, main directory metadata, hardlinks, xattrs, SHARE ACLs, full boot tree, collision refusal, and missing-layer failure.
- Final archive loaded through Docker and image-save inventory comparison passed for every fixture stock path. Ordinary Docker ADD was observed to lose xattrs and timestamp precision; exact-layer loading replaced it.
- Real 43.1 download checksum verified. Actual assembly reached the storage gate after GPT/FAT inspection, then stopped with 11,351,202,549 extra bytes required at that observation. No full-image success or publication is claimed.
- Failed assembly staging from this run was removed, retaining the verified download. Build orchestration now removes only its own newly created, recognized incomplete staging on failure, so adding storage permits a retry. Existing nonempty unrelated/incomplete staging is not deleted.

## Earlier acceptance blocker, resolved

At this stage the complete-image build and publication/deployment were still unverified. Later sections record their successful completion. Interactive Moonlight, heard audio, controller, gameplay, and relaunch-persistence QA remain pending.

The committed `build.sh` attempt at adapter `01075a76e5de18b884e21ba87efeed47cef841c3` reached the real space gate. That attempt needed 72,246,971,125 remaining bytes and found 59,719,843,840, a deficit of 12,527,127,285 bytes. Its recognized incomplete staging was cleaned automatically; an empty assembly directory was observed afterward. The verified compressed input remains cached.

`publish.sh --dry-run` refused missing build success evidence, and `remote.sh --prepare` refused missing publication evidence. No GHCR publication, remote directory/home creation, config edit, or restart occurred. Source is versioned locally only. No completed-spec archive is created while end-to-end acceptance is blocked.

## Storage prerequisite cleared

The user authorized original-repository build-output deletion and specifically protected unrelated application Docker resources. Generated output directories under `batocera.linux/output/x86_64_gow` and `output/x86_64` were removed. Saved `.config`, `.config.old`, wrapper/config metadata, source, Git metadata, and new-experiment downloads/outputs were retained. Retained top-level file contents, modes and ownership matched their pre-cleanup snapshots.

Six older Batocera test-image tags were removed with `docker image rm --no-prune`. Current Batocera latest/v0.1.0 images and the retained hotkey-test container remain. No global prune, builder-cache prune, container removal, volume removal, or remote operation ran. All 443 shared build-cache records remain. The unrelated application's database container remained running and healthy, with its image retained.

Free space increased from 75,344,457,728 to 291,938,918,400 bytes. The local storage blocker is cleared. The cleanup request is complete; the approved runtime build/publication/deployment remains pending. Detailed cleanup evidence is in `output/gow-full-x86/cleanup-report.json`. No full build was started as part of cleanup.

## Full build and publication verified

The complete official 43.1 image built at adapter `2748e728f3b01eaf5aae12a766ffa9f5c672e0d1`. Both whole SquashFS layers, the entire FAT payload, and the SHARE seed were assembled. Image-save inventory verification matched every one of 112,729 stock paths and allowed 21,782 isolated added paths. The final image ID is `sha256:cace76e1072ae77f43371b1e7d194052a6074be92a426d3939ff6f6a40d38cd7`.

The real publisher pushed `ghcr.io/dafrenchyman/batocera-gow-full-experiment:sha-2748e728f3b01eaf5aae12a766ffa9f5c672e0d1` and `:latest`. Independent `docker manifest inspect --verbose` calls confirmed both resolve to `sha256:a8e7867cdfd6cb2498f97ddb3b8aac12aac00af5be83d693e9b0ce198ed916ed`. The compressed registry layer is 9,649,979,156 bytes. The original image repository was not a publication target.

Disposable networkless containers without state binds passed the packaged static prerequisite check and executed packaged Xwayland, reporting 24.1.14. These do not establish display/audio/input/GPU runtime acceptance.

## Remote registry access blocker

`remote.sh --prepare` reached the experiment-owned deployment checkpoint but could not pull the private GHCR package. A direct SSH Docker pull identified `unauthorized`; credential-mechanism inspection found no Docker config for either the deployment account or `root`. GitHub's authenticated package API confirmed `visibility: private`.

The user selected making this experiment package public. No existing package is in scope. The supported documented control is the package's web settings: **Package settings → Danger Zone → Change visibility → Public**, then confirm the package name. GitHub documents that a public package cannot be made private again.

The available CLI cannot apply this setting: PATCH on the authenticated package endpoint returned 404 and GraphQL mutation introspection exposed only `deletePackageVersion` for package mutations. The browser relay timed out; the separate managed browser has no signed-in GitHub session and displayed the private package as unavailable. That managed tab was closed. No workstation registry credentials were copied to the server.

The remote checkpoint record exists with `registered: false`, no prepared image, and no native `WolfExperimental` home. No Wolf app was added, no config was edited, and Wolf was not restarted. Remote prerequisite, registration, session diagnostics, and interactive QA remain unverified.

Resume after the owner changes visibility on [the experiment package](https://github.com/users/dafrenchyman/packages/container/package/batocera-gow-full-experiment): verify public access, run `experiments/gow-full-x86/remote.sh --prepare`, then `--register` under the existing idle gate. Do not rebuild or republish merely to change visibility. Inspect only experiment sessions and collect their logs after an actual WolfUI/User launch. Existing Batocera state and unrelated application resources remain protected.

## Remote preparation verified; activation deferred

The registry access blocker is cleared. `experiments/gow-full-x86/remote.sh --prepare` succeeded on the authorized remote Wolf host. It pulled SHA and latest, checked them against the publication digest, pulled the digest reference, and passed the packaged prerequisite check in a disposable container without state binds. `output/gow-full-x86/remote-preparation.json` records the prepared image at `sha256:a8e7867cdfd6cb2498f97ddb3b8aac12aac00af5be83d693e9b0ce198ed916ed`, installed Wolf UI revision `34f278be6d556b9fd39bb5bd0d8404a3276c2cbc`, and native home `/etc/wolf/profile-data/user/WolfExperimental`. Preparation does not create or initialize that home.

`experiments/gow-full-x86/remote.sh --register` then refused activation with `activation deferred: active or paused sessions`. No Wolf config was written and no restart occurred. The experiment entry has not been added. Do not poll for idle or stop another user's session.

Both `--inspect-session` and `--collect-logs` completed and reported `{"containers": []}`. There is no experimental session or runtime log to inspect. This is diagnostic collection evidence, not display/audio/input/GPU/gameplay or persistence acceptance. Those checks remain pending user QA after registration and an actual WolfUI/User launch.

Next action after the operator ends active/paused Wolf sessions is `experiments/gow-full-x86/remote.sh --register` from the new repository. The intended entry remains `Batocera full x86 experiment` in profile `User`, with runner `WolfExperimental`. Existing Batocera configuration/state and unrelated application resources remain unchanged.

## Registration and API verification complete

After the operator restarted GoW-Wolf, `experiments/gow-full-x86/remote.sh --register` succeeded under the idle gate. It added exactly one `Batocera full x86 experiment` under profile `user`, pinned to the published digest, restarted only `wolf-wolf-1`, verified API health and the new app, and verified preservation of all preexisting profile/app values. The registered native home remains `/etc/wolf/profile-data/user/WolfExperimental`, with no explicit home bind. `output/gow-full-x86/remote-registration.json` records success.

Both `--inspect-session` and `--collect-logs` again completed with `{"containers": []}`. The experiment has not launched, so runtime initialization, visible ES, NVIDIA rendering, sound, controller hotplug, games, and stop/relaunch persistence are not claimed.

Operator launch path is **Moonlight → Wolf UI → User → Batocera full x86 experiment**. After launch, run experiment-only inspection/log collection and perform the interactive checks in the spec. Use Wolf UI's explicit experiment Stop action before the persistence relaunch check; disconnect/rejoin is insufficient.

The idle gate does not atomically reserve the server. Registration reports the residual possibility of a new session between the final idle check and restart. No original source, existing Batocera configuration/state, or unrelated application resources were modified during this activation.

## First real launch failure

- [x] Diagnose the first-run failure without changing existing Batocera or restarting Wolf.
- [x] Correct stock population semantics and add regression coverage.
- [x] Verify first-run and repeat startup against the complete official userspace.
- [x] Build and directly transfer the corrected image over SSH, replacing GHCR upload for this iteration at the user's request.
- [x] Verify the loaded image and idle-gate the experiment-only update; remove verified failed staging.
- [x] Record remote diagnostics and remaining interactive acceptance.
- [x] Record the operator's two failed retests and recover removed-container startup logs.

At diagnosis, the two experiment containers had exited with code 1 and been removed by Wolf. The home contained incomplete `.gow-full-x86-init` staging, no installed state marker, and no initialized user state.

Running the packaged initializer against fresh ephemeral state reproduced `cp: cannot stat '/usr/share/batocera/datainit/system/configs/emulationstation/es_settings.cfg'`. The full stock manifest contains no such file. Normal stock execution succeeds without it and creates data.version, machine-id, and batocera.conf. Our added `bash -e` and requirement for preexisting ES settings were incompatible with the real release. The earlier fixture incorrectly supplied that optional file and treated its absence as an error.

The correction preserves normal stock execution, verifies ROM subtrees that should have been newly copied, and requires the actual core state outputs. It does not edit stock scripts, generate fake ES defaults, or import earlier emulator patches. A missing required config and a broken ROM-copy pipeline still prevent the completion marker.

`sh experiments/gow-full-x86/tests/run-runtime-tests.sh` passed 20 mounted-state/process cases and seven runtime unit tests. A smoke using the complete published stock image with only the corrected runtime file bound read-only succeeded with real read-only ROM/BIOS mounts, produced the release/UID/GID marker, and preserved a preference and its inode/mtime on repeat startup. This proves the initialization fix, not Xwayland or streamed frontend acceptance.

## Direct local-image deployment

The user requested skipping the slow GHCR upload for this fix. The in-progress upload was cancelled; there is no completed publication record for the corrected image. Existing GHCR publishing code and SHA/latest tagging remain available for a later publication.

The corrected image was built at adapter `abe82e05e826cde480e917a3a5f31c7aead4708a`. All 112,729 stock paths again passed inventory verification. A smoke using the actual rebuilt image, without a runtime source override, passed initialization and repeat startup with read-only ROM/BIOS mounts and preserved ES preference contents, inode, and mtime.

The image was streamed with `docker image save | gzip -1 | ssh ... sudo -n docker image load`. Transfer and load completed in 317.71 seconds. The resulting remote image ID is `sha256:9d421bb0dc7bedb460fc946e252db41ce2ae382a57223c00e3147b86ae99f219`, matching the local build manifest exactly.

`remote.sh --prepare --local` succeeded without a GHCR pull. Local mode requires the successful inventory-verified experimental build manifest, the exact image ID, and matching remote experimental/revision labels. It runs the packaged prerequisite check without home/state binds. `remote.sh --register --local` succeeded under the existing idle gate, verified API health and the updated experiment entry, and preserved preexisting profile/app values. The runner now uses the immutable local image ID, not a mutable tag or registry manifest digest.

The failed initialization work directory was removed only after verifying deployment ownership, the corrected prepared image, canonical paths, no running experiment, no completion marker or installed seed, empty final ROM/BIOS mountpoint directories, and the exact interrupted checkpoint with empty data.version and absent batocera.conf/machine-id. No initialized user state, ROM/BIOS library, old Batocera state, or unrelated application resource was removed. Recovery evidence is in `output/gow-full-x86/failed-init-recovery.json`.

The local transport contract suite passed 13 tests. Full unit discovery passed 49 tests with one host ALSA prerequisite skip; builder runtime tests had already exercised ALSA without skips. Actual local preparation/registration are the smoke proof for the new transport. Post-update `--inspect-session --local` and `--collect-logs --local` both returned `{"containers": []}`.

The operator retested the initialization-only image twice and both launches failed. The investigation and correction below supersede the earlier pending-retest instructions. Userdata initialization succeeded; do not remove or reseed that installed state.

## Real Wolf startup correction

- [x] Recover both failed user launches from the host's journald Docker logging backend.
- [x] Review original runtime permission, NVIDIA, and hotkey setup read-only.
- [x] Correct Wayland descriptor transfer, private X11/runtime directory setup, and bridge GBM selection.
- [x] Start stock hotkeygen with container input-node filtering and a reload-handler readiness barrier.
- [x] Correct stock SDL audio backend selection and prevent appliance ALSA hooks from replacing the session route.
- [x] Pass 22 mounted-state/process regressions and seven runtime unit cases inside the isolated builder.
- [x] Verify the candidate on real remote Wolf with temporary read-only adapter/config overrides.
- [x] Build and inventory-verify the corrected image, transfer it directly, and idle-gate the experiment-only deployment.
- [x] Verify the packaged image on real Wolf without source/config overrides and capture its rendered frontend.
- [x] Record the final image identity, deployment evidence, and remaining Moonlight/controller/heard-audio acceptance.

The user containers `WolfExperimental_40b93051-cef3-4aab-98a4-1d8c1ac9a3e5` and `WolfExperimental_ef9c6f1e-5792-42b5-b1e8-a4f71dac0d13` were already removed. Their journal records show Xwayland's `could not connect to wayland server` and `Couldn't add screen`, not a new initialization failure. Inside a real diagnostic runner, `/tmp/sockets/wayland-2` was root-owned mode 0755: UID 0 connected, UID 1000 received EACCES. The installed userdata marker matched release 43.1 and UID/GID 1000.

The original `10-setup_user.sh` recursively chowns the shared runtime, but this experiment deliberately does not copy that behavior. Original `30-setup_nvidia.sh` and `launch-comp.sh` register/select the injected NVIDIA GBM backend; `startup-app.sh` waits for hotkey startup. The original hotkeygen also has a missing-input-node guard. Only startup compatibility is carried into the new isolated adapter; original files, stock image files, and old emulator patches are not changed or imported.

Further real-host probes exposed a one-use Wayland connection reset, absent private `/tmp/.X11-unix`, an unwritable newly created `/var/run`, missing GBM backend selection, hotkeygen's unforwarded host input nodes, and reload-before-handler startup ordering. Each correction stays in the new adapter. The input filter matches the missing device filename, so a missing unrelated hotkey configuration still fails startup.

Stock SDL2 lists ALSA, JACK, PipeWire, DSP, disk, and dummy, but no Pulse backend. SDL3 includes Pulse and ALSA. Both now use ALSA through the session's explicit Pulse plugin. Actual stock ALSA loading had changed the default back to PipeWire after parsing our file, producing `Host is down`; disabling the root load hooks fixes that without editing appliance config. The strengthened regression uses `snd_config_update_r` and a conflicting temporary `.asoundrc`; it failed with `null != pulse` before the config fix and passed afterward.

Real Wolf candidate lobby `86eb25b3-fdeb-4405-b4df-6759c5763b8f` started ES as UID 1000, passed authenticated `xset q`, and reported direct NVIDIA RTX 3090 OpenGL 4.6 with driver 570.195.03. Both stock SDL2 and SDL3 opened audio devices through ALSA against the session Pulse server. A captured 1280x720 X11 frame showed the EmulationStation Atari system menu. The application environment did not retain `WAYLAND_SOCKET`. Audio-device opening is not proof of heard audio; this diagnostic closed those devices before inspecting sink inputs. Every owned diagnostic lobby was stopped. No persistent Wolf config, other app, original repository, or unrelated application resource was changed during diagnosis.

Full project discovery through `.venv/bin/python -m unittest discover -s experiments/gow-full-x86/tests` passed 49 tests with one host ALSA prerequisite skip. The isolated builder exercised the strengthened ALSA case without a skip. The host's bare Python lacks the project's tomlkit dependency; use the existing project environment for delivery/registration tests.

### Packaged correction deployment

Runtime source revision `a6a33ee43f41415cd1284525e3e2a073774e4a8a` built successfully in 601.05 seconds. Both inventory gates preserved all 112,729 stock paths with 21,782 isolated additions. The resulting image is `sha256:e77918bd22b36e22ee3bf1ed8ba19da53c94af4b29fca7a5f58e21d145be41d4`, tagged locally as `batocera-gow-full-experiment:sha-a6a33ee43f41415cd1284525e3e2a073774e4a8a`. Its packaged prerequisite check passed without state binds. Direct Docker-save/gzip/SSH/load took 316.65 seconds. No GHCR upload was used.

Local preparation and idle-gated registration succeeded. Only the experiment app's image selection changed to the immutable local image ID; the helper verified preservation of all other profile/app values. Wolf alone restarted under the idle gate. No manual home bind was added, and installed userdata was not reset.

Native Wolf lobby `c0572aae-9b78-4376-8441-aef49bb81b3e` ran the packaged entrypoint/frontend with no adapter/config mounts or entrypoint overrides. EmulationStation ran as UID 1000; authenticated X11 readiness and direct NVIDIA RTX 3090 OpenGL 4.6 passed. SDL2 and SDL3 opened audio devices through ALSA. A queued SDL2 stream and then EmulationStation's own uncorked audio stream appeared on the assigned session Pulse sink. The captured `output/gow-full-x86/packaged-screen.png` was viewed and shows the Atari 2600 system menu at 1280x720.

Live `remote.sh --inspect-session --local` passed after correcting the helper's stock `readlink` path to `/usr/bin/readlink`. Its `output/gow-full-x86/remote-session.json` records the exact image, native home, intended read-only ROM/BIOS children, injected devices, process tree, state marker, and NVIDIA renderer. This helper-only correction does not change the runtime image revision.

An additional WM_DELETE_WINDOW probe did not produce a verified native frontend exit. The owned diagnostic lobby was then stopped through Wolf's API, yielding container exit 143. Do not report this as a successful native frontend quit. No owned diagnostic container remains. Temporary remote adapter/ALSA overrides and the local extracted hotkeygen inspection copy were removed; evidence images and logs remain.

Final unit discovery after the helper correction passed 49 tests with one host ALSA prerequisite skip. The builder had already passed that ALSA case without a skip, plus 22 mounted-state/process cases and seven runtime unit cases.

The startup correction is deployed and verified, but the experiment spec remains active. Operator acceptance still requires Moonlight video delivery, heard audio, physical controller navigation/hotplug, gameplay, hotkey return, native frontend quit, and real-session preference persistence. Select **Start**, not **Update**, for this locally loaded image. The original repository, existing Batocera entry/state, and unrelated application resources remain untouched.

## Emulator launch correction

- [x] Record operator confirmation of frontend and heard audio, and recover the failed emulator launch log remotely.
- [x] Identify missing stock library-cache initialization and reproduce the subsequent primary-output failure on real Wolf.
- [x] Initialize the container-private cache without rewriting stock links and use stock output selection after authenticated X11 readiness.
- [x] Pass the real stock-image PySDL2/configgen regression under an unprivileged UID on the remote host.
- [x] Pass 22 lifecycle/state fixtures, seven builder runtime cases, and full unit discovery of 49 tests with one host ALSA prerequisite skip.
- [x] Render Atari 2600/Stella, SNES/SNES9x, and standalone Dreamcast/Flycast through stock configgen on a real Wolf candidate and view captured frames.
- [x] Build and inventory-verify the emulator correction, transfer it directly, and deploy under the existing idle gate.
- [x] Repeat actual game-launch verification using only the packaged image, remove the temporary candidate, and record the image identity and acceptance limits.

The operator's remote `es_launch_stderr.log` fails importing stock `sdl2` from `configgen.emulatorlauncher`: SDL2 is present and directly loadable, but Python discovery has no linker cache. Stock `/etc/init.d/S04populate` normally creates the search configuration and launches `ldconfig`; the container had bypassed that boot setup. The adapter uses its exact search directories synchronously with `-X`, generating only the disposable container cache, not changing stock libraries or injected driver symlinks.

The next real launch passed that import but failed `videoMode.getCurrentResolution()` with an empty value because no RandR output was primary. Stock `batocera-resolution setOutput auto` establishes it. No emulator source, system configuration, or stock resolution script is patched.

Candidate lobby `39efe38e-cecb-4a21-9b29-34f21eb31ed7` used a temporary read-only copy of the updated adapter in the old image. Native startup initialized the cache and output without manual in-session corrections. Launch probes inherited the frontend's UID/GID, supplementary groups, and environment. Stella and SNES9x ran under RetroArch; standalone Flycast started the Dreamcast boot sequence. All three captured frames were viewed. Game rendering used NVIDIA RTX 3090 driver 570.195.03. Stock configgen selected its advertised 5120x2880 mode; screenshots were scaled to 1280 pixels for inspection, not presented as Moonlight capture proof.

The remote stock-image regression imports real configgen/PySDL2 after dropping to UID/GID 1234, queries the real SDL2 ABI, and verifies stock library symlinks are unchanged. It is in `tests/stock_runtime_tests.py` because it requires the actual stock image rather than the host or Debian fixture. Source the packaged `bridge.env` when invoking it through Python stdin in a disposable networkless container.

Earlier diagnostic setup errors are not production failures: a raw root Docker exec could not read the frontend's restricted `/proc` environment; dropping to its UID after copying its supplementary groups fixed the probe. An initial Docker exec using only UID/GID had omitted device groups and produced a misleading uinput permission error. The native identity probe did not repeat that error. Missing keyboard devices are expected without a Moonlight client. Stock logs also show nonfatal core-info cache, MIDI-device, and syslog warnings; no workarounds for those were added. All owned diagnostic lobbies were stopped.

### Packaged emulator correction deployment

Runtime revision `c1f673c31cb71c4e5628c5f508e10f7c911d33bd` built in 568.01 seconds. Both inventory gates preserved all 112,729 stock paths with 21,782 isolated additions. The image is `sha256:58a3799a794a4ee3bcf862a9be08154619c45a31170d838eccadbf307e625e6d`, locally tagged `batocera-gow-full-experiment:sha-c1f673c31cb71c4e5628c5f508e10f7c911d33bd`. Direct transfer/load took 322.53 seconds. Local preparation and idle-gated experiment-only registration passed, with preexisting app/profile values preserved. No GHCR upload or Docker restart was used.

The stock-library regression passed again against the actual new image on the remote host with no source bind. Packaged Wolf lobbies `33ff9a21-d976-4d87-8966-5e5d415ed777` and `2bd4b00f-954d-4da5-9dbc-3761a4e8580b` used the registered runner unchanged, with no source/config/entrypoint overrides or manual in-session startup corrections. All three stock configgen launch paths remained running until deliberately interrupted by the diagnostic. Stella rendered its game arena; SNES9x reached the Japanese soccer title screen; standalone Flycast progressed through Dreamcast boot into its animated intro. NVIDIA rendering and uncorked audio streams belonging to each emulator were observed on the assigned session sink.

The first single-frame SNES/Dreamcast captures landed on dark intro transitions. A bounded five-frame sequence established visible content rather than treating a running process or black frame as visual proof. Viewed evidence is `output/gow-full-x86/emulator-packaged-atari2600.png`, `emulator-packaged-snes-05.png`, and `emulator-packaged-dreamcast-05.png`; the other captured frames remain beside them. `emulator-packaged-smoke.json` records the image, lobbies, observations, and limits. These are scaled X11 captures, not client-streaming proof.

Every owned diagnostic lobby was stopped. The temporary remote adapter candidate was removed after deployment-owner, current-image, path, and active-mount checks. No experiment container remained at cleanup. The original repository, existing Batocera entry/state, and unrelated application resources were untouched.

Frontend video and heard frontend audio are operator-confirmed. Sampled emulator startup/rendering/audio-stream routing are now verified remotely. Client-side game video/heard audio, controller gameplay/hotplug, hotkey return, native frontend quit, preference persistence, and other emulator families remain operator acceptance. The spec stays active; use **Start**, not **Update**, for the locally loaded correction.

## Remaining emulator failures and session sizing

- [x] Record operator-confirmed Xbox and SNES success.
- [x] Diagnose confirmed Xbox 360 failure.
- [x] Diagnose confirmed Wii failure.
- [x] Diagnose confirmed PS3 failure.
- [x] Diagnose suspected PS2 failure without treating uncertain recollection as confirmation.
- [x] Keep emulator/dialog sizing consistent with Moonlight's negotiated resolution, with regression coverage for mode selection. Actual client readability remains operator acceptance.
- [x] Verify targeted fixes on real Wolf, deploy only the experiment, and record emulator-specific acceptance.

At the start of this iteration, the operator confirmed Xbox and SNES worked. Xbox 360, Wii, and PS3 failed; PS2 was suspected, and other failed systems were not recalled. Dialogs were too small at Moonlight 720p. Existing logs established that configgen replaced the initial 1280x720 mode with advertised 5120x2880. Moonlight settings were not changed; stock mode selection, not missing negotiated dimensions, caused the promotion.

Initial logs showed RPCS3 heap-corruption output during shutdown, Xenia DXGI factory failure, and PCSX2 stopping after CPU recompiler reset. Those symptoms alone did not establish causes. Native diagnostics then isolated insufficient private shared memory for Wii/PS2, Wine's lost injected NVIDIA dependency paths, a stock/injected CUDA version mismatch in Xenia, and Blood Stone's required per-game color-buffer option. Warnings that remained during successful rendering were not suppressed.

Confirmed causes, corrections, rejected hypotheses, and verification live in [runtime troubleshooting](research/runtime-troubleshooting.md). Runtime revision `fcffbfd04685d8ca59aac8ed6a57950e737a967c` is now packaged as `sha256:e0c179a04267b022a8fab94628db24feff53c4bd317c9bdce5554873ae2ade03`. Both inventory gates retained all 112,729 stock paths with 21,782 isolated additions. Build took 599.72 seconds; direct gzip/SSH/load took 339.54 seconds with every pipeline stage successful. Local-mode preparation and idle-gated registration deployed only the existing experimental entry. No GHCR publication or unrelated app change occurred.

Unit discovery completed 49 tests with the known host ALSA skip. The isolated builder passed all 22 mounted-state/process cases and seven runtime unit cases, including real ALSA evaluation. New cache and shared-memory regressions failed against the old image as expected. New packaged stock-runtime checks passed in both disposable and GPU-enabled containers with documented prerequisite skips. Both real-session resource/display checks passed at 720p and 1080p.

Packaged native lobby `89eff988-906f-4f0f-831a-03bee18e816e` rendered Wii, PS2, Xbox 360, PS3, SNES, and Xbox samples at 1280x720 with individual uncorked audio streams on the assigned sink. Fresh lobby `76bec08e-0f37-49b7-9414-f1051ebb58ba` launched Xenia and RPCS3 at 1920x1080 without manual cache initialization or config corrections. Blood Stone completed initial content setup and reached its title. Blue Dragon's press START prompt renders against a predominantly white background; full graphics correctness remains unverified. Viewed captures, complete logs, test prerequisites, and the 720p cache-check ordering are recorded in the troubleshooting notes.

Both lobbies were stopped. Final API inspection found no sessions, lobbies, or experiment containers. Original checkout/app/state and unrelated application resources were untouched. Use **Moonlight → Wolf UI → User → Batocera full x86 experiment → Start**, not **Update**.

- [ ] Operator acceptance of Moonlight game video/heard audio and dialog readability at 720p.
- [ ] Operator acceptance of controller gameplay/hotplug, hotkey return, native quit, and preference persistence.
- [ ] Record specific additional failing systems/games if encountered; no blanket compatibility claim.

## GHCR publication and local storage cleanup

- [x] Publish the already verified runtime image with both SHA and latest tags.
- [x] Verify both registry tags resolve to the same manifest digest.
- [x] Delete only four obsolete local experimental images and their matching generated root archives.
- [x] Verify the current build and all unrelated images/container states remain present.

Published `ghcr.io/dafrenchyman/batocera-gow-full-experiment:sha-fcffbfd04685d8ca59aac8ed6a57950e737a967c` and `:latest` from image `sha256:e0c179a04267b022a8fab94628db24feff53c4bd317c9bdce5554873ae2ade03`. The existing publisher verified both tags at digest `sha256:787d76b8fd70e8808d5156b5096bd5aaebd3a53ac89444249084c76a218a2706`; its success record is `output/gow-full-x86/publication-manifest.json`. Publication took 2212.14 seconds. To satisfy the publisher's exact-source gate, publication temporarily checked out the build revision after confirming only planning docs differed, then restored `main`. No source rebuild, Git push, remote registration, or Wolf restart occurred.

Removed local experimental image revisions `2748e728f3b01eaf5aae12a766ffa9f5c672e0d1`, `abe82e05e826cde480e917a3a5f31c7aead4708a`, `a6a33ee43f41415cd1284525e3e2a073774e4a8a`, and `c1f673c31cb71c4e5628c5f508e10f7c911d33bd`. Deletion required matching experimental/revision labels, only allowlisted experimental tags, and no referencing container. Explicit `docker image rm --no-prune` used no force. The four matching `packaging-<revision>/final-root.tar` files were regular, unshared, unmounted files inside this independent repository; only those archives were removed, retaining their provenance manifests.

Available local disk space increased from 105,392,340,992 to 257,691,181,056 bytes, a net increase of 141.84 GiB. `df -h` reports 240G available and 75% used. Exact deleted paths, image IDs/tags, sizes, preserved image IDs, and unchanged container identities/running states are in `output/gow-full-x86/storage-cleanup-latest.json`. The current image and archive, assembly/input caches, builder, source/history, diagnostics, original repository/images, volumes/shared build cache, and unrelated application resources were retained. No remote filesystem or Docker resources were changed. The temporary publication wrapper was removed.

The remote app remains pinned to the same locally loaded image ID. Use **Start**, not **Update**; publication alone did not change the Wolf entry or the operator acceptance list above.
