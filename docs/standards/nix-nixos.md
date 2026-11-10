# Nix standards

Apply this profile to Nix expressions, runtime closure inputs and optional development environments together with [shared standards](general.md). This project does not manage a NixOS host. The filename is retained for existing references, not as a host-management requirement.

## Runtime inputs and ownership

[bridge.nix](../../build-assets/bridge.nix) imports a revision-pinned Nixpkgs tarball for `x86_64-linux` and selects Xwayland, xauth, util-linux and Mesa. [Host build orchestration](../../src/batocera_gow/host/build.py) evaluates and builds those outputs and inventories their requisites for the packaged runtime closure. Preserve those runtime inputs and their provenance independently of any development environment.

Review input updates deliberately. The current expression pins a revision in its URL; it is not a root flake lock or a claim of content-hash verification. Preserve package override contracts and explicit target systems when changing expressions. Do not replace the runtime selection with whatever packages happen to be on the developer's host.

## Optional development environments

No root flake or developer shell is currently configured, and neither is required to satisfy this standard. If a development flake is adopted later, use reviewed stable inputs and retain its lockfile. Keep shell composition separate from runtime package selection. A shell supplies executables; uv retains ownership of project Python environments and dependencies.

On NixOS, follow the [Python interpreter policy](python.md#environment-and-dependency-ownership) for the supplied 3.12.x interpreter and disabled uv-managed downloads. Do not change OS Python or require a managed host just to supply development tools. System-wide tools remain a valid entry path. Report actual tool versions and platform when providing evidence.

## Expression quality

- Keep expressions small and explicit. Name repeated or non-obvious values with `let`; prefer explicit attribute access or `inherit` over broad `with` scopes.
- Pass dependencies as function arguments. Avoid ambient host package selection or undeclared filesystem/environment inputs.
- Keep overlays narrow and preserve caller override points. Split supporting files only when they clarify a real responsibility.
- Keep secrets out of Nix source and store paths. Untracked plaintext and repository permissions do not make evaluation output private.

## Formatting and verification

Alejandra owns formatting. Statix and deadnix are check-only; normal checks must not apply structural fixes or remove bindings automatically. Once available within the authorized work, target the actual expression paths, not an absent `flake.nix`:

```sh
alejandra --check build-assets/bridge.nix
statix check build-assets/bridge.nix
deadnix --fail build-assets/bridge.nix
```

These are policy entry points, not a claim that hooks are configured or these checks passed. Review formatter changes and resolve static findings manually. Confirm caller contracts before removing arguments flagged by unused-argument analysis; use only narrow explained exceptions for legitimate forwarding.

Static checks do not evaluate or build the runtime closure. For authorized expression changes, evaluate and build affected attributes through the actual build interface, then exercise runtime effects where required. If a flake is later introduced, run its declared checks outside hooks as well. An absent flake creates no flake-check obligation.

Report actual systems and outputs exercised. Evaluation is weaker than a build, and a build is weaker than runtime proof. This runtime selection targets x86_64 Linux; neither cross-system evaluation nor a successful local build establishes another platform's behavior. Builds and checks never authorize activation, deployment or service interruption.
