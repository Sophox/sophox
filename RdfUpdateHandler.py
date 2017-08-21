import requests
from RdfHandler import RdfHandler


class RdfUpdateHandler(RdfHandler):
    def __init__(self, options):
        super(RdfUpdateHandler, self).__init__(options)
        self.deleteIds = []
        self.insertStatements = []


    def finalizeObject(self, obj, statements, type):
        super(RdfUpdateHandler, self).finalizeObject(obj, statements, type)

        entityPrefix = self.types[type]
        self.deleteIds.append(entityPrefix + str(id))
        if statements:
            self.insertStatements.extend([entityPrefix + str(id) + ' ' + s + '.' for s in statements])

        if len(self.deleteIds) > 1300 or len(self.insertStatements) > 2000:
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

        if self.insertStatements:
            sparql += 'INSERT { ' + '\n'.join(self.insertStatements) + ' } WHERE {};\n'
        r = requests.post(self.options.blazegraphUrl, data={'update': sparql})
        if not r.ok:
            raise Exception(r.text)
        self.deleteIds = []
        self.insertStatements = []


    def getOsmSchemaVer(self):
        sparql = '''
prefix osmroot: <https://www.openstreetmap.org>
SELECT ?ver WHERE { osmroot: schema:version ?ver . }
'''
        r = requests.get(self.options.blazegraphUrl,
                         {'query': sparql},
                         headers={'Accept': 'application/sparql-results+json'})
        if not r.ok:
            raise Exception(r.text)
        return int(r.json()['results']['bindings'][0]['ver']['value'])


    def setOsmSchemaVer(self, ver):
        sparql = '''
prefix osmroot: <https://www.openstreetmap.org>
DELETE {{ osmroot: schema:version ?v . }} WHERE {{ osmroot: schema:version ?v . }};
INSERT {{ osmroot: schema:version {0} . }} WHERE {{}};
'''.format(ver)
        r = requests.post(self.options.blazegraphUrl, data={'update': sparql})
        if not r.ok:
            raise Exception(r.text)
