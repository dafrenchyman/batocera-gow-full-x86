# Input transport image deployment tasks

- [x] Inspect current live Wolf app, image command, Steam lobby and activation constraints.
- [x] Confirm self-contained image packaging, no host helper/software, only owned app launch settings and authorized Wolf interruption.
- [x] Record the user's choice to leave repository Git state unchanged; remove the unnecessary SourceProvenance test/check change.
- [x] Add an explicit working-tree-content build identity without commits or Git mutation; retain committed-build behavior.
- [x] Package the root transport entrypoint and normalize additive runtime ownership/permissions/ACLs. Actual image UID-1000 smoke verified all 13 runtime source hashes, root-owned ancestors/tree, no writable modes/ACLs and rejected app write/create attempts.
- [x] Run relevant behavioral tests, including actual packaging ownership regression. Python discovery: 95 tests, one skip; real GPT/FAT/ext4/zstd and image metadata fixture passed.
- [x] Add and validate the whole runtime/emulator/input Mermaid flow in README.md. Split startup and input diagrams for readability; Mermaid 10.9.3 parsed/rendered in Chromium and screenshots reviewed.
- [x] Add and validate the build/copy-destination Mermaid flow in README.md, excluding deployment. Parsed/rendered and visually reviewed; geometry recorded in output/gow-full-x86/readme-flow-verification.json.
- [x] Build the complete image and pass stock-path/image-save inventory gates. Image sha256:c0cf25d69864b56890011039336d207854578329c5adf33e53b933789a38aa19; 112,729 stock paths matched, 21,786 isolated additions.
- [x] Load and verify the exact image on the Wolf server without a host helper service. Immutable-ID Docker-save/gzip/SSH load completed; remote --prepare --local passed exact identity, revision-label and packaged-prerequisite checks.
- [x] Perform the authorized stopped-Wolf app-only config update and restart; verify preserved unrelated settings. Only approved Steam/UI containers were stopped; Wolf restarted at 2026-10-27T06:58:57.180973726Z. Parsed unrelated config and API profiles matched; activated config hash a70d0c17f3fbea74f948d4ff8c0233f248e8a8b13a244df0b6db8a7c09a8a74c.
- [x] Smoke actual packaged ES and stock RetroArch shortcuts on Wolf; remove owned diagnostics. Final serialized run passed all three paths; completed ES and RetroArch menu/game screenshots reviewed. Eight owned lobbies/containers and five remote directories removed; registered image/config unchanged.
- [x] Record completed deployment, verified image identity, current state and physical-controller acceptance limit. completion.md and [current application state](../../../current/app.md) record the deployed image, approved restart, native evidence, retained initial timeout, scoped cleanup and unverified physical-controller/all-emulator acceptance.
