# Dependency injection

Apply these rules when assembling services, configuration and resources in every execution environment. Read [shared standards](general.md) and [Python](python.md). Explicit configured-dependency injection and deterministic ownership are required; a container library is not required for every helper.

[dependency-injector](https://python-dependency-injector.ets-labs.org/) may be used at assembly boundaries outside Batocera. Keep classes independent of containers and wiring markers. Exclude the library and its transitive dependency staging from the final Batocera runtime, and keep runtime imports free of it. This does not prohibit existing valid stock libraries such as Pillow, evdev and pyudev. The ephemeral SSH helper has its own stdlib-only delivery boundary; do not generalize that restriction to the image. See the [accepted runtime boundary](../completed/epics/repository-maturation/research/runtime-python-dependencies.md#decision-impact).

The provider examples below apply only outside Batocera. In runtime code, entry points assemble plain constructors and context-managed resources explicitly. Neither approach permits consumers to construct hidden configured production dependencies. These excerpts are not installed application scaffolds or permission to add a dependency.

## Inject configured dependencies

Inject initialized dependencies and validated configuration. The entry point chooses the source and assembles dependencies. Pass only the settings a component needs; individual typed values are fine when a configuration class adds no useful grouping.

Configuration types may explicitly load and validate files. The application boundary chooses the source and injects the validated object. Where the external container library is used, `providers.Dependency(instance_of=ReportConfig)` accepts that object. The library's [Configuration provider](https://python-dependency-injector.ets-labs.org/providers/configuration.html) supports other loading patterns, but missing-value checks do not replace domain validation.

### Avoid

```python
class ReportService:
    def __init__(self) -> None:
        self._config = ReportConfig.from_yaml(Path("config/report.yaml"))
        self._client = ApiClient(base_url=self._config.api_url)
```

The service chooses the file and constructs the client, preventing callers from supplying either dependency directly.

### Prefer

```python
class ReportService:
    def __init__(self, client: ApiClient, config: ReportConfig) -> None:
        self._client = client
        self._config = config
```

## Host settings and explicit dotenv loading

The host [settings module](../../src/batocera_gow/host/settings.py) uses host-only [python-dotenv](https://bbc2.github.io/python-dotenv/#load-configuration-without-altering-the-environment) with `dotenv_values` to parse an explicitly selected file. `HostSettings.resolve` creates an immutable invocation snapshot and consumers apply domain validation. Host commands select files through `--env-file`; no selection means no discovery. Keep the parser and its imports out of Batocera and the stdlib-only remote payload.

Resolve settings once at the command boundary or in the authorized native session fixture, then inject each consumer's required values. Preserve `os.environ`. Imports and pytest collection must not read dotenv files, construct global settings or populate a process-wide ambient settings cache. Local-only operations must not require or validate remote settings. Independent invocations/sessions resolve their own snapshots.

Explicit command overrides win over exported environment, then selected dotenv values, then safe defaults. Without an explicitly selected file, use the other sources without searching the working directory or ancestors for dotenv files. A missing/unreadable selected file or an invalid required setting is a nonsecret configuration error, not permission to use another target or silently fall back. Defaults apply to absent settings, not invalid supplied values.

Keep settings separate from authorization. A target or path in `.env` cannot opt a test into remote activity or bypass build-freshness, idle, ownership or cleanup gates. Do not stage private dotenv files or key material into images/payloads or dump settings in logs, reports or validation errors. Preserve ignored-file permissions and neutral examples. The implemented command/testing documentation must describe file selection and precedence.

## Treat injected resources as borrowed

Injected resources are borrowed unless their contract explicitly transfers ownership. The owner arranges deterministic cleanup through a context manager, `try/finally`, or framework lifecycle. Do not rely on destructors; Python's `__del__` has no timely-cleanup guarantee and cannot await async cleanup.

### Avoid

```python
class ReportService:
    def __init__(self, client: ApiClient, config: ReportConfig) -> None:
        self._client = client
        self._config = config

    def __del__(self) -> None:
        self._client.close()
```

The service closes a borrowed client that another consumer may still need. Moving the close call to another method does not fix ownership.

### Prefer

Use a [Resource provider](https://python-dependency-injector.ets-labs.org/providers/resource.html) for a shared client with deterministic cleanup:

```python
from collections.abc import Iterator
from contextlib import contextmanager

from dependency_injector import containers, providers


@contextmanager
def open_client(config: ReportConfig) -> Iterator[ApiClient]:
    with ApiClient(base_url=config.api_url) as client:
        yield client


class Container(containers.DeclarativeContainer):
    config = providers.Dependency(instance_of=ReportConfig)
    client = providers.Resource(open_client, config=config)
    reports = providers.Factory(ReportService, client=client, config=config)


def main(config_path: Path) -> None:
    container = Container(config=ReportConfig.from_yaml(config_path))
    try:
        container.init_resources()
        container.reports().generate()
    finally:
        container.shutdown_resources()
```

The container owns the client; services borrow it. Initialization is inside `try` so shutdown is attempted after partial startup failure too. Use async context managers for async resources, awaiting initialization, dependent provider calls, and shutdown. A resource is shared within its provider instance, not automatically scoped to each request.

## Separate stable dependencies from request inputs

Inject stable dependencies through constructors. Pass request-specific values as method arguments or a typed request object. Never store request-specific state on a shared service.

### Avoid

```python
def handle_report(service: ReportService, request: ReportRequest) -> Report:
    service.account_id = request.account_id
    service.start_date = request.start_date
    service.end_date = request.end_date
    return service.generate()
```

Concurrent requests can overwrite these fields, and `generate()` hides its required inputs.

### Prefer

```python
def handle_report(service: ReportService, request: ReportRequest) -> Report:
    return service.generate(request)
```

`generate()` receives account, date range, and format through the request, not shared mutable fields. A shared client must also support the intended concurrency.

## Inject factories for request-time construction

Use [Factory providers](https://python-dependency-injector.ets-labs.org/providers/factory.html) when construction needs request-time values or a fresh instance. Inject the provider itself through `.provider`, not the result of calling it. This replaces `partial()` without hiding the remaining inputs.

### Avoid

```python
reports = providers.Factory(
    ReportService,
    client_factory=account_client,
    config=config,
)
```

Without `.provider`, the container constructs a client while building the service, before the request supplies its account ID.

### Prefer

The service accepts a narrow callable contract, not a container:

```python
from typing import Protocol


class AccountClientFactory(Protocol):
    def __call__(self, *, account_id: str) -> ApiClient: ...


class ReportService:
    def __init__(
        self,
        client_factory: AccountClientFactory,
        config: ReportConfig,
    ) -> None:
        self._client_factory = client_factory
        self._config = config

    def generate(self, request: ReportRequest) -> Report:
        with self._client_factory(account_id=request.account_id) as client:
            return client.fetch_report(
                start_date=request.start_date,
                end_date=request.end_date,
                timeout_seconds=self._config.timeout_seconds,
            )
```

For this request-scoped alternative to the shared-client container above:

```python
class Container(containers.DeclarativeContainer):
    config = providers.Dependency(instance_of=ReportConfig)
    account_client = providers.Factory(ApiClient, base_url=config.provided.api_url)
    reports = providers.Factory(
        ReportService,
        client_factory=account_client.provider,
        config=config,
    )
```

The provider is borrowed. Each factory call returns a fresh client owned by its caller, so the service closes that client through `with`. `Factory` itself does not close its results. Create the client at the request boundary instead if its lifetime spans several services.

## Keep dependency contracts explicit

| Rule                                                                       | Avoid                                                                     | Prefer                                                                                                                                                    |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Require dependencies instead of silently constructing production defaults. | `self._client = client or ApiClient(...)`                                 | A required `client: ApiClient` argument. Put convenient assembly in a separate entry point.                                                               |
| Inject dependencies, not a service locator.                                | `container.resolve(ApiClient)` inside business logic.                     | A constructor receiving the client. Keep container resolution at the assembly boundary.                                                                   |
| Control nondeterminism when it affects decisions.                          | Reading the real clock inside expiration rules.                           | Pass `now` to an operation or inject a clock for repeated reads. Apply the same reasoning to randomness and ID generation.                                |
| Keep resource lifetimes compatible.                                        | An application-wide service retaining a request-scoped database session.  | A request-scoped service, operation argument, or factory creating a session for each operation.                                                           |
| Choose providers by lifetime, not convenience.                             | `Singleton` for a request-specific client or as a substitute for cleanup. | `Factory` for fresh instances; `Resource` for managed initialization and shutdown. `Singleton` only caches an instance and is not thread-safe by default. |
| Keep provider resolution at application boundaries.                        | `Provide[...]` or global container calls inside business methods.         | Constructor injection; wiring only in entry points or framework adapters when needed.                                                                     |
| Scope test replacements.                                                   | A global override retained across tests or requests.                      | `with container.account_client.override(providers.Object(fake_client)):` and a fresh container per test.                                                  |

Do not introduce an interface for every injected class. Use a concrete type unless a narrower contract or interchangeable implementations justify a Python `Protocol` or callable contract. Pure functions and immutable constants do not need injection merely to satisfy this standard.

See the official [Singleton](https://python-dependency-injector.ets-labs.org/providers/singleton.html), [wiring](https://python-dependency-injector.ets-labs.org/wiring.html), and [provider overriding](https://python-dependency-injector.ets-labs.org/providers/overriding.html) documentation. Override dependencies before resolving consumers; already-created objects retain their injected instances. Test overrides belong in isolated tests, not concurrent request handling.
