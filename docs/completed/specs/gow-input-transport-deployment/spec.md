# Image-based stock shortcut transport deployment

## Status

Complete. The self-contained working-tree image is built, loaded and active for User / Batocera full x86 experiment / WolfExperimental. Complete stock inventory, actual image integrity, default ES and stock receiver/RetroArch native checks passed. The user authorized the owned app config update and Wolf/Steam/UI interruption. No host helper software, upstream source patch, Git mutation or GHCR publication was introduced. See completion.md for exact image identity, evidence and remaining acceptance limits.

## Existing implementation

At planning start, the completed input-transport trial provided input_transport.py, input_worker.py, x11_input.py and udev_input.py, with real stock receiver and RetroArch proof. Build.py already copied runtime/ recursively into the isolated /opt/gow-full-x86 addition. ImagePackager selected entrypoint.sh and frontend.sh. Registration used an owned-app transformation, prepared-image marker and idle-gated atomic activation.

The then-registered image was sha256:e0c179a04267b022a8fab94628db24feff53c4bd317c9bdce5554873ae2ade03, app ID 293341540. Steam lobby 77ac4288-102a-4003-975d-0460169efe5b and Wolf UI were active. This Wolf revision has no safe live app update; profile remove/re-add is lossy and forbidden. The user subsequently authorized the stopped-Wolf transaction.

## Packaging and launch contract

- Package the proven transport modules inside the normal isolated /opt/gow-full-x86 runtime addition. No host-mounted helper release or new host process/service.
- New image entrypoint is argv-form /usr/bin/python3 /opt/gow-full-x86/input_transport.py -- /opt/gow-full-x86/entrypoint.sh. Preserve the default Cmd /opt/gow-full-x86/frontend.sh.
- The outer root PID-1 supervisor wraps the unchanged packaged startup adapter. Batocera still owns controller combinations, contexts, generated emulator settings and process launch. No per-emulator wrapper, overlay or remap.
- The app runner retains NET_ADMIN/SYS_NICE and adds the tested SYS_PTRACE prerequisite. Explicit normal private bridge networking confines fake-udev notifications while preserving network access. Retain private PID/IPC, default seccomp, non-privileged mode, native home and read-only ROM/BIOS bindings.
- Normalize the additive runtime tree to root:root, remove group/other write permissions and strip access/default ACLs before producing the image. Application UID 1000 must not be able to replace root-executed transport code. Leave stock ownership and ACLs intact.
- Docker capabilities cannot be supplied by image contents. The required app launch setting is configuration, not a Wolf implementation change. Residual stale-node/dev_t reuse exposure remains disclosed; do not claim strict isolation.

## Build and delivery

Use existing complete-stock build/assembly/image-save inventory gates. Preserve the official input and reusable assembly caches. Record the new source revision, image ID and stock inventory results; do not push source or publish to GHCR unless requested. Transfer and load only the verified new experimental image on the server, verify its exact image ID and packaged prerequisites, then use the owned experiment registration path to select it.

The user selected leaving Git unchanged. Add explicit build.sh --working-tree mode that hashes actual experiments/gow-full-x86 inputs, excluding Python caches, and records an honest worktree-sha256 identity and worktree image tag. Reject source changes during the build before promotion. Keep the existing committed-build default unchanged. Do not create commits, stage files, push, or change Git settings. No Git-fixture tests are needed for this mode.

## Authorized activation

Capture the current config hash and approved active Wolf app/container identities before interruption. Gracefully stop Wolf and only its approved active app containers as needed, without deleting state or volumes. While Wolf is confirmed stopped and those app containers cannot race new launches, reuse the compare-and-atomic-write activation transaction with that stronger quiescence check. Write only the transformed owned app table and preserve every unrelated parsed value. Start Wolf, verify API recovery and the selected app, and verify no unrelated configuration changed. Do not replace the User profile through the API or edit Wolf sources.

## README diagrams

Add a Mermaid runtime flow covering Wolf injection, entrypoint/root setup, state initialization, privilege drop, Xwayland/Openbox/D-Bus/hotkeygen, ES, stock per-game configgen/evmapy/context/emulator cleanup, and final-only input transport via native udev and XTEST. Distinguish stock operations from additions and show there is no injected per-emulator wrapper.

Add a separate Mermaid build flow showing pinned inputs, both whole root layers, FAT payload, SHARE seed, Nix closure, workspace paths, /opt and /nix copy destinations, exact tar packaging, Docker-save single-layer loading and inventory gates. Exclude deployment from the build diagram. Validate both diagrams parse/render.

## Verification and acceptance

- Run input tests and relevant registration/build fixtures. Add unit tests for new uncertain behavior, not copies of launch-setting constants.
- Build must pass both complete stock-path inventory comparisons and the loaded-image inventory gate before delivery.
- Remote image ID must match the verified local artifact.
- Launch the actual new image in an owned native Wolf lobby under the registered app launch settings. Inspect effective entrypoint, default command, capabilities, mounts and private namespaces. Observe actual ES startup and stock RetroArch menu/exit; temporary diagnostic frontend overrides must not enter registration.
- Confirm the normal app points to the new image and Wolf is healthy after the authorized restart. Remove only owned diagnostic resources.
- Physical Moonlight-controller and all-emulator acceptance remain operator checks, not claims from synthetic input.
