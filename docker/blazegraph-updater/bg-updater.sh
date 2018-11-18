#!/usr/bin/env bash
set -e

if [[ ! -f "${FLAG_TTL_PARSED}" ]]; then
    echo '########### Waiting for TTLs to be parsed ###########'
    while [[ ! -f "${FLAG_TTL_PARSED}" ]]; do
      sleep 2
    done
else
    # Allow Blazegraph to start up
    sleep 60
fi

# TODO: Loop until Blazegraph is live

if [[ -f "${FLAG_TTL_IMPORT_FAIL}" ]]; then

    echo '########### TTLs import into Blazegraph has failed. Stopping. ###########'
    exit 1

elif [[ ! -f "${FLAG_TTL_IMPORTED}" ]]; then

    echo '########### Importing TTLs into Blazegraph ###########'

    if "${BLAZEGRAPH_APP}/loadRestAPI.sh" -d "${OSM_RDF_TTLS}" -h "${BLAZEGRAPH_HOST}"; then
        echo "ERROR: loadRestAPI.sh failed"
        LOADING_FAILED=true
    elif ! ls "${OSM_RDF_TTLS}/*.good"; then
        echo "ERROR: there are no files matching ${OSM_RDF_TTLS}/*.good"
        LOADING_FAILED=true
    elif ls "${OSM_RDF_TTLS}/*.fail"; then
        echo "ERROR: there are failed files - ${OSM_RDF_TTLS}/*.fail"
        LOADING_FAILED=true
    elif ls "${OSM_RDF_TTLS}/*.gz"; then
        echo "ERROR: there are files that were not imported - ${OSM_RDF_TTLS}/*.gz"
        LOADING_FAILED=true
    else
        echo "TTL file import was successful"
    fi

    if [[ -n "${LOADING_FAILED}" ]]; then
        touch "${FLAG_TTL_IMPORT_FAIL}"
    else
        touch "${FLAG_TTL_IMPORTED}"
    fi

    echo '########### Done importing TTLs into Blazegraph ###########'
fi

echo '########### Updating from OSM Wiki ###########'

echo 'TODO...'
