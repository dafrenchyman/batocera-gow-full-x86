# Research: temporary Wolf test homes

## Question

Can /tmp provide disposable integration-test userdata without changing Wolf or adding conflicting home mounts? The user first proposed /tmp, then accepted temporary homes under the existing shared state tree with a configurable root and /etc/wolf default. The findings below explain the path constraint; this choice is not execution permission.

## Context

Owner: [repository maturation](../explore.md#reproducible-real-wolf-integration-and-testing-readme). Regression-first sequencing is accepted. Native test state must not accidentally modify the working home.

## Method

Read native lobby, session and Docker runner source at the previously recorded Wolf revision ee271038da2b81c9e54c28c9daa7558692d415d6. Read retained local deployment records. No SSH, live mount inspection, directory creation, lobby launch or test ran. Source establishes path construction, not the current server's /tmp mounts.

## Evidence

- [Lobby API endpoint](https://github.com/games-on-whales/wolf/blob/ee271038da2b81c9e54c28c9daa7558692d415d6/src/moonlight-server/api/endpoints.cpp): CreateLobbyRequest accepts runner_state_folder and a runner, then emits CreateLobbyEvent. Creating an owned diagnostic lobby does not inherently require registering a new persistent app.
- [Native lobby setup](https://github.com/games-on-whales/wolf/blob/ee271038da2b81c9e54c28c9daa7558692d415d6/src/moonlight-server/sessions/lobbies.cpp): Wolf constructs a local state path from local_base_state_folder and runner_state_folder, creates directories there, and separately constructs the Docker-host path from host_base_state_folder and the same runner_state_folder.
- [Session runner setup](https://github.com/games-on-whales/wolf/blob/ee271038da2b81c9e54c28c9daa7558692d415d6/src/moonlight-server/sessions/common.cpp): the host state directory is automatically bound to /home/retro; its udev child is bound to /run/udev. The local and host path views must identify the same backing state.
- [Docker runner](https://github.com/games-on-whales/wolf/blob/ee271038da2b81c9e54c28c9daa7558692d415d6/src/moonlight-server/runners/docker.cpp): fake-udev files are created using the local app-state path before app startup. A home directory that exists only in the app container cannot replace this shared metadata path.
- Prior project records establish the working home under /etc/wolf/profile-data/user/WolfExperimental and reject an extra manual /home/retro bind. They do not establish that Wolf's /tmp and the Docker host's /tmp share storage.

## Findings

Scratch files and transient result staging can use a private run-owned temporary directory in whichever environment performs the operation. Avoid a predictable shared directory, unsafe symlinks and cleanup based only on a name. Export intended screenshots/results before deleting run-owned scratch.

Literal host /tmp as the whole native home is conditional. Wolf's local path and the Docker host's bind source must refer to the same backing directory. Absolute /tmp paths can escape the usual base translation and refer to different private filesystems. A symlink into /tmp is not a substitute for verifying shared storage. Existing /tmp sharing on the current server is unverified; changing Wolf's mounts would be a separate configuration change, not an image-only operation.

A source-supported design is a unique relative runner_state_folder under Wolf's already shared state root, for example test-runs/<run-id>. The user accepted this direction with a configurable Docker-host state root, default /etc/wolf. Derive the host path from that setting and preserve Wolf's separate local-root translation; do not hardcode a shared absolute root in both namespaces. The resulting home is automatically exposed as /home/retro without reusing WolfExperimental userdata. Temporary lifetime does not require literal /tmp. Actual configured root mapping and ownership need later authorized validation.

Persistence tests can keep the same disposable home across their own fresh lobbies. The user accepted cleanup on both success and failure: retain selected evidence locally, confirm owned lobbies/containers absent, then remove only verified run-owned userdata. Attempt cleanup even if evidence collection fails; loss of access or uncertain ownership must produce an explicit cleanup failure rather than unsafe deletion or a green result. Local evidence privacy/retention details remain open.

## Dead ends and failures

No runtime experiment was performed. Do not assume host /tmp, Wolf-container /tmp and app-container /tmp are the same filesystem. Do not add a duplicate manual home bind or use a symlink escape to force a temporary path while claiming unchanged native home semantics.

## Decision impact

The user selected disposable per-run state under the existing Wolf-shared root, with a configurable host root and /etc/wolf default. Literal /tmp is not required. This avoids introducing a new Wolf mount as a design prerequisite, but the harness must validate the selected host/local root mapping before writes. Changing its configuration does not itself change Wolf's installation. Private /tmp scratch remains possible.

## Follow-up questions

Choose legal controller/content fixtures, operational identity stability, configuration syntax and local artifact retention/redaction. The cleanup-on-failure default is resolved. No planning choice authorizes execution.
