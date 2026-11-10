# Batocera upstream emulator testing

Historical source observations refer to the experiment layout and the recorded image/revision, not a new measurement of current behavior. Source links now navigate the maintained counterparts; obsolete experiment line anchors are not current line numbers.

Research date: 2026-10-31. Public-source and local-source inspection only. No emulator suite, build, deployment or private/operator evidence was executed or inspected for this research. Existing local run results below are recorded evidence, not fresh measurements.

## Finding

Batocera already has real-emulator launch automation, `batocera-test`. This project should not be presented as Batocera's first automated emulator test. The defensible contribution is narrower: injecting actual synthetic controller chords and requiring stronger, bounded process-lifecycle evidence, rather than only requesting the named exit action. [U1, L1, L2]

The inspected public CI runs Python tests and lint. No invocation of `batocera-test`, booted-image emulator matrix or hardware-farm orchestration was found in that workflow. This does not establish the absence of private, external or maintainer-operated automation, nor how frequently the packaged runtime tool is used. [U2]

The inspected upstream snapshot is `cc793b75261c92d3b2a490c351e758ba155e9936`. The live API reported its commit timestamp as `2026-11-01T05:36:15Z`, later than the task date. These links identify the retrieved snapshot, not a reconstructed historical cutoff. [U9]

An independent date-bounded inspection at `a3d49969295830ff1f136d393e33839f858fa8d7`, committed on 2026-10-31, found the same runtime script. It is also unchanged at release tag `batocera-42`, commit `cae40d885f539abd1445a217ec64c340d559e4fa`. This is established upstream functionality, not just a newly discovered master-branch experiment. [U10]

## What Batocera already does

### Real emulator launches

The packaged `batocera-test` script reads EmulationStation's system configuration and finds local media. By default, executable code randomly samples two systems and chooses one game per available sampled system. An explicit `/userdata/system/gamesToTest.yml` supplies a game list instead. The comment promising one game per system is broader than that default implementation. [U1]

For each selected game it:

1. POSTs the media path to EmulationStation's `http://localhost:1234/launch` endpoint.
2. Waits 15 seconds by default, configurable with `--time`.
3. Queries `/runningGame` and checks the reported `systemName`.
4. Invokes `batocera-screenshot`.
5. Requests exit with `hotkeygen --send exit` and polls `/runningGame` until the system is no longer reported.
6. Writes a text report and screenshot directory under `/userdata/reportTest/batocera-test_<timestamp>/`. [U1]

The core system configuration selects the test package, whose install rule places the tool at `/usr/bin/batocera-test`. That proves package integration, not successful execution on every released image or scheduled CI use. [U3]

Its current source has weaker success checks than this project's native exit checks. Screenshot command status and image content are not validated. The success flag is set before exit finishes. The exit command's status is not checked and the polling loop has no exit deadline. Its running-game check binds to an ES-reported system, not an emulator PID/start identity. These are source observations, not failures reproduced here. [U1]

### Public CI and human QA

The inspected `checks.yml` runs `uv run py.test python-src package/batocera/utils/hotkeygen` and a separate `prek` lint job on `ubuntu-latest`, for matching changed paths. Automated tests do exist; this workflow is not a real-emulator image test. Inspected test examples use fake filesystem/mocked launch behavior, and the hotkeygen proxy test checks generated D-Bus proxy consistency. [U2, U4]

Official release validation asks testers to verify the image/version, at least three emulators including RetroArch, audio and optionally Kodi. The page frames this as a short final boot/minimum-functionality check, distinct from earlier bug-finding. The issue-report guide also describes beta testing and contributor access to particular hardware. Automated userspace checks would complement this process rather than replace hardware validation. [U5, U6]

The official organization's historical `evmapy` tests also exercise synthetic events, mappings and device-removal behavior with mocked devices/output. Those are relevant automated input-component tests, but not a live controller-to-emulator integration suite. Its old Travis configuration does not establish current CI execution. [U11]

## Comparison with this repository

| Behavior                | Upstream `batocera-test` source                             | This repo's maintained native checks                                                                      |
| ----------------------- | ----------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Start a real emulator   | ES HTTP launch endpoint                                     | Stock launcher/configgen in an owned Wolf session                                                         |
| Controller exit trigger | `hotkeygen --send exit`, a named semantic action            | Synthetic gamepad Guide+Start press/release through the stock input path and additive transport           |
| Running evidence        | ES reports the selected system                              | Pinned emulator identity, exact backend/core and live output barrier                                      |
| Image evidence          | Calls screenshot helper without checking its status/content | Server-side capture with nonblank-content predicate; not a gameplay or graphics-correctness oracle        |
| Exit evidence           | Polls ES state without a deadline                           | Same pinned process exits within budget and launcher returns zero; forced teardown cannot produce success |
| Results                 | Text report and screenshots                                 | Structured image/source-bound reports, artifact hashes, explicit skips and independent owned cleanup      |

Sources: upstream implementation [U1]; local lifecycle, rendered-output predicate and testing guide [L1, L2, L3]. The named-action request omits the gamepad binding and chord-recognition boundary tested locally. That is a concrete difference, not evidence that the complete method is unprecedented.

The local guide records full regression run `9921a31c38e84c229c05776716c13c91` on image109c14e2/source175676dc, with frontend/five receivers and six emulator variant exits: NES, SNES, Atari 2600, DuckStation OpenGL, DuckStation Vulkan and xemu. Mega Drive skipped for absent compatible media. That is five exercised backend rows, not six. The guide separately records a failed expanded replay and pending complete-proof rerun; do not turn the recorded regression pass into a claim that replay is qualified. [L1]

Important limits:

- The emulator exit tier directly invokes the stock launcher rather than navigating ES to select a game. Frontend readiness is a separate case. Upstream's existing ES launch route is worth preserving. [U1, L1, L4]
- Nonblank server pixels do not establish correct graphics, gameplay, decoded Moonlight video or heard audio. `rendered_content` checks the center image's dimensions and color diversity, not a known game state. [L3]
- Native controller consumption and a working hotkey do not prove that guest gameplay controls work. Upstream issue #15477 reports precisely that distinction: controllers worked in ES and the exit hotkey worked, while in-game controls failed on Pi4/v42. The reporter later said v43 fixed it. The current local exit test must not be advertised as catching this whole class of bug. [U7, L1]
- Observed exit does not qualify graceful shutdown, save persistence or frontend recovery. [L1, L2]
- The Wolf/Xwayland/XTEST session, device forwarding and injected GPU libraries differ from a stock Batocera boot. A container result cannot establish a board's bootloader, kernel, physical USB/Bluetooth or HDMI-audio behavior. This is an environment distinction, not a measured failure. [L4]
- Current upstream documents a `batocera-launch` replacement for the older configgen launcher. A contribution must target the launch interface of the tested upstream image, not assume this repo's pinned 43.1-era commands match current master. [U8, L4]

## Recommended upstream approach

This is a proposal, not evidence of maintainer interest or an implementation authorization.

Offer an optional controller/lifecycle regression mode for the existing `batocera-test` approach. Lead with the behavior and failure evidence, not a requirement to adopt GoW or Wolf. Keep the container runner as one possible execution environment and aim to make the assertions usable on normal Batocera targets too.

A small first demonstration should use one libretro core and one standalone emulator, explicit reproducible media, and a controller hotkey chord. Retain stock launch/configuration behavior. Record build, backend, renderer, input mapping and hardware identities; prove live-before/dead-after process identity; bound startup/exit; distinguish forced cleanup and missing-media skips from success. Produce a concise sanitized machine-readable report. Use distributable homebrew/test media where possible and keep licensed BIOS/media private.

Show a controlled failing-before/passing-after example at the input boundary, such as a disposable broken pad binding that the direct named-action request bypasses. This is a proposed demonstration, not one executed in this research. It would explain the incremental value much better than claiming all emulators work.

Keep ordinary host CI fast. A maintainer-triggered target runner or provisioned hardware job is a possible later integration, not infrastructure established by this research. Budget for hardware-specific behavior and test maintenance rather than proposing replacement of all human QA.

The official issue guide routes implementation discussion to Discord `#developers`, feature requests to `#batocera-linux-requests`, and reserves GitHub issues for genuine bugs. An appropriate opening question is: "I found `batocera-test`; would a mode that injects controller hotkey chords and verifies bounded same-process exit help your regression testing?" [U6]

Nothing in these sources establishes why maintainers were uninterested in the original project. Their response to a streaming/container project does not establish their response to a focused test improvement.

## Sources

### Upstream primary sources

- **U1:** [`batocera-test` implementation](https://github.com/batocera-linux/batocera.linux/blob/cc793b75261c92d3b2a490c351e758ba155e9936/package/batocera/utils/batocera-test/src/batocera-test).
- **U2:** [Public Checks workflow](https://github.com/batocera-linux/batocera.linux/blob/cc793b75261c92d3b2a490c351e758ba155e9936/.github/workflows/checks.yml).
- **U3:** [Core system selection](https://github.com/batocera-linux/batocera.linux/blob/cc793b75261c92d3b2a490c351e758ba155e9936/package/batocera/core/batocera-system/Config.in#L303) and [test installation rule](https://github.com/batocera-linux/batocera.linux/blob/cc793b75261c92d3b2a490c351e758ba155e9936/package/batocera/utils/batocera-test/batocera-test.mk).
- **U4:** [Launcher CLI test](https://github.com/batocera-linux/batocera.linux/blob/cc793b75261c92d3b2a490c351e758ba155e9936/python-src/batocera-launch/tests/test_cli_main.py), [shared pytest fixtures](https://github.com/batocera-linux/batocera.linux/blob/cc793b75261c92d3b2a490c351e758ba155e9936/python-src/pytest-batocera/pytest_batocera/plugin.py), and [hotkeygen proxy test](https://github.com/batocera-linux/batocera.linux/blob/cc793b75261c92d3b2a490c351e758ba155e9936/package/batocera/utils/hotkeygen/tests/test_proxies.py).
- **U5:** [Official release process, revision1778222025](https://wiki.batocera.org/doku.php?id=release_process&rev=1778222025).
- **U6:** [Official issue-report and beta guidance, revision1702704408](https://wiki.batocera.org/doku.php?id=report_issue&rev=1702704408).
- **U7:** [Issue15477, controllers work in ES but not in RetroArch](https://github.com/batocera-linux/batocera.linux/issues/15477). User report, not independently reproduced here.
- **U8:** [Current launcher README](https://github.com/batocera-linux/batocera.linux/blob/cc793b75261c92d3b2a490c351e758ba155e9936/python-src/batocera-launch/README.md).
- **U9:** [Retrieved commit metadata](https://api.github.com/repos/batocera-linux/batocera.linux/commits/cc793b75261c92d3b2a490c351e758ba155e9936).
- **U10:** [Date-bounded runtime script](https://github.com/batocera-linux/batocera.linux/blob/a3d49969295830ff1f136d393e33839f858fa8d7/package/batocera/utils/batocera-test/src/batocera-test) and [same script at v42](https://github.com/batocera-linux/batocera.linux/blob/cae40d885f539abd1445a217ec64c340d559e4fa/package/batocera/utils/batocera-test/src/batocera-test).
- **U11:** [Historical evmapy source-event tests](https://github.com/batocera-linux/evmapy/blob/bd65338c236cd30b4f2d7835733ea5d6b108b75d/tests/test_source.py), [multiplexer tests](https://github.com/batocera-linux/evmapy/blob/bd65338c236cd30b4f2d7835733ea5d6b108b75d/tests/test_multiplexer.py) and [Travis configuration](https://github.com/batocera-linux/evmapy/blob/bd65338c236cd30b4f2d7835733ea5d6b108b75d/.travis.yml).

### Local sources

- **L1:** [Maintained testing guide](../../../../../tests/README.md), especially tiers, current verification, baseline interpretation and evidence limits.
- **L2:** [EmulatorLifecycle.run](../../../../../src/batocera_gow/runtime/emulator_lifecycle.py), live output/chord/pinned-exit transition.
- **L3:** [emulator_probe.rendered_content](../../../../../src/batocera_gow/runtime/emulator_probe.py), nonblank-output predicate.
- **L4:** [Current application state](../../../../current/app.md), Wolf runtime/input transport, pinned stock behavior and recorded qualifications. The maintained guide is more current for the combined baseline and replay status.
