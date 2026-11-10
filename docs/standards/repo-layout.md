# Repository layout

Read [shared standards](general.md) when adding or reorganizing files. This standard describes the installed application layout. Source placement does not establish passing migration checks or authorize builds and remote effects.

## Directory map

Selected maintained paths and generated-data locations are shown below, not every file. Local environments, tool caches and legacy workspace remnants are omitted. Keep this map aligned with directory changes; the sections below explain ownership and safety constraints.

```text
.
|-- src/
|   `-- batocera_gow/          # Installed Python application
|       |-- host/             # Builds, publication, delivery and native coordination
|       |   `-- remote_payload/ # Checked stdlib source sent ephemerally over SSH
|       |-- builder/          # Stock userspace assembly and inventory verification
|       `-- runtime/          # Startup, input, emulator integration and probes
|-- build-assets/             # Non-Python build inputs and in-image entry points
|   |-- release.json          # Official Batocera image selection and checksum
|   |-- builder.Dockerfile    # Isolated builder environment
|   |-- bridge.nix            # Runtime package closure
|   `-- runtime/              # Launchers, ALSA config and stock-facing integration
|       `-- emulator-wrappers/ # Project-owned emulator launch wrappers
|-- tests/
|   |-- README.md             # Test prerequisites, selection and operator commands
|   |-- unit/                 # Isolated host, builder and runtime tests
|   |-- integration/
|   |   |-- local/            # Local-safe filesystem and process tests
|   |   |-- builder/          # Image and container build tests
|   |   |-- runtime/          # Packaged stock-runtime tests
|   |   `-- wolf/             # Explicitly authorized live-Wolf tests
|   `-- assets/               # Maintained input and media-selection fixtures
|-- scripts/                 # Repository tooling, including the line-coverage gate
|-- docs/
|   |-- standards/            # Engineering and repository policy
|   |-- current/              # Present behavior, operations and tooling
|   |-- adr/                  # Architectural decision records
|   |-- active/               # Active specs and epics, as defined by the lifecycle
|   `-- completed/            # Completed planning and delivery records
|-- .agents/
|   `-- skills/               # Reusable agent workflows and shared references
|-- output/                  # Generated builds, manifests and diagnostic reports
|-- cache/                   # Downloaded build inputs and reusable caches
|-- README.md                # Project entry point and operations
|-- GLOSSARY.md              # Domain terminology
|-- pyproject.toml           # Package, dependencies, entry points and Python checks
|-- uv.lock                  # Locked Python dependency resolution
`-- example.env              # Example operator settings, without private values
```

## Installed application

One project, declared by root `pyproject.toml` and `uv.lock`, installs `batocera_gow` from `src/batocera_gow/`. Its `host` package owns build, publication, registration, SSH delivery and native coordination. `builder` owns assembly and inventory. `runtime` owns additive startup, input, emulator integration and probes. Checked stdlib remote source lives under `host/remote_payload/`; it is delivered ephemerally, not installed persistently on the server.

Non-Python inputs live in `build-assets/`. Keep `release.json`, `builder.Dockerfile` and `bridge.nix` there, and audio configuration and shell launchers in `build-assets/runtime/`. Consumers resolve assets from the selected project/build-input root, not adjacency to Python modules. Install the package for development and tests instead of adding source directories to `sys.path`.

Keep execution boundaries explicit. Host parsers and development tools do not become builder or Batocera dependencies. The builder uses its isolated stock-aligned project interpreter. The final Batocera image receives the runtime package and selected assets beneath `/opt/gow-full-x86`, as mapped below. Stable in-image launchers invoke that implementation; they are not experiment-layout compatibility aliases.

### Final Batocera image

The final image does not contain the whole `src/` tree or a project virtualenv. [Runtime staging](../../src/batocera_gow/host/build.py) copies the following into `output/gow-full-x86/runtime/`. [Root packaging](../../src/batocera_gow/builder/assemble.py) then installs that staging tree at `/opt/gow-full-x86/`.

| Repository or generated input                   | Final image destination                      | What is included                                                                                                                             |
| ----------------------------------------------- | -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/batocera_gow/__init__.py`                  | `/opt/gow-full-x86/batocera_gow/__init__.py` | Top-level package marker                                                                                                                     |
| `src/batocera_gow/runtime/`                     | `/opt/gow-full-x86/batocera_gow/runtime/`    | The entire runtime package, excluding `__pycache__` and `*.pyc`, not a per-module allowlist                                                  |
| `build-assets/runtime/`                         | `/opt/gow-full-x86/`                         | Entire asset tree with relative paths preserved, including shell and Python launchers, `alsa.conf`, the ES override and `emulator-wrappers/` |
| Regular files directly in `tests/assets/input/` | `/opt/gow-full-x86/<filename>`               | Suite controller definition and ES input template, currently `suite-gamepad.json` and `suite-es-input.cfg`                                   |
| Generated `output/gow-full-x86/bridge.env`      | `/opt/gow-full-x86/bridge.env`               | Exact executable and driver paths for the Nix runtime closure                                                                                |
| Assembled `stock-share.tar`                     | `/opt/gow-full-x86/stock-share.tar`          | Complete stock SHARE seed, retained as an archive until runtime initialization                                                               |
| Generated Nix closure archive                   | `/nix/store/...`                             | Realized packages and their transitive runtime dependencies, selected through `build-assets/bridge.nix`                                      |

For example, `build-assets/runtime/entrypoint.sh` becomes `/opt/gow-full-x86/entrypoint.sh`, while `build-assets/runtime/emulator-wrappers/duckstation-qt` becomes `/opt/gow-full-x86/emulator-wrappers/duckstation-qt`. The thin `.py` launchers beside them invoke the staged package using stock Python, without replacing stock Python packages.

`src/batocera_gow/host/`, `src/batocera_gow/builder/` and `src/batocera_gow/provenance.py` are not staged into the final image. Neither are the test suites, `tests/assets/media/`, repository scripts, manifests, lockfile, development dependencies or private environment settings. `build-assets/release.json`, `builder.Dockerfile` and `bridge.nix` control the build; those files are not themselves installed into the final image.

The separate Debian builder image does copy all of `src/` into `/opt/project-source/src/` and installs the project into its own virtualenvs. That is a build environment, not a layer inherited by the final Batocera image. The final root starts from complete stock Batocera userspace and boot files, then adds the project runtime and Nix closure. See [the build flow](../../README.md#local-image-build).

Persistent userdata is separate from packaged code. At runtime, `/userdata` points to `/home/retro/userdata` in the Wolf-owned home. The SHARE archive seeds initialization there; it is not unpacked over `/userdata` during image construction. Follow [runtime operations](../../README.md#runtime-flow-on-wolf) for startup and persistence.

### Portable roots and owned destinations

Host commands accept `--project-root`, defaulting to the invocation's working directory. The selected independent checkout supplies declared build inputs and private Git metadata. No fixed checkout path or original Batocera checkout is required. Keep resolved-path containment, ancestor/root refusal, symlink-escape protection and Git-metadata protection. Remote writes also require an explicitly configured owned destination and on-host canonicalization and ownership checks immediately before mutation.

Generated build data belongs under `output/` and caches under `cache/`. Preserve upstream checkouts, operator content, deployed registry/app/runner/home identities and persistent state outside owned disposable destinations. Portable source roots do not authorize state migration.

The shared `batocera_gow.provenance` definition covers `src/`, `build-assets/`, `tests/assets/`, `pyproject.toml`, `uv.lock`, `.python-version` and `.dockerignore`, including file contents and file/directory modes. Preserve complete input/cache fingerprints and source-change refusal when moving callers or resources. Bytecode and generated output are not maintained inputs. Old manifests cannot be relabeled as evidence for the moved tree. Keep Docker build contexts restricted by `.dockerignore` and builder `/project` mounts limited to declared read-only inputs, rather than exposing the entire checkout or private dotenv/Git state.

### Test organization

Root `tests/unit/` covers isolated logic, with host/builder/runtime groups. `tests/integration/` uses `local`, `builder`, `runtime` and `wolf` subtrees to make real filesystem/process, image/container, stock-runtime and live-server prerequisites visible. Running on the host does not make a filesystem/process integration test a unit test.

Keep live-Wolf cases and their thin fixture adapters in `tests/integration/wolf/`, with native shared setup in its `conftest.py`. Reusable image preparation, native lifecycle, assertions and reporting belong in maintained application modules, not a large test helper or duplicated coordinator. Shared image preparation is session-scoped; owned lobbies, homes, input and cleanup are case-scoped.

Ordinary root pytest runs are local-safe. Builder, packaged-runtime and real-Wolf suites require separate deliberate selection; native selection also requires explicit target/resource authorization. Collection and imports remain side-effect free and require no server credentials. The test runner does not build images implicitly. Native image-backed tests fail setup when an explicit build is missing, stale or unverified.

Root `pyproject.toml` selects unit and local integration tests by default. The [testing guide](../../tests/README.md) owns selection commands, shared configuration, expected writes, cleanup and full-gate versus selected-case reporting. Historical reports retain their original source/image bindings and do not qualify the installed cutover.

## Nix

The runtime package selection is [bridge.nix](../../build-assets/bridge.nix), consumed by [host build orchestration](../../src/batocera_gow/host/build.py). Apply the [Nix standard](nix-nixos.md) to expressions and closure changes. There is no required root flake or managed NixOS host. An optional development flake cannot replace the runtime closure.

## Documentation and planning

Keep standards in `docs/standards/`, qualifying architectural decisions in `docs/adr/`, and current behavior in `docs/current/`. The [lifecycle reference](../../.agents/skills/_shared/lifecycle.md) owns planning paths, states and whole-folder moves. The [original full-x86 workspace](../completed/specs/gow-full-x86/spec.md) retains its legacy ledger and historical evidence under the single `docs/` root.

Use root `GLOSSARY.md` for domain definitions once established. Domain-modeling owns terminology and qualifying ADRs. Do not duplicate lifecycle policy or create a second execution ledger here.

## Agent guidance

Keep reusable skills in `.agents/skills/`. Root `AGENTS.md` supplies project scope and conditional routing. Detailed policy remains in standards and existing workflow owners; dependency pins and runnable commands belong in actual configuration.
