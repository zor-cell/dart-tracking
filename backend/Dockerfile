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

# the announcer's Piper voices (see VOICES in services/speech.py), in a layer of their own
RUN .venv/bin/python -m piper.download_voices --download-dir /app/voices \
    de_DE-thorsten-medium en_GB-alan-medium

COPY . .
RUN uv sync --frozen --no-dev

# every announcer phrase that names no player, voiced into the image
RUN .venv/bin/python scripts/app/prebuild_speech.py --voices /app/voices --out /app/speech-prebuilt \
    && mkdir /app/speech && chown zorphy-darts:zorphy-darts /app/speech
ENV VOICES_DIR=/app/voices \
    SPEECH_PREBUILT_DIR=/app/speech-prebuilt \
    SPEECH_DIR=/app/speech

# the tracker version passed from the deploy
ARG TRACKER_VERSION
ENV TRACKER_VERSION=$TRACKER_VERSION

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

USER zorphy-darts

# run migration before serving the app with limited ws messages size
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --app-dir src --host 0.0.0.0 --port 8000 --ws-max-size 2097152"]