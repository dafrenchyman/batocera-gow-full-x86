# Research: input-sensitive standalone emulator fixtures

## Question

Which small, rights-supported fixtures can prove guest button delivery for the required PlayStation/DuckStation and original Xbox/xemu cases through ordinary stock launch formats? A useful answer needs identifiable source, consumed dependencies and assets, a plausible build-to-media route, and a rendered press/release observation that an automatic assertion can distinguish from no input. An upstream sample is not an execution-qualified fixture.

## Context

Owner: [Wolf integration exploration](../explore.md) and [Draft specification](../spec.md). Inputs: [earlier fixture research](../../../../completed/epics/repository-maturation/research/emulator-fixtures.md), its [candidate catalog](../../../../completed/epics/repository-maturation/research/artifacts/fixture-candidate-catalog.json) and [stock inventory](../../../../completed/epics/repository-maturation/research/artifacts/packaged-system-inventory.json).

All six required cases remain required. This report covers only `psx/duckstation` and `xbox/xemu`. RPCS3 and Xbox 360/Xenia remain named nonblocking expanded targets. No alternative backend, runtime patch, overlay, personal controller profile or direct SDK executable launch is recommended.

## Method and limits

Read the saved exploration, relevant specification requirements, earlier research and the two catalog entries. Inspected first-party repository trees, source, build files, license texts, release APIs and official emulator documentation using text/API reads. Research date: 2026-10-28. Source revisions below are immutable; wiki pages, release API queries and official web documentation are observations on that date, not immutable snapshots.

No Git command, clone, installation, source build, binary or firmware download, SSH operation, emulator launch, test, formatter or remote experiment ran. No image, digest, pixel region, tolerance, observation deadline or passing result was generated. Compatibility with the packaged emulator versions, firmware, controller mapping, guest rendering and Wolf runtime remains unexecuted. The earlier catalog and research snapshots are unchanged.

The only saved artifact from this assignment is this report. Commands below describe a future authorized source-build workflow. They were not executed and are not a ready local command interface.

## Findings and selected leads

| Required backend   | Conservative selected lead                                                                                                                            | What this research resolves                                                                                                                                                                            | What it does not resolve                                                                                                                                |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PS1/DuckStation    | Unmodified `ps1-bare-metal` example 11 at `2af848a02dbdcc606b915b3b90698f9bbe9e74f3`, packaged as a newly authored data-only BIN/CUE with `mkpsxiso`  | Explicit authored-assets and MIT/ISC evidence; complete example target and font dependency; clear `cross` appearing while held and disappearing on release; a supported stock media construction route | Actual compiler pin, artifact/digests, successful license-free disc boot on the pinned backend/BIOS, screen assertions and all configured Guide effects |
| Original Xbox/xemu | `XboxDev/nxdk` `samples/sdl_gamecontroller` at `8d8438186c5dcf1187672b686a91c4603be9e111`, conditional on resolving its sample-specific license grant | Much smaller input oracle than the graphics suite; unchanged upstream Makefile already creates XBE and XISO; rendered `A:0` to `A:1` to `A:0`; concrete submodule/build and firmware boundaries        | Explicit license assignment for the sample itself, complete per-file linked-component clearance, qualified artifact/digests and native behavior         |

PS1 has an affirmative legal source lead, not an unavailable fixture. Xbox has a strong technical source lead and substantial permissive dependency evidence, but this inspection did not establish permission to redistribute that particular sample. Do not report either as a qualified binary. Do not turn the Xbox license gap into a claim that original Xbox input-sensitive homebrew cannot exist.

## Evidence: PlayStation/DuckStation

### Exact source and consumed inputs

The inspected [PS1 revision][ps1-tree] matches the earlier catalog pin. Its [README][ps1-readme] describes no external console SDK, an unmodified MIPS GCC toolchain, CMake and Python. It expressly says all code and assets are authored by hand and that everything in the repository, including vendored printf, is MIT or ISC. This is stronger asset evidence than a root license alone, although it is not an independent provenance audit.

The [example source][ps1-controller] contains the ISC-style permission notice and implements controller polling directly through SIO0/PSCTP. The [root CMake target][ps1-cmake] names:

- `src/11_controllers/main.c`;
- `src/common/font.c` and `src/common/gpu.c`, with their `src/common` and `src/ps1` headers;
- the shared `c` object target containing `src/libc/clz.s`, `crt0.c`, `cxxsupport.cpp`, `malloc.c`, `misc.c`, `setjmp.s`, `string.c`, `string.s` and `src/vendor/printf.c`;
- only `assets/font.png` converted into `build/assets/fontTexture.dat` and `fontPalette.dat` and embedded in `example11_controllers`.

The target does not consume `assets/test.wav`, `mipmap.png`, `test16bpp.png` or `test4bpp.png`. The root build describes those other examples, but a targeted example-11 build need not build or distribute them. `psxavenc` is optional for audio examples, not a dependency of this controller fixture. Neither PSn00bSDK nor Sony PsyQ libraries are linked by this route. Do not import their libraries merely because a development machine has them installed.

[Setup code][ps1-setup] uses `-nostdlib`, a repository linker script and `-lgcc`, with section garbage collection. The repository's own libc and printf are real runtime inputs, not a system newlib dependency. The exact object members retained by a future compiler still need an artifact/link record. In particular, `-lgcc` is an actual dependency that must not disappear from the rights inventory because the example is described as bare metal.

### Build and packaging route

The [README][ps1-readme], [CMake helpers][ps1-tools] and [Python requirements][ps1-requirements] establish this planned sequence:

1. Obtain the exact source revision and a recorded `mipsel-none-elf` GCC/binutils toolchain. Record compiler versions and tool binary identities. README requires CMake 3.25+, Python 3.10+ and Ninja. Its Python environment installs `numpy >= 1.19.4` and `Pillow >= 8.2.0`; those are open lower bounds, not a reproducible lock.
2. Prepare the upstream virtual environment as documented, then configure with `cmake --preset release`. If necessary, supply the documented `-DTOOLCHAIN_PATH` pointing at that compiler's `bin` directory.
3. Build only the controller target with `cmake --build build --target example11_controllers`. The target selection is an inference from the inspected CMake target, rather than a command quoted verbatim from the README. Upstream's general command builds every example.
4. The CMake helper converts the ELF to `build/example11_controllers.psexe` with `tools/convertExecutable.py`. That converter uses the Python standard library and explicitly requires no external dependencies. Image conversion consumes NumPy/Pillow. A `.psexe` is not an advertised PS1 media suffix in the pinned stock catalog, so it is an intermediate artifact only.
5. Author a minimal disc with a root executable named `PSX.EXE` containing that `.psexe` byte stream. The upstream README says this name should boot on modified non-Japanese hardware, not that every BIOS accepts every such disc. The maintained [psx-spx executable-format reference][ps1-boot-format] independently documents `PSX.EXE` as the default boot filename when `SYSTEM.CNF` is absent. This avoids copying a boot configuration or license data out of a commercial disc. Use `mkpsxiso` revision `a6b11ea86e67c189137ac50a4066044b3fdb0525`, version 2.30, with one data track and `PLAYSTATION` system/application identifiers. Its [example XML][mk-example] documents those identifiers, data files, output BIN/CUE names and optional license element. A new minimal XML would contain only the data-track structure, identifiers and the `PSX.EXE` file. It must omit the example's Sony `licensea.dat`, media files and extra tracks. If an explicit boot descriptor is needed, the same format reference documents newly authored ASCII `SYSTEM.CNF` with `BOOT = cdrom:\PSX.EXE;1` and CRLF line endings; do not copy a retail descriptor. Neither proposed layout is execution-qualified here.
6. Run the documented `mkpsxiso <project.xml>` interface to produce the declared BIN/CUE pair. Supply the CUE, with its matching BIN, through normal EmulationStation/emulatorlauncher selection of system `psx`, standalone `duckstation`. Do not invoke DuckStation directly with the loose executable.

The [mkpsxiso README][mk-readme] explicitly supports BIN/CUE and ISO output. Its changelog records a fix for invalid sectors when no license file is specified. Its XML calls the license file optional and says Sony license data is excluded for legal reasons. This establishes a practical license-free authoring route, not proof that the pinned DuckStation/BIOS combination will boot that exact generated disc. The PS1 sample README itself says disc authoring is not covered there. This report supplies the missing tool route without claiming upstream ships a complete disc project.

A future build should also record XML, all input/output hashes and deterministic timestamp choices. `mkpsxiso` documents file timestamp attributes, but no byte-reproducible build has been demonstrated here. Failure to boot an unlicensed data disc is a factual qualification issue. It is not permission to copy a Sony license sector, use a retail image as a template, rename `.psexe` to `.iso`, change stock configgen or bypass it.

### Rights and distribution boundaries

| Material                                            | Evidence and obligations                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Example, common/runtime code and headers            | [Root MIT grant][ps1-license] plus actual ISC-style file notices. Preserve the author copyright, permission and disclaimer text with source and distributed substantial compiled portions. The README's MIT/ISC statement covers the repository as a whole, but keep the actual notices rather than relabel every file MIT.                                                                                                                                         |
| `assets/font.png` and its converted texture/palette | The README's explicit all-assets authorship and licensing statement supplies affirmative coverage. Preserve the repository notice. No external PS1 BIOS font, Sony texture or 240p-suite artwork is needed. The generated font bytes retain the source asset's attribution requirements.                                                                                                                                                                            |
| Vendored printf                                     | `src/vendor/LICENSE.printf` is [Marco Paland's MIT grant][ps1-printf]. Include this notice separately from spicyjpeg's.                                                                                                                                                                                                                                                                                                                                             |
| `libgcc`                                            | Setup explicitly links it. The [GCC Runtime Library Exception 3.1][gcc-exception] allows eligible independent target-code combinations under the independent module's terms when the actual runtime files carry the exception. Record the chosen compiler's actual runtime notices. Do not assume any unrelated prebuilt toolchain is covered merely because it is called GCC. Redistributing the compiler/binutils themselves has separate GPL/source obligations. |
| NumPy, Pillow, Python, CMake and Ninja              | Host build tools, not guest libraries or disc assets. Record the versions used. This proposed fixture bundle need not redistribute those tools, their Python environment or the compiler. If it does, their own distribution notices and dependencies need separate clearance; the console source's MIT grant does not cover them.                                                                                                                                  |
| `mkpsxiso`                                          | [GPLv2 license text][mk-license] and [build configuration][mk-cmake]. Using the authoring executable does not make its independently authored input files GPL. Redistributing the tool itself requires GPL compliance and corresponding source, plus its actual dependencies' notices. Keep host tools outside the fixture/media bundle by default.                                                                                                                 |

The `mkpsxiso` build consumes tinyxml2 at `3dcad8e3c38e7091ae3771bf63020027f91715ce`, ghc/filesystem at `0e72911ba0f37f3eb883b181b855a5f4eb046ca1`, miniaudio at `9634bedb5b5a2ca38c1ee7108a9358a4e233f14d`, and ThreadPool at `251db61ff3e3c7b16436c9936c53e6f68ff07720`. The [pinned tree][mk-tree] records these gitlinks. Their inspected grants are respectively [zlib][mk-tiny-license], [MIT][mk-ghc-license], [Unlicense or MIT-0][mk-audio-license], and [zlib-style][mk-thread-license]. They are authoring-tool dependencies, not new PS1 runtime dependencies. CMake attaches libFLAC to `dumpsxiso`, not `mkpsxiso`; building only `mkpsxiso` with the documented `MKPSXISO_NO_LIBFLAC` configuration avoids claiming an unused FLAC encoder is necessary for the data-only route. No audio or model asset is consumed by this fixture.

The [PS1 releases API][ps1-releases] returned an empty release list. This establishes no ready GitHub Release artifact in the inspected project, not absence of usable source or of artifacts everywhere. Build the source as a planned workflow; do not replace an unbuilt artifact with an availability failure or claim binary/source correspondence without producing it.

### Rendered input observation and Start

Source-level observation from `printControllerInfo` and the main loop:

- At 320 by 240 guest resolution, the program polls both controller ports every frame, prints `Port 1:` and `Port 2:`, a controller type, `Buttons pressed:` and hexadecimal response bytes. A disconnected controller instead prints `No controller connected`.
- Controller response bytes 2 and 3 are an active-low button bitfield. The program inverts them and renders the names of the pressed bits. Bit 14 is `cross`; bit 3 is `start`.
- With no button held, the connected port's button list omits `cross`. Holding the suite pad's mapped Cross button adds `cross` in that guest port's list. Releasing it removes `cross`. The relevant response bits also return to their released values.

A proposed automatic observation is therefore a connected-controller baseline, the word `cross` appearing in that same port's button list while held, then disappearing after release, with an unrelated button label remaining absent. A no-injection control should remain in the released state. That distinguishes guest input consumption from static boot text, an event receiver, an emulator window or generic pixel motion. A future assertion may recognize glyphs or use qualified source-derived templates within the guest region; the actual scaling, regions, tolerances and timing remain native qualification outputs. No executable predicate is supplied or claimed here.

Plain Start only adds `start` to the printed list. The inspected infinite loop has no Start-exit branch. That makes this candidate preferable to a game whose own Start handler quits. Still run plain Start separately and prove the later Guide+Start effect against the pinned emulator process and actual frontend return. Absence of a guest-exit branch is source evidence, not a passing host-shortcut test.

### BIOS and stock launch boundaries

The pinned [DuckStation generator][stock-duckstation] passes the selected media path to `duckstation-qt -batch -nogui -- <rom>` when available, otherwise `duckstation-nogui -batch -fullscreen -- <rom>`. Those are observations about stock generation, not direct test commands to bypass emulatorlauncher. The catalog advertises `.cue` and `.iso`, among other formats, but not `.psexe`.

Operator-supplied PS1 BIOS remains external to source, images and media bundles. Do not use the sample's permissive license to infer firmware rights. Current upstream OpenBIOS recognition is already recorded as a lead in the baseline; this investigation did not qualify OpenBIOS against the packaged backend or this disc. BIOS identity, normal stock settings, media boot and dynarec/timing behavior must be recorded together. The sample README's development recommendation to use an interpreter does not authorize changing the accepted stock test backend/configuration to make a failing sample pass.

## Evidence: original Xbox/xemu

### Selected technical lead and guest behavior

The nxdk [source tree][nxdk-tree] identifies `samples/sdl_gamecontroller/main.c` and `Makefile`. Unlike `nxdk_pgraph_tests`, this sample exists specifically to display controller state. Its [complete main program][nxdk-pad] initializes guest SDL gamecontroller support and PBKit, sets 640 by 480 video and redraws a text display every frame.

On a controller-added event, it opens the controller and selects it if none is selected. Start selects a controller by its instance ID. It displays axes, triggers, buttons, vendor and product values. Its button line is exactly `- A:%d B:%d X:%d Y:%d`, populated by `SDL_GameControllerGetButton`. Other lines show Back, Start, White, Black, D-pad and stick buttons. Triggers control rumble; do not use trigger injection for the minimal observation or claim rumble/audio verification.

The source-derived observation is concrete:

1. Obtain the `Testing Controller` screen and establish the chosen pad has released A, rendered as `A:0`.
2. Hold plain mapped A. The same screen must render `A:1`, while B/X/Y remain in their released states.
3. Release A. It must render `A:0` again. A no-input control must not visit `A:1`.

This does not depend on time-varying graphics, a texture, a commercial game or input logs. PBKit draws the text into guest-rendered output. Its [text implementation][nxdk-print] has a 16-row, 60-column text buffer; qualify the A row itself instead of assuming every printed field fits or hashing the whole frame. Recognizable labels and changing glyphs are a useful semantic assertion proposal, not an already qualified OCR/template system.

Plain Start changes the selected controller and its printed Start state. It does not leave the sample's infinite main loop. Cleanup is reached after initialization failures, not because Start is pressed. The text `Press start on a controller to test` is not proof a controller has delivered input. The suite must first reach the selected-controller screen, and any Start needed for selection must be separate from the host Guide+Start case.

### Exact source build and XBE-to-XISO route

The [sample Makefile][nxdk-pad-make] sets:

```make
XBE_TITLE = nxdk\ sample\ -\ SDL2_GameController
GEN_XISO = $(XBE_TITLE).iso
SRCS = $(CURDIR)/main.c
NXDK_DIR ?= $(CURDIR)/../..
NXDK_SDL = y
```

It includes nxdk's root Makefile unchanged. The [README][nxdk-readme] documents recursive source acquisition, `bin/activate`, then `make` in a sample directory. For a future authorized build, record the exact nxdk revision, recursively obtain its pinned gitlinks, activate that tree, and use `make -C samples/sdl_gamecontroller`. This command is a composition of the documented sample-build route and inspected directory, not a result from this research.

The [root Makefile][nxdk-make] gives the entire media chain:

- Clang/nxdk wrappers compile sources; `nxdk-link` uses lld to produce `main.exe`.
- `tools/cxbe/cxbe` converts it to the default `bin/default.xbe` and sets the title.
- With `GEN_XISO` set, `tools/extract-xiso/build/extract-xiso -c <OUTPUT_DIR> <XISO_FLAGS> <GEN_XISO>` packages the output directory. The sample's default output filename is `nxdk sample - SDL2_GameController.iso` in the sample directory.
- The XISO's root contains `default.xbe`. No separate texture, TrueType font, audio, test configuration or dashboard asset appears in the sample directory or its XISO dependency rule.

The [nxdk XISO wiki][nxdk-xiso] independently documents `GEN_XISO` and directory packaging. This is already an upstream Makefile route, not an invented raw-XBE launch allowance. The [xemu disc documentation][xemu-disc] requires XISO, normally named `.iso`, and explicitly distinguishes it from a conventional ISO filesystem image. A future package must record the XBE and XISO hashes and their exact source/tool inputs. Merely changing an XBE's suffix cannot produce this media.

Launch that XISO as system `xbox`, backend `xemu`, through the normal stock frontend/emulatorlauncher/configgen path. The pinned catalog advertises `.iso` and `.squashfs`; choose plain XISO `.iso` to avoid an unnecessary second packaging layer. The [stock xemu generator][stock-xemu] invokes xemu with its generated config path, and [xemuConfig.py][stock-xemu-config] sets `sys.files.dvd_path` to the selected media. The media construction fits this route without changing Batocera or bypassing configgen. Runtime compatibility remains untested.

The [nxdk releases API][nxdk-releases] also returned an empty list. The inspected [sample CI workflow][nxdk-ci] builds samples but does not publish a Release fixture. There is source and an upstream build/media recipe; this inspection did not establish a ready redistributable sample XISO.

### Sample license is a real unresolved input

The sample's `main.c` and `Makefile` have no SPDX identifier, copyright notice or license statement. The inspected full nxdk tree has `LICENSES/*.txt` templates and file-level grants, but no root blanket license, sample license file or REUSE assignment that covers this sample. The [MIT template][nxdk-mit] contains placeholder copyright-holder text. The [GitHub license endpoint][nxdk-license-api] returned 404. The README calls nxdk open source and names licenses for several components; it does not explicitly grant a license to every unmarked sample.

None of those observations establishes that the sample is proprietary. They do establish that calling it cleared MIT would exceed the evidence. Its [file history][nxdk-pad-history] identifies the initial sample contribution at `176de1b09f77d0a3056ad3bc00179fbc07da706e` and later hotplug/rumble change at `22cef0181545ba7c0fdc6ba1d9a24db6b1d22b1a`. Those are concrete upstream authorship leads for a permission clarification, not a grant inferred from contribution alone. Do not distribute the sample XISO until the applicable permission is established.

### Dependencies actually consumed by the unchanged sample route

The sample itself uses SDL, HAL/debug/video, WinAPI/Sleep and PBKit. The actual Makefiles pull in more build inputs than those calls suggest. [Base libraries][nxdk-libs], [SDL integration][nxdk-sdl-make] and the pinned [SDL port Makefile][nxdk-sdl-port] make the following archive targets prerequisites of `main.exe`. Their contents are compiled, and the archives are passed to the linker through the root target rule. That does not prove every object is retained in the final XBE. A future link map must distinguish compiled-only code from linked runtime code. Do not call the unchanged build a two-library-only program.

| Component at nxdk pin                                 | Exact revision or path                                                                    | Rights evidence and scope                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PDCLib                                                | `lib/pdclib`, `9d257524e20e3e1ac90163b37f07702053e36321`                                  | [CC0][nxdk-pdclib-license]. Preserve any per-file exceptions encountered in the consumed source; CC0 is not a grant over unrelated SDK files.                                                                                                                                                                                                                                                                                                              |
| SDL2 port and SDL2 test archive                       | `lib/sdl/SDL2`, `2554902f7bbf469449216ee25f88016421271cd8`                                | [zlib-style grant][nxdk-sdl-license]. This is guest SDL inside the fixture, distinct from host xemu's SDL mapping.                                                                                                                                                                                                                                                                                                                                         |
| SDL_ttf                                               | `lib/sdl/SDL_ttf`, `200901a8f55bcf7aa031157f53a575c942d2b7aa`                             | [zlib-style grant][nxdk-ttf-license]. Built by unchanged `NXDK_SDL=y` integration despite no TTF call in the sample. No `.ttf` asset is loaded or distributed by this candidate.                                                                                                                                                                                                                                                                           |
| FreeType 2.4.12 inside SDL_ttf                        | `external/freetype-2.4.12`, at the same SDL_ttf revision                                  | [FTL or GPLv2-or-later choice][nxdk-ft-license]. Prefer the [FTL grant][nxdk-ftl] for this permissive candidate and retain its documentation attribution if code is linked or redistributed. The Makefile compiles the listed raster/base/SFNT/TrueType/autofit files, not every optional FreeType driver.                                                                                                                                                 |
| SDL_image                                             | `lib/sdl/SDL2_image`, `ab2a9c602623193d61827ccd395302d92d90fc38`                          | [zlib-style grant][nxdk-image-license]. Also built by unchanged SDL integration, although this sample loads no images. A complete shipped SDK/library package needs its included loader notices, not just this root grant.                                                                                                                                                                                                                                 |
| zlib                                                  | `lib/zlib/zlib`, `51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf`                               | [zlib terms][nxdk-zlib-license]. Archive is a base-build dependency.                                                                                                                                                                                                                                                                                                                                                                                       |
| libpng                                                | `lib/libpng/libpng`, `a40189cf881e9f0db80511c382292a5604c3c3d1`                           | [PNG Reference Library license][nxdk-png-license]. Preserve its notice and source-change requirements if redistributed. Archive is a base-build dependency.                                                                                                                                                                                                                                                                                                |
| libjpeg-turbo                                         | `lib/libjpeg/libjpeg-turbo`, `166e34213e4f4e2363ce058a7bcc69fd03e38b76`                   | [IJG, BSD and zlib component terms][nxdk-jpeg-license]. The IJG acknowledgment matters if JPEG runtime code is included. Do not blanket-relabel this library MIT.                                                                                                                                                                                                                                                                                          |
| USB/OHCI                                              | `lib/usb/libusbohci`, `6a0c5fefbcd9db53f4a27ee10df99f93d5bce745`, plus nxdk Xbox/XID glue | [Apache-2.0 text][nxdk-usb-license] and [Nuvoton disclaimer][nxdk-usb-disclaimer]. Preserve relevant copyright, license, NOTICE and modification obligations for consumed files. This current tree uses the libusbohci submodule; the README's historical Linux USB description is not a substitute for examining the pinned inputs.                                                                                                                       |
| lwIP                                                  | `lib/net/lwip`, `77dcd25a72509eb83f72b033d219b1d40cd8eb95`                                | [BSD-style terms][nxdk-lwip-license]. Root Makefile includes network build rules. The fixture does not call networking; do not infer a required test server or enable guest networking.                                                                                                                                                                                                                                                                    |
| PBKit, HAL, WinAPI, nxdk and Xbox runtime/import glue | Files at nxdk revision `8d8438186c5dcf1187672b686a91c4603be9e111`                         | PBKit core and text code have explicit MIT notices; HAL/debug has MIT. README identifies OpenXDK and compiler-rt origins, with separate file notices. This is a mixed per-file inventory, not a completed license audit of all runtime members. [Xbox runtime Makefile][nxdk-runtime] and [kernel-import rule][nxdk-import] identify further compiled/import inputs. The latter generates an import library, not a bundled Microsoft BIOS or kernel image. |

Assets require separate attention even for this small sample:

- `lib/pbkit/pbkit_print.c` embeds `systemFont` under its MIT file notice. There is no external font/image file in the sample. Independent origin of that older bitmap array was not established here, so retain the notice and record the provenance limit rather than claim a separate authored-font audit.
- [HAL/debug][nxdk-debug] embeds `lib/hal/font_unscii_16.h` in its debug rendering path. The [font header][nxdk-unscii] explicitly credits the upstream Unscii URL and marks this subset public domain. Initialization-error rendering uses `debugPrint`; this dependency must not be omitted merely because successful controller output uses PBKit.
- The unchanged conversion step adds another actual asset. [CxBE `Logo.cpp`][nxdk-logo] contains `defaultXbeLogo` under a GPL-2.0-or-later file notice. [XBE construction][nxdk-xbe] copies those bytes into the XBE when no custom logo is provided, and the inspected root Makefile provides no logo argument. Thus this is not solely a GPL host executable: its bitmap bytes enter the distributed artifact. The source does not identify the decoded image or a separate origin/grant for that array. Do not assume it is an independently authored nxdk logo, a Microsoft asset, or cleared merely because the tool is open source. Record the embedded bitmap's actual provenance and applicable source/notices/license treatment before distributing this unchanged-build artifact. A custom-logo facility exists in CxBE, but the sample's standard Makefile does not expose it; this report does not silently replace assets or claim an alternative build passed.
- No external sample font, image, mesh texture or model is consumed by this sample. Do not audit or bundle the entire samples tree as though it were part of the fixture.

The `lib/libcxx` gitlink is not part of this C sample's default `NXDK_CXX` conditional branch. nxdk's own runtime still has C++ translation units; that is not equivalent to importing the separate libc++ distribution. Final binary membership remains a link-record question.

Host build tools also need accurate boundaries. The documented toolchain uses make, Clang, lld, LLVM utilities, CMake and related host prerequisites. [CxBE's source][nxdk-cxbe] is GPL-2.0-or-later. The pinned `tools/extract-xiso` revision is `b72e5b60d598ec6df80534cda19cdcd4361aa18c`; its [license][xiso-license] is a modified Berkeley license with an advertising acknowledgment clause, not merely an unspecified modern BSD license. If distributing these tools, preserve their terms and satisfy GPL corresponding-source obligations for CxBE. Processing independent inputs is distinct from incorporating tool-owned content: the default-logo copy described above is the latter and needs its own artifact-rights treatment. Do not conclude that all CxBE output is automatically GPL, or that this XBE is unaffected by the GPL-marked bitmap.

The root Makefile defines shader conversion rules and a `tools` aggregate, but the controller sample has no shader inputs or `SHADER_OBJS`. Its default dependency graph needs CxBE and extract-xiso, not the NVIDIA Cg compiler or shader compiler tools. Do not import the NVIDIA Cg redistribution agreement into this fixture's actual runtime requirements, or bundle the SDK/tool directory wholesale and then pretend those binary tools were excluded. Source acquisition can contain unused files; redistribution of that whole SDK would be a separate, larger rights review.

### Firmware, disk and stock configuration

The official [required-files page][xemu-files] requires MCPX, a compatible BIOS and an HDD image. It says an unmodified retail BIOS cannot boot games in xemu because of unimplemented DRM functions; a debug or modified unsigned-capable BIOS is required. A source-built nxdk program does not remove that requirement. The official HDD route can use a preformatted image containing an unsigned open dashboard rather than the Microsoft dashboard. This investigation did not acquire or qualify any firmware/HDD image or dashboard release.

The pinned [stock configuration][stock-xemu-config] has concrete paths for the Xbox case:

- `/userdata/bios/Complex_4627.bin` for flash ROM;
- `/userdata/bios/mcpx_1.0.bin` for MCPX;
- `/userdata/saves/xbox/xbox_hdd.qcow2` for HDD state;
- `/userdata/saves/xbox/xemu_eeprom.bin` for EEPROM state;
- `dvd_path` set to the selected XISO.

The [generator][stock-xemu] copies `/usr/share/xemu/data/xbox_hdd.qcow2` into the save path if it does not exist, passes generated SDL mappings and selected controller GUIDs through the existing route, and uses an emulator-specific context declaring only Alt+F4 exit. That supplies a stock HDD-seeding lead. It does not establish the packaged HDD bytes' rights or compatibility and does not justify changing stock paths. A future disposable home can hold declared externally supplied/generated writable state without editing configgen; original operator firmware remains read-only and outside code, image and fixture bundles. Record the actual packaged seed's provenance or a rights-qualified operator HDD before qualification. Generated EEPROM/HDD writes belong only to the disposable home.

A filename or published BIOS checksum is not permission to distribute firmware. Keep the selected BIOS/MCPX profile and HDD route separate from the sample/XISO rights record. The [disc documentation][xemu-disc] also warns that media patching and BIOS behavior affect compatibility. Do not infer that any XBE-to-XISO conversion automatically boots on every unsigned-capable BIOS.

### Actual-stock HDD follow-up, 2026-10-30

This bounded [ticket06](../tickets/06-xemu-regression.md) finding concerns the packaged HDD prerequisite only. The Ready spec supersedes this report's historical guest-input/all-shortcut requirements. No sample-rights investigation or native qualification was reopened.

Method: queried the retained `output/gow-full-x86/stock-manifest.json`, read the pinned public packaging/configgen sources and first-party HDD documentation, release metadata, source and licenses. Because the 15.6 GB stock archive exceeds the reader limit, a read-only Python stdlib `tarfile` pass read only four named regular public members into memory, each bounded by its manifest size. No extraction or persisted binary/source copy occurred. The archive was `output/gow-full-x86/assembly-b48a2301452746b1ee77e951181bd7becde4fb975ed5d7988445fb3ee9e4f3d8/stock-root.tar`. No binary/firmware/media acquisition, private file read, build, test, hook, SSH or emulator operation ran. [Ticket03](../tickets/03-nes-guide-start-regression.md) already records stock preservation in immutable image `sha256:9d4980b16df126a71a1d2522f194528c3daaafc00e44d754216671dfaadb9368`, source `worktree-sha256:b63501d5a6fa6870d1b7be94e597ac25bb9d3788a65b39d0f347f0fe6260b7b5`; this research did not launch or reverify it.

The actual `/usr/share/xemu/data/xbox_hdd.qcow2` is 4,521,984 bytes, SHA-256 `eb35d069715dfc0d37cfac086a0b73a89a02e8f12519cd8eda82ad479d1a4eed`, matching the manifest. Its QCOW2 v3 header declares an 8 GiB virtual disk, no backing file and no encryption. Bounded in-memory QCOW2/FATX reads found formatted X/Y/Z/C/E partitions with 16 KiB filesystem clusters, empty X/Y/Z roots, `C:/xboxdash.xbe`, and empty `E:/TDATA` and `E:/UDATA`. The dashboard file is 172,032 bytes, SHA-256 `338e6e203d9f1db5f2c1d976b8969af42049c32e1a65ac0347fbc6efcf5bd7c6`, with an `XBEH` header and the literal `Please insert an Xbox disc...`. Directory layout and file-chain interpretation followed the first-party [FATX structures][hdd-fatx-structures], [partition map][hdd-fatx-partitions] and [allocation rules][hdd-fatx-allocation]. These are static content observations, not a forensic claim about every unused sector. The seed is preformatted and contains executable dashboard code; it is not just blank filesystem data.

The Batocera43.1 [recipe at revision `155c2d8d304cbb53db52e9479dcf683392821d5c`][stock-xemu-recipe] pins xemu `v0.8.134` and separately obtains `mborgerson/xemu-hdd-image/releases/download/1.0/xbox_hdd.qcow2.zip`, then unzips its `xbox_hdd.qcow2` member into `/usr/share/xemu/data`. That old repository URL redirects to `xemu-project/xemu-hdd-image`. Its [1.0 release API][hdd-release] identifies release `32946176`, asset `27398865`, ZIP size 68,552 bytes, uploaded 2020-10-22, with `digest: null`, an empty release body and `immutable: false`. The [1.0 tag][hdd-tag] resolves to `b2eeeae652295d60c5cefff31ef4a602299b5dbd`. Its [README][hdd-readme] describes XboxHDM1.9/QEMU formatting, copying a dummy dashboard to C and creating empty TDATA/UDATA directories. The [dummy dashboard source][hdd-dummy-source] prints the observed message; its [Makefile][hdd-dummy-makefile] uses an unpinned adjacent nxdk checkout. Recipe, directory contents and that distinctive message support the intended upstream origin. They do not prove that the release ZIP's member equals the stock fingerprint or that this source revision reproduces it. No retained ZIP was found under `output/gow-full-x86/`, and no new one was acquired.

Legal evidence is affirmative but has limits. The release-associated README explicitly calls the published image "Copyright-Free Xbox HDD Image", says it is "free of any copyrighted content", offers its prebuilt download and documents use with xemu. This is an upstream representation about the intended HDD artifact, not merely Batocera inclusion or a filename. It does not support inventing a distribution prohibition. However, the complete [release source tree][hdd-tree] has no license file, the small dummy source/Makefile has no separate grant, and the recipe does not pin the nxdk/compiler inputs or document the embedded binary's complete notices. The license API also returned404; that failed lookup is not evidence of a prohibition. The "copyright-free" wording must be recorded alongside the actual executable contents, not paraphrased as an empty disk or as independently established public-domain status for every linked component. Batocera's `XEMU_LICENSE = GPLv2` describes the emulator; xemu's own [license explanation][hdd-xemu-license] distinguishes separately distributed programs and their licenses. It is not a blanket HDD/dashboard grant.

Do not confuse this legacy seed with today's recommended image. The current [required-files page][xemu-files] links to **xemu-dashboard**, not the old1.0 ZIP, and says that image contains only an unsigned dashboard, not Microsoft's dashboard. The [dashboard page][hdd-dashboard-docs] confirms that replacement is optional for launching games. The newer project's [README][hdd-dashboard-readme] describes a different HDD-generation recipe, FTP and disc autolaunch; its [MIT license][hdd-dashboard-license] grants use and redistribution subject to retaining its copyright/permission notice. Those are real permissive sources, observed on this date, but neither that license nor current documentation authenticates the older stock dashboard bytes.

Disposition for06: packaged availability, intended origin, actual preformatted/dashboard contents and affirmative publisher evidence are resolved. Exact release-to-stock byte correspondence and complete redistribution terms for this embedded legacy dashboard remain unestablished. The missing evidence is an upstream member checksum/attestation matching `eb35d069…`, together with terms/notices covering that dashboard binary and its linked contents, or equivalent retained build provenance. The unpinned, interactive recipe alone cannot supply those facts. This is not a finding that the stock HDD is prohibited, and it does not close the whole HDD qualification gate or mark06 Done.

The existing alternative remains an operator-supplied, rights-qualified clean HDD seed through the already mounted read-only BIOS library. The coordinator can copy that declared seed only into the owned disposable `/userdata/saves/xbox/xbox_hdd.qcow2` before stock launch. The inspected packaged generator/config/paths matched manifest SHA-256 values `5feb5f75940cb560a86f2755fa804be10be664f50a76cd827e562baf84b1b021`, `64ef23f4121e1f4a27d639d824ebed358fc6fce1672a297a93dee656e2b4a557` and `c5163634606dc88b785937acd56df1e4d3b103955fb1d1ca292f08628e533ef6`; they confirm that stock configgen preserves an existing save-path HDD and seeds from stock only when absent. No new mount, configgen override, production-state copy or automatic download is needed. Keep external MCPX/BIOS read-only and all writable HDD/EEPROM/config/save/cache derivatives in disposable userdata. Native compatibility with the selected permitted XISO, operator BIOS/MCPX and packaged backend remains untested until the actual case. Neither upstream legality claims nor these static reads prove launch/output or Guide+Start exit.

## Alternatives, negative findings and failures

### Existing nxdk_pgraph_tests lead

The earlier pinned lead is `abaire/nxdk_pgraph_tests` revision `b3b7f7587b1924f46fb7bb9192efd61cab427282`. Its [README][pgraph-readme] confirms a genuine input-sensitive menu, so it is inaccurate to call the entire project graphics-only. D-pad moves the cursor, A or Start enters a submenu/test, B or Back returns and can exit at the root, and Black exits. A future menu-cursor change could be a guest observation, but it would need an exact menu/config/render identity and an assertion that excludes autorun.

It is a worse initial fixture than the nxdk controller sample:

- No input during the initial timeout starts tests automatically. Tests advancing or rendering changing is not proof of a button. [CMake][pgraph-cmake] and JSON settings support disabling autorun; any selected configuration must be recorded rather than silently relying on timing.
- Guest B/Back/Black self-exit must not be mistaken for host Guide exit. Plain Start selects a submenu/test, not necessarily an exit, but later test completion can reboot or shut down according to configuration.
- [Submodules][pgraph-submodules] include a modified nxdk, printf, fpng, tiny-json and pbkitplusplus. The README adds `nv2a-vsh` and a bootstrap workflow that builds nxdk samples. This is materially more source/tooling than the simple visualizer.
- The [pinned tree][pgraph-tree] contains textures, DDS conversions and models, including `resources/models/light_control_test_mesh_suzanne.mesh`, alongside procedural tests. A root MIT label and published XISO do not establish each imported resource's provenance or full release contents.

Retain it as a graphics-testing/alternate menu lead, not a cleared ready bundle and not evidence of completed controller tests. This research did not attempt to license-clear every resource in a candidate that is not selected. Removing resources from a release or manufacturing a reduced suite would require a new reproducible source/build input record, not a claim that the existing release is cleared.

### Other inspected or previously rejected paths

- nxdk `samples/usb/main.c` prints USB connect/disconnect identifiers. It does not display button state. Device enumeration cannot replace guest A press/release evidence.
- Do not reintroduce the earlier flagged Sony-derived PSn00bSDK routines, original 240p-suite artwork, or commercial disc license sectors as convenience dependencies.
- No already inspected source established an RPCS3 or Xenia qualification improvement. This report does not open another expanded-target research track, upgrade xsdk's known unsupported presentation path or invent an Xbox 360 firmware prerequisite.
- The attempted nxdk `Licensing` wiki URL resolved to a create-page response, not a license policy. The license API 404 is corroboration of absent endpoint metadata only. The substantive gap is the actual unmarked sample and lack of an inspected covering assignment, not the API response by itself.

## Input is separate from every configured Guide action

Both selected leads help plain guest input. Neither proves hotkey delivery by itself. The required route remains native gamepad to existing project adapter to unchanged stock hotkeygen to the emulator/common-context consumer effect. Emitting F7/Alt+F4 directly, observing a receiver event or seeing a process end does not prove that route.

The pinned [DuckStation context][stock-duckstation] actually declares exit Alt+F4, menu F7, reset F6, restore state F1, save state F2, previous slot F3, next slot F4, rewind F5, fast-forward Tab and next disk F8. The earlier research's menu/exit summary is not an exhaustive action list. The pinned [xemu context][stock-xemu] declares exit only, with no emulator-specific menu. Inspect the common context and trigger applicability on the actual pinned image as well; do not invent an xemu menu or omit common shortcuts.

A static pad display is useful for input but does not by itself make reset, fast-forward, rewind or save/restore effects visually distinguishable. Qualification must find actual consumer-visible effects, including applicable emulator UI/state changes, or establish nonapplicability from stock configuration. Single-disc media may limit next-disk applicability; it is not an automatic waiver without stock evidence. No new animation, injected overlay or emulator patch is proposed to manufacture those observations. If the full configured action set cannot be observed with this fixture/profile, supplement the legal fixture set or revisit the exact blocker rather than call menu/exit sufficient.

Retain real server screenshots at rendered, held, released and applicable shortcut checkpoints for optional review. Automatic assertions, negative controls, pinned process exit, launcher completion and ready EmulationStation return remain mandatory. Native device discovery, host SDL/controller mapping and guest SDL/PSCTP consumption are distinct facts. This investigation proves none by execution.

## Decision impact and remaining inputs

Recommend carrying PS1 example 11 forward as the primary rights-supported source lead, with data-only `mkpsxiso` BIN/CUE packaging and external BIOS. Recommend replacing nxdk_pgraph_tests as the first Xbox input-fixture investigation with nxdk's SDL gamecontroller sample, while visibly retaining its permission gate. Do not mark either fixture selected-and-qualified in the executable catalog yet.

The next factual inputs are specific:

1. An explicit upstream license statement covering nxdk `samples/sdl_gamecontroller/main.c` and its Makefile at the inspected revision or a later immutable revision, plus provenance and appropriate distribution treatment for the retained PBKit font and CxBE default-logo bytes. If the sample grant cannot be established, another rights-qualified Xbox fixture is needed. A generic nxdk MIT template is not the missing evidence.
2. Exact host compiler/tool versions and licenses, resolved Python dependencies for PS1, all pinned source inputs, actual linked members and complete binary notices. Produce XBE/XISO and PS1 BIN/CUE hashes with a corresponding-source/build recipe during separately authorized implementation. No ready artifact was established here.
3. The PS1 data-only, no-Sony-license disc must boot by normal stock configgen on the pinned DuckStation/BIOS profile. The nxdk-generated XISO must boot by normal stock xemu configgen with the accepted operator firmware and disposable HDD/EEPROM route. Current upstream documentation cannot answer these packaged runtime questions.
4. Native mapping/port identity and `cross` present/absent or `A:0/1/0` screenshot assertions must be qualified with no-input and wrong-button controls. Record actual geometry, tolerances and observation budgets rather than copying source guest coordinates into an assumed host capture region.
5. Establish all applicable common and emulator Guide actions and their independent consumer-visible effects. Record plain Start behavior first. Static input glyphs alone do not settle the remaining shortcut oracles.

There is no new scope-reduction decision to ask the user. The accepted source-build workflow and external firmware model already support the recommended direction. The missing Xbox grant is an upstream factual permission input, not a request that the user accept legal uncertainty. If rights clarification fails and another existing fixture cannot meet the contract, authorizing a newly written redistributable fixture would be a consequential implementation choice to discuss separately. It is not authorized or implemented by this report.

The exact remaining question is: can the permission-complete, pinned PS1 controller disc and nxdk controller XISO be produced and qualified on the accepted stock image with automatic guest press/release observations and every applicable Guide effect, without changing runtime behavior? Source research narrows that question substantially; only permission completion and authorized artifact/native qualification can answer it.

## Primary sources

[ps1-tree]: https://api.github.com/repos/spicyjpeg/ps1-bare-metal/git/trees/2af848a02dbdcc606b915b3b90698f9bbe9e74f3?recursive=1
[ps1-readme]: https://github.com/spicyjpeg/ps1-bare-metal/blob/2af848a02dbdcc606b915b3b90698f9bbe9e74f3/README.md
[ps1-controller]: https://github.com/spicyjpeg/ps1-bare-metal/blob/2af848a02dbdcc606b915b3b90698f9bbe9e74f3/src/11_controllers/main.c
[ps1-cmake]: https://github.com/spicyjpeg/ps1-bare-metal/blob/2af848a02dbdcc606b915b3b90698f9bbe9e74f3/CMakeLists.txt
[ps1-setup]: https://github.com/spicyjpeg/ps1-bare-metal/blob/2af848a02dbdcc606b915b3b90698f9bbe9e74f3/cmake/setup.cmake
[ps1-tools]: https://github.com/spicyjpeg/ps1-bare-metal/blob/2af848a02dbdcc606b915b3b90698f9bbe9e74f3/cmake/tools.cmake
[ps1-requirements]: https://github.com/spicyjpeg/ps1-bare-metal/blob/2af848a02dbdcc606b915b3b90698f9bbe9e74f3/tools/requirements.txt
[ps1-license]: https://github.com/spicyjpeg/ps1-bare-metal/blob/2af848a02dbdcc606b915b3b90698f9bbe9e74f3/LICENSE
[ps1-printf]: https://github.com/spicyjpeg/ps1-bare-metal/blob/2af848a02dbdcc606b915b3b90698f9bbe9e74f3/src/vendor/LICENSE.printf
[ps1-releases]: https://api.github.com/repos/spicyjpeg/ps1-bare-metal/releases?per_page=3
[ps1-boot-format]: https://psx-spx.consoledev.net/cdromfileformats/#cdrom-file-playstation-exe-and-systemcnf
[gcc-exception]: https://www.gnu.org/licenses/gcc-exception-3.1.html
[mk-readme]: https://github.com/Lameguy64/mkpsxiso/blob/a6b11ea86e67c189137ac50a4066044b3fdb0525/README.md
[mk-example]: https://github.com/Lameguy64/mkpsxiso/blob/a6b11ea86e67c189137ac50a4066044b3fdb0525/examples/example.xml
[mk-license]: https://github.com/Lameguy64/mkpsxiso/blob/a6b11ea86e67c189137ac50a4066044b3fdb0525/LICENSE.md
[mk-cmake]: https://github.com/Lameguy64/mkpsxiso/blob/a6b11ea86e67c189137ac50a4066044b3fdb0525/CMakeLists.txt
[mk-tree]: https://api.github.com/repos/Lameguy64/mkpsxiso/git/trees/a6b11ea86e67c189137ac50a4066044b3fdb0525?recursive=1
[mk-tiny-license]: https://github.com/leethomason/tinyxml2/blob/3dcad8e3c38e7091ae3771bf63020027f91715ce/LICENSE.txt
[mk-ghc-license]: https://github.com/gulrak/filesystem/blob/0e72911ba0f37f3eb883b181b855a5f4eb046ca1/LICENSE
[mk-audio-license]: https://github.com/mackron/miniaudio/blob/9634bedb5b5a2ca38c1ee7108a9358a4e233f14d/LICENSE
[mk-thread-license]: https://github.com/log4cplus/ThreadPool/blob/251db61ff3e3c7b16436c9936c53e6f68ff07720/COPYING
[stock-duckstation]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/generators/duckstation/duckstationGenerator.py
[nxdk-tree]: https://api.github.com/repos/XboxDev/nxdk/git/trees/8d8438186c5dcf1187672b686a91c4603be9e111?recursive=1
[nxdk-readme]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/README.md
[nxdk-pad]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/samples/sdl_gamecontroller/main.c
[nxdk-pad-make]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/samples/sdl_gamecontroller/Makefile
[nxdk-pad-history]: https://api.github.com/repos/XboxDev/nxdk/commits?path=samples/sdl_gamecontroller/main.c&per_page=30
[nxdk-make]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/Makefile
[nxdk-xiso]: https://github.com/XboxDev/nxdk/wiki/Create-an-XISO
[nxdk-releases]: https://api.github.com/repos/XboxDev/nxdk/releases?per_page=3
[nxdk-ci]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/.github/workflows/build_samples.yml
[nxdk-mit]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/LICENSES/MIT.txt
[nxdk-license-api]: https://api.github.com/repos/XboxDev/nxdk/license
[nxdk-libs]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/lib/Makefile
[nxdk-sdl-make]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/lib/sdl/Makefile
[nxdk-sdl-port]: https://github.com/XboxDev/nxdk-sdl/blob/2554902f7bbf469449216ee25f88016421271cd8/Makefile.xbox
[nxdk-pdclib-license]: https://github.com/XboxDev/nxdk-pdclib/blob/9d257524e20e3e1ac90163b37f07702053e36321/COPYING.CC0
[nxdk-sdl-license]: https://github.com/XboxDev/nxdk-sdl/blob/2554902f7bbf469449216ee25f88016421271cd8/COPYING.txt
[nxdk-ttf-license]: https://github.com/libsdl-org/SDL_ttf/blob/200901a8f55bcf7aa031157f53a575c942d2b7aa/COPYING.txt
[nxdk-ft-license]: https://github.com/libsdl-org/SDL_ttf/blob/200901a8f55bcf7aa031157f53a575c942d2b7aa/external/freetype-2.4.12/docs/LICENSE.TXT
[nxdk-ftl]: https://github.com/libsdl-org/SDL_ttf/blob/200901a8f55bcf7aa031157f53a575c942d2b7aa/external/freetype-2.4.12/docs/FTL.TXT
[nxdk-image-license]: https://github.com/libsdl-org/SDL_image/blob/ab2a9c602623193d61827ccd395302d92d90fc38/COPYING.txt
[nxdk-zlib-license]: https://github.com/madler/zlib/blob/51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf/LICENSE
[nxdk-png-license]: https://github.com/pnggroup/libpng/blob/a40189cf881e9f0db80511c382292a5604c3c3d1/LICENSE
[nxdk-jpeg-license]: https://github.com/libjpeg-turbo/libjpeg-turbo/blob/166e34213e4f4e2363ce058a7bcc69fd03e38b76/LICENSE.md
[nxdk-usb-license]: https://github.com/XboxDev/libusbohci/blob/6a0c5fefbcd9db53f4a27ee10df99f93d5bce745/LICENSE.txt
[nxdk-usb-disclaimer]: https://github.com/XboxDev/libusbohci/blob/6a0c5fefbcd9db53f4a27ee10df99f93d5bce745/DISCLAIMER.md
[nxdk-lwip-license]: https://github.com/lwip-tcpip/lwip/blob/77dcd25a72509eb83f72b033d219b1d40cd8eb95/COPYING
[nxdk-print]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/lib/pbkit/pbkit_print.c
[nxdk-debug]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/lib/hal/debug.c
[nxdk-unscii]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/lib/hal/font_unscii_16.h
[nxdk-runtime]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/lib/xboxrt/Makefile
[nxdk-import]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/lib/xboxkrnl/Makefile
[nxdk-cxbe]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/tools/cxbe/Main.cpp
[nxdk-logo]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/tools/cxbe/Logo.cpp
[nxdk-xbe]: https://github.com/XboxDev/nxdk/blob/8d8438186c5dcf1187672b686a91c4603be9e111/tools/cxbe/Xbe.cpp
[xiso-license]: https://github.com/XboxDev/extract-xiso/blob/b72e5b60d598ec6df80534cda19cdcd4361aa18c/LICENSE.TXT
[xemu-disc]: https://xemu.app/docs/disc-images/
[xemu-files]: https://xemu.app/docs/required-files/
[stock-xemu]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/generators/xemu/xemuGenerator.py
[stock-xemu-config]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/configgen/generators/xemu/xemuConfig.py
[pgraph-readme]: https://github.com/abaire/nxdk_pgraph_tests/blob/b3b7f7587b1924f46fb7bb9192efd61cab427282/README.md
[pgraph-tree]: https://api.github.com/repos/abaire/nxdk_pgraph_tests/git/trees/b3b7f7587b1924f46fb7bb9192efd61cab427282?recursive=1
[pgraph-cmake]: https://github.com/abaire/nxdk_pgraph_tests/blob/b3b7f7587b1924f46fb7bb9192efd61cab427282/CMakeLists.txt
[pgraph-submodules]: https://github.com/abaire/nxdk_pgraph_tests/blob/b3b7f7587b1924f46fb7bb9192efd61cab427282/.gitmodules
[stock-xemu-recipe]: https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/emulators/xemu/xemu.mk
[hdd-release]: https://api.github.com/repos/xemu-project/xemu-hdd-image/releases/tags/1.0
[hdd-tag]: https://api.github.com/repos/xemu-project/xemu-hdd-image/git/ref/tags/1.0
[hdd-tree]: https://api.github.com/repos/xemu-project/xemu-hdd-image/git/trees/b2eeeae652295d60c5cefff31ef4a602299b5dbd?recursive=1
[hdd-readme]: https://github.com/xemu-project/xemu-hdd-image/blob/b2eeeae652295d60c5cefff31ef4a602299b5dbd/README.md
[hdd-dummy-source]: https://github.com/xemu-project/xemu-hdd-image/blob/b2eeeae652295d60c5cefff31ef4a602299b5dbd/xboxdash/main.c
[hdd-dummy-makefile]: https://github.com/xemu-project/xemu-hdd-image/blob/b2eeeae652295d60c5cefff31ef4a602299b5dbd/xboxdash/Makefile
[hdd-xemu-license]: https://github.com/xemu-project/xemu/blob/v0.8.134/LICENSE
[hdd-dashboard-docs]: https://xemu.app/docs/dashboard/
[hdd-dashboard-readme]: https://github.com/xemu-project/xemu-dashboard/blob/master/README.md
[hdd-dashboard-license]: https://github.com/xemu-project/xemu-dashboard/blob/master/LICENSE
[hdd-fatx-structures]: https://api.github.com/repos/XboxDev/fatx/git/blobs/c3666fc91229012f3d964091847c9e1e5dd653b5
[hdd-fatx-partitions]: https://api.github.com/repos/XboxDev/fatx/git/blobs/93024ef66d9ef5092ca906b2699649ce881710f4
[hdd-fatx-allocation]: https://api.github.com/repos/XboxDev/fatx/git/blobs/10181120c0795f7ddf2958cfab29a894449b4b77
