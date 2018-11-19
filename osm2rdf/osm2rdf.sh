#!/usr/bin/env bash
set -e

UPDATE_URL=https://planet.openstreetmap.org/replication/minute
MAX_DOWNLOAD=5120

# Note that TEMP may be the same disk as DATA
NODES_CACHE="${OSM_RDF_DATA}/nodes.cache"
NODES_CACHE_TMP="${OSM_RDF_TEMP}/nodes.cache"

[[ -n "${IS_FULL_PLANET}" ]] && CACHE_STRATEGY="dense" || CACHE_STRATEGY="sparse"

mkdir -p "${OSM_RDF_DATA}"
mkdir -p "${OSM_RDF_TEMP}"

if [[ ! -f "${FLAG_TTL_PARSED}" ]]; then

    echo '########### Performing initial OSM->RDF parsing with osm2rdf ###########'

    mkdir -p "${OSM_RDF_TTLS}"
    if [[ ! -z "$(ls -A ${OSM_RDF_TTLS})" ]]; then
        echo "Removing partially parsed TTLs in ${OSM_RDF_TTLS}"
        rm -rf "${OSM_RDF_TTLS}/*"
    fi

    if [[ -f "${NODES_CACHE}" ]]; then
        echo "Removing nodes cache ${NODES_CACHE}"
        rm "${NODES_CACHE}"
    fi
    if [[ -f "${NODES_CACHE_TMP}" ]]; then
        echo "Removing temporary nodes cache ${NODES_CACHE_TMP}"
        rm "${NODES_CACHE_TMP}"
    fi

    set -x
    python3 osm2rdf.py                                        \
        --nodes-file "${NODES_CACHE_TMP}"                     \
        --cache-strategy "${CACHE_STRATEGY}"                  \
        parse "${OSM_FILE_PATH}" "${OSM_RDF_TTLS}"            \
        --workers "${OSM_RDF_WORKERS}"                        \
        --max-statements "${OSM_RDF_MAX_STMTS}"
    { set +x; } 2>/dev/null

    # If nodes.cache did not show up automatically in the data dir,
    # the temp dir is the different from the data dir, so need to move it
    if [[ ! -f "${NODES_CACHE}" ]]; then
        mv "${NODES_CACHE_TMP}" "${NODES_CACHE}"
    fi

    touch "${FLAG_TTL_PARSED}"

    # Once all status flag files are created, delete downloaded OSM file
    # Var must not be quoted (multiple files)
    set +e
    if ls ${FLAGS_TO_DELETE_OSM_FILE} > /dev/null ; then
        set -e
        echo "Deleting ${OSM_FILE_PATH}"

        echo "FIXME!!!!!!!!!!!!!!!!!!!!   Uncomment   rm ${OSM_FILE_PATH}"
        # rm "${OSM_FILE_PATH}"
    fi

    echo "########### Finished parsing with osm2rdf ###########"
fi

if [[ ! -f "${FLAG_TTL_IMPORTED}" ]]; then

    echo '########### Waiting for TTLs to be imported ###########'

    while [[ ! -f "${FLAG_TTL_IMPORTED}" ]]; do
      sleep 2
    done

    echo "########### TTLs have been imported ###########"
fi

echo "########### Running osm2rdf updater ###########"

# It is ok for the updater to crash - it should be safe to restart
set +e
FIRST_LOOP=true

# Give a few seconds to Blazegraph to start if needed
sleep 10

while :; do

    # First iteration - log the osm2rdf.py command
    if [[ "${FIRST_LOOP}" == "true" ]]; then
        FIRST_LOOP=false
        set -x
    fi

    python3 osm2rdf.py                                    \
        --nodes-file "${NODES_CACHE}"                     \
        --cache-strategy "${CACHE_STRATEGY}"              \
        update                                            \
        --host "${SOPHOX_URL}"                            \
        --max-download "${MAX_DOWNLOAD}"                  \
        --update-url "${UPDATE_URL}"

    retCode=$?
    { set +x; } 2>/dev/null

    if [[ ${retCode} = 0 ]]; then
        echo "osm2rdf exited with code=0, stopping" >&2
        exit
    fi

    echo "osm2rdf updater crashed with exit code $retCode.  Re-spawning in 5 seconds" >&2
    sleep 5

done
