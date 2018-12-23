from typing import List, Dict

import re
from collections import defaultdict

from pywikiapi import AttrDict

from .Properties import P_OSM_IMAGE, P_IMAGE, P_GROUP, P_STATUS, Property, P_INSTANCE_OF, \
    P_KEY_ID, P_TAG_ID, P_TAG_KEY, P_LIMIT_TO, ClaimValue, P_USE_ON_NODES, P_USE_ON_WAYS, P_USE_ON_AREAS, \
    P_USE_ON_RELATIONS, P_USE_ON_CHANGESETS, P_LANG_CODE
from .consts import reLanguagesClause, Q_TAG, Q_KEY, Q_IS_ALLOWED, Q_IS_PROHIBITED, Q_LOCALE_INSTANCE
from .utils import list_to_dict_of_lists, reTag_repl, remove_wikimarkup, lang_pick, sitelink_normalizer_tag, \
    sitelink_normalizer_key, sitelink_normalizer


class ItemFromConcept:

    def __init__(self, item, lang_code=None, lang_name=None) -> None:
        self.item = item
        self.lang_code = P_LANG_CODE.get_claim_value(item) if item else lang_code
        self.ok = True
        self.messages = []

        self.claims = {
            P_INSTANCE_OF: [ClaimValue(Q_LOCALE_INSTANCE)],
            P_LANG_CODE: [ClaimValue(self.lang_code)],
        }

        self.sitelink = sitelink_normalizer('Locale:' + self.lang_code)

        self.editData = {
            'labels': {},
            'descriptions': {},
            'sitelinks': [{'site': 'wiki', 'title': self.sitelink}],
        }

        if item:
            self.editData['labels'].update({k: v.value for k, v in item.labels.items()})
            self.editData['descriptions'].update({k: v.value for k, v in item.descriptions.items()})
        else:
            self.editData['labels']['en'] = f'{lang_name}-speaking region'
            self.editData['descriptions']['en'] = f'This region includes {lang_name}-speaking countries ' \
                f'to document the difference in rules. Use it with P26 qualifier.'

    def print(self, msg):
        self.messages.append(msg)

    def print_messages(self):
        if self.messages:
            print(f'Creating item for {self.lang_code}')
            for msg in self.messages:
                print(msg)
