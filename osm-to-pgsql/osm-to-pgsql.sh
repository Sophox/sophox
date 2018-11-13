#!/usr/bin/env bash
set -e

# osm2pgsql expects password in this env var
export PGPASSWORD="${POSTGRES_PASSWORD}"

TOTAL_MEMORY_MB=$(( $(free | awk '/^Mem:/{print $2}') / 1024 ))

# Note that TEMP may be the same disk as DATA
NODES_CACHE="${OSM_PGSQL_DATA}/nodes.cache"
NODES_CACHE_TMP="${OSM_PGSQL_TEMP}/nodes.cache"

mkdir -p "${OSM_PGSQL_DATA}"
mkdir -p "${OSM_PGSQL_TEMP}"

# Wait for the Postgres container to start up and possibly initialize the new db
sleep 30

IMPORTED_FLAG="${OSM_PGSQL_DATA}/status.imported"
if [[ ! -f "${IMPORTED_FLAG}" ]]; then

    echo '########### Performing initial Postgres import with osm-to-pgsql ###########'

    # osm2pgsql cache memory is per CPU, not total
    OSM_PGSQL_MEM_IMPORT=$(( ${TOTAL_MEMORY_MB} / 100 * ${OSM_PGSQL_MEM_IMPORT} / ${OSM_PGSQL_CPU_IMPORT} ))

    if [[ -f "${NODES_CACHE}" ]]; then
        rm "${NODES_CACHE}"
    fi
    if [[ -f "${NODES_CACHE_TMP}" ]]; then
        rm "${NODES_CACHE_TMP}"
    fi

    set -x
    osm2pgsql \
        --create \
        --slim \
        --host "${POSTGRES_HOST}" \
        --username "${POSTGRES_USER}" \
        --database "${POSTGRES_DB}" \
        --flat-nodes "${NODES_CACHE_TMP}" \
        --cache "${OSM_PGSQL_MEM_IMPORT}" \
        --number-processes "${OSM_PGSQL_CPU_IMPORT}" \
        --hstore \
        --style "${OSM_PGSQL_CODE}/wikidata.style" \
        --tag-transform-script "${OSM_PGSQL_CODE}/wikidata.lua" \
        "${OSM_FILE_PATH}"
    { set +x; } 2>/dev/null

    # If nodes.cache did not show up automatically in the data dir,
    # the temp dir is the different from the data dir, so need to move it
    if [[ ! -f "${NODES_CACHE}" ]]; then
        mv "${NODES_CACHE_TMP}" "${NODES_CACHE}"
    fi

    echo "########### Creating Indexes ###########"
    set -x
    psql "--host=${POSTGRES_HOST}" \
         "--username=${POSTGRES_USER}" \
         "--dbname=${POSTGRES_DB}" \
         "--file=${OSM_PGSQL_CODE}/create_indexes.sql"
    { set +x; } 2>/dev/null

    touch "${IMPORTED_FLAG}"

    echo "########### Finished osm-to-pgsql initial import ###########"
fi


echo "########### Running osm-to-pgsql updates every ${LOOP_SLEEP} seconds ###########"

# osm2pgsql cache memory is per CPU, not total
OSM_PGSQL_MEM_UPDATE=$(( ${TOTAL_MEMORY_MB} / 100 * ${OSM_PGSQL_MEM_UPDATE} / ${OSM_PGSQL_CPU_IMPORT} ))

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
        --flat-nodes "${NODES_CACHE}" \
        --cache "${OSM_PGSQL_MEM_UPDATE}" \
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
