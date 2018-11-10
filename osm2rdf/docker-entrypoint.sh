#!/usr/bin/env bash
set -e

if [[ "$1" != 'osm2rdf.py' ]]; then
    exec "$@"
else


BIGDATA_URL=http://localhost:9999/bigdata/sparql
UPDATE_URL=https://planet.openstreetmap.org/replication/minute
MAX_DOWNLOAD=5120

# Wait for the Blazegraph container to start up and possibly initialize the new db
sleep 15

if [[ ! -f "${OSM_RDF_DATA}/${OSM_FILE}.parsed" ]]; then

    echo '########### Performing initial OSM->RDF parsing with osm2rdf ###########'
    OUTPUT_DIR="${OSM_RDF_DATA}/ttls"

    if [[ -d "${OUTPUT_DIR}" ]]; then
        echo "Removing partially parsed TTLs in ${OUTPUT_DIR}"
        rm -rf "${OUTPUT_DIR}"
    fi
    mkdir -p "${OUTPUT_DIR}"

    set -x
    python3 osm2rdf.py \
        --nodes-file "${OSM_RDF_DATA}/nodes.cache" \
        --cache-strategy dense \
        --workers 2 \
        parse "${OSM_FILE}" "${OUTPUT_DIR}"
    set +x

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

    python3 osm2rdf.py \
        --nodes-file "${OSM_RDF_DATA}/nodes.cache" \
        --cache-strategy dense \
        update \
        --host "${BIGDATA_URL}" \
        --max-download "${MAX_DOWNLOAD}" \
        --update-url "${UPDATE_URL}"

    set +x
    echo "osm2rdf updater crashed with exit code $?.  Re-spawning in 5 seconds" >&2
    sleep 5

done

fi
