from typing import Union

import re

from pywikibot import textlib

from .utils import remove_wikimarkup, re_wikidata, re_tag_link, re_lang_template, goodValue, sitelink_normalizer
from .consts import reLanguagesClause, LANG_NS, ignoreLangSuspects, languages
from .ResolvedImageFiles import *

keysRe = re.compile(r'^(Key|Tag|Relation):(.+)$', re.IGNORECASE)
knownLangsRe = re.compile(r'^(' + reLanguagesClause + r'):(Key|Tag|Relation):(.+)$',
                          re.IGNORECASE)
suspectedLangsRe = re.compile(r'^([^:]+):(Key|Tag|Relation):(.+)$', re.IGNORECASE)

templ_param_map = {
    'descrizione': 'description',
    'leírás': 'description',
    'описание': 'description',
    'descrição': 'description',
    'descripción': 'description',
    'descrition': 'description',
    'groupe': 'group',
    'gruppo': 'group',
    'gruppe': 'group',
    'csoport': 'group',
    'required': 'requires',
    'nativekey': 'label',
    'polska nazwa': 'label',
    'combinazioni': 'combination',
    'combinations': 'combination',
    'language': 'lang',
    'wikdata': 'wikidata',
    'siehe auch': 'seealso',
}


def id_extractor(item, type, str_id, messages=None):
    item_key = item['key'] if 'key' in item else item['oldkey'] if 'oldkey' in item else False
    item_value = item['value'] if 'value' in item else item['oldvalue'] if 'oldvalue' in item else False
    item_id: Union[bool, str] = False
    if item_key:
        item_id = item_key
        if item_value and type == 'Tag':
            item_id += '=' + item_value
    if str_id and item_id and item_id != str_id:
        if sitelink_normalizer(item_id) != sitelink_normalizer(str_id):
            if messages:
                messages.append(f"Item keys don't match:   {item_id:30} {str_id:30} in {item.full_title}")
            return False
        return item_id
    return str_id if str_id else item_id if item_id else False


class ItemParser:

    def __init__(self, image_cache: ResolvedImageFiles, pwb_site: pb.Site, ns, title, template, template_params):
        self.image_cache = image_cache
        self.pwb_site = pwb_site
        self.ns = ns
        self.title = title
        self.template = template
        self.template_params = template_params
        self.result = {}
        self.messages = []

    def setter(self, key, value, allow_multiple=False):
        if key in self.result:
            if not allow_multiple:
                if value != self.result[key]:
                    self.messages.append(f"Key {key} is already set to {self.result[key]} for page {self.title}")
            else:
                self.result[key].append(value)
        else:
            self.result[key] = [value] if allow_multiple else value

    def parse(self):
        for tkey, tval in self.template_params.items():
            tkey = tkey.lower()
            tval = tval.strip()
            if tval and (self.template != 'Deprecated' or tkey in ['oldkey', 'oldvalue', 'newtext']):
                res = self.parse_template_param(tkey, tval)
                if isinstance(res, list):
                    for vv in res:
                        self.setter(*vv)
                elif res:
                    self.setter(*res)

        primens = self.ns - self.ns % 2
        try:
            lng = [k for k, v in LANG_NS.items() if v == primens][0]
        except IndexError:
            lng = 'en'

        page_type = False
        page_title = False

        title = self.title if self.ns == 0 else self.title.split(':', 1)[1]
        m = keysRe.match(title)
        if m:
            page_type = m.group(1)
            page_title = m.group(2)
        elif primens == 0:
            m = knownLangsRe.match(title)
            if m:
                lng = m.group(1).lower()
                page_type = m.group(2)
                page_title = m.group(3)
            else:
                m = suspectedLangsRe.match(title)
                if m and m.group(1).lower() not in ignoreLangSuspects:
                    self.messages.append(f'Suspected language code in { self.title }')

        if self.result:
            str_id = id_extractor(self.result, page_type, page_title, self.messages)
            if not str_id:
                self.messages.append(f'Unable to extract ID from { page_title }')
            elif str_id != page_title:
                page_title = str_id

            return {
                'type': page_type,
                'str_id': page_title,
                'lang': lng,
                'ns': self.ns,
                'full_title': self.title,
                'params': self.result,
            }

    def parse_template_param(self, tkey, tval):
        if tkey in templ_param_map:
            tkey = templ_param_map[tkey]
        if tval.startswith('*'):
            tval = tval[1:].strip()

        if tkey in ['key', 'value', 'oldkey', 'oldvalue', 'newtext', 'type', 'label', 'nativekey', 'nativevalue',
                    'lang', 'group', 'groups', 'category', 'description', 'osmcarto-rendering-size', 'image caption',
                    'website', 'displayname', 'proposal']:
            return tkey, tval
        elif tkey == 'wikidata':
            if re_wikidata.match(tval):
                return tkey, tval
            self.messages.append(f'Bad wikidata {tval}')
        elif tkey == 'status':
            return tkey, tval.lower()
        elif tkey in ['onnode', 'onarea', 'onway', 'onrelation', 'onclosedway', 'onchangeset']:
            tval = tval.lower()
            if tval in ['yes', 'no']:
                return tkey, tval
            if tval != '?':
                self.messages.append(f'Unrecognized {tkey}={tval}')
        elif tkey == 'statuslink':
            if tval.startswith('[[') and tval.endswith(']]'):
                tval = (tval[2:-2].split('|')[0]).strip()
            if tval:
                try:
                    return tkey, pb.Page(self.pwb_site, tval).full_url()
                except pb.exceptions.InvalidTitle as err:
                    self.messages.append(f'Unparsable {tkey}={tval}')
        elif tkey in ['image', 'osmcarto-rendering']:
            try:
                return tkey, self.image_cache.parse_image_title(tval)
            except:
                self.messages.append(f'image="{tval}" cannot be processed')
        elif tkey in ['combination', 'implies', 'seealso', 'requires']:
            tags = self.parse_combinations(tkey, tval)
            if len(tags) > 0:
                return [(tkey, tags), (tkey + '!text', tval)]
            self.messages.append(f'No tags found in {tkey} -- {tval}')
        elif tkey in 'members':
            members = self.parse_members(tval)
            if len(members) > 0:
                return [('members', members), (tkey + '!text', tval)]
            self.messages.append(f'No items found in {tkey} -- {tval}')
        elif tkey in ['languagelinks', 'image:desc', 'image_caption', 'float', 'debug', 'dir', 'rtl']:
            pass  # We know them, but they are not very useful at this point
        else:
            self.messages.append(f'Unknown "{tkey}={tval}"')
        return None

    def parse_combinations(self, tkey, tval):
        tags = {}
        for vt in textlib.extract_templates_and_params(tval, True, True):
            for k, v in self.parse_tag(vt, allow_key_only=True):
                tags[k] = v
        # Parse free text links like [[ (Key) : (lanes) | (lanes) ]]
        for link in re_tag_link.findall(tval):
            dummy, typ, lnk, freetext = link
            typ = typ.lower()
            ok = True
            if typ == 'key' and lnk not in tags:
                tags[lnk] = ''
            elif typ == 'tag' and '=' in lnk:
                k, v = lnk.split('=', 1)
                if k in tags:
                    ok = False
                else:
                    tags[k] = v
            else:
                ok = False
            if not ok:
                self.messages.append(f'Parsed link in {tkey} is unrecognized: {typ}:{lnk} | {freetext}')
        return tags

    def parse_members(self, tval):
        members = []
        for line in re.split('(^ *\*|\n *\*)', tval.strip()):
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
                    else:
                        self.messages.append(f"Unknown value param pattern in '{line}'")
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
                        self.messages.append(f"Unknown value param pattern in '{line}'")
                else:
                    self.messages.append(f"Unknown template {name} in '{line}'")
            if vals:
                if 'value' not in vals:
                    m = re.match(r'^\s*(?:{{[^{}]+\}\}(?:\s|-|—)*)*(\(?[a-z_: /]+(<[^ {}\[\]<>]*>)?\)?)\s*$',
                                 line)
                    if m:
                        if '/' in m[1]:
                            for v in m[1].split('/'):
                                v = v.strip()
                                if v:
                                    vals2 = vals.copy()
                                    vals2['value'] = v
                                    members.append(vals2)
                            continue
                        vals['value'] = m[1]
                    else:
                        self.messages.append(f"Value not found in '{line}'")
                        continue
                members.append(vals)
        return members

    def parse_tag(self, template, allow_key_only=False):
        name, params = template
        name = name.lower()
        if (name.startswith('template:') or name.startswith('Template:')):
            name = name[len('template:'):]
        if ':' in name:
            prefix, name = name.split(':', 1)
            if prefix not in languages:
                self.messages.append(f'Bad Tag value "{prefix}:{name}" (unknown prefix)')
                return
        if name not in ['tag', 'key', 'tagkey', 'tagvalue']:
            if allow_key_only and name != 'english':
                self.messages.append(f'Bad Tag value "{name}"')
            return
        key = ''
        if '1' in params:
            key = params['1'].strip()
            if ':' in params: key += ':' + params[':'].strip()
            if '::' in params: key += ':' + params['::'].strip()
            if ':::' in params: key += ':' + params[':::'].strip()
        value = ''
        if '2' in params:
            value = params['2'].strip()
        if value == '' and '3' in params:
            value = params['3'].strip()
        value = remove_wikimarkup(value)

        for value in re.split(r'[/;]+', value):
            value = value.strip()
            if not goodValue.match(value):
                if not allow_key_only: continue
                if value not in ['', '*']:
                    self.messages.append(f'Bad Tag value {value}')
            if not goodValue.match(key): continue
            yield key, value
