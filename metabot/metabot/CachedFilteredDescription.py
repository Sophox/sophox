import re

from pywikiapi import AttrDict

from .utils import list_to_dict_of_lists, to_json
from .Cache import CacheInMemory


class CachedFilteredDescription(CacheInMemory):

    def __init__(self, descriptions, filter):
        super().__init__()
        self.descriptions = descriptions
        self.filter = filter

    def generate(self):
        result = []
        for item in self.descriptions.get():
            if item.type == self.filter:
                result.append(item)
        return result


class RelationRolesDescription(CacheInMemory):

    def __init__(self, descriptions):
        super().__init__()
        self.descriptions = descriptions

    def generate(self):
        result = []
        for item in self.descriptions.get():
            # if 'amenity=bicycle' not in pt.full_title: continue
            if item.ns % 2 == 1 or item.ns == 2 or 'Proposed features/' in item.full_title:
                continue

            if item.type != 'Relation' or 'members' not in item.params:
                continue

            for role, lst in list_to_dict_of_lists(item.params.members, lambda v: v.value).items():
                if role == '(blank)':
                    role = ''
                if not re.match(r'^[a-zA-Z0-9_:-]*$', role):
                    role = role \
                        .replace('<숫자>', '<number>') \
                        .replace('<число>', '<number>') \
                        .replace('<数値>', '<number>') \
                        .replace('<číslo>', '<number>')
                    if not re.match(r'^[a-zA-Z0-9_:-]*<number>$', role):
                        print(f"Role '{role}' is not legal")
                        continue
                str_id = item.params.type + '=' + role.replace('(blank)', '')
                params = AttrDict()
                for rl in lst:
                    for k, v in rl.items():
                        if k != 'value':
                            params[k] = v
                result.append(AttrDict(
                    full_title=str_id,
                    lang=item.lang,
                    ns=item.ns,
                    str_id=str_id,
                    type='Role',
                    params=params
                ))

        return result
