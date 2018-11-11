#!/usr/bin/env bash
set -e

if [[ "$1" != 'osm2rdf.py' ]]; then
    exec "$@"
else


BIGDATA_URL=http://localhost:9999/bigdata/sparql
UPDATE_URL=https://planet.openstreetmap.org/replication/minute
MAX_DOWNLOAD=5120

# Note that TEMP may be the same disk as DATA
NODES_CACHE="${OSM_RDF_DATA}/nodes.cache"
NODES_CACHE_TMP="${OSM_RDF_TEMP}/nodes.cache"

mkdir -p "${OSM_RDF_DATA}"
mkdir -p "${OSM_RDF_TEMP}"

# Wait for the Blazegraph container to start up and possibly initialize the new db
sleep 30

if [[ ! -f "${OSM_RDF_DATA}/${OSM_FILE}.parsed" ]]; then

    echo '########### Performing initial OSM->RDF parsing with osm2rdf ###########'
    OUTPUT_DIR="${OSM_RDF_DATA}/ttls"

    if [[ -d "${OUTPUT_DIR}" ]]; then
        echo "Removing partially parsed TTLs in ${OUTPUT_DIR}"
        rm -rf "${OUTPUT_DIR}"
    fi
    mkdir -p "${OUTPUT_DIR}"

    if [[ -f "${NODES_CACHE}" ]]; then
        rm "${NODES_CACHE}"
    fi
    if [[ -f "${NODES_CACHE_TMP}" ]]; then
        rm "${NODES_CACHE_TMP}"
    fi

    set -x
    python3 osm2rdf.py                             \
        --nodes-file "${NODES_CACHE_TMP}" \
        --cache-strategy dense                     \
        parse "${OSM_FILE}" "${OUTPUT_DIR}"        \
        --workers "${OSM_RDF_WORKERS}"
    set +x

    # If nodes.cache did not show up automatically in the data dir,
    # the temp dir is the different from the data dir, so need to move it
    if [[ ! -f "${NODES_CACHE}" ]]; then
        mv --no-target-directory "${NODES_CACHE_TMP}" "${NODES_CACHE}"
    fi

    touch "${OSM_RDF_DATA}/${OSM_FILE}.parsed"
    echo "########### Finished parsing with osm2rdf ###########"
fi

exit


echo "########### Running osm2rdf updater ###########"

# It is ok for the updater to crash - it should be safe to restart
set +e
FIRST_LOOP=true

while :; do

    # First iteration - log the osm2rdf.py command
    if [[ "${FIRST_LOOP}" == "true" ]]; then
        FIRST_LOOP=false
        set -x
    fi

    python3 osm2rdf.py                             \
        --nodes-file "${NODES_CACHE}" \
        --cache-strategy dense                     \
        update                                     \
        --host "${BIGDATA_URL}"                    \
        --max-download "${MAX_DOWNLOAD}"           \
        --update-url "${UPDATE_URL}"

    set +x
    echo "osm2rdf updater crashed with exit code $?.  Re-spawning in 5 seconds" >&2
    sleep 5

done

fi
