FROM debian:buster
LABEL maintainer='Yuri Astrakhan <YuriAstrakhan@gmail.com>'

COPY ./requirements.txt /

ENV LANG=C.UTF-8

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
            python3-pip \
            python3-setuptools \
            build-essential \
            libexpat1-dev \
            libboost-python-dev \
            zlib1g-dev \
            libbz2-dev \
            curl \
            bash \
    && pip3 install --no-cache-dir -r /requirements.txt \
    && rm -rf /var/lib/apt/lists/*

# This script uses curl to initiate RDF data loading
COPY --from=sophox/wikidata-query-rdf:latest /app/loadRestAPI.sh /
