Historical exploration, consolidated 2026-10-28. Storage-blocked notes below predate the delivery and runtime continuation retained by the 2026-10-26 handoff. The operator subsequently confirmed the effort finished. See the [spec disposition](spec.md) and [current application state](../../../current/app.md); no older pending finding is converted into new verification.

# Implementation decisions

The approved spec is the contract. Original source is read-only reference, never a build input. This repository packages official 43.1 userspace and adds an isolated startup adapter. Wolf owns the experiment home and injected sockets/devices. No explicit home bind is added. Remote activation requires empty sessions/lobbies and no app runners, with the upstream concurrent-session race disclosed.

# Verification status

Independent directory and standalone .git created. No original repository Git commands or mutations performed. Product tooling and deterministic fixtures are verified in tasks.md. Real complete-image build, publication, deployment, and remote runtime acceptance remain blocked on local storage.

## Metadata-preserving image packaging

A real tiny-image smoke exposed Docker BuildKit ADD dropping a file xattr and directory timestamp precision. The final archive is now streamed as an exact Docker-save layer into Docker load. Its config carries the entrypoint, default frontend command, root setup identity, working directory, marker environment and provenance labels. Full image-save stock inventory verification passed on this route, without changing the comparison rules. This changes packaging mechanics, not stock payload or runtime scope.

## Fixture corrections

SquashFS does not encode the fixture's POSIX ACL namespace; ACL round-trip coverage belongs to ext4 SHARE instead. Main-layer directory ownership, mode, timestamps and ordinary file xattrs remain checked. The stock population script preserves an existing seeded BIOS directory rather than merging datainit BIOS into it; the state fixture now checks the shipped SHARE BIOS content accordingly.

Real libasound evaluation exposed a missing mandatory getenv default field in the scoped ALSA configuration. Empty syntactic defaults were added, with runtime validation still requiring the actual Wolf server and sink. The test uses libasound's in-place evaluation API and verifies resolved Pulse session values.

## Review findings

Read-only reviews found fixed scratch directories blocking build retries and an idle predicate missing numeric direct-Moonlight runner suffixes. Build orchestration now cleans recognized failed staging only if its own invocation began with an empty tree, retains verified input, and creates fresh inventory scratch per run. Both idle predicates cover numeric session IDs and UUID lobbies; transaction tests require no config/restart change for running or paused numeric runners.
