#!/usr/bin/env bash
set -e

# osm2pgsql expects password in this env var
export PGPASSWORD="${POSTGRES_PASSWORD}"

mkdir -p "${OSM_PGSQL_DATA}"
mkdir -p "${OSM_PGSQL_TEMP}"

# Note that TEMP may be the same disk as DATA
NODES_CACHE="${OSM_PGSQL_DATA}/nodes.cache"
NODES_CACHE_TMP="${OSM_PGSQL_TEMP}/nodes.cache"

FLAG_PG_IMPORTED_PENDING="${FLAG_PG_IMPORTED}.pending"
if [[ -f "${FLAG_PG_IMPORTED_PENDING}" ]]; then
    echo "Postgres import has crashed in the previous attempt.  Aborting"
    exit 1
fi

if [[ ! -f "${FLAG_PG_IMPORTED}" ]]; then

    echo '########### Performing initial Postgres import with osm-to-pgsql ###########'
    touch "${FLAG_PG_IMPORTED_PENDING}"

    # osm2pgsql cache memory is per CPU, not total
    OSM_PGSQL_MEM_IMPORT_PER_CPU=$(( ${OSM_PGSQL_MEM_IMPORT} / ${OSM_PGSQL_CPU_IMPORT} ))

    if [[ -n "${IS_FULL_PLANET}" ]]; then
      if [[ -f "${NODES_CACHE}" ]]; then
          rm "${NODES_CACHE}"
      fi
      if [[ -f "${NODES_CACHE_TMP}" ]]; then
          rm "${NODES_CACHE_TMP}"
      fi
    fi

    set -x
    osm2pgsql \
        --create \
        --slim \
        --host "${POSTGRES_HOST}" \
        --username "${POSTGRES_USER}" \
        --database "${POSTGRES_DB}" \
        ${IS_FULL_PLANET:+ --flat-nodes "${NODES_CACHE_TMP}"} \
        --cache "${OSM_PGSQL_MEM_IMPORT_PER_CPU}" \
        --number-processes "${OSM_PGSQL_CPU_IMPORT}" \
        --hstore \
        --style "${OSM_PGSQL_CODE}/wikidata.style" \
        --tag-transform-script "${OSM_PGSQL_CODE}/wikidata.lua" \
        "${OSM_FILE_PATH}"
    { set +x; } 2>/dev/null

    if [[ -n "${IS_FULL_PLANET}" ]]; then
      # If nodes.cache did not show up automatically in the data dir,
      # the temp dir is the different from the data dir, so need to move it
      if [[ ! -f "${NODES_CACHE}" ]]; then
        echo "Moving temporary node cache: ${NODES_CACHE_TMP} -> ${NODES_CACHE}"
        mv "${NODES_CACHE_TMP}" "${NODES_CACHE}"
      fi
    fi

    echo "########### Creating Indexes ###########"
    set -x
    psql "--host=${POSTGRES_HOST}" \
         "--username=${POSTGRES_USER}" \
         "--dbname=${POSTGRES_DB}" \
         "--file=${OSM_PGSQL_CODE}/create_indexes.sql"
    { set +x; } 2>/dev/null

    mv "${FLAG_PG_IMPORTED_PENDING}" "${FLAG_PG_IMPORTED}"
    echo "########### Finished osm-to-pgsql initial import ###########"
fi
