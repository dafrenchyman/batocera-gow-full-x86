# Research: emulator and test-content catalog

Historical planning research. The original decision-impact requirements below predate the accepted [observed shortcut-exit and missing-media contract](../explore.md#open-questions), which supersedes mandatory guest-gamepad/all-shortcut proof and all-six-qualified-fixture gating. Preserve the candidate/licensing findings; [Wolf delivery](../../../../completed/specs/wolf-integration/completion.md) and [modernization delivery](../../../../completed/specs/repository-modernization/completion.md) own executed, image-bound outcomes.

## Question

What systems, emulator backends and cores does the selected full-x86 Batocera image advertise, and what openly licensed or otherwise explicitly redistributable content could exercise them? Distinguish a fixture candidate from a verified native Wolf test, and distinguish missing legal prerequisites from emulator failures.

## Context

Owner: [repository maturation exploration](../explore.md#available-multi-backend-test-content). The user accepted redistributable test content, requested RetroArch cases for SNES, Genesis/Mega Drive and Atari plus xemu, Xenia, RPCS3 and DuckStation, then expanded research to every supported emulator. The selected scope is the existing pinned full-x86 43.1 image, not every Batocera architecture or release. No emulator/source/config changes or test execution are authorized by this planning.

## Method

Statically inspected the retained stock-root tar with Python tarfile after the generic archive reader's memory limit prevented opening this large archive. Parsed the original /usr/share/emulationstation/es_systems.cfg using ElementTree, retained its original-byte SHA-256, and saved every system, extension and emulator/core entry in [the packaged inventory](artifacts/packaged-system-inventory.json). The retained assembly manifest identifies upstream revision 155c2d8d304cbb53db52e9479dcf683392821d5c. The inventory was partitioned into disjoint research families covering every advertised entry.

Read-only research used official emulator/framework documentation, project source and file-level licenses, release listings and source-build recipes. No ROM/firmware binary download, installation, cross-compilation, emulator launch, SSH operation, screenshot capture or test ran. Published binaries and source candidates below are upstream evidence, not locally qualified fixtures.

## Evidence

### Complete advertised catalog

| Dimension                         | Count |
| --------------------------------- | ----: |
| System/category entries           |   253 |
| Distinct emulator identifiers     |    98 |
| Distinct emulator/core pairs      |   233 |
| System/emulator/core combinations |   477 |

These are declarations in the packaged ES catalog, not verified installed executables or successful launches. Three categories have no emulator declaration: imageviewer, library and recordings. Other entries include ports, package managers and streaming tools that do not naturally take a console ROM. Do not present 253 as the number of independent emulators or count one RetroArch launch as coverage of every core.

Original catalog SHA-256: 401638d6cbc26e574456f36a4b59007b823b576b35422f519640be9bfd3efc23. The inventory preserves the source path, release/revision and exact extensions/emulator/core alternatives. Grouping is for research ownership only, not an accepted test-tier design.

### Full candidate ledger

The [readable fixture index](artifacts/fixture-candidate-index.md) covers all 253 advertised entries. The [structured catalog](artifacts/fixture-candidate-catalog.json) owns each entry's advertised extensions/backend/core alternatives, candidate or gap, license scope, prerequisites, primary sources and caveats. Exact set equality against the packaged inventory and unique system IDs were checked; every row has a recognized disposition and source URLs.

This is complete inventory coverage for initial discovery, not individual qualification of all 477 system/backend/core combinations. Dispositions identify the leading research constraint, not every applicable constraint. A redistribution lead can still need a source build, asset review or external firmware; a source-only lead can still have unresolved rights. Every row explicitly remains unapproved for redistribution and unverified by execution during this research.

Useful broader leads include cc65 platform samples, Mooneye and mGBA tests, Amiga Test Kit, EmuTOS, C-BIOS, FreeDOS examples, Freedoom, OpenQuartz, EasyRPG TestGame, MrBoom, and framework-authored procedural demos. Modern-console SDK samples often require cross-toolchains and target-specific packaging. Many arcade/computer entries require separately provisioned ROMs, operating systems or commercial data; replacement firmware must be qualified for the exact backend and machine model. DICE's documented ROM-free Pong path and media/tool categories do not require a conventional game ROM.

### Priority fixture findings

| System / backend                                                          | Candidate                                                                                                                       | Availability and qualification                                                                                                                                                                                                                                                    |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NES / RetroArch FCEUmm, with other advertised cores separately selectable | [240p-test-mini v0.23](https://github.com/pinobatch/240p-test-mini/releases/tag/v0.23), 240pee.nes                              | Ready release; GPL-2.0-or-later with explicit replaced-asset provenance. Controller indicators and visual patterns. Preserve the existing FCEUmm regression rather than replacing it with a different core.                                                                       |
| SNES / Snes9x                                                             | [gilyon/snes-tests](https://github.com/gilyon/snes-tests), cputest-basic.sfc                                                    | MIT repository, ready v1.4 release. Rendered CPU success/failure; not a controller visualizer. Included font is covered by the repository grant, without an independent origin audit.                                                                                             |
| Genesis/Mega Drive / Genesis Plus GX                                      | [SGDK v2.11 joy-test](https://github.com/Stephane-D/SGDK/tree/v2.11/sample/joy-test)                                            | Ready ROM committed upstream. MIT software/library terms, text/button indicators. Toolchain terms and binary/source correspondence are separate concerns. Ordinary cartridge case does not require Sega CD firmware.                                                              |
| Atari 2600 / Stella                                                       | [a26-kickstart](https://github.com/owlcreekworkshop/a26-kickstart) color-bar program                                            | MIT procedural rendering source. Requires template generation/assembly; no ready ROM established. No controller polling, so it cannot prove guest input delivery.                                                                                                                 |
| PS1 / DuckStation                                                         | [ps1-bare-metal](https://github.com/spicyjpeg/ps1-bare-metal) graphics/controller examples                                      | Source-build candidates with repository/per-file notices. External BIOS required. [OpenBIOS](https://pcsx-redux.consoledev.net/openbios/) is an upstream-licensed alternative recognized by current DuckStation source, not verified with this packaged version.                  |
| Xbox / xemu                                                               | [nxdk_pgraph_tests](https://github.com/abaire/nxdk_pgraph_tests)                                                                | MIT source and a published XISO lead. Complete release asset/dependency qualification remains open. MCPX and unsigned-capable BIOS are separate operator prerequisites; a free game does not supply them.                                                                         |
| Xbox 360 / Xenia                                                          | [hwtests](https://github.com/xenia-project/hwtests), [xsdk](https://github.com/xenosworks/xsdk) research leads                  | No qualified visual/input fixture established. hwtests is CPU/log oriented with build/format gaps. xsdk's procedural cube has useful licensing evidence but upstream documents unsupported presentation in its checked Xenia version. Do not promote either to visual acceptance. |
| PS3 / RPCS3                                                               | [PSL1GHT videoTest](https://github.com/ps3dev/PSL1GHT/tree/f649a08fd536a9e27c08c7db2d93a2d7ee4c3bbe/samples/graphics/videoTest) | Source-only animated gradient. MIT root plus GPLv3 helper files and substantial toolchain/port-library obligations. Operator-provisioned Sony firmware remains necessary. Start exits the guest, which alone does not prove host Guide+Start handling.                            |

Every row is a research candidate or gap, not a passing scenario. Game Boy's [dmg-acid2](https://github.com/mattcurrie/dmg-acid2) is an additional useful MIT visual-oracle candidate with ready release/reference images, but does not replace any explicit system request.

### Batocera's licenses versus test-content licenses

The user asked whether this project must follow Batocera's licensing. Yes for the Batocera components redistributed, but there is no single license covering the distribution and every possible test game. Batocera's [official licensing policy](https://www.wiki.batocera.org/license) identifies a mixture of GPL, LGPL, BSD, MIT and non-commercial terms. Code specifically written by its team is generally LGPL v3 unless upstream terms apply. Preserve applicable notices and meet the redistribution/source obligations of the actual components; leaving stock files unchanged does not remove those obligations.

Additional test software and its artwork retain their own terms. Emulator licensing does not grant game or firmware redistribution rights. Original code written for this repository is not automatically LGPL v3 merely because it runs alongside Batocera; any reused upstream code still carries its applicable terms. No repository-wide license was selected by this clarification, and no root LICENSE, COPYING or NOTICE file was found.

Batocera's [games and BIOS guidance](https://wiki.batocera.org/add_games_bios) explicitly describes bundled freely distributable games as useful tests and requires users to supply copyrighted BIOS files separately. The retained stock manifest already lists NES 2048, Genesis Old Towers, GBA SpaceTwins and SNES DonkeyKongClassic, among other content. Reusing a suitable stock game may avoid acquiring another fixture, but inclusion is not proof that the game is open source, that all assets share the engine's license, or that the game provides the observable input checks needed. These existing payloads have not been run or separately license-qualified by this research.

### Firmware and asset boundaries

- [xemu required files](https://xemu.app/docs/required-files/) separately require MCPX, compatible unsigned-capable BIOS and an HDD image. [xemu-dashboard](https://github.com/xemu-project/xemu-dashboard) offers an open dashboard/HDD route; that does not remove the MCPX/BIOS boundary. EEPROM can be generated rather than requiring a console dump.
- [Xenia quickstart](https://github.com/xenia-project/xenia/wiki/Quickstart) says it does not require Xbox 360 system files. Its fixture gap is not automatically a firmware gap. The repository's actual Xenia branch/Wine/native path must be recorded rather than inferred from current upstream Linux releases.
- [RPCS3 quickstart](https://rpcs3.net/quickstart) requires PS3 system software. [Sony's system-software agreement](https://www.playstation.com/en-us/legal/ps3-system-software-license-agreement/) is not a redistribution grant for a complete PUP or installed firmware tree. Keep this an explicit operator-provisioned prerequisite, not a repository/image asset.
- An open-source emulator or engine does not license its games. A commercial-data port can need external data even when the engine itself is GPL/MIT. Free downloads, shareware, community galleries and screenshots are not substitutes for explicit distribution terms.

### Stock launch and shortcut contracts

Static inspection of the retained configgen generators establishes different contracts:

| Backend     | Stock menu action | Stock exit action   |
| ----------- | ----------------- | ------------------- |
| DuckStation | F7                | Alt+F4              |
| RPCS3       | Shift+F10         | /usr/bin/rpcs3-exit |
| xemu        | None declared     | Alt+F4              |
| Xenia       | None declared     | Alt+F4              |

These come from getHotkeysContext in the archived configgen/generators/<backend>/<backend>Generator.py files. Test the applicable stock context rather than imposing a universal menu on backends without one. These are action definitions, not a new mapping or proof that a physical client chord works.

The catalog also constrains launch formats. For example, Xbox advertises ISO/squashfs rather than raw XBE, PS3 advertises .ps3/.psn/.iso/.squashfs rather than arbitrary standalone ELF, and PS1 advertises media formats rather than every SDK executable. A source build's output must be integrated through the ordinary stock launch path; launching a sample directly around configgen is insufficient acceptance.

## Findings

Useful open classic-system fixtures exist, including separate visual and controller cases. Modern/arcade/engine entries vary considerably. Some require a source toolchain, some require external firmware or commercial data, some are not ROM targets, and some have no qualified candidate established. The complete advertised catalog is the discovery boundary, not evidence that every entry can have a self-contained legal test today.

The later executable matrix must identify system, emulator, core, fixture/source/hash, prerequisite profile and expected observable behavior. Distinguish guest rendering, guest button response, stock shortcut handling, pinned process exit and frontend return. A static screenshot, boot message, CPU-only test or Start-driven guest quit cannot stand in for all those checks.

## Dead ends and failures

- Do not blanket-approve the original multi-platform 240p Test Suite's artwork. The NES mini port specifically documents replacing graphics to keep its software free; other ports need their own terms checked.
- PSn00bSDK-linked PS1 test binaries have an upstream-documented provenance concern around Sony-derived routines. Prefer independent bare-metal examples for the initial fixture investigation; do not treat a test repository's root license as clearance of its linked SDK.
- The inspected xsdk presentation path fails in upstream's checked Xenia configuration. This resolves that candidate negatively for that configuration; no local rerun or optimistic screenshot claim is justified.
- RPCS3 autotest repositories contain useful TTY tests and expected images, but not every ready graphics binary has complete corresponding source/build evidence. A repository-wide GPL label is not blanket qualification.
- A declared ES entry is not installed/working-support evidence. A normal base-console ROM does not prove CD/add-on, linked-player, MSU, special mapper or arcade-board variants.
- MAME's [official free-ROM page](https://www.mamedev.org/roms/) explicitly restricts its distribution permission to that site. Download availability does not authorize mirroring those ROMs or bundling them in this repository, image or test package.

## Reusable artifacts

[The packaged inventory](artifacts/packaged-system-inventory.json) supplies exact system/extensions/backend/core data and original catalog provenance. [The candidate catalog](artifacts/fixture-candidate-catalog.json) preserves all research dispositions and evidence; [its index](artifacts/fixture-candidate-index.md) provides a readable view. Existing native probe/screenshot mechanisms remain reusable; replacing their hardcoded private ROM/profile assumptions is future implementation, not work performed by this research.

## Decision impact

Keep the full catalog as a discoverable fixture/prerequisite ledger. Do not require all entries to have equivalent ROM assets or present unresolved entries as passing tests. Retain the requested classic-system/core and standalone-backend coverage when selecting executable tiers. Cross-building samples and provisioning firmware require explicit implementation/execution contracts; this research grants neither.

The user accepted operator-supplied BIOS/firmware outside source, images and distributed fixture bundles, without automatic proprietary firmware acquisition. Missing prerequisites cannot produce a passing verification result. See [the owning exploration decision](../explore.md#available-multi-backend-test-content). This permits that prerequisite model in the test design, not live-host access or execution; case-specific prerequisites and observable acceptance remain open.

The user accepted two run levels and six required regression cases: NES/FCEUmm, SNES/Snes9x, Mega Drive/Genesis Plus GX, Atari 2600/Stella, DuckStation and original Xbox/xemu. All six must have qualified fixtures and passing native tests before broad refactoring or source moves. RPCS3 and Xbox 360/Xenia remain named, nonblocking expanded targets whose gaps must be reported without claiming passing coverage. Accepting this matrix does not qualify the candidate ROMs or establish their input or shortcut behavior.

Required cases must demonstrate observable guest gamepad response and the effects of all applicable configured stock Guide shortcuts through the native gamepad/project-input/stock-hotkeygen path. The user emphasized protecting the input handling added to make Guide hotkeys work. Direct command execution and receiver-side event logs are insufficient substitutes for that route and its consumer-visible result. The SNES CPU-test and Atari color-bar leads lack guest-input proof, so they cannot alone meet the accepted contract.

Manual Moonlight/controller checks are optional, not required for acceptance. The native suite still requires guest-input and Guide-shortcut proof. Its server-side injection and screenshots do not verify real-controller forwarding, client-decoded video or heard audio; reports must preserve that limit without treating an optional unperformed check as a pass.

## Follow-up question

Which reproducible, rights-qualified input-sensitive fixtures fulfill the six required backend/core contracts through stock launch formats? The SNES and Atari input gaps, PS1 source build and xemu resource qualification remain concrete work. See the owning exploration for target-concurrency and other planning decisions before any experiment; no build, download or remote execution is authorized by this research.
