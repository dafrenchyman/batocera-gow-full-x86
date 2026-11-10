# Research: runtime Python dependencies

## Question

Does the existing runtime use third-party Python libraries, can needed dependencies be added without altering stock Batocera files, and does dependency-injector require a host-only exception? The user also requires the project to use Batocera's Python version.

## Context

Owner: [repository maturation exploration](../explore.md#standards-hooks-and-secret-prevention). Related decisions: [source layout](../explore.md#single-project-source-layout) and [Batocera-led Python version](../explore.md#batocera-led-python-version). The proposed host-only dependency-injector restriction was not accepted. Stock Batocera, Wolf and GoW files must remain intact.

## Method

Inspected current runtime imports, including imports inside functions and the adapter's in-process execution of stock hotkeygen. Queried retained stock filesystem metadata, builder package metadata and release provenance. Read official Batocera/Buildroot package declarations and upstream dependency-injector release/distribution documentation. No package installation, application execution, image build/import, SSH operation or test ran.

The general archive reader rejected the retained 15.6 GB stock-root tar because it exceeds its 256 MB memory limit. A read-only Python tarfile inspection instead sought the known sysconfig member, parsed its assignment using ast.literal_eval and printed selected build values. It did not execute the member or extract files. This establishes static interpreter build metadata, not a fresh runtime sys.version result.

## Evidence

### Current code and actual retained stock contents

- experiments/gow-full-x86/runtime/emulator_probe.py imports Pillow as PIL.Image inside Desktop.screenshot and pyudev when inspecting the final keyboard. These are third-party Python libraries, not standard-library modules.
- experiments/gow-full-x86/runtime/transport_probe.py imports evdev inside Probe.setup for real input-device creation and observation.
- experiments/gow-full-x86/runtime/runtime.py uses runpy.run_path on stock hotkeygen in run_hotkeys. Its top-level imports do not describe all Python dependencies executed by the session.
- The core adapter/input modules directly import standard-library and project-local modules. Native X11/XTEST/libc access through ctypes is also a system-library dependency, although ctypes itself is standard library. Do not describe this as a dependency-free runtime.
- output/gow-full-x86/stock-manifest.json lists /usr/bin/python3.12, /usr/lib/python3.12/site-packages and the following installed distribution metadata: pillow-11.0.0, evdev-1.7.1, pyudev-0.24.3, PyYAML-6.0.2, requests-2.32.3 and typing_extensions-4.15.0. It also lists configgen and evmapy. These are observed stock inventory paths, not merely optional package definitions.
- Querying all retained stock paths for dependency_injector or dependency-injector returned no entries. It is not present under those names in this retained inventory; this is not a universal claim about every Batocera release.
- output/gow-full-x86/assembly/assembly-manifest.json identifies release 43.1 and upstream revision 155c2d8d304cbb53db52e9479dcf683392821d5c.
- Static inspection of usr/lib/python3.12/_sysconfigdata__linux_x86_64-linux-gnu.py in output/gow-full-x86/assembly/stock-root.tar yielded VERSION=3.12, LDVERSION=3.12, SOABI=cpython-312-x86_64-linux-gnu, SIZEOF_VOID_P=8 and HOST_GNU_TYPE=x86_64-buildroot-linux-gnu. This member did not establish the Python patch version. The stock inventory also contains /lib/libc.so.6; its path alone does not establish the glibc version.

### Official Batocera Python and package declarations

The [43.1 source tag](https://api.github.com/repos/batocera-linux/batocera.linux/git/ref/tags/batocera-43.1) identifies the same Batocera revision as the retained assembly. Its [Buildroot submodule](https://api.github.com/repos/batocera-linux/batocera.linux/contents/buildroot?ref=155c2d8d304cbb53db52e9479dcf683392821d5c) pins revision 2ef23189ecd626c334e071230e5cbe102b8c41f5. That revision's [python3.mk](https://github.com/batocera-linux/buildroot/blob/2ef23189ecd626c334e071230e5cbe102b8c41f5/package/python3/python3.mk#L7-L10) declares Python 3.12.8. This establishes the source-defined full version for the current baseline, not a newly executed interpreter version.

Stock components explicitly use third-party Python libraries. [Configgen's project metadata](https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/core/batocera-configgen/configgen/pyproject.toml) declares PyYAML, toml, evdev, pyudev, configobj, ffmpeg-python, Pillow, ruamel.yaml, requests, qrcode and pysdl2. [Hotkeygen](https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/utils/hotkeygen/hotkeygen.py) imports evdev and pyudev. [Evmapy's package configuration](https://github.com/batocera-linux/batocera.linux/blob/155c2d8d304cbb53db52e9479dcf683392821d5c/package/batocera/utils/evmapy/Config.in) selects evdev. These declarations corroborate, but do not replace, the retained installed-file evidence.

The pinned Python recipe configures --without-ensurepip. Do not assume a stock pip development environment; private build-time staging avoids needing one in the runtime.

The retained output/gow-full-x86/builder-manifest.json reports Debian Python 3.13.5 packages. The existing builder therefore does not already match the stock Python minor. The interpreter plan must account for project-owned builder execution as well as host development, without replacing an unrelated OS system interpreter or treating a builder import as runtime compatibility proof.

### dependency-injector distribution

The inspected release is 4.49.1. It is evidence for feasibility, not an accepted project dependency pin.

- [Tagged pyproject.toml](https://github.com/ets-labs/python-dependency-injector/blob/4.49.1/pyproject.toml) declares Python >=3.8, Python 3.12 support and typing-extensions for Python <3.13. Optional YAML/Pydantic/framework integrations add dependencies only when selected. Basic providers/containers do not require all those extras.
- [Installation documentation](https://python-dependency-injector.ets-labs.org/introduction/installation.html) and [tagged setup.py](https://github.com/ets-labs/python-dependency-injector/blob/4.49.1/setup.py) establish compiled Cython extensions. Copying ordinary .py files alone is insufficient. Source compilation requires a toolchain; loading a suitable prebuilt wheel does not require a runtime compiler.
- [Versioned PyPI metadata](https://pypi.org/pypi/dependency-injector/4.49.1/json) publishes dependency_injector-4.49.1-cp310-abi3-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl, SHA-256 10e481880b307a6a438c1cc7b0a1fa8754247239ef5a2e8fe82bd8a1e76e7682. This is a candidate for the observed CPython 3.12 x86_64 glibc environment, not a tested import.
- Upstream's build script selects the CPython 3.10 Limited API for this wheel. cp310-abi3 does not restrict it to Python 3.10. [CPython stable ABI documentation](https://docs.python.org/3/c-api/stable.html) also explains why Python version alone is not a complete native compatibility guarantee.
- [PyPA platform tags](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/) describe interpreter/ABI/platform matching. Dot-separated wheel platform tags are alternatives; do not interpret the candidate filename as requiring every listed glibc baseline. Native loader dependencies and the actual image remain to be checked.
- [Tagged license](https://github.com/ets-labs/python-dependency-injector/blob/4.49.1/LICENSE.rst) is BSD 3-clause. Preserve its notices and those of any other redistributed dependencies.

### Additive private packaging

[INFERENCE] A private dependency tree under the project's existing owned /opt subtree can preserve stock files. [Pip's target option](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-t) supports directory-targeted installation; [Python sys.path](https://docs.python.org/3/library/sys.html#sys.path) permits process-local import-path selection. Neither requires replacing stock site-packages or changing Wolf.

Prefer resolving and staging pinned, hashed compatible wheels during image assembly. Ship the resulting files in the image, retaining metadata/licenses and including them in provenance/security inventories. Runtime should not fetch packages or mutate itself. Keep uv as project dependency authority; a separate runtime artifact selection must agree with the project's declared target and lock rather than become an independent floating dependency graph. [Pip hash checking](https://pip.pypa.io/en/stable/topics/secure-installs/) and [target-aware downloads](https://pip.pypa.io/en/stable/cli/pip_download/) describe relevant artifact controls. Exact integration into this project's build remains a design task.

A private directory is process-local visibility, not per-module isolation. Stock code loaded with runpy shares sys.path and sys.modules with the adapter. Blindly prepending private dependencies can shadow stock packages; blindly appending can select an unpinned stock copy instead. The retained image already supplies typing_extensions, making this a concrete overlap for the inspected dependency-injector release. Define the intended origin/version for overlapping imports and keep stock-launched processes free of global path changes. Do not install .pth/sitecustomize into stock directories or export a global PYTHONPATH.

### NixOS and patch-level compatibility

The user reports NixOS with Python 3.12.12 already installed. Treat that as supplied environment evidence, not something to rerun for confirmation. These findings came from primary documentation, not a package install, local interpreter check or environment smoke test.

[CPython 3.12's C API stability documentation](https://docs.python.org/3.12/c-api/stable.html) states that the public ABI is forward/backward compatible within a minor release when compiled the same way. Private APIs can change even in patch releases. This supports considering 3.12.12 a reasonable host-development interpreter for 3.12-targeted code; it does not make NixOS and Batocera interchangeable environments or prove every package compatible. Native dependencies, build flags, system libraries and actual runtime behavior still need their own checks. Never copy a Nix host virtualenv or native extensions into Batocera as a compatibility shortcut.

[Nixpkgs' uv guidance](https://github.com/NixOS/nixpkgs/blob/master/doc/packages/uv.section.md) warns that uv's generic dynamically linked interpreter downloads do not run on unconfigured NixOS. It prefers explicitly providing a Nix interpreter with UV_PYTHON and setting UV_PYTHON_DOWNLOADS=never. Enabling nix-ld is an alternative, but the project must not assume it is enabled or require an unapproved host change. The [official NixOS quickstart](https://wiki.nixos.org/wiki/Python_quickstart_using_uv) documents that alternative and confirms that a global Python install is not inherently required when managed Python can run.

uv can use a supplied interpreter by path, as documented in its [Python selection rules](https://docs.astral.sh/uv/concepts/python-versions/#requesting-a-version). A Nix project shell may supply Python and uv without changing the OS Python or introducing a second Python dependency graph. Generic PyPI native libraries can have additional NixOS loader requirements; neither selecting the interpreter nor matching a Python minor proves all dependency imports.

## Findings

The runtime is not standard-library-only. Existing probes directly consume stock third-party Python packages, and normal startup invokes stock Python components. Third-party dependencies are not inherently incompatible with preserving Batocera.

[INFERENCE] Adding an available pure-Python wheel is ordinary build packaging. A compatible prebuilt native wheel can also be staged without changing stock files, but interpreter/architecture/libc checks and a real-image import are necessary. A source-only package needing new native system libraries is a larger build task. These cases must not be described as equally easy.

For dependency-injector, a plausible prebuilt wheel exists for the observed target. Compatibility and correct package-origin handling are not proven. The user considered this feasibility evidence and selected no dependency-injector in the Batocera runtime, judging the added packaging/compatibility risk unnecessary for this cleanup. This is a design choice, not a finding that runtime installation is impossible.

## Dead ends and failures

Do not infer all executed imports from module-level import statements. Do not equate keeping stock files intact with forbidding private additive libraries. Do not install into Batocera's global site-packages or use a host virtualenv as proof of image compatibility. The archive reader's size limit was bypassed by static read-only member inspection, not by executing extracted code.

## Reusable artifacts

Current runtime/probe files, stock-manifest.json, assembly/assembly-manifest.json and the stock-root tar above provide concrete import/inventory/ABI evidence. Upstream versioned package metadata provides candidate artifact identities. No test scaffold or generated image was created.

## Decision impact

The accepted policy permits dependency-injector only in code outside Batocera and excludes it from runtime/final-image staging. Explicit configured-dependency injection and deterministic resource ownership apply everywhere, without requiring the library. The user's constructor-injection example is preserved in [the owning decision](../explore.md#dependency-injection-boundary). No blanket standard-library-only rule was accepted; existing stock libraries remain valid. Keep the stdlib-only SSH helper's delivery contract distinct.

The user accepted host patch differences within the stock major/minor version, so the reported NixOS Python 3.12.12 satisfies the planned host 3.12.x version policy. The default full-version pin and builder project interpreter remain aligned to confirmed stock; pinned source currently defines 3.12.8, pending a future authorized runtime-version check. Native tests use actual stock Python. Host tolerance does not establish dependency or native-extension compatibility, and the builder's unrelated 3.13.5 interpreter is not an aligned project interpreter. Review this contract on Batocera upgrades.

For interpreter supply, [uv's Python-version documentation](https://docs.astral.sh/uv/concepts/python-versions/) supports exact version requests, .python-version pins and managed interpreter downloads separate from system installations. Downloadable versions are fixed per uv release. This establishes the mechanism, not availability or execution of a selected build on this host/builder. No interpreter was installed or run during research.

The accepted supply policy uses Nix-provided 3.12.x on NixOS, explicitly selected for uv-managed environments/dependencies with managed interpreter downloads disabled there. uv provisions the builder interpreter separately, using the confirmed stock full version before networkless assembly. Exact host patch matching was not selected. Keep unrelated OS interpreters and Batocera's interpreter untouched, and exclude host environments/native extensions and uv development tooling from the final runtime.

## Follow-up questions

The host patch/provider policy is resolved. Remaining research/implementation prerequisites include confirming stock's full runtime version, selecting available pinned builder interpreter artifacts, preparing them before networkless assembly and verifying needed native dependency imports. None was installed or executed here. Keep the accepted runtime dependency-injector exclusion and explicit configured-dependency injection contract unchanged.
