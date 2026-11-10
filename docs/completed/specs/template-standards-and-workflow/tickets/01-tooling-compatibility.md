# 01: Verify tooling compatibility

**Status:** Done

## Parent

[Template standards and local planning workflows](../spec.md)

## What to build

Identify a compatible, reviewed toolchain before installing the template baseline. Produce a research record with exact supported runtime/package choices, reviewed hook revisions, sources, commands, observed outcomes, failed approaches, security boundaries, and reusable integration findings. Reuse the existing [Prettier assessment](../research/prettier-remote-hook.md) without inflating its assurance.

Use disposable fixtures in the intended frontend layout to prove remote ESLint flat-config, plugins, eslint-config-prettier, type-aware dependency resolution, and genuine diagnostics/fixes for TS, TSX, JS, and JSX. Prove strict mypy sees project dependencies/stubs while supplied filenames remain its explicit targets; exercise a real type error and an untyped-import limitation. Confirm uv installs the chosen Python development dependencies without packaging this repository. Remove disposable fixtures; do not implement the project toolchain here.

A conclusive negative finding can complete research but cannot provide missing inputs to dependent implementation. Retain the evidence, return to exploration before changing agreed policy, and leave required dependent work blocked when compatible inputs are unavailable.

The checkout has no Git metadata. Hook experiments use disposable Git repositories; no project initialization, branch, or commit is authorized. Available system tools are Python 3.12.12, Node 24.11.1, npm 11.6.2, uv 0.7.22, pre-commit 4.0.1, and Nix 2.28.5.

[Compatibility report](../research/tooling-compatibility.md) records exact candidates, reviewed hook sources, and actual diagnostics. Remote ESLint checked all four frontend file types, applied fixes while retaining remaining errors, and stabilized with Prettier on two subsequent runs. Strict remote mypy saw project dependencies, rejected assignment/import-untyped errors, and passed the single explained-exception target while unrelated failing files remained.

The supported-runtime candidates are Python 3.12, Node 24 LTS, and stable Nixpkgs 26.05. Official jsx-a11y has no declared compatibility with maintained ESLint 10; the exercised ESLint 9.39.5 candidate is EOL. Exploration and the spec permit that temporary combination with an explicit maintenance exception. [Ticket 02](02-tooling-baseline.md) records subsequent shell/build and final baseline verification in disposable checkouts. Research fixtures were removed; no project Git initialization occurred.

## Acceptance criteria

- [x] The report identifies exact compatible choices and distinguishes executed proof from source-based findings or unverified assumptions.
- [x] ESLint evidence shows that intended files are checked, required plugins/configuration are loaded, violations are rejected, and fixes leave remaining errors visible. Ignored files cannot count as passing.
- [x] Mypy evidence demonstrates strict checking and project dependency visibility without blanket missing-import suppression or replacing staged targets with a whole-project invocation.
- [x] Hook review makes no claim of guaranteed safety or absence of compromise. NixOS activation and permanent application scaffolds are not part of this research.
- [x] A supported negative conclusion can complete this research ticket. An inconclusive investigation remains unresolved, with the missing evidence recorded.

## Blocked by

- None
