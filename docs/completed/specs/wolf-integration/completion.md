# Completion: maintained Wolf integration

State: Complete
Source before completion: `docs/active/specs/wolf-integration/`
Delivered location: `docs/completed/specs/wolf-integration/`
Parent: [repository maturation](../../../completed/epics/repository-maturation/epic.md). This child delivered independently; the parent's combined-outcome review is recorded separately.

## Delivered behavior

All seven [tickets](tickets/) are Done. The maintained coordinator separates local checks, packaged fixtures, native smoke, full six-backend regression and explicit expanded replay. Normal frontend/transport and all five receivers remain independent requirements. Eligible emulators use stock launcher/configgen, actual rendering/native-device consumption, native Guide+Start press/release, pinned-emulator exit, launcher zero, retained evidence and owned cleanup.

The complete baseline passed NES/FCEUmm, SNES/Snes9x, Atari2600/Stella, DuckStation OpenGL and Vulkan, and xemu. Mega Drive/GenesisPlusGX is an observed nonblocking no-media skip, never a passing emulator result. Automatic DuckStation visual selection remains scoped to generated OpenGL settings; Vulkan and stock Batocera are preserved.

Expanded replay validates the exact retained successful proof and current media/profile/firmware before input. Selected backend evidence retains only constrained necessary fields, not arbitrary environments. Reports/qualifications publish privately without overwrite; sync/publication failures cannot leave reusable passing claims. Advertised coverage retains 253 systems and 477 mappings, with six qualified definitions covering five mappings and 472 mappings still unqualified.

## Verification

Exact image: `sha256:109c14e2c097e3b53d8feef6afb65dfddae09c2e3cb3b7f5f3ce4423a7c76e9c`.
Packaged source: `worktree-sha256:175676dc4cbb761031dd423ee41c88e22dfeccf63d008884cea44cefc37e768e`.

| Exercised check                                        | Observed outcome                                                                                                                                                                                                                |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Complete-source branch-enabled pytest                  | 1,121 passed, 11 skipped; 108.93 seconds                                                                                                                                                                                        |
| Targeted coordinator/installed-state suites            | 479 passed; 53.96 seconds                                                                                                                                                                                                       |
| Native `--tier regression`                             | [15a1f2112dad4487905100cb4a5d8615](../../../../output/integration/15a1f2112dad4487905100cb4a5d8615/report.json): full gate true, eight passing components/one no-media skip; five passing backend rows/one skip; 156.45 seconds |
| Native `--tier expanded`, all six exact qualifications | [c85e22e7deb046c58c8cce849841ee58](../../../../output/integration/c85e22e7deb046c58c8cce849841ee58/report.json): eight components passed, full-regression flag correctly false; 150.33 seconds                                  |
| Independent evidence/current-input inspection          | 83 full-run and 78 expanded capture digests/private modes/causal checkpoints verified; all 25 packaged inputs match current source; final full-run frontend/emulator captures visually inspected                                |
| Independent final native cleanup/config inspection     | All 30 resource sets from two full/two expanded attempts absent; zero sessions/lobbies, no unclassified activity; beta config unchanged at that checkpoint                                                                      |
| Configured hooks                                       | Changed/new files pass without suppression; explicit operational selection checks 52 Python files. Repeated mandatory all-files runs retain only the approved inherited findings, with unchanged passing formatters             |

[Ticket07](tickets/07-full-baseline-and-testing-guide.md) records the causal regressions, final checks and review. Private [whole-spec verification](../../../../output/integration/ticket07-0dde938ef53642f3b2583423219db897/final-verification.json) maps acceptance to observed scenarios. The [testing guide](../../../../tests/README.md#operator-sequence-and-current-verification) owns exercised commands, permissions, prerequisites, recovery and proof limits. Local media selection/reproduction smoke and no-effects planning also passed. Saved-image inventory preserves all 112,729 stock paths with 21,799 isolated additions.

The direct correctness/security/maintainability/test-quality/spec review resolved passing-proof fabrication, failed-run qualification, partial publication, lossy standalone replay and installed catalog/canonical-path errors. Earlier successful/failed/diagnostic reports remain immutable; no sanitizer or validator was weakened, no Vulkan fallback added and no new image built for host-only repairs.

## Deviations and limits

The spec explicitly approves inherited-file hook failures and a bounded application-line-coverage exception. Final line coverage is 3,452/8,422 lines across all 27 application files, 40.99%; only tests are omitted, with 39 default excluded lines. Native/subprocess coverage is not merged. All-files findings remain 50 Ruff errors, 1,843 mypy errors in 29 inherited files and four Statix W04 warnings. No new-file exception or repository-wide compliance is claimed; modernization retains its 80% floor.

RPCS3/Xenia and other unqualified mappings remain gaps. MangoHUD-enabled bezels, gameplay, graceful shutdown, saves, frontend recovery, physical Moonlight forwarding and decoded/heard client output are not qualified. Server captures and the approved shortcut-exit contract do not imply those outcomes. [Modernization subsequently repeated the complete native gate](../repository-modernization/completion.md) on its own changed source/image; that later proof does not extend this baseline's image identity.

All 18 original workspace files moved intact before reference repair; research and unsuccessful approaches remain preserved. Operational document links use the completed location. Two frozen image-bound source comments retain their original active-workspace paths as historical source references: `runtime/duckstation_visual.py:237` maps to the [EGL/window trace](research/duckstation-startup-failure.md#actual-egl-config-and-qt-window-trace), and `runtime/runtime.py:319` maps to the [wrapper decision](explore.md#configgen-preserving-emulator-wrappers). Their packaged bytes/provenance were not changed merely for lifecycle bookkeeping. The private [reference inventory](../../../../output/integration/ticket07-0dde938ef53642f3b2583423219db897/completion-reference-inventory.json) records preserved files and old/new targets.

After native verification, the operator separately authorized changing only beta's saved image to this exact verified image. [Transaction evidence](../../../../output/integration/ticket07-0dde938ef53642f3b2583423219db897/beta-image-change-09572d99d0f149bf97623c6cab056f44.json) verifies every unrelated config byte/value, runner/home identity and ownership/mode/xattr preserved, a root-private backup and unchanged Wolf process identity. No restart, userdata change, image removal or production change was performed. Beta reload/manual testing awaits the operator; it is not a missing automated baseline outcome.

## Current documentation

- [Application state](../../../current/app.md#full-native-baseline-and-exact-input-replay): exercised native tiers, image-bound results, evidence/privacy limits and beta-only handoff.
- [Tooling](../../../current/tooling.md#current-configuration): complete-source pytest/coverage and explicitly bounded inherited findings.
- [Batocera integration standard](../../../standards/batocera.md#duckstation-visual-selection-example): unchanged override policy with corrected qualification/routing references.
- [Root README](../../../../README.md) and [testing guide](../../../../tests/README.md): exercised entry points, tier selection, exact-input reuse and cleanup/proof boundaries.

At this child's delivery, the parent combined-outcome review and modernization were outstanding. [Modernization delivery](../repository-modernization/completion.md) now records the installed cutover and its own local/build/native gates; the parent owns their combined review. Neither completion grants new installation, build, native, deployment or service-interruption permission.
