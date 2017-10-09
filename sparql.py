import requests


class Sparql:
    def __init__(self, rdf_url, dry_run):
        self.rdf_url = rdf_url
        self.dry_run = dry_run

    def run(self, queryType, sparql):
        if not self.dry_run:
            r = requests.post(self.rdf_url,
                              data={queryType: sparql},
                              headers={'Accept': 'application/sparql-results+json'})
            try:
                if not r.ok:
                    print(r.reason)
                    print(sparql)
                    raise Exception(r.reason)
                if queryType == 'query':
                    return r.json()['results']['bindings']
            finally:
                r.close()
