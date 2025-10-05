# syntax=docker/dockerfile:1.7                 # unlock BuildKit features
FROM python:3.12-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    TZ=Europe/Moscow \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /bot

# --- 1. OS packages ----------------------------------------------------------
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update -q \
 && apt-get install -y --no-install-recommends \
        curl ca-certificates git \
 && rm -rf /var/lib/apt/lists/*    # cleans layer size

# --- 2. uv installation (single curl, cached) -------------------------------
ADD --chmod=755 https://astral.sh/uv/install.sh /install.sh
RUN /install.sh && rm /install.sh
ENV PATH="/root/.local/bin:${PATH}"

# --- 3. Python deps layer – COPY only lock + metadata  -----------------------
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# --- 4. Copy source (with BuildKit hard-link optimisation) -------------------
COPY --link . .

# --- 5. Final tweaks ---------------------------------------------------------
EXPOSE ${WEBAPP_PORT}

CMD ["uv", "run", "-m", "src.main"]
