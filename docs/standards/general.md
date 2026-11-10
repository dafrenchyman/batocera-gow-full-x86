# Shared coding and review standards

## Applicability and defaults

Read this standard for every change. Read [Python](python.md) for Python source, tests and tooling, [Nix](nix-nixos.md) for Nix expressions and build environments, [Batocera](batocera.md) for startup, emulator integration and userdata overrides, and [repository layout](repo-layout.md) when adding or reorganizing files.

This application packages complete official x86 Batocera with additive Wolf/GoW startup and input integration. Maintained Python lives in `src/batocera_gow/`, with non-Python inputs in `build-assets/` and tests in root `tests/`. Standards describe required policy for new or changed work, not measured compliance of existing code. Do not create frontend tooling, a managed host or application scaffolds to satisfy inherited template prose.

Configuration is authoritative for runtime selections, dependency pins, hook revisions, scripts, and exact rule settings. Use the documented command entry points, but read their configuration before changing behavior. Keep project dependencies and hook executables aligned. Review lockfile changes with their manifest changes and retain the applicable lockfiles in version control.

Replace a prescribed tool only through an approved policy change that preserves its relevant checks and updates configuration, locks and routing. Removing an inactive profile is different from disabling checks for existing application code.

## Code design

- Use names that describe domain concepts and observable actions. Consult root `GLOSSARY.md` once established. Use [domain-modeling](../../.agents/skills/domain-modeling/SKILL.md) when resolving terminology or considering a decision record. That skill owns ADR selection and format.
- Keep responsibilities small enough to explain without listing unrelated tasks. Put rules with the code that owns them. Separate domain decisions from filesystem, network, process, and UI operations when it makes the rules easier to test.
- Prefer existing conventions and dependencies. Introduce an abstraction for a demonstrated shared responsibility, not for hypothetical callers. Make dependencies explicit rather than hide them in mutable globals.
- Follow [dependency injection](dependency-injection.md) when passing configuration, assembling services, managing resource ownership, or creating request-scoped dependencies.
- Define boundary behavior. Handle missing values, invalid external input, cancellation, and relevant failure modes deliberately. Catch errors where the caller can recover or where a boundary can translate them into a useful result. Preserve the original cause when adding context.
- Keep a single source of truth for each fact. Derive values when practical instead of synchronizing copies. Remove obsolete callers and comments when changing an interface.
- Choose data structures and algorithms for the actual workload. Avoid needless copying, allocation, repeated I/O, and repeated computation. Measure before adding a cache or optimization that complicates correctness.
- Protect secrets and personal data at input, storage, and logging boundaries. Diagnostics should identify the failed operation without exposing credentials or sensitive payloads.

## Tests and review

Test observable behavior at the highest useful seam. Cover public outcomes, relevant boundaries, errors, invariants, state transitions, and regressions. Assertions should distinguish correct behavior from a plausible wrong implementation. Prefer a small integration test over a chain of mocks that only checks forwarding.

Keep tests independent and repeatable. Control time, randomness, filesystem state, and external services where they affect the result. Mock an expensive or nondeterministic boundary, not the rule under test. Test names should describe the condition and expected outcome. See the applicable profile for its runner and coverage gate. A passing coverage percentage does not demonstrate correct behavior.

Review the change as a future maintainer:

- Does it implement the requested behavior, including failure paths and compatibility effects?
- Do callers, tests, documentation, configuration, and locks agree with the new behavior?
- Are the tests capable of detecting the defect or behavior change, rather than just exercising lines?
- Are security, data-loss, resource ownership, and platform assumptions explicit where relevant?
- Can unnecessary state, dependencies, abstractions, or comments be removed without losing the behavior?

Required checks must pass. Prefer correcting code over suppressing a diagnostic. If a check is genuinely inapplicable or wrong, scope the exception to the affected rule and smallest useful location, explain why, and retain unrelated checks. Reassess exceptions during tool upgrades. Blanket disables and unexplained excludes are not substitutes for review.

## Environment and verification entry points

Read [current tooling](../current/tooling.md) before selecting commands. Root `pyproject.toml` and `uv.lock` own the installed project and dependency environment. The supplied [hook configuration](../../.pre-commit-config.yaml) does not establish passing application checks. uv owns project environments and dependencies, not the OS interpreter.

Use only available, applicable checks within the authorized task scope. Installation may execute third-party code; hook environments are not sandboxes. Review packages, executable configuration and plugins before trusting them. Pins identify inputs, not proof of safety.

The execution lifecycle requires this gate before a ticket is Done:

```sh
pre-commit run --all-files
```

Report missing configuration or environment prerequisites rather than installing tools, inventing configuration or skipping absent checks silently. When hooks exist, inspect permitted fixes and rerun until stable. Hooks do not replace whole-project typing, behavioral tests, application coverage or applicable Nix verification. Hook installation, Git operations and deployment require their own authorization.

## Documentation

Document contracts and non-obvious reasons, not a paraphrase of the code. Explain constraints, side effects, and relevant failure behavior at public boundaries. Update descriptions of implemented behavior when a change makes them inaccurate. Keep proposed behavior in planning documents, not in claims about current behavior.

Use direct prose, sentence-case headings, and no em dashes. Keep detailed standards here and route to them from agent guidance rather than copy them into every instruction file. Repository organization belongs in [repository layout](repo-layout.md); planning and lifecycle behavior belongs to the corresponding skills.

### README content

Root and directory `README.md` files are task-oriented entry points, not execution logs. Explain the component's purpose, how to use it, expected outcomes and constraints that affect safe use. Link to detailed topic documentation rather than copying it.

Keep run-by-run results, image/source hashes, run IDs, timings, test counts and cleanup observations in the owning ticket, research or completion record. Generated reports belong under `output/`. Include an exact value in a README only when the reader needs it to perform a documented task, such as selecting an immutable deployment image or reproducing a failure.

When verification status affects use, state the current limitation briefly and link to the supporting record. Preserve the distinction between verified and unverified behavior without narrating every attempt. Update or replace stale status instead of appending another run. Current-topic documentation should describe present behavior and relevant limits, with links to historical evidence rather than a copied run diary. Follow [repository layout](repo-layout.md#documentation-and-planning) for document placement.

### Useful diagrams

Prefer a Mermaid diagram when it makes a non-obvious flow, sequence, state transition or dependency easier to understand than prose alone, including in READMEs. Each diagram should answer a concrete reader question, such as which process owns a resource or how input reaches an emulator. Omit it when a short sentence, list or table is clearer; there is no diagram quota.

Use actual component names, meaningful arrows and only the detail needed for that question. Keep diagrams consistent with current behavior and update them when that behavior changes. Let nearby prose explain constraints or exceptions instead of repeating every node and arrow. Avoid decorative diagrams, trivial linear step lists and multiple views of the same information.
