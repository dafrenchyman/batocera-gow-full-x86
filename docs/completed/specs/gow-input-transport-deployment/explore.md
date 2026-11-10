# Input transport deployment decisions

## Upstream boundaries

Keep Batocera controller mappings, hotkeygen, configgen and emulator generators unchanged. Keep Wolf and games-on-whales source unchanged. The project packages its existing runtime and transport helpers inside the image. No universal overlay, emulator-specific patch, host helper service or source mount.

## Image and launch settings

The original host-mounted helper proposal is superseded by the user's request for a self-contained image. The image ENTRYPOINT wraps entrypoint.sh with input_transport.py; frontend.sh remains Cmd. The owned WolfExperimental runner selects the immutable new image ID, adds SYS_PTRACE to existing NET_ADMIN/SYS_NICE and explicitly uses private bridge networking. Preserve private PID/IPC, default seccomp, native home and read-only content binds. Image contents cannot grant a Docker capability.

The stale event-node/device-number reuse exposure remains accepted for this experiment, not solved by deployment. Private network namespaces contain fake-udev notifications; they do not establish strict kernel input-device isolation.

## Privileged runtime ownership

The diagnostic used a root-owned read-only helper mount. Packaging with the original rsync flags would instead preserve source UID 1000 into root-executed Python files. Normalize only the additive runtime tree to root:root, remove group/other writes and strip access/default ACLs. A real assembly fixture supplies UID-1000-owned writable files and inherited ACLs and checks the packaged result. Inspect actual deployed image metadata and application-UID write rejection before closing the security finding. Stock owners, modes and ACLs remain inventory-protected.

## Git and local delivery

The user selected leaving Git unchanged. The interim change to scope the cleanliness check and its SourceProvenance Git-fixture test were removed. Default committed builds retain the original clean-checkout requirement. Explicit --working-tree mode hashes current build-source files, directories and permission modes, excludes Python caches, rejects links/special files and detects source drift before image promotion. It records an honest worktree-sha256 identity and a worktree image tag, never a fabricated Git commit. No commit, staging, push or Git configuration change.

Use the complete official 43.1 input and all stock/image-save inventory gates. Assembler-source changes use a fingerprint-keyed assembly directory so old caches remain intact. Transfer only the verified image, with no GHCR publication.

## Authorized activation

The previous instruction to preserve Wolf's uptime is superseded. The user explicitly permits changing config.toml and stopping/restarting Wolf. The initial Steam lobby was 77ac4288-102a-4003-975d-0460169efe5b, with zero connected clients, and Wolf UI was active. They may be interrupted by this authorized restart; persistent data and unrelated configuration remain protected.

The pinned Wolf API has no safe live app update. Profile remove/re-add loses unrelated fields and is rejected. Stop Wolf and only captured approved Wolf app containers as needed, then apply the existing compare-and-atomic-write transaction with a confirmed-stopped quiescence check. Transform only the owned app table. Verify API recovery, exact new image selection and equality of all unrelated parsed settings. Do not weaken the normal idle-gated --register command for this one authorized rollout.

## Verification

README must show startup and stock emulator lifecycle, input forwarding, and a separate build/copy-destination flow without deployment. Parse and render Mermaid. Launch a native Wolf lobby with the image's default entrypoint and frontend for ES proof, then a separate owned diagnostic lobby using only the packaged emulator probe as a temporary Cmd. Inspect capabilities, namespaces, source integrity and mount boundaries before opening the input gate. Observe real RetroArch menu/exit and retain screenshots. Physical Moonlight-controller and all-emulator behavior remain operator acceptance, not synthetic-test claims.
