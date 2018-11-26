# Copyright Yuri Astrakhan <YuriAstrakhan@gmail.com>


import argparse
import logging

import shapely.speedups
from shapely.geometry import MultiPoint
from shapely.wkt import loads

import osmutils
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
        query = '''# Get relations without osmm:loc
SELECT ?rel WHERE {
  ?rel osmm:type 'r' .
  FILTER NOT EXISTS { ?rel osmm:loc ?relLoc . }
}'''   # LIMIT 100000
        result = self.rdf_server.run('query', query)
        self.skipped = ['osmrel:' + i['rel']['value'][len('https://www.openstreetmap.org/relation/'):] for i in result]

        while True:
            relIds = self.skipped
            self.skipped = []
            count = len(relIds)
            self.log.info(f'** Processing {count} relations')
            self.run_list(relIds)
            if len(self.skipped) >= count:
                self.log.info(f'** Unable to process {len(self.skipped)} relations, exiting')
                break
            else:
                self.log.info(f'** Processed {count - len(self.skipped)} out of {count} relations')

        self.log.info('done')


    def run_list(self, relIds):
        for chunk in osmutils.chunks(relIds, 2000):
            self.fixRelations(chunk)

    def fixRelations(self, relIds):
        pairs = self.get_relation_members(relIds)

        insertStatements = []
        for group in self.groupByValues(pairs):
            insertStatements.append(self.processSingleRel(*group))

        if len(insertStatements) > 0:
            sparql = '\n'.join(osmutils.prefixes) + '\n\n'
            sparql += f'INSERT {{ {0} }} WHERE {{}};\n'.format('\n'.join(insertStatements))
            self.rdf_server.run('update', sparql)
            self.log.info(f'Updated {len(insertStatements)} relations')

    def get_relation_members(self, relIds):
        query = f'''# Get relation member's locations
SELECT
  ?rel ?member ?loc
WHERE {{
  VALUES ?rel {{ {' '.join(relIds)} }}
  ?rel osmm:has ?member .
  OPTIONAL {{ ?member osmm:loc ?loc . }}
}}'''
        result = self.rdf_server.run('query', query)

        return [(
            'osmrel:' + i['rel']['value'][len('https://www.openstreetmap.org/relation/'):],
            i['member']['value'],
            i['loc']['value'] if 'loc' in i else ''
        ) for i in result]

    def processSingleRel(self, relId, memberPoints):
        points = MultiPoint([loads(p) for p in memberPoints])
        return relId + ' ' + osmutils.formatPoint('osmm:loc', points.centroid) + '.'


    def groupByValues(self, tupples):
        """Yield a tuple (id, [list of ids])"""
        points = None
        lastId = None
        skip = False
        for id,  ref, value in sorted(tupples):
            if lastId != id:
                if lastId is not None and not skip:
                    if not points:
                        self.skipped.append(lastId)
                    else:
                        yield (lastId, points)
                skip = False
                points = []
                lastId = id
            if not skip:
                if value == '':
                    if ref.startswith('https://www.openstreetmap.org/node/'):
                        if self.nodeCache:
                            nodeId = ref[len('https://www.openstreetmap.org/node/'):]
                            try:
                                point = self.nodeCache.get(int(nodeId))
                                points.append(f'Point({point.lon} {point.lat})')
                            except osmium._osmium.NotFoundError:
                                pass
                    elif ref.startswith('https://www.openstreetmap.org/way/'):
                        pass # not much we can do about missing way's location
                    elif ref.startswith('https://www.openstreetmap.org/relation/'):
                        skip = True
                        self.skipped.append(id)
                    else:
                        raise ValueError('Unknown ref ' + ref)
                else:
                    points.append(value)
        if lastId is not None and not skip:
            if not points:
                self.skipped.append(lastId)
            else:
                yield (lastId, points)

if __name__ == '__main__':
    UpdateRelLoc().run()
    # UpdateRelLoc().fixRelations(['osmrel:13', 'osmrel:3344', 'osmrel:2938' ])
    # UpdateRelLoc().processSingleRel(*('osmrel:13', ['Point(-1.1729935 52.7200423)', 'Point(-1.1755875 52.7180761)']))
