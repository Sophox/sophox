#!/usr/bin/env bash

DATA_DEV=/dev/sdb
MAIN_DIR=/mnt/disks/data

set +e
if (mount | grep -q "${DATA_DEV} on ${MAIN_DIR} type ext4"); then

  set -e
  echo "${MAIN_DIR} is already mounted"

else

  set -e
  sudo mkdir -p ${MAIN_DIR}
  sudo mount -o discard,defaults ${DATA_DEV} ${MAIN_DIR}

  if [ ! -d "${MAIN_DIR}/lost+found" ]; then
    echo "Unable to mount ${MAIN_DIR} - follow README_GCP.md to set up persistent disk"
    exit 1
  fi

fi


cd "${MAIN_DIR}"

REPO_DIR=${MAIN_DIR}/sophox_git
VOLUMES_DIR=${MAIN_DIR}/volumes

if [ ! -d "${REPO_DIR}" ]; then
  git clone -b gcp https://github.com/Sophox/sophox.git "${REPO_DIR}"
fi

if [ ! -d "${REPO_DIR}/.git" ]; then
  echo "${REPO_DIR} has no .git directory"
  exit 1
fi

cd "${REPO_DIR}"


set +e
git diff-files --quiet
retVal=$?
set -e

if [[ "${retVal}" == 0 ]]; then
    echo "Pulling latest from github"
    git pull
else
    echo "GIT repo has local changes, skipping git pull..."
    git status
fi

mkdir -p "${VOLUMES_DIR}"
cd "${VOLUMES_DIR}"

docker run --rm                                         \
    -v /var/run/docker.sock:/var/run/docker.sock        \
    -v "${MAIN_DIR}:/rootfs"                            \
    --workdir "/rootfs"                                 \
    docker/compose:1.23.1                               \
    --file "/rootfs/sophox_git/docker-compose-gcp.yml"  \
    --project-directory "/rootfs/volumes"               \
    up                                                  \
    --detach
