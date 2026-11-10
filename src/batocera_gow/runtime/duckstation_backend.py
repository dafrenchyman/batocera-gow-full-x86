"""Reduce owned stock DuckStation logs to renderer evidence, without text export."""

import re
from dataclasses import dataclass

MAX_LOG_BYTES = 1024 * 1024


@dataclass
class _Activation:
    """Track one device/context sequence, refusing fallback or recreation."""

    requested: str | None = None
    context: str | None = None
    active: str | None = None

    def consume(self, payload: bytes) -> bool:
        """Consume one complete payload; return false for ambiguous evidence."""
        attempt = re.fullmatch(
            rb"I/Host: Trying to create a (OpenGL|OpenGLES|Vulkan) GPU device\.\.\.",
            payload,
        )
        if attempt is not None:
            if self.requested is not None:
                return False
            self.requested = attempt[1].decode("ascii")
            return True
        if payload in (
            b"I/OpenGLContext: Created an OpenGL context",
            b"I/OpenGLContext: Created an OpenGL ES context",
        ):
            if self.context is not None or self.requested not in ("OpenGL", "OpenGLES"):
                return False
            self.context = "OpenGLES" if payload.endswith(b"ES context") else "OpenGL"
            return True
        if re.fullmatch(
            rb"I/GPU_HW: Created HW framebuffer of [1-9][0-9]*x[1-9][0-9]*",
            payload,
        ):
            return self.activate()
        return not (
            re.fullmatch(
                rb"E\(CreateGPU\): Failed to initialize [^\r\n]* renderer, "
                rb"falling back to software renderer",
                payload,
            )
            or payload.startswith(b"E(CreateGPUDevice): Failed to create GPU device:")
        )

    def activate(self) -> bool:
        """Accept framebuffer recreation, but require a matching device/context."""
        if self.requested is None:
            return False
        if self.requested in ("OpenGL", "OpenGLES"):
            if self.context is None:
                return False
            self.active = self.context
        else:
            if self.context is not None:
                return False
            self.active = self.requested
        return True


def active_backend(data: bytes) -> str | None:
    """Require ordered GPU-device, context and HW-framebuffer startup records.

    Source pin 3a08ad18406efc1ddc4927a59bea715961bb63fa: core/host.cpp's
    CreateGPUDevice, util/opengl_context.cpp, core/gpu_hw.cpp's CreateFramebuffer,
    and common/log.cpp's FileOutputLogCallback. Info uses channel names, errors
    use function names. A preference, device attempt or mapped library alone
    cannot prove an active backend. Rendered output is still a separate gate.

    Args:
        data: At most 1 MiB from this launch's private file log. No text retained.

    Returns:
        OpenGL, OpenGLES or Vulkan only after matching HW activation; None for
        incomplete, ambiguous, fallback or recreated-device records.
    """
    if len(data) > MAX_LOG_BYTES:
        return None
    if data and not data.endswith(b"\n"):
        # Keep complete records only if the partial trailing message cannot
        # describe a device/context/error transition.
        tail = data.rsplit(b"\n", 1)[-1]
        match = re.fullmatch(
            rb"\[ *[0-9]+\.[0-9]{4}\] I/([A-Za-z0-9_]+): [^\r\n]*",
            tail,
        )
        if match is None or match[1] in (b"Host", b"OpenGLContext", b"GPU_HW"):
            return None
    state = _Activation()
    for line in data.split(b"\n")[:-1]:
        match = re.fullmatch(rb"\[ *[0-9]+\.[0-9]{4}\] (.*)", line)
        if match is not None and not state.consume(match[1]):
            return None
    return state.active
