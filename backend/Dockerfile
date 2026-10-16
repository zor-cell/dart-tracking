FROM python:3.12-slim

# system libraries for opencv
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# unprivileged user the app runs as
RUN groupadd --system --gid 10001 zorphy-darts \
    && useradd --system --uid 10001 --gid zorphy-darts --no-create-home zorphy-darts

# copy uv binary
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

# the tracker version passed from the deploy
ARG TRACKER_VERSION
ENV TRACKER_VERSION=$TRACKER_VERSION

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

USER zorphy-darts

# run migration before serving the app
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --app-dir src --host 0.0.0.0 --port 8000"]