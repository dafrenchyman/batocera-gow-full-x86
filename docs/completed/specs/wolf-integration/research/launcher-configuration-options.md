# Launcher configuration options for DuckStation under Wolf

Historical source observations refer to the experiment layout and the recorded image/revision, not a new measurement of current behavior. Source links now navigate the maintained counterparts; obsolete experiment line anchors are not current line numbers.

Research only, 2026-10-31. No emulator, remote action, configuration change, build, test, formatter or restart was performed. This note owns launcher/configuration routing, not DuckStation's native INI settings. Historical observations remain in [DuckStation startup failure](duckstation-startup-failure.md).

## Finding

The official documentation does offer a useful configuration-first entry point: a partial EmulationStation system overlay can replace only the PSX launch command, retain normal `emulatorlauncher` and pass an environment variable into configgen. The exact packaged frontend supports that merge. This is an early launch entry point, not a late environment override or a demonstrated OpenGL fix. In particular, an `LD_LIBRARY_PATH` prefix before `emulatorlauncher` still loses to DuckStation's generator. No generic `batocera.conf` key for overriding the final DuckStation environment, command prefix or configgen bypass was found in the complete launcher, base generator and DuckStation generator paths inspected below. [customize][es-merge][es-command][generator][launcher-run]

The most relevant new launcher-side candidate is therefore a PSX-only custom command carrying a source-supported diagnostic environment selector while preserving normal generation. Display mode and optional HUD controls exist but are weaker candidates for the reported EGL failures. Boot-time NVIDIA selection is a different ownership path and is not a container-driver remedy. None of these candidates was exercised by this research. [gl-context][launcher-start][standalone][nvidia-boot][adapter]

## Versions and evidence limits

All Batocera source links below use commit `155c2d8d304cbb53db52e9479dcf683392821d5c`. Its EmulationStation recipe pins `batocera-linux/batocera-emulationstation` commit `2c29a330e487210a7d51ad2650bb7b280ea44c86`; frontend findings use that commit, not upstream master. The package lists three numbered patches plus battery/config-event patches. The loader and launch-command evidence comes from the pinned frontend files. [es-recipe]

DuckStation context-selection evidence uses `duckstation/old-releases` commit `3a08ad18406efc1ddc4927a59bea715961bb63fa`, the source pin retained in the existing investigation. Batocera patches and the generated launch environment still matter; unpatched upstream behavior is not a fresh observation of the packaged child. [prior-source][gl-context]

The live [coding rules][coding] and [configuration syntax][syntax] pages were read directly. They describe the configuration model and link to master, not this image's immutable source. The live [customize systems][customize] page was also read, using its raw export because the HTML reader omitted the body. Its Python 3.9 example is historical, whereas the pinned generator emits the version-independent `emulatorlauncher` command. The wiki's ES feature-file layout also predates this pin's per-emulator YAML files. For this image, an actual source consumer wins over a wiki label or example. [customize-raw][system-builder][duck-features]

The live PSX wiki's standalone DuckStation table advertises `psx.gfxbackend`, but this pin reads `duckstation_gfxbackend`. Do not copy the old key into a candidate or assume arbitrary native keys pass through. `.retroarch.` and `.retroarchcore.` are expressly RetroArch facilities, not standalone DuckStation facilities. [psx-wiki][generator][syntax]

## What wins when settings disagree

The precise low-to-high precedence in `Emulator.py` is:

1. Generic YAML `default`.
2. Architecture YAML `default`.
3. Generic YAML system entry, such as `psx`.
4. Architecture YAML system entry.
5. `display.*` entries, with their names retained, then `controllers.*` entries.
6. `global.<key>`.
7. `psx.<key>`.
8. `psx.folder["<ROM parent path>"].<key>`.
9. `psx["<ROM filename including extension>"].<key>`.
10. Specific launcher arguments where implemented, notably `-emulator` and `-core`.

These are dictionary merges, not automatic translation of every key into native emulator settings. The loader selects the ROM's immediate parent folder; it does not walk ancestor directories. It removes `=` and `#` from the game's configuration name before loading game settings. `UnixSettings` normalizes names for matching and ordinarily ignores values `''`, `default` and `auto`; `display.*` is loaded with `keep_defaults=True`. Thus setting a higher-priority key to `auto` is not a reliable way to erase a lower-priority explicit value. Remove the explicit override at its owning level. [emulator][unix-settings]

The x86_64 recipe installs `configgen-defaults-x86_64.yml` as `/usr/share/batocera/configgen/configgen-defaults-arch.yml`. Generic defaults include `videomode: default` and `hud_support: true`; the x86_64 defaults also enable HUD support. Generic PSX defaults select libretro/pcsx_rearmed, and the inspected x86_64 file has no PSX override. Explicit standalone DuckStation selection must therefore come from a higher level or launcher argument, not an assumption about the platform default. This is selection accounting, not a proposal to change emulator. [configgen-recipe][defaults][arch-defaults][emulator]

For supported keys, global/system/folder/game scopes reach standalone DuckStation through this common loader. For example, the generator reads the resolved `duckstation_gfxbackend` with fallback `OpenGL`. Its native INI is then read and selected values are rewritten. Scope support does not imply an environment-variable namespace: `psx.LD_LIBRARY_PATH=...` merely loads a configuration entry unless a consumer reads it, and this DuckStation generator does not. [emulator][generator]

## Priority: partial frontend command overlay

The documented location is `/userdata/system/configs/emulationstation/es_systems_<custom_name>.cfg`. A file with `<system><name>psx</name>...</system>` merges into the matching existing system. The pinned loader removes each supplied child tag from that matching system and appends the supplied replacement. Unmentioned tags remain. A partial `<command>` replacement therefore need not copy the complete catalog, emulator list, extensions or ROM path. Multiple overlays that replace the same tag are order-sensitive; this source does not establish a stable ordering guarantee to use as configuration precedence. Avoid overlapping owners. [customize-raw][es-merge][es-paths]

Whole-file replacement is also supported, but is unnecessary here. The pinned frontend first prefers user `es_systems_custom.cfg`, then user `es_systems.cfg`, then the installed catalog. Its additional-overlay pass still processes matching `es_systems_*.cfg` files. Prefer one narrowly owned partial file rather than duplicating the stock catalog. [es-config-path][es-merge]

The pinned default command is:

```text
emulatorlauncher %CONTROLLERSCONFIG% -system %SYSTEM% -rom %ROM% -gameinfoxml %GAMEINFOXML% -systemname %SYSTEMNAME%
```

The frontend obtains the system command unless an emulator/core-specific XML `command` attribute takes precedence. It expands the placeholders, adds forced emulator/core arguments when required, and runs the resulting command through its Linux shell execution path. Consequently, a PSX-only `<command>` can prepend `/usr/bin/env NAME=value` or invoke a carefully quoted prelude that finally `exec`s `/usr/bin/emulatorlauncher` with the stock placeholders. The absolute executable path and preservation of all placeholders should be checked against the installed catalog before any separately authorized trial. Do not reuse the wiki's hardcoded Python path. [system-builder][es-command][es-expand][es-process]

For example, the source-grounded diagnostic hypothesis is a partial PSX command with `PREFER_GLES_CONTEXT=1` before the normal launcher. This retains Batocera's generation, input/hotkey setup and final command assembly. It is not the same as directly launching `duckstation-qt`, setting arbitrary `batocera.conf` keys, installing a post-configgen hook, or replacing stock source. Native selector behavior is summarized only in the candidate ranking below. No overlay was created or installed. [launcher-start][gl-context]

The same early command can prepend a userdata-owned wrapper directory to `PATH` while still executing untouched `/usr/bin/emulatorlauncher` with the stock placeholders. Since final `runCommand` preserves `PATH` and DuckStation's generated command uses the bare executable name, this can select a wrapper after config generation. That wrapper must finally exec the absolute untouched emulator binary to avoid recursion. It offers a userdata-only installation route for a post-generation experiment without replacing the stock catalog or binary. It is not a new graphics fix: trial `e13077521317447aa98ab2c3a677af10` already restored `/usr/nvidia/lib:/usr/nvidia/lib32:/usr/stenzek-shaderc/lib:/usr/lib` at that boundary and still failed. A different installation mechanism does not justify repeating the same failed recipe. The Qt/non-Qt branch still follows the generator's absolute Qt-existence check; a wrapper name must match the branch actually emitted. These frontend changes affect ES launches only, not a native CLI suite that directly invokes its own command. [generator][launcher-run][es-merge][prior-wrapper]

## Complete normal command and environment path

The relevant order is fixed in the pinned launcher:

1. Load effective configuration and select the generator.
2. Obtain current video mode, perform automatic or explicit mode handling and obtain current resolution.
3. Set parent `SDL_RENDER_VSYNC` from resolved `sdlvsync`, default true.
4. Invoke system then user `gameStart` scripts.
5. Enter evmapy/hotkey contexts, change directory only if the generator requests it, and call `generate`.
6. Optionally add MangoHud environment and prepend `mangohud` when HUD or a HUD bezel is actually active.
7. Perform gun-overlay/mouse-reset work, then `runCommand`.
8. Copy `os.environ`, overlay `command.env`, and `subprocess.Popen(command.array, env=command.env)` without a shell.
9. After child completion, invoke user then system `gameStop`; restore video mode if changed. [launcher-start][launcher-run][generator-base]

DuckStation checks `/usr/bin/duckstation-qt` exists but emits the bare executable name `duckstation-qt`, with `-batch -nogui -- <rom>`. Its fallback command is `duckstation-nogui -batch -fullscreen -- <rom>`. It reads/writes the fixed `CONFIGS/duckstation/settings.ini`, creates the controller database and returns the following final environment entries. These entries overwrite inherited values in `runCommand`. [generator]

| Entry                      | Exact generator behavior                                                                                                             |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `LD_LIBRARY_PATH`          | Always `/usr/stenzek-shaderc/lib:/usr/lib`.                                                                                          |
| `XDG_CONFIG_HOME`          | Always Batocera `CONFIGS`, `/userdata/system/configs`.                                                                               |
| `QT_QPA_PLATFORM`          | `wayland` if inherited `WAYLAND_DISPLAY` is nonempty, otherwise `xcb`. It does not preserve a requested inherited `QT_QPA_PLATFORM`. |
| `SDL_GAMECONTROLLERCONFIG` | Generated from the passed controllers.                                                                                               |
| `SDL_JOYSTICK_HIDAPI`      | Always `0`.                                                                                                                          |

Other inherited environment entries survive this merge unless some earlier owner changed them. Thus a prefix can deliver `PREFER_GLES_CONTEXT`, `QT_XCB_GL_INTEGRATION`, EGL/vendor diagnostic variables or `DISPLAY` to the child, but mere survival does not prove the library consumes a particular value or that changing it is useful. `DISPLAY` selects an X server; it is not `display.*` in `batocera.conf`. The existing adapter sets `DISPLAY=:0`, Xauthority, X11 session/SDL and Qt xcb, and removes `WAYLAND_DISPLAY`, `WAYLAND_SOCKET` and `SWAYSOCK`. This makes the stock generator choose xcb too. Faking a Wayland variable is not a valid candidate for this external-Xwayland design. [launcher-run][generator][paths][adapter-x11]

The inspected complete common launcher, base generator and DuckStation generator have no generic final environment map or configurable late command-prefix callback. This is a bounded negative finding about that selected path and pin, not every Batocera package, future release or user-defined frontend command. A PATH-resolved wrapper after generation is possible because of the bare executable name, but that is executable lookup, not a documented DuckStation override key. The existing investigation already exercised a temporary library-path wrapper and records its negative result. Do not repeat it as a new untested candidate. [generator][generator-base][launcher-start][launcher-run][prior-wrapper]

### Hooks and custom configuration are not interchangeable

The official [script page][script-wiki] documents executable game hooks under `/userdata/system/scripts/` and separate frontend event hooks. The pinned consumer recursively executes executable files in its system and user script directories with event/system/emulator/core/ROM arguments using `subprocess.call`. They are children, not sourced scripts. Their exports cannot update the launcher parent's environment. They run before generation, so editing a generator-managed INI value there also loses to the later generator write. File-based effects on preserved native settings are a different mechanism and need per-setting evidence. [launcher-scripts][launcher-start][paths]

Frontend `game-start` scripts likewise run as separate processes through `ProcessStartInfo`, not as parent-shell exports. The frontend fires the event before its game process launch. These events do not provide a late environment update to `runCommand`. [es-events][es-scripting][es-process]

`configfile` is demonstrably generator-specific. Libretro's generator checks it and uses it as the RetroArch `--config` path, bypassing its own default config-generation branch. The complete DuckStation generator instead always uses its fixed settings path and does not read `configfile` or `customcfg`. The common launcher never interprets either as a universal skip-generation flag. A frontend `<command>` that directly executes DuckStation would truly bypass configgen, but would also bypass its normal controller/configuration/hotkey path. It is not an equivalent configuration override and is not recommended here. [libretro-configfile][generator][launcher-start]

### Official support versus executable interception

Rechecked the live `coding_rules`, `emulationstation:customize_systems`, `launch_a_script` and `scripting_services_rules_examples` pages on 2026-10-31. None documents a general post-configgen executable/argument wrapper, command-prefix setting or arbitrary DuckStation command-line arguments setting. The pinned launcher argument parser also has no arbitrary emulator-argument forwarding facility, and the DuckStation generator constructs its fixed argv without reading such a setting. In particular, adding `-visual <id>` to the frontend's `emulatorlauncher` command does not forward it to Qt. The launcher uses `argparse.parse_args()`, not a pass-through parser. This is a negative finding limited to those pages and the pinned normal DuckStation path. [coding][customize-raw][script-wiki][services-wiki][launcher-cli][generator]

The proposed `gameStart` script exporting `LD_LIBRARY_PATH` is not an inline post-configgen hook. At this pin it runs before `generate` as a separate child through `subprocess.call`, so its exports cannot change its parent's environment. The generator would overwrite an inherited library-path value anyway. Services are startup/shutdown scripts, not an alternative final-command callback; their exports likewise do not update an already-running launcher. [launcher-start][launcher-scripts][launcher-run][generator][services-wiki]

A custom ES `<command>` is an officially documented frontend override, although the wiki recommends retaining the default command. Directly invoking `duckstation-qt` there allows the author to supply native arguments but bypasses configgen and its normal controller/configuration/hotkey setup. Retaining the stock `emulatorlauncher` instead and prepending a fixed wrapper directory to `PATH` preserves that setup. The generated bare `duckstation-qt` name can then resolve to the wrapper after generation. The installation entry point is documented; the late interception is generic executable lookup, not an official dedicated Batocera wrapper API or a stable cross-version contract. It depends on this generator continuing to emit a bare name and the launcher preserving `PATH`. [customize-raw][generator][launcher-start][launcher-run]

`-visual <id>` belongs to Qt's XCB integration, not a DuckStation INI key or Batocera option. Qt 6.10.1 parses it as a numeric visual ID, removes it from argv and passes the selection to `QXcbConnection`. The retained DuckStation pin constructs `QApplication` before parsing its remaining arguments. This establishes the native argument consumer, not a supported Batocera transport or proof that a selected visual fixes EGL. A post-generation executable wrapper can supply that argument without changing stock source, but its existence must not be described as a newly discovered official hook. The prior failed `LD_LIBRARY_PATH` restoration is a separate experiment, not evidence against a different visual selection and not a new fix to repeat. [qt-xcb-visual][duck-qt-cli][prior-wrapper]

Keep newer upstream separate. The live wiki is not pinned documentation. During this recheck, upstream `master` resolved to `a3d49969295830ff1f136d393e33839f858fa8d7`; its core directory no longer contains the old `batocera-configgen` package path, and its Python tree contains reorganized `batocera-launch-*` packages. This note does not audit that replacement architecture or claim its interfaces are absent. None of those newer changes establishes a wrapper facility in installed revision `155c2d8d304cbb53db52e9479dcf683392821d5c`. No runtime or configuration change followed this clarification. [newer-core-tree][newer-python-tree]

The accepted project design is recorded in [exploration](../explore.md#configgen-preserving-emulator-wrappers). Reusable policy and the proposed override locations are in the [Batocera integration standard](../../../../standards/batocera.md); neither document claims that the installer or wrapper has been implemented.

## Display, X11 and NVIDIA settings

| Setting or mechanism                                                                                        | Consumer, default and scope                                                                                                                                                                                                                                      | Relevance here                                                                                                                                                                                                                                                                                                                              |
| ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `global.videomode`, `psx.videomode`, folder/game `videomode`                                                | Base generator returns resolved `videomode`; default YAML value is `default`. Launcher changes output mode before generation and restores it afterward. Explicit modes must exist in `batocera-resolution listModes`; `max-WxH` is a supported capped-mode form. | Applies to standalone DuckStation but changes display mode, not internal rendering scale or the EGL provider. In the Xorg script this becomes RandR operations on the selected primary output. An externally owned Xwayland server still determines what those requests mean. [generator-base][launcher-start][video-mode][resolution-xorg] |
| `global.videooutput`, `global.videooutput2`, `global.videooutput3`                                          | `emulationstation-standalone` reads master settings, then ordinary settings, validates against listed outputs and calls `setOutput`. With no valid primary choice it finds a current/available output.                                                           | This is frontend display setup, not a DuckStation per-game adapter or EGLConfig selector. No per-game `videooutput` selection occurs in the inspected normal DuckStation launcher path. [standalone][launcher-start][generator]                                                                                                             |
| `es.resolution`, `es.resolution2`, `es.resolution3`                                                         | Standalone frontend reads primary boot `es.resolution`, with secondary/tertiary values from settings; absent values invoke automatic min/max handling. The Xorg min/max helper also reads boot then master resolution.                                           | Desktop/output mode controls. Do not conflate boot configuration with a container-owned emulator option. [standalone][resolution-xorg]                                                                                                                                                                                                      |
| `display.rotate[.<output>]`, `display.rotate2`, `display.rotate3`, `display.reflection`, `display.position` | Frontend setup applies rotation/reflection where supported; `display.position` repositioning is labwc-specific. Common config loading retains `display.*`, but retaining a key does not imply DuckStation uses it.                                               | Not a selector for Qt's X connection or DuckStation's EGL API. No direct EGL-display/config consumer appears in this selected generator path. [standalone][emulator][generator]                                                                                                                                                             |
| `global.dpi`                                                                                                | Standalone frontend calls `batocera-resolution setDPI`; Xorg implementation calls `xrandr --dpi`. Sample configuration comments use 96.                                                                                                                          | UI/display sizing, not an EGL provider fix. [standalone][resolution-xorg][conf]                                                                                                                                                                                                                                                             |
| `psx.hud=none`, `psx.bezel=none`, `psx.hud_support=0`                                                       | HUD support defaults true. `hud=none` suppresses HUD content, but a bezel can still cause MangoHud injection; `hud_support=0` skips that entire launcher branch. These use normal setting scopes.                                                                | A conditional diagnostic to remove actual optional interposition, only if the launch is using it. Do not claim it is active in the failing launch without its argv/environment evidence. [defaults][launcher-start]                                                                                                                         |
| `psx.sdlvsync=0`                                                                                            | Common launcher defaults it true and exports `SDL_RENDER_VSYNC=0` when disabled.                                                                                                                                                                                 | Not DuckStation's GPU/display VSync control and no evidenced selector for its EGL display/window-surface construction. Low relevance. [launcher-start][generator]                                                                                                                                                                           |

The boot file's `nvidia-driver` controls Batocera's own boot-time driver selection: absent or `true` uses detection, `legacy580`/`legacy470` request those branches, and `false` requests Nouveau. `S05nvidia` invokes `batocera-nvidia`, which rewrites installed driver symlinks/JSONs/module links and loads modules. These are bare-metal boot actions, not standalone-emulator keys. The source has an ambiguous legacy alias in its ordered branches; use the explicit documented names when describing it, not `legacy`. No such change is proposed. [nvidia-boot][nvidia-init][nvidia-selector]

Similarly `nvidia-prime` is read by `S30checkprime` for multi-GPU boot detection. Its marker later causes the Xorg startup script to inspect RandR providers and export `__NV_PRIME_RENDER_OFFLOAD`, `__VK_LAYER_NV_optimus`, `__GLX_VENDOR_LIBRARY_NAME`, `VDPAU_DRIVER` and `LIBVA_DRIVER_NAME`. That local Xorg startup path is separate from our adapter's injected `/usr/nvidia` libraries, generated EGL/vendor selectors and external Xwayland. A boot setting cannot be assumed to reconfigure those owners. The installed NVIDIA workaround script is gated to its PRIME marker and model2/xbox360/wine system arguments, not PSX, and its child exports are not parent environment edits. [prime-check][xinitrc][nvidia-hook][adapter]

## Ranked configuration-first candidates

1. **PSX-only early environment diagnostic through a partial frontend command.** `PREFER_GLES_CONTEXT=1` is the strongest concrete launcher-side candidate found. The pinned DuckStation consumer moves GLES versions ahead of desktop versions while leaving fallback available. The generator does not overwrite it, so an early prefix survives. This retains the OpenGL renderer and EGL-X11 route; it is not a GLES-only force, a GLX switch or proof of compatibility. It could distinguish API/config negotiation at the manual surface-failure boundary, but is less targeted at an earlier failure to acquire an EGL display. No overlay/prefix trial was run here. [es-merge][es-expand][es-process][launcher-run][gl-context]
2. **Disable actual optional HUD/bezel injection.** If the failing launch demonstrably prepends MangoHud, a scoped `hud_support=0` diagnostic removes that launcher interposition without changing the renderer. Without evidence of injection, it is not a reason to edit settings. [launcher-start]
3. **Hold a supported explicit display mode.** A scoped `psx.videomode=<exact listed mode>` can avoid automatic min/max mode adjustment and narrow geometry/mode-change differences. It does not make an invalid EGLConfig valid and may be irrelevant on the external Xwayland output. Select from actual available modes only in a separately authorized trial; do not assume a physical HDMI output or invent a refresh-rate spelling. [launcher-start][video-mode][resolution-xorg]

`QT_XCB_GL_INTEGRATION` or EGL diagnostics can be transported by the same early command, but no new Qt value is recommended by this launcher audit. The pinned DuckStation X11 OpenGL consumer directly chooses EGL-X11, so Qt xcb does not imply DuckStation uses GLX, and a Qt integration variable cannot be described as replacing that explicit route. Keep any such test with the separate native Qt/EGL source analysis. [gl-context][prior-source]

There is no supported launcher key identified here that preserves an arbitrary final `LD_LIBRARY_PATH` or overrides the generator's Qt platform value. The existing post-configgen restoration trial already failed before output/chord in the automated original-selection route. Its pre-exec witness is not a sampled final-child provider map, and its earlier EGL-display/context failure is not the operator's later EGL_BAD_CONFIG surface failure. These limits forbid both declaring all OpenGL broken and presenting library-path restoration as an untried fix. [generator][launcher-run][prior-wrapper]

## Sources

[coding]: https://wiki.batocera.org/coding_rules
[syntax]: https://wiki.batocera.org/batocera_conf_syntax
[customize]: https://wiki.batocera.org/emulationstation:customize_systems
[customize-raw]: https://wiki.batocera.org/emulationstation:customize_systems?do=export_raw
[psx-wiki]: https://wiki.batocera.org/systems:psx
[emulator]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/Emulator.py#L43-L211
[unix-settings]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/settings/unixSettings.py#L18-L93
[configgen-recipe]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/batocera-configgen.mk#L48-L111
[defaults]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configs/configgen-defaults.yml
[arch-defaults]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configs/configgen-defaults-x86_64.yml
[generator]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/generators/duckstation/duckstationGenerator.py
[generator-base]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/generators/Generator.py#L32-L62
[launcher-start]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/emulatorlauncher.py#L83-L262
[launcher-scripts]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/emulatorlauncher.py#L399-L413
[launcher-run]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/emulatorlauncher.py#L574-L602
[paths]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/batoceraPaths.py
[libretro-configfile]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/generators/libretro/libretroGenerator.py#L96-L141
[video-mode]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/utils/videoMode.py
[resolution-xorg]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-resolution/scripts/resolution/batocera-resolution.xorg
[conf]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-system/batocera.conf#L235-L254
[duck-features]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/emulators/duckstation-common/duckstation.emulator.yml
[es-recipe]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/emulationstation/batocera-emulationstation/batocera-emulationstation.mk
[system-builder]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/python-src/batocera-es-system/batocera_es_system/es_systems.py#L27-L98
[es-merge]: https://github.com/batocera-linux/batocera-emulationstation/blob/2c29a330e487210a7d51ad2650bb7b280ea44c86/es-app/src/SystemData.cpp#L778-L850
[es-config-path]: https://github.com/batocera-linux/batocera-emulationstation/blob/2c29a330e487210a7d51ad2650bb7b280ea44c86/es-app/src/SystemData.cpp#L1304-L1319
[es-paths]: https://github.com/batocera-linux/batocera-emulationstation/blob/2c29a330e487210a7d51ad2650bb7b280ea44c86/es-core/src/Paths.cpp#L48-L53
[es-command]: https://github.com/batocera-linux/batocera-emulationstation/blob/2c29a330e487210a7d51ad2650bb7b280ea44c86/es-app/src/SystemData.cpp#L1944-L1960
[es-expand]: https://github.com/batocera-linux/batocera-emulationstation/blob/2c29a330e487210a7d51ad2650bb7b280ea44c86/es-app/src/FileData.cpp#L548-L649
[es-process]: https://github.com/batocera-linux/batocera-emulationstation/blob/2c29a330e487210a7d51ad2650bb7b280ea44c86/es-core/src/utils/Platform.cpp#L158-L180
[es-events]: https://github.com/batocera-linux/batocera-emulationstation/blob/2c29a330e487210a7d51ad2650bb7b280ea44c86/es-app/src/FileData.cpp#L702-L728
[es-scripting]: https://github.com/batocera-linux/batocera-emulationstation/blob/2c29a330e487210a7d51ad2650bb7b280ea44c86/es-core/src/Scripting.cpp#L137-L205
[standalone]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/emulationstation/batocera-emulationstation/emulationstation-standalone#L66-L329
[nvidia-boot]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-system/batocera-boot.conf#L22-L51
[nvidia-init]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/board/batocera/x86/fsoverlay/etc/init.d/S05nvidia#L14-L30
[nvidia-selector]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/gpu/batocera-nvidia/batocera-nvidia#L64-L290
[prime-check]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/board/batocera/x86/fsoverlay/etc/init.d/S30checkprime#L54-L72
[xinitrc]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/emulationstation/batocera-emulationstation/xorg/xinitrc#L25-L60
[nvidia-hook]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/scripts/nvidia-workaround.sh
[gl-context]: https://github.com/duckstation/old-releases/blob/3a08ad18406efc1ddc4927a59bea715961bb63fa/src/util/opengl_context.cpp#L37-L217
[adapter]: ../../../../../src/batocera_gow/runtime/runtime.py
[prior-source]: duckstation-startup-failure.md#sources-and-method
[prior-wrapper]: duckstation-startup-failure.md#post-configgen-library-path-restoration-test
[adapter-x11]: ../../../../../src/batocera_gow/runtime/runtime.py
[script-wiki]: https://wiki.batocera.org/launch_a_script
[services-wiki]: https://wiki.batocera.org/scripting_services_rules_examples
[launcher-cli]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/emulatorlauncher.py#L617-L665
[qt-xcb-visual]: https://code.qt.io/cgit/qt/qtbase.git/tree/src/plugins/platforms/xcb/qxcbintegration.cpp?h=v6.10.1#n144
[duck-qt-cli]: https://github.com/duckstation/old-releases/blob/3a08ad18406efc1ddc4927a59bea715961bb63fa/src/duckstation-qt/qthost.cpp#L2534-L2541
[newer-core-tree]: https://api.github.com/repos/batocera-linux/batocera.linux/contents/package/batocera/core?ref=a3d49969295830ff1f136d393e33839f858fa8d7
[newer-python-tree]: https://api.github.com/repos/batocera-linux/batocera.linux/git/trees/2938890876d2da759cb6c00e0e8e8ea9b08eb6c5?recursive=1
