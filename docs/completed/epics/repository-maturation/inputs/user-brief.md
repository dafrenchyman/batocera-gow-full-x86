# Repository maturation intake

The user reports committing the current changes. This is exploration under grill-with-docs, not implementation, deployment, publication, hook installation or Git authorization.

## Requested outcome

Make this repository better for automated AI development, using `/path/to/ProjectTemplate` as the reference. The user copied its docs folder into this repository before this request.

## Concrete requests

- Add project-specific root guidance such as `AGENTS.md` and `GLOSSARY.md`.
- Clean up the existing code's organization and style, following `docs/standards`, including proper docstrings.
- Bring over the applicable ProjectTemplate pre-commit hooks.
- Add Yelp detect-secrets to reduce accidental secret commits.
- Treat the project as past the experiment phase. Consider moving `experiments/gow-full-x86/` into `src` or another appropriate maintained layout. The user is flexible and requests a recommendation.
- Formalize the real Wolf verification used during development into proper integration tests. The user specifically values SSH execution on the Wolf system and screenshot evidence of real behavior.
- Add a testing README explaining how that remote verification and screenshot capture works, how to run it and what the evidence establishes.
- Remove personal SSH connection details and private-key filenames from shared source. The user requests environment-based connection configuration so others can use the repository without inheriting the operator's machine-specific settings. A filename is not private-key material, but still exposes personal configuration and prevents reuse.

## Existing safety context

The working system wraps complete stock Batocera, preserving Batocera/Wolf/games-on-whales sources and controller/configgen behavior. Earlier user decisions reject a universal overlay, per-emulator patches and host-installed runtime helpers. The current user confirms the deployed shortcut changes work in the emulators tried. The published/deployed image is the working reference, not proof of every emulator or shortcut.

Prior permission to restart Wolf or publish an image was specific to that rollout. This exploration does not reuse that permission for new integration runs, production changes, commits or pushes. Existing games, BIOS content, paired-client credentials, app state and unrelated projects must remain protected.
