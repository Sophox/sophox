#!/bin/bash

# https://unix.stackexchange.com/a/260594/111317
# close_app_sub GREP_STATEMENT SIGNAL DURATION_SEC
# GREP_STATEMENT must not match itself!
close_app_sub() {
    APP_PID=`/usr/bin/pgrep -o -f 'java -server'`
    if [ ! -z "$APP_PID" ]; then
        echo `date -u -Iseconds` "Killing #$APP_PID with $1. Max $2sec.">>/mnt/tiles/wikidata/wikidata-query-gui/build2/checkBlazegraph.txt
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
}

record_stack() {
  APP_PID=`/usr/bin/pgrep -o -f 'java -server'`
  /usr/bin/jstack -l $APP_PID>>/mnt/tiles/wikidata/wikidata-query-gui/build2/crashthreads.txt 2>>/mnt/tiles/wikidata/wikidata-query-gui/build2/crashthreads.err.txt
  echo `date -u -Iseconds` "$APP_PID Called jstack, returned=$?">>/mnt/tiles/wikidata/wikidata-query-gui/build2/checkBlazegraph.txt
}

close_app() {
    close_app_sub "-SIGINT" "30"
    close_app_sub "-KILL" "30"
    return $?
}

run_one_test() {
  SPARQL='prefix schema: <http://schema.org/> SELECT * WHERE {<https://www.openstreetmap.org> schema:dateModified ?y}'
  curl --max-time $1 -X POST http://localhost:9999/bigdata/sparql --data-urlencode "query=$SPARQL" -H 'Accept:application/sparql-results+json'
  return $?
}

run_test() {

  run_one_test 3
  if (( $? == 0 )); then
    echo `date -u -Iseconds` `/usr/bin/pgrep -o -f 'java -server'` 'ok'>>/mnt/tiles/wikidata/wikidata-query-gui/build2/checkBlazegraph.txt
    return 0
  fi
  echo `date -u -Iseconds` `/usr/bin/pgrep -o -f 'java -server'` 'slowdown'>>/mnt/tiles/wikidata/wikidata-query-gui/build2/checkBlazegraph.txt
  sleep 10

  run_one_test 15
  if (( $? == 0 )); then return 0; fi
  echo `date -u -Iseconds` `/usr/bin/pgrep -o -f 'java -server'` 'major slowdown'>>/mnt/tiles/wikidata/wikidata-query-gui/build2/checkBlazegraph.txt
  record_stack
  sleep 10

  run_one_test 15
  if (( $? == 0 )); then return 0; fi

  echo `date -u -Iseconds` `/usr/bin/pgrep -o -f 'java -server'` 'test failed, restarting'>>/mnt/tiles/wikidata/wikidata-query-gui/build2/checkBlazegraph.txt
  return 1
}

restart_blazegraph() {
  record_stack
  close_app

  echo `date -u -Iseconds` 'running blazegraph'>>/mnt/tiles/wikidata/wikidata-query-gui/build2/checkBlazegraph.txt
  setsid /mnt/tiles/wikidata/service3/runBlazegraph.sh >/dev/null 2>&1 < /dev/null &
  sleep 15
  echo `date -u -Iseconds` `/usr/bin/pgrep -o -f 'java -server'` ' started'>>/mnt/tiles/wikidata/wikidata-query-gui/build2/checkBlazegraph.txt
  exit 1
}

if (( $# == 1 ))
then
  close_app
  exit 1
fi

( ! run_test >/dev/null 2>&1 ) && restart_blazegraph
