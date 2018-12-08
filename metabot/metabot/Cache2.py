from .DescriptionParser import DescriptionParser
from .utils import to_json
from .consts import elements, Q_KEY, Q_TAG
from .Property import Property as Prop
from .Cache import CacheJsonl, CacheInMemory
from .utils import getpt


class Cached_descriptionParsed(CacheJsonl):

    def __init__(self, filename, descriptions, parser: DescriptionParser):
        super().__init__(filename)
        self.descriptions = descriptions
        self.parser = parser

    def generate(self):
        with open(self.filename, "w+") as file:
            for page in self.descriptions.iter():
                val = self.parser.parse(page['ns'], page['title'], page['template'], page['params'])
                if val:
                    print(to_json(val), file=file)
                else:
                    print(f'Skipping {page["title"]}')


class CachedFilteredDescription(CacheInMemory):

    def __init__(self, descriptions, filter):
        super().__init__()
        self.descriptions = descriptions
        self.filter = filter

    def generate(self):
        result = []
        for item in self.descriptions.get():
            pt = getpt(item)
            # if 'amenity=bicycle' not in pt.full_title: continue
            if pt.ns % 2 != 1 and pt.ns != 2 and 'Proposed features/' not in pt.full_title and pt.type == self.filter:
                result.append(item)
        return result


class Cached_items(CacheJsonl):

    def __init__(self, filename, site, use_bot_limits):
        super().__init__(filename)
        self.site = site
        self.use_bot_limits = use_bot_limits

    def generate(self):
        with open(self.filename, "w+") as file:
            # For bots this might need to be smaller because the total download could exceed maximum allowed
            batch_size = 500 if self.use_bot_limits else 50
            for sublist in itergroup(self.site.allpages(namespace=120, filterredir=False), batch_size):
                entities = _get_entities([item.titleWithoutNamespace() for item in sublist])
                if entities:
                    # JSON Lines format
                    print('\n'.join(to_json(item) for item in entities), file=file)


class CachedItems(CacheInMemory):
    def __init__(self, items):
        super().__init__()
        self.items = items


class Cached_itemByQid(CachedItems):
    def generate(self):
        result = {}
        for item in self.items.get():
            result[item['id']] = item
        return result


class Cached_itemDescByQid(CachedItems):
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


class Cached_itemKeysByStrid(CachedItems):
    def generate(self):
        result = {}
        for item in self.items.get():
            qid = item['id']
            # if qid != 'Q923': continue  #DEBUG
            instof = Prop.INSTANCE_OF.get_claim_value(item)
            if instof == Q_KEY:
                result[Prop.KEY_ID.get_claim_value(item)] = qid
            elif instof == Q_TAG:
                result[Prop.TAG_ID.get_claim_value(item)] = qid
        return result


class Cached_byname(CachedItems):
    def __init__(self, items, instanceof):
        super().__init__(items)
        self.instanceof = instanceof

    def generate(self):
        result = {}
        for item in self.items.get():
            if Prop.INSTANCE_OF.get_claim_value(item) != self.instanceof:
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
