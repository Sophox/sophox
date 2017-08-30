import requests


class Sparql:
    def __init__(self, rdf_url, dry_run):
        self.rdf_url = rdf_url
        self.dry_run = dry_run

    def query_rdf(self, sparql):
        r = requests.get(self.rdf_url,
                         {'query': sparql},
                         headers={'Accept': 'application/sparql-results+json'})
        try:
            if not r.ok:
                raise Exception(r.text)
            return r.json()['results']['bindings']
        finally:
            r.close()

    def update_rdf(self, sparql):
        if not self.dry_run:
            r = requests.post(self.rdf_url, data={'update': sparql})
            try:
                if not r.ok:
                    raise Exception(r.text)
            finally:
                r.close()
