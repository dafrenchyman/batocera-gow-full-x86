# Preimplementation security review

## Result

The initial checkpoint proved descriptor-based discovery before transport code or a native lobby existed. The completed diagnostic subsequently passed native receiver and RetroArch menu/exit scenarios without rebuilding the deployed image or changing registration, packaged Batocera files, Wolf configuration, or the protected Steam lobby.

Functional review found no blocker and required explicit checks of both uinput hops, readiness before reload, held/repeat state, source loss, context changes, pointer delivery and command-on-release behavior.

Security review identified four contract gaps: kernel-device lifetime/reuse, PID lifetime and cleanup, privileged Xauthority-path handling, and non-root application capability confinement. The specification now records pinned process identities, retained creator/evdev descriptors, exact node cleanup identity, a separate non-root X11 worker, pinned no-follow authority reads, and an explicit nonzero application UID/capability check.

## Residual lifetime risk (accepted for the diagnostic only)

A retained uinput descriptor does not prevent another holder from calling UI_DEV_DESTROY. A manually created `/dev/input/eventN` node can briefly remain after that device is destroyed. If the kernel reuses the event device number before asynchronous revocation, another app process opening the stale node could access a foreign replacement device. Kernel-remove notifications and polling shorten but do not eliminate that interval. Sysfs revalidation plus pinned evdev descriptors protect the relay from name substitution; they do not establish strict lifetime isolation for every consumer of the exposed node.

The security reviewer considered this potentially reasonable for a short non-adversarial diagnostic, not an approved permanent guarantee. The user explicitly accepted both this exposure and temporary SYS_PTRACE for the bounded trial below. Existing Wolf unplug behavior is not a justification for adopting the exposure permanently.

## Options considered

- Bounded diagnostic only after the operator ends other Wolf sessions/lobbies, accepting that this reduces competing device creation but does not eliminate the underlying dev_t reuse interval. Do not stop the existing Steam lobby on the operator's behalf.
- Bounded diagnostic alongside the current Steam lobby, explicitly accepting cross-session replacement-device exposure during the revocation interval.
- Require strict lifetime isolation and reject asynchronous node forwarding; research a different transport boundary instead of claiming this design meets that requirement.

No source-device events from any other session were collected by the disposable probes. Those probes queried exact owned creator descriptors, created only their corresponding nodes, observed stock readiness, and then removed their own resources.

## User decision

After both risks were disclosed, the user selected **Trial alongside the existing Steam lobby**. Proceed with the bounded disposable diagnostic and leave Steam untouched. This is not approval for permanent deployment or a claim of strict lifetime isolation.

## Implementation review outcomes

- Fixed the root stock-pidfile read boundary: pinned no-follow directory/file opens, nonblocking FIFO rejection, expected UID/type/link/mode checks, and bounded reads. Regression tests passed.
- The X11 worker reads the pinned app authority only after dropping UID/GID/groups/capabilities and setting NoNewPrivs. Root does not follow app-controlled authority paths.
- The native-backend addition classifies only the descriptor-proven final keyboard with stock input_id, publishes no-clobber records in the root-controlled app-local udev directory, and uses the existing injected fake-udev sender. The candidate explicitly used NetworkMode=none with a host-distinct network namespace, preserving Unix-socket Wayland/audio access.
- Security finding UDEV-CLEANUP-001 was resolved before the metadata trial: one failed remove notification no longer aborts later source cleanup. Both owned records/nodes and real descriptors are cleaned in the two-source failure-injection regression; foreign Wolf state survives and the first error remains visible.
- Targeted security re-review found no concrete blocker in the implemented changes. Static review is not a strict lifetime-isolation guarantee. Actual native consumption was then measured: RetroArch opened the final keyboard, displayed its menu, and exited on the stock combos.
- All candidate lobbies and seven owned remote trial directories were removed. No experiment container remained running; the original Steam lobby and Wolf config hash were preserved.
