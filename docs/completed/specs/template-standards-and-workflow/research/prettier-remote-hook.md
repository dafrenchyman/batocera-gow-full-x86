# Remote Prettier hook assessment

## Conclusion

The pinned rbubley/mirrors-prettier hook is a reasonable candidate for the template's plugin-free formatting baseline. No suspicious wrapper or install script was found in the inspected mirror files. This is not certification that the repository or the entire Prettier distribution is uncompromised.

Adopt the reviewed SHA for the plugin-free baseline, keep project and hook versions aligned, and review updates before changing the pin. Prefer remote hooks where suitable; local hooks remain acceptable when a remote integration cannot meet project requirements.

## Inspected target

- Repository: https://github.com/rbubley/mirrors-prettier
- Release: v3.9.10
- Reviewed commit: 331f33fa4dfbcbca7c3da3620c137fde0faab273
- Hook entry: prettier --write --ignore-unknown
- Hook language: node
- Hook dependency: prettier@3.9.10

Primary sources:

- Complete pinned tree: https://api.github.com/repos/rbubley/mirrors-prettier/git/trees/331f33fa4dfbcbca7c3da3620c137fde0faab273?recursive=1
- Hook manifest: https://github.com/rbubley/mirrors-prettier/blob/331f33fa4dfbcbca7c3da3620c137fde0faab273/.pre-commit-hooks.yaml
- Package manifest: https://github.com/rbubley/mirrors-prettier/blob/331f33fa4dfbcbca7c3da3620c137fde0faab273/package.json
- Maintainer workflow: https://github.com/rbubley/mirrors-prettier/blob/331f33fa4dfbcbca7c3da3620c137fde0faab273/.github/workflows/main.yml

## Consumer execution and security boundaries

The mirror has eight files and no custom JS, Python, or shell wrapper. Its package.json is placeholder metadata with no scripts or dependencies. The consumer hook invokes the npm-published formatter, not the mirror's generation workflow.

The npm prettier@3.9.10 package manifest has no lifecycle scripts or external dependencies. The downloaded package manifest and CLI bootstrap were inspected, not every bundled parser or formatter implementation. The bootstrap loads Prettier's CLI and checks the supported Node version; no suspicious payload was found in those inspected files.

Pre-commit's Node environment installation is not a security sandbox. npm dependencies can execute lifecycle scripts, and formatter plugins and JavaScript configuration can execute code. Run hooks only on trusted project configuration; additional plugins expand the trust boundary.

Pinning the full Git commit prevents an upstream tag move from silently changing the mirror files. It does not independently pin the npm tarball's expected integrity, Node runtime, or plugin transitive dependencies. Source: https://github.com/pre-commit/pre-commit/blob/v4.3.0/pre_commit/languages/node.py.

The downloaded Prettier tarball matched npm's published integrity metadata:

sha512-skGHTH1Yb9QvaTC4hWnRTzEYtCpApF0UMBPz+t/0ZPzP8ihefo/btKd+QA7pUE0fEwA1SbS/NmhyEcstdXOIdA==

Source: npm view prettier@3.9.10 dist.integrity and npm pack prettier@3.9.10 --ignore-scripts --json. Agreement with registry metadata is not an independent source-to-binary verification.

## Maintenance and upstream risks

GitHub metadata reports the repository is not archived, with an October 11, 2026 push and current release tags. The reviewed release commit updates version/dependency metadata. Public issue inspection found no compromise report in the returned inventory; that does not prove absence of compromise.

The generation workflow uses old checkout@v1 and setup-python@v1 action tags, installs an unpinned mirror-maker from Git HEAD, and publishes generated commits and tags without consumer smoke tests. These are upstream publication weaknesses, not actions run when a consumer installs this pinned hook. Review updates instead of trusting automatic tag generation.

The original mirror is archived because plugin integration broke, and the fork's plugin example still uses older Prettier conventions:

- https://github.com/pre-commit/mirrors-prettier
- https://github.com/rbubley/mirrors-prettier
- https://prettier.io/docs/plugins

## Runtime evidence

Executed the actual pre-commit hook in a separate temporary Git repository using the reviewed full SHA. No project hook configuration was changed and no commits were created.

| Scenario                                                                                       | Observed result                                                                                      |
| ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Plain TSX, JSON, CSS, Markdown, and YAML fixtures                                              | First run rewrote files and exited 1 as expected; second all-files run passed                        |
| Plugin configured as @prettier/plugin-xml, installed only through hook additional_dependencies | Failed with Cannot find package '@prettier/plugin-xml' imported from the temporary project's noop.js |
| Same plugin installed in the temporary project, pinned at 3.4.2                                | Remote hook formatted XML; second all-files run passed                                               |
| npm audit signatures for the temporary project's five installed packages                       | Five verified registry signatures and one verified attestation reported                              |

The signature check authenticates registry metadata for the installed packages. It does not certify benign behavior, audit all source, or identify which package had the attestation in the displayed output.

The plugin fixture was a compatibility experiment, not a proposal to add XML or Tailwind dependencies to the template. No Tailwind plugin was exercised.

Consumer additional_dependencies replaces the hook manifest's dependency list. If adding plugins there, repeat the exact Prettier version as well; do not accidentally lose the formatter pin. Source: https://github.com/pre-commit/pre-commit/blob/v4.3.0/pre_commit/repository.py.

## Recommended adoption conditions

- Pin the reviewed full SHA, with its release version noted for humans.
- Restrict file filters to intended frontend/document formats; retain Ruff and Alejandra for Python and Nix.
- Keep hook and project Prettier versions aligned.
- Use a supported Node runtime compatible with the chosen environment.
- Review hook/package changes before updating the pin and repeat actual hook smoke verification.
- Verify each selected plugin's resolution separately. Installing it only in the hook environment is not sufficient for the tested project-relative configuration.
- Do not claim the mirror is guaranteed safe or uncompromised. A stronger assurance requirement would need deeper dependency/source and provenance review.
