from collections import defaultdict

from pywikiapi import Site

from .utils import strid_from_item, batches, get_instance_of
from .consts import elements, Q_KEY, Q_LOCALE_INSTANCE
from .Cache import CacheInMemory
from .Properties import P_INSTANCE_OF, P_LANG_CODE

from .Cache import CacheJsonl
from .utils import to_json, get_entities

ignore_qids = {
    'Q2761', # Sandbox
}


class DataItems(CacheJsonl):

    def __init__(self, filename: str, site: Site, use_bot_limits: bool):
        super().__init__(filename)
        self.site = site
        self.use_bot_limits = use_bot_limits

    def generate(self):
        with open(self.filename, "w+") as file:
            # For bots this might need to be smaller because the total download could exceed maximum allowed
            batch_size = 500 if self.use_bot_limits else 50
            for batch in batches(self.items(), batch_size):
                entities = get_entities(self.site, ids=batch)
                if entities:
                    # JSON Lines format
                    print('\n'.join(to_json(item) for item in entities), file=file)

    def items(self):
        for q in self.site.query(list='allpages', apnamespace=120, apfilterredir='nonredirects', aplimit='max'):
            for p in q.allpages:
                qid = p.title[len('Item:'):]
                if qid not in ignore_qids:
                    yield qid


class DataItemCache(CacheInMemory):
    def __init__(self, items):
        super().__init__()
        self.items = items


class DataItemsByQid(DataItemCache):
    def generate(self):
        result = {}
        for item in self.items.get():
            result[item['id']] = item
        return result

    def get_item(self, qid):
        return self.get()[qid]


class DataItemDescByQid(DataItemCache):
    def generate(self):
        result = {}
        ignore_ids = set(elements.values())
        for item in self.items.get():
            if 'en' in item['labels']:
                value = item['labels']['en']['value']
            else:
                value = next(iter(item['labels'].values()), {'value': ''})['value']
            if item['id'] not in ignore_ids:
                value += ' (' + item['id'] + ')'
            result[item['id']] = value
        return result


class DataItemBySitelink(DataItemCache):
    def generate(self):
        result = {}
        for item in self.items.get():
            if 'sitelinks' in item and 'wiki' in item['sitelinks']:
                result[item['sitelinks']['wiki']['title']] = item['id']
        return result


class DataItemsKeysByStrid(DataItemCache):
    def __init__(self, items):
        super().__init__(items)
        self.duplicate_strids = defaultdict(set)

    def generate(self):
        result = {}
        self.duplicate_strids.clear()
        for item in self.items.get():
            strid = strid_from_item(item)
            if strid:
                if strid in result:
                    self.duplicate_strids[strid].add(result[strid])
                    self.duplicate_strids[strid].add(item['id'])
                else:
                    result[strid] = item['id']
        if self.duplicate_strids:
            print('#### DUPLICATE STRIDs')
            for strid, lst in self.duplicate_strids.items():
                print(f'{strid} -- {", ".join(lst)}')
        return result

    def get_strid(self, strid):
        try:
            return self.get()[strid]
        except KeyError:
            return None


class RegionByLangCode(DataItemCache):
    def generate(self):
        result = {}
        for item in self.items.get():
            if get_instance_of(item) == Q_LOCALE_INSTANCE:
                result[P_LANG_CODE.get_claim_value(item)] = item
        return result


class DataItemsByName(DataItemCache):
    def __init__(self, items, instanceof):
        super().__init__(items)
        self.instanceof = instanceof

    def generate(self):
        result = {}
        for item in self.items.get():
            if get_instance_of(item) != self.instanceof:
                continue
            qid = item['id']
            labels = item['labels']
            aliases = item['aliases']
            for k, v in labels.items():
                result[v['value'].lower()] = qid
            for k, v in aliases.items():
                for vv in v:
                    result[vv['value'].lower()] = qid
        return result
