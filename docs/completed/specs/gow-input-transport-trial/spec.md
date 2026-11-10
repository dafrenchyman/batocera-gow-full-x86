# Runtime-owned input transport trial

## Status

Completed as a bounded diagnostic, not a deployment. Native stock shortcut receiver cases and real stock-configured RetroArch menu/exit passed. After disclosure of diagnostic SYS_PTRACE and residual stale-node/device-number reuse exposure, the user chose the disposable trial alongside the existing Steam lobby; both risks were accepted for that trial only. The candidate lobbies and temporary remote directories were removed. No image rebuild, publication, registration change, Wolf restart, or deployed-entry replacement occurred. Production adoption remains a separate decision.

## Goal and boundaries

Make the stock Batocera evmapy/hotkeygen pipeline deliver its existing shortcuts into the experiment's X11 and native udev keyboard consumers. Transport keyboard and pointer events, not Guide combinations or emulator action mappings. Keep every packaged Batocera path and Wolf/GoW implementation unchanged. Preserve normal hotkey contexts, command actions, and press/release timing. No universal overlay or emulator-specific fallback.

The operator reports all tried emulators now run. Guide alone sometimes opens a native menu; that does not establish shared shortcut delivery. The prior project worked around synthetic-device discovery and later added individual emulator exits. Do not import those patches.

## Existing implementation

- `experiments/gow-full-x86/runtime/runtime.py` supervises stock hotkeygen and Xwayland/Openbox. Its existing narrow subclass ignores precisely absent forwarded event nodes. This trial does not expand that subclass.
- Stock evmapy emits semantic keys on a uinput device. Stock hotkeygen translates these using the active context and emits a second keyboard or executes a command.
- Wolf forwards selected devices and supplies a private compositor. Xwayland receives Wayland input; it does not discover arbitrary evdev keyboards itself.
- The deployed image remains `sha256:e0c179a04267b022a8fab94628db24feff53c4bd317c9bdce5554873ae2ade03`.
- Stock inventory contains libX11, libXtst and libevdev. XTEST support in the running bridge must still be exercised.

## Trial design

Add an experiment-owned root supervisor wrapping the unchanged entrypoint. Pin the launched process with a pidfd before reaping. Acquire descendant pidfds before validating their start identities and ancestry against live pinned ancestors; revalidate around descriptor access. Retain approved process identities for cleanup and reload signaling. Do not authorize unknown processes merely because they reparented to the supervisor, and do not use numeric process-group cleanup.

Use `pidfd_getfd` to duplicate a verified uinput character descriptor, then `UI_GET_SYSNAME` to obtain its authoritative kernel identity. Device names are not ownership evidence. Hold the owned reference while checking canonical sysfs identity, creating a missing container-local event node, and opening its evdev descriptor. Use a root-controlled node directory and record node filesystem device, inode and character-device number. Never alter a preexisting node. Retain creator references while their sources are active, but revoke them when the original writer disappears or explicitly destroys the device. Relay from pinned evdev descriptors rather than reopening names.

Let the existing stock daemon discover newly accessible devices through its supported reload behavior, only after its existing SIGHUP-handler readiness barrier and with a verified owned daemon identity. Expose both owned uinput hops, but relay only the final output named `batocera hotkeys`. The name selects the output role after descriptor ownership is established. Send pinned source descriptors over a private inherited socket to a separate non-root, capability-free X11 worker. Forward key press/release, relative pointer motion and mouse buttons; preserve held keys, ignore duplicate repeat notifications, and release transport-owned state on source removal, input loss, or shutdown. Reject unsupported event types visibly. Do not route evmapy's semantic keys into X11. Command-valued actions remain stock hotkeygen's responsibility.

The real stock RetroArch trial exposed a native udev-backend boundary after XTEST receiver acceptance. Extend only the descriptor-proven final keyboard's lifecycle with app-local udev publication: classify its exact event sysfs path through stock `udevadm test-builtin input_id`, publish a completed no-clobber `cMAJOR:MINOR` record in Wolf's existing per-app `/run/udev/data`, and notify through the unmodified injected `/usr/bin/fake-udev`. Preserve classifier-derived properties; do not invent keyboard classes or expose intermediate semantic keys as application keyboards. Require a runtime-created node, recheck creator ownership around classification/publication, and remove only an unchanged owned record before node teardown. Never replace Wolf records, import host metadata, run rules/triggers, or change emulator input drivers. Retain XTEST for X11 consumers. Test collision/replacement cleanup, malformed classification, and ownership loss; prove discovery and consumption in the real emulator rather than treating notification success as acknowledgement.

The metadata diagnostic explicitly uses Docker `NetworkMode=none` and checks that its network namespace differs from the host before permitting frontend input. Wayland and audio use the existing Unix sockets. Root notifications must never run in host networking or a namespace shared with the Steam session.

The helper must fail visibly on unsupported prerequisites, conflicting nodes, XTEST failure, or missing ownership evidence. Require a nonzero app UID and verify effective, permitted and ambient capabilities after privilege drop. Validate the root-owned, non-writable session metadata, expected display `:0`, and private runtime location. Only the non-root worker opens the app-owned runtime directory and authority file using descriptor-relative, no-follow opens and restrictive ownership/mode checks. Pin the authority descriptor and give Xlib its `/proc/self/fd` path rather than a mutable pathname. Keep privileged descriptors out of application inheritance. Remove only created nodes whose filesystem device, inode and character-device number still match. Stop only processes identified by retained approved pidfds.

Retaining a uinput reference does not prevent an explicit `UI_DEV_DESTROY`. Canonical sysfs checks before and after opening and pinned relay descriptors prevent name-based relay substitution. A manually created event node can still briefly outlive explicit kernel-device destruction until revocation; this numeric-device reuse exposure must receive explicit security review before a native trial and is not an approved permanent isolation guarantee.

## Observed prerequisite and security limit

A disposable remote container proved exact descriptor-to-kernel-device discovery and actual stock hotkeygen readiness. Docker 27.5.1's default policy rejects `pidfd_getfd` with EPERM; adding `SYS_PTRACE` permits it. The user approved that addition only in the private-PID disposable diagnostic candidate. No host PID namespace, privileged mode, Docker socket, host-wide input bind, or host service is allowed. Do not add the capability to the registered experiment without separate user approval.

The first disposable probe lacked `/var/run`; a second lacked input-device cgroup permission. After reproducing the existing runtime directory setup and dynamically derived input-major permission, stock readiness succeeded. These were probe prerequisites, not claimed production defects.

## Verification

- Unit tests for key ownership/reference counting, held/repeat events, disconnect releases, invalid input, descriptor/node identity validation, and foreign-source refusal where practical without kernel coupling.
- Disposable real stock-container checks for descriptor discovery, fail-closed default-policy behavior, device readiness, and cleanup.
- A native Wolf diagnostic lobby using the exact registered image, temporary read-only mounts of added files only, and the isolated capability addition. Check current sessions first; do not disturb the existing Steam lobby or change registration.
- Exercise the stock evmapy -> hotkeygen -> XTEST path with deterministic owned inputs and an authenticated X11 receiver. Check exact press/release ordering, a held action, held-source disappearance/recreation, relative pointer and button delivery, a context change without semantic-key leakage, and exactly one stock command execution on release. Exercise a real emulator path if the transport proof succeeds.
- Observe no stuck keys and cleanup of the owned lobby. Verify the candidate uses a fresh private PID namespace, exact baseline capabilities plus only SYS_PTRACE, the unchanged default seccomp policy, and approved additive mounts. Distinguish synthetic input proof from physical Moonlight-controller acceptance.

## Acceptance and stop conditions

A successful trial establishes verified creator-descriptor ownership, actual delivery into X11, preserved holds/releases, unchanged upstream files, and cleanup evidence. Asynchronous node forwarding does not establish strict device-lifetime isolation; the residual reuse exposure requires explicit acceptance before a native trial. Success does not claim physical-controller acceptance or universal emulator feature support. If the approach requires forbidden upstream edits or cannot establish creator ownership, record the failed experiment and stop instead of implementing a name-based or privileged fallback. No publication or deployment is part of this trial.
