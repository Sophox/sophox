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
REPO_DIR=${DATA_DIR}/sophox_repo
ACME_FILE=${DATA_DIR}/acme.json
POSTGRES_PASSWORD_FILE=${DATA_DIR}/postgres_password
DOWNLOAD_DIR=${DATA_DIR}/download
SOPHOX_HOST=staging.sophox.org
OSM_FILE=planet-latest.osm.pbf

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
if [[ ! -f "${DOWNLOAD_DIR}/${OSM_FILE}.downloaded" ]]; then
    curl -SL \
        https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf.md5 \
        -o "${DOWNLOAD_DIR}/${OSM_FILE}.md5"

    curl -SL --compressed \
        https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf \
        -o "${DOWNLOAD_DIR}/${OSM_FILE}"

    pushd "${DOWNLOAD_DIR}"
    md5sum --check "${DOWNLOAD_DIR}/${OSM_FILE}.md5"
    popd

    touch "${DOWNLOAD_DIR}/${OSM_FILE}.downloaded"
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
export OSM_FILE

docker run --rm                                       \
    -e DATA_DIR                                       \
    -e REPO_DIR                                       \
    -e DOWNLOAD_DIR                                   \
    -e ACME_FILE                                      \
    -e POSTGRES_PASSWORD                              \
    -e SOPHOX_HOST                                    \
    -e OSM_FILE                                       \
    -e REPO_DIR2=/git_repo                            \
                                                      \
    -v "${REPO_DIR}:/git_repo"                        \
    -v /var/run/docker.sock:/var/run/docker.sock      \
                                                      \
    docker/compose:1.23.1                             \
    --file "/git_repo/${COMPOSE_FILE}" \
    up ${DETACH:+ --detach}
