# Accepted release input

Downloaded official generic x86_64 43.1 into the independent project's cache. Size 4,334,005,632 bytes. Publisher checksum fetched independently over HTTPS and matched fixed MD5 `0c365dc3c17b05a4b276c579168b01da`. Computed SHA-256 `7ac08d5fcf6f9c00e85e71b6d0c68ddffe710f1e0667aab2931c5bf1509018b8`. Only after checksum success was `.partial` renamed.

Pinned nixpkgs evaluates Xwayland 24.1.14. `mesa.drivers` is a deprecated alias at this pin; canonical `mesa` resolves to the same store output and is used instead. Full bridge requisites were realized and archived, reported NAR closure size 1,456,490,168 bytes. These are build-input checks, not Wolf runtime proof.

# Remote read-only preflight

The selected Wolf host was reachable through the provided SSH key with existing host-key verification and passwordless Docker sudo. Personal hostname and key filename are omitted. Root filesystem reported 235,934,052,352 available bytes. New deployment directory and experiment native home were absent. A Steam runner was active. No session or container was stopped, and no config or state was modified.

Injected NVIDIA payload has `lib`, `lib32`, `bin`, `share`, with libEGL_nvidia.so.0 and libGLX_nvidia.so.0 for driver 570.195.03 under `lib`. Its EGL/Vulkan JSON paths were confirmed read-only. The adapter must not write this volume.
