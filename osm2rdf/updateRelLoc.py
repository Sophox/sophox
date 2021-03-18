# Copyright Yuri Astrakhan <YuriAstrakhan@gmail.com>

import time
import argparse
import logging

import shapely.speedups
from shapely.geometry import MultiPoint
from shapely.wkt import loads

import osmutils
from utils import chunks
from sparql import Sparql
import osmium

if shapely.speedups.available:
    shapely.speedups.enable()


class UpdateRelLoc(object):
    def __init__(self):

        self.log = logging.getLogger('osm2rdf')
        self.log.setLevel(logging.INFO)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        self.log.addHandler(ch)

        # create the top-level parser
        parser = argparse.ArgumentParser(
            description='Updates centroids of OSM relations',
            usage='python3 %(prog)s [options]'
        )

        parser.add_argument('--host', action='store', dest='rdf_url',
                            default='http://localhost:9999/bigdata/namespace/wdq/sparql',
                            help='Host URL to upload data. Default: %(default)s')
        parser.add_argument('-s', '--cache-strategy', action='store', dest='cacheType', choices=['sparse', 'dense'],
                            default='dense', help='Which node strategy to use (default: %(default)s)')
        parser.add_argument('-c', '--nodes-file', action='store', dest='cacheFile',
                            default=None, help='File to store node cache.')
        parser.add_argument('-n', '--dry-run', action='store_true', dest='dry_run', default=False,
                            help='Do not modify RDF database.')

        opts = parser.parse_args()

        self.options = opts
        self.rdf_server = Sparql(opts.rdf_url, opts.dry_run)
        self.skipped = []

        if self.options.cacheFile:
            if self.options.cacheType == 'sparse':
                idx = 'sparse_file_array,' + self.options.cacheFile
            else:
                idx = 'dense_file_array,' + self.options.cacheFile
            self.nodeCache = osmium.index.create_map(idx)
        else:
            self.nodeCache = None

    def run(self):
        while True:
            self.run_once()
            time.sleep(600)  # every 10 minutes

    def run_once(self):
        query = '''# Get relations without osmm:loc
SELECT ?rel WHERE {
  ?rel osmm:type 'r' .
  FILTER NOT EXISTS { ?rel osmm:loc ?relLoc . }
}'''  # LIMIT 100000
        result = self.rdf_server.run('query', query)
        self.skipped = ['osmrel:' + i['rel']['value'][len('https://www.openstreetmap.org/relation/'):] for i in result]

        while True:
            rel_ids = self.skipped
            self.skipped = []
            count = len(rel_ids)
            self.log.info(f'** Processing {count} relations')
            self.run_list(rel_ids)
            if len(self.skipped) >= count:
                self.log.info(f'** Unable to process {len(self.skipped)} relations, exiting')
                break
            else:
                self.log.info(f'** Processed {count - len(self.skipped)} out of {count} relations')

        self.log.info('done')

    def run_list(self, rel_ids):
        for chunk in chunks(rel_ids, 2000):
            self.fix_relations(chunk)

    def fix_relations(self, rel_ids):
        pairs = self.get_relation_members(rel_ids)

        insert_statements = []
        for group in self.group_by_values(pairs):
            insert_statements.append(self.process_single_rel(*group))

        if len(insert_statements) > 0:
            sparql = '\n'.join(osmutils.prefixes) + '\n\n'
            sparql += 'INSERT {\n'
            sparql += '\n'.join(insert_statements)
            sparql += '\n} WHERE {};'

            self.rdf_server.run('update', sparql)
            self.log.info(f'Updated {len(insert_statements)} relations')

    def get_relation_members(self, rel_ids):
        query = f'''# Get relation member's locations
SELECT
  ?rel ?member ?loc
WHERE {{
  VALUES ?rel {{ {' '.join(rel_ids)} }}
  ?rel osmm:has ?member .
  OPTIONAL {{ ?member osmm:loc ?loc . }}
}}'''
        result = self.rdf_server.run('query', query)

        return [(
            'osmrel:' + i['rel']['value'][len('https://www.openstreetmap.org/relation/'):],
            i['member']['value'],
            i['loc']['value'] if 'loc' in i else ''
        ) for i in result]

    @staticmethod
    def process_single_rel(rel_id, member_points):
        points = MultiPoint([loads(p) for p in member_points])
        return rel_id + ' ' + osmutils.formatPoint('osmm:loc', points.centroid) + '.'

    def group_by_values(self, tuples):
        """Yield a tuple (rid, [list of ids])"""
        points = None
        last_id = None
        skip = False
        for rid, ref, value in sorted(tuples):
            if last_id != rid:
                if last_id is not None and not skip:
                    if not points:
                        self.skipped.append(last_id)
                    else:
                        yield last_id, points
                skip = False
                points = []
                last_id = rid
            if not skip:
                if value == '':
                    if ref.startswith('https://www.openstreetmap.org/node/'):
                        if self.nodeCache:
                            node_id = ref[len('https://www.openstreetmap.org/node/'):]
                            try:
                                point = self.nodeCache.get(int(node_id))
                                points.append(f'Point({point.lon} {point.lat})')
                            except KeyError:
                                pass
                    elif ref.startswith('https://www.openstreetmap.org/way/'):
                        pass  # not much we can do about missing way's location
                    elif ref.startswith('https://www.openstreetmap.org/relation/'):
                        skip = True
                        self.skipped.append(rid)
                    else:
                        raise ValueError('Unknown ref ' + ref)
                else:
                    points.append(value)
        if last_id is not None and not skip:
            if not points:
                self.skipped.append(last_id)
            else:
                yield last_id, points


if __name__ == '__main__':
    UpdateRelLoc().run()
    # UpdateRelLoc().fix_relations(['osmrel:13', 'osmrel:3344', 'osmrel:2938' ])
    # UpdateRelLoc().process_single_rel('osmrel:13', ['Point(-1.1729935 52.7200423)', 'Point(-1.1755875 52.7180761)'])
