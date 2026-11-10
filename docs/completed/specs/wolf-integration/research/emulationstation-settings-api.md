# EmulationStation API and DuckStation renderer selection

Historical source observations refer to the experiment layout and the recorded image/revision, not a new measurement of current behavior. Source links now navigate the maintained counterparts; obsolete experiment line anchors are not current line numbers.

Research date: 2026-10-31. Source inspection only. No remote access, configuration writes, emulator runs, builds or tests were performed. This investigation does not authorize replacing the existing test route.

## Answer

The EmulationStation HTTP API in this repository's pinned Batocera does not provide a renderer/settings setter or per-launch renderer override. Its `/launch` endpoint accepts a game path, not a JSON launch specification. Testing DuckStation OpenGL and Vulkan remains possible by preparing Batocera configuration separately before each API launch, but that is a configuration-file-plus-HTTP workflow, not API-only configuration. [P1, P2, P3]

A newer inspected ES reference adds `/input`, which can indirectly operate frontend menus. It still has no direct renderer/configuration setter. That input endpoint is absent from our pinned frontend and is not raw controller input into an emulator. [N1]

## Versions and scope

- Batocera pin: `155c2d8d304cbb53db52e9479dcf683392821d5c`.
- That package's ES pin: `2c29a330e487210a7d51ad2650bb7b280ea44c86`. [P4]
- Newer comparison ES reference: `703116c6aefb61c68f1a5ea1e725ea8bb4d6ba52`. This is an inspected reference, not a claim about every later release.

Inspected HTTP route registrations and launch handlers, metadata importer/schema, configuration persistence behavior, the pinned DuckStation generator and renderer declaration, and the existing local renderer fixture. The negative finding is bounded to these source revisions and their built-in ES HTTP server. It is not a claim about third-party web services or future releases.

## Why the obvious API approaches do not work

`POST /launch` converts the entire body to an absolute path, searches the loaded game catalog for that path and queues `ViewController::launch(file)`. It does not parse renderer options from JSON, query parameters or extra command arguments. A renderer query parameter is not a supported override. A successful HTTP response alone also does not prove the game was found or launched. [P1]

`POST /systems/{systemName}/games/{gameId}` edits declared game metadata through `HttpApi::ImportFromJson`. It is not arbitrary `batocera.conf` editing. The importer accepts declared non-path string fields, and `duckstation_gfxbackend` is not in the metadata schema. Sending that field does not configure the renderer. [P1, P5, P6]

`GET /reloadgames` reloads the game lists; it is not a settings mutation endpoint. `GET /restart` requests `QuitMode::REBOOT`, not a harmless configuration refresh. Neither supplies a renderer value. [P1]

The complete pinned route set exposes frontend operations, systems/game data, metadata/media writes, game-store additions/removals, storage notification and resource reads. No direct settings/configuration/command-execution handler is registered. [P1]

## How renderer selection actually works

The pinned supported system setting is one of:

```ini
psx.duckstation_gfxbackend=OpenGL
```

```ini
psx.duckstation_gfxbackend=Vulkan
```

These are alternatives for separate runs, not two lines to append together. The graphics feature declaration supplies the exact values `OpenGL`, `Vulkan` and `Software`. The generator reads `duckstation_gfxbackend`, defaulting to `OpenGL`, and writes `GPU.Renderer` in DuckStation's generated settings. Editing the managed native `GPU.Renderer` directly is not a substitute because the next generation rewrites it. [P2, P3]

System settings can lose to explicit folder/game overrides. The selected emulator must also actually be standalone DuckStation. A correct test must control the isolated profile and inspect the generated and active renderer, not assume that writing a system key establishes effective behavior. [L1, L2]

A possible hybrid sequence is to prepare isolated userdata with the requested Batocera renderer setting, launch the cataloged game through `/launch`, verify actual output/active renderer, send and verify the exit chord, then use separately controlled state for the other renderer. This is a source-supported workflow proposal, not an API integration executed here. It still requires non-HTTP configuration access and appropriate isolation; nothing should edit the operator's persistent profile as part of this research.

Configgen constructs `UnixSettings(BATOCERA_CONF)` and reads the disk file for each new `Emulator`. [INFERENCE] A renderer-only external change completed before the next launch should therefore reach generation without restarting ES, provided DuckStation is already selected, no higher-priority override wins and no concurrent writer changes that key. This was not runtime-tested. ES's own configuration map can remain stale; do not generalize this to externally changing emulator/core selection. Its saver merges dirty keys against disk rather than unconditionally rewriting every cached value. [P7, P8]

Our existing `EmulatorProbe.prepare_duckstation_renderer` already prepares the requested renderer in owned disposable `batocera.conf`. `duckstation_renderer` checks the generated renderer, and `finalize_duckstation_renderer` checks actual active-backend evidence. No change to these tests is needed merely to test both renderers. [L2]

## Newer API nuance

At the newer reference, `POST /input` takes a configured input name such as `down` or `a` as plain text. It resolves the name against the keyboard input configuration and posts a press/release pair to `Window::input`. This can support frontend UI navigation, so it would be too broad to say that no HTTP interaction could ever change a menu setting. [N1]

However, navigating to Graphics API and selecting Vulkan that way would be UI automation tied to menu state, not a direct `set renderer` API. No DuckStation menu-navigation sequence was executed or qualified here. The route does not exercise our synthetic controller-to-emulator input path and does not exist in the pinned frontend. It is not a reason to change the current tests.

## Sources

- **P1:** [Pinned complete HTTP server and handlers](https://github.com/batocera-linux/batocera-emulationstation/blob/2c29a330e487210a7d51ad2650bb7b280ea44c86/es-app/src/services/HttpServerThread.cpp), especially `/launch`, metadata POST, `/reloadgames` and `/restart`.
- **P2:** [Pinned DuckStation generator](https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/generators/duckstation/duckstationGenerator.py).
- **P3:** [Pinned graphics API declaration](https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/emulators/duckstation-common/gfxbackend.duckstation.emulator.yml).
- **P4:** [Pinned frontend recipe](https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/emulationstation/batocera-emulationstation/batocera-emulationstation.mk). The companion launcher research retains the package pin and patch scope.
- **P5:** [Pinned metadata importer](https://github.com/batocera-linux/batocera-emulationstation/blob/2c29a330e487210a7d51ad2650bb7b280ea44c86/es-app/src/services/HttpApi.cpp).
- **P6:** [Pinned metadata schema](https://github.com/batocera-linux/batocera-emulationstation/blob/2c29a330e487210a7d51ad2650bb7b280ea44c86/es-app/src/MetaData.cpp).
- **P7:** [Pinned Emulator configuration loader](https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/Emulator.py#L43-L211) and [UnixSettings disk reader](https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/settings/unixSettings.py#L18-L93).
- **P8:** [Pinned SystemConf cache and merge saver](https://github.com/batocera-linux/batocera-emulationstation/blob/2c29a330e487210a7d51ad2650bb7b280ea44c86/es-core/src/SystemConf.cpp).
- **N1:** [Newer HTTP server, including `/input`](https://github.com/batocera-linux/batocera-emulationstation/blob/703116c6aefb61c68f1a5ea1e725ea8bb4d6ba52/es-app/src/services/HttpServerThread.cpp).
- **L1:** [Existing launcher and precedence research](launcher-configuration-options.md#what-wins-when-settings-disagree), backed by pinned `Emulator.py` and `unixSettings.py`.
- **L2:** [Existing emulator probe](../../../../../src/batocera_gow/runtime/emulator_probe.py), renderer preparation, generated-selection and active-backend checks.
