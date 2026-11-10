# Tooling compatibility

Runtime and hook candidates were checked against upstream source and registry metadata. The runtime evidence below distinguishes executed checks from source-only compatibility findings.

## Recommended runtime choices

Choose Python 3.12, Node 24, and stable Nixpkgs 26.05. This keeps the workstation's observed Python minor and Node major, while using an explicit stable shell selection. Allow Python patches and Node minor/patch updates, but constrain project declarations to `>=3.12,<3.13` and `>=24 <25`. Align Ruff `py312`, mypy `3.12`, hook interpreter selection, `.python-version`, and the shell's `python312`.

| Choice        | Source observation                                                                                                                  | Primary source                                                                                                                                                                                       |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python 3.12   | Security support through October 2028. Stable snapshot has 3.12.14. Workstation has 3.12.12.                                        | https://devguide.python.org/versions/ and https://raw.githubusercontent.com/NixOS/nixpkgs/6fcc160353f63555b560f25588925133c8f61f2a/pkgs/development/interpreters/python/default.nix                  |
| Node 24       | LTS since 2025-10-28, maintenance starts 2026-10-20, support ends 2028-04-30. Stable snapshot has 24.21.0. Workstation has 24.11.1. | https://raw.githubusercontent.com/nodejs/Release/main/schedule.json and https://raw.githubusercontent.com/NixOS/nixpkgs/6fcc160353f63555b560f25588925133c8f61f2a/pkgs/development/web/nodejs/v24.nix |
| Nixpkgs 26.05 | Official download page names 26.05 as current. Channel revision endpoint returned `6fcc160353f63555b560f25588925133c8f61f2a`.       | https://nixos.org/download/ and https://channels.nixos.org/nixos-26.05/git-revision                                                                                                                  |

Use `github:NixOS/nixpkgs/nixos-26.05` as the declared input and lock its resolved revision. The source revision above is a verified candidate, not a generated flake lock or a tested shell.

Other source-available interpreters at that revision are Python 3.11.16, 3.13.15, 3.14.7, and 3.15.0. Python 3.14 remains a supported upgrade option, but choosing it now would need a new workstation interpreter and separate runtime proofs. Python 3.10 is already end-of-life. Node 22.23.3 is available and supported until 2027-04-30, but has a shorter support runway. Node 26.11.1 is available, yet is not LTS until 2026-10-28. Do not select Node 26 merely because Nixpkgs has it.

## Stable shell package versions

Read these values from package definitions at the pinned revision. They establish source availability, not substitutes, successful builds, or runtime compatibility.

| Attribute    | Source version                                                             | Definition                                                                                                                                |
| ------------ | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `python312`  | 3.12.14                                                                    | https://raw.githubusercontent.com/NixOS/nixpkgs/6fcc160353f63555b560f25588925133c8f61f2a/pkgs/development/interpreters/python/default.nix |
| `nodejs_24`  | 24.21.0                                                                    | https://raw.githubusercontent.com/NixOS/nixpkgs/6fcc160353f63555b560f25588925133c8f61f2a/pkgs/development/web/nodejs/v24.nix              |
| `uv`         | 0.11.21                                                                    | https://raw.githubusercontent.com/NixOS/nixpkgs/6fcc160353f63555b560f25588925133c8f61f2a/pkgs/by-name/uv/uv/package.nix                   |
| `pre-commit` | 4.5.1                                                                      | https://raw.githubusercontent.com/NixOS/nixpkgs/6fcc160353f63555b560f25588925133c8f61f2a/pkgs/by-name/pr/pre-commit/package.nix           |
| `alejandra`  | 4.0.0                                                                      | https://raw.githubusercontent.com/NixOS/nixpkgs/6fcc160353f63555b560f25588925133c8f61f2a/pkgs/by-name/al/alejandra/package.nix            |
| `deadnix`    | 1.3.2                                                                      | https://raw.githubusercontent.com/NixOS/nixpkgs/6fcc160353f63555b560f25588925133c8f61f2a/pkgs/by-name/de/deadnix/package.nix              |
| `statix`     | `0-unstable-2026-05-14`, source `f0d256d60d9b9736b274a0edc0492be472318166` | https://raw.githubusercontent.com/NixOS/nixpkgs/6fcc160353f63555b560f25588925133c8f61f2a/pkgs/by-name/st/statix/package.nix               |

Stable Nixpkgs ships a Statix development snapshot. Its Cargo manifest says `0.6.0`. Neither fact means the flake uses an unstable Nixpkgs input. Report the package source honestly rather than relabel it a released Statix version. Source: https://raw.githubusercontent.com/molybdenumsoftware/statix/f0d256d60d9b9736b274a0edc0492be472318166/bin/Cargo.toml.

npm is provided with the selected Node package. The bundled npm version was not established from source in this investigation. Workstation has npm 11.6.2 system-wide. Record the actual shell npm version during shell proof rather than invent an exact bundled value.

## Python development dependencies

These exact candidate releases satisfy Python 3.12 according to PyPI metadata. Use pre-commit 4.5.1 rather than latest 4.7.0 if matching the stable shell version is useful.

| Package pin              | Declared Python requirement                            | Primary source                              |
| ------------------------ | ------------------------------------------------------ | ------------------------------------------- |
| `ruff==0.17.0`           | `>=3.7`                                                | https://pypi.org/pypi/ruff/0.17.0/json      |
| `mypy==2.4.0`            | `>=3.10`                                               | https://pypi.org/pypi/mypy/2.4.0/json       |
| `pytest==9.1.1`          | `>=3.10`                                               | https://pypi.org/pypi/pytest/9.1.1/json     |
| `pytest-cov==7.1.0`      | `>=3.9`, requires pytest `>=7` and coverage `>=7.10.6` | https://pypi.org/pypi/pytest-cov/7.1.0/json |
| `coverage[toml]==7.16.2` | `>=3.10`                                               | https://pypi.org/pypi/coverage/7.16.2/json  |
| `pre-commit==4.5.1`      | `>=3.10`                                               | https://pypi.org/pypi/pre-commit/4.5.1/json |

PyPI lists x86_64 Linux wheels for Ruff, mypy on CPython 3.12, and coverage on CPython 3.12. This does not prove loading them on NixOS. Installation and diagnostics are reported below; final baseline verification remains required. Lock all transitive dependencies with uv.

uv documents that omitting a build system prevents project installation, and `tool.uv.package = false` explicitly disables it. A tooling-only root manifest can use those settings without starter source or a build backend. Source: https://docs.astral.sh/uv/concepts/projects/config/.

## Verified remote hook revisions

Resolved upstream Git tag refs through first-party repository Git APIs and peeled annotated tags where present. Inspected the hook manifests and the Python mirrors' package pins at these exact commits. This is a limited source review, not a security certification.

| Repository                  | Release   | Verified commit                            | Relevant hooks                                                                                            |
| --------------------------- | --------- | ------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| `astral-sh/ruff-pre-commit` | `v0.17.0` | `44b5042edab9382aba712eed4f9c7bab7a3d6a3e` | `ruff-check`, `ruff-format`                                                                               |
| `pre-commit/mirrors-mypy`   | `v2.4.0`  | `2834ec6639549dd6796205c8f011dedcd587288b` | `mypy`                                                                                                    |
| `kamadorueda/alejandra`     | `4.0.0`   | `3e2a85506627062313e131bf8a85315f3387c8e0` | `alejandra`, `alejandra-nix`, `alejandra-system`                                                          |
| `astro/deadnix`             | `v1.3.2`  | `ba988ddf46f1e57abe3dfacbfbd17fec5a7276d9` | `deadnix`                                                                                                 |
| `molybdenumsoftware/statix` | `v0.5.8`  | `d324490e45bcda1b664f28b6f88da8580deda76b` | No pre-commit manifest in the returned complete tree. This is not a usable upstream remote hook revision. |

Sources for exact revisions and entry points:

- https://api.github.com/repos/astral-sh/ruff-pre-commit/git/ref/tags/v0.17.0
- https://raw.githubusercontent.com/astral-sh/ruff-pre-commit/44b5042edab9382aba712eed4f9c7bab7a3d6a3e/.pre-commit-hooks.yaml
- https://raw.githubusercontent.com/astral-sh/ruff-pre-commit/44b5042edab9382aba712eed4f9c7bab7a3d6a3e/pyproject.toml
- https://api.github.com/repos/pre-commit/mirrors-mypy/git/ref/tags/v2.4.0
- https://raw.githubusercontent.com/pre-commit/mirrors-mypy/2834ec6639549dd6796205c8f011dedcd587288b/.pre-commit-hooks.yaml
- https://raw.githubusercontent.com/pre-commit/mirrors-mypy/2834ec6639549dd6796205c8f011dedcd587288b/setup.py
- https://api.github.com/repos/kamadorueda/alejandra/git/ref/tags/4.0.0
- https://raw.githubusercontent.com/kamadorueda/alejandra/3e2a85506627062313e131bf8a85315f3387c8e0/.pre-commit-hooks.yaml
- https://api.github.com/repos/astro/deadnix/git/ref/tags/v1.3.2
- https://raw.githubusercontent.com/astro/deadnix/ba988ddf46f1e57abe3dfacbfbd17fec5a7276d9/.pre-commit-hooks.yaml
- https://api.github.com/repos/molybdenumsoftware/statix/git/ref/tags/v0.5.8
- https://api.github.com/repos/molybdenumsoftware/statix/git/trees/d324490e45bcda1b664f28b6f88da8580deda76b?recursive=1

Ruff's pinned metadata installs exactly 0.17.0. Select the nonlegacy `ruff-check` ID, supply `--fix`, then run `ruff-format`. Restrict the formatter hook to Python and stubs because the upstream manifest now also includes Markdown. That prevents accidental overlap with the approved Prettier document hook. Keep unsafe fixes and preview off. Formatter-conflicting exclusions still need to follow https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules.

The mypy mirror installs exactly 2.4.0, but its default arguments include `--ignore-missing-imports`. Replace those defaults. Keep supplied filenames as targets and point `--python-executable` at the project environment's Python so third-party dependencies/stubs remain visible without duplicating them into the hook environment. The mypy documentation explicitly supports that interpreter selection: https://mypy.readthedocs.io/en/stable/running_mypy.html. The source-backed design still needs real typed-dependency and untyped-import proofs.

Alejandra's `alejandra-system` is a suitable remote hook candidate when 4.0.0 is supplied system-wide or by the stable shell. It directly executes `alejandra` and defaults to `-q`. Its manifest does not enforce the installed version. The `alejandra` hook uses Rust and needs a Rust installation path; the optional baseline shell does not currently promise Rust. Avoid `alejandra-nix`: its script uses `nix-build` against a mutable release-tag tarball and creates `result-alejandra`. Source: https://raw.githubusercontent.com/kamadorueda/alejandra/3e2a85506627062313e131bf8a85315f3387c8e0/.pre-commit-entry.sh.

Deadnix's remote hook uses Rust, executes `deadnix`, and defaults to `--fail`. It is a valid upstream candidate, but Rust provisioning and NixOS installation remain unproved. A deliberate local system hook supplied by the locked shell avoids that additional install path. Keep `--fail`, never `--edit`. Source: https://raw.githubusercontent.com/astro/deadnix/ba988ddf46f1e57abe3dfacbfbd17fec5a7276d9/README.md.

Statix has no native remote hook at the inspected release or stable snapshot. A justified local system hook is consistent with the spec's preference for suitable remote hooks. Its `check` subcommand has one `PathBuf` target, not a filename vector. Invoke it once per supplied filename, preserve failure from any invocation, and do not substitute a whole-project `.` invocation. Source: https://raw.githubusercontent.com/molybdenumsoftware/statix/f0d256d60d9b9736b274a0edc0492be472318166/bin/src/config.rs. Runtime proof must verify nonzero failure on a genuine lint finding.

Retain the existing Prettier assessment without expanding its assurance: `rbubley/mirrors-prettier` commit `331f33fa4dfbcbca7c3da3620c137fde0faab273`, Prettier 3.9.10, plugin-free. Plugin-resolution experiments were not repeated; combined lint/format stability is recorded below.

## Frontend package choices and maintenance gap

There is a real maintenance conflict. The latest ESLint is 10.12.0, but official `eslint-plugin-jsx-a11y` 6.10.2 only declares peers through ESLint 9. The registry inventory has no published prereleases, only `latest=6.10.2` and `v5-backport=5.1.1`, and no newer release with an ESLint 10 peer range. Current upstream main also ends at ESLint 9.

ESLint 9.39.5 is peer-compatible, but upstream ended maintenance on 2026-08-06 and npm marks the package deprecated. The temporary baseline retains that version with an explicit end-of-life exception. Reassess the exception during dependency updates and migrate when a reviewed maintained integration preserves the required checks. Do not describe ESLint 9 as supported or use peer overrides to conceal the conflict.

Primary sources:

- https://eslint.org/version-support/
- https://registry.npmjs.org/eslint/9.39.5
- https://registry.npmjs.org/eslint-plugin-jsx-a11y
- https://raw.githubusercontent.com/jsx-eslint/eslint-plugin-jsx-a11y/main/package.json

The following exact candidate versions have mutually compatible declared direct peers and Node engines, subject to that ESLint EOL limitation. This is a source-based compatibility inference, not an installed or exercised dependency graph.

| Package                       | Exact candidate | Primary metadata                                                |
| ----------------------------- | --------------- | --------------------------------------------------------------- |
| `eslint`                      | 9.39.5          | https://registry.npmjs.org/eslint/9.39.5                        |
| `@eslint/js`                  | 9.39.5          | https://registry.npmjs.org/@eslint%2Fjs/9.39.5                  |
| `typescript`                  | 5.9.3           | https://registry.npmjs.org/typescript/5.9.3                     |
| `typescript-eslint`           | 8.71.2          | https://registry.npmjs.org/typescript-eslint/8.71.2             |
| `eslint-plugin-react-hooks`   | 7.1.1           | https://registry.npmjs.org/eslint-plugin-react-hooks/7.1.1      |
| `eslint-plugin-jsx-a11y`      | 6.10.2          | https://registry.npmjs.org/eslint-plugin-jsx-a11y/6.10.2        |
| `eslint-config-prettier`      | 10.1.8          | https://registry.npmjs.org/eslint-config-prettier/10.1.8        |
| `prettier`                    | 3.9.10          | https://registry.npmjs.org/prettier/3.9.10                      |
| `react`                       | 19.3.0          | https://registry.npmjs.org/react/19.3.0                         |
| `react-dom`                   | 19.3.0          | https://registry.npmjs.org/react-dom/19.3.0                     |
| `@types/react`                | 19.3.0          | https://registry.npmjs.org/@types%2Freact/19.3.0                |
| `@types/react-dom`            | 19.3.0          | https://registry.npmjs.org/@types%2Freact-dom/19.3.0            |
| `@types/node`                 | 24.19.2         | https://registry.npmjs.org/@types%2Fnode/24.19.2                |
| `vitest`                      | 5.0.4           | https://registry.npmjs.org/vitest/5.0.4                         |
| `@vitest/coverage-v8`         | 5.0.4           | https://registry.npmjs.org/@vitest%2Fcoverage-v8/5.0.4          |
| `vite`                        | 8.3.4           | https://registry.npmjs.org/vite/8.3.4                           |
| `@testing-library/react`      | 16.3.3          | https://registry.npmjs.org/@testing-library%2Freact/16.3.3      |
| `@testing-library/dom`        | 10.4.2          | https://registry.npmjs.org/@testing-library%2Fdom/10.4.2        |
| `@testing-library/jest-dom`   | 7.0.1           | https://registry.npmjs.org/@testing-library%2Fjest-dom/7.0.1    |
| `@testing-library/user-event` | 14.6.7          | https://registry.npmjs.org/@testing-library%2Fuser-event/14.6.7 |
| `jsdom`                       | 27.4.0          | https://registry.npmjs.org/jsdom/27.4.0                         |

Reasons these are not simply all-latest:

- TypeScript latest is 7.0.2, outside typescript-eslint 8.71.2's declared `>=4.8.4 <6.1.0`. TypeScript 5.9.3 satisfies that range. A supported 6.0.x candidate could also be investigated, but was not selected here.
- ESLint latest 10 is excluded by jsx-a11y's peer declaration, as described above.
- jsdom latest 30.1.2 requires `^22.22.2 || ^24.15.0 || >=26.0.0`. Workstation Node 24.11.1 does not meet that requirement. jsdom 27.4.0 accepts `^20.19.0 || ^22.12.0 || >=24.0.0`, so it permits both the workstation and chosen shell Node versions.
- React DOM 19.3.0 requires React `^19.3.0`; pinning both at 19.3.0 satisfies it. Matching React type versions satisfy the React DOM type peer.
- React Testing Library 16.3.3 requires React/React DOM 18 or 19 and `@testing-library/dom ^10.0.0`. Include the DOM package explicitly.
- Vitest 5.0.4 requires Node `^22.12.0 || ^24.0.0 || >=26.0.0` and Vite `^6.4.0 || ^7.0.0 || ^8.0.0`. Coverage-v8 requires exactly Vitest 5.0.4. Keep those versions equal. Vite here is a test-runner dependency, not a new framework dev/build policy.
- jest-dom 7.0.1 requires Node >=22 and DOM Testing Library >=10 <11. Node 24 and DOM 10.4.2 satisfy them.

Type-aware configuration must enable a type-checked preset and `parserOptions.projectService`. Source: https://typescript-eslint.io/getting-started/typed-linting/. The project configuration must include the intended TS/TSX inputs; explicit JS/JSX lint coverage still needs fixtures. Registry peer agreement does not prove flat-config imports, correct rule application, remote environment resolution, or meaningful diagnostics. Remote-hook proofs are recorded below.

## Gaps, failed source approaches, and trust limits

- The recursive Nixpkgs tree API response was truncated. Python/tool paths were present in the returned portion; Node paths were separately discovered through its directory API before reading exact source definitions. No absent package conclusion rests on the truncated tree.
- Ruff's current mirror has `pyproject.toml`, not `setup.py`. A request for the latter returned 404. The discovered actual metadata establishes its exact Ruff dependency.
- Statix's upstream hook-manifest URL returned 404. Its complete release and snapshot trees contain no native manifest. The returned cachix/git-hooks.nix tree likewise has no native `.pre-commit-hooks.yaml`; it cannot simply be listed as a standard remote hook repo.
- Direct peer and engine compatibility does not guarantee transitive resolution, NixOS native-module loading, CLI behavior, JS DOM behavior, or fix stability. Those remain acceptance proofs.
- Version pins and registry metadata do not certify safety, authorship, uncompromised publication, or reproducibility of every install path. No signatures, attestations, tarballs, native binaries, transitive implementation source, or installation scripts were validated here.
- Remote hooks, npm packages, project configuration, plugins, dependency installation, and Rust build dependencies execute code. None of these environments is a security sandbox.
- Remote Alejandra system execution depends on the installed binary matching the reviewed version. Rust hooks need separate Rust provisioning. Statix's stable package version differs from its source Cargo version.
- The maintained-ESLint peer conflict and latest-jsdom Node requirement are source-confirmed limitations. The chosen older compatible ESLint was exercised below, but its maintenance exception remains unresolved. Final Nix shell, test-runner, coverage, and integrated-template checks have not run.

## Executed integration evidence

Used a disposable Git repository on x86_64 Linux/NixOS. No project Git metadata, commits, branches, worktrees, application scaffolds, or activation were created. Workstation tools were Python 3.12.12, Node 24.11.1, npm 11.6.2, uv 0.7.22, Nix 2.28.5, and pre-commit 4.0.1. The uv environment also installed and exercised pre-commit 4.5.1.

### Remote ESLint and Prettier

The exact exercised npm pins were ESLint/@eslint/js 9.39.5, TypeScript 5.9.3, typescript-eslint 8.71.2, React Hooks plugin 7.1.1, jsx-a11y 6.10.2, eslint-config-prettier 10.1.8, Prettier 3.9.10, and React/@types/react 19.3.0. npm installed without peer overrides or lifecycle scripts. npm explicitly warned that ESLint 9 is unsupported.

The ESLint mirror source was commit `6b0a6fbdd14ed9625d6475c2523f325db6f6637a`, whose hook manifest normally supplies 9.39.1. Consumer `additional_dependencies: [eslint@9.39.5]` selected the exact tested executable. The inspected package manifest had placeholder metadata and no scripts/dependencies. Sources:

- https://raw.githubusercontent.com/pre-commit/mirrors-eslint/6b0a6fbdd14ed9625d6475c2523f325db6f6637a/.pre-commit-hooks.yaml
- https://raw.githubusercontent.com/pre-commit/mirrors-eslint/6b0a6fbdd14ed9625d6475c2523f325db6f6637a/package.json

Configured the remote hook with system Node, `types: [file]`, an explicit JS/JSX/TS/TSX frontend filter, and `--fix --max-warnings=0 --config web/eslint.config.mjs`. The configuration imported dependencies installed in the frontend project. It enabled type-checked TypeScript rules using the project tsconfig and an explicit configuration-relative root, Hook and accessibility rules, and eslint-config-prettier last. This resolved project plugins without duplicating them into the remote hook environment.

| Exercise                                                     | Observed outcome                                                                                                                                  |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Remote ESLint on JS, JSX, TS, TSX violations                 | Exit 1; reported no-undef, jsx-a11y/alt-text, type-aware require-await, and conditional rules-of-hooks. No intended fixture was silently ignored. |
| Automatic fixes with remaining errors                        | let became const; hook reported modified tracked files while retaining five errors and nonzero exit.                                              |
| Corrected inputs through remote ESLint and approved Prettier | First tracked run reported modifications from both hooks. Next two runs passed without further changes.                                           |
| eslint-config-prettier helper on all four input types        | Reported no unnecessary or conflicting rules. Executed from the frontend directory, where configuration discovery works.                          |
| Configured TypeScript project check                          | `npm exec -- tsc --noEmit` passed after fixture correction. This was not a staged-filename compiler invocation.                                   |

An early fixture used TS and TSX files with the same basename. TypeScript omitted the TSX file from the configured project, and type-aware ESLint correctly failed rather than silently checking it without types. Using distinct basenames fixed the fixture, not the lint rules. Passing explicit files before staging cannot demonstrate pre-commit modification detection; the final fix/stability exercises used tracked fixture files.

Commands included `uv run pre-commit run eslint --files web/src/bad.ts web/src/component.tsx web/src/bad.js web/src/bad.jsx`, the same supplied-files command without a hook ID for combined formatting, and `npm exec -- eslint-config-prettier src/component.tsx src/bad.ts src/bad.js src/bad.jsx` from the frontend directory.

### Strict mypy and dependency visibility

uv installed all proposed Python development pins into a tooling-only project with no build backend or package installation. Installed Ruff 0.17.0, mypy 2.4.0, pytest 9.1.1, pytest-cov 7.1.0, coverage 7.16.2, and pre-commit 4.5.1. Ruff/pytest/coverage version commands ran successfully; this does not claim their future baseline configuration or coverage policy has been verified.

The remote mypy mirror at `2834ec6639549dd6796205c8f011dedcd587288b` used `args: [--strict]`, replacing the mirror's blanket missing-import defaults. Project configuration enabled strict mode, Python 3.12, and `python_executable = ".venv/bin/python"`. httpx 0.28.1 and PyYAML 6.0.2 were installed only in the disposable project environment, not added to the hook environment or template baseline.

| Exercise                                                     | Observed outcome                                                                                                                                                            |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Supplied typed-error and untyped-import files                | Exit 1; exactly two source files checked. A string-to-int assignment failed with assignment; PyYAML failed with import-untyped. Typed httpx resolved without import errors. |
| One supplied file with an explained import-untyped exception | Passed with both unrelated error fixtures still present. No whole-project target or disabled filename passing was used.                                                     |
| Incorrect suppression on a typed dependency                  | Earlier pyfiglet fixture contained py.typed; strict mypy rejected its unnecessary ignore. PyYAML provided the genuine untyped case.                                         |

Commands were `uv sync --python /run/current-system/sw/bin/python3`, exact-pin `uv add --dev`, and `uv run pre-commit run mypy --files <supplied-files>`. The source docs explain project interpreter lookup: https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-python-executable.

### Remaining disposition

The remote integrations are technically feasible. Use the tested ESLint 9.39.5/official jsx-a11y combination under the temporary maintenance exception recorded in exploration and the spec. Keep the remote hook, accessibility/type-aware rules, and explicit dependency pins; do not silently use peer overrides or report ESLint 9 as maintained.

The project remains without Git metadata. Staged and all-tracked-files verification uses disposable checkouts of actual template files. No project initialization, commits, branch changes, or remote operations are needed.

Research-stage compatibility does not replace final baseline acceptance or certify package safety. Ticket 02 records actual shell, flake, runner, coverage, and all-files verification. The research fixtures were removed.

## Baseline compatibility corrections

Vitest 5.0.4 ran the rendered tests but failed configured TypeScript checking with TS2428. Its Assertion interface has two type parameters; jest-dom 7.0.1 augments the older single-parameter interface. Use Vitest and coverage-v8 4.1.11 together. The final dependency tree resolved without invalid peers, and the disposable React suite passed eight tests, strict type checking, and linting. Do not hide this mismatch with skipLibCheck or patch vendor declarations.

Coverage.py's branch-enabled fail-under combines statements and branches. Keep branch measurement and reports, but enforce the configured line floor with the coverage JSON totals through scripts/check_python_coverage.py. The actual Python fixture failed at 45% lines despite six passing tests and passed at 100% after ten meaningful application cases plus two tooling regressions. CLI regressions prove that 80% lines passes despite low branch coverage, while 70% lines fails despite high branch coverage.

The actual frontend configuration needed flattened extends before applying its configuration-relative basePath. Root-invoked remote hooks then rejected JavaScript, JSX, type-aware TypeScript, conditional Hooks, and missing image alternatives. The empty frontend profile reports no applicable application tests/coverage; adding application source without a suite fails. Vitest's independent line floor rejected 37.5% coverage with passing rendered tests and accepted 100% after parser boundaries were exercised.

Stable-shell checks ran on x86_64 Linux. All three declared Nix checks passed; aarch64 Linux is declared but was not built. The stable Statix snapshot has no --version flag, so its check/help interface and locked package source identify it. System-wide Statix 0.5.8 and deadnix 1.2.1 also exercised the check-only hooks; shell tools came from the locked stable input. Neither path activated a system.
