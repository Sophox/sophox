#!/usr/bin/env bash


if [[ ! -f "${OSM_PGSQL_DATA}/${OSM_FILE}.imported" ]]; then

    osm2pgsql \
        --create \
        --slim \
        --database "${POSTGRES_DB}" \
        --flat-nodes "${OSM_PGSQL_DATA}/nodes.cache" \
        --cache "${OSM_PGSQL_MEM_IMPORT}" \
        --number-processes "${OSM_PGSQL_CPU_IMPORT}" \
        --hstore \
        --style "${OSM_PGSQL_CODE}/wikidata.style" \
        --tag-transform-script "${OSM_PGSQL_CODE}/wikidata.lua" \
        "${OSM_FILE}"

    touch "${OSM_PGSQL_DATA}/${OSM_FILE}.imported"

fi


while :; do

    osmosis \
        --read-replication-interval "workingDirectory=${OSM_PGSQL_DATA}" \
        --simplify-change \
        --write-xml-change \
        - \
    | osm2pgsql \
        --append \
        --slim \
        --database "${POSTGRES_DB}" \
        --flat-nodes "${OSM_PGSQL_DATA}/nodes.cache" \
        --cache "${OSM_PGSQL_MEM_UPDATE}" \
        --number-processes "${OSM_PGSQL_CPU_UPDATE}" \
        --hstore \
        --style "${OSM_PGSQL_CODE}/wikidata.style" \
        --tag-transform-script "${OSM_PGSQL_CODE}/wikidata.lua" \
        -r xml \
        -

    # Set LOOP_SLEEP to 0 to run this only once, otherwise sleep that many seconds until retry
    [[ "${LOOP_SLEEP}" -eq 0 ]] && exit $?
    sleep "${LOOP_SLEEP}" || exit

done
