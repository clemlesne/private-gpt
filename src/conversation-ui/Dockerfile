# Build container
FROM docker.io/library/node:20-alpine3.17 AS build

RUN npm install --global npm@latest

ARG VERSION
ENV VITE_VERSION=${VERSION}

RUN mkdir /app
WORKDIR /app

COPY . .

RUN npm install \
  && npm run build

# Output container
FROM docker.io/nginxinc/nginx-unprivileged:1.25-alpine3.17

USER root

RUN rm -rf /usr/share/nginx/html/*
COPY --from=build --chown=$UID:$UID /app/dist /usr/share/nginx/html

USER $UID
