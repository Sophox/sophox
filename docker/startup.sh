#!/usr/bin/env bash

DATA_DEV=/dev/sdb
DATA_DIR=/mnt/disks/data
COMPOSE_FILE=docker/docker-compose.yml
REPO_URL=https://github.com/Sophox/sophox.git
REPO_BRANCH=gcp
REPO_DIR_NAME=sophox_repo
REPO_DIR=${DATA_DIR}/${REPO_DIR_NAME}
ACME_FILE=${DATA_DIR}/acme.json
POSTGRES_PASSWORD_FILE=${DATA_DIR}/postgres_password

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
  set +e
  RET_CODE=$(sudo mount -o discard,defaults ${DATA_DEV} ${DATA_DIR}; echo $?)
  set -e
  if [[ ${RET_CODE} -eq 32 ]]; then
    # Format new partition when mount exits with code 32. It usually prints this:
    #   mount: /mnt/disks/data: wrong fs type, bad option, bad superblock on /dev/sdb, missing codepage or helper program, or other error.
    echo "Formatting new partition..."
    sudo mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard "${DATA_DEV}"
    sudo mount -o discard,defaults ${DATA_DEV} ${DATA_DIR}
  fi

  sudo chmod a+w "${DATA_DIR}"

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
if [[ ! -f "${ACME_FILE}" ]]; then
    touch "${ACME_FILE}"
    chmod 600 "${ACME_FILE}"
fi

if [[ ! -f "${POSTGRES_PASSWORD_FILE}" ]]; then
    openssl rand -base64 15 | head -c 12 > "${POSTGRES_PASSWORD_FILE}"
    chmod 400 "${POSTGRES_PASSWORD_FILE}"
fi
POSTGRES_PASSWORD=$(<"${POSTGRES_PASSWORD_FILE}")

#
# #####################  Run docker-compose from a docker container
#

# If DEBUG env is not set, run docker compose in the detached (service) mode
DETACH="" && [[ "${DEBUG}" == "" ]] && DETACH=true

# Must match the list of -e docker params
export DATA_DIR
export REPO_DIR
export ACME_FILE
export POSTGRES_PASSWORD

docker                                                \
    run --rm                                          \
    -e DATA_DIR                                       \
    -e REPO_DIR                                       \
    -e ACME_FILE                                      \
    -e POSTGRES_PASSWORD                              \
                                                      \
    -v "${DATA_DIR}:/rootfs"                          \
    -v /var/run/docker.sock:/var/run/docker.sock      \
                                                      \
    docker/compose:1.23.1                             \
    --file "/rootfs/${REPO_DIR_NAME}/${COMPOSE_FILE}" \
    up ${DETACH:+ --detach}
