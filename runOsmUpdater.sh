#!/bin/bash

HOST="http://localhost:9999/bigdata/sparql"
UPDATEURL="https://planet.openstreetmap.org/replication/minute"
MAXDOWNLOAD=5120

while getopts c:s:i:u:h:m:n:t option
do
    case "${option}"
    in
      c) NODESFILE=${OPTARG};;
      s) CACHESTRATEGY=${OPTARG};;
      i) SEQID=${OPTARG};;
      u) UPDATEURL=${OPTARG};;
      h) HOST=${OPTARG};;
      m) MAXDOWNLOAD=${OPTARG};;
      n) DRYRUN=${OPTARG};;
    esac 
done

if [ -z "$SEQID" ]; then
    SEQID_ARG=
else
    SEQID_ARG="--seqid $SEQID"
fi

if [ -z "$DRYRUN" ]; then
    DRYRUN_ARG=
else    
    DRYRUN_ARG="--dry-run"
fi

until python3 osm2rdf.py -c $NODESFILE -s $CACHESTRATEGY update \
            --host $HOST --max-download $MAXDOWNLOAD \
            --update-url $UPDATEURL \
            $SEQID_ARG $DRYRUN_ARG; do
    echo "It crashed with exit code $?.  Respawning in 5 seconds" >&2
    sleep 5
done
