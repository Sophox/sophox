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
import sqlite3


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

        parser.add_argument('--db', action='store', dest='sqlite_db',
                            help='SQLite DB file')
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
        self.save_stats()

    def get_taginfo_stats(self):
        with sqlite3.connect(self.options.sqlite_db) as conn:
            cur = conn.cursor()
            tags = self.get_tags()
            for qid in tags:
                key, value = tags[qid]
                all, nodes, ways, rels = next(
                    iter(cur.execute(
                        'select count_all, count_nodes, count_ways, count_relations '
                        'from tags '
                        'where key = ? and value = ?',
                        (key, value)).fetchall()),
                    (None, None, None, None))
                if all is not None:
                    yield (qid, all, nodes, ways, rels)

    def get_tags(self):
        # sparql = 'SELECT ?id ?tag WHERE { ?id osmdt:P19 ?tag. }'
        # res = self.rdf_server.run('query', sparql)
        # res = [{'id':{'value': v['id']['value']}, 'tag': {'value': v['tag']['value']}} for v in res]
        # with open('all_tags_with_ids_from_sparql.json', 'w+') as fp:
        #     json.dump(res, fp)

        with open('all_tags_with_ids_from_sparql.json', 'r') as fp:
            res = json.load(fp)
        return {
            v['id']['value'][len('http://wiki.openstreetmap.org/entity/'):]: tuple(
                v['tag']['value'].split('=', maxsplit=1))
            for v in res}

    def save_stats(self):
        info_keys = ['tag_count_all', 'tag_count_nodes', 'tag_count_ways', 'tag_count_relations']
        sparql = f'''
            DELETE {{ ?s ?p ?o }} WHERE {{
              VALUES ?p {{ {' '.join([f'osmm:{k}' for k in info_keys])} }}
                     ?s ?p ?o .
            }}'''

        self.rdf_server.run('update', sparql)
        self.log.info(f'Existing counts deleted, importing...')

        done = 0
        last_print = datetime.utcnow()
        for items in chunks(self.get_taginfo_stats(), 1000):
            sparql = (
                    'INSERT {\n' +
                    '\n'.join([f'?id osmm:{k} ?{k}.' for k in info_keys]) +
                    '\n} WHERE {\n' +
                    f"VALUES (?id {' '.join([f'?{k}' for k in info_keys])}) {{\n" +
                    '\n'.join([f"(osmd:{qid} {all} {nodes} {ways} {rels})" for qid, all, nodes, ways, rels in items]) +
                    '\n} }'
            )

            self.rdf_server.run('update', sparql)
            done += len(items)
            if (datetime.utcnow() - last_print).total_seconds() > 60:
                self.log.info(f'Imported {done} tag usage stats, pausing for a few seconds...')
                time.sleep(60)
                last_print = datetime.utcnow()

        self.log.info(f'Finished importing {done} tag usage stats')

    def get_current_ts(self):
        ts_str = requests.get(self.url_stats).json()['data_until']
        return parse_utc(ts_str)


if __name__ == '__main__':
    UpdateUsageStats().run()
