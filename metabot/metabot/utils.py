import json
from typing import Type, Tuple

import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from collections import namedtuple

from pywikiapi import Site, AttrDict

ParsedTitle = namedtuple('ParsedTitle', 'type str_id lang ns full_title')


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


def getpt(item):
    pt = item['_parsed_title']
    if type(pt) is list:
        pt = ParsedTitle(*pt)
        item['_parsed_title'] = pt
    return pt
