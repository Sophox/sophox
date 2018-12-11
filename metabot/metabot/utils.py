import json
import re
from typing import Union, List, Dict

import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from collections import namedtuple, defaultdict

from pywikiapi import Site, AttrDict

from .consts import reLanguagesClause

def to_json(obj, pretty=False):
    if pretty:
        return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2)
    else:
        return json.dumps(obj, ensure_ascii=False)


def get_osm_site():
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
