---
name: docs-baseline
description: Establish or reconcile docs/standards and qualifying ADRs in an existing repository. Use when adopting documentation conventions, backfilling missing standards, or reviewing a partial documentation baseline without changing application behavior.
---

# Documentation baseline

Build a small, repo-specific documentation baseline, not a migration to this template's technology choices. This invocation authorizes documentation work only. Preserve source, manifests, locks, hooks, infrastructure, and existing planning state. Do not install tools, initialize Git, commit, or execute repository scripts without authorization.

Read [writing-for-agents](../writing-for-agents/SKILL.md) and [unslop](../unslop/SKILL.md). Use [shared interview rules](../_shared/interview.md) for decisions, one question at a time. Use available skill discovery or read the linked files directly.

## 1. Inspect the repository

Read supplied agent guidance and inspect source layout, manifests, tool configuration, tests, existing documentation, and relevant decision records. Sample actual implementation boundaries, not just dependency names. Exclude generated code, vendored dependencies, credentials, and environment contents from the survey.

Identify:

- Active technologies and authoritative tool configurations.
- Existing standards, conventions, and conflicting practices.
- Important architectural boundaries, resource lifetimes, and integration choices.
- Evidence for decision rationale, and facts that remain unknown.

Use paths and relevant symbols as evidence. Configuration establishes configured checks, not that checks pass. Code establishes behavior, not historical intent. Inspect history only when available and relevant; a hosted repository is unnecessary.

This step is complete when each proposed document has a concrete scope and evidence, or is explicitly identified as a new policy proposal.

## 2. Establish the shared baseline

Read [baseline recipes](references/baseline.md). Create missing `docs/standards/general.md` and `docs/standards/dependency-injection.md` by default, scoped to the actual repository. These defaults are guidance for new or changed code, not claims that existing code already complies. Preserve framework-managed dependency lifecycles and document exceptions rather than prescribe a new architecture.

Reuse existing equivalent documents and link to them instead of creating competing authorities. Incorporate nonconflicting guidance in place; preserve user content and established names. When guidance conflicts, show the evidence and ask before replacing policy. Do not overwrite an existing standard with a template.

Read an explicitly supplied baseline source when available. Reuse only applicable guidance, not its project-specific scope, tool pins, paths, or historical exceptions. The bundled recipes also work when no template checkout is available.

Add technology-specific standards only for active technologies and demonstrated needs. Derive commands from current configuration. A Python repository need not adopt uv, Ruff, or strict mypy merely because this template uses them. Identify missing checks as proposals, not installed capabilities. Avoid a standard for every library.

Keep each standard short. Use focused Avoid / Prefer pairs where a distinction needs code, compact comparisons elsewhere, and no example comments or docstrings that repeat surrounding prose. Refer to authoritative configuration instead of copying its settings.

This step is complete when the shared baseline exists, applicable technology guidance has one owner, and conflicts are either resolved or explicitly awaiting a decision.

## 3. Recover decisions without inventing history

Read [domain-modeling](../domain-modeling/SKILL.md) before proposing or recording ADRs. It owns selection, format, and numbering. Existing ADRs remain authoritative unless explicitly superseded.

For each candidate, distinguish the observed implementation from the rationale supported by existing records. Ask the user to resolve missing consequential rationale or confirm a present-day decision. Explain alternatives and consequences using the actual repository. Never infer that an observed implementation was deliberately chosen over alternatives.

Write a qualifying ADR only after its decision and rationale are established by an authoritative record or explicit user confirmation. A present-day confirmation must not be presented as a historical decision. Link the relevant evidence without adding an audit transcript. Preserve existing ADR identities and allocate the next unused number under the domain-modeling rules.

An empty ADR result is valid. Create `docs/adr/` only when an ADR qualifies. Routine formatter, package manager, and dependency choices do not receive automatic ADRs.

Save each answered choice in the affected standard or qualifying ADR before asking the next question. For unresolved design work needing durable exploration, hand off to `grill-with-docs` under its own lifecycle rules. Do not create placeholder ADRs, a parallel decision ledger, specs, or tickets merely to bootstrap docs.

This step is complete when qualifying established decisions are recorded and remaining candidates are clearly unresolved, deferred, or rejected, not fabricated accepted ADRs.

## 4. Connect and verify

Link standards from existing agent guidance or documentation navigation. Keep one short pointer per applicability branch and put detailed policy in standards. Read [writing-for-agents](../writing-for-agents/SKILL.md) before editing agent guidance. If no guide exists, add a minimal root `AGENTS.md` describing observed scope and routing to the new standards, without importing unrelated template workflows.

Check local links and document claims against the inspected configuration and source. Use an already available documentation formatter or checker when safe and applicable; do not install tools or run unrelated application suites for documentation work. Review the result for conflicting authority, invented rationale, copied settings, secrets, and unnecessary prose. Remove empty placeholders created during this run, preserving pre-existing content.

Finish with created or updated documents, actual checks, and unresolved decisions or compliance gaps. Separate baseline adoption from verified implementation compliance. Do not claim a complete baseline while a required policy conflict remains unresolved. A later invocation must reuse the documents and identifiers rather than append duplicate standards or ADRs.
