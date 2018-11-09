# osm2pgsql_osmium docker image

A Docker container that includes osmium and osm2pgsql for OpenStreetMap replication

## Usage

Example of piping osmium to osm2pgsql

```
docker run \
  -it \
  --rm \
  -v $(pwd):/var/lib/osm \
  sophox/osm2pgsql_osmium \
  osmosis \
    --read-replication-interval workingDirectory=/var/lib/osm \
    --simplify-change \
    --write-xml-change - \
  | osm2pgsql \ 
    --append \
    --slim \
    --database gis \ 
    --flat-nodes /var/lib/osm/nodes.cache -C 2000 \
    --number-processes 4 \
    --hstore \
    --style /var/lib/osm/osm.style \
    --tag-transform-script /var/lib/osm/osm.lua -r xml -
```

See [this tutorial](https://ircama.github.io/osm-carto-tutorials/updating-data/) for more info.
