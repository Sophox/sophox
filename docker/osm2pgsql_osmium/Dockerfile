FROM yagajs/osmosis as osmosis

FROM openjdk:alpine

ENV OSM2PGSQL_VERSION=0.96.0

WORKDIR /usr/local/bin

RUN apk add --no-cache \
    boost-filesystem \
    boost-system \
    boost-thread \
    expat \
    libbz2 \
    libgcc \
    libstdc++ \
    libpq \
    postgresql-libs \
    lua

RUN apk add --no-cache \
    geos \
    proj4 \
    --repository http://dl-cdn.alpinelinux.org/alpine/edge/testing

RUN apk add --no-cache --virtual .build-deps \
    boost-dev \
    bzip2-dev \
    cmake \
    expat-dev \
    g++ \
    geos-dev@testing \
    git \
    lua-dev \
    make \
    postgresql-dev \
    proj4-dev@testing \
    zlib-dev \
    --repository http://dl-cdn.alpinelinux.org/alpine/edge/testing \
    && git clone --depth 1 --branch $OSM2PGSQL_VERSION https://github.com/openstreetmap/osm2pgsql.git /usr/src/osm2pgsql \
    && mkdir -p /usr/src/osm2pgsql/build \
    && cd /usr/src/osm2pgsql/build \
    && cmake .. \
    && make \
    && make install \
    && apk del .build-deps \
    && rm -rf /usr/src/osm2pgsql

COPY --from=osmosis /opt/osmosis/ /opt/osmosis
RUN ln -s /opt/osmosis/bin/osmosis

ENTRYPOINT [ "sh" ]
