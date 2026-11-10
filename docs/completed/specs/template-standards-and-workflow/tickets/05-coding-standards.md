# 05: Populate reusable coding standards

**Status:** Done

## Parent

[Template standards and local planning workflows](../spec.md)

## What to build

Populate reusable shared, Python, React, combined Nix/NixOS, and repository-layout standards aligned with the working toolchain. Provide coding/review guidance as well as setup: maintainability, meaningful behavior tests and independent coverage floors, scoped exceptions, concise documentation, prescribed defaults, and applicable-profile routing. Keep Nix and NixOS in one file and do not assume Python is a backend.

Cover the parent spec's Python source layout, uv/runtime/lock policy, Ruff ALL/safe fixes/exclusions, strict mypy and explained individual import exceptions, pytest, and Google Args/Returns/relevant Raises. Cover framework-neutral React/TypeScript, strict indexed access, built-in state defaults, server-data separation, accessibility/Hooks, npm, ESLint/Prettier cooperation, project typing, public component outcomes, and Playwright when critical browser flows justify it. Cover stable flakes/locks, Alejandra, check-only Nix linting, honest evaluation/build/platform limits, affected-host builds, and authorization before activation/deployment.

Document both environment entry paths without copying authoritative configuration versions/scripts. Preserve the agreed future source layout without demanding unused profiles or application scaffolds. Explain concise fork overrides and refer to domain-modeling for qualifying ADRs. Check examples/commands against configured tools, apply unslop, and run all-files hooks. Do not impose CI pipelines or additional frameworks/libraries, retain fake coverage, or turn dependency pins into safety guarantees.

Implemented shared, Python, React, combined Nix/NixOS, and layout standards against the actual baseline. Configuration owns pins/settings; standards own coding/review guidance and applicable command entry points. ADR selection and format remain in domain-modeling.

Observed verification: documented root Ruff check/format, strict mypy, pytest (two tooling regressions), the line-only coverage checker, frontend lint/typecheck/test/format checks, and Alejandra/Statix/deadnix commands passed. Empty application profiles reported no application coverage rather than a manufactured suite. The actual Python docstring example accepted bounds/whitespace and rejected invalid text and out-of-range values. Ticket 02 supplies rendered React and independent line-floor pass/fail evidence. Host commands are explicitly conditional examples; no host exists, no activation was run, and aarch64 remains unverified.

All eight configured hooks passed with pre-commit run --all-files on the actual template copy after reviewed formatter changes; the final run made no changes.

## Acceptance criteria

- [x] The agreed standards are populated, mutually consistent, and useful for coding/review as well as tool setup. Nix/NixOS stay in one file and Python is not assumed to be a backend.
- [x] The exact accepted defaults and exceptions match the spec and actual configuration. Runtime/library/framework choices beyond the approved baseline are not imposed.
- [x] Testing requirements combine meaningful behavior with measured profile floors. Empty tooling-only profiles do not acquire dummy tests or fictitious coverage.
- [x] Commands/examples work for their stated context, platform limits and exclusions are clear, and dependency safety is not inferred from lockfiles or mirror pins.
- [x] Prose uses no em dashes, approval narration, or irrelevant session history. Detailed rules have one authoritative home.

## Blocked by

- [02: Build the working tooling baseline](02-tooling-baseline.md)
