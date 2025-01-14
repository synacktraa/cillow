# Multi-stage build. Build published at: https://hub.docker.com/repository/docker/synacktra/cillow

FROM python:3.12-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /cillow

COPY . .

RUN uv pip install --system --no-cache .

RUN rm -rf /root/.cache \
    && find /usr/local -depth \
    -type f -name '*.pyc' -delete \
    -o -type d -name __pycache__ -delete


FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
