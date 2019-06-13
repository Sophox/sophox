import json
import re
from datetime import datetime, timedelta, timezone
from typing import Union, List, Dict, Iterator, Iterable

import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from collections import defaultdict
from pywikibot import textlib

from pywikiapi import Site, AttrDict

from .Properties import P_INSTANCE_OF, P_KEY_ID, P_TAG_ID, P_SUBCLASS_OF, P_REL_ID, P_ROLE_ID, P_LANG_CODE
from .consts import reLanguagesClause, Q_KEY, Q_TAG, LANG_NS, ignoreLangSuspects, Q_RELATION, Q_REL_MEMBER_ROLE, \
    Q_LOCALE_INSTANCE


def to_json(obj, pretty=False):
    if pretty:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    else:
        return json.dumps(obj, ensure_ascii=False)


def get_osm_site() -> Site:
    retries = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=retries))

    return Site('https://wiki.openstreetmap.org/w/api.php', session=session, json_object_hook=AttrDict)


def get_entities(site: Site, ids: Union[str, List[str]] = None, titles: Union[str, List[str]] = None) \
        -> Union[None, Dict, List[Dict]]:
    if ids is None == titles is None:
        raise ValueError('Missing one of args, or both are given')
    if ids:
        expect_single = type(ids) is not list
        resp = site(action='wbgetentities',
                    ids=[ids] if expect_single else ids,
                    redirects='no',
                    formatversion=1)
    else:
        expect_single = type(titles) is not list
        resp = site(action='wbgetentities',
                    sites='wiki',
                    titles=[titles] if expect_single else titles,
                    formatversion=1)

    if 'success' in resp and resp['success'] == 1 and 'entities' in resp:
        items = [v for v in resp['entities'].values() if 'missing' not in v]
        if expect_single:
            if len(items) > 1:
                raise ValueError('Unexpectedly got more than 1 value for a single request')
            return items[0] if len(items) == 1 else None
        return items
    else:
        return None


def id_to_sitelink(typ, strid):
    if typ == 'Relation':
        return sitelink_normalizer(strid, 'Relation:')
    elif typ == 'Role':
        if strid.endswith('<number>'):
            strid = strid[:-len('<number>')]
        return sitelink_normalizer(strid, 'Relation:')
    elif typ == 'Tag':
        return sitelink_normalizer(strid, 'Tag:')
    elif typ == 'Key':
        return sitelink_normalizer(strid, 'Key:')
    elif typ == 'Locale':
        return sitelink_normalizer(strid, 'Locale:')
    raise ValueError(f'Unknown type {typ} for {strid}')


def sitelink_normalizer(strid, prefix=''):
    return (prefix + strid).replace('_', ' ').strip()


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
re_wikidata = re.compile(r'^(Q|Property:P)[1-9][0-9]{0,11}$')

# links like [[Key:...|...]], with the optional language prefix??//
re_tag_link = re.compile(r'\[\[(?:(' + reLanguagesClause + r'):)?(Key|Tag|Relation):([^|\]]+)(?:\|([^|\]]+))?\]\]',
                         re.IGNORECASE)

re_lang_template = re.compile(r'^(?:' + reLanguagesClause + r':)?(?:Template:)?(.*)$', re.IGNORECASE)
goodValue = re.compile(r'^[a-zA-Z0-9]+([-: _.][a-zA-Z0-9]+)*:?$')


def lang_pick(vals, lang):
    return vals[lang] if lang in vals else vals['en']


def get_instance_of(item):
    value = P_INSTANCE_OF.get_claim_value(item, allow_multiple=True)
    if value and len(value) == 1 and value[0] == Q_TAG:
        return value[0]
    return None


def strid_from_item(item):
    instance_of = get_instance_of(item)
    if instance_of == Q_KEY:
        return 'Key', P_KEY_ID.get_claim_value(item) or item.labels.en.value
    elif instance_of == Q_TAG:
        return 'Tag', P_TAG_ID.get_claim_value(item) or item.labels.en.value
    elif instance_of == Q_RELATION:
        return 'Relation', P_REL_ID.get_claim_value(item)
    elif instance_of == Q_REL_MEMBER_ROLE:
        return 'Role', P_ROLE_ID.get_claim_value(item)
    elif instance_of == Q_LOCALE_INSTANCE:
        return 'Locale', P_LANG_CODE.get_claim_value(item)
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


def to_item_sitelink(sitelink):
    return {'wiki': {'site': 'wiki', 'title': sitelink}}


def parse_members(line, printer, info):
    vals = {}
    for vt in textlib.extract_templates_and_params(line, True, True):
        name, params = vt
        m = re_lang_template.match(name)
        if m:
            name = m[1]
        name = name.lower()
        if name == 'iconnode' or (name == 'icon' and '1' in params and params['1'] == 'node'):
            vals['onnode'] = 'yes'
        elif name == 'iconway' or (name == 'icon' and '1' in params and params['1'] == 'way'):
            vals['onway'] = 'yes'
        elif name == 'iconrelation' or (name == 'icon' and '1' in params and params['1'] == 'relation'):
            vals['onrelation'] = 'yes'
        elif name == 'iconarea' or (name == 'icon' and '1' in params and params['1'] == 'area'):
            vals['onarea'] = 'yes'
        elif name == 'iconclosedway' or (name == 'icon' and '1' in params and params['1'] == 'closedway'):
            vals['onclosedway'] = 'yes'
        elif name == 'value':
            if list(params.keys()) == ['1']:
                vals['value'] = params['1']
                vals['value'] = params['1']
            elif len(params.keys()) == 0:
                vals['value'] = ''
            else:
                printer(f"Unknown value param pattern in '{line}'")
        elif name == 'icon':
            if list(params.keys()) == ['1']:
                p = params['1'].lower()
                if p == 'n' or p == 'node':
                    vals['onnode'] = 'yes'
                elif p == 'w' or p == 'way':
                    vals['onway'] = 'yes'
                elif p == 'r' or p == 'relation':
                    vals['onrelation'] = 'yes'
            else:
                printer(f"Unknown value param pattern in '{line}'")
        else:
            info(f"Unknown template {name} in '{line}'")
    return vals


def get_recently_changed_items(site, last_change, grace_period, caches):
    stop_at = (datetime.utcnow() - timedelta(minutes=grace_period)).replace(tzinfo=timezone.utc)
    todo_titles = set()
    found_unprocessed_changes = False
    for res in site.query(
            list='recentchanges',
            rcstart=last_change,
            rcdir='newer',
            rcprop=['timestamp', 'title'],
            rclimit='max'):
        for change in res.recentchanges:
            ts = datetime.fromisoformat(change.timestamp.replace("Z", "+00:00"))
            if not found_unprocessed_changes:
                last_change = ts
            if ts > stop_at:
                # Do not process anything within the last few minutes - often people do multiple corrections
                found_unprocessed_changes = True
            if change.ns % 2 == 1 or change.ns == 120:
                continue
            typ, _, strid, _ = parse_wiki_page_title(change.ns, change.title)
            if typ and strid:
                if found_unprocessed_changes:
                    if change.title in todo_titles:
                        # We will get to it in the next round
                        todo_titles.remove(change.title)
                else:
                    todo_titles.add(change.title)
    if not found_unprocessed_changes:
        # There are no recent changes within the grace period,
        # make sure not to get the same one we already did
        last_change += timedelta(seconds=1)

    todo_items = set()
    for batch in batches(todo_titles, 50):
        for wp in caches.descriptionParsed.parse_manual(caches.description.get_new_pages(batch)):
            todo_items.add((wp.type, wp.str_id))

    return last_change, todo_items
