import json
import re
from collections import defaultdict

from pywikiapi import Site, AttrDict

from .utils import to_json

reComment = re.compile(r'^/\* wb(?P<cmd>[a-z]+)(?:-(?P<subcmd>[a-z]+))?:(?:[0-9|]+)?(?:\|(?P<lang>[a-z-]+))? \*/ (?P<text>.*)$')
reProperty = re.compile(r'\[\[Property:(?P<prop>P[0-9]+)\]\]')


class DataItemContributors():

    def __init__(self, filename: str, site: Site):
        self.filename = filename
        self.site = site
        self.data = {}

        try:
            with open(self.filename, "r") as file:
                for line in file.readlines():
                    line = line.rstrip()
                    if line:
                        obj = json.loads(line)
                        self.data[obj['qid']] = obj
        except FileNotFoundError:
            pass

    def __call__(self, qid, force=True):
        if qid in self.data and not force:
            return self.data[qid]
        if not force:
            return {}
        item_qid = 'Item:' + qid

        if qid not in self.data:
            # Ensure we only get a single page result
            (page,) = self.site.query_pages(prop='contributors', pclimit='max', titles=item_qid)
            if [v.name for v in page.contributors] == ['Yurikbot']:
                return {}

        (page,) = self.site.query_pages(prop='revisions', titles=item_qid, rvprop=['user', 'comment'], rvlimit='max')

        data = defaultdict(set)
        for v in page.revisions:
            if v.user == 'Yurikbot':
                continue
            m = reComment.search(v.comment)
            if not m:
                if 'sitelink' not in v.comment and 'undo' not in v.comment and 'restore' not in v.comment and 'Reverted edits' not in v.comment:
                    print(f'Unable to parse wb comment "{v.comment}"')
                continue
            cmd = m.group('cmd')
            lang = m.group('lang')
            subcmd = m.group('subcmd')
            created = 'editentity' == cmd and 'create' == subcmd
            if 'aliases' in cmd or created:
                data['aliases'].add(lang)
            if 'description' in cmd or created:
                data['description'].add(lang)
            if 'label' in cmd or created:
                data['label'].add(lang)
            if 'claim' in cmd:
                m2 = reProperty.search(m.group('text'))
                if m2:
                    data['claims'].add(m2.group('prop'))

        if not data:
            print(f'Unable to find any user contributions for {qid}')
        else:
            data = {'qid': qid, **{k: list(v) for k, v in data.items()}}
            self.data[qid] = data
            # with open(self.filename, "a") as file:
            #     print(to_json({'qid': qid}), file=file)
            with open(self.filename, "w+") as file:
                for v in self.data.values():
                    print(to_json(v), file=file)

        return data
