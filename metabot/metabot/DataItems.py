import pywikiapi

from .consts import elements, Q_KEY, Q_TAG
from .Cache import CacheInMemory
from .Properties import P_INSTANCE_OF, P_KEY_ID, P_TAG_ID

from .Cache import CacheJsonl
from .utils import to_json, get_entities


class DataItems(CacheJsonl):

    def __init__(self, filename: str, site: pywikiapi.Site, use_bot_limits: bool):
        super().__init__(filename)
        self.site = site
        self.use_bot_limits = use_bot_limits

    def generate(self):
        with open(self.filename, "w+") as file:
            # For bots this might need to be smaller because the total download could exceed maximum allowed
            batch_size = 500 if self.use_bot_limits else 50
            for batch in self.items(batch_size):
                entities = get_entities(self.site, batch)
                if entities:
                    # JSON Lines format
                    print('\n'.join(to_json(item) for item in entities), file=file)

    def items(self, batch_size):
        res = []
        for q in self.site.query(list='allpages', apnamespace=120, apfilterredir='nonredirects', aplimit='max'):
            for p in q.allpages:
                res.append(p.title[len('Item:'):])
                if len(res) >= batch_size:
                    yield res
                    res = []
        if res:
            yield res


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


class DataItemsKeysByStrid(DataItemCache):
    def generate(self):
        result = {}
        for item in self.items.get():
            qid = item['id']
            # if qid != 'Q923': continue  #DEBUG
            instof = P_INSTANCE_OF.get_claim_value(item)
            if instof == Q_KEY:
                result[P_KEY_ID.get_claim_value(item)] = qid
            elif instof == Q_TAG:
                result[P_TAG_ID.get_claim_value(item)] = qid
        return result


class DataItemsByName(DataItemCache):
    def __init__(self, items, instanceof):
        super().__init__(items)
        self.instanceof = instanceof

    def generate(self):
        result = {}
        for item in self.items.get():
            if P_INSTANCE_OF.get_claim_value(item) != self.instanceof:
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
