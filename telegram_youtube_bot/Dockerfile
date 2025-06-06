FROM python:3.11-slim

# --- Build args ---
ARG PUID=1001
ARG PGID=1001

ENV PUID=${PUID}
ENV PGID=${PGID}
ENV TZ=America/New_York

# --- Install dependencies ---
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        curl \
        gcc \
        build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# --- Create user and group for non-root operation ---
RUN groupadd -g ${PGID} appuser && \
    useradd -u ${PUID} -g ${PGID} -s /bin/bash -m appuser

# --- Set up working directory ---
WORKDIR /app

# --- Install Python dependencies ---
COPY telegram_youtube_bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy source code ---
COPY telegram_youtube_bot/ .

# --- Set ownership on runtime volumes (if mounted as host paths, permissions need to be managed externally) ---
RUN mkdir -p /input /metadata /cookies && \
    chown -R ${PUID}:${PGID} /input /metadata /cookies

# --- Switch to non-root user ---
USER appuser

ENTRYPOINT ["python", "bot.py"]
