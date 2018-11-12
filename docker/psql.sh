#!/usr/bin/env bash

# This command should be in sync with the docker-compose's "postgres" service
docker run \
    -it \
    --rm \
    --network=docker_postgres_conn \
    -e PGHOST=postgres \
    -e PGUSER=sophox \
    -e PGPASSWORD=`sudo cat /mnt/disks/data/postgres_password` \
    -e PGDATABASE=gis \
    openmaptiles/postgis:2.9 psql
