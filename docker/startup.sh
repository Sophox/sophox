#!/usr/bin/env bash
if [[ "$EUID" -ne 0 ]]; then echo "This script must run with sudo" && exit 1; fi

#
# DEBUGGING:  This script can ran interactively on a VM instance:
#    cat /mnt/disks/data/sophox_repo/docker/startup.sh | DEBUG=true sudo -E bash
#
# LOGs:  To see the logs this script generated during the startup use
#    sudo journalctl -u google-startup-scripts.service
#

DATA_DEV=/dev/sdb
DATA_DIR=/mnt/disks/data
COMPOSE_FILE=docker/docker-compose.yml
REPO_URL=https://github.com/Sophox/sophox.git
REPO_BRANCH=gcp
REPO_DIR_NAME=sophox_repo
REPO_DIR=${DATA_DIR}/${REPO_DIR_NAME}
ACME_FILE=${DATA_DIR}/acme.json
POSTGRES_PASSWORD_FILE=${DATA_DIR}/postgres_password
OSMSYNC_DIR=${DATA_DIR}/osmsync
DOWNLOAD_DIR=${DATA_DIR}/download
SOPHOX_HOST=staging.sophox.org

#
# #####################  Mount Persisted Disk
#

set +e
if (mount | grep -q "${DATA_DEV} on ${DATA_DIR} type ext4"); then
  set -e
  echo "${DATA_DIR} is already mounted"
else
  mkdir -p ${DATA_DIR}
  RET_CODE=$(mount -o discard,defaults ${DATA_DEV} ${DATA_DIR}; echo $?)
  set -e
  if [[ ${RET_CODE} -eq 32 ]]; then
    # Format new partition when mount exits with code 32. It usually prints this:
    #   mount: /mnt/disks/data: wrong fs type, bad option, bad superblock on /dev/sdb, missing codepage or helper program, or other error.
    echo "Formatting new partition..."
    mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard "${DATA_DEV}"
    mount -o discard,defaults ${DATA_DEV} ${DATA_DIR}
  fi

  chmod a+w "${DATA_DIR}"

  if [[ ! -d "${DATA_DIR}/lost+found" ]]; then
    echo "Unable to mount ${DATA_DIR} - follow README_GCP.md to set up persistent disk"
    exit 1
  fi
fi

#
# #####################  Clone/update GIT repo
#

if [[ ! -d "${REPO_DIR}" ]]; then
  git clone -b "${REPO_BRANCH}" "${REPO_URL}" "${REPO_DIR}"
fi
if [[ ! -d "${REPO_DIR}/.git" ]]; then
  echo "${REPO_DIR} has no .git directory"
  exit 1
fi

cd "${REPO_DIR}"
set +e
if git diff-files --quiet; then
    set -e
    echo "Pulling latest from github"
    git pull
else
    set -e
    echo "GIT repo has local changes, skipping git pull..."
    git status
fi

#
# #####################  Initialize needed files if they do not exist
#

# File for the Let's encrypt certificate
if [[ ! -f "${ACME_FILE}" ]]; then
    touch "${ACME_FILE}"
    chmod 600 "${ACME_FILE}"
fi

# Generate a random Postgres password
if [[ ! -f "${POSTGRES_PASSWORD_FILE}" ]]; then
    openssl rand -base64 15 | head -c 12 > "${POSTGRES_PASSWORD_FILE}"
    chmod 400 "${POSTGRES_PASSWORD_FILE}"
fi
POSTGRES_PASSWORD=$(<"${POSTGRES_PASSWORD_FILE}")


#
# #####################  Download OSM data
#

# Download the latest OpenStreetMap data if it doesn't exist.
# Interrupted downloads are continued.
# TODO curl bug returns FTP transient problem if file already exists.
# See https://github.com/curl/curl/issues/2464
mkdir -p "${DOWNLOAD_DIR}"
if [[ ! -f "${DOWNLOAD_DIR}/planet-latest.osm.pbf.downloaded" ]]; then
    curl -SL \
        https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf.md5 \
        -o "${DOWNLOAD_DIR}/planet-latest.osm.pbf.md5"

    curl -SL --compressed \
        https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf \
        -o "${DOWNLOAD_DIR}/planet-latest.osm.pbf"

    md5sum --check "${DOWNLOAD_DIR}/planet-latest.osm.pbf.md5"

    touch "${DOWNLOAD_DIR}/planet-latest.osm.pbf.downloaded"
fi

# Create a state file for the planet download. The state file is generated for 1 week previous
# in order not to miss any data changes. Since the planet dump is weekly and we generate this
# file when we download the planet-latest.osm.pbf file, we should not miss any changes.
if [[ ! -d "${OSMSYNC_DIR}" ]]; then
    mkdir -p "${OSMSYNC_DIR}"
    cp "${REPO_DIR_NAME}/docker/sync_config.txt" "${OSMSYNC_DIR}"
    curl -SL \
        "https://replicate-sequences.osm.mazdermind.de/?"`date -u -d@"$$(( \`date +%s\`-1*7*24*60*60))" +"%Y-%m-%d"`"T00:00:00Z" \
        -o "${OSMSYNC_DIR}/state.txt"
fi

#
# #####################  Run docker-compose from a docker container
#

# If DEBUG env is not set, run docker compose in the detached (service) mode
DETACH="" && [[ "${DEBUG}" == "" ]] && DETACH=true

# Must match the list of -e docker params
export DATA_DIR
export REPO_DIR
export DOWNLOAD_DIR
export ACME_FILE
export POSTGRES_PASSWORD
export SOPHOX_HOST

docker run --rm                                       \
    -e DATA_DIR                                       \
    -e REPO_DIR                                       \
    -e DOWNLOAD_DIR                                   \
    -e ACME_FILE                                      \
    -e POSTGRES_PASSWORD                              \
    -e SOPHOX_HOST                                    \
                                                      \
    -v "${DATA_DIR}:/rootfs"                          \
    -v /var/run/docker.sock:/var/run/docker.sock      \
                                                      \
    docker/compose:1.23.1                             \
    --file "/rootfs/${REPO_DIR_NAME}/${COMPOSE_FILE}" \
    up ${DETACH:+ --detach}


#
# #####################  Parse OSM data into Postgres
#

docker run --rm                                        \
        --network=${COMPOSE_PROJECT_NAME}_postgres_conn    \
        -e OSM2PGSQL_VERSION=${OSM2PGSQL_VERSION}          \
        -e PGHOST=${POSTGRES_HOST}                         \
        -e PGPORT=${POSTGRES_PORT}                         \
        -e PGUSER=${POSTGRES_USER}                         \
        -e PGPASSWORD=${POSTGRES_PASSWORD}                 \
        -e PGDATABASE=${POSTGRES_DB}                       \
        -v ${COMPOSE_PROJECT_NAME}_temp_data:/var/tmp      \
        -v ${COMPOSE_PROJECT_NAME}_wdqs_data:/var/lib/wdqs \
        -v $PWD:/var/lib/osm2pgsql                         \
        --entrypoint osm2pgsql                             \
    sophox/osm2pgsql_osmium                                \
        --create
        --slim
        --database ${POSTGRES_DB}
        --flat-nodes /var/lib/wdqs/rgn_nodes.cache \
        -C 26000
        --number-processes 8
        --hstore
        --style /var/lib/osm2pgsql/wikidata.style \

        --tag-transform-script /var/lib/osm2pgsql/wikidata.lua \
        /var/tmp/planet-latest.osm.pbf
