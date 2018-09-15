# Sophox

## Docker Usage

1.  Install [Docker](https://www.docker.com/community-edition) and [Docker Compose](https://docs.docker.com/compose/install/)
2.  Change the `POSTGRES_USER` and `POSTGRES_PASSWORD` in the `.env` file
3.  In your terminal run `docker-compose up`
4.  Visit http://localhost:8080

## Implementation Progress

- [x] Postgres database service
- [x] Wikidata Query RDF backend service (http://localhost:8080/bigdata)
- [x] Wikidata Query GUI frontend service (http://localhost:8080)
- [x] Nginx proxy for services
- [x] Mapshaper service
- [x] OSM Regions service (http://localhost:8080/regions)
- [ ] SSL certificate generation
- [ ] `/sandbox`
- [ ] `/store`
- [ ] Script to load OSM database
- [ ] Script to load Wikdata

# Scripts
A set of scripts to import OSM data into an RDF database

## Steps
Follow [Standalone installation steps](https://www.mediawiki.org/wiki/Wikidata_query_service/User_Manual#Standalone_service)
* Make sure to get and compile https://github.com/nyurik/wikidata-query-rdf to optimize for OSM data
* Dir structure: `service/`, `data/`, `split/` -- on the same level
* Download [latest-all.ttl.gz](https://dumps.wikimedia.org/wikidatawiki/entities/) into `data`
* Parse the wd data from the `service` dir:  `./munge.sh -f ../data/latest-all.ttl.gz -d ../split`
* Download latest planet PBF file [from a mirror!](https://wiki.openstreetmap.org/wiki/Planet.osm)
* Parse it with `python3 .../osm2rdf.py -c nodes.cache -s dense parse planet-latest.osm.pbf ../split`

* From `service/`, run `./runBlazegraph.sh`
* From `service/`, run ```./loadRestAPI.sh -d `pwd`/../split -h http://localhost:9998```
* From `service/`, run `./runUpdate.sh` to catch up to Wikidata's current state



# Notes
```
yuri@tileserv:/mnt/tiles/wikidata/service-0.2.4$ ./runBlazegraph.sh
yuri@tileserv:/mnt/tiles/wikidata/service-0.2.4$ ./runUpdate.sh
yuri@tileserv:/mnt/tiles/openmaptilestileserver-gl-light planet_z0_z14.mbtiles
yuri@tileserv:/mnt/tiles/osm2rdf$ python3 osm2rdf.py -c nodes.cache update
yuri@tileserv:/mnt/tiles/wikidata/service-0.2.5-SNAPSHOT$ ./runBlazegraph.sh -p 9998
yuri@tileserv:/mnt/tiles/wikidata/service-0.2.5-SNAPSHOT$ ./runUpdate.sh
yuri@tileserv:/mnt/tiles/osm2rdf$ python3 osm2rdf.py /mnt/backup/planet-latest.osm.pbf  output
```

monitor tail:
```
ls /var/log/nginx/access.log* \
    | grep -v .gz$ \
    | xargs tail -n1000 \
    | grep --line-buffered -v '%3E%20schema:dateModified' \
    | grep --line-buffered 'query=' \
    | gawk -F' ' '{ print $1 " " $4 "\n" gensub(/^\/bigdata\/namespace\/wdq\/sparql\?query=/, "", "g", $7) }' \
    | while read; do echo -e ${REPLY//%/\\x}; done

```

get all queries by their count:
```
zgrep 'query=' /var/log/nginx/access.log* | grep -v '%3E%20schema:dateModified' | gawk -F' ' '{ print $1 " " $4 "\n" gensub(/^\/bigdata\/namespace\/wdq\/sparql\?query=/, "", "g", $7) }' | sort | uniq -c | sort -g | while read; do echo -e ${REPLY//%/\\x}; done | less
```

```
zcat -f /var/log/nginx/access.log* | grep 'query=' | grep -v '%3E%20schema:dateModified' | goaccess -a -o /mnt/tiles/wikidata/wikidata-query-gui/build2/logrep.html -
```
