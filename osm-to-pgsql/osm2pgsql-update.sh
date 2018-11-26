#!/usr/bin/env bash
set -e
echo "########### Running osm-to-pgsql updates every '${LOOP_SLEEP}' seconds ###########"

# osm2pgsql expects password in this env var
export PGPASSWORD="${POSTGRES_PASSWORD}"
NODES_CACHE="${OSM_PGSQL_DATA}/nodes.cache"

if [[ ! -f "${FLAG_PG_IMPORTED}" ]]; then
  echo "########### ERROR: osm2pgsql has not been imported"
  exit 1
elif [[ -n "${IS_FULL_PLANET}" ]] && [[ ! -f "${NODES_CACHE}" ]]; then
  echo "########### ERROR: osm2pgsql node cache not found:  ${NODES_CACHE}"
  exit 1
fi

# osm2pgsql cache memory is per CPU, not total
OSM_PGSQL_MEM_UPDATE_PER_CPU=$(( ${OSM_PGSQL_MEM_UPDATE} / ${OSM_PGSQL_CPU_UPDATE} ))

FIRST_LOOP=true
while :; do

    # It is ok for the import to crash - it should be safe to restart
    set +e

    # First iteration - log the osmosis + osm2pgsql commands
    if [[ "${FIRST_LOOP}" == "true" ]]; then
        FIRST_LOOP=false
        set -x
    fi

    osmosis \
        --read-replication-interval "workingDirectory=${OSM_PGSQL_DATA}" \
        --simplify-change \
        --write-xml-change \
        - \
    | osm2pgsql \
        --append \
        --slim \
        --host "${POSTGRES_HOST}" \
        --username "${POSTGRES_USER}" \
        --database "${POSTGRES_DB}" \
        ${IS_FULL_PLANET:+ --flat-nodes "${NODES_CACHE}"} \
        --cache "${OSM_PGSQL_MEM_UPDATE_PER_CPU}" \
        --number-processes "${OSM_PGSQL_CPU_UPDATE}" \
        --hstore \
        --style "${OSM_PGSQL_CODE}/wikidata.style" \
        --tag-transform-script "${OSM_PGSQL_CODE}/wikidata.lua" \
        -r xml \
        -

    { set +x; } 2>/dev/null

    # Set LOOP_SLEEP to 0 to run this only once, otherwise sleep that many seconds until retry
    [[ "${LOOP_SLEEP}" -eq 0 ]] && exit $?
    sleep "${LOOP_SLEEP}" || exit

done
