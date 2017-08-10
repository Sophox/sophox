# osm2rdf
A script to import OSM data into an RDF database

# Steps
Follow [Standalone installation steps](https://www.mediawiki.org/wiki/Wikidata_query_service/User_Manual#Standalone_service)
* Dir structure: `service/`, `data/`, `split/` -- on the same level
* Download [latest-all.ttl.gz](https://dumps.wikimedia.org/wikidatawiki/entities/) into `data` 
* Parse the data from the `service` dir:  `./munge.sh -f ../data/latest-all.ttl.gz -d ../split`

* From `service/`, run `./runBlazegraph.sh`
* From `service/`, run ```./loadRestAPI.sh -d `pwd`/../split -h http://localhost:9998``` 
* From `service/`, run `./runUpdate.sh` to catch up to Wikidata's current state

* Download latest planet PBF file [from a mirror!](https://wiki.openstreetmap.org/wiki/Planet.osm)
* Parse it with `osm2rdf planet.pbf outputdir`
* From `service/`, run ```./loadRestAPI.sh -d `pwd`/../outputdir -h http://localhost:9998``` 


# Notes
yuri@tileserv:/mnt/tiles/wikidata/service-0.2.4$ ./runBlazegraph.sh
yuri@tileserv:/mnt/tiles/wikidata/service-0.2.4$ ./runUpdate.sh
yuri@tileserv:/mnt/tiles/openmaptilestileserver-gl-light planet_z0_z14.mbtiles 
yuri@tileserv:/mnt/tiles/osm2rdf$ python3 osm2rdf.py 
yuri@tileserv:/mnt/tiles/wikidata/service-0.2.5-SNAPSHOT$ ./runBlazegraph.sh -p 9998
yuri@tileserv:/mnt/tiles/wikidata/service-0.2.5-SNAPSHOT$ ./runUpdate.sh 
yuri@tileserv:/mnt/tiles/osm2rdf$ python3 osm2rdf.py /mnt/backup/planet-latest.osm.pbf  output                                                                               
