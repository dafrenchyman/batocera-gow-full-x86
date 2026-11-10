# Deployment implementation review

## Privileged runtime ownership

The pre-implementation security review identified DEPLOY-RUNTIME-OWNERSHIP-001. The original numeric-owner-preserving runtime copy would let source UID 1000 own Python code executed by the root supervisor.

The implemented correction applies only to the additive runtime namespace: rsync --chown=0:0 --chmod=go-w, followed by recursive access/default ACL removal. The real assembly fixture supplies app-owned writable source files and named/default ACLs, extracts the final archive, and verifies root ownership, no group/other writes and no ACLs. That fixture passed.

PackagedRuntimeReview found no actionable defect in the correction, approved-name/stopped-Wolf activation transaction, or owned-lobby smoke procedure. Actual built image sha256:c0cf25d69864b56890011039336d207854578329c5adf33e53b933789a38aa19 then passed application-UID-1000 inspection: 13 source content hashes matched, runtime and ancestors were root-owned, write modes/access/default ACLs were absent, and write/create attempts were rejected. Evidence is output/gow-full-x86/input-transport-image-integrity.json. The same boundary was inspected in native Wolf lobbies. This closes the packaging ownership finding.

## Build identity

BuildIdentityReview found no concrete blocker. The working-tree manifest covers contents, modes, directory entries and new helpers, excludes transient Python caches, and records a distinct worktree identity/tag. Guards recheck source before packaging and promotion. Default committed builds retain their original Git-cleanliness check. Local preparation checks exact image ID and revision labels. No Git command, test, build or edit was run by either reviewer.

## Native verification and transient timeout

The selected image passed a serialized native run covering the normal ES entrypoint, five stock receiver cases and actual stock-configured RetroArch. Completed ES and RetroArch game/Quick Menu screenshots were reviewed. Guide + ES logical b (physical Xbox A in this profile) opened Quick Menu; Guide+Start exited the pinned emulator with stock launcher status 0. The controller profile and stock input hashes were unchanged.

The first combined run timed out waiting for receiver readiness. Isolated frontend and receiver checks passed. Only the temporary coordinator was changed: wait for frontend transport readiness and complete owned container removal between cases. The unchanged image then passed the full run. The exact initial transient cause was not established; do not present this as a production fix or an exhaustive reliability result. The first failure and final results are retained under output/gow-full-x86.

Final cleanup verified eight owned lobbies/containers absent, removed five owned remote diagnostic directories, and confirmed Wolf running with the selected image/config unchanged. Temporary local operator coordinators were removed after verification. No unrelated container or persistent data was removed.

## Accepted limits

SYS_PTRACE remains an explicit app-runner prerequisite. Private namespaces do not solve stale event-node/device-number reuse. Physical Moonlight-controller and all-emulator acceptance are outside synthetic native smoke evidence. No upstream source patch, host helper service, overlay or per-emulator remap is introduced.
