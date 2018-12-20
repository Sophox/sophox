#!/usr/bin/env python3

# Copyright Yuri Astrakhan <YuriAstrakhan@gmail.com>
import json
import logging
import time
from typing import Dict

import argparse
import requests
from datetime import datetime

from utils import stringify, chunks, query_status, set_status_query, parse_utc
from sparql import Sparql

info_keys = [
    'count_all', 'count_all_fraction', 'count_nodes', 'count_nodes_fraction', 'count_ways', 'count_ways_fraction',
    'count_relations', 'count_relations_fraction', 'values_all', 'users_all'
]


class UpdateUsageStats(object):
    ids: Dict[str, str]

    def __init__(self):

        self.log = logging.getLogger('osm2rdf')
        self.log.setLevel(logging.INFO)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        self.log.addHandler(ch)

        # create the top-level parser
        parser = argparse.ArgumentParser(
            description='Update key and tag usage stats',
            usage='python3 %(prog)s [options]'
        )

        parser.add_argument('--host', action='store', dest='rdf_url',
                            default='http://localhost:9999/bigdata/namespace/wdq/sparql',
                            help='Host URL to upload data. Default: %(default)s')
        parser.add_argument('-n', '--dry-run', action='store_true', dest='dry_run', default=False,
                            help='Do not modify RDF database.')
        opts = parser.parse_args()

        self.options = opts
        self.rdf_server = Sparql(opts.rdf_url, 'query' if opts.dry_run else False)
        self.date_subject = '<https://taginfo.openstreetmap.org>'
        self.url_stats = 'https://taginfo.openstreetmap.org/api/4/key/stats'
        self.url_keys = ' https://taginfo.openstreetmap.org/api/4/keys/all'
        self.ids = {}

    def run(self):

        while True:
            self.run_once()
            time.sleep(1000)

    def run_once(self):
        ts_taginfo = self.get_current_ts()
        ts_db = query_status(self.rdf_server, self.date_subject) if not self.options.dry_run else None

        if ts_taginfo is not None and ts_taginfo == ts_db:
            self.log.info(f'Data is up to date {ts_taginfo}, sleeping...')
            return

        if ts_db is None:
            self.log.info(f'schema:dateModified is not set for {self.date_subject}, performing first import')
        else:
            self.log.info(f'Loading taginfo data, last updated {ts_db}')
        stats, ts = self.get_stats()
        if stats:
            self.log.info(f'Updating {len(stats)} stats')
            self.save_stats(stats, ts)

        self.log.info('Import is done, waiting for new data...')

    def get_stats(self):
        if self.options.dry_run:
            with open('/home/yurik/dev/sophox/all.keys.json', 'r') as f:
                data = json.load(f)
        else:
            data = requests.get(self.url_keys).json()

        ts = parse_utc(data['data_until'])
        stats = {}
        for row in data['data']:
            stats[row['key']] = tuple([row[k] for k in info_keys])

        return stats, ts

    def save_stats(self, stats, timestamp):
        # Resolve keys to IDs
        for keys in chunks([k for k in stats.keys() if k not in self.ids], 5000):
            sparql = f'''
SELECT ?key ?id WHERE {{
  VALUES ?key {{{' '.join([stringify(k) for k in keys])}}}
  ?id osmdt:P16 ?key.
}}'''
            res = self.rdf_server.run('query', sparql)
            # http://wiki.openstreetmap.org/entity/Q103
            self.ids.update(
                {v['key']['value']: v['id']['value'][len('http://wiki.openstreetmap.org/entity/'):] for v in res})

        self.log.info(f'Total resolved keys is {len(self.ids)}, updating...')

        # Delete all usage counters
        sparql = f'''
DELETE {{ ?s ?p ?o }} WHERE {{
  VALUES ?p {{ {' '.join([f'osmm:{k}' for k in info_keys])} }}
         ?s ?p ?o .
}}'''

        self.rdf_server.run('update', sparql)
        self.log.info(f'Existing counts deleted, importing...')

        done = 0
        last_print = datetime.utcnow()
        for keys in chunks(stats.keys(), 5000):
            sparql = (
                    'INSERT {\n' +
                    '\n'.join([f'?id osmm:{k} ?{k}.' for k in info_keys]) +
                    '\n} WHERE {\n' +
                    f"VALUES (?id {' '.join([f'?{k}' for k in info_keys])}) {{\n" +
                    '\n'.join([
                        f"(osmd:{self.ids[k]} {' '.join([str(stats[k][i]) for i in range(len(info_keys))])})"
                        for k in keys if k in self.ids
                    ]) + '\n} }'
            )

            self.rdf_server.run('update', sparql)
            done += len(keys)
            if (datetime.utcnow() - last_print).total_seconds() > 60:
                self.log.info(f'Imported {done} pageview stats, pausing for a few seconds...')
                time.sleep(60)
                last_print = datetime.utcnow()

        self.rdf_server.run('update', set_status_query(self.date_subject, timestamp))
        self.log.info(f'Finished importing {done} pageview stats')

    def get_current_ts(self):
        ts_str = requests.get(self.url_stats).json()['data_until']
        return parse_utc(ts_str)


if __name__ == '__main__':
    UpdateUsageStats().run()
