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
    if [[ -n "$(ls -A "${OSM_RDF_TTLS}")" ]]; then
        echo "WARNING: Removing partially parsed TTLs in ${OSM_RDF_TTLS}"
        rm -rf "${OSM_RDF_TTLS:?}"/*
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
    fi

    # Create curl data blob without using temporary files
    # This blob assumes that RWStore.properties is located in the same dir as Blazegraph itself
    read -r -d '' LOAD_PROPS << EOT || true
quiet=false
verbose=0
closure=false
durableQueues=true
#Needed for quads
#defaultGraph=
com.bigdata.rdf.store.DataLoader.flush=false
com.bigdata.rdf.store.DataLoader.bufferCapacity=100000
com.bigdata.rdf.store.DataLoader.queueCapacity=10
#Namespace to load
namespace=wdq
#Files to load
fileOrDirs=${OSM_RDF_TTLS}
#Property file (if creating a new namespace)
propertyFile=RWStore.properties
EOT

    if ! echo -e "${LOAD_PROPS}" | curl -X POST --data-binary @- --header 'Content-Type:text/plain' --silent --show-error "${BLAZEGRAPH_HOST}/bigdata/dataloader"; then
        echo
        echo "ERROR: loadRestAPI.sh failed"
        exit 1
    elif ! ls "${OSM_RDF_TTLS}"/*.good >/dev/null 2>&1 ; then
        echo "ERROR: there are no files matching ${OSM_RDF_TTLS}/*.good"
        exit 1
    elif ls "${OSM_RDF_TTLS}"/*.fail >/dev/null 2>&1 ; then
        echo "ERROR: there are failed files - ${OSM_RDF_TTLS}/*.fail"
        exit 1
    elif ls "${OSM_RDF_TTLS}"/*.gz >/dev/null 2>&1 ; then
        echo "ERROR: there are files that were not imported - ${OSM_RDF_TTLS}/*.gz"
        exit 1
    else
        echo "TTL file import was successful"
    fi

    mv "${FLAG_TTL_IMPORTED_PENDING}" "${FLAG_TTL_IMPORTED}"
    echo '########### Done importing TTLs into Blazegraph ###########'
fi
