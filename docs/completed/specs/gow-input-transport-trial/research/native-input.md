# Native keyboard backend boundary

## Observed behavior

The native diagnostic in `output/gow-full-x86/input-transport-native-shortcuts.json` passed all five stock evmapy -> hotkeygen -> XTEST receiver cases and exited 0. Holds lasted 253–257 ms, graceful source removal released all keys, the first recreated combo worked without a clearing press, and stock command dispatch occurred exactly once per real release. The second command execution during graceful source destruction is preserved stock behavior, not a helper-generated semantic release. A reverse-order teardown assertion was removed because the functional contract is complete, non-duplicated releases without stuck keys, not which cleanup path wins.

The stock configgen/RetroArch diagnostic exposed a separate backend gap. The actual ROM rendered correctly, but Guide + ES `b` did not open the menu and Guide+Start did not exit. This is recorded as a failure, not emulator acceptance. Screenshots under `output/gow-full-x86/input-transport-emulator-visuals-c7s9z5zh/` show the game continuing after the attempted menu shortcut.

`input-transport-native-emulator-state.json` establishes:

- The real stock launcher loaded the existing ES controller profile and generated the expected KEY_EXIT/KEY_MENU combos.
- Its evmapy process PID 160 was approved before reparenting to PID 1; kernel input205/event11 was forwarded. No missing creator ownership was demonstrated in this run.
- Stock hotkeygen had an event11 descriptor, and its selected `retroarch` context matched the unmodified generator: Shift+Escape for exit and Shift+F1 for menu.
- Generated RetroArch configuration selects `input_driver = udev` and `input_joypad_driver = udev`.
- The experiment's scoped udev `data` directory was empty after the failed scenario. The current helper creates event nodes but publishes no udev classification records.

The existing ES controller file and the twelve checked packaged shortcut files remained unchanged. Wolf configuration SHA256 remained `4a65af34e636e9995f53f1f880dc0946e0ea5f6f7307e159d9ae3129ba21b2b1`; the original Steam lobby remained running.

## Classifier prerequisite

A disposable, network-isolated stock container created its own keyboard/mouse-capable uinput device, obtained its exact UI_GET_SYSNAME identity (`input208`), and ran stock `/usr/bin/udevadm test-builtin input_id` only on that identity. It exited 0 and returned:

```
ID_INPUT=1
ID_INPUT_MOUSE=1
ID_INPUT_KEY=1
ID_INPUT_KEYBOARD=1
```

The initial classifier fixture incorrectly included the KEY_CNT sentinel and was rejected before UI_DEV_CREATE; the corrected fixture follows stock hotkeygen's valid key range. No other session device was classified or read.

## Decision

XTEST alone is not a universal keyboard transport for applications configured to read evdev through udev. Publish normal app-local udev metadata for only the descriptor-proven final keyboard, using stock input_id and the existing Wolf fake-udev sender. Keep the intermediate semantic device unclassified as an application keyboard. No RetroArch driver change, emulator-specific mapping, host-wide udev/input bind, rules replay, or global trigger is needed.

## Measured resolution

`output/gow-full-x86/input-transport-native-udev.json` records the metadata-enabled native trial:

- Docker used a private PID namespace, NetworkMode=none with a host-distinct network namespace, private IPC, default seccomp, and baseline NET_ADMIN/SYS_NICE plus only the approved diagnostic SYS_PTRACE.
- App-side libudev read the actual final keyboard's stock-derived ID_INPUT, ID_INPUT_KEY, ID_INPUT_KEYBOARD and ID_INPUT_MOUSE properties, all 1. RetroArch had the exact final event node open.
- The observed final menu chord was key 42 + 59 (Shift+F1), with matching releases. Visual inspection of `output/gow-full-x86/input-transport-emulator-visuals-_g97v7vw/retroarch-menu.png` confirmed the native RetroArch Quick Menu, not a helper overlay; the before image shows the running NES game.
- The final exit chord was key 42 + 1 (Shift+Escape), with matching releases. The pinned RetroArch PID exited and the stock launcher returned 0. The semantic reader's ENODEV during launcher teardown is expected device removal, not missing final-keyboard delivery.
- The ES controller file and twelve checked packaged shortcut files were unchanged. The frontend and worker ran UID/GID 1000, no effective/permitted/ambient capabilities, NoNewPrivs=1.

`input-transport-native-udev-shortcuts.json` then passed all five X11 receiver cases with metadata enabled: holds, pointer reset/button delivery, context switch, first use after graceful source recreation, and exactly one command invocation per actual stock release. Both native candidates exited 0. The original Steam lobby and Wolf config hash were preserved; the owned lobbies and seven remote trial directories were removed.

The mechanism is generic transport, not proof of every emulator or shortcut. Physical Moonlight input, abrupt-crash behavior, tag-filtered udev listeners, and production capability/isolation policy remain unverified or outside this bounded trial. Upgrade compatibility still depends on the stock final-device role, public helper interface and input/backend conventions.

## Interface references

- [Pinned Wolf fake-udev CLI](https://github.com/games-on-whales/wolf/blob/ee271038da2b81c9e54c28c9daa7558692d415d6/src/fake-udev/fake-udev-cli.cpp): sends notifications only; it does not register database records.
- [Pinned Wolf keyboard metadata](https://github.com/games-on-whales/wolf/blob/ee271038da2b81c9e54c28c9daa7558692d415d6/src/core/src/platforms/linux/uinput/keyboard.cpp): normal app-local E: property format.
- [RetroArch udev backend](https://github.com/libretro/RetroArch/blob/4b74434a30c534c763b60ba4cc16f6a94a611c5f/input/drivers/udev_input.c): ID_INPUT_KEY discovery and raw keyboard state are distinct from X11 callbacks. This cached source revision informed the experiment; exact deployed source equality was not established. Actual FD inspection and menu/exit behavior establish the deployed result.
