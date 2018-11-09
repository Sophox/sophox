#!/usr/bin/env bash

while :; do
    osmosis \
        --read-replication-interval workingDirectory=/var/lib/wdqs/geosync_workdir \
        --simplify-change \
        --write-xml-change - \
    | osm2pgsql \
        --append \
        --slim \
        --database "${POSTGRES_DB}" \
        --flat-nodes "${PG_UPDATER_DATA}/nodes.cache" \
        --cache "${PG_UPDATER_MEM}" \
        --number-processes "${PG_UPDATER_CPU}" \
        --hstore \
        --style /var/lib/osm2pgsql/wikidata.style \
        --tag-transform-script /var/lib/osm2pgsql/wikidata.lua \
        -r xml -
    [ "${LOOP}" -eq 0 ] && exit $?
    sleep "${LOOP}" || exit
done