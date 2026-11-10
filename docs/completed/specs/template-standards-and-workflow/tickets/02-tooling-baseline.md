# 02: Build the working tooling baseline

**Status:** Done

## Parent

[Template standards and local planning workflows](../spec.md)

## What to build

Deliver the complete tooling-only Python, React, and stable-flake baseline, including locked development dependencies, aligned runtimes, working project scripts, an optional Nix shell, and the actual agreed pre-commit hooks. Keep tooling and hooks together so all-files verification is available before later implementation tickets need it. No installable Python package, React application, NixOS host, CI pipeline, or permanent dummy tests are introduced.

The baseline must satisfy the parent spec's Ruff ALL/safe-fix/docstring rules, strict mypy and staged targets, strict TypeScript/indexed access, type-aware/Hook/accessibility linting, separate stable ESLint/Prettier formatting, configured project-wide typing, pytest and meaningful rendered-component testing, and independent coverage floors with branch reports. The optional shell and system-wide entry must both work; uv/npm continue to own project dependencies. Alejandra formats Nix while Statix/deadnix remain check-only.

Exercise genuine diagnostics, permitted fixes, actual staged hooks with an unrelated unstaged file, Python stubs, imported dependency analysis, all-files hooks, formatter compatibility, and stable reruns. Disposable application fixtures must demonstrate each profile's coverage floor passing and failing without hiding unexecuted source. Record actual shell/flake/platform coverage without activation. Remove all disposable application source/tests before final verification; application coverage is not applicable to an empty tooling-only profile. Return to exploration rather than silently weaken or replace an agreed integration.

Research 01 supplies tested frontend inputs. Use ESLint 9.39.5 and the official accessibility plugin under the temporary maintenance exception in exploration and the spec; preserve all required checks without peer overrides. Leave the project without Git metadata. Staged/all-files verification uses disposable checkouts of the actual template files, not project initialization or commits. See the [compatibility report](../research/tooling-compatibility.md).

Implemented root uv/Ruff/mypy/pytest/coverage configuration, Python minor selection and lockfile; the framework-neutral npm/TypeScript/ESLint/Prettier/Vitest baseline and lockfile; stable flake/shell/checks and lockfile; and staged-file hooks. Root scripts/check_python_coverage.py enforces the line-only floor from actual coverage JSON. Its two permanent CLI regressions catch line/branch metric confusion, not dummy application behavior.

Observed verification:

- Root and disposable-checkout uv installation succeeded without installing the template as a package. Strict mypy passed the two tooling files. Safe Ruff import fixes left an unsafe F841 removal unapplied and reported the remaining violation.
- Actual staged mypy passed one valid supplied target with an unrelated unstaged error present, then rejected the staged target after its type error was staged. The pyi filter rejected an undefined stub type. Research 01 proves project dependency visibility and individual import-untyped exceptions.
- Root-invoked remote ESLint rejected JS/JSX/TS/TSX violations with configuration/plugins loaded. The corrected configured project passed lint/typecheck; weakening a provider's tuple guarantee made its unchanged indexed-access consumer fail.
- Meaningful Python fixtures failed the line gate at 45% and passed at 100%; reports retained branches and unexecuted source. Eight rendered React/parser tests passed at 100% lines/branches. An incomplete passing React suite failed at 37.5% lines, and application source without tests failed.
- Vitest/coverage-v8 use 4.1.11 because 5.0.4 conflicted with jest-dom's assertion types. No library-check suppression or vendor patch was used. The empty frontend profile reports application tests/coverage as not applicable; the Python profile has two real tooling regressions and no application coverage.
- System-wide commands worked outside nix develop. The actual stable shell supplied Python 3.12.14, Node 24.21.0/npm 11.19.0, uv 0.11.21, pre-commit 4.5.1, Alejandra 4.0.0, Statix, and deadnix 1.3.2. nix flake check passed all three x86_64-linux checks; aarch64-linux remains unverified. No host or activation was introduced.
- Actual Statix and deadnix hooks rejected genuine findings without changing their inputs; Statix retained failure across supplied filenames. Alejandra formatted/checks the actual flake.
- pre-commit run --all-files passed twice in a disposable checkout of the actual template. Formatter changes were inspected and applied to the original files. No project Git initialization or commits occurred.

## Acceptance criteria

- [x] The actual manifests, lockfiles, configurations, scripts, flake, and hooks satisfy the corresponding spec sections and run with the selected supported runtimes.
- [x] Both environment entry paths work; neither workflows nor hooks depend silently on Nix shell setup.
- [x] Hooks check intended files, see required dependencies, fix only as permitted, fail on remaining violations, and reach a stable result. No required plugin/type-aware check is disabled and no agreed remote integration is silently replaced.
- [x] Mypy keeps staged filenames as explicit commit-time targets. Frontend typecheck uses the configured project rather than a staged-filename invocation that ignores tsconfig.
- [x] Coverage measures application source independently for each profile. The final tooling-only template honestly reports that application suites/coverage are not applicable where application code is absent; it does not manufacture a passing suite.
- [x] No runtime application, host configuration, permanent fixture, automatic commit, or activation is introduced.

## Blocked by

- [01: Verify tooling compatibility](01-tooling-compatibility.md)
