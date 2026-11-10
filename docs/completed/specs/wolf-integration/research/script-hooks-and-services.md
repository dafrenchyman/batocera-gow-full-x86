# Script hooks and services under Wolf

Historical source observations refer to the experiment layout and the recorded image/revision, not a new measurement of current behavior. Source links now navigate the maintained counterparts; obsolete experiment line anchors are not current line numbers.

Research date: 2026-10-31. Source inspection only. No scripts, services, userdata settings, image, Wolf configuration or runtime changed. The operator correctly identified that launching this application is not a normal Batocera boot.

## User-provided documentation

- [Launch a script](https://wiki.batocera.org/launch_a_script) distinguishes boot scripts, user services, configgen game events and EmulationStation events.
- [Service rules and examples](https://wiki.batocera.org/scripting_services_rules_examples) documents `/userdata/system/services/`, valid service names and enable/start differences.
- [Custom systems](https://wiki.batocera.org/emulationstation:customize_systems) documents userdata catalog overlays. Exact pinned overlay and launch-command behavior belongs to [launcher configuration options](launcher-configuration-options.md).

The applicable Batocera revision is `155c2d8d304cbb53db52e9479dcf683392821d5c`. Current wiki version statements are not proof of behavior at that revision. The script page itself gives conflicting removal versions for `custom.sh`; the pinned source below is authoritative for this investigation.

## Services do not automatically start with this application

The current [entrypoint](../../../../../src/batocera_gow/runtime/runtime.py) initializes userdata and executes the unprivileged application session. [Session.run](../../../../../src/batocera_gow/runtime/runtime.py) starts Xwayland, D-Bus, Openbox, hotkeygen and its command. [Frontend.run](../../../../../src/batocera_gow/runtime/runtime.py) runs EmulationStation directly. None runs the ordinary init sequence or `S99userservices`.

Pinned [S99userservices][init-services] reads `system.services` and starts enabled service files as child processes. It also migrates `custom.sh` into `services/custom_service` when invoked. Those actions do not happen merely because the files or enabled setting exist. Therefore enabling a userdata service does not make it run automatically on Wolf application startup. Adding boot/service integration is not needed for this investigation and was not performed.

A caller can explicitly invoke the pinned [batocera-services][services] command without booting. Its `start` action calls a matching service directly or through Bash, without checking whether it is enabled. Its `enable` action changes `system.services` and does not start the service. This source distinction corrects the script page's instruction to enable before starting, but is not a proposal to add a service. A service's `export` affects its own descendants, not the existing EmulationStation/configgen process.

There is a narrower startup exception, not a general hook. [StateInitializer.populate](../../../../../src/batocera_gow/runtime/runtime.py) explicitly invokes stock `S12populateshare start` during fresh initialization. The pinned [population script][populate] would invoke `/boot/postshare.sh` if present. However, [StateInitializer.run](../../../../../src/batocera_gow/runtime/runtime.py) returns early for valid initialized state and explicitly rejects an existing or symlinked `/boot/postshare.sh` before fresh population. Installing that boot hook is not compatible with the current initialization contract.

## Game hooks do not require boot

The pinned [emulator launcher][launcher] invokes system then user `gameStart` scripts before `generator.generate`. It invokes user then system `gameStop` scripts after normal emulator return. [callExternalScripts][external-scripts] recursively executes executable files as child processes; it does not source shell code or import an environment result. These are launch-path hooks, so they remain applicable without `S99userservices` or normal boot when the stock launcher runs.

This timing matters. A `gameStart` script cannot repair the final child's library path with `export LD_LIBRARY_PATH=...`. Its parent does not inherit that export. Even an environment prefix applied before configgen would lose to DuckStation's explicit `Command.env` library path. The final [runCommand][run-command] copies its own environment, overwrites matching keys with `Command.env`, then starts the command. There is no post-generation environment-import hook in this inspected path.

Hooks can change files, but that is not equivalent to changing the parent's environment. A managed native INI value written before generation can be overwritten immediately. Use the supported Batocera option for managed values. [DuckStation configuration options](duckstation-configuration-options.md) records the unmanaged logging keys which the generator preserves, their exact consumers and their diagnostic limits.

## Consequence for the next experiment

Do not add boot services to solve a per-emulator launch problem. The useful candidates are preserved native diagnostic settings and a PS1-only userdata EmulationStation command override which still invokes the stock launcher. The companion [launcher research](launcher-configuration-options.md) owns the exact pinned overlay semantics, inherited environment route and optional post-configgen executable wrapper.

A cleaner way to install a wrapper is not evidence that its library-path recipe fixes OpenGL. The [existing native result](duckstation-startup-failure.md#post-configgen-library-path-restoration-test) already records failure after restoring injected library directories while retaining shaderc. These documentation findings neither repeat that test nor resolve ticket 05 or its dependent baseline.

[init-services]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/board/batocera/fsoverlay/etc/init.d/S99userservices
[services]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-scripts/scripts/batocera-services
[populate]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/board/batocera/fsoverlay/etc/init.d/S12populateshare
[launcher]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/emulatorlauncher.py#L170-L245
[external-scripts]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/emulatorlauncher.py#L400-L410
[run-command]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/emulatorlauncher.py#L574-L589
