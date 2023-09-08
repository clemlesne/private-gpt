# Build container
FROM docker.io/library/python:3.11-slim-bullseye@sha256:4fbe5ac40627d19df270ab4c9050f0eb0ffe1402c7706f53d35b13ec7070a747 AS build

RUN apt-get update \
  && apt-get install --yes gcc python3-dev \
  && python3 -m pip install --upgrade pip setuptools wheel

RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH

COPY requirements.txt .
RUN python3 -m pip install --requirement requirements.txt

# Output container
FROM docker.io/library/python:3.11-slim-bullseye@sha256:4fbe5ac40627d19df270ab4c9050f0eb0ffe1402c7706f53d35b13ec7070a747

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
