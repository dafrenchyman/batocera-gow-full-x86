# Python standards

Apply this profile to Python source, tests, stubs, and tooling configuration together with [shared standards](general.md).

## Environment and dependency ownership

Batocera leads interpreter compatibility. Host project environments use Python 3.12.x; the user's reported Nix-provided 3.12.12 is allowed. Disposable stock execution confirmed Python 3.12.8 and successful Pillow 11.0.0, evdev and pyudev 0.24.3 imports. The root `.python-version` and builder project interpreter select 3.12.8. This import evidence does not qualify the moved staged runtime or a new final image. Review the boundary on Batocera upgrades and verify native dependencies in the actual target.

uv owns project environments, dependencies and `uv.lock`, not OS Python. On NixOS, supply the Nix-provided interpreter explicitly through `UV_PYTHON` and disable managed downloads with `UV_PYTHON_DOWNLOADS=never`; do not assume generic downloaded interpreters run there. The builder provisions its project environment before networkless assembly and leaves Debian's OS interpreter intact. Leave stock Python untouched, and never copy host virtualenvs or native extensions into Batocera.

Root [project configuration](../../pyproject.toml) declares the installed `src/batocera_gow/` package, host/development dependency groups, Python checks and default pytest selection. Default `uv sync` includes the host and dev groups. The [layout standard](repo-layout.md) owns source/assets/test placement. Configuration and available hooks are not passing compliance evidence.

## Code and interfaces

- Use typed, explicit function boundaries. Choose concrete types for owned data and suitable protocols or abstract collection types for consumer contracts. Do not use `Any`, casts, or ignores to hide a mismatch that can be modeled correctly.
- Use normal annotation evaluation by default. Add `from __future__ import annotations` only when the module requires postponed annotation evaluation on a supported interpreter, and explain the concrete need in a nearby comment. Prefer a quoted forward reference for an isolated case. Do not add the import as boilerplate or solely to satisfy a lint preference.
- Put imports at module scope, after the module docstring and any required `__future__` imports, before other code. Use local imports only for a concrete requirement, such as an optional dependency or circular import, and explain the reason.
- Keep imports free of network calls, process execution, and other surprising side effects. Put CLI execution behind a main entry point.
- Use context managers for resources and keep ownership clear. Specify encoding for text files and distinguish text from bytes at I/O boundaries.
- Validate external data where it enters the program. Use exceptions for caller-actionable failure and preserve causes when translating errors. Catch specific exceptions, not every exception around an entire operation.
- Keep application validation separate from assertions. Assertions may be disabled by the interpreter and are not a reliable input contract.
- Avoid mutable default arguments and hidden shared state. Make mutation visible in the API, especially when a caller supplies a collection.
- Prefer cohesive classes for stateful domain concepts and orchestration. Use functions for pure stateless helpers.

## Modules and packages

- Give each module a cohesive responsibility. Separate CLI parsing and dependency assembly from transport, filesystem operations, validation and application orchestration when those concerns have independently meaningful contracts.
- Organize related modules into named packages when a feature spans multiple responsibilities. Follow [repository layout](repo-layout.md) for placement and preserve host, builder, runtime and remote-execution dependency boundaries.
- Keep entry points thin. They parse arguments, resolve configuration, construct collaborators and invoke application behavior. Reusable behavior belongs in importable modules.
- Keep coordinators focused on sequencing, state transitions and resource lifetime. Delegate transport, artifact handling and scenario-specific validation to cohesive collaborators or functions. Keep tightly coupled lifecycle and cleanup invariants together.
- Before extending a module, check whether the new behavior belongs to its existing responsibility. Extract an independently meaningful responsibility rather than continuing to append unrelated behavior.
- Treat module length as a review signal, not a quota. A split must improve ownership, dependency direction or independent testing. Avoid catch-all `utils.py`, numbered file fragments, and mixins that merely distribute one large class across files.

## Google-style docstrings

Document public APIs and non-obvious helpers with Google-style docstrings. Describe what arguments mean, the meaning of returned data, constraints, side effects, and caller-facing exceptions. Type annotations do not explain units, accepted values, ordering, or ownership. Omit sections that do not apply, but do not replace meaningful descriptions with type names.

For example, a parsing API can state the successful result and distinguish two invalid inputs:

```python
def parse_attempt_limit(raw: str) -> int:
    """Parse a bounded retry-attempt count from configuration text.

    Args:
        raw: Decimal integer text. Leading and trailing whitespace is accepted.

    Returns:
        The maximum number of attempts, including the initial attempt, between
        one and five inclusive.

    Raises:
        ValueError: If raw is not integer text or the count is outside the
            supported range.
    """
    try:
        attempts = int(raw, 10)
    except ValueError as error:
        message = "Attempt limit must be integer text."
        raise ValueError(message) from error
    if not 1 <= attempts <= 5:
        message = "Attempt limit must be between one and five."
        raise ValueError(message)
    return attempts
```

The docstring describes an actual contract, not every internal exception. Review it against the implementation and tests. Ruff checks conventions, not factual accuracy.

## Ruff linting and formatting

Ruff owns Python linting, import sorting and formatting. Root `pyproject.toml` enables ALL rules, disables preview and unsafe fixes, and documents formatter/docstring compatibility exclusions. It does not invent legal attribution where the repository has no copyright policy. Test-only assertion and independent expected-value literals, and deliberately non-package external launchers, have rule-specific scoped exceptions. Review newly enabled rules during upgrades. Configured rules do not establish passing whole-source checks.

Within authorized work, use safe fixes before formatting, then review changes and diagnostics:

```sh
uv run ruff check --fix .
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
```

Do not add parallel Black or isort defaults. A safe fix still needs review. Permit S101 narrowly for actual pytest test paths; test expected-value literals must remain independent of production constants. Retain unrelated rules and application assertion checks. Include Python and `.pyi` stubs. Configuration does not prove hooks are installed.

## Strict typing

Require strict mypy across applicable host, builder, runtime, remote-helper source and tests. It must see project dependencies and maintained stubs in the selected environment. Configure any isolated hook to use that environment deliberately, rather than inheriting blanket missing-import defaults.

Whole-project checks include `src/` and `tests/`, as selected by root mypy configuration. Supplied staged filenames and import following do not replace project-wide verification.

The checked remote modules under `batocera_gow.host.remote_payload` are packaged for stdlib-only execution. Preserve that context when adding annotations or imports; host parsers and development dependencies cannot leak into remote or final-image execution.

Prefer a typed dependency release or maintained stub package for an untyped dependency. If neither is available, suppress only the reported import error on that import and explain the limitation. An illustrative exception for a genuinely untyped vendor package is:

```python
import vendor_parser  # type: ignore[import-untyped]  # Vendor ships no typing metadata or available stubs.
```

Use the actual diagnostic code and real reason, not this example verbatim. Keep untyped results behind a small typed boundary. Do not set global `ignore_missing_imports`, disable strict mode, or suppress unrelated errors. Remove an exception when typing support becomes available.

## Tests and independent line coverage

Use pytest for behavior, boundaries, exceptions, state transitions and regressions. Assert meaningful results and observable side effects, using `pytest.raises` for failure contracts. Fixtures expose required setup and avoid shared mutable state. Parametrize shared contracts without obscuring why each case exists. Historical unittest and container/native results retain their original scope; they are not passing evidence for the moved pytest suite.

Follow [repository layout's test organization](repo-layout.md#test-organization). Keep `conftest.py` focused on fixture/configuration adapters and reusable behavior in checked application modules. Fixtures must clean up successful allocations even if later setup fails before `yield`; use explicit ownership and context managers or registered finalizers. Session-scoped preparation does not make mutable case state safe to share or guarantee exclusivity across pytest workers. Preserve separate native opt-in, build-freshness checks and run-level evidence/cleanup failures rather than interpreting passing test items as the entire native gate.

### Executable test fixtures

Keep test-only executable Python in maintained `.py` files under `tests/`, within the configured Ruff and strict mypy checks. This includes one-line subprocess programs, nested children and generated executable wrappers. Use guarded entry points and invoke helpers by file path or module name. Pass variable inputs through arguments, stdin, files or explicit environment values, not source interpolation.

Do not embed test programs in strings passed to Python `-c`, `exec` or `eval`, or generate them by concatenating Python source. If a transport or wrapper needs source bytes, read or copy a maintained `.py` fixture without templating its code. Strings remain appropriate for data under test, such as logs, configuration, tracebacks and Python text supplied to a parser.

Preserve interpreter flags, readiness and stdio protocols, descriptor lifetimes and cleanup when extracting helpers. Keep application subprocesses covered; stdlib-only synthetic children may retain their explicitly justified `-S` isolation. See the checked fixtures beside the [local integration tests](../../tests/integration/local/).

### Application coverage

Require at least 80% application line coverage, independently measured from branch results or tooling-only tests. Include all applicable application source under `src/batocera_gow/`, including unexecuted builder, runtime, remote and native coordinator modules. Historical Wolf-integration coverage and inherited-file exceptions do not apply to modernization.

Keep branch reporting enabled and inspect untested decisions, without a separate numerical branch floor. Do not exclude meaningful code to reach the line floor. Explain justified exclusions and preserve execution-environment boundaries when combining measurements.

The independent gate must consume a fresh report from the same test run and enforce lines independently. Coverage.py's branch-enabled combined percentage alone is insufficient. Missing reports, invalid measurements/counts or nonfinite thresholds must fail rather than count as coverage success. Root configuration enables branch reporting over `batocera_gow`; the permanent independent coverage gate belongs to modernization ticket 02. This documentation update establishes no current application percentage or passing gate.
