import json

from pywikiapi import Site

from .utils import to_json


class DataItemContributors():

    def __init__(self, filename: str, site: Site):
        self.filename = filename
        self.site = site
        self.data = set()

        try:
            with open(self.filename, "r") as file:
                for line in file.readlines():
                    line = line.rstrip()
                    if line:
                        obj = json.loads(line)
                        self.data.add(obj['qid'])
        except FileNotFoundError:
            pass

    def __call__(self, qid, force=True):
        if qid in self.data:
            return True
        if not force:
            return False
        resp = self.site('query', prop='contributors', pclimit='max', titles='Item:' + qid)
        contributors = [v.name for v in resp.query.pages[0].contributors]
        if contributors != ['Yurikbot']:
            self.data.add(qid)
            with open(self.filename, "a") as file:
                print(to_json({'qid': qid}), file=file)
            return True
        else:
            return False
