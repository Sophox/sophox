#!/usr/bin/env bash

docker rm metabot || 0

docker run \
    --name metabot \
    --restart on-failure \
    -e "YURIKBOT_PASSWORD=$(<./password)" \
    -v $PWD/_cache/:/usr/src/app/_cache \
    sophox/metabot:latest
