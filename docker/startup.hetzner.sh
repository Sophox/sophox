#!/usr/bin/env bash

#
# Use this script to run Sophox on a Hetzner box
#

: "${DATA_DIR:=/mnt/data}"

: "${IS_FULL_PLANET:=true}"
: "${OSM_FILE:=planet-latest.osm.pbf}"
: "${OSM_FILE_URL:=https://planet.openstreetmap.org/pbf/${OSM_FILE}}"
: "${OSM_FILE_MD5_URL:=${OSM_FILE_URL}.md5}"

: "${BACKFILL_DAYS:=14}"
: "${TOTAL_MEMORY_PRCNT:=100}"

: "${REPO_BRANCH:=rewrite}"
: "${STARTUP_SCRIPT:=https://raw.githubusercontent.com/Sophox/sophox/${REPO_BRANCH}/docker/startup.sh}"


echo "Starting up ${STARTUP_SCRIPT} with curl"
source <(curl --fail --silent --show-error --location --compressed "${STARTUP_SCRIPT}")
