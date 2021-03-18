#!/usr/bin/env bash

#
# Use this script to run Sophox on the GCP cloud
#

# Format and mount these GCP disks.  Set *_DEV to "-" to skip disk initialization & mounting
: "${DATA_DEV:=/dev/sdb}"
: "${TEMP_DEV:=/dev/nvme0n1}"
# as these mount points
: "${DATA_DIR:=/mnt/disks/data}"
: "${TEMP_DIR:=/mnt/disks/temp}"

: "${SOPHOX_HOST:=sophox.org}"

: "${IS_FULL_PLANET:=true}"
: "${OSM_FILE:=planet-latest.osm.pbf}"
: "${OSM_FILE_URL:=https://planet.openstreetmap.org/pbf/${OSM_FILE}}"
: "${OSM_FILE_MD5_URL:=${OSM_FILE_URL}.md5}"

: "${SHAPES_BACKFILL_DAYS:=14}"
: "${TOTAL_MEMORY_PRCNT:=100}"

# Reduce the size of the initial pageviews data (so it would fit on 375GB)
: "${PAGEVIEW_HR_FILES:=0}"

: "${REPO_BRANCH:=main}"
: "${STARTUP_SCRIPT:=https://raw.githubusercontent.com/Sophox/sophox/${REPO_BRANCH}/docker/startup.sh}"


echo "DATA_DEV='${DATA_DEV}'"
echo "TEMP_DEV='${TEMP_DEV}'"

#
# #####################  Initialize and Mount Persisted Disk
#

function init_disk {
    local device_id="$1"
    local mount_dir="$2"
    local is_optional="$3"

    # If no device id is given, make sure data/temp dirs exist
    if [[ -z "${device_id}" ]] || [[ "${device_id}" -ne "-" ]]; then
      if [[ ! -d "${mount_dir}" ]]; then
        echo "Directory ${mount_dir} does not exist, and device id is not set. Aborting."
        exit 1
      else
        return 0
      fi
    fi

    if [[ "$EUID" -ne 0 ]]; then
      # local execution?
      echo "This script must run with sudo"
      exit 1
    fi

    echo "########### Setting up ${device_id} as ${mount_dir}"
    if (mount | grep -q "${device_id} on ${mount_dir} type ext4"); then
      echo "${mount_dir} is already mounted"
      return 0
    fi

    echo "Checking if device ${device_id} exists:"
    if ! lsblk --noheadings ${device_id}; then
        if [[ "${is_optional}" = true ]]; then
            echo "Optional disk ${device_id} does not exist, skipping"
            return 111
        else
            echo "Data disk ${device_id} does not exist"
            exit 1
        fi
    fi

    mkdir -p "${mount_dir}"

    local mount_options="discard,defaults"
    if [[ "${is_optional}" = true ]]; then
        mount_options="${mount_options},nobarrier"
    fi

    local ret_code=$(mount -o "${mount_options}" "${device_id}" "${mount_dir}"; echo $?)
    if [[ ${ret_code} -eq 32 ]]; then
      # Format new partition when mount exits with code 32. It usually prints this:
      #   mount: /mnt/disks/data: wrong fs type, bad option, bad superblock on /dev/sdb, missing codepage or helper program, or other error.
      echo "Formatting new partition...".
      if ! mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard "${device_id}"; then
        echo "Formatting failed for ${device_id}"
        exit 1
      fi
      if ! mount -o discard,defaults "${device_id}" "${mount_dir}"; then
        echo "Unable to mount ${mount_dir} on ${device_id}"
        exit 1
      fi
    fi

    chmod a+w "${mount_dir}"
    if [[ ! -d "${mount_dir}/lost+found" ]]; then
      echo "Unable to mount ${mount_dir} on ${device_id}"
      exit 1
    fi
    echo "${device_id} has been mounted as ${mount_dir}"
    return 0
}

init_disk "${DATA_DEV}" "${DATA_DIR}"

if ! init_disk "${TEMP_DEV}" "${TEMP_DIR}" true; then
  TEMP_DIR=""
fi


echo "Starting up ${STARTUP_SCRIPT} with curl"
source <(curl --fail --silent --show-error --location --compressed "${STARTUP_SCRIPT}")
