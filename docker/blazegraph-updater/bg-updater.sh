#!/usr/bin/env bash
set -e
echo "Starting $0"

cd "${BLAZEGRAPH_APP}"

if [[ ! -f "${FLAG_TTL_PARSED}" ]]; then
    echo '########### Waiting for TTLs to be parsed ###########'
    while [[ ! -f "${FLAG_TTL_PARSED}" ]]; do
      sleep 2
    done
else
    # Allow Blazegraph to start up
    sleep 40
fi

# TODO: Loop until Blazegraph is live

if [[ -f "${FLAG_TTL_IMPORT_FAIL}" ]]; then

    echo '########### TTLs import into Blazegraph has failed. Stopping. ###########'
    exit 1

elif [[ ! -f "${FLAG_TTL_IMPORTED}" ]]; then

    echo '########### Importing TTLs into Blazegraph ###########'
    LOADING_FAILED=true

    if ls "${OSM_RDF_TTLS}" | grep -v '\.ttl\.gz$' ; then
        echo "ERROR: unable to start import because there are non .ttl.gz files in ${OSM_RDF_TTLS}"
    elif ! "${BLAZEGRAPH_APP}/loadRestAPI.sh" -d "${OSM_RDF_TTLS}" -h "${BLAZEGRAPH_HOST}"; then
        echo
        echo "ERROR: loadRestAPI.sh failed"
    elif ! ls ${OSM_RDF_TTLS}/*.good; then
        echo "ERROR: there are no files matching ${OSM_RDF_TTLS}/*.good"
    elif ls ${OSM_RDF_TTLS}/*.fail; then
        echo "ERROR: there are failed files - ${OSM_RDF_TTLS}/*.fail"
    elif ls ${OSM_RDF_TTLS}/*.gz; then
        echo "ERROR: there are files that were not imported - ${OSM_RDF_TTLS}/*.gz"
    else
        echo "TTL file import was successful"
        LOADING_FAILED=""
    fi

    if [[ "${LOADING_FAILED}" = "true" ]]; then
        touch "${FLAG_TTL_IMPORT_FAIL}"
        # No need to continue if the original import has failed
        exit 1
    else
        touch "${FLAG_TTL_IMPORTED}"
    fi

    echo '########### Done importing TTLs into Blazegraph ###########'
fi

echo '########### Updating from OSM Wiki ###########'

# It is ok for the updater to crash - it should be safe to restart
set +e
FIRST_LOOP=true

# TODO: INIT_TIME should be set from the value of
#  <http://wiki.openstreetmap.org>  schema:dateModified  ?????

if [[ ! -f "${FLAG_WB_INITIALIZED}" ]]; then
    INIT_TIME="--start 2018-01-01T00:00:00Z"
    touch "${FLAG_WB_INITIALIZED}"
else
    INIT_TIME=""
fi

while :; do

    # First iteration - log the osm2rdf.py command
    if [[ "${FIRST_LOOP}" == "true" ]]; then
        FIRST_LOOP=false
        set -x
    fi

    # conceptUri must be http: to match with the OSM
    "${BLAZEGRAPH_APP}/runUpdate.sh" \
        -h "${BLAZEGRAPH_HOST}" \
        -- \
        ${INIT_TIME} \
        --wikibaseUrl "https://wiki.openstreetmap.org" \
        --conceptUri "${WB_CONCEPT_URI}" \
        --entityNamespaces 120,122 \

    retCode=$?
    { set +x; } 2>/dev/null
    INIT_TIME=""

    echo "runUpdate.sh crashed with exit code $retCode.  Re-spawning in 5 seconds" >&2
    sleep 5

done
