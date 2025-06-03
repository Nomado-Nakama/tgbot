FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1
ENV TZ Europe/Moscow

WORKDIR /bot
COPY pyproject.toml pyproject.toml

# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"
# ENV TRANSFORMERS_OFFLINE=1
# ENV OMP_NUM_THREADS=4
# ENV MKL_NUM_THREADS=4


RUN uv sync
COPY . .
EXPOSE ${WEBAPP_PORT}

# # ---- download Sentence-Transformers model once ----
# RUN python - <<'PY'
# from sentence_transformers import SentenceTransformer
# SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
# PY
# # ---------------------------------------------------

CMD ["sh", "-c", "uv run alembic upgrade head && uv run -m src.bot.main -u"]
