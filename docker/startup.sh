#!/usr/bin/env bash
set -e

#
# To see the logs this script generated during the startup use
#    sudo journalctl -u google-startup-scripts.service
#

################ Input variables. Only DATA_DIR is required

if [[ -z "${DATA_DIR}" ]]; then
  echo "Must set DATA_DIR before running this script"
  exit 1
fi

# DEBUG (true/false) . Set to any non-empty string except "false" to run in debug mode:
#  - disable https
#  - do not detach from docker-compose until ctrl+C (stop all)
#  - print all logs
if [[ "${DEBUG}" = "false" ]]; then
  DEBUG=""
fi

# Optional location of the temporary files.
: "${TEMP_DIR:=}"

# Domain of this service
: "${SOPHOX_HOST:=sophox.org}"

# Sophox GIT repository clone - directory, git url, git branch
# Set REPO_URL to "-" to prevent automatic git clone
: "${REPO_DIR:=${DATA_DIR}/git-repo}"
: "${REPO_URL:=https://github.com/Sophox/sophox.git}"
: "${REPO_BRANCH:=master}"

# Which OSM dump file to download, what to save it as, and the optional URL of the md5 hash (use '-' to skip)
: "${OSM_FILE:=new-jersey-latest.osm.pbf}"
: "${OSM_FILE_URL:=http://download.geofabrik.de/north-america/us/${OSM_FILE}}"
: "${OSM_FILE_MD5_URL:=${OSM_FILE_URL}.md5}"

# IS_FULL_PLANET (true/false) optimizes node storage. Set to "false" or empty for smaller imports.
# Defaults to "false"
if [[ "${IS_FULL_PLANET}" = "false" ]]; then
  IS_FULL_PLANET=""
fi

# number of days to go back from today to backfill after the dump file
: "${BACKFILL_DAYS:=7}"

# Optionally override maximum memory (e.g. this is needed when testing on a Mac without `free` util)
: "${MAX_MEMORY_MB:=}"

# Percentage (integer) of the total memory to be used by Sophox, e.g. 80 for 80% of the total RAM
# This param is not used if MAX_MEMORY_MB is set.
: "${TOTAL_MEMORY_PRCNT:=30}"

# Number of hours (1hr per file) to download at once from the Wikipedia pageviews statistics service
# This number also affects how far back from "now" it will backfill
#
: "${PAGEVIEW_HR_FILES:=48}"

# To disable any of these, set it to an empty value
: "${ENABLE_IMPORT_OSM2PGSQL=true}"
: "${ENABLE_IMPORT_OSM2RDF=true}"
: "${ENABLE_IMPORT_PAGEVIEWS=true}"

: "${ENABLE_UPDATE_METADATA=true}"
: "${ENABLE_UPDATE_OSM2PGSQL=true}"
: "${ENABLE_UPDATE_OSM2RDF=true}"
: "${ENABLE_UPDATE_PAGEVIEWS=true}"

# If DEBUG env is not set, run docker compose in the detached (service) mode
DETACH_DOCKER_COMPOSE=$( [[ "${DEBUG}" == "" ]] && echo "true" || echo "" )


##############  NO USER-SERVICABLE VARIABLES BEYOND THIS POINT :)

# Print parameters:
echo "DATA_DIR='${DATA_DIR}'"
echo "TEMP_DIR='${TEMP_DIR}'"
echo "SOPHOX_HOST='${SOPHOX_HOST}'"
echo "REPO_DIR='${REPO_DIR}'"
echo "REPO_URL='${REPO_URL}'"
echo "REPO_BRANCH='${REPO_BRANCH}'"
echo "OSM_FILE='${OSM_FILE}'"
echo "OSM_FILE_URL='${OSM_FILE_URL}'"
echo "OSM_FILE_MD5_URL='${OSM_FILE_MD5_URL}'"
echo "BACKFILL_DAYS='${BACKFILL_DAYS}'"
echo "TOTAL_MEMORY_PRCNT='${TOTAL_MEMORY_PRCNT}'"
echo "IS_FULL_PLANET='${IS_FULL_PLANET}'"
echo "DEBUG='${DEBUG}'"

##############  Setup internal vars

STATUS_DIR=${DATA_DIR}/status
ACME_FILE=${DATA_DIR}/acme.json
POSTGRES_PASSWORD_FILE=${DATA_DIR}/postgres_password
POSTGRES_DATA_DIR=${DATA_DIR}/postgres
# Ideally download should go to the temp, but it might not fit together with Blazegraph in 375GB
# DOWNLOAD_DIR=${TEMP_DIR:-$DATA_DIR}/download
DOWNLOAD_DIR=${DATA_DIR}/download
OSM_PGSQL_DATA_DIR=${DATA_DIR}/osm-pgsql
OSM_RDF_DATA_DIR=${DATA_DIR}/osm-rdf
OSM_TTLS_DIR=${DATA_DIR}/osm-rdf-ttls
BLAZEGRAPH_URL=http://blazegraph:9999/bigdata/namespace/wdq/sparql

WB_CONCEPT_URI="http://wiki.openstreetmap.org"
BLAZEGRAPH_IMAGE=openjdk:8-jdk

# If DEBUG env is not set, run docker compose in the detached (service) mode
DETACH_DOCKER_COMPOSE=$( [[ "${DEBUG}" == "" ]] && echo "true" || echo "" )
# Do not use https redirect and Let's Encrypt certs when debugging
TRAEFIK_FILE=$( [[ "${DEBUG}" == "" ]] && echo "${REPO_DIR}/docker/traefik.toml" || echo "${REPO_DIR}/docker/traefik.debug.toml" )
TRAEFIK_HOST=$( [[ "${DEBUG}" == "" ]] && echo "0.0.0.0" || echo "127.0.0.1" )

# Get total system memory, reducing it by some optional percentage, in MB
if [[ -z "${MAX_MEMORY_MB}" ]]; then
  # TODO: support Mac
  TOTAL_MEMORY_KB=$(free | awk '/^Mem:/{print $2}')
  MAX_MEMORY_MB=$(( ${TOTAL_MEMORY_KB} * ${TOTAL_MEMORY_PRCNT} / 100 / 1024 ))
fi
echo "MAX_MEMORY_MB='${MAX_MEMORY_MB}'"

# WORKERS = 1..4, per each ~30GB of the total
OSM_RDF_WORKERS=$(( ${MAX_MEMORY_MB} / 30000 ))
OSM_RDF_WORKERS=$(( ${OSM_RDF_WORKERS} < 1 ? 1 : ( ${OSM_RDF_WORKERS} > 4 ? 4 : ${OSM_RDF_WORKERS} ) ))
# MEM = 40000 MB ~~ max statements = 10000 / workers count
OSM_RDF_MAX_STMTS=$(( ${MAX_MEMORY_MB} / 4 / ${OSM_RDF_WORKERS} ))


# Blazegraph - full should be maxed at 16g, partial can be maxed at 2g
if [[ -n "${IS_FULL_PLANET}" ]]; then
  echo "### Optimizing for full planet import"
  MEM_BLAZEGRAPH_MB=$(( 12 * 1024 ))
else
  echo "### Optimizing for a small OSM file import"
  MEM_BLAZEGRAPH_MB=$(( 1024 ))
fi
MEM_BLAZEGRAPH_MB=$(( ${MAX_MEMORY_MB} / 2 > ${MEM_BLAZEGRAPH_MB} ? ${MEM_BLAZEGRAPH_MB} : ${MAX_MEMORY_MB} / 2 ))

# In case there is a local SSD, use it as the temp storage, otherwise use data dir.
OSM_PGSQL_TEMP_DIR=$( [[ "${TEMP_DIR}" == "" ]] && echo "${OSM_PGSQL_DATA_DIR}" || echo "${TEMP_DIR}/osm-pgsql-tmp" )
OSM_RDF_TEMP_DIR=$( [[ "${TEMP_DIR}" == "" ]] && echo "${OSM_RDF_DATA_DIR}" || echo "${TEMP_DIR}/osm-rdf-tmp" )

# TODO: For now, try to use Local SSD for RDF data
BLAZEGRAPH_DATA_DIR="${TEMP_DIR:-$DATA_DIR}/blazegraph-data"

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
      set -x
      git pull
      git submodule update --init --recursive
      { set +x; } 2>/dev/null
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
    echo "########### Creating ${ACME_FILE}"
    touch "${ACME_FILE}"
    chmod 600 "${ACME_FILE}"
fi

# Generate a random Postgres password
if [[ ! -f "${POSTGRES_PASSWORD_FILE}" ]]; then
    echo "########### Creating ${POSTGRES_PASSWORD_FILE}"
    openssl rand -base64 15 | head -c 12 > "${POSTGRES_PASSWORD_FILE}"
    chmod 400 "${POSTGRES_PASSWORD_FILE}"
fi
export POSTGRES_PASSWORD=$(<"${POSTGRES_PASSWORD_FILE}")


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
    echo "########### Downloading ${OSM_FILE}"
    # md5 file should be downloaded before the much slower data file to reduce chances of a race condition
    if [[ "${OSM_FILE_MD5_URL}" != "-" ]]; then
      curl --fail --silent --show-error --location --compressed \
          "${OSM_FILE_MD5_URL}" \
          --output "${DOWNLOAD_DIR}/${OSM_FILE}.md5"
    fi

    set -x
    curl --fail --silent --show-error --location --compressed \
        "${OSM_FILE_URL}" \
        --output "${DOWNLOAD_DIR}/${OSM_FILE}"
    { set +x; } 2>/dev/null

    if [[ "${OSM_FILE_MD5_URL}" != "-" ]]; then
      pushd "${DOWNLOAD_DIR}" > /dev/null
      echo "########### Validating ${OSM_FILE} md5 hash"
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

# Create a state file with the sync start time. The state file is generated for N weeks prior to now
# in order not to miss any data changes. Since the planet dump is weekly and we generate this
# file when we download the planet-latest.osm.pbf file, we should not miss any changes.
mkdir -p "${OSM_PGSQL_DATA_DIR}"
if [[ ! -f "${OSM_PGSQL_DATA_DIR}/state.txt" ]]; then

    echo "########### Initializing ${OSM_PGSQL_DATA_DIR} state files ###########"
    cp "${REPO_DIR}/docker/osmosis_configuration.txt" "${OSM_PGSQL_DATA_DIR}/configuration.txt"
    touch "${OSM_PGSQL_DATA_DIR}/download.lock"
    # Current date minus N days
    start_date=$(( `date +%s` - ${BACKFILL_DAYS}*24*60*60 ))
    if [[ "$(uname -s)" = "Darwin" ]]; then
      start_date_fmt=$(date -u -r "${start_date}" +"%Y-%m-%dT00:00:00Z")
    else
      start_date_fmt=$(date --utc --date="@${start_date}" +"%Y-%m-%dT00:00:00Z")
    fi
    set -x
    curl --fail --silent --show-error --location --compressed \
        "https://replicate-sequences.osm.mazdermind.de/?${start_date_fmt}" \
        --output "${OSM_PGSQL_DATA_DIR}/state.txt"
    { set +x; } 2>/dev/null
fi

#
# #####################  Utility functions
#

function wait_for {
    local name=$1
    local command=$2
    local id

    printf "Waiting for ${name} to start "
    id=$(docker ps "--filter=label=com.docker.compose.service=${name}" --quiet)
    if [[ -z $id ]]; then
        echo "Unable to find docker service '${name}'"
        exit 1
    fi
    while ! docker exec ${id} ${command} > /dev/null ; do
        sleep 2
        printf "."
    done
    echo
}

#
# #####################  Run docker-compose from a docker container
#

echo "########### Starting Services"

NETWORK_NAME=proxy_net
if [[ -z $(docker network ls --filter "name=^${NETWORK_NAME}$" --format="{{ .Name }}") ]] ; then
     docker network create "${NETWORK_NAME}"
fi

set -x
docker run --rm                                                      \
    -e "BLAZEGRAPH_DATA_DIR=${BLAZEGRAPH_DATA_DIR}"                  \
    -e "BLAZEGRAPH_IMAGE=${BLAZEGRAPH_IMAGE}"                        \
    -e "MEM_BLAZE_HEAP_MB=${MEM_BLAZEGRAPH_MB}"                      \
    -e "MEM_BLAZE_LIMIT_MB=$(( ${MAX_MEMORY_MB} * 70 / 100 ))"       \
    -e "MEM_PG_MAINTENANCE_MB=$(( ${MAX_MEMORY_MB} * 20 / 100 ))"    \
    -e "MEM_PG_SHARED_BUFFERS_MB=$(( ${MAX_MEMORY_MB} * 15 / 100 ))" \
    -e "MEM_PG_WORK_MB=$(( ${MAX_MEMORY_MB} * 5 / 100 ))"            \
    -e "OSM_TTLS_DIR=${OSM_TTLS_DIR}"                                \
    -e "POSTGRES_DATA_DIR=${POSTGRES_DATA_DIR}"                      \
    -e "SOPHOX_HOST=${SOPHOX_HOST}"                                  \
    -e "WB_CONCEPT_URI=${WB_CONCEPT_URI}"                            \
    -e POSTGRES_PASSWORD                                             \
                                                                     \
    -v "${REPO_DIR}:/git_repo"                                       \
    -v /var/run/docker.sock:/var/run/docker.sock                     \
                                                                     \
    docker/compose:1.23.1                                            \
    --file /git_repo/docker/dc-databases.yml                          \
    --project-name sophox                                            \
    up --detach
{ set +x; } 2>/dev/null


wait_for "blazegraph" "curl --fail --silent http://127.0.0.1:9999/bigdata/status"
wait_for "postgres" "pg_isready --dbname=gis --quiet"
sleep 5 # just in case :)

echo "########### Starting Importers"

if [[ -n ${ENABLE_IMPORT_OSM2PGSQL} || -n ${ENABLE_IMPORT_OSM2RDF} || -n ${ENABLE_IMPORT_PAGEVIEWS} ]]; then
    set -x
    docker run --rm                                                     \
        -e "BLAZEGRAPH_URL=${BLAZEGRAPH_URL}"                           \
        -e "BUILD_DIR=/git_repo"                                        \
        -e "DOWNLOAD_DIR=${DOWNLOAD_DIR}"                               \
        -e "IS_FULL_PLANET=${IS_FULL_PLANET}"                           \
        -e "MEM_OSM_PGSQL_IMPORT_MB=$(( ${MAX_MEMORY_MB} * 20 / 100 ))" \
        -e "MEM_OSM_RDF_LIMIT_MB=$(( ${MAX_MEMORY_MB} * 70 / 100 ))"    \
        -e "OSM_FILE=${OSM_FILE}"                                       \
        -e "OSM_PGSQL_DATA_DIR=${OSM_PGSQL_DATA_DIR}"                   \
        -e "OSM_PGSQL_TEMP_DIR=${OSM_PGSQL_TEMP_DIR}"                   \
        -e "OSM_RDF_DATA_DIR=${OSM_RDF_DATA_DIR}"                       \
        -e "OSM_RDF_MAX_STMTS=${OSM_RDF_MAX_STMTS}"                     \
        -e "OSM_RDF_TEMP_DIR=${OSM_RDF_TEMP_DIR}"                       \
        -e "OSM_RDF_WORKERS=${OSM_RDF_WORKERS}"                         \
        -e "OSM_TTLS_DIR=${OSM_TTLS_DIR}"                               \
        -e "PAGEVIEW_HR_FILES=${PAGEVIEW_HR_FILES}"                     \
        -e "REPO_DIR=${REPO_DIR}"                                       \
        -e "STATUS_DIR=${STATUS_DIR}"                                   \
        -e POSTGRES_PASSWORD                                            \
                                                                        \
        -v "${REPO_DIR}:/git_repo"                                      \
        -v /var/run/docker.sock:/var/run/docker.sock                    \
                                                                        \
        docker/compose:1.23.1                                           \
        ${ENABLE_IMPORT_OSM2PGSQL:+ --file /git_repo/docker/dc-importers-osm2pgsql.yml}  \
        ${ENABLE_IMPORT_OSM2RDF:+ --file /git_repo/docker/dc-importers-osm2rdf.yml}      \
        ${ENABLE_IMPORT_PAGEVIEWS:+ --file /git_repo/docker/dc-importers-pageviews.yml}  \
        --project-name sophox                                           \
        up
    { set +x; } 2>/dev/null
else
    echo "All import services have been disabled, skipping"
fi

# Once all status flag files are created, delete downloaded OSM file
if [[ -f "${DOWNLOAD_DIR}/${OSM_FILE}" ]]; then
  if ls "${STATUS_DIR}/osm-rdf.parsed" "${STATUS_DIR}/osm-pgsql.imported" > /dev/null ; then
    echo "Deleting ${DOWNLOAD_DIR}/${OSM_FILE}"
    rm "${DOWNLOAD_DIR}/${OSM_FILE}"
  fi
fi

echo "########### Starting Updaters"

set -x
docker run --rm                                                    \
    -e "ACME_FILE=${ACME_FILE}"                                    \
    -e "BLAZEGRAPH_IMAGE=${BLAZEGRAPH_IMAGE}"                      \
    -e "BLAZEGRAPH_URL=${BLAZEGRAPH_URL}"                          \
    -e "BUILD_DIR=/git_repo"                                       \
    -e "IS_FULL_PLANET=${IS_FULL_PLANET}"                          \
    -e "MEM_OSM_PGSQL_UPDATE_MB=$(( ${MAX_MEMORY_MB} * 5 / 100 ))" \
    -e "OSM_PGSQL_DATA_DIR=${OSM_PGSQL_DATA_DIR}"                  \
    -e "OSM_RDF_DATA_DIR=${OSM_RDF_DATA_DIR}"                      \
    -e "REPO_DIR=${REPO_DIR}"                                      \
    -e "SOPHOX_HOST=${SOPHOX_HOST}"                                \
    -e "STATUS_DIR=${STATUS_DIR}"                                  \
    -e "TRAEFIK_FILE=${TRAEFIK_FILE}"                              \
    -e "TRAEFIK_HOST=${TRAEFIK_HOST}"                              \
    -e "WB_CONCEPT_URI=${WB_CONCEPT_URI}"                          \
    -e POSTGRES_PASSWORD                                           \
                                                                   \
    -v "${REPO_DIR}:/git_repo"                                     \
    -v /var/run/docker.sock:/var/run/docker.sock                   \
                                                                   \
    docker/compose:1.23.1                                          \
    --file /git_repo/docker/dc-services.yml                        \
    ${ENABLE_UPDATE_METADATA:+ --file /git_repo/docker/dc-updaters-metadata.yml}   \
    ${ENABLE_UPDATE_OSM2PGSQL:+ --file /git_repo/docker/dc-updaters-osm2pgsql.yml} \
    ${ENABLE_UPDATE_OSM2RDF:+ --file /git_repo/docker/dc-updaters-osm2rdf.yml}     \
    ${ENABLE_UPDATE_PAGEVIEWS:+ --file /git_repo/docker/dc-updaters-pageviews.yml} \
    --project-name sophox                                          \
    up                                                             \
    ${DETACH_DOCKER_COMPOSE:+ --detach}
{ set +x; } 2>/dev/null

echo "########### Startup is done, exiting"
