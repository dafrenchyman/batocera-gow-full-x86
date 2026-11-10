# 01: Mounted-media configuration and coverage catalog

**Status:** Done

## Parent

[Maintained Wolf integration and testing guide](../spec.md)

## What to build

Deliver usable content configuration, stock-backed media selection and maintained executable case/catalog records in the existing `experiments/gow-full-x86/` layout. Follow root `AGENTS.md` and applicable `docs/standards/`; broad source cleanup, packaging and relocation remain modernization work.

Resolve `BATOCERA_GOW_ROMS_ROOT` and `BATOCERA_GOW_BIOS_ROOT` as Docker-host sources for the existing `/home/retro/userdata/roms:ro` and `/home/retro/userdata/bios:ro` mounts. Use one configuration contract for test app mount construction and coordinator inspection. Do not assume TOML interpolates environment variables or that the coordinator's local filesystem is the Docker host. Provide neutral `example.env` values and explicit shell-sourcing instructions. Never automatically load dotenv or read/change an operator's private `.env`. Later modernization migrates existing host-tool consumers; it is not this ticket's prerequisite.

Start from the retained [packaged inventory](../../../../completed/epics/repository-maturation/research/artifacts/packaged-system-inventory.json), [candidate catalog](../../../../completed/epics/repository-maturation/research/artifacts/fixture-candidate-catalog.json) and [readable index](../../../../completed/epics/repository-maturation/research/artifacts/fixture-candidate-index.md). Retain all advertised IDs, extensions and backend/core mappings. Recover exact system directory declarations from the matching packaged `es_systems.cfg`, whose provenance must match the approved pin. Do not guess directories from system IDs. Maintain executable cases and qualification records with test assets, preserving historical research and earlier results.

Provide an eligibility/selection operation that can be exercised locally without SSH and used against inspected native mounts later. Select only readable supported entries inside the selected stock system directory beneath the existing read-only ROM mount. Preserve CUE/track and other multi-file relationships. Random selection records the actual chosen identity/digest privately for reproduction, without rerolling a failed attempt. No arbitrary host search, extra test-only content mounts, acquisition or private-media redistribution.

Create the readable coverage table with the testing guide. Distinguish research leads, public distribution clearance, private authorized use and actual native qualification. All six required cases remain initially unqualified, and expanded gaps remain explicit. No custom ROM development, source adaptation or mandatory fixture build is introduced.

Execution claim: the current `implement-spec` request authorizes local implementation and verification of this ticket. The original `MountedMediaCatalog` worker ended; ownership is explicitly reassigned to fresh replacement `MediaVerificationFix` for ticket-owned final verification findings and evidence reconciliation. The coordinator owns integration and all-files checks. Bounded edits remain the host catalog/configuration/selection code, its tests and maintained case assets under `experiments/gow-full-x86/`, `example.env`, the initial testing guide, this ticket and a concise current-application description of the exercised local tools. Preserve existing deployment tooling and historical research. No SSH, downloads, image build/provisioning, production-state access or Git mutation belongs to this worker.

Eligibility and pre-code review: no prerequisite tickets. Read-only bounded extraction recovered `./usr/share/emulationstation/es_systems.cfg` from the retained tar. Its 212,533 original bytes match SHA-256 `401638d6cbc26e574456f36a4b59007b823b576b35422f519640be9bfd3efc23`. Three stock categories point outside the ROM tree and must remain cataloged without enabling arbitrary filesystem searches. Keep Docker-host source strings separate from explicitly supplied local/native filesystem views. Treat discovery/access/mount errors as errors, incomplete companion sets as ineligible, and extension matches as eligibility only.

Implementation uses the specification's approved public seams: catalog reconciliation and shared mount configuration; temporary-filesystem eligibility/companions and reproducible private selection; typed qualification transitions and maintained case records; local CLI and readable guide. No TDD red/green execution was observed, and test-first execution is not claimed. No public fixture bytes or firmware are distributed. Rights approval and research never imply native qualification. All six cases start unqualified; no runner, deployment cutover or native success is implied.

Verified local implementation paths: `experiments/gow-full-x86/{media_catalog.py,mounted_media.py,media_qualification.py}`, `experiments/gow-full-x86/tests/{test_media_catalog.py,test_mounted_media.py,test_media_qualification.py,media_smoke.py,README.md}`, maintained `tests/assets/media/{stock-es_systems.cfg,cases.json}`, root `example.env`, this ticket and the local-tool description in `docs/current/app.md`. The original XML is the sole directory/extension/backend declaration source and is hash-checked when loaded. All 253 entries reconcile exactly against both retained inventories. Six required cases and three expanded backend variants remain initially unqualified, with 468 mapping and 245 system/category gaps explicit.

Direct review dispositions: Docker-host strings never imply a local filesystem view; native callers must validate complete effective mounts before discovery. Anchored no-follow filesystem operations protect containment, and referenced disc components are not separate random choices. Missing companions are rejected without hiding discovery/access errors. Selection hashes all members, writes one exclusive private mode-0600 record and never rerolls; reproduction checks the recorded entry only. Research, rights and native qualification remain separate. Private use requires permission, not public game source; distribution clearance applies only to actually distributed content. Native observation summaries are a typed aggregation input, not host-generated proof of native behavior.

Final correctness/security/maintainability review resolved the smoke TRY004 finding with `TypeError`. Behavioral tests assert actual selected entries and exact companion retention, private-record modes/overwrite refusal, containment, no reroll, changed-input rejection and qualification invalidation/requalification. The coordinator exercised the reviewed final state after hook fixes. No further local correctness blocker was found; native qualification remains outside this ticket's proof.

Final coordinator evidence: `env PYTHONPATH=experiments/gow-full-x86 .venv/bin/python -m pytest experiments/gow-full-x86/tests` passed 151 tests with one host-prerequisite skip, including all 57 media cases. `.venv/bin/python experiments/gow-full-x86/tests/media_smoke.py` passed actual CLI subprocess scenarios for catalog/system lookup, no implicit dotenv, absence, private selection/mode, reproduction, overwrite refusal and changed-input refusal. Python was 3.12.12 and pytest 8.4.2. No emulator or private library was exercised.

Observed targeted test and CLI commands were:

```sh
env PYTHONPATH=experiments/gow-full-x86 .venv/bin/python -m pytest \
  experiments/gow-full-x86/tests/test_media_catalog.py \
  experiments/gow-full-x86/tests/test_mounted_media.py \
  experiments/gow-full-x86/tests/test_media_qualification.py
.venv/bin/python experiments/gow-full-x86/tests/media_smoke.py
```

The dependency-aware typing command was:

```sh
/path/to/pre-commit/repo8h96obbs/py_env-python3.12/bin/mypy --strict --python-executable .venv/bin/python \
  experiments/gow-full-x86/media_catalog.py \
  experiments/gow-full-x86/mounted_media.py \
  experiments/gow-full-x86/media_qualification.py \
  experiments/gow-full-x86/tests/test_media_catalog.py \
  experiments/gow-full-x86/tests/test_mounted_media.py \
  experiments/gow-full-x86/tests/test_media_qualification.py \
  experiments/gow-full-x86/tests/media_smoke.py
```

The coordinator ran `pre-commit run --all-files` before and after final integration. The remaining failures are 53 pre-existing Ruff findings, 1,584 legacy mypy errors across 29 files and four Statix W04 findings. The user explicitly accepts failures in pre-existing files, but requires every new file to pass pre-commit; that bounded exception is recorded in the approved spec and exploration. `.pre-commit-config.yaml` now supplies pinned pytest 8.4.2 to the isolated strict-mypy hook, without disabling any check. Explicit hooks over every generated file, including the unchanged stock XML, and all changed configuration/current/planning files passed Ruff check/format, strict mypy and Prettier. No applicable Nix/frontend files were generated. The command below records the initial explicit selection; the passing final selection additionally included `.pre-commit-config.yaml`, the stock XML, `docs/current/app.md`, `spec.md` and `explore.md`.

```sh
pre-commit run --files example.env \
  experiments/gow-full-x86/media_catalog.py \
  experiments/gow-full-x86/mounted_media.py \
  experiments/gow-full-x86/media_qualification.py \
  experiments/gow-full-x86/tests/test_media_catalog.py \
  experiments/gow-full-x86/tests/test_mounted_media.py \
  experiments/gow-full-x86/tests/test_media_qualification.py \
  experiments/gow-full-x86/tests/media_smoke.py \
  experiments/gow-full-x86/tests/README.md \
  experiments/gow-full-x86/tests/assets/media/cases.json \
  docs/completed/specs/wolf-integration/tickets/01-mounted-media-and-catalog.md \
  docs/completed/specs/wolf-integration/tickets/02-native-frontend-and-receivers.md
```

Final disposition: Done under the user's approved pre-existing-file exception. Generated files pass the configured hooks; repeated all-files execution still reports only the accepted legacy failures. The dependency-complete hook environment, final behavioral/CLI checks and review are observed. No remaining local resume work. Coordinator next reassesses 02 using the actual shared content configuration, stock catalog, media selection and qualification assets, without inferring native delivery from this ticket.

Limits: no SSH, acquisition, image build/provisioning, private `.env` access, deployment/runtime cutover or Git action was performed by this worker. No actual library absence or native launch/display/Guide+Start result was observed. Compressed/directory-format internals and firmware are not validated by extension eligibility; native qualification must supply them. Descriptor text supports bounded UTF-8/BOM, not every historical encoding. Selection is not an atomic host-library snapshot. No application-wide coverage percentage, standards compliance, native baseline or passing six-case result is claimed.

The integration resumption is verified. `MediaPrivateModeFixtureFix` added explicit0755 setup to the existing shared-parent negative fixture; product implementation and dependency artifacts did not change. The real shared-parent refusal passed under privacy umask077. Complete host run `bg_115` passed797 tests with two SDL/stock-ALSA prerequisite skips in76.13 seconds, and the maintained media CLI smoke passed. All17 generated Python modules passed configured hooks in `bg_117`. Mandatory all-files `bg_118` stayed unchanged at50 Ruff findings,1,817 mypy errors across29 inherited files and four Statix W04 warnings; every formatter passed. Direct review found no weakened privacy assertion or additional product scope. Ticket01 returns to Done under the existing-file exception. Its supplied inputs remain valid for02 and later native tickets. Application line coverage is42.17%, not an80% gate pass; whole-spec disposition remains separate.

## Acceptance criteria

- [x] Neutral configuration and documentation preserve both fixed read-only destinations, explicit `.env` sourcing and target-independent local catalog operations. Effective mount mismatches are errors, not media absence.
- [x] Catalog reconciliation preserves 253 system/category IDs, 98 emulator IDs, 233 emulator/core pairs and 477 system/backend/core mappings for the approved pin, with no duplicate/lost IDs or mappings. Exact stock directories, extensions and catalog provenance are retained.
- [x] Missing, empty and unsupported-only system folders yield `Skipped: no compatible mounted media`. Permission/discovery/mount failures do not. Multi-file selection rejects incomplete relationships without treating extension alone as proof of a working emulator.
- [x] Selection records a reproducible private media identity without exporting private filenames, library paths or media bytes into public documentation or distributed artifacts. A failed attempt is not replaced by another random candidate to obtain green.
- [x] Case records and the readable table identify system/backend/core/variant, route/format, public rights or private-use disposition, firmware requirements, qualification identity and explicit missing/unrun/failed entries. Research or rights approval cannot become passing coverage; changed inputs invalidate affected qualification claims.
- [x] Deterministic behavioral tests exercise eligibility, containment, companion files, selection identity, errors and qualification transitions. Public fixture rights are required only for content actually distributed; no private source disclosure or custom program is required.
- [x] The initial testing guide documents implemented configuration/selection behavior and links the retained catalog. Verification evidence records actual commands and limits without claiming native execution from host tests.

## Blocked by

None. Matching packaged directory provenance and local implementation inputs are verified. Legacy all-files failures have the bounded user-approved disposition above; every generated file passes configured hooks. Native prerequisites and permission checks remain owned by the dependent tickets.
