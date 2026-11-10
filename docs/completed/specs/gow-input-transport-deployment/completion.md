# Input transport image deployment completion

## Status

Complete. Standalone spec, no parent epic. Historical source workspace was `planning/active/specs/gow-input-transport-deployment`; actual completed workspace is `docs/completed/specs/gow-input-transport-deployment/`.

The experimental Wolf app now selects the self-contained input-transport image. The user authorized its launcher/config update and interruption of Wolf, Steam and Wolf UI. No upstream Batocera/Wolf/GoW source patch, host helper installation, source mount, overlay, per-emulator remap or Git mutation was introduced. The user subsequently authorized GHCR publication of the same accepted image, recorded below.

## Delivered behavior

The image ENTRYPOINT is `/usr/bin/python3 /opt/gow-full-x86/input_transport.py -- /opt/gow-full-x86/entrypoint.sh`; Cmd remains `/opt/gow-full-x86/frontend.sh`. The root supervisor discovers descendant uinput creators, exposes exact app-local event nodes and requests verified stock hotkeygen reloads. Final-only output reaches the app-UID XTEST worker and native consumers through stock-classified app-local udev metadata. Batocera retains combinations, per-emulator contexts, config generation, command actions and game launch/cleanup.

The owned WolfExperimental runner retains NET_ADMIN/SYS_NICE, adds SYS_PTRACE and explicitly uses private bridge networking. Private PID/IPC, default seccomp, nonprivileged mode, the native home and read-only ROM/BIOS bindings remain in place. Docker cannot grant SYS_PTRACE through image contents alone.

The additive runtime is root-owned, has no group/other write permissions or access/default ACLs, and rejects app-UID write/create attempts. Stock metadata is not normalized or relaxed.

README.md contains parsed/rendered Mermaid startup/emulator, input and build flows. The build diagram shows workspace paths, full stock layers/FAT/SHARE, Nix and runtime copy destinations, Docker-save loading and inventory gates, without deployment.

## Artifact identity and activation

- Image: `sha256:c0cf25d69864b56890011039336d207854578329c5adf33e53b933789a38aa19`.
- Source: `worktree-sha256:4e09792ac70efd9362e9c202429a78765079c8cfc445ff8974ca95d4a64df4a4`.
- Official input SHA-256: `7ac08d5fcf6f9c00e85e71b6d0c68ddffe710f1e0667aab2931c5bf1509018b8`.
- Complete inventory: 112,729 matching stock paths, 21,786 isolated additions.
- App: User / Batocera full x86 experiment / WolfExperimental.
- Native home: `/etc/wolf/profile-data/user/WolfExperimental`, automatically bound to `/home/retro`.
- Wolf restarted at `2026-10-27T06:58:57.180973726Z` after the authorized stopped-service transaction.
- Activated config SHA-256: `a70d0c17f3fbea74f948d4ff8c0233f248e8a8b13a244df0b6db8a7c09a8a74c`.

The exact two previously observed Steam/UI containers were stopped. The transaction repeatedly checked the config hash and stopped-service/app state, preserved file owner/mode, atomically replaced only the transformed owned-app table and started Wolf. Unrelated parsed config values and API profiles matched before/after. No private config backup or raw session/AES output was saved. The normal idle-gated --register path was not weakened.

## Changed files

- experiments/gow-full-x86/image.py: package the outer supervisor as the default entrypoint while preserving frontend Cmd.
- experiments/gow-full-x86/assemble.py: normalize only added runtime ownership/write permissions and remove ACLs.
- experiments/gow-full-x86/build.py: explicit --working-tree content identity, input-drift checks, cache exclusion and fingerprint-keyed assembly directories. Original committed-build default remains unchanged.
- experiments/gow-full-x86/remote.py: validate honest worktree identities/tags for local delivery, alongside existing Git artifacts.
- experiments/gow-full-x86/registration.py: immutable-image experiment runner with SYS_PTRACE and private bridge networking.
- experiments/gow-full-x86/tests/assembly_fixtures.py: actual packaging regression with app-owned writable source and access/default ACLs.
- experiments/gow-full-x86/tests/test_working_tree.py: content/mode/new-helper coverage, cache exclusion, source-drift rejection and external-link boundary tests. No Git fixtures.
- experiments/gow-full-x86/tests/test_registration.py: remove a tautological copy comparison; retain behavioral preservation/security tests.
- README.md and [current application state](../../../current/app.md): actual build/runtime/deployment behavior, flows and acceptance limits.

The four transport modules and two native probes were already implemented in the completed diagnostic spec; this rollout packages and activates them. The abandoned SourceProvenance class and interim Git-cleanliness-check change were removed. Temporary local operator coordinators were removed after verification.

## Verification performed

- `.venv/bin/python -m unittest discover -s experiments/gow-full-x86/tests -p 'test_*.py'`: 95 tests, one host prerequisite skip, no failures.
- `experiments/gow-full-x86/tests/run-assembly-fixtures.sh`: real GPT/FAT/ext4/zstd, full stock/SHARE metadata, hostile runtime ownership/ACL input, final-archive and exact Docker-layer metadata checks passed.
- `PATH="$PWD/.venv/bin:$PATH" experiments/gow-full-x86/build.sh --working-tree`: complete build and loaded-image stock inventory passed. Build time 1153.83 seconds.
- Actual image as UID 1000 with no capabilities: all 13 runtime source hashes and root-owned ancestors/tree checked; no write ACLs or group/other writes; write/open/create attempts rejected.
- Disposable image packaged prerequisite check and exact Nix Xwayland executable: passed, Xwayland 24.1.14.
- Immutable-ID Docker-save/gzip/SSH load: exact remote image matched, 416.43 seconds. `remote.sh --prepare --local` passed identity, labels and packaged prerequisites.
- One-time authorized stopped-Wolf activation: API recovery and unrelated config/profile preservation passed.
- Native default ENTRYPOINT/Cmd, capabilities, private PID/IPC/bridge namespaces, seccomp, no source mount and app-UID source integrity: inspected in real owned Wolf lobbies.
- Final serialized native run: default ES, all five stock receiver cases and actual stock-configured RetroArch passed. A separate normal-frontend capture showed the completed ES system menu with NVIDIA RTX 3090 rendering and a connected worker/final device.
- RetroArch: unchanged ES profile and stock input hashes; actual game/title and native Quick Menu screenshots reviewed. Guide + ES logical b, Xbox A for this profile, opened Quick Menu. Guide+Start exited the pinned emulator; stock launcher exit was 0.
- Scoped cleanup: eight owned lobbies/containers absent, five owned remote diagnostic directories removed. Wolf running, configured image and activated config unchanged. No persistent data or unrelated container was removed.
- Three README Mermaid blocks parsed/rendered with Mermaid 10.9.3 in managed Chromium; screenshots reviewed and tab closed.

## Initial smoke timeout

The first combined operator run rendered ES but timed out waiting for receiver readiness. It did not wait for ready input transport before stopping ES or complete container removal before the next case. Isolated default-frontend and receiver runs passed. The coordinator was tightened to require both lifecycle barriers; the unchanged image then passed the full three-case run in 23.01 seconds. The exact transient cause was not established. This is not claimed as a production source fix, and the first failure is retained rather than overwritten.

## Review findings

DEPLOY-RUNTIME-OWNERSHIP-001 is resolved by the additive-only owner/mode/ACL correction, hostile-input packaging fixture and actual-image/native app-UID checks. BuildIdentityReview and PackagedRuntimeReview found no further concrete blocker in their reviewed changes. See research/deployment-review.md.

## Evidence

Experimental output under output/gow-full-x86 contains:

- build-manifest.json and source-worktree-<source SHA-256>.json.
- input-transport-image-integrity.json and remote-preparation.json.
- input-transport-activation.json and remote-registration.json.
- input-transport-packaged-smoke-first.json, input-transport-packaged-debug.json and input-transport-packaged-receiver-debug.json.
- input-transport-packaged-smoke.json and input-transport-packaged-frontend.json.
- input-transport-deployment-cleanup.json and readme-flow-verification.json.
- input-transport-packaged-visuals/retroarch/retroarch-game.png and retroarch-menu.png.
- input-transport-packaged-visuals/frontend-ready/emulationstation/emulationstation.png.

## Accepted limits and operator acceptance

SYS_PTRACE and stale event-node/device-number reuse remain disclosed experimental risks. Private namespaces do not establish strict kernel device-lifetime isolation. Synthetic native input does not prove physical Moonlight Guide handling, every shortcut or every emulator, abrupt-source crash recovery, or heard/streamed output. The observed receiver timeout above remains documented; do not convert one final passing run into an exhaustive reliability claim.

The operator subsequently reported that the deployed shortcut changes work in the emulators tried. That report accepts those paths but does not enumerate every shortcut, emulator or reconnect scenario. Launch Moonlight → Wolf UI → User → Batocera full x86 experiment → Start. The server still selects the same immutable local image ID; publishing it does not itself change that selection. Do not choose Update for this local-image registration.

## Current-state update

[Current application state](../../../current/app.md) records the selected image, content identity, approved activation, packaged transport, actual native evidence, cleanup and remaining limits. At this delivery the broader full-x86 spec remained active. It is now [completed history](../gow-full-x86/spec.md) following the operator's later completion clarification, without broader emulator/shortcut verification.

## README flow and launcher verification

The diagrams were checked against runtime/build code and the exact deployed image's stock configgen sources. Stock context cleanup restores hotkeygen's default context, stops/clears evmapy, calls gameStop scripts and restores changed display/mouse state. Corrections clarify the Nix extraction root, absent-or-empty /boot precondition, driver directory paths and StateInitializer's adapter ownership. All three corrected Mermaid 10.9.3 diagrams parsed/rendered in Chromium and were visually reviewed; no runtime source or image changed.

README now includes the deployed experimental app's TOML block inside the existing user-profile context. A read-only server query selected only that app and checked it against the expected registration. The documented TOML parsed and matched the deployed app after JSON whitespace normalization. Credentials, paired clients and unrelated apps/settings were not copied. Evidence: output/gow-full-x86/readme-flow-review.json and readme-config-verification.json.

## GHCR publication

The exact accepted image was published under `ghcr.io/dafrenchyman/batocera-gow-full-experiment:worktree-4e09792ac70efd9362e9c202429a78765079c8cfc445ff8974ca95d4a64df4a4`, then `latest`. Both references were read back from GHCR and resolved to manifest `sha256:f52be2d9c6a8150cd7066f7504da8fa86550069c991bc7f83752f31e87e675a5`. Their config digest matched the deployed image ID and their single-layer shape was verified. The previous latest manifest was `sha256:787d76b8fd70e8808d5156b5096bd5aaebd3a53ac89444249084c76a218a2706`.

A one-time operator program checked successful stock-inventory evidence, current source-content identity, exact image/labels/ENTRYPOINT/Cmd and immutable-tag collisions before publishing. It used existing Docker credentials without printing them, pushed the content tag first, verified it, then updated and verified latest. It completed successfully in 2062.68 seconds and was removed after use. No rebuild, commit, source push, server config write or Wolf restart occurred.

Evidence is output/gow-full-x86/worktree-publication-manifest.json. This deliberately does not masquerade as a Git-SHA publication or replace the normal committed-build publication record. The existing publish.sh and registry-prepare path remain committed-build-only; the live app remains on its already-loaded immutable ID. README records the digest-pinned pull reference and how it differs from the local config ID.
