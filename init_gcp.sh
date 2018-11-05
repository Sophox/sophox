#!/usr/bin/env bash

set -e

if [ ! -d "/mnt/disks/data/" ]; then
  echo '/mnt/disks/data/ not found - follow README_GCP.md to set up persistent disk'
  exit 1
fi

cd /mnt/disks/data/

MAIN_DIR=$PWD
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

echo "Pulling latest from github"
git pull

mkdir -p "${VOLUMES_DIR}"
cd "${VOLUMES_DIR}"

docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "${MAIN_DIR}:/rootfs" \
    --workdir "/rootfs" \
    docker/compose:1.23.1 \
    --file "${REPO_DIR}/docker-compose-gcp.yml"
    --project-directory "${VOLUMES_DIR}" \
    up \
    --detach
