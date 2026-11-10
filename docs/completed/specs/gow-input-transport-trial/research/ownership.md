# Synthetic-device ownership probe

## Question

Can an experiment-owned runtime supervisor identify a uinput device without relying on names or exposing all host input devices?

## Method

Run disposable networkless containers using the exact deployed image on the real Wolf host. Keep state mounts absent and expose only `/dev/uinput`. The probe launches the image's existing `runtime.py hotkeys` action as its own child. It duplicates that child's uinput descriptor with `pidfd_getfd`, queries `UI_GET_SYSNAME`, reads the corresponding sysfs event device number, and creates only that node inside the disposable container. Original-repository helpers are not executed.

## Observed results

- Remote Docker server version: 27.5.1.
- Host descriptor query against the caller's own descriptor succeeded.
- Default disposable-container query failed with EPERM, errno 1.
- Adding SYS_PTRACE in the private container PID namespace permitted the same query.
- The first stock daemon probe exposed owned kernel input180/event9 but failed because the disposable probe had not created `/var/run`.
- Creating `/var/run` exposed input181/event9, then failed opening the node because the disposable container lacked input-device cgroup access.
- With `/var/run`, SYS_PTRACE, `/dev/uinput`, and an input-major cgroup rule derived from `/proc/devices`, the probe identified child PID 7's uinput descriptor 4 as input182, created only `/dev/input/event9` with device 13:73, and observed the real stock daemon's SIGHUP-handler readiness.
- The device numbers are observations, never constants for a later implementation.
- Each disposable container exited and was removed; the probe terminated its own child and removed its own node. No host input directory was mounted. No registered runner, Wolf configuration, or upstream file was changed.

## Decision impact

Descriptor-based ownership is feasible in the trial environment. This does not yet prove evmapy discovery, XTEST delivery, physical controller input, or a safe permanent capability policy. SYS_PTRACE is an explicit diagnostic prerequisite, not an approved registered-runner change.

Current API inspection found a Steam lobby and a session record, but no running experiment container. The trial must not stop Steam or restart Wolf. Session payloads and pairing secrets were neither printed nor saved.
