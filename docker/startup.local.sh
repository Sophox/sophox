#!/usr/bin/env bash

#
# Use this script instead of startup.sh to run Sophox locally in the debug mode, with a much smaller file
#

export REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null && pwd )"
export REPO_URL=-

export DATA_DIR="${REPO_DIR}/_data_dir"
mkdir -p "${DATA_DIR}"

export TEMP_DIR="${DATA_DIR}"

export DATA_DEV=-
export TEMP_DEV=-

export SOPHOX_HOST=sophox.localhost

export OSM_FILE=new-jersey-latest.osm.pbf
export OSM_FILE_URL=http://download.geofabrik.de/north-america/us/new-jersey-latest.osm.pbf
export OSM_FILE_MD5_URL="${OSM_FILE_URL}.md5"
export BACKFILL_DAYS=0
export IS_FULL_PLANET=false

export TOTAL_MEMORY_PRCNT=60
export DEBUG=true

echo "Running in the local (debug) mode"
echo "REPO_DIR=${REPO_DIR}"
echo "DATA_DIR=${DATA_DIR}"

"${REPO_DIR}/docker/startup.sh"
