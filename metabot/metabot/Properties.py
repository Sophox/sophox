from collections import namedtuple
from typing import Dict, Set, Union
import pywikibot as pb
from dataclasses import dataclass, field


@dataclass
class ClaimValue:
    value: str
    qualifiers: Dict['Property', Set[str]] = field(default_factory=dict)
    rank: str = 'normal'

    def promote(self):
        if self.rank != 'normal':
            raise ValueError(f'{self} cannot be promoted')
        return ClaimValue(self.value, self.qualifiers, 'preferred')


class Property:
    ALL: Dict[str, 'Property'] = {}

    def __init__(self, id, name, type, allow_multiple=False, allow_qualifiers=False, is_qualifier=False, ignore=False):
        self.ignore = ignore
        self.id = id
        self.name = name
        self.type = type
        self.allow_multiple = allow_multiple
        self.allow_qualifiers = allow_qualifiers
        self.is_qualifier = is_qualifier
        self.is_item = type == 'wikibase-item'
        self.dv_type = 'wikibase-entityid' if self.is_item else 'string'
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
        return {
            'snaktype': 'value',
            'property': self.id,
            'datatype': self.type,
            'datavalue': {
                'value': {'entity-type': 'item', 'id': value} if self.is_item else value,
                'type': self.dv_type,
            }
        }

    def set_claim_on_new(self, data, value: ClaimValue):
        if 'claims' not in data: data['claims'] = {}
        claims = data['claims']
        claim = {
            'type': 'statement',
            'rank': value.rank,
            'mainsnak': self.create_snak(value.value),
        }
        if value.qualifiers:
            claim['qualifiers'] = {}
            for q in value.qualifiers:
                print(q)

        if self.id in claims:
            if not self.allow_multiple:
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
            else:
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
            value = self.get_value(claim)
            if allow_qualifiers:
                qualifiers = {}
                if 'qualifiers' in claim:
                    qlf = P_LIMIT_TO.get_claim_value(claim.qualifiers)
                    if qlf:
                        qualifiers[P_LIMIT_TO] = set(qlf)
                value = ClaimValue(value, qualifiers, claim.rank)
            elif 'qualifiers' in claim:
                raise ValueError(f'{self} does not support qualifiers')
            values.append(value)
        if not allow_multiple:
            return values[0]
        else:
            self.sort_claims(values, allow_qualifiers)
            return values

    def sort_claims(self, values, allow_qualifiers=None):
        if allow_qualifiers is None: allow_qualifiers = self.allow_qualifiers
        values.sort(key=lambda v: (1 if v.rank == 'preferred' else 2, v.value) if allow_qualifiers else v)

    def create_claim(self, site, value: Union[ClaimValue, str]):
        claim = pb.Claim(site, self.id, is_qualifier=self.is_qualifier)
        if type(value) == ClaimValue:
            val = value.value
            claim.setRank(value.rank)
        else:
            val = value
        if self.is_item:
            claim.setTarget(pb.ItemPage(site, val))
        elif self.type == 'commonsMedia':
            claim.setTarget(pb.FilePage(site, val))
        else:
            claim.setTarget(val)
        return claim

    def value_from_claim(self, claim):
        if self.is_item:
            return claim.target.id
        if self.type == 'commonsMedia':
            return claim.target.titleWithoutNamespace()
        return claim.target


P_INSTANCE_OF = Property('P2', 'instance-of', 'wikibase-item')
P_SUBCLASS_OF = Property('P3', 'subclass-of', 'wikibase-item')

P_IMAGE = Property('P4', 'image', 'commonsMedia', allow_qualifiers=True)
P_OSM_IMAGE = Property('P28', 'osm-image', 'string', allow_qualifiers=True)
P_STATUS = Property('P6', 'status', 'wikibase-item', allow_qualifiers=True)
P_GROUP = Property('P25', 'group', 'wikibase-item', allow_qualifiers=True)
P_USE_ON_NODES = Property('P33', 'use-on-nodes', 'wikibase-item', allow_qualifiers=True)
P_USE_ON_WAYS = Property('P34', 'use-on-ways', 'wikibase-item', allow_qualifiers=True)
P_USE_ON_AREAS = Property('P35', 'use-on-areas', 'wikibase-item', allow_qualifiers=True)
P_USE_ON_RELATIONS = Property('P36', 'use-on-relations', 'wikibase-item', allow_qualifiers=True)
P_USE_ON_CHANGESETS = Property('P37', 'use-on-changesets', 'wikibase-item', allow_qualifiers=True)

P_KEY_TYPE = Property('P9', 'key-type', 'wikibase-item')
P_TAG_KEY = Property('P10', 'tag-key', 'wikibase-item')
P_REF_URL = Property('P11', 'ref-url', 'url')
P_KEY_ID = Property('P16', 'key-id', 'string')
P_TAG_ID = Property('P19', 'tag-id', 'string')
P_ROLE_ID = Property('P21', 'role-mem-id', 'string')
P_LANG_CODE = Property('P32', 'lang-code', 'string')
P_LIMIT_TO = Property('P26', 'limit-to', 'wikibase-item', allow_multiple=True, is_qualifier=True)


# [sorted(self.claims.items(), lambda v: ['P2', 'P3', 'P16', 'P9', 'P19', 'P10', 'P4', 'P28', 'P6', 'P33', 'P34', 'P35', 'P36', 'P37', 'P25']
