# Input transport trial tasks

- [x] Record the approved upstream-preservation and experiment-only scope.
- [x] Check current remote state without stopping the existing Steam lobby.
- [x] Prove exact uinput descriptor ownership and stock daemon readiness in a disposable real-stock container.
- [x] Record default pidfd_getfd denial and the isolated SYS_PTRACE requirement.
- [x] Review the trial contract before product-code changes; record device-lifetime, process-identity and privilege-boundary findings.
- [x] Obtain an explicit decision on diagnostic SYS_PTRACE and residual stale-node/device-number reuse risk: user approved the disposable trial alongside the existing Steam lobby, not permanent deployment.
- [x] Implement descendant-only device forwarding and lifecycle supervision.
- [x] Implement XTEST keyboard/pointer transport without shortcut or emulator mappings.
- [x] Add deterministic behavioral tests for state transitions, invalid inputs and identity boundaries.
- [x] Run the final integrated input boundary/state tests: 43 tests passed, including scoped udev ownership and multi-source cleanup after notification failure.
- [x] Exercise actual stock shortcut delivery, holds, graceful source removal/first-use recreation and command dispatch in an owned native Wolf lobby: all five cases passed, container exit 0.
- [x] Verify unchanged upstream inputs, clean owned-lobby shutdown and no registration change; original Steam lobby preserved and Wolf config SHA256 unchanged.
- [x] Exercise stock configgen and real RetroArch using the same additive transport: Guide + ES `b` visibly opened the native menu; Guide+Start terminated the pinned emulator and stock launcher exited 0.
- [x] Identify the native keyboard backend boundary and prove the stock single-device classifier in a disposable owned-device probe.
- [x] Add no-clobber, identity/content-checked app-local metadata for only the descriptor-proven final keyboard; retain XTEST and original stock mappings.
- [x] Complete security review of metadata publication and native proof: cleanup finding resolved; RetroArch opened the exact final keyboard and read stock-classifier properties.
- [x] Record prerequisite results and the security decision required to continue in `research/ownership.md` and `research/security-review.md`.
- [x] Record end-to-end results and the diagnostic-only deployment boundary; no permanent activation was approved or performed.
