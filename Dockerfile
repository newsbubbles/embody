# The embody server as one container: the engine, the packs and the worlds in this repository, served over
# streamable HTTP with bearer grants. deploy/start.sh loads (or renews) the world named by EMBODY_WORLD into the
# database on the mounted volume, then serves. docs/HOSTING.md has the path; railway.json the platform settings.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# the package first, so the dependency layer is reused while worlds change
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra mcp

COPY packs ./packs
COPY worlds ./worlds
COPY deploy ./deploy
# the skill, served over the door by guide() so a guest's agent reads the rules the host's agents read
COPY .claude/skills/embody ./.claude/skills/embody
COPY docs/SCRIPTING.md ./docs/SCRIPTING.md

# the database lives on the platform volume mounted at /data; the hosting principal is `host`
ENV PATH=/app/.venv/bin:$PATH \
    EMBODY_DB=/data/embody.db \
    EMBODY_WORKSPACE=/app \
    EMBODY_AS=host \
    EMBODY_WORLD=glass-reach \
    PORT=8900
RUN mkdir -p /data   # the platform mounts its volume here (a Docker VOLUME line is refused by Railway)
EXPOSE 8900

CMD ["sh", "deploy/start.sh"]
