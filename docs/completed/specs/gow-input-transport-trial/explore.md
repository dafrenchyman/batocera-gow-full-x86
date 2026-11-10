# Input transport trial decisions

## Chosen direction

The user approved trying an additive experiment-owned transport helper. Batocera retains all controller combinations, semantic actions and emulator contexts. Wolf/GoW and the existing display arrangement remain unchanged. A new compositor, rewritten hotkeygen, per-emulator mappings, and universal overlay are out of scope.

## Ownership

Use the creating descendant process's actual uinput descriptor and UI_GET_SYSNAME. Neither device names nor a before/after host device snapshot establish session ownership. A remote disposable probe successfully created only the corresponding event node and reached stock hotkeygen readiness.

## Security boundary

The descriptor API is blocked by the current Docker default policy. A disposable SYS_PTRACE-capable container proved the API works. Restrict this capability to the diagnostic candidate for now; no registered runner change is approved. Private PID namespace and descendant-only inspection are required.

## Trial outcome

- Both stock uinput hops were proven through creator descriptors; all five native XTEST receiver cases passed.
- The first real RetroArch trial still failed because its configured udev keyboard backend did not discover the generated final keyboard.
- Adding stock-classifier metadata and existing fake-udev notifications for only the owned final keyboard made the real native menu and exit work without emulator-specific configuration.
- Security review fixes and 43 targeted unit tests cover ownership, state transitions and cleanup failure boundaries. The accepted dev_t reuse exposure remains.

## Next discussion

The bounded trial is complete. Permanent rollout needs a separate decision on SYS_PTRACE and residual device-lifetime exposure. A tighter syscall/ownership mechanism may be researched separately; do not silently disable Docker's default filter. Physical-controller and other-emulator acceptance are not established by synthetic transport proof.
