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
TEMP_DEV=/dev/nvme0n1
TEMP_DIR=/mnt/disks/temp
STATUS_DIR=${DATA_DIR}/status
COMPOSE_FILE=docker/docker-compose.yml
REPO_URL=https://github.com/Sophox/sophox.git
REPO_BRANCH=gcp
REPO_DIR=${DATA_DIR}/sophox_repo
ACME_FILE=${DATA_DIR}/acme.json
POSTGRES_PASSWORD_FILE=${DATA_DIR}/postgres_password
DOWNLOAD_DIR=${DATA_DIR}/download
SOPHOX_HOST=staging.sophox.org
OSM_FILE=planet-latest.osm.pbf
OSM_PGSQL_DATA_DIR=${DATA_DIR}/osm-pgsql
OSM_RDF_DATA_DIR=${DATA_DIR}/osm-rdf
BLAZEGRAPH_ENDPOINTS='"wiki.openstreetmap.org"'

# This path must match docker-compose.yml - blazegraph volume
BLAZEGRAPH_JNL_DATA_FILE=/app-data/osmdata.jnl

TOTAL_MEMORY_MB=$(( $(free | awk '/^Mem:/{print $2}') / 1024 ))

#
# #####################  Initialize and Mount Persisted Disk
#

function init_disk {
    local device_id="$1"
    local mount_dir="$2"

    echo "########### Setting up ${device_id} as ${mount_dir} ###########"
    set +e
    if (mount | grep -q "${device_id} on ${mount_dir} type ext4"); then
      set -e
      echo "${mount_dir} is already mounted"
      return
    fi

    echo "Checking if device ${device_id} exists:"
    if ! lsblk --noheadings ${device_id}; then
        if [[ "${device_id}" == "${TEMP_DEV}" ]]; then
            echo "Temporary disk does not exist, skipping"
            TEMP_DIR=""
            return 0
        else
            echo "Data disk does not exist"
            exit 1
        fi
    fi

    mkdir -p "${mount_dir}"
    RET_CODE=$(mount -o discard,defaults "${device_id}" "${mount_dir}"; echo $?)
    if [[ ${RET_CODE} -eq 32 ]]; then
      # Format new partition when mount exits with code 32. It usually prints this:
      #   mount: /mnt/disks/data: wrong fs type, bad option, bad superblock on /dev/sdb, missing codepage or helper program, or other error.
      echo "Formatting new partition..."
      set -e
      mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard "${device_id}"
      mount -o discard,defaults "${device_id}" "${mount_dir}"
    fi

    set -e
    chmod a+w "${mount_dir}"
    if [[ ! -d "${mount_dir}/lost+found" ]]; then
      echo "Unable to mount ${mount_dir} on ${device_id}"
      exit 1
    fi
    echo "${device_id} has been mounted as ${mount_dir}"
}

init_disk "${DATA_DEV}" "${DATA_DIR}"
init_disk "${TEMP_DEV}" "${TEMP_DIR}"

#
# #####################  Clone/update GIT repo
#

echo "########### Updating git repo ${REPO_DIR} ###########"
set -e
if [[ ! -d "${REPO_DIR}" ]]; then
  git clone -b "${REPO_BRANCH}" --recurse-submodules -j4 "${REPO_URL}" "${REPO_DIR}"
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
    git submodule update --init --recursive
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
    echo "########### Creating ${ACME_FILE} ###########"
    touch "${ACME_FILE}"
    chmod 600 "${ACME_FILE}"
fi

# Generate a random Postgres password
if [[ ! -f "${POSTGRES_PASSWORD_FILE}" ]]; then
    echo "########### Creating ${POSTGRES_PASSWORD_FILE} ###########"
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

FLAG_DOWNLOADED="${STATUS_DIR}/${OSM_FILE}.downloaded"
if [[ ! -f "${FLAG_DOWNLOADED}" ]]; then
    echo "########### Downloading ${OSM_FILE} ###########"
    set -x
    curl --silent --show-error --location --compressed \
        https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf.md5 \
        --output "${DOWNLOAD_DIR}/${OSM_FILE}.md5"

    curl --silent --show-error --location --compressed \
        https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf \
        --output "${DOWNLOAD_DIR}/${OSM_FILE}"
    { set +x; } 2>/dev/null

    pushd "${DOWNLOAD_DIR}"
    md5sum --check "${DOWNLOAD_DIR}/${OSM_FILE}.md5"
    popd

    touch "${FLAG_DOWNLOADED}"
fi

# Create a state file for the planet download. The state file is generated for N weeks prior to now
# in order not to miss any data changes. Since the planet dump is weekly and we generate this
# file when we download the planet-latest.osm.pbf file, we should not miss any changes.
function init_state {
    local data_dir=$1
    mkdir -p "${data_dir}"
    if [[ ! -f "${data_dir}/state.txt" ]]; then

        echo "########### Initializing ${data_dir} state files ########### ###########"
        cp "${REPO_DIR}/docker/osmosis_configuration.txt" "${data_dir}/configuration.txt"
        touch "${data_dir}/download.lock"
        # Current date minus N weeks (first number)
        local start_date=$(( `date +%s` - 2*7*24*60*60 ))
        local start_date_fmt=$(date --utc --date="@${start_date}" +"%Y-%m-%dT00:00:00Z")
        set -x
        curl --silent --show-error --location --compressed \
            "https://replicate-sequences.osm.mazdermind.de/?${start_date_fmt}" \
            --output "${data_dir}/state.txt"
        { set +x; } 2>/dev/null
    fi
}

init_state "${OSM_PGSQL_DATA_DIR}"
init_state "${OSM_RDF_DATA_DIR}"

#
# #####################  Compile Blazegraph
#

set -e
FLAG_BUILD_BLAZE="${STATUS_DIR}/blazegraph.build"
if [[ ! -f "${FLAG_BUILD_BLAZE}" ]]; then

    # Extract the version number from the line right above the <packaging>pom</packaging>
    BLAZE_VERSION=$(grep --before-context=1 '<packaging>pom</packaging>' "${REPO_DIR}/wikidata-query-rdf/pom.xml" \
        | head --lines=1 \
        | sed 's/^[^>]*>\([^<]*\)<.*$/\1/g')
    echo "########### Building Blazegraph ${BLAZE_VERSION} ###########"

    # Cleanup the source code dir
    cd "${REPO_DIR}/wikidata-query-rdf"
    set +e
    if git diff-files --quiet; then
        set -e
        echo "Cleaning ${PWD}"
        git clean -fdx
    else
        set -e
        echo "GIT repo ${PWD} has local changes, skipping git clean..."
        git status
    fi

    # Compile & package Blazegraph, and extract result to the /blazegraph dir
    set -x
    docker run --rm \
        -v "${REPO_DIR}/wikidata-query-rdf:/app-src:rw" \
        -v "${DATA_DIR}/blazegraph_app:/app:rw" \
        -v "${DATA_DIR}/blazegraph:/app-data:rw" \
        -w /app-src maven:3.6.0-jdk-8 \
        sh -c "\
            mvn package -DskipTests=true -DskipITs=true && \
            rm -rf /app/* && \
            unzip -d /app /app-src/dist/target/service-${BLAZE_VERSION}-dist.zip && \
            mv /app/service-${BLAZE_VERSION}/* /app && \
            rmdir /app/service-${BLAZE_VERSION} && \
            \
            # Install envsubst
            apt-get update && \
            apt-get -y install gettext-base && \
            \
            export BLAZEGRAPH_ENDPOINTS='${BLAZEGRAPH_ENDPOINTS}' && \
            export BLAZEGRAPH_JNL_DATA_FILE='${BLAZEGRAPH_JNL_DATA_FILE}' && \
            cd /app && \
            envsubst < RWStore.properties > subst.temp && mv subst.temp RWStore.properties && \
            envsubst < services.json > subst.temp && mv subst.temp mwservices.json"
    { set +x; } 2>/dev/null

    touch "${FLAG_BUILD_BLAZE}"
fi

#
# #####################  Run docker-compose from a docker container
#

# If DEBUG env is not set, run docker compose in the detached (service) mode
DETACH="" && [[ "${DEBUG}" == "" ]] && DETACH=true

# In case there is a local SSD, use it as the temp storage, otherwise use data dir.
OSM_PGSQL_TEMP_DIR=$( [[ "${TEMP_DIR}" == "" ]] && echo "${OSM_PGSQL_DATA_DIR}" || echo "${TEMP_DIR}/osm-pgsql-tmp" )
OSM_RDF_TEMP_DIR=$( [[ "${TEMP_DIR}" == "" ]] && echo "${OSM_RDF_DATA_DIR}" || echo "${TEMP_DIR}/osm-pgsql-tmp" )

# Keep the container around (no --rm) to simplify debugging
echo "########### Starting Docker-compose ###########"
export POSTGRES_PASSWORD
set -x

docker run --rm                                           \
    -e "DATA_DIR=${DATA_DIR}"                             \
    -e "REPO_DIR=${REPO_DIR}"                             \
    -e "STATUS_DIR=${STATUS_DIR}"                         \
    -e "DOWNLOAD_DIR=${DOWNLOAD_DIR}"                     \
    -e "ACME_FILE=${ACME_FILE}"                           \
    -e "SOPHOX_HOST=${SOPHOX_HOST}"                       \
    -e "OSM_FILE=${OSM_FILE}"                             \
    -e "OSM_PGSQL_DATA_DIR=${OSM_PGSQL_DATA_DIR}"         \
    -e "OSM_PGSQL_TEMP_DIR=${OSM_PGSQL_TEMP_DIR}"         \
    -e "OSM_RDF_DATA_DIR=${OSM_RDF_DATA_DIR}"             \
    -e "OSM_RDF_TEMP_DIR=${OSM_RDF_TEMP_DIR}"             \
    -e "MEM_5_PRCNT_MB=$(( ${TOTAL_MEMORY_MB}*5/100 ))"   \
    -e "MEM_15_PRCNT_MB=$(( ${TOTAL_MEMORY_MB}*15/100 ))" \
    -e "MEM_30_PRCNT_MB=$(( ${TOTAL_MEMORY_MB}*30/100 ))" \
    -e BUILD_DIR=/git_repo                                \
    -e POSTGRES_PASSWORD                                  \
                                                          \
    -v "${REPO_DIR}:/git_repo"                            \
    -v /var/run/docker.sock:/var/run/docker.sock          \
                                                          \
    docker/compose:1.23.1                                 \
    --file "/git_repo/${COMPOSE_FILE}"                    \
    up ${DETACH:+ --detach}
