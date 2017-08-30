# Copyright Yuri Astrakhan <YuriAstrakhan@gmail.com>


import argparse
import logging

import shapely.speedups
from shapely.geometry import MultiPoint
from shapely.wkt import loads

import osmutils
from sparql import Sparql

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
                            default='http://localhost:9999/bigdata/sparql',
                            help='Host URL to upload data. Default: %(default)s')
        parser.add_argument('--ids', action='store', dest='ids_file',
                            default='ids.txt',
                            help='File to store skipped ids. Default: %(default)s')
        parser.add_argument('-n', '--dry-run', action='store_true', dest='dry_run', default=False,
                            help='Do not modify RDF database.')

        opts = parser.parse_args()

        self.options = opts
        self.rdf_server = Sparql(opts.rdf_url, opts.dry_run)
        self.skipped = []

        self.run()
        # self.fixRelations(['osmrel:13', 'osmrel:3344', 'osmrel:2938' ])
        # self.processSingleRel(*('osmrel:13', ['Point(-1.1729935 52.7200423)', 'Point(-1.1755875 52.7180761)']))

        self.log.info('done')


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
            self.log.info('** Processing {0} relations', count)
            self.run_list(relIds)
            if len(self.skipped) >= count:
                self.log.info('** {0} out of {1} relations left, exiting', len(self.skipped), count)
                break
            else:
                self.log.info('** Processed {0} out of {1} relations', count - len(self.skipped), count)


    def run_list(self, relIds):
        for chunk in chunks(relIds, 2000):
            self.fixRelations(chunk)

    def fixRelations(self, relIds):
        pairs = self.get_relation_members(relIds)

        insertStatements = []
        for group in self.groupByValues(pairs):
            insertStatements.append(self.processSingleRel(*group))

        if len(insertStatements) > 0:
            sparql = '\n'.join(osmutils.prefixes) + '\n\n'
            sparql += 'INSERT {{ {0} }} WHERE {{}};\n'.format('\n'.join(insertStatements))
            self.rdf_server.run('update', sparql)
            self.log.info('Updated {0} relations'.format(len(insertStatements)))


    def get_relation_members(self, relIds):

        query = '''# Get relation member's locations
SELECT
  ?rel ?loc
WHERE {{
  VALUES ?rel {{ {0} }}
  ?rel osmm:has ?member .
  OPTIONAL {{ ?member osmm:loc ?loc . }}
}}'''.format(' '.join(relIds))

        result = self.rdf_server.run('query', query)

        return [(
            'osmrel:' + i['rel']['value'][len('https://www.openstreetmap.org/relation/'):],
            i['loc']['value'] if 'loc' in i else ''
        ) for i in result]

    def processSingleRel(self, relId, memberPoints):
        points = MultiPoint([loads(p) for p in memberPoints])
        return relId + ' ' + osmutils.formatPoint('osmm:loc', points.centroid) + '.'


    def groupByValues(self, tupples):
        """Yield a tuple (id, [list of ids])"""
        vals = None
        lastId = None
        skip = False
        for v in sorted(tupples):
            if lastId != v[0]:
                if lastId is not None and not skip:
                    yield (lastId, vals)
                vals = []
                lastId = v[0]
            if not skip:
                if v[1] == '':
                    skip = True
                    self.skipped.append(v[0])
                else:
                    vals.append(v[1])
        if lastId is not None and not skip:
            yield (lastId, vals)

# https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks
def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

if __name__ == '__main__':
    UpdateRelLoc()
