# Batocera integration and overrides

## Applicability

Read this standard when changing Batocera startup, EmulationStation system commands, configgen integration, emulator wrappers or persistent userdata setup. It governs new and changed work alongside [shared standards](general.md). Policy and agreed designs are not claims of installed behavior; [current application state](../current/app.md) owns those claims.

## Preserve stock Batocera for upgrades

Do not modify the supplied stock Batocera payload to make our integration work. Keep its emulator binaries, configgen, libraries, system catalogs and controller/hotkey definitions intact. Do not carry a downstream Batocera source patch or replace a stock file with a project version. Supported userdata configuration and separate project-owned wrappers are additive integration, not permission to patch the upstream implementation.

This boundary is deliberate: a new official Batocera release should not require rebasing a collection of local source and binary patches. Keep compatibility fixes in our own startup/runtime assets and scoped userdata overrides so they can be reviewed, tested and removed independently.

This does not promise zero-work upgrades. Pin the upstream input, inspect changed setting/command consumers and wrapper assumptions, verify stock inventory preservation, and rerun affected native paths before qualifying a replacement image. If a solution requires modifying stock Batocera, stop and raise that conflict instead of silently weakening this constraint.

## Preferred override mechanisms

Use the narrowest mechanism that reaches the demonstrated failure while preserving stock behavior:

1. Prefer a supported Batocera setting or emulator-native setting that the pinned generator preserves. Check the actual consumer and precedence; a key accepted by one generator is not a universal configgen option.
2. Prefer a documented userdata customization over replacing a stock file. For frontend command changes, use a partial `es_systems_<project_name>.cfg` with only the affected system and fields. Retain the normal stock launcher and its frontend placeholders.
3. If generation overwrites the needed value or only a final executable argument can fix the failure, consider a narrowly scoped post-generation executable wrapper. Establish the actual generated command, environment merge and executable lookup before adopting it.

Do not bypass configgen to fix a graphics problem. It also owns controller configuration, emulator settings and the normal hotkey path. Do not replace stock generators, emulator binaries or vendor libraries as an incidental workaround. Keep project changes additive under the project-owned runtime and scoped userdata files.

Batocera [documents partial frontend overrides](https://wiki.batocera.org/emulationstation:customize_systems), not a universal post-configgen wrapper API. A wrapper selected through `PATH` depends on the generator emitting a bare executable name and the launcher preserving that path. An absolute generated executable path does not use this lookup. Record the source pin and recheck both assumptions on upgrades. The [pinned launcher audit](../completed/specs/wolf-integration/research/launcher-configuration-options.md#official-support-versus-executable-interception) contains the inspected consumers and source links.

## Process and configuration boundaries

Read the final generated configuration when deciding whether an override applies. Do not infer the renderer from a frontend preference that configgen may resolve or replace. Leave unrelated renderers and emulators unchanged; avoid global graphics flags or blanket library-path changes for a single-emulator issue.

A hook running as a separate child cannot change the launcher's environment by exporting variables. The inspected stock `gameStart` hooks run before generation and through a child process, not a sourced shell. Use such hooks for their documented lifecycle effects, not as an assumed late environment override. A service has the same parent/child limitation. See the [script documentation](https://wiki.batocera.org/launch_a_script) and [actual hook/configuration ordering](../completed/specs/wolf-integration/research/launcher-configuration-options.md#hooks-and-custom-configuration-are-not-interchangeable).

A wrapper must retain generated arguments and environment except for its explicitly justified correction, then `exec` the absolute stock binary. The absolute path prevents recursive lookup of the wrapper; `exec` preserves the final process and exit chain needed by supervision and native-exit checks. Do not reconstruct or discard stock launch arguments to simplify interception.

## Startup installation and ownership

For project-managed automatic installation, run setup in the additive container startup adapter after userdata is available and before EmulationStation reads its system catalog. Do not depend on Batocera's boot/service sequence when the container launches only the application.

Keep executable assets in the image's project-owned runtime. Keep only the scoped persistent configuration in the profile's userdata. Follow the existing `/userdata` to mounted-home arrangement; Wolf owns the home mount, so do not add another explicit home bind. Profile/runner identity selects persistent state, and a renamed runner is not a harmless display-name change. See [runtime operations](../../README.md#runtime-flow-on-wolf) and [profile boundaries](../current/app.md).

An install-if-missing setup must:

- Create its own absent override automatically, without requiring manual installation in each profile.
- Leave the expected installed file untouched on subsequent starts.
- Preserve and report a different file at its destination or a conflicting user command override instead of silently overwriting either.
- Leave other system definitions and profiles unchanged.

Install-if-missing is not an automatic update or migration policy. Define any later replacement policy explicitly before changing existing persistent files. Do not rely on unspecified ordering between conflicting partial system overlays.

## DuckStation visual-selection example

The implemented DuckStation adapter illustrates these rules. [Its exploration topic](../completed/specs/wolf-integration/explore.md#configgen-preserving-emulator-wrappers) owns the case-specific decisions; [current application state](../current/app.md#scoped-duckstation-opengl-correction) records image-bound qualification and deployment limits.

| Piece                                   | Agreed location                                                                   | Reason                                                                                                                        |
| --------------------------------------- | --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Maintained installer and wrapper source | `src/batocera_gow/runtime/`, with non-Python launchers in `build-assets/runtime/` | Keep the compatibility code with the additive startup adapter.                                                                |
| Packaged wrapper                        | `/opt/gow-full-x86/emulator-wrappers/duckstation-qt`                              | A dedicated lookup directory intercepts only the explicitly provided executable, without replacing `/usr/bin/duckstation-qt`. |
| Partial PSX frontend override           | `/userdata/system/configs/emulationstation/es_systems_gow_duckstation.cfg`        | Use the documented persistent customization directory instead of editing the stock system catalog.                            |
| Final generated settings to inspect     | `/userdata/system/configs/duckstation/settings.ini`                               | The wrapper reads configgen's actual `GPU/Renderer` decision, not an earlier preference.                                      |

The partial command prepends the dedicated wrapper directory to `PATH` and invokes stock `/usr/bin/emulatorlauncher` with the normal placeholders. The generated bare `duckstation-qt` command then selects the wrapper after generation. Only generated `OpenGL` selection receives Qt's `-visual <id>` correction; Vulkan and other renderer values pass through unchanged, and both paths exec stock `/usr/bin/duckstation-qt`.

The [observed failure](../completed/specs/wolf-integration/research/duckstation-startup-failure.md#actual-egl-config-and-qt-window-trace) was a difference between the EGL config's native visual and Qt's actual X11 window visual, with `EGL_BAD_CONFIG` during surface creation. A [bounded corrected-visual comparison](../completed/specs/wolf-integration/research/duckstation-startup-failure.md#corrected-qt-visual-actual-surface-success) created the actual surface while retaining stock `LD_LIBRARY_PATH`. Library-path restoration alone had not solved the launch failure. The correction therefore targets the Qt window rather than imposing a global library override.

X11 visual IDs are server- and screen-specific. The diagnostic `0x7d` is not a portable default. The accepted design selects the visual automatically from the live EGL/X11 configuration and validates it on the actual screen; the current Qt consumer makes a stale or wrong-screen value unsafe. Do not require manual IDs or reuse a discovered ID across sessions. Discovery or validation failure stops the OpenGL launch with a clear diagnostic. Do not retry without the correction or switch to Vulkan to turn an OpenGL failure into a pass; qualify explicitly selected OpenGL and Vulkan independently.

Surface creation is not game acceptance. Qualify actual rendered output and the approved native-exit/evidence/cleanup contract separately for each renderer; retain diagnostic failures as failures. The maintained PSX fixture uses supported `psx.bezel=none`, matching the working beta profile and avoiding the extra MangoHUD interposer that stock configgen adds for default bezels. This is a disposable test setting, not a global HUD policy or qualification of MangoHUD-enabled bezels. Consult the [testing guide](../../tests/README.md#duckstation-exit-smoke) and [fixture comparison](../completed/specs/wolf-integration/research/duckstation-startup-failure.md#native-regression-invocation-and-fixture-correction) for image-bound evidence and limits.

## Comments and verification

Put non-obvious reasons beside the code that enforces them. Installer comments should explain pre-ES timing, idempotence and ownership protection. Wrapper comments should explain generated-setting precedence, renderer-specific pass-through, the pinned executable-lookup assumption, the correction's observed failure mechanism and the absolute final exec. Link the issue/research record rather than copying its experiment history. Do not add comments that merely restate commands.

Exercise first installation, repeated startup and conflicting existing configuration in disposable userdata before touching operator profiles. Exercise the correction and its unchanged renderer path through the normal stock launcher. A direct root-shell launch or isolated EGL probe does not establish frontend behavior: use the actual application UID, groups, environment and native session resources.

Preserve stock shortcut definitions and generated mappings; the additive adapter transports their output rather than replacing their policy. Verify affected previously working emulator paths when a shared startup or graphics change could affect them. Bind results to the actual packaged image and exercised selection; do not transfer another image's or emulator's success to the changed route. Native execution, profile installation and restarts still require their applicable authorization.
