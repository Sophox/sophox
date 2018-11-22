#!/usr/bin/env bash

#
# Use this script to run Sophox on a dedicated box.
#   * Setup the machine's data dir, e.g. /mnt/data
#   * Run this command (adjust params as needed). Default branch is "master"
#
#   export REPO_BRANCH=rewrite && \
#   export DATA_DIR=/mnt/data && \
#   nohup curl --fail --silent --show-error --location --compressed \
#     https://raw.githubusercontent.com/Sophox/sophox/${REPO_BRANCH}/docker/startup.planet.sh | \
#     bash >> "${DATA_DIR}/startup.log" 2>&1 &


: "${IS_FULL_PLANET:=true}"
: "${OSM_FILE:=planet-latest.osm.pbf}"
: "${OSM_FILE_URL:=https://planet.openstreetmap.org/pbf/${OSM_FILE}}"
: "${OSM_FILE_MD5_URL:=${OSM_FILE_URL}.md5}"

: "${BACKFILL_DAYS:=14}"
: "${TOTAL_MEMORY_PRCNT:=100}"

: "${REPO_BRANCH:=master}"
: "${STARTUP_SCRIPT:=https://raw.githubusercontent.com/Sophox/sophox/${REPO_BRANCH}/docker/startup.sh}"


echo "Starting up ${STARTUP_SCRIPT} with curl"
source <(curl --fail --silent --show-error --location --compressed "${STARTUP_SCRIPT}")
