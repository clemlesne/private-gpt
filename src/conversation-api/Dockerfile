# Build container
FROM docker.io/library/python:3.11-slim-bullseye@sha256:de917502e531b3f6e4a5acef017e9feef392cf3eb76826fd46d6810c70ae9b5e AS build

RUN apt-get update \
  && apt-get install --yes gcc python3-dev \
  && python3 -m pip install --upgrade pip setuptools wheel

RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH

COPY requirements.txt .
RUN python3 -m pip install --requirement requirements.txt

# Output container
FROM docker.io/library/python:3.11-slim-bullseye@sha256:de917502e531b3f6e4a5acef017e9feef392cf3eb76826fd46d6810c70ae9b5e

ARG VERSION
ENV VERSION=${VERSION}

RUN useradd -m appuser \
  && mkdir /app \
  && chown -R appuser:appuser /app

USER appuser

COPY --from=build /venv /venv
ENV PATH=/venv/bin:$PATH

COPY --chown=appuser:appuser . /app

CMD ["bash", "-c", "WEB_CONCURRENCY=$(nproc --all) cd /app && uvicorn main:api --host 0.0.0.0 --port 8080 --proxy-headers --no-server-header --timeout-keep-alive 30 --header x-version:${VERSION}"]
