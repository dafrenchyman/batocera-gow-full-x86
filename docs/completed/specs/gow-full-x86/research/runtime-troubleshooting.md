# Runtime troubleshooting

Historical corrections and verification from the runtime continuation retained by the 2026-10-26 handoff. Consolidated 2026-10-28 after the operator confirmed the effort finished. Pending acceptance and active-state instructions below describe that earlier stage, not reopened QA. Later deployment and sampled operator reports are in [current application state](../../../../current/app.md), with their original limits.

Record confirmed fixes here with their cause, correction, and verification. Keep incomplete fixes and hypotheses separate. Deployment is a separate check from a successful diagnostic. Earlier startup corrections and their image identities remain in [the implementation ledger](../tasks.md#emulator-launch-correction).

## Confirmed causes and corrections

### Wii and PS2 exceed Docker's default shared memory

Wii exited with SIGBUS. PS2 loaded its BIOS and disc, then aborted after CPU recompiler reset. The operator had reported Wii failure and suspected PS2 failure. A native diagnostic established both failures in the current image.

The experiment's Docker container had a 67,108,864-byte `/dev/shm`. Keeping the image, ROMs, launch commands, NVIDIA cache correction, and 1280x720 boot setting unchanged, a second owned diagnostic lobby set only `HostConfig.ShmSize` to 2,147,483,648 bytes. Both emulators then stayed running until the diagnostic deliberately interrupted them.

Dolphin used 100,925,440 bytes of shared memory and rendered the Wii wrist-strap safety screen for `007 - Quantum of Solace`. PCSX2 used 163,704,832 bytes and rendered the EA Games intro for `007 - Agent Under Fire`. Both exceed the old limit. Viewed captures are `output/gow-full-x86/diagnose-wii.png` and `diagnose-ps2.png`.

The failing lobby was `64f59858-9046-4f65-8bc8-29a856441382`. The corrected diagnostic lobby was `7fa29440-aeac-44aa-85b6-ed8a3a069409`. Both used image `sha256:58a3799a794a4ee3bcf862a9be08154619c45a31170d838eccadbf307e625e6d`; both were stopped. The permanent experiment-only runner now sets private `ShmSize` to 2 GiB. Packaged native verification below confirms both games render with the registered runner. No host IPC sharing, privileged mode, or emulator patch is needed.

This proves startup and visible intro rendering, not Moonlight gameplay, controller mapping, heard game audio, hotkey exit, or saves.

### Wine loses injected NVIDIA dependency paths

Stock Xenia's generator replaces `LD_LIBRARY_PATH` with `/usr/lib:/lib32:/usr/wine/wine-proton/lib/wine`. The injected NVIDIA ICD still points to `/usr/nvidia/lib/libGLX_nvidia.so.0`, but its version-specific dependencies were absent from the runtime linker cache.

In lobby `64f59858-9046-4f65-8bc8-29a856441382`, the loader failed to find `libnvidia-glsi.so.570.195.03` under that exact Wine environment. `vulkaninfo --summary` failed with `ERROR_INCOMPATIBLE_DRIVER` and no usable drivers. Running `ldconfig -X` with `/usr/nvidia/lib` and `/usr/nvidia/lib32` in addition to the existing stock directories resolved the injected driver's dependencies. The same Vulkan probe then found the RTX 3090 with driver 570.195.03. `-X` leaves library symlinks unchanged.

This fixes driver discovery. A second correction below fixes Xenia's later device-creation failure. Raising shared memory alone did not fix that error. Permanent cache initialization is implemented and packaged. A fresh 1080p lobby launched Xenia without a manual cache refresh.

### Xenia mixes stock CUDA with the injected driver

After the cache correction, Xenia found the RTX 3090 but VKD3D-Proton 3.0 failed `vkCreateDevice` with result -3. Host strace of the owned Xenia process showed it opening `/usr/lib/libcuda.so.1`, which resolves to stock 590.48.01. Vulkan and the kernel use injected 570.195.03. A same-UID native CUDA probe returned `CUDA_ERROR_COMPAT_NOT_SUPPORTED_ON_DEVICE`, code 804, with that mismatched library. It returned zero with injected CUDA. A native Vulkan device probe using Xenia's extensions likewise failed with the Wine search path and succeeded with matching libraries.

The startup correction preloads only injected `libcuda.so.1` for stock application children. Private `injected-cuda/lib64` and `injected-cuda/lib` links select the matching 64-bit and 32-bit files through the loader's literal `$LIB` token. Existing app preloads are preserved; the Nix bridge gets no added preload. This avoids rewriting stock or shared NVIDIA files. An allocator-only preload did not fix the failure and was rejected.

Owned lobby `62b9582f-01f8-427b-9aa8-d3643e9ae723` ran unchanged stock `emulatorlauncher`, Wine, DXVK, VKD3D, and Xenia Canary with this correction. Blue Dragon reached its press START screen. The final process maps show injected CUDA 570.195.03; the launcher log has neither the device-creation failure nor preload warnings. Both stock loader token values were measured, and both injected CUDA architectures exist. Evidence remains under remote `/home/operator/batocera-gow-full-x86/xenia-device-diagnosis/`, including `xenia-token-title.png`, `xenia-token-driver-maps.txt`, and `cuda-driver-comparison.txt`. The lobby and owned strace processes were stopped.

The startup implementation and real-loader regressions are packaged and deployed. GPU checks passed injected dependency resolution, CUDA initialization, and acceptance of the same preload by the stock 32-bit loader. Packaged Blue Dragon launches reached the press START prompt at both resolutions. Its capture has a predominantly white background; full graphics correctness, controller gameplay, and heard game audio are not established.

## Display sizing uses the negotiated session limit

Moonlight supplied 1280x720 and Xwayland initially used it. Stock `batocera-resolution minTomaxResolution` later selected advertised 5120x2880, so blaming missing Moonlight dimensions is wrong.

The stock script accepts `es.resolution` from `/boot/batocera-boot.conf` as its normal resolution limit. Startup now writes the validated session width and height there with stock `batocera-settings-set -f`, before privilege drop. Xwayland geometry uses the same dimension helper. That file belongs to the container's private writable layer, not Wolf's persistent home or the protected Batocera application. Packaged sessions stayed at 1280x720 through all six sampled emulator launches and at 1920x1080 through Xenia and RPCS3 launches. The real-session regression calls stock `minTomaxResolution` and observes unchanged requested dimensions at both sizes. No stock script patch or Moonlight preference change was made. Dialog readability on an actual Moonlight client remains operator acceptance.

## PS3 Blood Stone requires a per-game color-buffer option

RPCS3 loads firmware 4.90 and boots the Blood Stone ISO, but its default `Write Color Buffers = false` produces a black screen. Corrected 720p sizing and 2 GiB shared memory did not resolve that black screen in lobby `3c1314bf-8eee-47c8-872b-4fbf8799d8af`.

[RPCS3 issue 18608](https://github.com/RPCS3/rpcs3/issues/18608) documents the same game symptom and confirms that enabling Write Color Buffers fixes it. The installed stock generator exposes this as `rpcs3_colorbuffers`. Its normal per-game configuration takes precedence over system/global values.

Using stock `batocera-settings-set`, set only this experiment's saved per-game key to `true`:

```text
ps3["007 - Blood Stone (USA) (En,Fr) (BLUS30289).iso"].rpcs3_colorbuffers=true
```

The key was previously absent. No global PS3 default, other game, stock generator, runtime script, or protected app setting was changed for this game-specific correction. Do not hardcode it into image startup.

The same native launch in lobby `77b7c4e2-433e-45cb-ad26-e7ab40ab70c1` then rendered Blood Stone's intro and saving-content screen. Viewed evidence is `output/gow-full-x86/full-x86-ps3-wcb-3.png`; the preceding black capture is `full-x86-ps3-3.png`. Both lobbies were stopped. Memlock, Qt parser, PipeWire, and QPainter warnings still appeared while the game rendered, so suppressing those warnings is not this fix.

The earlier user-session heap abort occurred during shutdown. Deliberate diagnostic interruption is not a native/controller exit test, so clean exit remains acceptance work. A new unit test would only repeat an unchanged upstream option mapping; the paired real-game launches provide the relevant evidence. Packaged verification reached the saving-content screen at 720p, then finished initial content setup and reached the title/press START screen in the longer 1080p launch.

## Packaged deployment and verification

Runtime revision `fcffbfd04685d8ca59aac8ed6a57950e737a967c` produced image `sha256:e0c179a04267b022a8fab94628db24feff53c4bd317c9bdce5554873ae2ade03`. Both inventory gates retained all 112,729 stock paths with 21,782 isolated additions. Direct gzip/SSH/load took 339.54 seconds. Local-mode preparation and idle-gated registration deployed only **Batocera full x86 experiment**, runner `WolfExperimental`. No GHCR update, extra home bind, source bind, config bind, or entrypoint override was used.

Native 720p lobby `89eff988-906f-4f0f-831a-03bee18e816e` ran stock configgen launches for Wii/Dolphin, PS2/PCSX2, Xbox 360/Xenia, PS3/RPCS3, SNES/RetroArch, and Xbox/xemu. Viewed X11 captures show the Wii safety screen, PS2 intro, Xenia prompt, PS3 content setup, SNES title, and Xbox intro. All six stayed at 1280x720 and each had an uncorked audio stream on its assigned session sink. The actual container had 2 GiB private shared memory. GPU regression checks ran before these games and refreshed the linker cache through the same packaged initialization helper.

Fresh 1080p lobby `76bec08e-0f37-49b7-9414-f1051ebb58ba` used the unchanged registered runner and no manual cache initialization or configuration correction. Xenia reached its prompt and RPCS3 reached Blood Stone's title after completing initial content setup. Both stayed at 1920x1080 with assigned-sink audio streams. Viewed captures are `output/gow-full-x86/full-x86-packaged1080-{xbox360,ps3}-3.png`. The six 720p captures use `full-x86-packaged-<system>-3.png`. Complete launcher logs and all three frames per launch also remain in the owned remote deployment directory.

Host unit discovery passed 49 cases with the known ALSA skip. The isolated builder passed all 22 mounted-state/process cases and seven runtime unit cases, including real ALSA evaluation. The new transitive-loader regression failed against the old image for both injected directories; the new resource regression failed there with child SIGBUS at 64 MiB. The new disposable packaged image passed two stock-runtime cases with two GPU-dependent skips, and the memory regression passed with the display-dependent case skipped. On real Wolf, three stock-runtime checks passed with only the synthetic-cache fixture skipped to protect injected payloads. Both real-session resource/display cases passed separately at 720p and 1080p.

All owned lobbies were stopped. Final API inspection found no sessions, lobbies, or experiment containers. Captures are native X11 evidence, not Moonlight video. Processes were deliberately interrupted after observation, not closed through controller hotkeys. Client video/heard game audio, controller gameplay/hotplug, dialog readability, normal exit, preference persistence, and untested systems remain acceptance work. Keep this spec active.

## Read-only findings from the original repository

The original Dolphin troubleshooting notes document missing Xwayland support in Sway/wlroots, then successful GameCube/Wii rendering after rebuilding it. This experiment already provides a live rootful Xwayland display. That old fix is not applicable wholesale. The old setup also had window-capture and audio-routing differences.

The original NVIDIA initializer registered injected library directories with the linker. This is a useful lead, confirmed by the actual Wine-environment probe above. Do not copy its global metadata/symlink replacement behavior into this experiment.

Sources inspected read-only under the original checkout:

- `planning/active/epics/batocera-gow-container/specs/emulator-expansion/dolphin-xemu-troubleshooting.md`
- `package/batocera/core/batocera-gow-runtime/scripts/30-setup_nvidia.sh`

No original-repository files, protected Batocera app/state, or unrelated application resources were changed.
