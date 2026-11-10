# Batocera Wolf integration

Language for complete stock Batocera packaging, additive integration and the evidence used to distinguish their behavior.

## Language

### Payload and integration

**Stock payload**:
The complete official Batocera userspace, including its original files, metadata, emulator configuration and input mappings. It is distinct from the selectively built GoW runtime.

**Additive integration**:
Project-owned packaging, startup and input transport added around the stock payload without replacing upstream sources or stock mappings/configgen.

### Input and actions

**Guide button**:
The physical controller's Guide control, used with another control to request a stock shortcut. It is an input, not an emulator menu action.
_Avoid_: Menu button when referring to Guide.

**Emulator menu action**:
A backend-specific action that opens an emulator's menu when supported and configured. A configured Guide combination does not imply that every emulator has such a menu.

**Client/physical input**:
Controller input originating at the client and forwarded toward the Wolf session. This observation point is distinct from input generated inside the server session.

**Session-owned synthetic gamepad**:
A virtual gamepad created by an owned process within a particular native session. Its generated input can exercise server-side consumers without proving physical-controller forwarding.

**Stock shortcut processing**:
Batocera's existing mapping and context processing that translates controller combinations into keyboard, pointer or command actions. It is distinct from both source controller events and the final consumer's response.

**Consumer-visible output**:
The input or resulting action observed by the actual frontend, emulator or other target application. An intermediate transport event alone is not evidence of this output.

### Application, session and state

**Wolf application**:
A configured launch entry with a runner identity. Its configuration can outlive many individual sessions and containers.

**Runner identity**:
The configured runner name associated with a Wolf application and used in native home selection. It is not the identifier of an individual running container.

**Native session**:
An individual Wolf-managed execution with its own runtime resources. A session is distinct from the persistent application configuration and home.

**Lobby**:
A Wolf UI session that clients can join or rejoin. Disconnecting and rejoining does not establish a new lobby or a fresh application lifetime.

**Session container**:
The container executing an application's runtime for a particular session. Its removal is distinct from removal of the configured application or persistent userdata.

**Production userdata**:
Persistent application state, including configuration, saves and caches, retained across production sessions. Read-only content mounts do not make userdata disposable or prevent writes to it.

**Disposable test userdata**:
Independently owned state for a bounded test run, separate from production userdata. Its disposability derives from ownership and isolation, not merely from a temporary-looking name.

### Artifact identity

**Docker image ID**:
The content digest of an image's configuration object used to identify the local image. It is not the registry manifest digest.
_Avoid_: Registry digest when referring to an image ID.

**Registry manifest digest**:
The content digest identifying the registry manifest used for a digest-pinned image reference. That manifest refers to image configuration and layers; its digest is distinct from the configuration's image ID.

**Image tag**:
A registry or local name pointing to an image version. A tag can move and is not itself a content digest.

**Source revision**:
The version-control identity of committed source. It does not identify uncommitted build-input changes.

**Worktree content fingerprint**:
A content-derived identity for the selected working-tree build inputs. It is distinct from a source commit, built image ID and registry manifest digest.

### Evidence boundaries

**Image qualification**:
An evidence-backed result for one immutable image and its corresponding source inputs across the required preservation, packaged-runtime, host and native checks. Its scope excludes untested media, unselected catalog mappings and unobserved client behavior.

**Server-side input evidence**:
Observations of generated or forwarded events and actions inside the server session. Synthetic-input results do not establish physical-controller forwarding from a client.

**Server-side render evidence**:
Pixels captured from the application's server display. They do not establish video decoded and displayed by Moonlight.

**Client-decoded video**:
Video decoded and displayed by the streaming client. A server screenshot or live emulator process is not evidence of this outcome.

**Heard client audio**:
Audio actually heard at the client. A server-side audio stream or assigned sink alone does not establish it.
