# Project guidance

This repository packages complete official x86 Batocera userspace with additive Wolf/GoW startup and input integration. Maintained Python lives in the installed `src/batocera_gow/{host,builder,runtime}` package, non-Python inputs in `build-assets/`, and tests in root `tests/`.

## Protected boundaries

Preserve unchanged Batocera, Wolf and GoW sources, stock mappings/configgen, and the complete stock payload and metadata. Keep project additions separate from stock files. The original Batocera checkout and its outputs, existing upstream deployment, operator content and unrelated services are not mutation targets.

Remote actions require explicit authorization and proven ownership of each affected resource. Restrict cleanup to those resources; never use destructive global cleanup. Preserve persistent production userdata and use independently owned disposable state for authorized tests. Read [current application constraints](docs/current/app.md) and [README isolation](README.md#isolation) before build or runtime work. They describe portable project roots, native ownership and state selection.

Preserve registry, application, runner and home identities. Exact operational values belong in [README operations](README.md#wolf-activation-and-qa) and [current deployment records](docs/current/app.md#remote-deployment-and-acceptance), not duplicated policy. Renaming source does not authorize migrating these identities or state.

## Standards and terminology

Read [shared standards](docs/standards/general.md) for every change, then the applicable profiles:

- Adding or reorganizing files: [repository layout](docs/standards/repo-layout.md).
- Python source, tests or tooling: [Python](docs/standards/python.md).
- Nix expressions, runtime closure inputs or development environments: [Nix](docs/standards/nix-nixos.md).
- Configuration, service assembly or resource ownership: [dependency injection](docs/standards/dependency-injection.md).
- Domain language: [glossary](GLOSSARY.md). Resolve terminology and qualifying ADRs through [domain-modeling](.agents/skills/domain-modeling/SKILL.md).
- Agent instructions or skills: [writing-for-agents](.agents/skills/writing-for-agents/SKILL.md), its [skill mechanics](.agents/skills/writing-for-agents/SKILL-MECHANICS.md) and [unslop](.agents/skills/unslop/SKILL.md).

## Current facts and planning owners

Read [application state](docs/current/app.md) for implemented behavior, historical evidence and operator reports, and [tooling](docs/current/tooling.md) before choosing checks. Configured hooks are not passing compliance; source-defined versions are not fresh runtime measurements. Server-side diagnostics do not establish client video, heard audio or physical-controller forwarding. Emulator success reports cover only the paths tried.

[Repository guidance](docs/completed/specs/repository-guidance/completion.md) records the documentation cutover. [Repository maturation](docs/completed/epics/repository-maturation/epic.md) routes the delivered guidance, Wolf integration and modernization outcomes and their combined review. The [original full-x86 workspace](docs/completed/specs/gow-full-x86/spec.md) is completed history with per-check evidence limits, not a current execution procedure. These records and local skills are sufficient for discovery without private continuation files, generated evidence or an external template checkout.

## Workflow routing

Before selecting work or changing planning status, read the [lifecycle reference](.agents/skills/_shared/lifecycle.md). Before consequential questions or exploration updates, read the [interview reference](.agents/skills/_shared/interview.md). They own eligibility, states, permissions and delivery gates. Specification approval, ticket creation, implementation, Git operations, publication, deployment and service interruption are distinct permissions.

Use [local planning workflow](docs/current/planning-workflow.md#artifacts-and-responsibilities) to select the existing owner for exploration, specs, tickets, single-ticket implementation, whole-spec execution, epic coordination or completion. Discover named skills through the host or read their linked `SKILL.md` directly. Do not duplicate their procedures here.
