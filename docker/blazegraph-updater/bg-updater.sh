#!/usr/bin/env bash
set -e
echo '########### Updating from OSM Wiki ###########'

if [[ ! -f "${FLAG_WB_INITIALIZED}.disabled" ]]; then
  echo "########### osm wiki importer is disabled"
  exit 0
fi


cd "${BLAZEGRAPH_APP}"

# TODO: INIT_TIME should be set from the value of
#  <http://wiki.openstreetmap.org>  schema:dateModified  ?????

if [[ ! -f "${FLAG_WB_INITIALIZED}" ]]; then
    INIT_TIME="--start 2018-01-01T00:00:00Z"
    touch "${FLAG_WB_INITIALIZED}"
else
    INIT_TIME=""
fi

export UPDATER_OPTS="-DwikibaseMaxDaysBack=720"

set -x
# conceptUri must be http: to match with the OSM
"${BLAZEGRAPH_APP}/runUpdate.sh" \
    -h "${BLAZEGRAPH_HOST}" \
    -- \
    ${INIT_TIME} \
    --wikibaseUrl "https://wiki.openstreetmap.org" \
    --conceptUri "${WB_CONCEPT_URI}" \
    --entityNamespaces 120,122 \
