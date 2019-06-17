from typing import Dict, Set, Union
from dataclasses import dataclass, field


def mono_value(lang, text):
    return {'language': lang, 'text': text}

@dataclass
class ClaimValue:
    value: Union[str, Dict]
    qualifiers: Dict['Property', Set[str]] = field(default_factory=dict)
    rank: str = 'normal'


class Property:
    ALL: Dict[str, 'Property'] = {}

    def __init__(self, id, name, type, allow_multiple=False, allow_qualifiers=False, is_qualifier=False, ignore=False, merge_all=False):
        self.ignore = ignore
        self.id = id
        self.name = name
        self.type = type
        self.merge_all = merge_all
        self.allow_multiple = allow_multiple
        self.allow_qualifiers = allow_qualifiers
        self.is_qualifier = is_qualifier
        self.is_item = type == 'wikibase-item'
        self.is_monotext = type == 'monolingualtext'
        if self.is_item:
            self.dv_type = 'wikibase-entityid'
        elif self.is_monotext:
            self.dv_type = 'monolingualtext'
        else:
            self.dv_type = 'string'
        if self.id in Property.ALL:
            raise ValueError(f'{self.id} already exists for {Property.ALL[self.id]}')
        Property.ALL[self.id] = self

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f'{self.name} ({self.id})'

    def __hash__(self) -> int:
        return self.id.__hash__()

    def __eq__(self, o: 'Property') -> bool:
        return self.id.__eq__(o.id)

    def create_snak(self, value):
        if self.is_item:
            value = {'entity-type': 'item', 'id': value}
        elif self.is_monotext:
            # if isinstance(value, tuple) and len(value) == 2:
            #     value = mono_value(value[0], value[1])
            # el
            if not isinstance(value, dict) or len(value) != 2:
                raise ValueError('Monolingual values expect a two value tuple or a lang/text dict')

        return {
            'snaktype': 'value',
            'property': self.id,
            'datatype': self.type,
            'datavalue': {
                'value': value,
                'type': self.dv_type,
            }
        }

    def remove_claim(self, data, value: ClaimValue):
        if 'claims' not in data or self.id not in data['claims']:
            return
        claims = data['claims'][self.id]
        for claim in claims:
            if self.claim_to_claimvalue(claim, True) == value:
                claims.remove(claim)
                if not claims:
                    del data['claims'][self.id]
                break

    def set_claim_on_new(self, data, value: ClaimValue):
        if 'claims' not in data: data['claims'] = {}
        claims = data['claims']
        claim = {
            'type': 'statement',
            'rank': value.rank,
            'mainsnak': self.create_snak(value.value),
        }
        if value.qualifiers and len(value.qualifiers) > 0:
            claim['qualifiers'] = {}
            for p, vals in value.qualifiers.items():
                claim['qualifiers'][p.id] = [p.create_snak(v) for v in vals]

        if self.id in claims:
            if not self.merge_all and not self.allow_multiple and not self.allow_qualifiers:
                raise ValueError(
                    f"Cannot set value of {self} to '{value}', "
                    f"already set to '{self.get_value(data['claims'][self])}'")
            claims[self.id].append(claim)
        else:
            claims[self.id] = [claim]

    def get_value(self, item):
        if 'mainsnak' in item:
            if item['type'] != 'statement':
                raise ValueError(f'Unknown mainsnak type "{item["type"]}"')
            item = item['mainsnak']
        if 'datavalue' in item:
            if item['snaktype'] != 'value':
                raise ValueError(f'Unknown snaktype "{item["snaktype"]}"')
            dv = item['datavalue']
            if dv['type'] != self.dv_type:
                raise ValueError(f'Datavalue type "{dv["type"]}" should be "{self.dv_type}"')
            value = dv['value']
            if self.is_item:
                if not isinstance(value, dict):
                    raise ValueError(f'Unexpected type "{type(value)}", should be "dict"')
                if value['entity-type'] != 'item':
                    raise ValueError(f'wd item type "{value["entity-type"]}" should be "item"')
                return value['id']
            # elif self.is_monotext:
            #     return value['language'], value['text']
            return value
        raise ValueError('Unexpected item')

    def get_claim_value(self, item, allow_multiple=None, allow_qualifiers=None):
        if allow_multiple is None: allow_multiple = self.allow_multiple
        if allow_qualifiers is None: allow_qualifiers = self.allow_qualifiers
        if 'claims' in item and self.id in item.claims:
            claims = item.claims[self.id]
        elif self.id in item:
            # parsing qualifier
            claims = item[self.id]
        else:
            return None
        if len(claims) > 1 and not allow_multiple:
            raise ValueError(f"Item {item.id} has {len(claims)} claims {self}")
        values = []
        for claim in claims:
            values.append(self.claim_to_claimvalue(claim, allow_qualifiers))
        if not allow_multiple:
            return values[0]
        else:
            return values

    def claim_to_claimvalue(self, claim, include_qualifiers):
        value = self.get_value(claim)
        if include_qualifiers:
            qualifiers = {}
            if 'qualifiers' in claim:
                for qid, qval in claim.qualifiers.items():
                    qprop = Property.ALL[qid]
                    qlf = qprop.get_claim_value(claim.qualifiers)
                    if qlf:
                        qualifiers[qprop] = qlf if qprop.is_monotext else set(qlf)
            value = ClaimValue(value, qualifiers, claim.rank)
        elif 'qualifiers' in claim:
            raise ValueError(f'{self} does not support qualifiers')
        return value

    def value_from_claim(self, claim):
        if self.is_item:
            return claim.target.id
        if self.type == 'commonsMedia':
            return claim.target.titleWithoutNamespace()
        return claim.target


P_INSTANCE_OF = Property('P2', 'instance-of', 'wikibase-item')
P_SUBCLASS_OF = Property('P3', 'subclass-of', 'wikibase-item')

P_IMAGE_DEPRICATED = Property('P4', 'image-depr', 'commonsMedia', allow_qualifiers=True)
P_IMAGE = Property('P28', 'image', 'string', allow_qualifiers=True)
P_STATUS = Property('P6', 'status', 'wikibase-item', allow_qualifiers=True)
P_GROUP = Property('P25', 'group', 'wikibase-item', allow_qualifiers=True)
P_USE_ON_NODES = Property('P33', 'use-on-nodes', 'wikibase-item', allow_qualifiers=True)
P_USE_ON_WAYS = Property('P34', 'use-on-ways', 'wikibase-item', allow_qualifiers=True)
P_USE_ON_AREAS = Property('P35', 'use-on-areas', 'wikibase-item', allow_qualifiers=True)
P_USE_ON_RELATIONS = Property('P36', 'use-on-relations', 'wikibase-item', allow_qualifiers=True)
P_USE_ON_CHANGESETS = Property('P37', 'use-on-changesets', 'wikibase-item', allow_qualifiers=True)
P_WIKIDATA_EQUIVALENT = Property('P7', 'wikidata-equivalent', 'string', allow_qualifiers=True)
P_WIKIDATA_CONCEPT = Property('P12', 'wikidata-concept', 'string', allow_qualifiers=True)
P_URL_FORMAT = Property('P8', 'url-format', 'string')

P_REQUIRES_KEY_OR_TAG = Property('P22', 'requires-key-or-tag', 'wikibase-item', allow_multiple=True, merge_all=True)

P_RENDERING_IMAGE_DEPRECATED = Property('P38', 'rendering-image-depr', 'commonsMedia', allow_qualifiers=True)
P_RENDERING_IMAGE = Property('P39', 'rendering-image', 'string', allow_qualifiers=True)

P_KEY_TYPE = Property('P9', 'key-type', 'wikibase-item')
P_TAG_KEY = Property('P10', 'tag-key', 'wikibase-item')
P_REL_TAG = Property('P40', 'rel-tag', 'wikibase-item')
P_REDIRECT_TO = Property('P17', 'redirect-to', 'wikibase-item')
P_DIFF_FROM = Property('P18', 'diff-from', 'wikibase-item', merge_all=True)
P_REF_URL = Property('P11', 'ref-url', 'url')
P_KEY_ID = Property('P16', 'key-id', 'string')
P_TAG_ID = Property('P19', 'tag-id', 'string')
P_REL_ID = Property('P41', 'rel-id', 'string')
P_ROLE_ID = Property('P21', 'role-mem-id', 'string')
P_LANG_CODE = Property('P32', 'lang-code', 'string')
P_LIMIT_TO = Property('P26', 'limit-to', 'wikibase-item', allow_multiple=True, is_qualifier=True)
P_LIMIT_TO_RGN = Property('P48', 'limit-to-rgn', 'wikibase-item', allow_multiple=True, is_qualifier=True)
P_REL_FOR_ROLE = Property('P43', 'role-rel', 'wikibase-item')
P_REGEX = Property('P13', 'regex', 'string')
P_WIKI_PAGES = Property('P31', 'wiki-pages', 'monolingualtext', allow_multiple=True)
P_WIKI_PAGE_REDIR = Property('P50', 'wiki-pages-redir', 'string', is_qualifier=True)
P_INCOMPATIBLE_WITH = Property('P44', 'incompatible-with', 'wikibase-item')

P_IMPLIES = Property('P45', 'implies', 'wikibase-item', merge_all=True)
P_COMBINATION = Property('P46', 'combination', 'wikibase-item', merge_all=True)

P_IMG_CAPTION = Property('P47', 'img-caption', 'monolingualtext', allow_multiple=True, is_qualifier=True)
