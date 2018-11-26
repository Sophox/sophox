#!/usr/bin/env bash
set -e
echo '########### Running osm2rdf updatePageViewStats ###########'

# Pageview counts are "relative" to one another, so it does not matter how many times
# this script is ran, or if we accidentally get the same data twice.
# We only optimize backfill, so it doesn't happen on every restart

# If true, back-fills the data up to max files. Otherwise runs forward indefinitely
: "${BACKFILL:=}"

if [[ -n "${BACKFILL}" ]] && [[ -f "${FLAG_PV_BACKFILLED}" ]]; then
  echo "########### pageviews have already been backfilled"
  exit 0
fi

set -x
python3 updatePageViewStats.py           \
    --host "${BLAZEGRAPH_URL}"           \
    --maxfiles "${PAGEVIEW_HR_FILES}" \
    ${BACKFILL:+ --go-backwards}
{ set +x; } 2>/dev/null


if [[ -n "${BACKFILL}" ]]; then
    touch "${FLAG_PV_BACKFILLED}"
fi

