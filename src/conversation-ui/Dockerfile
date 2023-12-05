# Build container
FROM docker.io/library/node:21-alpine3.17@sha256:6abd1eabeba303403a2ffbbbd104e21b01d37b1e39faecabac32211b595402cb AS build

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
COPY --chown=$UID:$UID conf/default.conf.template /etc/nginx/templates/default.conf.template

USER $UID
