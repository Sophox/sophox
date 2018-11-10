#!/usr/bin/env bash
set -e

if [[ "$1" != 'osm2rdf.py' ]]; then
    exec "$@"
else


BIGDATA_URL=http://localhost:9999/bigdata/sparql
UPDATE_URL=https://planet.openstreetmap.org/replication/minute
MAX_DOWNLOAD=5120


# Create a state file for the planet download. The state file is generated for 1 week previous
# in order not to miss any data changes. Since the planet dump is weekly and we generate this
# file when we download the planet-latest.osm.pbf file, we should not miss any changes.
if [[ ! -f "${OSM_RDF_DATA}/state.txt" ]]; then

    echo '########### Initializing osm-to-pgsql state file ###########'

    cp "${OSM_RDF_CODE}/sync_config.txt" "${OSM_RDF_DATA}"

    curl -SL \
        "https://replicate-sequences.osm.mazdermind.de/?"`date -u -d@"$$(( \`date +%s\`-1*7*24*60*60))" +"%Y-%m-%d"`"T00:00:00Z" \
        -o "${OSM_RDF_DATA}/state.txt"
fi


# Wait for the Blazegraph container to start up and possibly initialize the new db
sleep 15

if [[ ! -f "${OSM_RDF_DATA}/${OSM_FILE}.parsed" ]]; then

    echo '########### Performing initial OSM->RDF parsing with osm2rdf ###########'
    TTLS="${OSM_RDF_DATA}/ttls"

    if [[ -d "${TTLS}" ]]; then
        echo "Removing partially parsed TTLs in ${TTLS}"
        rd -rf "${TTLS}"
    fi
    mkdir -p "${TTLS}"

    python3 osm2rdf.py \
        --nodes-file "${OSM_RDF_DATA}/nodes.cache" \
        --cache-strategy dense \
        parse "${OSM_FILE}" "${OSM_RDF_DATA}"

    touch "${OSM_RDF_DATA}/${OSM_FILE}.parsed"

fi

echo "########### Running osm2rdf updater ###########"

# It is ok for the updater to crash - it should be safe to restart
set +e

until python3 osm2rdf.py \
    --nodes-file "${OSM_RDF_DATA}/nodes.cache" \
    --cache-strategy dense \
    update \
    --host "${BIGDATA_URL}" \
    --max-download "${MAX_DOWNLOAD}" \
    --update-url "${UPDATE_URL}"
do
    echo "osm2rdf updater crashed with exit code $?.  Re-spawning in 5 seconds" >&2
    sleep 5
done
fi
