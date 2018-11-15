#!/usr/bin/env bash
set -e

if [[ ! -f "${FLAG_TTL_PARSED}" ]]; then
    echo '########### Waiting for TTLs to be parsed ###########'
    while [[ ! -f "${FLAG_TTL_PARSED}" ]]; do
      sleep 2
    done
fi

if [[ ! -f "${FLAG_TTL_IMPORTED}" ]]; then
    echo '########### Importing TTLs into Blazegraph ###########'

    ${BLAZEGRAPH_APP}/loadRestAPI.sh -d "${OSM_RDF_TTLS}" -h "${BLAZEGRAPH_HOST}"

    touch "${FLAG_TTL_IMPORTED}"
    echo '########### Done importing TTLs into Blazegraph ###########'
fi

echo '########### Updating from OSM Wiki ###########'

echo 'TODO...'
