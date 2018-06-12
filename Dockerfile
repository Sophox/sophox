FROM debian:buster

COPY ./requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-setuptools \
    build-essential \
    libexpat1-dev \
    libboost-python-dev \
    zlib1g-dev \
    libbz2-dev \
    && pip3 install --no-cache-dir -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*

COPY . .

ENTRYPOINT [ "python3", "./osm2rdf.py" ]

