"""Build complete pinned userspace with explicit roots and checked provenance."""

import argparse
import hashlib
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from batocera_gow.builder.assemble import assemble_in_builder
from batocera_gow.builder.inventory import verify_image
from batocera_gow.host.common import ProjectPaths, docker_command, isolated_environment
from batocera_gow.host.image import ImagePackager
from batocera_gow.host.remote_payload.contracts import SOURCE_URL
from batocera_gow.host.settings import HostSettings
from batocera_gow.provenance import (
    InputManifest,
    declared_inputs,
    file_sha256,
    project_mounts,
    tree_source,
)


class BuildError(RuntimeError):
    """An operator-actionable refusal whose message contains no private inputs."""


def working_tree_source(root: Path) -> InputManifest:
    """Identify all declared inputs, including assets and dependency configuration."""
    return declared_inputs(root)


def _record(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        message = "Expected a JSON object with text keys"
        raise ValueError(message)
    return {str(key): item for key, item in value.items()}


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        message = "Required build resource metadata is missing or invalid"
        raise ValueError(message)
    return value


@dataclass(frozen=True)
class BuildSource:
    """Separate publication revision from the complete current input identity."""

    kind: str
    revision: str
    tag: str
    inputs: InputManifest


class Build:
    """Own a local build attempt, borrowing explicitly configured process settings."""

    def __init__(
        self,
        paths: ProjectPaths,
        docker: list[str],
        environment: Mapping[str, str],
        *,
        working_tree: bool = False,
    ) -> None:
        """Configure a build without starting processes or creating output."""
        self.paths = paths
        self.root = paths.root
        self.assets = self.root / "build-assets"
        self.output = paths.assert_local("output/gow-full-x86")
        self.env = dict(environment)
        self.docker = list(docker)
        self.working_tree = working_tree

    def run(self, arguments: Sequence[str | Path], *, capture: bool = False) -> str:
        """Run argument-vector commands from the explicit root, failing on errors."""
        # Only this build's explicit argv reaches the configured process boundary.
        result = subprocess.run(  # noqa: S603
            [str(argument) for argument in arguments],
            cwd=self.root,
            env=self.env,
            check=True,
            text=True,
            stdout=subprocess.PIPE if capture else None,
        )
        return result.stdout if capture else ""

    def save(self, name: str, value: object) -> None:
        """Atomically replace an owned record without exposing private settings."""
        path = self.paths.assert_local(self.output / name)
        temporary = path.with_suffix(".partial")
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def source_identity(self) -> BuildSource:
        """Snapshot inputs; publishable builds also require clean committed source."""
        inputs = working_tree_source(self.root)
        if self.working_tree:
            digest = inputs["sha256"]
            self.save("source-worktree-" + digest + ".json", inputs)
            return BuildSource(
                "worktree", "worktree-sha256:" + digest, "worktree-" + digest, inputs
            )
        if self.run(["git", "status", "--porcelain"], capture=True).strip():
            message = (
                "Commit project source before building a publishable image; "
                "use --working-tree for local builds"
            )
            raise BuildError(message)
        revision = self.run(["git", "rev-parse", "HEAD"], capture=True).strip()
        return BuildSource("git", revision, "sha-" + revision, inputs)

    def verify_source(self, source: BuildSource) -> None:
        """Refuse promotion after any declared-input change in either build mode."""
        if declared_inputs(self.root) != source.inputs:
            message = "Build inputs changed during assembly; candidate not promoted"
            raise BuildError(message)

    def download(self, release: dict[str, object]) -> tuple[Path, str]:
        """Reuse verified input or finish its owned partial download."""
        url = _text(release.get("image_url"))
        name = url.rsplit("/", 1)[-1]
        path = self.paths.assert_local("cache/" + name)
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(path.suffix + ".partial")
        checked = path if path.exists() else partial
        if not path.exists():
            self.run(
                [
                    "curl",
                    "--fail",
                    "--location",
                    "--retry",
                    "3",
                    "--continue-at",
                    "-",
                    "--output",
                    partial,
                    url,
                ]
            )
        # The publisher supplies MD5 as corruption detection, not authentication.
        md5 = hashlib.md5(usedforsecurity=False)
        sha256 = hashlib.sha256()
        with checked.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                md5.update(block)
                sha256.update(block)
        if md5.hexdigest() != release.get("compressed_md5"):
            message = "Official compressed input checksum mismatch"
            raise BuildError(message)
        if checked != path:
            checked.replace(path)
        return path, sha256.hexdigest()

    def bridge(self) -> int:
        """Build and inventory the unchanged pinned x86_64 Nix runtime closure."""
        expression = (
            "{ bridgePath }: let b = import (builtins.toPath bridgePath); "
            "in builtins.mapAttrs (_: p: p.outPath) b"
        )
        raw: object = json.loads(
            self.run(
                [
                    "nix-instantiate",
                    "--eval",
                    "--strict",
                    "--json",
                    "--expr",
                    expression,
                    "--argstr",
                    "bridgePath",
                    self.assets / "bridge.nix",
                ],
                capture=True,
            )
        )
        outputs = {name: _text(value) for name, value in _record(raw).items()}
        for attribute in outputs:
            self.run(
                [
                    "nix-build",
                    self.assets / "bridge.nix",
                    "-A",
                    attribute,
                    "--no-out-link",
                ]
            )
        requisites = sorted(
            set(
                self.run(
                    ["nix-store", "--query", "--requisites", *outputs.values()],
                    capture=True,
                ).splitlines()
            )
        )
        sizes: object = json.loads(
            self.run(
                [
                    "nix",
                    "--extra-experimental-features",
                    "nix-command",
                    "path-info",
                    "--json",
                    *requisites,
                ],
                capture=True,
            )
        )
        values = list(_record(sizes).values()) if isinstance(sizes, dict) else sizes
        if not isinstance(values, list):
            message = "Nix closure size inventory is invalid"
            raise BuildError(message)
        closure_bytes = 0
        for value in values:
            size = _record(value).get("narSize")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                message = "Nix closure size is invalid"
                raise ValueError(message)
            closure_bytes += size
        archive = self.output / "bridge.tar"
        self.run(
            [
                "tar",
                "--numeric-owner",
                "--acls",
                "--xattrs",
                "-cpf",
                archive,
                "-C",
                "/",
                *[path.lstrip("/") for path in requisites],
            ]
        )
        hashes = {
            path: self.run(
                ["nix-store", "--query", "--hash", path], capture=True
            ).strip()
            for path in requisites
        }
        bridge_env = {
            "GOW_XWAYLAND": outputs["xwayland"] + "/bin/Xwayland",
            "GOW_XAUTH": outputs["xauth"] + "/bin/xauth",
            "GOW_SETPRIV": outputs["util-linux"] + "/bin/setpriv",
            "GOW_MESA_DRIVERS": outputs["mesa"] + "/lib/dri",
        }
        (self.output / "bridge.env").write_text(
            "".join(
                f"export {key}={shlex.quote(value)}\n"
                for key, value in bridge_env.items()
            ),
            encoding="utf-8",
        )
        self.save(
            "bridge-manifest.json",
            {"outputs": outputs, "hashes": hashes, "closure_bytes": closure_bytes},
        )
        return closure_bytes

    def builder(self) -> tuple[str, str]:
        """Provision the stock-aligned project interpreter before networkless work."""
        self.run([*self.docker, "pull", "debian:trixie"])
        raw: object = json.loads(
            self.run([*self.docker, "image", "inspect", "debian:trixie"], capture=True)
        )
        if not isinstance(raw, list) or len(raw) != 1:
            message = "Cannot identify the builder base image"
            raise ValueError(message)
        digests = _record(raw[0]).get("RepoDigests")
        if not isinstance(digests, list) or not digests:
            message = "Builder base lacks immutable provenance"
            raise ValueError(message)
        base = _text(digests[0])
        builder = "batocera-gow-full-experiment-builder:trixie"
        self.run(
            [
                *self.docker,
                "build",
                "--build-arg",
                "DEBIAN_BASE=" + base,
                "-t",
                builder,
                "-f",
                self.assets / "builder.Dockerfile",
                self.root,
            ]
        )
        packages = self.run(
            [
                *self.docker,
                "run",
                "--rm",
                "--network=none",
                "--entrypoint",
                "dpkg-query",
                builder,
                "-W",
                "-f=${Package}\t${Version}\n",
            ],
            capture=True,
        )
        interpreter = self.run(
            [
                *self.docker,
                "run",
                "--rm",
                "--network=none",
                "--entrypoint",
                "/opt/batocera-gow/bin/python",
                builder,
                "-I",
                "-c",
                "import sys; print(sys.version)",
            ],
            capture=True,
        ).strip()
        self.save(
            "builder-manifest.json",
            {"base": base, "packages": packages, "project_python": interpreter},
        )
        return builder, base

    def assemble(self, image: Path, builder: str, closure_bytes: int) -> Path:
        """Assemble complete stock input, cleaning only fresh failed owned staging."""
        fingerprint = declared_inputs(self.root)["sha256"]
        assembly = self.paths.assert_local(self.output / ("assembly-" + fingerprint))
        assembly.mkdir(exist_ok=True)
        fresh = not any(assembly.iterdir())
        try:
            assemble_in_builder(
                image,
                assembly,
                builder,
                closure_bytes,
                project_root=self.root,
                docker=self.docker,
            )
        except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError):
            if fresh and not (assembly / "assembly-manifest.json").exists():
                self.run(
                    [
                        *self.docker,
                        "run",
                        "--rm",
                        "--network=none",
                        *project_mounts(self.root),
                        "--mount",
                        f"type=bind,src={assembly},dst=/work",
                        builder,
                        "--project-root",
                        "/project",
                        "cleanup",
                        "--output",
                        "/work",
                        "--inside",
                    ]
                )
            raise
        return assembly

    def stage_runtime(self) -> Path:
        """Stage runtime modules, assets and license, never host dependencies."""
        runtime = self.paths.assert_local(self.output / "runtime")
        if runtime.exists():
            shutil.rmtree(runtime)
        shutil.copytree(self.assets / "runtime", runtime)
        package = runtime / "batocera_gow"
        package.mkdir()
        shutil.copyfile(
            self.root / "src/batocera_gow/__init__.py", package / "__init__.py"
        )
        shutil.copytree(
            self.root / "src/batocera_gow/runtime",
            package / "runtime",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        for path in (self.root / "tests/assets/input").iterdir():
            if path.is_file():
                shutil.copyfile(path, runtime / path.name)
        shutil.copyfile(self.root / "LICENSE", runtime / "LICENSE")
        shutil.copyfile(self.output / "bridge.env", runtime / "bridge.env")
        return runtime

    def package(
        self, assembly: Path, runtime: Path, builder: str, source: BuildSource
    ) -> Path:
        """Run installed packaging with explicitly declared read-only input binds."""
        packaging = self.paths.assert_local(self.output / ("packaging-" + source.tag))
        self.run(
            [
                sys.executable,
                "-m",
                "batocera_gow.builder.assemble",
                "--project-root",
                self.root,
                "--docker",
                shlex.join(self.docker),
                "package",
                "--stock-root",
                assembly / "stock-root.tar",
                "--reference",
                self.output / "stock-manifest.json",
                "--bridge",
                self.output / "bridge.tar",
                "--runtime",
                runtime,
                "--seed",
                assembly / "stock-share.tar",
                "--output",
                packaging,
                "--builder",
                builder,
            ]
        )
        return packaging

    def execute(self) -> str:
        """Stock-verify and promote an exact image, without deployment/publication."""
        self.output.mkdir(parents=True, exist_ok=True)
        for name in ("build-manifest.json", "publication-manifest.json"):
            (self.output / name).unlink(missing_ok=True)
        source = self.source_identity()
        raw: object = json.loads(
            (self.assets / "release.json").read_text(encoding="utf-8")
        )
        release = _record(raw)
        image, sha256 = self.download(release)
        closure_bytes = self.bridge()
        builder, base = self.builder()
        assembly = self.assemble(image, builder, closure_bytes)
        shutil.copyfile(
            assembly / "stock-manifest.json", self.output / "stock-manifest.json"
        )
        runtime = self.stage_runtime()
        runtime_inputs = tree_source(runtime)
        self.verify_source(source)
        packaging = self.package(assembly, runtime, builder, source)
        candidate = "batocera-gow-full-experiment-candidate:" + source.tag
        local = "batocera-gow-full-experiment:" + source.tag
        labels = {
            "org.opencontainers.image.source": SOURCE_URL,
            "org.opencontainers.image.revision": source.revision,
            "org.opencontainers.image.version": "43.1",
            "io.gow.full-x86.input.sha256": sha256,
            "io.gow.full-x86.input.md5": _text(release.get("compressed_md5")),
            "io.gow.full-x86.experimental": "true",
            "io.gow.full-x86.source.kind": source.kind,
            "io.gow.full-x86.declared-inputs.sha256": source.inputs["sha256"],
        }
        if source.kind == "worktree":
            labels["io.gow.full-x86.source.sha256"] = source.inputs["sha256"]
        loaded_image = ImagePackager(self.docker, self.root, self.env).load(
            packaging / "final-root.tar", candidate, labels
        )
        verification = Path(tempfile.mkdtemp(prefix="verification-", dir=self.output))
        stock_sha256 = file_sha256(self.output / "stock-manifest.json")
        preservation = verify_image(
            self.output / "stock-manifest.json",
            loaded_image,
            builder,
            verification,
            project_root=self.root,
            docker=self.docker,
        )
        inventory_report = verification / "inventory-verification.json"
        report_sha256 = file_sha256(inventory_report)
        inventory_result = _record(
            json.loads(inventory_report.read_text(encoding="utf-8"))
        )
        if (
            preservation.get("image") != loaded_image
            or file_sha256(self.output / "stock-manifest.json") != stock_sha256
            or inventory_result
            != {key: value for key, value in preservation.items() if key != "image"}
        ):
            message = "Saved-image preservation report changed before promotion"
            raise BuildError(message)
        self.verify_source(source)
        if tree_source(runtime) != runtime_inputs:
            message = "Staged runtime inputs changed; candidate not promoted"
            raise BuildError(message)
        if (
            file_sha256(self.output / "stock-manifest.json") != stock_sha256
            or file_sha256(inventory_report) != report_sha256
        ):
            message = "Preservation evidence changed; candidate not promoted"
            raise BuildError(message)
        self.run([*self.docker, "tag", loaded_image, local])
        image_id = self.run(
            [*self.docker, "image", "inspect", "--format", "{{.Id}}", local],
            capture=True,
        ).strip()
        if image_id != loaded_image:
            message = "Promoted image differs from stock-verified immutable image"
            raise BuildError(message)
        self.save(
            "build-manifest.json",
            {
                "status": "success",
                "adapter_revision": source.revision,
                "release": "43.1",
                "input_sha256": sha256,
                "local_image": local,
                "image_id": image_id,
                "inventory_verified": True,
                "builder_base": base,
                "source_kind": source.kind,
                "source_sha256": source.inputs["sha256"]
                if source.kind == "worktree"
                else None,
                "declared_inputs": source.inputs,
                "runtime_inputs": runtime_inputs,
                "preservation": {
                    "schema": 1,
                    "image": image_id,
                    "declared_inputs_sha256": source.inputs["sha256"],
                    "stock_sha256": stock_sha256,
                    "report": inventory_report.relative_to(self.output).as_posix(),
                    "report_sha256": report_sha256,
                    "result": inventory_result,
                },
            },
        )
        return local


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve command settings once and report nonsecret build failures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--working-tree",
        action="store_true",
        help=(
            "Build current declared inputs locally, without Git mutation or publication"
        ),
    )
    arguments = parser.parse_args(argv)
    try:
        settings = HostSettings.resolve(env_file=arguments.env_file)
        paths = ProjectPaths(arguments.project_root)
        environment = isolated_environment(paths, settings.values)
        Path(environment["TMPDIR"]).mkdir(parents=True, exist_ok=True)
        Path(environment["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)
        local = Build(
            paths,
            docker_command(settings.values),
            environment,
            working_tree=arguments.working_tree,
        ).execute()
    except BuildError as error:
        sys.stderr.write(f"Build refused: {error}\n")
        return 1
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError):
        sys.stderr.write(
            "Build refused: check declared inputs, configured resources "
            "and local build prerequisites\n"
        )
        return 1
    sys.stdout.write("Complete stock inventory verified. Built " + local + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
