# https://docs.astral.sh/uv/guides/integration/docker/#using-uv-in-docker
# https://github.com/astral-sh/uv-docker-example/blob/main/Dockerfile
FROM ghcr.io/astral-sh/uv:python3.13-alpine
LABEL maintainer="eimeredelin@sberbank.ru"

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# It is highly recommended to set the MPLCONFIGDIR environment variable
# to a writable directory, in particular to speed up the import of Matplotlib
# and to better support multiprocessing.
# Default is /.config/matplotlib and it is not a writable directory.
ENV MPLCONFIGDIR=/tmp/matplotlib

# Install the project into `/code`
WORKDIR /code

# https://wiki.alpinelinux.org/wiki/Fonts
# https://unix.stackexchange.com/questions/438257
RUN apk --no-cache add msttcorefonts-installer fontconfig \
    && update-ms-fonts \
    && fc-cache -f

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
ADD . /code
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Place executables in the environment at the front of the path
ENV PATH="/code/.venv/bin:$PATH"

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT []

# FastAPI requirement: write CMD in exec form, do not use shell form
# https://fastapi.tiangolo.com/deployment/docker/#use-cmd-exec-form
# Cloud.ru Container Apps requirement:
# do not run container on port 8012, 8013, 8022, 8112, 9090, 9091, 1-1024
CMD ["fastapi", "run", "app/main.py", "--port", "1704"]
