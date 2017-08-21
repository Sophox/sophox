# osm2rdf
A script to import OSM data into an RDF database

# Steps
Follow [Standalone installation steps](https://www.mediawiki.org/wiki/Wikidata_query_service/User_Manual#Standalone_service)
* Dir structure: `service/`, `data/`, `split/` -- on the same level
* Download [latest-all.ttl.gz](https://dumps.wikimedia.org/wikidatawiki/entities/) into `data`
* Parse the data from the `service` dir:  `./munge.sh -f ../data/latest-all.ttl.gz -d ../split`

* Add this to `service/ldf-config.json` file - "prefixes" section
```
"osmnode": "https://www.openstreetmap.org/node/",
"osmway": "https://www.openstreetmap.org/way/",
"osmrel": "https://www.openstreetmap.org/relation/",
"osmt": "https://wiki.openstreetmap.org/wiki/Key:",
"osmm": "https://www.openstreetmap.org/meta/",
"osmroot": "https://www.openstreetmap.org",
```

* Add this to `service/prefixes.conf` file
```
PREFIX osmnode: <https://www.openstreetmap.org/node/>
PREFIX osmway: <https://www.openstreetmap.org/way/>
PREFIX osmrel: <https://www.openstreetmap.org/relation/>
PREFIX osmt: <https://wiki.openstreetmap.org/wiki/Key:>
PREFIX osmm: <https://www.openstreetmap.org/meta/>
PREFIX osmroot: <https://www.openstreetmap.org>
```

* From `service/`, run `./runBlazegraph.sh`
* From `service/`, run ```./loadRestAPI.sh -d `pwd`/../split -h http://localhost:9998```
* From `service/`, run `./runUpdate.sh` to catch up to Wikidata's current state

* Download latest planet PBF file [from a mirror!](https://wiki.openstreetmap.org/wiki/Planet.osm)
* Parse it with `osm2rdf -c nodes.cache parse planet.pbf outputdir`
* From `service/`, run ```./loadRestAPI.sh -d `pwd`/../outputdir -h http://localhost:9998```


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
    | grep --line-buffered -v 'wikidata.org%3E%20schema:dateModified' \
    | grep --line-buffered 'query=' \
    | gawk -F' ' '{ print $1 " " $4 "\n" gensub(/^\/bigdata\/namespace\/wdq\/sparql\?query=/, "", "g", $7) }' \
    | while read; do echo -e ${REPLY//%/\\x}; done

```
