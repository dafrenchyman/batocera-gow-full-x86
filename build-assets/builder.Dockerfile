ARG DEBIAN_BASE=debian:trixie
FROM ${DEBIAN_BASE}
ENV DEBIAN_FRONTEND=noninteractive \
    LIBGUESTFS_BACKEND=direct \
    LIBGUESTFS_BACKEND_SETTINGS=force_tcg \
    TMPDIR=/work/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_INSTALL_DIR=/opt/project-interpreters \
    UV_PYTHON_DOWNLOADS=never
RUN mkdir -p /work/tmp && apt-get update && apt-get install -y --no-install-recommends \
    fdisk mtools squashfs-tools rsync python3 tar acl attr libguestfs-tools \
    qemu-system-x86 qemu-utils linux-image-amd64 e2fsprogs dosfstools util-linux dbus-bin dbus-daemon \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && dpkg-query -W -f='${Package}\t${Version}\n' > /builder-packages.tsv \
    && mkdir -p /work/tmp /inputs
# Immutable official uv 0.13.6 release artifact; never replace Debian's python3.
ADD --checksum=sha256:f29c3e94ffabd7e6f3ba521dba169a9b7ec12100bf3257087f0f24f6123f3645 \
    https://github.com/astral-sh/uv/releases/download/0.13.6/uv-x86_64-unknown-linux-gnu.tar.gz /tmp/uv.tar.gz
RUN tar -xzf /tmp/uv.tar.gz -C /usr/local/bin --strip-components=1 uv-x86_64-unknown-linux-gnu/uv \
    && rm /tmp/uv.tar.gz \
    && UV_PYTHON_DOWNLOADS=automatic uv python install cpython-3.12.8-linux-x86_64-gnu \
    && uv python list --only-installed > /builder-python.tsv \
    && uv --version > /builder-uv.txt
WORKDIR /opt/project-source
COPY pyproject.toml uv.lock .python-version LICENSE ./
COPY src ./src
# The application has no runtime dependencies. Host parsers and dev tools stay out.
RUN UV_PROJECT_ENVIRONMENT=/opt/batocera-gow uv sync --locked --no-default-groups --no-dev --no-editable \
    --python cpython-3.12.8-linux-x86_64-gnu \
    && UV_PROJECT_ENVIRONMENT=/opt/batocera-gow-tests uv sync --locked --no-default-groups --no-dev \
    --group builder-test --no-editable --python cpython-3.12.8-linux-x86_64-gnu \
    && chmod -R a+rX /opt/project-interpreters /opt/batocera-gow /opt/batocera-gow-tests \
    && rm -rf /root/.cache/uv
WORKDIR /work
ENTRYPOINT ["/opt/batocera-gow/bin/python", "-m", "batocera_gow.builder.assemble"]
