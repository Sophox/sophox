#!/usr/bin/env bash

#
# Use this script to run Sophox on the GCP cloud
#

# Format and mount these GCP disks
: "${DATA_DEV:=/dev/sdb}"
: "${TEMP_DEV:=/dev/nvme0n1}"
# as these mount points
: "${DATA_DIR:=/mnt/disks/data}"
: "${TEMP_DIR:=/mnt/disks/temp}"

# FIXME!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Should be sophox.org by default
: "${SOPHOX_HOST:=staging.sophox.org}"

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
