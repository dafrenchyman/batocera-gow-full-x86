# 01: Reconcile applicable standards and tooling facts

**Status:** Done

## Parent

[Repository guidance and documentation](../spec.md)

## What to build

Make the retained standards and current tooling topic describe this Python/Nix packaging application rather than ProjectTemplate. Use the Ready specification, [saved exploration](../explore.md), [baseline research](../../../../completed/epics/repository-maturation/research/repository-baseline.md), actual source/configuration and existing attributed template records as inputs. No prerequisite ticket is required.

Reconcile `docs/standards/general.md`, `repo-layout.md`, `dependency-injection.md`, `python.md` and `nix-nixos.md`. Remove `docs/standards/react.md`, inactive React/npm/ESLint/Vitest routing and unused NixOS host-management instructions. Repair references affected by the removed profile, including historical live links, without erasing their attributed meaning. Do not add tooling or application scaffolding to make copied prose true.

Preserve explicit configured-dependency injection and deterministic resource ownership in every environment. Permit `dependency-injector` outside Batocera, exclude it from final-runtime staging/imports, and distinguish that boundary from the stdlib-only ephemeral SSH helper. Preserve existing valid stock third-party dependencies.

State typed Python boundaries, meaningful Google-style docstrings, Ruff ALL with documented formatter compatibility, strict mypy, pytest, at least 80% independently measured application line coverage and branch reporting without a separate branch floor. Document these as policy, not measured current compliance. Retain Batocera-led interpreter alignment: host 3.12.x is allowed, including the user's reported Nix-provided 3.12.12; builder/default full-version pinning follows confirmed stock. Source defines 3.12.8, not newly runtime-verified here. uv owns project environments/dependencies, not OS Python.

Keep `experiments/gow-full-x86/` as the current source location until modernization. The future installed-package layout does not make current source or coverage inapplicable. Trim Nix policy to actual expressions, pinned runtime closure and applicable optional development environments; preserve `bridge.nix` runtime inputs and do not require an absent root flake.

Rewrite `docs/current/tooling.md` to distinguish installed/configured facts, future policy and attributed historical template exercises. Tool/hook installation, new tests, secret-baseline review and substantive application compliance belong to other specifications.

Include local claim, file/heading-link and available documentation-format checks in this ticket. Do not install tools, run application suites, contact Wolf or add permanent Markdown wording/source-text tests. Work in the current checkout. Coordinate shared navigation/history edits with ticket 02 rather than edit the same files concurrently; this scheduling constraint is not a prerequisite edge. Ticket 02 owns the later legacy-path integration.

Owner: omp coding assistant. The user's implement invocation authorizes this ticket in the current checkout. Eligibility reviewed against the Ready spec, exploration, parent epic, baseline and runtime-dependency research: no prerequisite or separate condition prevents execution.

Completed documentation tranche: reconciled `docs/standards/{general,repo-layout,dependency-injection,python,nix-nixos}.md` and `docs/current/tooling.md`; removed `docs/standards/react.md`. Retained explicit dependency/resource ownership, external-only container examples, stock libraries, interpreter boundaries and independent application line coverage. Current source remains applicable. Nix guidance preserves the actual runtime selection without inventing a root flake. Template exercises remain attributed history, not application verification. Ticket 02 still owns root navigation and legacy-path integration. The initial tranche did not edit shared history/navigation files; the resumed hook run below subsequently formatted some of them.

Initial verification on x64 Linux compared claims with `bridge.nix`, its `build.py` consumer, `builder.Dockerfile`, `requirements.txt`, `common.py`, remote-helper assembly and runtime probe imports, plus retained baseline/runtime-dependency research. A read-only local Python link/heading check covered outgoing links from the seven changed Markdown files and incoming references throughout `docs/`, `planning/`, `.agents/` and README: 46 local references, including seven incoming references, zero missing targets/headings. Removed-profile/changed-heading searches found no remaining live link to `react.md` or lost incoming anchor. The initial inventory found no root Python manifests/lock/version, hook config, flake/lock, installed source, coverage utility or frontend manifest. The user subsequently supplied hook configuration; standards/tooling now distinguish that configured inventory from missing complete policy enforcement.

`prettier --check` on the five standards, tooling and this ticket initially flagged DI/tooling formatting. `prettier --write` formatted those two files; the subsequent seven-file check passed. Initial direct correctness/security/maintainability/spec review found no documentation-contract blocker. Application suites, TypeScript checks, Nix builds, secret scans and runtime-version execution were not run. No tool installation, remote contact, permanent tests or throwaway files were introduced.

The original missing-config failure is resolved by the user's supplied `.pre-commit-config.yaml`. The resumed `pre-commit run --all-files` exited 1: Ruff reported 96 errors with 42 fixed and 54 remaining; Ruff format reformatted 29 Python files; strict mypy reported 1,584 errors in 29 files, including missing tomlkit in its environment; Statix reported four W04 warnings. ESLint had no matching files; deadnix passed. Prettier also modified README, `planning/current/app.md` and the legacy full-x86 `spec.md`; Alejandra modified `bridge.nix`. No installation or application suite was run. These automatic edits expand beyond this documentation ticket and have not been runtime-verified or accepted as modernization delivery.

The user explicitly accepts the pre-commit edits as correct and logic-preserving and directs that they remain. No rollback is needed or authorized. This resolves the automatic-edit disposition, not the remaining lint/type/Nix failures. The user-supplied config remains untouched, including its inactive frontend entry.

After updating inventory claims for the supplied hook file, explicit Prettier checks passed on all seven affected Markdown files. The repeated local reference check covered 49 references, including seven incoming references, with zero missing files/headings. Documentation review distinguishes configured hooks from measured compliance and keeps the user's configuration unchanged. The automatic edits are accepted by the user; no new runtime verification is claimed.

The repository owner explicitly accepts ticket 01 as complete and waives the passing all-files gate for this documentation-only ticket. Documentation acceptance and local formatting/link checks passed. The recorded Ruff, mypy and Statix failures remain unresolved and are deferred to separately authorized repository modernization, which also owns hook reconciliation. This ticket does not claim passing hooks or application standards compliance. No further work remains in ticket 01.

## Acceptance criteria

- [x] Retained active standards match this application's Python/Nix scope; the React profile and inactive frontend/host-management prescriptions are removed, with affected live references repaired and historical meaning preserved.
- [x] DI guidance preserves explicit configured dependencies and deterministic ownership while accurately distinguishing external `dependency-injector`, excluded final-runtime imports/staging, valid stock libraries and the stdlib-only remote helper.
- [x] Python policy preserves the specified typing, docstring, lint/type/test and independent 80% application line-coverage requirements, branch reporting and Batocera-led interpreter boundaries without claiming measured compliance or a new stock runtime-version check.
- [x] Current `experiments/` code remains applicable; future packaging/tool configuration is labeled future, and absent `src/` does not create a false coverage exemption.
- [x] Nix guidance preserves the actual pinned runtime closure and contains no requirement to create a root flake, developer shell or managed host merely to satisfy inherited prose.
- [x] `docs/current/tooling.md` matches the observed configuration inventory and attributes template runs instead of presenting them as application verification.
- [x] Local claim and file/heading-reference review plus available documentation checks have recorded results and limits; no application execution, installation, remote contact or permanent wording tests were introduced.

## Blocked by

None. Pending status does not authorize implementation.
