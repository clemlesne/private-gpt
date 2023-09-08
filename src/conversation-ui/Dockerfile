# Build container
FROM docker.io/library/node:20-alpine3.17@sha256:b46062adc42a16400adbc25c766966efee688ddd71ef315a5d333238c817dac8 AS build

RUN npm install --global npm@latest

ARG VERSION
ENV VITE_VERSION=${VERSION}

RUN mkdir /app
WORKDIR /app

COPY . .

RUN npm install \
  && npm run build

# Output container
FROM docker.io/nginxinc/nginx-unprivileged:1.25-alpine3.17@sha256:c38e27fdba47f725f49177b88fdd1fd2feef11b13dc11dea3695c3feb2c6d96d

USER root

RUN rm -rf /usr/share/nginx/html/*
COPY --from=build --chown=$UID:$UID /app/dist /usr/share/nginx/html

USER $UID
