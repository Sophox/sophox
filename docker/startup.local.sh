#!/usr/bin/env bash

#
# Use this script to run Sophox locally in the debug mode, with a small OSM file.
#
# For testing, you should create a file in the docker directory, e.g. docker/_belize.sh
# Make sure the filename begins with an underscore (ignored by git).  See README.md
#
#    #!/usr/bin/env bash
#    OSM_FILE=belize-latest.osm.pbf
#    OSM_FILE_REGION=central-america
#    MAX_MEMORY_MB=3000
#    source "$(dirname "$0")/startup.local.sh"
#

# Assume this script is ran from the git repo
REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null && pwd )"
REPO_URL=-

# Create a data dir in /_data_dir, relative to the root of the repo
DATA_DIR="${REPO_DIR}/_data_dir"
mkdir -p "${DATA_DIR}"

: "${SOPHOX_HOST:=sophox.localhost}"

# No need to backfill for testing
: "${SHAPES_BACKFILL_DAYS:=0}"

# Number of Wikipedia pageview stats (hours) to backfill - one is plenty
: "${PAGEVIEW_HR_FILES:=1}"

# Set maximum memory Sophox will use (in MB).
# Use it if your system does not have a `free` utility (e.g. on a Mac)
#   MAX_MEMORY_MB=6000

# Use 30% of the system's memory. Will be ignored if MAX_MEMORY_MB is set
: "${TOTAL_MEMORY_PRCNT:=30}"
: "${DEBUG:=true}"

STARTUP_SCRIPT=${REPO_DIR}/docker/startup.sh
echo "Starting up ${STARTUP_SCRIPT}"
source "${STARTUP_SCRIPT}"
