import requests
import logging
import datetime as dt
from datetime import datetime
from RdfHandler import RdfHandler

logger = logging.getLogger('osm2rdf')


class RdfUpdateHandler(RdfHandler):
    def __init__(self, options):
        super(RdfUpdateHandler, self).__init__(options)
        self.deleteIds = []
        self.updatedIds = []
        self.insertStatements = []

    def finalize_object(self, obj, statements, obj_type):
        super(RdfUpdateHandler, self).finalize_object(obj, statements, obj_type)

        prefixed_id = self.types[obj_type] + str(obj.id)
        if obj.deleted:
            self.deleteIds.append(prefixed_id)
        else:
            self.deleteIds.append(prefixed_id)
        if statements:
            self.insertStatements.extend([prefixed_id + ' ' + s + '.' for s in statements])

        if len(self.deleteIds) > 1000 or len(self.updatedIds) > 1000 or len(self.insertStatements) > 2000:
            self.close()

    def close(self):
        if not self.deleteIds and not self.insertStatements:
            return

        sparql = '\n'.join(self.prefixes) + '\n\n'
        sparql += '''
DELETE {{ ?s ?p ?o . }}
WHERE {{
  VALUES ?s {{ {0} }}
  ?s ?p ?o .
}};'''.format(' '.join(self.deleteIds))

        sparql += '''
DELETE {{ ?s ?p ?o . }}
WHERE {{
  VALUES ?s {{ {0} }}
  ?s ?p ?o .
}};'''.format(' '.join(self.updatedIds))

        if self.insertStatements:
            sparql += 'INSERT { ' + '\n'.join(self.insertStatements) + ' } WHERE {};\n'
        r = requests.post(self.options.rdf_url, data={'update': sparql})
        if not r.ok:
            raise Exception(r.text)
        self.deleteIds = []
        self.insertStatements = []

    def get_osm_schema_ver(self, repserv):
        sparql = '''
PREFIX osmroot: <https://www.openstreetmap.org>
SELECT ?dummy ?ver ?mod ?yyy WHERE {
 BIND( "42" as ?dummy )
 OPTIONAL { osmroot: schema:version ?ver . }
 OPTIONAL { osmroot: schema:dateModified ?mod . }
 OPTIONAL { <http://www.wikidata.org> schema:dateModified ?yyy . }
}
'''
        r = requests.get(self.options.rdf_url,
                         {'query': sparql},
                         headers={'Accept': 'application/sparql-results+json'})
        if not r.ok:
            raise Exception(r.text)
        result = r.json()['results']['bindings'][0]
        if result['dummy']['value'] != '42':
            raise Exception('Failed to get a dummy value from RDF DB')

        try:
            return int(result['ver']['value'])
        except KeyError:
            pass

        try:
            mod_date = datetime.strptime(result['mod']['value'], "%Y-%m-%dT%H:%M:%S.%fZ")\
                .replace(tzinfo=dt.timezone.utc)
        except KeyError:
            logger.error('Neither schema:version nor schema:dateModified are set for <https://www.openstreetmap.org>')
            return None

        logger.info('schema:dateModified={0}, shifting back and getting sequence ID'.format(mod_date))

        mod_date -= dt.timedelta(minutes=60)
        return repserv.timestamp_to_sequence(mod_date)

    def set_osm_schema_ver(self, ver):
        if self.last_timestamp.year < 2000: # Something majorly wrong
            raise Exception('last_timestamp was not updated')

        sparql = '''
PREFIX osmroot: <https://www.openstreetmap.org>
DELETE {{ osmroot: schema:version ?v . }} WHERE {{ osmroot: schema:version ?v . }};
DELETE {{ osmroot: schema:dateModified ?m . }} WHERE {{ osmroot: schema:dateModified ?m . }};
INSERT {{
  osmroot: schema:version {0} .
  osmroot: schema:dateModified {1} .
}} WHERE {{}};
'''.format(ver, self.format_date(self.last_timestamp))

        r = requests.post(self.options.rdf_url, data={'update': sparql})
        if not r.ok:
            raise Exception(r.text)
