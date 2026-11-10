# Completion: full-x86 GoW experiment

Consolidation note, 2026-10-28: this is the initial delivery snapshot retained from before the later runtime corrections documented by the 2026-10-26 continuation record. Its pending-status notes and image references are historical. The operator subsequently confirmed the effort finished; the complete workspace now resides at `docs/completed/specs/gow-full-x86/`. See the [spec disposition](spec.md) and [current application topic](../../../current/app.md) for later evidence and limits. No historical check is upgraded by this move.

## Status

- Delivery complete through publication, remote preparation, registration, API verification, and available diagnostics.
- Interactive runtime acceptance remains pending user QA under the spec's explicit no-accessible-client contingency. No display, audio, input, GPU, gameplay, or persistence success is claimed.
- Previous location: `planning/active/specs/gow-full-x86/`.
- Originally stated completed location: `planning/completed/specs/gow-full-x86/`. Actual consolidated location: `docs/completed/specs/gow-full-x86/`.
- Parent epic: none.

## Delivered behavior

The independent project at `/path/to/batocera-gow-full-x86` packages the complete official 43.1 generic x86_64 release with isolated Xwayland/startup additions. Both whole root layers, the entire boot partition, and the SHARE archive are retained. Stock emulator/configgen/default content is not replaced by the earlier GoW workarounds.

Published references:

- `ghcr.io/dafrenchyman/batocera-gow-full-experiment:sha-2748e728f3b01eaf5aae12a766ffa9f5c672e0d1`
- `ghcr.io/dafrenchyman/batocera-gow-full-experiment:latest`
- Common digest: `sha256:a8e7867cdfd6cb2498f97ddb3b8aac12aac00af5be83d693e9b0ce198ed916ed`.

The operator's Wolf server pulled and checked the published image. After the operator restarted GoW-Wolf, idle-gated registration succeeded and API health recovered. The new app is **Batocera full x86 experiment**, profile **User**, runner `WolfExperimental`, pinned to that digest. The automatic native home is `/etc/wolf/profile-data/user/WolfExperimental`; no manual home bind is configured. Only ROM/BIOS child content mounts are explicit and read-only.

Existing Wolf Batocera app/profile values were preserved by registration checks. Only the Wolf container was restarted. No changes to original source/runtime settings or unrelated application resources were part of activation.

## Implementation files

- `experiments/gow-full-x86/assemble.py`, `inventory.py`, `build.py`, `image.py`, and `build.sh`: complete assembly, metadata verification, and exact-layer image packaging.
- `experiments/gow-full-x86/bridge.nix`, `builder.Dockerfile`, and `release.json`: pinned display closure, assembly tools, and official release input.
- `experiments/gow-full-x86/runtime/`: staged stock state initialization and supervised display/frontend startup.
- `experiments/gow-full-x86/common.py`, `publish.py`, and `publish.sh`: path isolation and SHA/latest publication.
- `experiments/gow-full-x86/registration.py`, `remote.py`, and `remote.sh`: profile-preserving registration, idle gate, and experiment-only diagnostics.
- `experiments/gow-full-x86/tests/`: deterministic assembly, inventory, state/process, publication, and registration coverage.
- [Current application state](../../../current/app.md): later deployment evidence and acceptance limits.

## Observed verification

Earlier implementation verification is retained in `tasks.md`:

- Unit discovery: 47 tests, one host ALSA prerequisite skip. Seven runtime unit tests passed inside the builder without skips.
- Mounted-state/process fixtures: 19 passed using the actual stock initializer and read-only content children.
- Publisher fixtures: 10 passed.
- Real GPT/FAT/ext4/zstd assembly and exact-layer Docker inventory fixtures passed.
- Real `build.sh` succeeded. Full image-save inventory verification matched all 112,729 stock paths and allowed 21,782 isolated added paths.
- Real `publish.sh` succeeded. Independent `docker manifest inspect --verbose` calls for SHA and latest returned the common digest above.
- Disposable networkless runtime prerequisite and Xwayland executable checks passed. Xwayland reported 24.1.14.

Remote delivery verification:

- `remote.sh --prepare` succeeded after the owner changed package access. SHA/latest and image identity were verified; the packaged prerequisite check passed without state binds.
- The first registration attempt refused active or paused sessions without a config write or restart.
- After the operator restarted GoW-Wolf, `remote.sh --register` succeeded with the idle gate enforced, verified the new profile app and API recovery, and preserved preexisting profile/app values.
- `remote.sh --inspect-session` and `remote.sh --collect-logs` both completed after registration with `{"containers": []}`. There is no experiment runtime evidence yet.
- Machine-readable evidence remains under `output/gow-full-x86/`, including build/publication manifests, `remote-preparation.json`, and `remote-registration.json`.

## Review findings and accepted risks

Exact-layer Docker loading replaced Docker ADD after fixtures observed xattr and timestamp loss. Stock comparison was not weakened. Failed assembly staging cleanup and numeric/UUID runner idle checks were corrected during implementation and verified by fixtures.

The idle check cannot atomically reserve Wolf. A new session can begin between the final idle check and restart; registration explicitly reports this residual race. No host/app session was stopped to force idleness.

## Approved deviations

The user separately authorized deleting generated original-repository build outputs and old Batocera test-image tags to clear the storage gate. Source, saved configs, current images, volumes/shared build cache, and unrelated application resources were protected. Cleanup evidence is retained in `tasks.md` and `output/gow-full-x86/cleanup-report.json`.

The new GHCR package initially defaulted to private. The owner approved public visibility and changed its access before remote pull succeeded. Workstation credentials were not copied to the server.

## Pending operator acceptance

Launch **Moonlight → Wolf UI → User → Batocera full x86 experiment**. Do not select the existing Batocera entry for these checks.

- Collect experiment-only session inspection and logs after launch. Verify state marker, UID/GID, automatic home and sockets, isolated IPC/capabilities, and NVIDIA renderer rather than llvmpipe.
- Verify visible ES, controller navigation/reconnect, heard Pulse and ALSA-routed audio, a legal libretro game and standalone game, return to ES, and clean frontend exit.
- Change an ES preference. Explicitly stop only the experiment through Wolf UI, confirm its lobby/container ended, and relaunch. Require a new lobby UUID, the same native home, and the preserved preference. Disconnect/rejoin alone does not establish persistence.
- Record observed incompatibilities without importing old emulator patches by default.

Runtime inspection commands remain `experiments/gow-full-x86/remote.sh --inspect-session` and `experiments/gow-full-x86/remote.sh --collect-logs`. No local compositor or synthetic stream substitutes for these remote interactive checks.
