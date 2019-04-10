#!/usr/bin/env bash

IMAGE=sophox/metabot:latest

docker stop metabot ; docker rm metabot ; :

docker pull ${IMAGE}

docker run \
    --detach \
    --name metabot \
    --restart on-failure \
    -e "YURIKBOT_PASSWORD=$(<./password)" \
    -v $PWD/_cache/:/usr/src/app/_cache \
    ${IMAGE}
