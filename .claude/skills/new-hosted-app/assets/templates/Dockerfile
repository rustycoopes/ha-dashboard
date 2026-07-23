FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# git is required at build time because organizeme-chrome is a git dependency - uv sync needs
# git on PATH to resolve/clone it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

RUN uv sync --frozen --no-dev

EXPOSE 8080

# Listens on Cloud Run's injected $PORT (defaults to 8080 for a fresh service). Wrapped in
# /bin/sh -c because CMD's exec form does not perform shell/env-var expansion on its own.
#
# --forwarded-allow-ips='*' trusts the X-Forwarded-Proto header from whatever peer connects to
# the container. Cloud Run terminates TLS at its own front end and always proxies to the
# container over a private, single-hop connection - the container is never reachable except
# through that proxy - so this is safe here.
CMD ["/bin/sh", "-c", "/app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
