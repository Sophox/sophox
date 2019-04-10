#!/usr/bin/env bash

docker stop metabot ; docker rm metabot ; :

docker run \
    --name metabot \
    --restart on-failure \
    -e "YURIKBOT_PASSWORD=$(<./password)" \
    -v $PWD/_cache/:/usr/src/app/_cache \
    sophox/metabot:latest
