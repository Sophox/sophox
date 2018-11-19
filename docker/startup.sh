#!/usr/bin/env bash
set -e

#
# To see the logs this script generated during the startup use
#    sudo journalctl -u google-startup-scripts.service
#

# These vars could be customized.  Use "-" for the *_DEV to skip
: "${DATA_DEV:=/dev/sdb}"
: "${DATA_DIR:=/mnt/disks/data}"
: "${TEMP_DEV:=/dev/nvme0n1}"
: "${TEMP_DIR:=/mnt/disks/temp}"

: "${SOPHOX_HOST:=staging.sophox.org}"

: "${REPO_DIR:=${DATA_DIR}/git-repo}"
: "${REPO_URL:=https://github.com/Sophox/sophox.git}"
: "${REPO_BRANCH:=gcp}"

: "${OSM_FILE:=planet-latest.osm.pbf}"
: "${OSM_FILE_URL:=https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf}"
: "${OSM_FILE_MD5_URL:=https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf.md5}"
: "${BACKFILL_DAYS:=14}" # number of days to go back relative to today

# Percentage (integer) of the total memory to be used by Sophox, e.g. 80 for 80% of the total
: "${TOTAL_MEMORY_PRCNT:=100}"

if [[ "${IS_FULL_PLANET}" = "false" ]]; then
  IS_FULL_PLANET=""
else
  IS_FULL_PLANET=true
fi

STATUS_DIR=${DATA_DIR}/status
COMPOSE_FILE=docker/docker-compose.yml
BLAZEGRAPH_APP_DIR=${DATA_DIR}/blazegraph-app
BLAZEGRAPH_DATA_DIR=${DATA_DIR}/blazegraph-data
ACME_FILE=${DATA_DIR}/acme.json
POSTGRES_PASSWORD_FILE=${DATA_DIR}/postgres_password
POSTGRES_DATA_DIR=${DATA_DIR}/postgres
DOWNLOAD_DIR=${DATA_DIR}/download
OSM_PGSQL_DATA_DIR=${DATA_DIR}/osm-pgsql
OSM_RDF_DATA_DIR=${DATA_DIR}/osm-rdf
OSM_TTLS_DIR=${DATA_DIR}/osm-rdf-ttls
WB_CONCEPT_URI="http://wiki.openstreetmap.org"
BLAZEGRAPH_ENDPOINTS='"wiki.openstreetmap.org"'
BLAZEGRAPH_IMAGE=openjdk:8-jdk

# This path must match docker-compose.yml - blazegraph volume
BLAZEGRAPH_JNL_DATA_FILE=/app-data/osmdata.jnl

# If DEBUG env is not set, run docker compose in the detached (service) mode
DETACH_DOCKER_COMPOSE=$( [[ "${DEBUG}" == "" ]] && echo "true" || echo "" )
# Do not use https redirect and Let's Encrypt certs when debugging
TRAEFIK_FILE=$( [[ "${DEBUG}" == "" ]] && echo "${REPO_DIR}/docker/traefik.toml" || echo "${REPO_DIR}/docker/traefik.debug.toml" )
TRAEFIK_HOST=$( [[ "${DEBUG}" == "" ]] && echo "0.0.0.0" || echo "127.0.0.1" )

# Get total system memory, reducing it by some optional percentage, in MB
TOTAL_MEMORY_MB=$(( $(free | awk '/^Mem:/{print $2}') * ${TOTAL_MEMORY_PRCNT} / 100 / 1024 ))

# MEM = 40000 MB ~~ max statements = 10000 / workers count
OSM_RDF_WORKERS=2
OSM_RDF_MAX_STMTS=$(( ${TOTAL_MEMORY_MB} / 4 / ${OSM_RDF_WORKERS} ))

# Blazegraph - full should be maxed at 16g, partial can be maxed at 2g
if [[ -n "${IS_FULL_PLANET}" ]]; then
  MEM_BLAZEGRAPH_MB=$(( 16 * 1024 ))
else
  MEM_BLAZEGRAPH_MB=$(( 2 * 1024 ))
fi
MEM_BLAZEGRAPH_MB=$(( ${TOTAL_MEMORY_MB} / 2 > ${MEM_BLAZEGRAPH_MB} ? ${MEM_BLAZEGRAPH_MB} : ${TOTAL_MEMORY_MB} / 2 ))

#
# #####################  Initialize and Mount Persisted Disk
#

function init_disk {
    local device_id="$1"
    local mount_dir="$2"
    local is_optional="$3"

    if [[ "${device_id}" = "-" ]]; then
      if [[ ! -d "${mount_dir}" ]]; then
        echo "Directory ${mount_dir} does not exist, and device id is not given. Aborting."
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

    echo "########### Setting up ${device_id} as ${mount_dir} ###########"
    if (mount | grep -q "${device_id} on ${mount_dir} type ext4"); then
      echo "${mount_dir} is already mounted"
      return 0
    fi

    echo "Checking if device ${device_id} exists:"
    if ! lsblk --noheadings ${device_id}; then
        if [[ "${is_optional}" = true ]]; then
            echo "Optional disk ${device_id} does not exist, skipping"
            return 9876
        else
            echo "Data disk ${device_id} does not exist"
            exit 1
        fi
    fi

    mkdir -p "${mount_dir}"
    local ret_code=$(mount -o discard,defaults "${device_id}" "${mount_dir}"; echo $?)
    if [[ ${ret_code} -eq 32 ]]; then
      # Format new partition when mount exits with code 32. It usually prints this:
      #   mount: /mnt/disks/data: wrong fs type, bad option, bad superblock on /dev/sdb, missing codepage or helper program, or other error.
      echo "Formatting new partition..."
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


mkdir -p "${STATUS_DIR}"

#
# #####################  Clone/update GIT repo
#

if [[ "${REPO_URL}" = "-" ]]; then
   echo "REPO_URL is not set, skipping git clone/update"
else
  if [[ ! -d "${REPO_DIR}" ]]; then
    echo "########### Cloning git repo ${REPO_URL} #${REPO_BRANCH} to ${REPO_DIR}"
    git clone -b "${REPO_BRANCH}" --recurse-submodules -j4 "${REPO_URL}" "${REPO_DIR}"
  fi
  if [[ ! -d "${REPO_DIR}/.git" ]]; then
    echo "ERROR: ${REPO_DIR} has no .git directory"
    exit 1
  fi

  cd "${REPO_DIR}"
  if git diff-files --quiet; then
      echo "git pull and submodule update from ${REPO_URL} in ${REPO_DIR}"
      git pull
      git submodule update --init --recursive
  else
      echo "git repo ${REPO_DIR} has local changes, update skipped"
      git status
  fi
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

FLAG_DOWNLOADED="${STATUS_DIR}/osm_data.downloaded"
if [[ ! -f "${FLAG_DOWNLOADED}" ]]; then
    echo "########### Downloading ${OSM_FILE} ###########"
    # md5 file should be downloaded before the much slower data file to reduce chances of a race condition
    if [[ "${OSM_FILE_MD5_URL}" != "-" ]]; then
      curl --silent --show-error --location --compressed \
          "${OSM_FILE_MD5_URL}" \
          --output "${DOWNLOAD_DIR}/${OSM_FILE}.md5"
    fi

    set -x
    curl --silent --show-error --location --compressed \
        "${OSM_FILE_URL}" \
        --output "${DOWNLOAD_DIR}/${OSM_FILE}"
    { set +x; } 2>/dev/null

    if [[ "${OSM_FILE_MD5_URL}" != "-" ]]; then
      pushd "${DOWNLOAD_DIR}" > /dev/null
      echo "########### Validating ${OSM_FILE} md5 hash ###########"
      if which md5sum; then
        set -x
        md5sum --check "${DOWNLOAD_DIR}/${OSM_FILE}.md5"
        { set +x; } 2>/dev/null
      else
        echo "WARNING:  You do not have md5sum installed, unable to verify md5 hash"
      fi
      popd > /dev/null
    fi

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
        # Current date minus N days
        local start_date=$(( `date +%s` - ${BACKFILL_DAYS}*24*60*60 ))
        local start_date_fmt=$(date --utc --date="@${start_date}" +"%Y-%m-%dT00:00:00Z")
        set -x
        curl --silent --show-error --location --compressed \
            "https://replicate-sequences.osm.mazdermind.de/?${start_date_fmt}" \
            --output "${data_dir}/state.txt"
        { set +x; } 2>/dev/null
    fi
}

init_state "${OSM_PGSQL_DATA_DIR}"
#init_state "${OSM_RDF_DATA_DIR}"

#
# #####################  Compile Blazegraph
#

function cleanup_git_repo {
    # Cleanup the source code dir
    if [[ "${REPO_URL}" = "-" ]]; then
       echo "REPO_URL is not set, skipping git clean for ${PWD}"
    else
      if git diff-files --quiet; then
        echo "Cleaning ${PWD}"
        git clean -fdx
      else
        echo "GIT repo ${PWD} has local changes, skipping git clean..."
        git status
      fi
    fi
}

cd "${REPO_DIR}/wikidata-query-rdf"
FLAG_BUILD_BLAZE="${STATUS_DIR}/blazegraph.build.$(git rev-parse HEAD || echo 'no_git_dir')"
if [[ ! -f "${FLAG_BUILD_BLAZE}" ]]; then

    # Extract the version number from the line right above the <packaging>pom</packaging>
    BLAZE_VERSION=$(grep --before-context=1 '<packaging>pom</packaging>' "${REPO_DIR}/wikidata-query-rdf/pom.xml" \
        | head --lines=1 \
        | sed 's/^[^>]*>\([^<]*\)<.*$/\1/g')
    echo "########### Building Blazegraph ${BLAZE_VERSION} ###########"
    cleanup_git_repo

    # Compile & package Blazegraph, and extract result to the /blazegraph dir
    set -x
    docker run --rm \
        -v "${REPO_DIR}/wikidata-query-rdf:/app-src:rw" \
        -v "${BLAZEGRAPH_APP_DIR}:/app:rw" \
        -v "${BLAZEGRAPH_DATA_DIR}:/app-data:rw" \
        -w /app-src \
        maven:3.6.0-jdk-8 \
        sh -c "\
            mvn package -DskipTests=true -DskipITs=true && \
            rm -rf /app/* && \
            unzip -d /app /app-src/dist/target/service-${BLAZE_VERSION}-dist.zip && \
            mv /app/service-${BLAZE_VERSION}/* /app && \
            rmdir /app/service-${BLAZE_VERSION} && \
            \
            cd /app && \
            sed 's|%BLAZEGRAPH_JNL_DATA_FILE%|'"${BLAZEGRAPH_JNL_DATA_FILE}"'|g' RWStore.properties > subst.temp && \
            mv subst.temp RWStore.properties && \
            sed 's|%BLAZEGRAPH_ENDPOINTS%|'"${BLAZEGRAPH_ENDPOINTS}"'|g' services.json > subst.temp && \
            mv subst.temp services.json"

        { set +x; } 2>/dev/null

    touch "${FLAG_BUILD_BLAZE}"
fi

#
# #####################  Compile Wikibase GUI
#

cd "${REPO_DIR}/wikidata-query-gui"
FLAG_BUILD_GUI="${STATUS_DIR}/gui.build.$(git rev-parse HEAD || echo 'no_git_dir')"
if [[ ! -f "${FLAG_BUILD_GUI}" ]]; then

    echo "########### Building GUI ###########"
    cleanup_git_repo

    # Compile & package wikibase-query-gui
    set -x
    docker run --rm \
        -v "${REPO_DIR}:/app-src:rw" \
        -v "${BLAZEGRAPH_APP_DIR}:/app:rw" \
        -v "${BLAZEGRAPH_DATA_DIR}:/app-data:rw" \
        -w /app-src \
        node:10.11-alpine \
        sh -c "\
            apk add --no-cache git bash && \
            cd /app-src/wikidata-query-gui && \
            npm install && \
            npm run build"

        { set +x; } 2>/dev/null

    touch "${FLAG_BUILD_GUI}"
fi

#
# #####################  Run docker-compose from a docker container
#

# In case there is a local SSD, use it as the temp storage, otherwise use data dir.
OSM_PGSQL_TEMP_DIR=$( [[ "${TEMP_DIR}" == "" ]] && echo "${OSM_PGSQL_DATA_DIR}" || echo "${TEMP_DIR}/osm-pgsql-tmp" )
OSM_RDF_TEMP_DIR=$( [[ "${TEMP_DIR}" == "" ]] && echo "${OSM_RDF_DATA_DIR}" || echo "${TEMP_DIR}/osm-rdf-tmp" )

echo "########### Starting Docker-compose ###########"
export POSTGRES_PASSWORD

NETWORK_NAME=proxy_net
if [[ -z $(docker network ls --filter "name=^${NETWORK_NAME}$" --format="{{ .Name }}") ]] ; then
     docker network create "${NETWORK_NAME}"
fi

set -x
docker run --rm                                               \
    -e "REPO_DIR=${REPO_DIR}"                                 \
    -e "TRAEFIK_FILE=${TRAEFIK_FILE}"                         \
    -e "TRAEFIK_HOST=${TRAEFIK_HOST}"                         \
    -e "BLAZEGRAPH_IMAGE=${BLAZEGRAPH_IMAGE}"                 \
    -e "BLAZEGRAPH_APP_DIR=${BLAZEGRAPH_APP_DIR}"             \
    -e "BLAZEGRAPH_DATA_DIR=${BLAZEGRAPH_DATA_DIR}"           \
    -e "STATUS_DIR=${STATUS_DIR}"                             \
    -e "DOWNLOAD_DIR=${DOWNLOAD_DIR}"                         \
    -e "ACME_FILE=${ACME_FILE}"                               \
    -e "SOPHOX_HOST=${SOPHOX_HOST}"                           \
    -e "POSTGRES_DATA_DIR=${POSTGRES_DATA_DIR}"               \
    -e "IS_FULL_PLANET=${IS_FULL_PLANET}"                     \
    -e "OSM_FILE=${OSM_FILE}"                                 \
    -e "OSM_PGSQL_DATA_DIR=${OSM_PGSQL_DATA_DIR}"             \
    -e "OSM_PGSQL_TEMP_DIR=${OSM_PGSQL_TEMP_DIR}"             \
    -e "OSM_RDF_DATA_DIR=${OSM_RDF_DATA_DIR}"                 \
    -e "OSM_RDF_TEMP_DIR=${OSM_RDF_TEMP_DIR}"                 \
    -e "OSM_RDF_WORKERS=${OSM_RDF_WORKERS}"                   \
    -e "OSM_RDF_MAX_STMTS=${OSM_RDF_MAX_STMTS}"               \
    -e "OSM_TTLS_DIR=${OSM_TTLS_DIR}"                         \
    -e "WB_CONCEPT_URI=${WB_CONCEPT_URI}"                     \
    -e "MEM_BLAZEGRAPH_MB=${MEM_BLAZEGRAPH_MB}"               \
    -e "MEM_5_PRCNT_MB=$(( ${TOTAL_MEMORY_MB} * 5 / 100 ))"   \
    -e "MEM_15_PRCNT_MB=$(( ${TOTAL_MEMORY_MB} * 15 / 100 ))" \
    -e "MEM_20_PRCNT_MB=$(( ${TOTAL_MEMORY_MB} * 20 / 100 ))" \
    -e "MEM_50_PRCNT_MB=$(( ${TOTAL_MEMORY_MB} * 50 / 100 ))" \
    -e "MEM_65_PRCNT_MB=$(( ${TOTAL_MEMORY_MB} * 65 / 100 ))" \
    -e BUILD_DIR=/git_repo                                    \
    -e POSTGRES_PASSWORD                                      \
                                                              \
    -v "${REPO_DIR}:/git_repo"                                \
    -v /var/run/docker.sock:/var/run/docker.sock              \
                                                              \
    docker/compose:1.23.1                                     \
    --file "/git_repo/${COMPOSE_FILE}"                        \
    --project-name sophox                                     \
    up ${DETACH_DOCKER_COMPOSE:+ --detach}
{ set +x; } 2>/dev/null

echo "########### Docker-compose finished, exiting ###########"
