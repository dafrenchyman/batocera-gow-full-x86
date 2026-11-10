# Completion: runtime-owned stock shortcut transport trial

## Status

- State: Complete as an isolated diagnostic; not deployed or enabled by default.
- Source before completion: `planning/active/specs/gow-input-transport-trial/`.
- Completed location: `docs/completed/specs/gow-input-transport-trial/`.
- Parent epic: none.
- No in-scope task remains open. Permanent activation was neither approved nor performed.

## Implemented behavior

The additive supervisor identifies uinput devices through approved descendant pidfds, actual creator descriptors and UI_GET_SYSNAME, exposes only their exact event nodes, and lets stock hotkeygen discover them through its supported reload behavior. A separate capability-free worker transports only hotkeygen's final keyboard/pointer output into authenticated X11. The final keyboard also receives stock input_id classification in Wolf's existing app-local udev database, with notifications through the unchanged fake-udev sender. Semantic intermediate keys are not advertised as application keyboards.

Batocera still owns Guide combinations, emulator contexts, held actions and command-on-release behavior. There is no overlay, hotkeygen rewrite, emulator-specific mapping, input-driver override, stock-file replacement, Wolf modification or GoW modification. The existing default runtime/entrypoint, registered image and app registration were not changed.

## Changed files

- `experiments/gow-full-x86/runtime/input_transport.py`: descendant ownership, exact event-node forwarding, stock reload readiness and bounded lifecycle cleanup.
- `runtime/input_worker.py` and `runtime/x11_input.py` under the same experiment: capability-free authenticated XTEST transport and source-owned input state.
- `runtime/udev_input.py`: stock classification, completed no-clobber metadata publication, identity/content-checked cleanup and existing fake-udev notification.
- `runtime/transport_probe.py` and `runtime/emulator_probe.py`: reusable diagnostic frontend commands exercising real stock evmapy/hotkeygen, authenticated X11, actual configgen and actual RetroArch; neither is a default frontend.
- `experiments/gow-full-x86/tests/test_input_transport.py`, `test_x11_input.py`, and `test_udev_input.py`: behavior, ownership and failure-boundary regressions.
- `README.md`, this completed workspace and [current application state](../../../current/app.md): diagnostic usage, measured results and deployment boundary.

## Verification performed

- `python3 -m unittest discover -s experiments/gow-full-x86/tests -p 'test_*input*.py' -v`: 43 tests passed after final code cleanup.
- Disposable exact-stock ownership probes: default Docker policy rejected pidfd_getfd; temporary SYS_PTRACE permitted authoritative device discovery and stock daemon readiness.
- `output/gow-full-x86/input-transport-native-udev-shortcuts.json`: all five native stock receiver cases passed with metadata enabled; held keys, pointer/button ordering, context changes, graceful source removal and first recreated use, and one command execution per actual stock release. Container exit 0.
- `output/gow-full-x86/input-transport-native-udev.json`: unchanged stock configgen launched real RetroArch/FCEUmm with an existing ES controller profile. RetroArch opened the exact final event node and read its classifier properties. Guide+Start terminated the pinned emulator; stock launcher and container exited 0. ES profile and twelve checked packaged shortcut inputs were unchanged.
- Visual review of `output/gow-full-x86/input-transport-emulator-visuals-_g97v7vw/retroarch-game.png` and `retroarch-menu.png`: the game rendered before the shortcut and Guide + ES `b` opened RetroArch's native Quick Menu. The existing profile maps logical `b` to Linux code 304, the Xbox A/south button, not the Xbox B label. This is actual X11 application evidence, not Moonlight-stream or physical-controller acceptance.
- `input-transport-cleanup.json` and `input-transport-container-cleanup.json` in the same output directory: seven owned remote trial directories removed; all seven exact candidate containers absent; transient experiment udev directory absent; original Steam lobby preserved. Wolf config SHA256 remained `4a65af34e636e9995f53f1f880dc0946e0ea5f6f7307e159d9ae3129ba21b2b1`.

The native candidates used the exact deployed image, private PID/IPC namespaces, default seccomp, baseline NET_ADMIN/SYS_NICE plus only approved temporary SYS_PTRACE, and additive source/results mounts. Metadata candidates explicitly used NetworkMode=none and a host-distinct network namespace. Unix-socket Wayland/audio remained functional. No publication, image rebuild, registration mutation or Wolf restart occurred.

## Review findings and design changes

Security review required pinned process identities, no-follow/bounded stock pidfile reads, app-side pinned authority access after privilege drop, and visible failures. X11 review found mixed-frame pointer/key reordering; ordered motion segments and regression tests fixed it. Metadata review found that failed remove notification could abandon later resources; the supervisor now attempts every source cleanup, retains the first failure, and completes independent resource cleanup before reporting it. Targeted re-review found no concrete blocker in that correction.

XTEST receiver success alone did not solve the real emulator: RetroArch's stock udev backend required final-keyboard discovery metadata. The generic metadata extension resolved the measured menu/exit failure without changing the emulator's configuration. See [native input research](research/native-input.md) for the failed-before/passed-after evidence and interface references.

## Outside approved scope and limits

The user accepted temporary SYS_PTRACE and residual stale-node/dev_t reuse exposure only for this bounded trial alongside Steam. Retained descriptors do not prevent explicit UI_DEV_DESTROY; this is not strict lifetime isolation. Permanent capability/isolation policy requires a separate decision.

Physical Moonlight input, every shortcut/emulator, abrupt-crash recovery and tag-filtered udev listeners were not verified. Existing stock feature support still determines which shortcuts an emulator implements. Future Batocera/Wolf upgrades require rechecking the generic device-role/classifier/helper contracts, not carrying per-emulator mappings.

A new physical-controller candidate would need an explicitly approved temporary session; the cleaned diagnostic is not available in the normal Moonlight app. Current deployed Guide behavior is therefore unchanged.

## Current-state updates

At this diagnostic delivery, the application topic recorded the verified diagnostic capability separately from the unchanged deployed application; README did not instruct permanent activation. [Current application state](../../../current/app.md) now also includes the separately authorized [deployment](../gow-input-transport-deployment/completion.md). Diagnostic acceptance alone did not authorize that deployment.
