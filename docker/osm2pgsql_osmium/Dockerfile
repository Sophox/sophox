FROM yagajs/osmosis as osmosis
FROM openjdk:alpine

ENV OSM2PGSQL_VERSION=0.96.0

WORKDIR /usr/local/bin

COPY --from=osmosis /opt/osmosis/ /opt/osmosis

RUN ln -s /opt/osmosis/bin/osmosis \
    && \
    apk add --no-cache \
        boost-filesystem \
        boost-system \
        boost-thread \
        expat \
        libbz2 \
        libgcc \
        libstdc++ \
        libpq \
        postgresql-libs \
        lua \
    && \
    apk add --no-cache --repository http://dl-cdn.alpinelinux.org/alpine/edge/testing \
        geos \
        proj4 \
    && \
    apk add --no-cache --repository http://dl-cdn.alpinelinux.org/alpine/edge/testing --virtual .build-deps \
        boost-dev \
        bzip2-dev \
        cmake \
        expat-dev \
        g++ \
        geos-dev \
        git \
        lua-dev \
        make \
        postgresql-dev \
        proj4-dev \
        zlib-dev \
    && git clone --depth 1 --branch $OSM2PGSQL_VERSION https://github.com/openstreetmap/osm2pgsql.git /usr/src/osm2pgsql \
    && mkdir -p /usr/src/osm2pgsql/build \
    && cd /usr/src/osm2pgsql/build \
    && cmake .. \
    && make \
    && make install \
    && apk del .build-deps \
    && rm -rf /usr/src/osm2pgsql

ENTRYPOINT [ "sh" ]
