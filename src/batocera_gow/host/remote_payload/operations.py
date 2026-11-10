"""Owned deployment, activation and inspection using only the standard library."""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import NoReturn

from batocera_gow.host.remote_payload.activation import activate_config
from batocera_gow.host.remote_payload.activity import require_idle
from batocera_gow.host.remote_payload.contracts import (
    NATIVE_HOME,
    OWNER,
    PROTECTED_HOME,
    REPOSITORY,
)
from batocera_gow.host.remote_payload.json_data import (
    Json,
    decode,
    record,
    sequence,
    text,
)
from batocera_gow.host.remote_payload.privacy import sanitize

HOME = Path(NATIVE_HOME)
CONFIG = Path("/etc/wolf/cfg/config.toml")
PROTECTED = Path(PROTECTED_HOME)


class RemoteError(RuntimeError):
    """A controlled nonsecret operation refusal."""


def fail(message: str) -> NoReturn:
    """Raise a controlled error containing no external process output."""
    raise RemoteError(message)


def capture(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Capture trusted executable argv, never invoking a shell or logging stdin."""
    # Callers select fixed commands and validate image, identity and path arguments.
    return subprocess.run(  # noqa: S603
        args, text=True, capture_output=True, check=False
    )


def command(args: list[str]) -> str:
    """Execute trusted argv without exposing command output on failure."""
    result = capture(args)
    if result.returncode:
        fail("remote process operation failed")
    return result.stdout


def docker(*args: str) -> str:
    """Use existing noninteractive privilege authorization, never install helpers."""
    return command(["sudo", "-n", "docker", *args])


def canonical(path: Path) -> None:
    """Reject symlink traversal on the host where the path will be written."""
    if path.resolve() != path:
        fail("symlinked remote destination refused")


def atomic_record(path: Path, value: dict[str, Json]) -> None:
    """Replace one canonical owned record with mode0600, without private backups."""
    canonical(path)
    temporary = path.with_name(path.name + ".partial")
    canonical(temporary)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        canonical(path.parent)
        canonical(path)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def api(endpoint: str) -> Json:
    """Keep raw Wolf API responses in process memory, never diagnostic records."""
    return decode(
        command(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--max-time",
                "10",
                "--unix-socket",
                "/var/run/wolf/wolf.sock",
                "http://localhost/api/v1/" + endpoint,
            ]
        )
    )


def containers() -> list[dict[str, Json]]:
    """Inspect all containers for activity and owned runner collisions."""
    identifiers = docker("ps", "-aq").split()
    return (
        [record(item) for item in sequence(decode(docker("inspect", *identifiers)))]
        if identifiers
        else []
    )


def idle() -> None:
    """Require no sessions, lobbies, running or paused numeric/UUID app runners."""
    require_idle(api("sessions"), api("lobbies"), containers())


def ui_revision() -> str:
    """Require one identifiable installed Wolf UI revision."""
    identifiers = sorted(set(docker("image", "ls", "--format", "{{.ID}}").split()))
    found: set[str] = set()
    values = (
        sequence(decode(docker("image", "inspect", *identifiers)))
        if identifiers
        else []
    )
    for item in values:
        value = record(item)
        labels = record(record(value.get("Config", {})).get("Labels") or {})
        tags = " ".join(text(tag) for tag in sequence(value.get("RepoTags") or []))
        if (
            "wolf-ui" in tags.lower()
            or "wolf-ui"
            in text(labels.get("org.opencontainers.image.source", "")).lower()
        ):
            revision = text(labels.get("org.opencontainers.image.revision", ""))
            if re.fullmatch("[0-9a-f]{40}", revision):
                found.add(revision)
    if len(found) != 1:
        fail("cannot identify one installed Wolf UI revision")
    return found.pop()


class Deployment:
    """Operate only one explicitly selected deployment and fixed production identity."""

    def __init__(self, root: Path, *, home: Path = HOME, config: Path = CONFIG) -> None:
        """Validate deployment isolation and retain fixed native/config identities."""
        if not root.is_absolute() or root == Path("/") or ".." in root.parts:
            fail("an explicit absolute deployment root is required")
        if root == home or root in home.parents or home in root.parents:
            fail("deployment root overlaps native home")
        if root == PROTECTED or root in PROTECTED.parents or PROTECTED in root.parents:
            fail("deployment root overlaps protected state")
        self.root, self.home, self.config = root, home, config

    def ownership(self) -> dict[str, Json] | None:
        """Reject unrelated occupied or symlinked deployment roots before writes."""
        canonical(self.root)
        if not self.root.exists():
            return None
        marker = self.root / "deployment.json"
        canonical(marker)
        if not marker.is_file():
            fail("unrelated occupied deployment directory")
        value = record(decode(marker.read_text(encoding="utf-8")))
        if value.get("owner") != OWNER:
            fail("deployment ownership mismatch")
        return value

    def write_ownership(self, value: dict[str, Json]) -> None:
        """Persist only controlled deployment ownership metadata."""
        canonical(self.root)
        atomic_record(self.root / "deployment.json", value)

    def check_home(self, value: dict[str, Json] | None) -> None:
        """Validate native state ownership and release without creating userdata."""
        canonical(self.home)
        protected = PROTECTED.resolve()
        if (
            self.home == protected
            or protected in self.home.parents
            or self.home in protected.parents
        ):
            fail("experiment home overlaps protected Batocera home")
        if self.home.exists():
            if (
                not value
                or not value.get("registered")
                or value.get("native_home") != str(self.home)
            ):
                fail("unowned occupied native experiment home")
            marker = self.home / ".gow-full-x86-state.json"
            canonical(marker)
            if (
                marker.exists()
                and record(decode(marker.read_text(encoding="utf-8"))).get("release")
                != "43.1"
            ):
                fail("native home belongs to another release")

    def dispatch(self, request: dict[str, Json]) -> dict[str, Json]:
        """Execute one recognized JSON operation against validated owned paths."""
        action = text(request.get("action"))
        value = self.ownership()
        if action == "prepare":
            return self.prepare(request, value)
        if not value:
            fail("prepare the published image first")
        image = image_reference(request)
        if value.get("prepared_image") != image:
            fail("prepare the published image first")
        self.check_home(value)
        if action == "read-registration":
            canonical(self.config)
            return {
                "config": self.config.read_text(encoding="utf-8"),
                "owned": bool(value.get("registered")),
                "ui_revision": ui_revision(),
                "native_home": str(self.home),
                "profiles": api("profiles"),
            }
        if action == "activate":
            return self.activate(request, value)
        if action in {"inspect", "logs"}:
            return {
                "containers": [
                    self.inspect_container(
                        container, image, value, request, logs=action == "logs"
                    )
                    for container in containers()
                    if re.fullmatch(
                        r"WolfExperimental_[0-9a-fA-F-]{36}",
                        text(container.get("Name", "")).lstrip("/"),
                    )
                ]
            }
        if action == "write-diagnostics":
            filename = text(request.get("filename"))
            if filename not in {"remote-logs.json", "remote-session.json"}:
                fail("invalid owned diagnostic destination")
            diagnostic = record(sanitize(record(request.get("diagnostics"))))
            atomic_record(self.root / filename, diagnostic)
            return {"saved": True}
        fail("unknown remote operation")

    def prepare(
        self, request: dict[str, Json], value: dict[str, Json] | None
    ) -> dict[str, Json]:
        """Verify selected image and prerequisites before recording prepared state."""
        self.check_home(value)
        image = image_reference(request)
        revision = ui_revision()
        if not self.root.exists():
            canonical(self.root.parent)
            self.root.mkdir(mode=0o700)
        if value is None:
            value = {"owner": OWNER, "native_home": str(self.home), "registered": False}
            self.write_ownership(value)
        required = request.get("required_bytes")
        if not isinstance(required, int) or isinstance(required, bool) or required < 0:
            fail("invalid required image space")
        capacity = os.statvfs(self.root)
        if capacity.f_bavail * capacity.f_frsize < required:
            fail("insufficient remote space for experiment image")
        if request.get("local") is not True:
            _pull_publication(request, image)
        actual = record(sequence(decode(docker("image", "inspect", image)))[0])
        if actual.get("Id") != request.get("image_id"):
            fail("remote image content differs from local build")
        _validate_prepared_image(actual, request)
        docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "/opt/gow-full-x86/check-runtime.sh",
            image,
        )
        value.update(prepared_image=image, image_id=actual["Id"], ui_revision=revision)
        self.write_ownership(value)
        return {
            "prepared": True,
            "ui_revision": revision,
            "native_home": str(self.home),
            "image": image,
        }

    def activate(
        self, request: dict[str, Json], value: dict[str, Json]
    ) -> dict[str, Json]:
        """Run the shared atomic transaction and require API recovery afterward."""
        canonical(self.config)
        if ui_revision() != request.get("ui_revision"):
            fail("installed Wolf UI changed during registration")

        def ownership(activated: bool) -> None:  # noqa: FBT001  # Required positional Callable[[bool], object] transaction callback.
            value.update(
                registered=True,
                activated=activated,
                registered_image=image_reference(request),
            )
            self.write_ownership(value)

        changed = activate_config(
            self.config,
            text(request.get("expected_hash")),
            text(request.get("config")),
            idle,
            lambda: docker("restart", "wolf-wolf-1"),
            ownership,
            retry_restart=not bool(value.get("activated")),
        )
        for _ in range(20):
            try:
                profiles = api("profiles")
                break
            except (RemoteError, OSError, TypeError, ValueError):
                time.sleep(1)
        else:
            fail("Wolf API did not recover after activation")
        return {
            "config": self.config.read_text(encoding="utf-8"),
            "profiles": profiles,
            "changed": changed,
        }

    def _validate_mounts(
        self, mounts: list[dict[str, Json]], request: dict[str, Json]
    ) -> None:
        """Validate automatic home ownership and protected-state mount isolation."""
        destinations = [text(mount["Destination"]) for mount in mounts]
        if len(destinations) != len(set(destinations)):
            fail("duplicate injected mount destinations")
        homes = [mount for mount in mounts if mount["Destination"] == "/home/retro"]
        if len(homes) != 1 or Path(text(homes[0]["Source"])).resolve() != self.home:
            fail("unexpected automatic app home")
        protected = PROTECTED.resolve()
        for mount in mounts:
            source = Path(text(mount["Source"])).resolve()
            if (
                source == protected
                or protected in source.parents
                or source in protected.parents
            ):
                fail("mount overlaps protected existing Batocera state")
        _check_content_mounts(mounts, request)

    def inspect_container(
        self,
        container: dict[str, Json],
        image: str,
        value: dict[str, Json],
        request: dict[str, Json],
        *,
        logs: bool,
    ) -> dict[str, Json]:
        """Validate container ownership before collecting bounded diagnostics."""
        config = record(container.get("Config", {}))
        if (
            container.get("Image") != value.get("image_id")
            or config.get("Image") != image
        ):
            fail("runner prefix occupied by a different image")
        mounts = [record(item) for item in sequence(container.get("Mounts", []))]
        self._validate_mounts(mounts, request)
        host = record(container.get("HostConfig", {}))
        _validate_security(host, mounts)
        env = dict(
            text(item).split("=", 1)
            for item in sequence(config.get("Env", []))
            if "=" in text(item)
        )
        state = record(container.get("State", {}))
        info: dict[str, Json] = {
            "name": text(container.get("Name", "")).lstrip("/"),
            "image": container["Image"],
            "state": state.get("Status"),
            "mounts": list(mounts),
            "environment": {
                key: env[key]
                for key in (
                    "PUID",
                    "PGID",
                    "XDG_RUNTIME_DIR",
                    "WAYLAND_DISPLAY",
                    "PULSE_SERVER",
                    "PULSE_SINK",
                    "PULSE_SOURCE",
                )
                if key in env
            },
            "ipc_mode": host.get("IpcMode"),
            "cap_add": host.get("CapAdd"),
            "devices": host.get("Devices"),
        }
        identifier = text(container["Id"])
        if state.get("Running"):
            info.update(_runtime_diagnostics(identifier, env))
        if logs:
            output = capture(
                ["sudo", "-n", "docker", "logs", "--tail", "2000", identifier]
            )
            info["logs"] = output.stdout + output.stderr
        return record(sanitize(info))


def _pull_publication(request: dict[str, Json], image: str) -> None:
    """Pull only verified immutable/latest references and require digest agreement."""
    for field in ("sha_reference", "latest_reference"):
        reference = text(request.get(field))
        if not re.fullmatch(
            re.escape(REPOSITORY) + r":(latest|sha-[0-9a-f]{40})", reference
        ):
            fail("invalid publication reference")
        docker("pull", reference)
        inspected = record(sequence(decode(docker("image", "inspect", reference)))[0])
        if image not in sequence(inspected.get("RepoDigests", [])):
            fail("remote pull digest differs from verified publication")
    docker("pull", image)


def _validate_prepared_image(actual: dict[str, Json], request: dict[str, Json]) -> None:
    """Require exact image identity and local adapter ownership/revision labels."""
    if request.get("local") is True:
        labels = record(record(actual.get("Config", {})).get("Labels") or {})
        if labels.get("io.gow.full-x86.experimental") != "true" or labels.get(
            "org.opencontainers.image.revision"
        ) != request.get("adapter_revision"):
            fail("loaded image is not the verified experimental adapter")


def _check_content_mounts(
    mounts: list[dict[str, Json]], request: dict[str, Json]
) -> None:
    """Require unique read-only content binds from configured host roots."""
    for destination, field in (
        ("/home/retro/userdata/roms", "roms_root"),
        ("/home/retro/userdata/bios", "bios_root"),
    ):
        source = Path(text(request.get(field)))
        if not source.is_absolute():
            fail("invalid configured content root")
        matches = [mount for mount in mounts if mount["Destination"] == destination]
        if (
            len(matches) != 1
            or matches[0].get("RW")
            or Path(text(matches[0]["Source"])).resolve() != source.resolve()
        ):
            fail("ROM/BIOS mount contract mismatch")


def _validate_security(host: dict[str, Json], mounts: list[dict[str, Json]]) -> None:
    """Require effective private namespaces, input capabilities and Wolf mounts."""
    if (
        host.get("IpcMode") != "private"
        or host.get("Privileged")
        or host.get("PidMode") == "host"
    ):
        fail("unsafe effective app namespace/privilege settings")
    caps = {
        text(item).upper().removeprefix("CAP_")
        for item in sequence(host.get("CapAdd") or [])
    }
    if not {"NET_ADMIN", "SYS_NICE"}.issubset(caps) or "SYS_ADMIN" in caps:
        fail("effective app capabilities do not match experiment contract")
    if not any(
        record(item).get("PathInContainer") == "/dev/uinput"
        for item in sequence(host.get("Devices") or [])
    ):
        fail("uinput is not exposed")
    destinations = [text(mount["Destination"]) for mount in mounts]
    if any(
        destination not in destinations
        for destination in ("/usr/nvidia", "/usr/bin/fake-udev", "/run/udev")
    ):
        fail("missing Wolf automatic mount")
    if not next(mount for mount in mounts if mount["Destination"] == "/usr/nvidia").get(
        "RW"
    ):
        fail("unexpected NVIDIA injection mode")


def _graphics_diagnostics(
    identifier: str, uid: str, gid: str, auth: str
) -> dict[str, Json]:
    """Run GLX inspection as the actual session identity and Xauthority owner."""
    graphics = capture(
        [
            "sudo",
            "-n",
            "docker",
            "exec",
            "--user",
            uid + ":" + gid,
            "--env",
            "DISPLAY=:0",
            "--env",
            "XAUTHORITY=" + auth,
            "--env",
            "LD_LIBRARY_PATH=/usr/nvidia/lib:/usr/nvidia/lib32",
            identifier,
            "glxinfo",
            "-B",
        ]
    )
    return {
        "graphics": graphics.stdout + graphics.stderr,
        "nvidia_renderer_verified": (
            graphics.returncode == 0
            and "nvidia" in graphics.stdout.lower()
            and "llvmpipe" not in graphics.stdout.lower()
        ),
    }


def _runtime_diagnostics(identifier: str, env: dict[str, str]) -> dict[str, Json]:
    """Verify runtime/persistent identities before inspecting session processes."""
    contract = record(
        decode(docker("exec", identifier, "/bin/cat", "/run/gow-full-x86-session.json"))
    )
    uid, gid = str(contract["puid"]), str(contract["pgid"])
    if not uid.isdigit() or not gid.isdigit() or contract.get("display") != ":0":
        fail("invalid runtime identity/display contract")
    auth = text(contract.get("xauthority"))
    # This is validation of the runtime's private Xauthority contract, not creation.
    if not re.fullmatch(r"/tmp/gow-full-x86-[A-Za-z0-9_-]+/Xauthority", auth):  # noqa: S108
        fail("unexpected private Xauthority location")
    link = docker("exec", identifier, "/usr/bin/readlink", "/userdata").strip()
    if link != "/home/retro/userdata":
        fail("userdata does not resolve through native home")
    marker = record(
        decode(
            docker(
                "exec", identifier, "/bin/cat", "/home/retro/.gow-full-x86-state.json"
            )
        )
    )
    if (
        marker != {"release": "43.1", "puid": int(uid), "pgid": int(gid)}
        or env.get("PUID", "1000") != uid
        or env.get("PGID", "1000") != gid
    ):
        fail("persistent/runtime identity differs from Wolf injection")
    return {
        "session_contract": contract,
        "userdata_link": link,
        "state_marker": marker,
        "processes": docker("exec", identifier, "/bin/ps", "-eo", "pid,ppid,comm"),
        **_graphics_diagnostics(identifier, uid, gid, auth),
    }


def image_reference(request: dict[str, Json]) -> str:
    """Require an immutable local ID or the dedicated repository digest."""
    image = text(request.get("image", ""))
    pattern = (
        r"sha256:[0-9a-f]{64}"
        if request.get("local") is True
        else re.escape(REPOSITORY) + r"@sha256:[0-9a-f]{64}"
    )
    if not re.fullmatch(pattern, image):
        fail("invalid experimental image identity")
    return image


def main() -> int:
    """Translate remote failures without echoing private request data."""
    try:
        request = record(decode(sys.stdin.read()))
        root = Path(text(request.get("deployment_root")))
        result = Deployment(root).dispatch(request)
    except (OSError, TypeError, ValueError, KeyError, IndexError, RuntimeError):
        response: dict[str, Json] = {
            "ok": False,
            "error": (
                "Remote operation refused; check owned paths, request and prerequisites"
            ),
        }
        sys.stdout.write(json.dumps(response) + "\n")
        return 1
    sys.stdout.write(json.dumps({"ok": True, "result": result}) + "\n")
    return 0
