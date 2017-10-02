#!/bin/bash

# Run this with flock -xn /mnt/tiles/osm2rdf/checkBlazegraph.lck -c /mnt/tiles/osm2rdf/checkBlazegraph.sh

# https://unix.stackexchange.com/a/260594/111317
# close_app_sub GREP_STATEMENT SIGNAL DURATION_SEC
# GREP_STATEMENT must not match itself!
close_app_sub() {
    APP_PID=`/usr/bin/pgrep -o -f 'java -server'`
    if [ ! -z "$APP_PID" ]; then
        echo "App is open. Trying to close app (SIGNAL $1). Max $2sec."
        kill $1 "$APP_PID"
        WAIT_LOOP=0
        while ps -p "$APP_PID" > /dev/null 2>&1; do
            sleep 1
            WAIT_LOOP=$((WAIT_LOOP+1))
            if [ "$WAIT_LOOP" = "$2" ]; then
                break
            fi
        done
    fi
    APP_PID=`/usr/bin/pgrep -o -f 'java -server'`
    if [ -z "$APP_PID" ]; then return 0; else return "$APP_PID"; fi
}

record_stack() {
  /usr/bin/jstack -l $APP_PID>>/mnt/tiles/wikidata/wikidata-query-gui/build2/crashthreads.txt 2>>/mnt/tiles/wikidata/wikidata-query-gui/build2/crashthreads.err.txt
}

close_app() {
    close_app_sub "-SIGINT" "60"
    close_app_sub "-KILL" "60"
    return $?
}

run_test() {
  SPARQL='prefix schema: <http://schema.org/> SELECT * WHERE {<https://www.openstreetmap.org> schema:dateModified ?y}'

  curl --max-time 30 -X POST http://localhost:9999/bigdata/sparql --data-urlencode "query=$SPARQL" -H 'Accept:application/sparql-results+json'

  return $?
}

if (( $# == 1 ))
then
  close_app
  exit 1
fi

( ! run_test >/dev/null 2>&1 ) && sleep 10 && ( ! run_test >/dev/null 2>&1 ) && (record_stack; close_app; exec /mnt/tiles/wikidata/service3/runBlazegraph.sh &)
