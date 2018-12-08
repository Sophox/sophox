class Property:
    def __init__(self, id, name, type, allow_multiple=False):
        self.id = id
        self.name = name
        self.type = type
        self.allow_multiple = allow_multiple
        self.is_item = type == 'wikibase-item'
        self.dv_type = 'wikibase-entityid' if self.is_item else 'string'

        if not hasattr(Property, 'ALL'):
            Property.ALL = {}
        Property.ALL[self.id] = self

    def __str__(self):
        return f'{self.name} ({self.id})'

    def create_mainsnak(self, value):
        return {
            'type': 'statement',
            'rank': 'normal',
            'mainsnak': self.create_snak(value),
        }

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

    def set_claim_on_new(self, data, value):
        if 'claims' not in data: data['claims'] = {}
        claims = data['claims']
        mainsnak = self.create_mainsnak(value)
        if self.id in claims:
            if not self.allow_multiple:
                raise ValueError(
                    f"Cannot set value of {self} to '{value}', alread set to '{self.get_value(data['claims'][self.id])}'")
            claims[self.id].append(mainsnak)
        else:
            claims[self.id] = [mainsnak]

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
                if type(value) is not dict:
                    raise ValueError(f'Unexpected type "{type(value)}", should be "dict"')
                if value['entity-type'] != 'item':
                    raise ValueError(f'wd item type "{value["entity-type"]}" should be "item"')
                return value['id']
            else:
                return value
        raise ValueError('Unexpected item')

    def get_claim_value(self, item, allow_multiple=None):
        if 'claims' not in item or self.id not in item['claims']:
            return None
        if allow_multiple is None: allow_multiple = self.allow_multiple
        claims = item['claims'][self.id]
        if len(claims) > 1 and not allow_multiple:
            raise ValueError(f"Item {item['id']} has {len(claims)} claims {self}")
        if allow_multiple:
            values = [self.get_value(claim) for claim in claims]
            values.sort()
            return values
        else:
            return self.get_value(claims[0])

    def create_claim(self, value):
        claim = pb.Claim(repo, self.id)
        if self.is_item:
            value = pb.ItemPage(repo, value)
        elif self.type == 'commonsMedia':
            value = pb.FilePage(site, value)
        claim.setTarget(value)
        return claim

    def value_from_claim(self, claim):
        if self.is_item:
            return claim.target.id
        if self.type == 'commonsMedia':
            return claim.target.titleWithoutNamespace()
        return claim.target


INSTANCE_OF = Property('P2', 'instance-of', 'wikibase-item')
IMAGE = Property('P4', 'image', 'commonsMedia')
OSM_IMAGE = Property('P28', 'osm-image', 'string')
USED_ON = Property('P5', 'used-on', 'wikibase-item', allow_multiple=True)
NOT_USED_ON = Property('P24', 'not-used-on', 'wikibase-item', allow_multiple=True)
STATUS = Property('P6', 'status', 'wikibase-item')
KEY_TYPE = Property('P9', 'key-type', 'wikibase-item')
TAG_KEY = Property('P10', 'tag-key', 'wikibase-item')
REF_URL = Property('P11', 'ref-url', 'url')
KEY_ID = Property('P16', 'key-id', 'string')
TAG_ID = Property('P19', 'tag-id', 'string')
ROLE_ID = Property('P21', 'role-mem-id', 'string')
GROUP = Property('P25', 'group', 'wikibase-item')
