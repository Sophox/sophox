#!/usr/bin/env bash
set -e
echo '########### Running osm2rdf parsing converting OSM->RDF TTLs ###########'

# Note that TEMP may be the same disk as DATA
NODES_CACHE="${OSM_RDF_DATA}/nodes.cache"
NODES_CACHE_TMP="${OSM_RDF_TEMP}/nodes.cache"
[[ -n "${IS_FULL_PLANET}" ]] && CACHE_STRATEGY="dense" || CACHE_STRATEGY="sparse"

mkdir -p "${OSM_RDF_DATA}"
mkdir -p "${OSM_RDF_TEMP}"

FLAG_TTL_IMPORTED_PENDING="${FLAG_TTL_IMPORTED}.pending"
if [[ -f "${FLAG_TTL_IMPORTED_PENDING}" ]]; then
    echo "Blazegraph TTL import has crashed in the previous attempt.  Aborting"
    exit 1
fi

if [[ ! -f "${FLAG_TTL_PARSED}" ]]; then

    mkdir -p "${OSM_RDF_TTLS}"
    if [[ ! -z "$(ls -A ${OSM_RDF_TTLS})" ]]; then
        echo "WARNING: Removing partially parsed TTLs in ${OSM_RDF_TTLS}"
        rm -rf "${OSM_RDF_TTLS:?}/*"
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
        echo "Moving temporary node cache: ${NODES_CACHE_TMP} -> ${NODES_CACHE}"
        mv "${NODES_CACHE_TMP}" "${NODES_CACHE}"
    fi

    touch "${FLAG_TTL_PARSED}"
    echo "########### Finished parsing with osm2rdf ###########"
fi


if [[ ! -f "${FLAG_TTL_IMPORTED}" ]]; then
    echo '########### Importing TTLs into Blazegraph ###########'

    touch "${FLAG_TTL_IMPORTED_PENDING}"

    if ls "${OSM_RDF_TTLS}" | grep -v '\.ttl\.gz$' >/dev/null 2>&1 ; then
        echo "ERROR: unable to start import because there are non .ttl.gz files in ${OSM_RDF_TTLS}"
        exit 1
    elif ! "${BLAZEGRAPH_APP}/loadRestAPI.sh" -d "${OSM_RDF_TTLS}" -h "${BLAZEGRAPH_HOST}"; then
        echo
        echo "ERROR: loadRestAPI.sh failed"
        exit 1
    elif ! ls ${OSM_RDF_TTLS}/*.good >/dev/null 2>&1 ; then
        echo "ERROR: there are no files matching ${OSM_RDF_TTLS}/*.good"
        exit 1
    elif ls ${OSM_RDF_TTLS}/*.fail >/dev/null 2>&1 ; then
        echo "ERROR: there are failed files - ${OSM_RDF_TTLS}/*.fail"
        exit 1
    elif ls ${OSM_RDF_TTLS}/*.gz >/dev/null 2>&1 ; then
        echo "ERROR: there are files that were not imported - ${OSM_RDF_TTLS}/*.gz"
        exit 1
    else
        echo "TTL file import was successful"
    fi

    mv "${FLAG_TTL_IMPORTED_PENDING}" "${FLAG_TTL_IMPORTED}"
    echo '########### Done importing TTLs into Blazegraph ###########'
fi
