#!/usr/bin/env bash

docker run \
    -it \
    --rm \
    --network=docker_postgres_conn \
    -e PGHOST=postgres \
    -e PGUSER=sophox \
    -e PGPASSWORD=`sudo cat /mnt/disks/data/postgres_password` \
    -e PGDATABASE=gis \
    postgres:9.6 psql
