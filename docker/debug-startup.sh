#!/usr/bin/env bash

export REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null && pwd )"
export REPO_URL=-

export DATA_DIR="$( cd "${REPO_DIR}/.." >/dev/null && pwd )"
export TEMP_DIR="${DATA_DIR}"

export DATA_DEV=-
export TEMP_DEV=-

export SOPHOX_HOST=sophox.localhost

export OSM_FILE=new-jersey-latest.osm.pbf
export OSM_FILE_URL=http://download.geofabrik.de/north-america/us/new-jersey-latest.osm.pbf
export OSM_FILE_MD5_URL="${OSM_FILE_URL}.md5"
export BACKFILL_DAYS=0
export IS_FULL_PLANET=false

export TOTAL_MEMORY_DIVIDER=2
export DEBUG=true

echo "Running in the local (debug) mode"
echo "REPO_DIR=${REPO_DIR}"
echo "DATA_DIR=${DATA_DIR}"

"${DATA_DIR}/sophox/docker/startup.sh"
