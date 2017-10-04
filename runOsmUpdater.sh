#!/bin/bash

until python3 osm2rdf.py -c /mnt/tiles/wikidata/data2/nodes.cache -s dense update; do
    echo "It crashed with exit code $?.  Respawning in 5 seconds" >&2
    sleep 5
done
