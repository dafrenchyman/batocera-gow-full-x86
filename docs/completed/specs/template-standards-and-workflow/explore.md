# Template standards and local planning workflow

## Status

Exploration in an active grill-with-docs interview. Not a specification or implementation approval. Update this document during the interview. Confirmed requirements and recommendations must remain distinct.

## Problem

This repository is a template for future repositories forked from it, mainly for Python and React work, with Nix and NixOS standards also required. Write reusable standards here for those future projects, rather than derive their coverage solely from the template's current code. Its coding standards are mostly empty. Its copied workflow skills expect an issue tracker, while its documented-* workflows use a different local planning convention. Maintaining two workflow families risks inconsistent instructions and lost decisions.

Waiting until the end of a long interview to record choices can lose details when conversation context is compacted or becomes too large. Preserve exploration incrementally, then derive the specification from the saved exploration.

## Confirmed requirements

- Populate docs/standards/ with reusable shared, Python, React, and Nix/NixOS standards in this template for future repositories forked from it.
- Keep Nix and NixOS standards together in one document, docs/standards/nix.md.
- Populate docs/adr/ with relevant decisions. Which decisions warrant ADRs remains open.
- Replace issue-tracker-based spec and ticket workflows with local documents.
- Store active specs at docs/active/specs/<spec-name>/spec.md and completed specs at docs/completed/specs/<spec-name>/spec.md.
- Store each ticket as a single Markdown file in its owning spec's tickets/ directory, named <NN>-<short-name>.md, for example 01-short-name.md.
- Merge the documented-* workflows with the copied Matt Pocock workflows rather than retain competing workflow families.
- Grill-with-docs creates or resumes explore.md and updates it as choices are discussed. It does not create spec.md. To-spec creates the specification from the saved exploration.
- Ask one decision question at a time in grill-with-docs, then wait for the answer. Do not present the entire question backlog.
- When relevant, explain alternatives with concrete pros and cons, code snippets, and comparisons. Keep examples focused on the current decision.
- Apply unslop guidance when rewriting skills. Do not use em dashes.
- Move completed specs out of the active-work location. Do not keep completed specs beside active specs with only a status change.
- Support epics containing multiple linked specs, while allowing specs without an epic. Never nest spec folders inside epic folders.
- To-tickets requires spec.md marked Ready. Exploration, conversation context alone, and draft or blocked specifications are not valid sources for ticket generation.
- Use Ruff for Python linting and include it in pre-commit hooks. Add pre-commit configuration to this template repository, not only guidance for future forks.

## Existing implementation

- docs/standards/general.md, python.md, and ci.md are empty.
- docs/standards/repo-layout.md contains only a heading.
- No React standards document exists.
- docs/adr/ and docs/epics/ were empty at initial inspection. docs/specs/ was empty before this draft.
- GLOSSARY.md contains introductory text but no defined terms.
- to-spec publishes a spec to the configured issue tracker.
- to-tickets supports local tickets under .scratch/<feature-slug>/issues/ as well as external trackers.
- implement fetches tracker references and instructs automatic commits.
- implement-spec expects a tracker, an integration branch, per-ticket worktrees, and task-graph scheduling.
- documented-spec already captures decisions during exploration, but its default locations are under planning/active/.
- Repository guidance also names planning/active/, planning/completed/, planning/archived/, and planning/current/.
- grill-with-docs delegates to grilling and domain-modeling. It does not explicitly require incremental spec updates.

## Decisions and rationale

### Incremental exploration

Explore.md is the working document during the interview. Capture confirmed requirements, user decisions, rationale, rejected alternatives, useful examples, and unresolved questions as they arrive. Never mark an assistant recommendation as accepted without a user answer. To-spec subsequently creates spec.md from this durable record.

Reason: long conversations can lose details from context. Future sessions must be able to recover the requirements and decision state from local files.

Consequence: update explore.md before asking the next question. Preserve the original context-loss protection without treating an exploratory document as a specification. Documenting exploration does not authorize implementation.

### One question at a time

Present only the next consequential decision, give a recommendation with its tradeoffs, and wait for the user's answer. Keep the remaining discussion queue in durable documentation rather than displaying it as a batch of questions.

Reason: large question lists are overwhelming and make the interview harder to work through.

Consequence: grill-with-docs must not inherit grilling's requirement to ask the whole decision frontier in one round. The merged instructions must resolve that conflict explicitly. Update explore.md after each answer before advancing to the next question.

Use code snippets and comparisons when they clarify a real choice. Do not add examples mechanically or turn one question into several hidden decisions.

### Grilling and documented exploration boundaries

Retain grilling for general stress-testing of plans, decisions, and ideas outside documented exploration and domain modeling. Use one-question-at-a-time pacing. It does not create explore.md or perform glossary and ADR updates.

Grill-with-docs owns durable exploration and uses domain-modeling when the discussion develops domain terms, relationships, or architectural decisions. Challenge ambiguous or conflicting terminology, test concrete scenarios, and record resolved terms in GLOSSARY.md. Keep requirements and decision rationale in explore.md. Create ADRs only when domain-modeling's selection criteria are met.

Keep shared interview guidance authoritative in one place. The plain grilling entry point must not inherit the document-writing responsibilities of grill-with-docs.

### One workflow family

Merge the documented-* workflows and the copied workflows. Preserve incremental documentation rather than reducing the result to end-of-conversation synthesis.

Reason: the user wants both interactive questioning and durable specifications without competing workflows.

Consequence: skill ownership, public command names, completion behavior, and existing planning guidance need an explicit migration decision.

### Canonical documentation location

Use docs/ as the canonical root for the merged planning workflows. Replace planning/ conventions in affected skills and repository guidance rather than maintain two systems.

Reason: this matches the requested local spec and ticket paths and gives humans and agents one place to find planning documents.

Consequence: active specs live under docs/active/specs/ and completed specs under docs/completed/specs/. Epic layout, archival, and current-state locations still require decisions. Historical planning/ references in the existing-implementation inventory describe the pre-migration state, not the target convention.

### Ticket documents

Use one Markdown file per ticket under the owning spec's tickets/ directory, named <NN>-<short-name>.md. Do not create a directory per ticket.

Reason: single files are simpler to browse, link, and review. Supporting research can live beside the spec when needed.

Each ticket owns its acceptance checklist, status, blockers, execution progress, and verification evidence in its Markdown file. Do not maintain a separate tasks.md for the same work. Spec.md owns overall requirements, acceptance criteria, and ticket links.

Use the existing to-tickets issue-template sections: Parent, What to build, Acceptance criteria, and Blocked by. Parent references the local spec; retain the original local template's status field. Do not generate custom Objective, Scope, Deliverable, Execution checklist, Dependency impact, Evidence to record, or Completion handoff sections.

Write acceptance criteria as unchecked boxes and check each only after verification with supporting evidence. Record actual progress and evidence within the ticket as execution occurs; do not generate boilerplate evidence instructions. Migrate the documented workflows' progress-recording responsibilities into the ticket without imposing a second checklist.

Use the existing to-spec template sections: Problem Statement, Solution, User Stories, Implementation Decisions, Testing Decisions, Out of Scope, and Further Notes. Replace tracker publication with local persistence while preserving the agreed exploration, approval, and lifecycle contracts.

### Separate completed work

Move completed specs out of the active-work location. The user rejected keeping all specs at stable paths with status-only lifecycle tracking.

Reason: the user prefers a separate location for completed work.

Consequence: move the whole spec folder from docs/active/specs/<spec-name>/ to docs/completed/specs/<spec-name>/ when complete. The user selected lifecycle-first folders rather than docs/specs/active/ and docs/specs/completed/. Completion must account for references affected by the move.

### Spec completion gate

Move a spec to docs/completed/specs/ only when every ticket is Done or Unnecessary and the specification's acceptance criteria are satisfied. Done tickets record verification evidence; Unnecessary tickets record their reason and supporting evidence.

Reason: closed tickets alone do not prove that the promised behavior exists.

Consequence: verify the spec-level outcome before moving the whole folder and updating affected links. If research rules out the outcome, revise scope through grill-with-docs or archive the spec as abandoned rather than completed.

### Shared completion workflow

Replace documented-completion with a shared complete skill. It verifies the applicable completion gate, moves the whole folder, updates affected references and the parent epic when present, and updates current-behavior documentation.

Implement-spec and wayfinder reuse this procedure rather than duplicate it. Spec and epic completion criteria remain distinct.

Consequence: migrate documented-completion responsibilities and callers before removing it. The complete skill must be reachable by the workflows that invoke it. Current-state updates are a required part of completion, not an optional follow-up.

### Current implementation documentation

Keep docs/current/ as the topic-organized description of implemented behavior. Active, completed, and archived documents preserve planning and history; current documents explain what the project does today.

The complete process reviews the implemented changes from the spec or epic against docs/current/ and updates affected topic documents, including replacing obsolete descriptions. Describe verified implementation, not planned or Unnecessary work. Create topic files only when substantive behavior needs documentation.

Reason: the user wants completion to update the current implementation description rather than leave readers to reconstruct behavior from historical specs.

Consequence: completion is not finished until affected current-behavior documents reflect the verified changes. Epic completion reviews the combined outcome without blindly repeating updates already made for child specs.

### Current-state instruction ownership

Complete absorbs documented-current-state. Keep detailed current-documentation rules in a reference file inside the complete skill, reached explicitly from its current-state update step. Remove documented-current-state after its responsibilities and callers have migrated.

Consequence: updating docs/current/ directly remains possible without marking a spec or epic complete. Preserve that distinction in the reference and in any instructions that point to it.

### Implementation workflow ownership

Implement executes an individual local ticket, verifies its acceptance criteria, and records status and evidence. Implement-spec absorbs documented-spec-implementation and coordinates the approved ticket dependency graph, reassesses conditional work, verifies the whole specification, and invokes complete.

Consequence: migrate documented-spec-implementation responsibilities and callers before removing it. Branch and worktree policies remain separate decisions; the merge does not authorize automatic Git actions.

### Commit policy

Leave commits to the user unless the user explicitly instructs the agent to commit. Implementation, verification, ticket updates, and completion do not grant permission to commit automatically.

Reason: the user wants control over commit creation and boundaries.

Consequence: remove automatic commit instructions from the merged workflows. Record progress and verification in local documents without requiring commits as completion evidence.

### Branch and worktree policy

Implement in the current branch and checkout by default. Create or switch branches and create worktrees only when the user explicitly requests or authorizes those actions.

Consequence: remove mandatory integration-branch and per-ticket-worktree instructions. Independent, non-conflicting work may run in parallel in the shared checkout; conflicting work must be sequenced or use explicitly authorized isolation. Permission to create a branch or worktree does not imply permission to commit.

### Archived work

Move rejected, abandoned, or superseded spec and epic folders to docs/archived/specs/<spec-name>/ and docs/archived/epics/<epic-name>/. Record the disposition, reason, and replacement link when relevant.

Reason: retain rejected approaches for future planning without presenting them as successful completions.

Consequence: blocked or deferred work stays active while its outcome is still being pursued. An Unnecessary ticket stays with its owning spec; that status alone does not archive the spec. Update references affected by an archival move.

### Epics and standalone specs

Support an epic that groups multiple specs, and support standalone specs without an epic. Do not require an artificial parent epic for bounded work.

The existing wayfinder skill plans a map of decision tickets and normally finishes when decisions are resolved, not when implementation is complete. The documented-epic skill tracks child specs through implementation. The merged workflow must distinguish planning readiness from epic completion.

Keep every spec in the lifecycle-first specs/ directory and represent epic membership with links and a parent reference. An epic owns shared outcomes, cross-spec decisions, sequencing, and the spec backlog; a spec owns its detailed requirements and implementation tickets.

Reason: the user prefers linked specs and explicitly rejected nesting. A spec can complete independently of its epic or gain a parent without moving to a different folder hierarchy.

Consequence: the merged workflows must synchronize epic backlog links and spec parent references when documents move. Epic locations are docs/active/epics/<epic-name>/epic.md and docs/completed/epics/<epic-name>/epic.md.

### Epic completion gate

An epic is complete only when every required linked spec is completed and the epic's overall acceptance criteria are verified, including interactions between specs. Planning readiness and passing individual spec checks are not sufficient.

If a linked spec becomes unnecessary, retain its record and explain why it is no longer required. Removing that requirement does not waive an unmet epic outcome.

For example, completed Python API and React interface specs do not complete their epic until the required user flow works across the interface and API. Record combined verification evidence before invoking complete to move the epic and update current-behavior documentation.

### Epic workflow ownership

Expand wayfinder into the single epic-level workflow and absorb documented-epic. Remove documented-epic once its responsibilities and callers have migrated.

Wayfinder must explore one question at a time, update epic.md during discussion, maintain a linked spec backlog, and track the epic through completion. Planning readiness and implementation completion remain separate states.

Consequence: the merged skill is no longer planning-only. This does not authorize implementation during an exploratory interview. Ownership of standalone spec review, completion mechanics, archival, and current-state updates still needs decisions.

### Spec workflow ownership

Grill-with-docs absorbs documented-spec's exploration responsibilities. It creates or resumes explore.md, asks one decision question at a time, and updates explore.md after each answer. It does not create spec.md.

To-spec creates the specification from the saved exploration and reviews it for contradictions, unresolved decisions, scope, and acceptance criteria. It must preserve accepted decisions and meaningful examples rather than reconstruct them from chat alone. Unknown decisions remain explicit.

Consequence: remove documented-spec after its responsibilities and callers have migrated. Keep explore.md beside the resulting spec.md. Specification creation and readiness review do not authorize implementation.

### Specification readiness approval

To-spec writes spec.md as Draft, checks it against explore.md, and presents it for user review. Mark it Ready only after explicit user approval. Readiness review does not authorize ticket creation or implementation.

If unresolved decisions remain, return to grill-with-docs to resolve and record them before presenting the specification for approval. Do not request approval for an incomplete implementation contract.

### Exploration and specification consistency

To-spec leaves explore.md intact by default. Do not rewrite exploration merely to mirror the specification's wording or structure.

If specification generation reveals an error, contradiction, or unresolved decision, stop generation and return to grill-with-docs. Resolve the issue there, one question at a time, and correct the affected decision and rationale in explore.md first. Then resume to-spec using the corrected exploration.

Reason: exploration owns decisions; specification generation translates settled decisions into a contract. Keep that boundary explicit rather than turning to-spec into another interview workflow.

Consequence: to-spec does not conduct the correction interview or silently override accepted choices. It identifies the issue and provides the context needed to resume exploration. Preserve relevant rejected alternatives and explain why an agreed correction replaces an earlier choice. An existing specification affected by the correction must not be treated as ready until it has been updated.

### Ticket source

To-tickets requires spec.md marked Ready as its source. Exploration, chat alone, and draft or blocked specifications are not valid inputs for generating implementation tickets.

Reason: tickets must implement a reviewed specification rather than make unresolved choices look settled.

Consequence: remove the copied skill's direct exploration and conversation-to-ticket paths. Check readiness before generating tickets. Ticket generation does not itself authorize implementation.

### Ticket breakdown approval

To-tickets reviews the proposed work split with the user, including grouping, deliverables, and blockers. Discuss requested merges, splits, and alternative groupings one decision at a time. Revise the proposal until the user approves it, then write the ticket files.

Reason: the user may prefer a different grouping of work. Approval must support an actual discussion, not merely a yes-or-no confirmation of the agent's first breakdown.

Consequence: a Ready specification permits proposing tickets, not writing them without breakdown approval. Revisions require approval before file creation.

### Permanent ticket identities and unnecessary work

Ticket numbers are permanent within a spec. Once assigned, never delete, reuse, or renumber them. Retain invalidated tickets and mark their work Unnecessary instead of removing the files or pretending the work was completed.

Record why the work became unnecessary and link the decision, research result, or prior work that invalidated it. New tickets receive new numbers.

Reason: the user wants the history of planned work preserved, including branches ruled out by research or made redundant by earlier work.

Consequence: an unsuccessful research outcome can make conditional downstream work unnecessary. Retain those tickets without executing their work. A terminal research result is not proof that its proposed implementation should proceed.

### Research ticket completion

Mark a research ticket Done when it answers its question with supporting evidence, including a conclusive negative result. Distinguish rejection of an approach from failure to complete the research.

For example, evidence that a library lacks a required capability completes the evaluation ticket. Review dependent tickets and mark conditional implementation work Unnecessary when its conditions are false. Inconclusive research remains unresolved, with missing evidence or blockers recorded.

### Dependencies, conditions, and parallel work

Represent ticket ordering through explicit blockers, not ticket numbers. Independent tickets may run in parallel; dependent work waits for its prerequisites.

Conditional tickets include a Proceed only if condition separate from their blockers. Once the prerequisite evidence exists, evaluate the condition. If false, mark the ticket Unnecessary and record the reason. An unresolved condition does not authorize execution.

Consequence: the implementation workflow selects tickets whose prerequisites are satisfied and whose conditions permit execution. Actual concurrency must also account for conflicting edits or shared resources. An Unnecessary prerequisite does not automatically count as successful completion.

### Reviewing dependents of unnecessary work

Review each affected dependent when a prerequisite becomes Unnecessary. Do not automatically unblock or cancel all downstream tickets.

Continue only when the dependent's required inputs exist and its conditions permit execution. Mark it Unnecessary when its condition is false, recording the evidence. Keep it blocked when required inputs are missing. If proceeding requires changing an agreed decision, return to grill-with-docs before revising the specification and affected tickets.

Reason: downstream work can remain useful even when one planned approach is rejected, while other dependents require outputs that will never exist.

Consequence: document the dependency reassessment so subsequent sessions do not mistake waived work for a completed prerequisite.

### Combined Nix and NixOS standards

Keep Nix and NixOS rules in docs/standards/nix.md rather than separate documents.

Consequence: distinguish shared Nix-language and project-environment rules from NixOS-specific configuration rules within the document. Combining the document does not require every Nix project to manage NixOS hosts. Detailed coverage and configuration validation remain undecided.

### Nix entry point and dependency pinning

Use flakes as the default entry point when a fork uses Nix, including NixOS configurations. Define the entry point in flake.nix and record dependency revisions in flake.lock.

Flakes provide consistent outputs for packages, development shells, and NixOS configurations. They require enabling the relevant Nix features and following flake conventions. This choice does not require Python or React projects to adopt Nix.

### Nix formatter and hook

Use Alejandra as the default Nix formatter and include its pre-commit hook in the template. Familiarity with its formatting style outweighs adopting nixfmt's different convention.

[Alejandra](https://github.com/kamadorueda/alejandra) provides pre-commit integration. Keep one Nix formatter rather than run Alejandra and nixfmt together. Contributions to other repositories must follow their upstream formatting requirements.

The commit-time hook formats applicable staged Nix files; pre-commit run --all-files checks all applicable tracked Nix files during implementation verification. Review formatter changes before recording completion. Hook provisioning and version pinning still need definition.

### Nix linting and hooks

Use Statix and deadnix for Nix linting and include their pre-commit hooks in the template. Run both in check-only mode; do not automatically apply structural fixes or remove bindings.

[Statix](https://github.com/nerdypepper/statix) checks Nix antipatterns without evaluating code. [Deadnix](https://github.com/astro/deadnix) checks unused bindings and arguments; argument forwarding through callPackage can require narrow exceptions.

Formatting and static linting do not prove that a Nix expression evaluates or a NixOS configuration builds. Tool provisioning and version pinning remain to be defined.

### NixOS build and activation policy

Verify affected NixOS configurations by building their system output without activating it, using nix build .#nixosConfigurations.<host>.config.system.build.toplevel.

Builds provide evidence beyond formatting and static linting, at the cost of time, downloads, and disk usage. A successful build does not establish that runtime services behave correctly after activation.

Activation, boot-configuration changes, and remote deployment require explicit authorization. Building a system output does not grant permission to run nixos-rebuild switch or otherwise change the running machine.

### Flake verification

Run nix flake check during verification of Nix changes in flake-based projects. Keep it outside commit-time hooks.

It evaluates supported flake outputs and runs declared checks, complementing static linting and formatting. Verification is limited by the declared outputs, checks, and supported execution platform; record that coverage rather than imply every system was built.

Flake checks can trigger expensive builds. They do not replace explicit affected-host NixOS builds or authorize activation.

### Development environment entry

Support system-wide installations of development tools. Running the workflows and hooks must not require entering a Nix development shell.

Include an optional flake-based development shell in this template. Supply the chosen entry-point tools, including Python/uv, Node.js/npm, pre-commit, Alejandra, Statix, and deadnix. Do not add a NixOS host configuration merely to provide the shell.

Keep tool availability separate from project dependencies: uv and npm still manage project dependencies and their selected versions. System-wide tool setup must have a documented path that works without nix develop.

Verify both the shell-provided tool path and the supported system-wide tool path. Neither hooks nor workflow commands may silently depend on shell-only setup.

### Nixpkgs release policy

Use a supported stable Nixpkgs release as the prescribed flake input for development environments and NixOS configurations. Pin the resolved revision through flake.lock and review lockfile updates.

A fork may select nixos-unstable when its requirements justify the change, following the project-specific standards override policy. Select the concrete supported stable release during implementation.

### Prescribed tooling defaults

Standards prescribe concrete default tools rather than remain tool-neutral. Choose the tools for each language and configuration profile during exploration.

Consequence: future forks have a defined tooling baseline. Writing the standards does not itself authorize installing dependencies, creating application code, or adding CI pipelines. Verification commands and the exception process still need definition.

### Python environment and dependency management

Use uv as the default Python environment and dependency manager, with project dependencies declared in pyproject.toml.

Consequence: Python standards use one uv-based workflow rather than competing pip, Poetry, and uv defaults. Detailed tool configuration still needs definition.

Include a basic root pyproject.toml in the template implementation, with uv development dependencies for Ruff, mypy, pytest, and pre-commit and configuration for Ruff linting, formatting, import sorting, strict mypy, and pytest. Keep runtime dependencies out of the baseline until application requirements justify them.

The initial Python baseline is tooling-only: do not create a dummy package, add a build backend, or install this repository as a Python package. Exercise dependency setup and configured checks with uv. When a fork adds an installable package, put it in src/<python_package>/ and add the required packaging metadata and build backend.

### Python version policy

Select one explicit, supported Python minor version for the template's development baseline. Align uv interpreter selection, the optional Nix shell, Ruff's target version, and mypy's Python version. Allow patch updates; make minor-version upgrades deliberate compatibility changes.

The development baseline does not imply that every future library supports only that version. Forks must declare and verify their own supported interpreter range. Select the concrete template minor version after verifying the chosen tools and available Nix interpreter.

### Dependency lockfiles

Keep generated uv.lock, web/package-lock.json, and flake.lock in version control for the profiles present in the project. Lock development dependencies as well as runtime dependencies because tool versions affect linting, formatting, typing, and test results.

Update lockfiles deliberately and review dependency changes. Reproducibility does not establish dependency safety. Generating or updating lockfiles does not authorize automatic commits.

### Python test runner

Use pytest as the default Python test runner, invoked with uv run pytest. Run relevant tests during implementation verification.

Consequence: tests are separate from the pre-commit hook suite. Adding a test-running hook is not part of this decision. Standards must describe behavior-focused tests rather than tests coupled to incidental implementation details.

### Python linting and template hooks

Use Ruff for Python linting, formatting, and import sorting, replacing separate Black and isort defaults. Include Ruff lint and formatting hooks in this template's pre-commit configuration. Enable Ruff's import-sorting rules explicitly; formatting alone does not sort imports.

Consequence: implementation must include real hook configuration and exercise it against applicable files. Tool version pinning and additional hook coverage remain open. Running hooks does not authorize committing.

Ruff's [formatter](https://docs.astral.sh/ruff/formatter/) replaces Black-style formatting; its [I001 rule](https://docs.astral.sh/ruff/rules/unsorted-imports/) groups and sorts imports. Ruff is [not a type checker](https://docs.astral.sh/ruff/faq/#how-does-ruff-compare-to-ty-mypy-pyright-or-pyre), so it does not replace mypy. The official [pre-commit integration](https://docs.astral.sh/ruff/integrations/#pre-commit) exposes separate ruff-check and ruff-format hooks.

### Ruff rule selection

Use select = ["ALL"] as the Python lint baseline. Prefer its broader coverage over the previously considered curated rule sets.

Keep preview mode and unsafe fixes disabled. Configure the documented formatter-incompatible rule exclusions and narrow, explained exceptions for legitimate cases. Review new enforced rules when upgrading Ruff. Sources: https://docs.astral.sh/ruff/rules/ and https://docs.astral.sh/ruff/linter/#rule-selection.

Allow S101 only under tests/ through the per-file exception "tests/**" = ["S101"]. Pytest uses assertions to express expected behavior; a directory-scoped exception avoids repeating a suppression on each assertion while retaining the rule in application code. Other lint rules still apply to tests.

### Python docstrings

Use Google-style docstrings. Describe input arguments in Args and meaningful return values in Returns. Include Raises for exceptions callers need to handle, and describe relevant constraints and side effects. Type annotations do not replace descriptions of what inputs and outputs mean.

For example:

```python
def load_settings(path: Path) -> Settings:
    """Load and validate settings from a TOML file.

    Args:
        path: Path to the TOML settings file.

    Returns:
        Validated settings loaded from the file.

    Raises:
        FileNotFoundError: If the settings file does not exist.
        ValueError: If required settings are missing or invalid.
    """
```

Document actual behavior rather than invent guarantees or exception types. Configure Ruff for the Google convention; linting checks structure but cannot establish that descriptions are accurate.

### Ruff hook fixes

Run ruff-check with --fix, then ruff-format. Permit safe lint fixes without enabling --unsafe-fixes.

Consequence: hooks can modify files and require review and re-staging before another commit attempt. Agents review the changes and rerun verification without creating commits automatically.

### Python type checking

Use mypy as the conservative default Python type checker and include a type-checking pre-commit hook. The user accepted mypy subject to considering better or faster alternatives.

The alternatives reviewed do not establish a universally better default. [Pyright](https://github.com/microsoft/pyright) is a full-featured checker designed for high performance. [Ty](https://github.com/astral-sh/ty) advertises faster checking but is currently beta and explicitly permits breaking changes between releases. Its published speed claims are not measurements of this template or future forks. [Mypy's daemon](https://mypy.readthedocs.io/en/stable/mypy_daemon.html) supports faster repeated checking using cached state.

Reason: prioritize a conservative template baseline over unmeasured performance claims. Keep one default checker rather than require several with different diagnostics.

Consequence: retain mypy unless the user selects an alternative after reviewing the tradeoff. The hook must see the project's dependencies and type stubs.

### Strict Python type checking

Enable mypy strict = true for new Python code. Use narrow, explained exceptions for third-party typing limitations rather than disabling checks globally.

Strict checking requires typed function boundaries and exposes typing gaps that gradual checking can leave unchecked. The tradeoff is additional work around dependencies with incomplete type information.

For an individual untyped third-party import, use an error-code-specific inline suppression with an explanation, such as `import vendor_sdk  # type: ignore[import-untyped]  # Upstream ships no typing metadata.` Prefer that targeted exception over blanket `ignore_missing_imports = true`.

### Prettier hook integration

Prettier remains maintained and documents [Git pre-commit integration](https://prettier.io/docs/precommit). The [pre-commit/mirrors-prettier repository](https://github.com/pre-commit/mirrors-prettier) is archived because its plugin integration broke. Do not use that mirror as the template integration.

Prefer remote hooks where suitable; local hooks remain an option when needed. Use [rbubley/mirrors-prettier](https://github.com/rbubley/mirrors-prettier) pinned to reviewed revision 331f33fa4dfbcbca7c3da3620c137fde0faab273 for the plugin-free baseline. Keep project and hook formatter versions aligned. Review updates before changing the pin; source inspection and registry signatures do not certify absence of compromise.

Include the reviewed remote Prettier hook in the template. Prettier's archived original mirror is not evidence that Prettier itself or Git hook use is discontinued.

The actual pinned hook formatted TSX, JSON, CSS, Markdown, and YAML and passed a second run. Plugin-only hook installation failed project-relative resolution; installing the test plugin in the project allowed the hook to pass. See research/prettier-remote-hook.md for security boundaries, upstream publication weaknesses, signature verification, and runtime evidence.

### React language and type checking

Use TypeScript for new React code with compiler strict checking enabled. Typed component contracts and strict null checking catch interface mistakes before runtime.

The tradeoff is additional type definitions, especially around external libraries.

Require a project-wide TypeScript check before marking tickets that affect frontend code or tooling Done. Run an npm typecheck script against the project's TypeScript configuration, typically using tsc --noEmit. Keep this outside staged-file commit hooks. ESLint does not replace compiler type checking; changes can break unchanged consumers. Source: https://www.typescriptlang.org/docs/handbook/compiler-options.html.

Enable noUncheckedIndexedAccess alongside strict mode in the default frontend TypeScript configuration. Handle potentially missing array elements and dictionary entries explicitly. Prefer checked access or types that express a proven guarantee over routine non-null assertions. This catches missing-value errors at the cost of additional narrowing where the compiler cannot prove an index exists. Source: https://www.typescriptlang.org/tsconfig/noUncheckedIndexedAccess.html.

### Framework-neutral React standards

Keep React standards framework-neutral. Do not prescribe Vite or Next.js for every fork or add an application scaffold as part of these standards.

Select rendering, routing, and deployment architecture in each project's planning based on its requirements. The prescribed TypeScript, npm, linting, formatting, and testing defaults remain the baseline, with framework-specific configuration where needed.

Include a tooling-only frontend baseline in web/ with package.json, a generated package-lock.json, TypeScript configuration, ESLint configuration, and test configuration as needed for working lint, format, typecheck, and test commands. Include React, its TypeScript types, TypeScript, ESLint, Prettier, Vitest, and React Testing Library. Do not add an application, routing, or framework-specific dev/build scripts until a framework is selected. npm uses package.json, not package.yaml.

### React state management

Default to React's built-in state tools rather than prescribe or install an external state-management library. Keep state local where possible, lift it when components must coordinate, and use reducers or context where the requirements justify them. Context is not a default store for all application state.

Add an external state library only for a concrete project need. Treat server-data caching as a separate concern. This avoids dependencies and conventions that a simple application does not need while allowing more capable tools when shared state becomes complex.

### React linting and formatting

Use ESLint for React and TypeScript linting and Prettier for formatting. Include TypeScript-aware linting, React Hooks rules, and accessibility checks. Keep formatting rules in Prettier rather than duplicate them in ESLint.

This separates semantic lint checks from formatting and permits a React-aware rule set. The tradeoff is maintaining two tools and compatible configurations. Detailed rules remain undecided.

Include eslint-config-prettier after other flat-config entries to disable conflicting formatting rules, retain canonical plugin names, and check representative file overrides with its CLI helper. Run Prettier separately rather than through eslint-plugin-prettier. Sources: https://prettier.io/docs/integrating-with-linters and https://github.com/prettier/eslint-config-prettier.

Verify the combined configured tools reach a stable result on representative files. Hook order alone is not a solution to conflicting rules.

### ESLint remote hook

Include ESLint through a remote pre-commit hook rather than a local hook. The [pre-commit/mirrors-eslint](https://github.com/pre-commit/mirrors-eslint) repository provides an eslint hook and documents additional_dependencies for plugins and file filters for TypeScript and JSX.

Pin a reviewed mirror revision and exact compatible ESLint/plugin versions, aligned with the project's npm tooling. Ensure hook filters include TS, TSX, JS, and JSX. Type-aware checks still require access to the project's TypeScript configuration and dependencies.

The remote integration's source, version compatibility, plugin resolution, and actual diagnostics must be verified before implementation is considered complete. If the selected setup fails, investigate the remote integration rather than silently omit plugins, disable type-aware checks, or substitute a local hook.

Compatibility research found a maintenance conflict. Official eslint-plugin-jsx-a11y 6.10.2 supports ESLint through major 9; no published official release or prerelease declares ESLint 10 compatibility. ESLint 9 reached end of maintenance on 2026-08-06. Its remote hook was exercised successfully, but technical compatibility does not resolve the maintenance risk. See [tooling compatibility](research/tooling-compatibility.md).

Use ESLint 9 temporarily with an explicit end-of-life exception. This retains the proven official accessibility-plugin combination without bypassing peers or weakening rules. Reassess the exception during dependency updates and move to maintained ESLint when a reviewed integration preserves the required checks and remote-hook behavior.

Remote hooks run against the checkout's configuration and files, but do not automatically inherit its npm-installed packages. Ensure the selected resolution path provides eslint-config-prettier and all enabled plugins with aligned pinned versions. Prove the actual remote hook loads that configuration and rejects representative lint violations; a passing run with silently ignored files is not verification.

Eslint-config-prettier disables known conflicting rules; the ordinary lint hook does not automatically audit the configuration for later overrides that re-enable conflicts. Use the compatibility CLI helper during configuration verification, separately from lint diagnostics.

### ESLint automatic fixes

Run the remote ESLint hook with --fix. Apply rule-provided automatic fixes, report remaining violations, and keep Prettier responsible for formatting through eslint-config-prettier.

ESLint fixes can change code structure, unlike layout-only formatting. Review the resulting diff and run acceptance verification; automatic fixes are not proof of correctness. Issues without an automatic fix still require manual resolution. Source: https://eslint.org/docs/latest/use/command-line-interface#--fix.

If hooks modify files, review and re-stage before retrying a commit. Neither fixing nor verification authorizes the agent to commit automatically.

### Frontend package manager

Use npm as the default frontend package manager. Familiar commands reduce setup and troubleshooting friction compared with adopting pnpm.

Pnpm's isolated default dependency layout remains a useful alternative, but does not outweigh familiarity for this template. Both support workspaces. See research/frontend-package-manager.md for the comparison.

Use the generated web/package-lock.json under the dependency lockfile policy. Do not introduce pnpm commands or a second package-manager lockfile as competing defaults.

### Node.js version policy

Select one explicit, supported Node.js LTS major version for the frontend baseline. Align project tooling, remote Node-based hooks, and the optional Nix shell. Allow patch and minor updates within that major; make major upgrades deliberate compatibility changes.

Verify the selected runtime against locked frontend dependencies and actual remote hooks. System-wide tool installations remain supported without entering the Nix shell. Select the concrete LTS major during compatibility verification.

### React unit and component tests

Use Vitest as the React unit and component test runner and React Testing Library to exercise rendered components through user-visible behavior.

Test observable outcomes and interactions rather than internal state or component structure. Component tests require a configured DOM environment.

### Browser-level end-to-end tests

Use Playwright for browser-level end-to-end tests when a project needs that coverage. Target critical user journeys involving routing, browser behavior, or backend integration rather than duplicate every component test.

Real-browser coverage complements unit and component tests. It requires browser installation and a more expensive test environment.

### Type-checking hook scope

The commit-time mypy hook takes only staged Python files as explicit targets, using the filenames supplied by pre-commit. Do not replace that input with a whole-project target or pass_filenames: false.

Consequence: mypy may follow imports needed to analyze those targets; staged targets do not imply zero analysis of unstaged dependency files. A passing staged-file hook is not evidence that unchanged callers remain valid.

### All-files verification before ticket completion

Run pre-commit run --all-files before marking an implementation ticket Done, in addition to its acceptance verification. Commit-time hooks remain limited to staged files. The all-files run executes the configured hooks against all applicable tracked files, including the mypy hook's Python targets.

Consequence: hook filters must cover the intended Python code and stubs. Document exclusions rather than claim excluded files were checked. If a hook changes files, inspect the changes and rerun until the checks pass before recording completion. Running verification does not authorize committing or adding CI pipelines.

### Behavioral tests and coverage

Use both behavior-based testing requirements and a numerical coverage baseline. Cover relevant public behavior, boundaries, errors, state transitions, acceptance criteria, and bug regressions. Meeting a percentage does not replace meaningful assertions or acceptance verification.

Require at least 80% line coverage separately for the Python and React application profiles. Measure application source rather than tests or generated code, and report branch coverage as well. Explain exclusions. Do not add tests without useful behavioral assertions or exclude meaningful application code merely to raise the percentage.

A tooling-only profile without application source has no application coverage to measure. Do not create dummy application code or tests to manufacture a passing report. Once application code exists, meeting the coverage floor remains necessary but does not replace behavioral acceptance verification.

### Required checks and scoped exceptions

Required checks must pass before work is marked Done. Fix violations by default. When a legitimate case is misrepresented by a tool limitation, use the narrowest supported exception and explain it at the affected code or configuration.

Apply this policy to Python typing, ESLint, and Nix linting. Prefer an individual rule or error-code suppression over disabling checks globally. Unresolved violations and unexplained suppressions block completion.

### Writing style

Use unslop guidance in rewritten skills and new documentation. Em dashes are prohibited.

Consequence: prose cleanup must not silently change execution requirements.

Use writing-for-agents for skill structure and instruction design, alongside unslop for prose. Keep ordered steps visible, define checkable completion criteria, co-locate related rules, and disclose branch-specific reference through explicit pointers. Shared workflow rules should have one authoritative home rather than repeated copies. Skill invocation settings and cross-skill calls need review during migration.

Record requirements, decisions, rationale, and unresolved questions in planning documents. Omit session narration such as which skills the assistant loaded or when they became available.

Include rationale only when it explains a constraint, tradeoff, or consequence. Statements that merely say the user accepted or selected a default add no design information and should be omitted.

### Exploration relevance gate

Keep `explore.md` as a decision record, not an activity log. Before writing, ask: would removing this information change how a future reader specifies the work, resolves an open question, or understands a meaningful tradeoff? If not, omit it.

- Record requirements, decisions, design constraints, meaningful rationale, unresolved questions, and examples that clarify them.
- Update the existing topic instead of appending a duplicate. Preserve rejected alternatives only when their rationale helps future decisions.
- Omit routine file changes, skills loaded, session chronology, and statements that merely report user approval. Record the approved choice, not the approval event.
- Keep implementation progress and verification evidence in tickets. Keep detailed research in linked research files; retain only findings that affect the design in `explore.md`.
- After each update, remove redundant or superseded wording. Do not add a note saying that you cleaned up the document.

### ADR selection and format

Use domain-modeling as the authoritative skill for deciding when an ADR is warranted and use its ADR-FORMAT.md reference for the document format. An ADR is warranted only when the choice is hard to reverse, surprising without context, and the result of a real tradeoff. If any criterion is missing, keep the decision in exploration or standards instead.

Grill-with-docs and wayfinder must consult domain-modeling when a discussion changes domain terminology or raises an ADR candidate. Reference the skill rather than copy its selection rules and format into multiple workflows. Reuse applicable accepted ADRs during specification and implementation.

### Standards applicability

Python, React, and Nix are optional profiles. Keep a concise project scope and standards-routing section in AGENTS.md: identify the technologies and relevant areas, point to shared standards, and require technology-specific standards when work touches that technology.

Use manifests and source files to confirm applicability rather than duplicate dependency lists or versions in AGENTS.md. Update the scope and pointers when the project adopts or removes a technology. A stale profile list must not exempt existing code from its applicable standards.

Apply shared standards to all work and technology-specific standards to the affected areas. A Python-only fork does not require React scaffolding or Node tooling solely because the template includes React standards.

Include the project-scope and standards-routing sections in this repository's default AGENTS.md. Describe actual contents rather than claim optional application scaffolds exist. Use src-based Python organization rather than a backend directory.

### Project-specific standards overrides

Future forks may replace a prescribed default by updating the relevant configuration and recording a concise standards exception in AGENTS.md. Identify the replacement and explain the reason. Preserve the relevant quality checks and update affected workflow instructions so they agree with the selected tool.

Create an ADR only when the override meets domain-modeling's ADR criteria. A tool substitution alone does not require one.

### Repository layout

Keep Python packaging at the root with pyproject.toml, uv.lock, src/<python_package>/, and tests/. Put the React application in web/ with its own package.json, package-lock.json, and src/. Keep flake.nix and flake.lock at the root, with supporting Nix modules in nix/. Retain docs/ and .agents/ at the root. The normative layout is recorded in docs/standards/repo-layout.md.

This preserves a conventional Python source layout and gives the frontend a separate dependency boundary without assuming the Python code is a server. Do not create empty application scaffolds for unused profiles. The remote frontend hooks must resolve configuration and dependencies from web/ and must be verified against this layout.

## Open decisions

None remain for this contract. The [specification](spec.md) defines the selected profiles, verification and exception policy, workflow ownership, ticket graph, and lifecycle gates. Application/host scaffolds and CI remain out of scope.

## Workflow responsibilities

- Confirmed: grill-with-docs absorbs documented-spec's exploration responsibilities and maintains explore.md one decision at a time, without creating spec.md.
- Confirmed: to-spec creates and reviews spec.md from the saved exploration.
- Confirmed: to-tickets derives local tickets only from spec.md marked Ready and writes ticket files only after user approval of the proposed breakdown.
- Confirmed: implement executes an individual local ticket and records acceptance verification, status, and evidence.
- Confirmed: implement-spec absorbs documented-spec-implementation, coordinates the ticket graph, verifies the whole spec, and invokes complete.
- Confirmed: wayfinder absorbs documented-epic and owns epic exploration, the linked spec backlog, and epic lifecycle tracking.
- Confirmed: rejected, abandoned, and superseded specs and epics move to docs/archived/ with reasons preserved.
- Confirmed: complete replaces documented-completion and owns the shared completion procedure.
- Confirmed: docs/current/ describes implemented behavior, and complete must review and update affected topic documents as part of spec or epic completion.
- Confirmed: complete absorbs documented-current-state, with detailed current-documentation rules in a reference file inside the skill.

## Exploration acceptance examples

- A resumed interview can recover settled decisions and unresolved questions from explore.md without the previous chat.
- Draft recommendations cannot be mistaken for approved requirements.
- The merged workflows consistently resolve specs and tickets from local paths without requiring an issue tracker.
- Skill names and responsibilities do not leave competing sources of workflow authority.
- To-spec preserves accepted decisions and meaningful examples from explore.md, and exposes unresolved questions rather than inventing answers.
- To-spec preserves explore.md. Issues discovered during generation return to grill-with-docs for correction in explore.md before specification generation resumes.
- To-tickets requires spec.md marked Ready and refuses ticket generation from exploration, chat alone, or draft or blocked specifications.
- To-tickets supports discussion and revision of ticket grouping, deliverables, and blockers before user approval and file creation.
- Ticket numbers remain permanent. Invalidated tickets remain on disk with status Unnecessary and a reason; their work is not executed or reported as completed.
- Ticket blockers determine execution order; independent work may run in parallel.
- Conditional tickets distinguish prerequisite completion from permission to proceed. False conditions produce retained Unnecessary tickets; unresolved conditions do not permit execution.
- An Unnecessary prerequisite triggers review of affected dependents, not automatic unblocking or cancellation. Required inputs and conditions govern the outcome; changes to agreed decisions return to grill-with-docs.
- Spec completion requires all tickets to be Done or Unnecessary with supporting records and all specification acceptance criteria to be satisfied before the folder moves to docs/completed/specs/.
- Archival preserves stopped or superseded specs and epics separately from completed work, with disposition, reason, and replacement links when relevant.
- Implement-spec and wayfinder reuse complete for completion mechanics rather than duplicate its procedure.
- Completion updates docs/current/ to reflect verified implementation changes and removes obsolete descriptions; planned and Unnecessary work are not documented as implemented.

These examples are design context, not an execution checklist. The approved acceptance contract is in [Testing Decisions](spec.md#testing-decisions).
