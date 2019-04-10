import time
from json import loads

from pywikiapi import Site, AttrDict
from .Properties import *

prop_delete = {'P5', 'P24'}
root_order = ['pageid', 'ns', 'title', 'lastrevid', 'modified', 'type', 'id', 'labels', 'descriptions', 'aliases', 'sitelinks', 'claims']

prop_order = [
    P_INSTANCE_OF.id,
    P_SUBCLASS_OF.id,
    P_LANG_CODE.id,
    P_KEY_ID.id,
    P_KEY_TYPE.id,
    P_TAG_ID.id,
    P_TAG_KEY.id,
    P_REL_ID.id,
    P_REL_TAG.id,
    P_ROLE_ID.id,
    P_REDIRECT_TO.id,
    P_IMAGE_DEPRICATED.id,
    P_IMAGE.id,
    P_RENDERING_IMAGE_DEPRECATED.id,
    P_RENDERING_IMAGE.id,
    P_STATUS.id,
    P_USE_ON_NODES.id,
    P_USE_ON_WAYS.id,
    P_USE_ON_AREAS.id,
    P_USE_ON_RELATIONS.id,
    P_USE_ON_CHANGESETS.id,
    P_GROUP.id,
    P_WIKIDATA_CONCEPT.id,
    P_REQUIRES_KEY_OR_TAG.id,
    P_INCOMPATIBLE_WITH.id,
    P_IMPLIES.id,
    P_COMBINATION.id,
    P_DIFF_FROM.id,
    P_REF_URL.id,
    P_LIMIT_TO.id,
    P_IMG_CAPTION.id,
    P_WIKI_PAGES.id,
    P_WIKIDATA_EQUIVALENT.id,
    P_URL_FORMAT.id,
    P_REL_FOR_ROLE.id,
    P_REGEX.id,
]

qualifier_order = [
    'Q7811',  # Albanian-speaking region
    'Q7780',  # Arabic-speaking region
    'Q7781',  # Azerbaijani-speaking region
    'Q7783',  # Bengali-speaking region
    'Q7782',  # Bulgarian-speaking region
    'Q7816',  # Cantonese-speaking region
    'Q7784',  # Catalan-speaking region
    'Q7817',  # Region that uses Simplified Chinese
    'Q7818',  # Region that uses Traditional Chinese
    'Q7794',  # Croatian-speaking region
    'Q7785',  # Czech-speaking region
    'Q7786',  # Danish-speaking region
    'Q7804',  # Dutch-speaking region
    'Q7789',  # Estonian-speaking region
    'Q7791',  # Finnish-speaking region
    'Q7792',  # French-speaking region
    'Q7793',  # Galician-speaking region
    'Q6994',  # German-speaking region
    'Q7787',  # Greek-speaking region
    'Q7795',  # Region that speaks Haitian Creole
    'Q7796',  # Hungarian-speaking region
    'Q7797',  # Indonesian-speaking region
    'Q7798',  # Italian-speaking region
    'Q7799',  # Japanese-speaking region
    'Q7800',  # Korean-speaking region
    'Q7802',  # Latvian-speaking region
    'Q7801',  # Lithuanian-speaking region
    'Q7803',  # Malay-speaking region
    'Q7805',  # Norwegian-speaking region
    'Q7790',  # Persian-speaking region
    'Q7806',  # Polish-speaking region
    'Q7807',  # Portuguese-speaking region
    'Q7808',  # Romanian-speaking region
    'Q7809',  # Russian-speaking region
    'Q7810',  # Slovak-speaking region
    'Q7788',  # Spanish-speaking region
    'Q7812',  # Swedish-speaking region
    'Q7813',  # Turkish-speaking region
    'Q7814',  # Ukrainian-speaking region
    'Q7815',  # Vietnamese-speaking region
]


def dict_sorter(content, key_func, filter_func=None):
    if filter_func:
        return {v[0]: v[1] for v in sorted(content.items(), key=key_func) if filter_func(v)}
    else:
        return {v[0]: v[1] for v in sorted(content.items(), key=key_func)}


def key_from_list(key, order, ignore=None):
    try:
        return order.index(key)
    except ValueError:
        if not ignore or key not in ignore:
            print(f'Unknown value {key}')
            # return int(key[1:]) + 10000
            return key
        else:
            return 10000


def mainsnak_key(snak):
    pref = snak['rank'] == 'preferred'
    val = snak_key(snak['mainsnak'])
    return claim_order(pref, val)


def claim_order(pref, val):
    if type(val) == str:
        return (' ' if pref else '_') + val
    if type(val) == dict or type(val) == AttrDict:
        res = ' ' if pref else '_'
        if 'language' in val:
            if val['language'] == 'en':
                res += '__'
            else:
                res += val['language']
        if 'id' in val:
            res += val['id']
        return res
    if type(val) == tuple:
        return '' if val[0] == 'en' else val[0]
    return (0 if pref else 1000) + val


def snak_key(snak):
    val = snak['datavalue']['value']
    if type(val) != str and 'id' in val:
        return val['id']
    return val


def lang_sorter(kv):
    return '' if kv[0] == 'en' else kv[0]


def monoling_sorter(kv):
    lang = kv['datavalue']['value']['language']
    return '' if lang == 'en' else lang


class Sorter:

    def __init__(self, site: Site) -> None:
        self.site = site

    def do_page(self, title, page):
        new_content = self.order(loads(page.revisions[0].content))
        if not new_content:
            print(f"{title} has not changed")
            return

        print(f"Uploading {title}")
        time.sleep(7)
        self.site('wbeditentity',
                  id=title[len('Item:'):],
                  summary='Removing meant/not-meant props, sorting',
                  token=self.site.token(),
                  data=new_content,
                  clear=1,
                  bot=1,
                  POST=1)

    def order(self, content):
        content = dict_sorter(content, lambda v: key_from_list(v[0], root_order))
        for k in ['labels', 'descriptions', 'aliases']:
            if k in content and content[k]:
                content[k] = dict_sorter(content[k], lang_sorter)
        if 'claims' in content and content['claims']:
            content['claims'] = dict_sorter(
                content['claims'],
                lambda v: key_from_list(v[0], prop_order, prop_delete),
                lambda v: v[0] not in prop_delete)

            for prop_id, claim in content['claims'].items():
                if not Property.ALL[prop_id].merge_all:
                    claim.sort(key=mainsnak_key)
                for cl in claim:
                    if 'qualifiers' in cl:
                        for qp, qvals in cl['qualifiers'].items():
                            if qp == P_LIMIT_TO.id:
                                qvals.sort(key=lambda v: key_from_list(snak_key(v), qualifier_order))
                            elif qp == P_IMG_CAPTION.id:
                                qvals.sort(key=monoling_sorter)
                            else:
                                qvals.sort(key=lambda v: v.datavalue.value)
                    if 'qualifiers-order' in cl:
                        cl['qualifiers-order'].sort(key=lambda v: key_from_list(v, prop_order, prop_delete))
        return content

    def run(self):
        for title in self.get_pages():
            try:
                id = int(title[len('Item:Q'):])
                if id > 8100:
                    continue
                self.run_page(title)
            except Exception as exception:
                print(title, exception)

    def run_page(self, title):
        for page in self.site.query_pages(
                prop='revisions',
                rvprop='content',
                redirects='no',
                titles=title):
            self.do_page(title, page)

    def get_pages(self):
        for q in self.site.query(list='allpages', apnamespace=120, apfilterredir='nonredirects', aplimit='100'):
            for p in q.allpages:
                yield p.title
