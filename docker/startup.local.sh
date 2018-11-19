#!/usr/bin/env bash

#
# Use this script to run Sophox locally in the debug mode, with a small OSM file
#

# Assume this script is ran from the git repo
REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null && pwd )"
REPO_URL=-

# Create a data dir in /_data_dir, relative to the root of the repo
DATA_DIR="${REPO_DIR}/_data_dir"
mkdir -p "${DATA_DIR}"

SOPHOX_HOST=sophox.localhost

IS_FULL_PLANET=false
OSM_FILE=new-jersey-latest.osm.pbf
OSM_FILE_URL=http://download.geofabrik.de/north-america/us/${OSM_FILE}
OSM_FILE_MD5_URL="${OSM_FILE_URL}.md5"

# No need to backfill for testing
BACKFILL_DAYS=0

TOTAL_MEMORY_PRCNT=30
DEBUG=true

STARTUP_SCRIPT=${REPO_DIR}/docker/startup.sh

echo "Starting up ${STARTUP_SCRIPT}"
source "${STARTUP_SCRIPT}"
