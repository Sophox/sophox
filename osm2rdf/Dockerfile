FROM python:3
LABEL maintainer='Yuri Astrakhan <YuriAstrakhan@gmail.com>'

COPY ./requirements.txt /

ENV LANG=C.UTF-8

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
            libboost-python-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*
