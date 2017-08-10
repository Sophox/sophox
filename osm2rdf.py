# Copyright Yuri Astrakhan <YuriAstrakhan@gmail.com>

import argparse
import datetime as dt
import json
import osmium
import re
import sys
import traceback
from urllib.parse import quote
import os
import gzip
import requests
from osmium import replication
from osmium.replication.server import ReplicationServer
import time
import shapely.speedups
if shapely.speedups.available:
    shapely.speedups.enable()
from shapely.wkb import loads

wkbfab = osmium.geom.WKBFactory()

# May contain letters, numbers anywhere, and -:_ symbols anywhere except first and last position
reSimpleLocalName = re.compile(r'^[0-9a-zA-Z_]([-:0-9a-zA-Z_]*[0-9a-zA-Z_])?$')
reWikidataKey = re.compile(r'(.:)?wikidata$')
reWikidataValue = re.compile(r'^Q[1-9][0-9]*$')
reWikipediaValue = re.compile(r'^([-a-z]+):(.+)$')
reRoleValue = reSimpleLocalName

blazegraphUrl = 'http://localhost:9999/bigdata/sparql'
osmUpdatesUrl = 'http://planet.openstreetmap.org/replication/minute'

types = {
    'n': 'osmnode:',
    'w': 'osmway:',
    'r': 'osmrel:',
}

prefixes = [
    'prefix osmnode: <https://www.openstreetmap.org/node/>',
    'prefix osmway: <https://www.openstreetmap.org/way/>',
    'prefix osmrel: <https://www.openstreetmap.org/relation/>',
    'prefix osmt: <https://wiki.openstreetmap.org/wiki/Key:>',
    'prefix osmm: <https://www.openstreetmap.org/meta/>',
    'prefix wd: <http://www.wikidata.org/entity/>',
    'prefix geo: <http://www.opengis.net/ont/geosparql#>',
    'prefix rootosm: <https://www.openstreetmap.org>',

    # 'prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>',
    # 'prefix xsd: <http://www.w3.org/2001/XMLSchema#>',
    # 'prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>',
    # 'prefix owl: <http://www.w3.org/2002/07/owl#>',
    # 'prefix wikibase: <http://wikiba.se/ontology#>',
    # 'prefix wdata: <https://www.wikidata.org/wiki/Special:EntityData/>',
    # 'prefix wd: <http://www.wikidata.org/entity/>',
    # 'prefix wds: <http://www.wikidata.org/entity/statement/>',
    # 'prefix wdref: <http://www.wikidata.org/reference/>',
    # 'prefix wdv: <http://www.wikidata.org/value/>',
    # 'prefix wdt: <http://www.wikidata.org/prop/direct/>',
    # 'prefix p: <http://www.wikidata.org/prop/>',
    # 'prefix ps: <http://www.wikidata.org/prop/statement/>',
    # 'prefix psv: <http://www.wikidata.org/prop/statement/value/>',
    # 'prefix psn: <http://www.wikidata.org/prop/statement/value-normalized/>',
    # 'prefix pq: <http://www.wikidata.org/prop/qualifier/>',
    # 'prefix pqv: <http://www.wikidata.org/prop/qualifier/value/>',
    # 'prefix pqn: <http://www.wikidata.org/prop/qualifier/value-normalized/>',
    # 'prefix pr: <http://www.wikidata.org/prop/reference/>',
    # 'prefix prv: <http://www.wikidata.org/prop/reference/value/>',
    # 'prefix prn: <http://www.wikidata.org/prop/reference/value-normalized/>',
    # 'prefix wdno: <http://www.wikidata.org/prop/novalue/>',
    # 'prefix skos: <http://www.w3.org/2004/02/skos/core#>',
    # 'prefix schema: <http://schema.org/>',
    # 'prefix cc: <http://creativecommons.org/ns#>',
    # 'prefix geo: <http://www.opengis.net/ont/geosparql#>',
    # 'prefix prov: <http://www.w3.org/ns/prov#>',
]

def addLocation(point, statements):
    spoint = str(point.x) + ' ' + str(point.y)
    if point.has_z:
        spoint += ' ' + str(point.z)
    statements.append('osmm:loc "Point(' + spoint + ')"^^geo:wktLiteral')

def addError(statements, tag, fallbackMessage):
    try:
        e = traceback.format_exc()
        statements.append(tag + ' ' + json.dumps(e, ensure_ascii=False))
    except:
        statements.append(tag + ' ' + fallbackMessage)


class RdfHandler(osmium.SimpleHandler):
    def __init__(self, seqid, path, addWayLoc):
        osmium.SimpleHandler.__init__(self)
        self.seqid = seqid
        self.path = path
        self.length = None
        self.output = None
        self.file_counter = 0
        self.insertStatements = []
        self.deleteIds = []
        self.addWayLoc = addWayLoc

    def finalizeObject(self, obj, statements, type):
        if not obj.deleted and statements:
            statements.append('osmm:type "' + type + '"')
            statements.append('osmm:version "' + str(obj.version) + '"^^<http://www.w3.org/2001/XMLSchema#integer>')

        if self.path:
            if statements:
                self.writeToFile(obj.id, type, statements)
        else:
            self.recordItem(obj.id, type, statements)

    def parseTags(self, obj):
        if not obj.tags or obj.deleted:
            return None

        statements = []

        for tag in obj.tags:
            key = tag.k
            val = None
            if key == 'created_by' or not reSimpleLocalName.match(key):
                continue
            if 'wikidata' in key:
                if reWikidataValue.match(tag.v):
                    val = 'wd:' + tag.v
            elif 'wikipedia' in key:
                match = reWikipediaValue.match(tag.v)
                if match:
                    # For some reason, sitelinks stored in Wikidata WDQS have spaces instead of '_'
                    # https://www.mediawiki.org/wiki/Wikibase/Indexing/RDF_Dump_Format#Sitelinks
                    val = '<https://' + match.group(1) + '.wikipedia.org/wiki/' + \
                          quote(match.group(2).replace(' ', '_'), safe='~') + '>'
            if val is None:
                val = json.dumps(tag.v, ensure_ascii=False)
            statements.append('osmt:' + key + ' ' + val)

        return statements

    def writeToFile(self, id, type, statements):
        if self.length is None or self.length > 512*1024*1024:
            self.create_output_file()
            header = '\n'.join(['@' + p + ' .' for p in prefixes]) + '\n\n'
            self.output.write(header)
            self.length = len(header)

        text = types[type] + str(id) + '\n' + ';\n'.join(statements) + '.\n\n'
        self.output.write(text)
        self.length += len(text)

    def recordItem(self, id, type, statements):
        entityPrefix = types[type]
        self.deleteIds.append(entityPrefix + str(id))
        if statements:
            self.insertStatements.extend([entityPrefix + str(id) + ' ' + s + '.' for s in statements])

        if len(self.deleteIds) > 1300 or len(self.insertStatements) > 2000:
            self.uploadToBlazegraph()

    def uploadToBlazegraph(self):
        if not self.deleteIds and not self.insertStatements:
            return

        sparql = '\n'.join(prefixes) + '\n\n'
        sparql += '''
DELETE {{ ?s ?p ?o . }}
WHERE {{
  VALUES ?s {{ {0} }}
  ?s ?p ?o .
}};'''.format(' '.join(self.deleteIds))

        if self.insertStatements:
            sparql += 'INSERT { ' + '\n'.join(self.insertStatements) + ' } WHERE {};\n'
        r = requests.post(blazegraphUrl, data={'update': sparql})
        if not r.ok:
            raise Exception(r.text)
        self.deleteIds = []
        self.insertStatements = []

    def getOsmSchemaVer(self):
        sparql = '''
prefix rootosm: <https://www.openstreetmap.org>
SELECT ?ver WHERE { rootosm: schema:version ?ver . }
'''
        r = requests.get(blazegraphUrl,
                         {'query': sparql},
                         headers={'Accept': 'application/sparql-results+json'})
        if not r.ok:
            raise Exception(r.text)
        return int(r.json()['results']['bindings'][0]['ver']['value'])

    def setOsmSchemaVer(self, ver):
        sparql = self.get_updatever_sparql(ver)
        r = requests.post(blazegraphUrl, data={'update': sparql})
        if not r.ok:
            raise Exception(r.text)

    def get_updatever_sparql(self, ver):
        sparql = '''
DELETE {{ rootosm: schema:version ?v . }} WHERE {{ rootosm: schema:version ?v . }};
INSERT {{ rootosm: schema:version {0} . }} WHERE {{}};
'''.format(ver)
        return sparql

    def node(self, obj):
        statements = self.parseTags(obj)
        if statements:
            try:
                wkb = wkbfab.create_point(obj)
                point = loads(wkb, hex=True)
                addLocation(point, statements)
            except:
                addError(statements, 'osmm:loc:error', "Unable to parse location data")
        self.finalizeObject(obj, statements, 'n')

    def way(self, obj):
        statements = self.parseTags(obj)
        if statements:
            statements.append('osmm:isClosed "' + ('true' if obj.is_closed() else 'false') + '"^^xsd:boolean')
            if self.addWayLoc:
                try:
                    wkb = wkbfab.create_linestring(obj)
                    point = loads(wkb, hex=True).representative_point()
                    addLocation(point, statements)
                except:
                    addError(statements, 'osmm:loc:error', "Unable to parse location data")
        self.finalizeObject(obj, statements, 'w')

    def relation(self, obj):
        statements = self.parseTags(obj)
        if obj.members:
            statements = statements if statements else []
            for mbr in obj.members:
                # ref role type
                ref = types[mbr.type] + str(mbr.ref)
                role = 'osmm:has'
                if mbr.role != '':
                    if reRoleValue.match(mbr.role):
                        role += ':' + mbr.role
                    else:
                        role += ':_'  # for unknown roles, use "osmm:has:_"
                statements.append(role + ' ' + ref)

        self.finalizeObject(obj, statements, 'r')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        if not self.path:
            self.uploadToBlazegraph()
        else:
            self.close_output()

    def create_output_file(self):
        self.close_output()
        os.makedirs(self.path, exist_ok=True)
        filename = os.path.join(self.path, 'osm-{0:06}.ttl.gz'.format(self.file_counter))

        # TODO switch to 'xt'
        print('{0} Exporting to {1}'.format(dt.datetime.now(), filename))
        self.output = gzip.open(filename, 'wt', compresslevel=5)
        self.file_counter += 1

    def close_output(self):
        if self.output:
            self.output.write('\n' + self.get_updatever_sparql(self.seqid))
            self.output.close()
            self.output = None

def getLastOsmSequence():
    query = '''SELECT ?date ?version WHERE {
  <http://www.openstreetmap.org> schema:dateModified ?date .
  <http://www.openstreetmap.org> schema:version ?ver .
}'''


if __name__ == '__main__':

    # import logging
    # logging.basicConfig(level=logging.INFO,
    #                     format='%(asctime)s %(levelname)s %(message)s')

    # # fun with command line options
    # parser = argparse.ArgumentParser(description=__doc__,
    #                                  formatter_class=argparse.RawDescriptionHelpFormatter,
    #                                  usage='%(prog)s [options] <osm file>')
    # parser.add_argument('-d', action='store', dest='database', default='osmosis',
    #                     help='name of database')
    # parser.add_argument('-r', action='store', dest='replication', default=None,
    #                     help='URL to replication service')
    # parser.add_argument('-S', action='store', dest='change_size', default=50*1024,
    #                     type=int,
    #                     help='Maxium size in kB for changes to download at once')
    # parser.add_argument('-c', action='store_true', dest='createdb', default=False,
    #                     help='Create a new database and set up the tables')
    # parser.add_argument('-i', action='store_true', dest='createindices', default=False,
    #                     help='Create primary keys and their indices')
    # parser.add_argument('-v', action='store_true', dest='verbose', default=False,
    #                     help='Enable verbose output.')
    # parser.add_argument('inputfile', nargs='?', default="-",
    #                     help='OSM input file')
    #
    # options = parser.parse_args()
    #

    paramCount = len(sys.argv)
    if paramCount != 3 and paramCount != 1 and paramCount != 2:
        print('Usage:   python3 ' + __file__ + '                      -- realtime update from OSM')
        print('         python3 ' + __file__ + ' date                 -- realtime update from OSM with a start date')
        print('         python3 ' + __file__ + ' inputfile outputdir  -- convert planet file to turtle files')
        exit(-1)

    repserv = ReplicationServer(osmUpdatesUrl)

    addWayLoc = True
    pbfFile = None
    seqid = None
    outputDir = None
    lastSeqid = None
    lastTime = None
    isUpToDate = False

    if paramCount == 3:
        pbfFile = sys.argv[1]
        outputDir = sys.argv[2]
        print('{0} Getting start date from {1}'.format(dt.datetime.now(), pbfFile))
        start_date = replication.newest_change_from_file(pbfFile)
        if start_date is None:
            raise ValueError("Cannot determine timestamp from the given pbf file")
        print('{0} Start date {1} for file {2}'.format(dt.datetime.now(), start_date, pbfFile))
        start_date -= dt.timedelta(minutes=60)
        seqid = repserv.timestamp_to_sequence(start_date)
        print('{0} Sequence id {1} for file {2}'.format(dt.datetime.now(), seqid, pbfFile))
    else:
        if paramCount == 2:
            start_date = dt.datetime.strptime(sys.argv[1], '%y%m%d').replace(tzinfo=dt.timezone.utc)
            start_date -= dt.timedelta(days=1)
            seqid = repserv.timestamp_to_sequence(start_date)

    while True:
        with RdfHandler(seqid, outputDir, addWayLoc) as ttlFile:
            if pbfFile:
                usePersistedCache = False
                idx = None
                if addWayLoc:
                    # if file is under 10GB, use sparse mode
                    if os.path.getsize(pbfFile) < 10 * 1024 * 1024 * 1024:
                        idx = 'sparse_mem_array'
                    elif not usePersistedCache:
                        idx = 'dense_mmap_array'
                    else:
                        idx = 'dense_file_array,' + pbfFile + '.nodecache'

                ttlFile.apply_file(pbfFile, locations=addWayLoc, idx=idx)
                break
            else:
                if not seqid:
                    seqid = ttlFile.getOsmSchemaVer()
                if not lastTime:
                    lastTime = dt.datetime.now()
                    lastSeqid = seqid
                    print('{0} Initial sequence id: {1}'.format(lastTime, seqid))

                seqid = repserv.apply_diffs(ttlFile, seqid, 50*1024)
                if seqid is None or seqid == lastSeqid:
                    lastTime = dt.datetime.now()
                    print('{0} Sequence {1} is not available, sleeping'.format(lastTime, lastSeqid))
                    if seqid == lastSeqid:
                        isUpToDate = True
                    time.sleep(60)
                else:
                    ttlFile.setOsmSchemaVer(seqid)
                    now = dt.datetime.now()
                    sleep = isUpToDate and (seqid - lastSeqid) == 1
                    print('{0} Processed up to {1}, {2:.2f}/s{3}'.format(
                        now, seqid,
                        (seqid-lastSeqid)/(now-lastTime).total_seconds(),
                        ', waiting 60s' if sleep else ''))
                    if sleep:
                        time.sleep(60)
                lastTime = dt.datetime.now()
                lastSeqid = seqid
