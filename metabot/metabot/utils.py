import json
import re
from typing import Union, List, Dict, Iterator, Iterable

import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from collections import defaultdict

from pywikiapi import Site, AttrDict

from .Properties import P_INSTANCE_OF, P_KEY_ID, P_TAG_ID, P_SUBCLASS_OF
from .consts import reLanguagesClause, Q_KEY, Q_TAG, LANG_NS, ignoreLangSuspects


def to_json(obj, pretty=False):
    if pretty:
        return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2)
    else:
        return json.dumps(obj, ensure_ascii=False)


def get_osm_site() -> Site:
    retries = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=retries))

    return Site('https://wiki.openstreetmap.org/w/api.php', session=session, json_object_hook=AttrDict)


def get_entities(site: Site, ids: Union[str, List[str]]) -> Union[None, Dict, List[Dict]]:
    expect_single = type(ids) is not list

    resp = site(action='wbgetentities',
                ids=[ids] if expect_single else ids,
                redirects='no')
    if 'success' in resp and resp['success'] == 1 and 'entities' in resp:
        items = list(resp['entities'].values())
        if expect_single:
            if len(items) > 1:
                raise ValueError('Unexpectedly got more than 1 value for a single request')
            return items[0] if len(items) == 1 else None
        return items
    else:
        return None


def sitelink_normalizer(strid):
    return strid.replace('_', ' ').strip()


def sitelink_normalizer_key(strid):
    return sitelink_normalizer('Key:' + strid)


def sitelink_normalizer_tag(strid):
    return sitelink_normalizer('Tag:' + strid)


def get_sitelink(item):
    if 'sitelinks' not in item or 'wiki' not in item['sitelinks']:
        return None
    sl = item['sitelinks']['wiki']['title']
    norm_sl = sitelink_normalizer(sl)
    if sl != norm_sl:
        raise ValueError(f"Sitelink '{sl}' is different from normalized '{norm_sl}' for {item['id']}")
    return sl


def list_to_dict_of_lists(items, key, item_extractor=None):
    result = defaultdict(list)
    for item in items:
        k = key(item)
        if k:
            if item_extractor: item = item_extractor(item)
            result[k].append(item)
    return result


def reTag_repl(match):
    if not match[2] and not match[3]:
        return f'"{match[1]}"'
    return match[1] + '=' + (match[2] if match[2] else match[3])


def remove_wikimarkup(text):
    if "''" in text:
        return reItalic.sub(
            r'\1', reBold.sub(
                r'\1', reBoldItalic.sub(
                    r'\1', text)))
    return text


reBoldItalic = re.compile(r"'''''(.*)'''''")
reBold = re.compile(r"'''(.*)'''")
reItalic = re.compile(r"''(.*)''")
re_wikidata = re.compile(r'^Q[1-9][0-9]{0,11}$')

# links like [[Key:...|...]], with the optional language prefix??//
re_tag_link = re.compile(r'\[\[(?:(' + reLanguagesClause + r'):)?(Key|Tag|Relation):([^|\]]+)(?:\|([^|\]]+))?\]\]',
                         re.IGNORECASE)

re_lang_template = re.compile(r'^(?:' + reLanguagesClause + r':)?(?:Template:)?(.*)$', re.IGNORECASE)
goodValue = re.compile(r'^[a-zA-Z0-9]+([-: _.][a-zA-Z0-9]+)*:?$')


def lang_pick(vals, lang):
    return vals[lang] if lang in vals else vals['en']


def strid_from_item(item):
    instance_of = P_INSTANCE_OF.get_claim_value(item)
    if instance_of == Q_KEY:
        return P_KEY_ID.get_claim_value(item)
    elif instance_of == Q_TAG:
        return P_TAG_ID.get_claim_value(item)
    elif instance_of is None and P_SUBCLASS_OF.get_claim_value(item) is None and item.id != 'Q2761':
        # Ignore Sandbox Q2761
        return item.labels.en.value
    return None


keysRe = re.compile(r'^(Key|Tag|Relation):(.+)$', re.IGNORECASE)
knownLangsRe = re.compile(r'^(' + reLanguagesClause + r'):(Key|Tag|Relation):(.+)$',
                          re.IGNORECASE)
suspectedLangsRe = re.compile(r'^([^:]+):(Key|Tag|Relation):(.+)$', re.IGNORECASE)


def parse_wiki_page_title(ns, title):
    type_from_title = False
    id_from_title = False
    has_suspect_lang = False

    primens = ns - ns % 2
    try:
        lang = [k for k, v in LANG_NS.items() if v == primens][0]
    except IndexError:
        lang = 'en'

    title = title if ns == 0 else title.split(':', 1)[1]
    m = keysRe.match(title)
    if m:
        type_from_title = m.group(1)
        id_from_title = m.group(2)
    elif primens == 0:
        m = knownLangsRe.match(title)
        if m:
            lang = m.group(1).lower()
            type_from_title = m.group(2)
            id_from_title = m.group(3)
        else:
            m = suspectedLangsRe.match(title)
            if m and m.group(1).lower() not in ignoreLangSuspects:
                has_suspect_lang = True

    return type_from_title, lang, id_from_title, has_suspect_lang


def batches(items: Iterable, batch_size: int):
    res = []
    for value in items:
        res.append(value)
        if len(res) >= batch_size:
            yield res
            res = []
    if res:
        yield res
