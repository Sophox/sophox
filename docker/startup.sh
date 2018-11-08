#!/usr/bin/env bash

DATA_DEV=/dev/sdb
DATA_DIR=/mnt/disks/data
COMPOSE_FILE=docker/docker-compose.yml
REPO_URL=https://github.com/Sophox/sophox.git
REPO_BRANCH=gcp
REPO_DIR_NAME=sophox_repo
REPO_DIR=${DATA_DIR}/${REPO_DIR_NAME}
VOLUMES_DIR=${DATA_DIR}/volumes
ACME_FILE=${VOLUMES_DIR}/acme.json
POSTGRES_PASSWORD_FILE=${VOLUMES_DIR}/postgres_password

#
# #####################  Mount Persisted Disk
#

set +e
if (mount | grep -q "${DATA_DEV} on ${DATA_DIR} type ext4"); then
  set -e
  echo "${DATA_DIR} is already mounted"
else
  set -e
  sudo mkdir -p ${DATA_DIR}
  sudo mount -o discard,defaults ${DATA_DEV} ${DATA_DIR}
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
if ! git diff-files --quiet; then
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
mkdir -p "${VOLUMES_DIR}"

if [[ ! -f "${ACME_FILE}" ]]; then
    touch "${ACME_FILE}"
    chmod 600 "${ACME_FILE}"
fi

if [[ ! -f "${POSTGRES_PASSWORD_FILE}" ]]; then
    openssl rand -base64 15 | head -c 10 > "${POSTGRES_PASSWORD_FILE}"
    chmod 400 "${POSTGRES_PASSWORD_FILE}"
fi
POSTGRES_PASSWORD=$(<"${POSTGRES_PASSWORD_FILE}")

#
# #####################  Run docker-compose from a docker container
#

export VOLUMES_DIR
export REPO_DIR
export ACME_FILE
export POSTGRES_PASSWORD

docker run --rm                                   \
    -v /var/run/docker.sock:/var/run/docker.sock  \
    -v "${DATA_DIR}:/rootfs"                      \
    -e VOLUMES_DIR                                \
    -e REPO_DIR                                   \
    -e ACME_FILE                                  \
    -e POSTGRES_PASSWORD                          \
    docker/compose:1.23.1                         \
    --file "/rootfs/${REPO_DIR_NAME}/${COMPOSE_FILE}" \
    up --detach
