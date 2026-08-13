# syntax=docker/dockerfile:1

# Two stages so that build tooling never reaches the final image. The
# runtime layer carries the interpreter, the installed packages and the
# application, and nothing else.

# ---------- Stage 1: resolve and install dependencies ----------
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Dependencies are copied and installed before the application source
# so that Docker reuses the cached layer whenever only code changes.
COPY requirements.lock.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.lock.txt

# ---------- Stage 2: runtime ----------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app:/app/src

# Run as an unprivileged user. Cloud Run does not require this, but a
# container that only ever needs to read its own code has no reason to
# run as root.
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser config/ ./config/

USER appuser

# Documents the contract rather than fixing the value. Cloud Run
# overrides PORT at run time and the command below honours it.
EXPOSE 8080

# Used by docker-compose and local tooling. Cloud Run ignores Docker
# healthchecks and probes the port directly.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT','8080') + '/health').status == 200 else 1)"

# Shell form so that ${PORT} is expanded by the shell at container
# start. Exec form would pass the literal string to uvicorn and the
# container would fail to bind on Cloud Run.
CMD exec uvicorn clausegraph.api.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8080}