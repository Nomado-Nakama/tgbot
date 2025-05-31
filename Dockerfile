FROM python:3.12-alpine
WORKDIR /bot
COPY pyproject.toml pyproject.toml

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN uv sync
COPY . .
EXPOSE ${WEBAPP_PORT}
ENV TZ Europe/Moscow
CMD ["uv", "run" "-m", "src.bot.main"]
