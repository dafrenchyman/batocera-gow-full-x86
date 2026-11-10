# Baseline recipes

Use these recipes only when the target repository lacks equivalent guidance. They specify minimum content for generated standards, not a replacement for existing policy. Adapt examples and terminology to the target repository. Apply technology defaults only to the matching language.

Existing policy and the skill's conflict review take precedence over these recipes. When adoption is deferred, omit conflicting rules and examples from active guidance, record the unresolved scope briefly in the affected standard, and report a partial baseline.

## Shared standards

Create a concise `docs/standards/general.md` covering:

- Applicability from actual source and configuration, with links to relevant standards.
- Small responsibilities, explicit boundaries, clear failure behavior, and reuse of established conventions.
- Secret handling and diagnostics that do not expose credentials or sensitive payloads.
- Behavior-focused tests covering meaningful outcomes, failures, and boundaries. Separate configured checks from observed passing results.
- Documentation of contracts and non-obvious constraints. Use direct prose, sentence-case headings, no em dashes, and no activity logs.

Reference configuration for exact tools, commands, versions, and rule settings. Do not import coverage thresholds, mandatory tooling, or repository layout from an unrelated project. Describe discovered compliance gaps without turning this documentation task into implementation.

## Dependency injection

Create `docs/standards/dependency-injection.md` by default. For Python, prescribe [dependency-injector](https://python-dependency-injector.ets-labs.org/) for application dependency assembly unless existing policy requires a reviewed exception. This is documentation guidance, not permission to install or migrate the library. Keep React guidance separate. Cover these rules concisely:

- Inject configured dependencies and validated configuration. Configuration types may load files explicitly, but the application boundary chooses the source. Pass only relevant settings; an application-wide settings object is not required.
- Injected resources are borrowed unless ownership transfers explicitly. Owners arrange deterministic cleanup through context managers or the framework lifecycle, not destructors. A consumer must not retain a shorter-lived resource beyond its valid scope.
- Separate stable dependencies from request inputs. Keep request state off shared service instances.
- For Python, use `DeclarativeContainer` with `Factory` for construction, `Resource` for managed cleanup, and `.provider` when injecting a factory rather than its result. Keep validated configuration objects and plain constructor arguments. `Singleton` does not arrange cleanup or automatically provide request isolation or thread safety. Use explicit request-time factory calls instead of `partial()`; state ownership of factory results.
- Require dependencies explicitly instead of silently constructing production defaults. Resolve containers at assembly boundaries, not inside business logic.
- Control clocks, randomness, and ID generation when they affect decisions. Pure functions and immutable constants do not need injection merely to satisfy a rule.
- Use concrete types unless a narrower contract or interchangeable implementations justify an interface. Do not require an interface for every class or a container for pure helpers.

Use paired Avoid / Prefer examples for configured dependencies and request-time factory construction. Reuse one small domain scenario and show cleanup ownership. Explain its contract in prose instead of repeating it in example comments or docstrings. Compact comparisons are sufficient for the remaining rules.

For React repositories, also cover props for local dependencies, Context for subtree-wide dependencies, clear errors for missing required providers, stable client identity within its intended lifetime, and isolation of user-specific dependencies during server rendering. For frameworks with managed dependency scopes, use their native lifecycle rather than inventing a parallel container.

## Repository-specific additions

Create another standard only when active source and configuration give it a useful scope. Explain project conventions and non-obvious constraints, linking to authoritative configuration rather than reproducing it. Prefer one focused language or platform standard to a file per tool.

Repository inspection may expose a consequential choice instead of an established convention. Ask about that choice before writing it as policy. Keep proposed behavior separate from current implementation and accepted decisions.
