from typing import Union

import re

from pywikibot import textlib

from .utils import remove_wikimarkup, re_wikidata, re_tag_link, re_lang_template, goodValue, sitelink_normalizer, \
    parse_wiki_page_title
from .consts import languages
from .ResolvedImageFiles import *

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
    'polska nazwa': 'nativekey',
    'combinazioni': 'combination',
    'combinations': 'combination',
    'language': 'lang',
    'wikdata': 'wikidata',
    'siehe auch': 'seealso',
}


class ItemParser:

    def __init__(self, image_cache: ResolvedImageFiles, pwb_site: pb.Site, ns, title, template, template_params, print_info=False):
        self.print_info = print_info
        self.image_cache = image_cache
        self.pwb_site = pwb_site
        self.ns = ns
        self.title = title
        self.template = template.lower()
        self.template_params = template_params
        self.result = {}
        self.messages = []

        self.type_from_title, self.lang, self.id_from_title, has_suspect_lang = parse_wiki_page_title(ns, title)
        if has_suspect_lang:
            self.print(f'Suspected language code in { title }')

    def setter(self, key, value, allow_multiple=False):
        if key in self.result:
            if not allow_multiple:
                if value != self.result[key]:
                    self.print(f"Key {key} is already set to {self.result[key]} for page {self.title}")
            else:
                self.result[key].append(value)
        else:
            self.result[key] = [value] if allow_multiple else value

    def parse(self):
        if self.template not in [
            'keydescription', 'valuedescription', 'template:keydescription', 'template:valuedescription',
            'deprecated', 'pl:keydescription', 'pl:valuedescription', 'template:pl:keydescription',
            'template:pl:valuedescription', 'template:relationdescription', 'relationdescription'
        ]:
            # Ignore relations for now
            return

        for tkey, tval in self.template_params.items():
            tkey = tkey.lower()
            tval = tval.strip()
            if tval and (self.template != 'deprecated' or tkey in ['oldkey', 'oldvalue', 'newtext']):
                res = self.parse_template_param(tkey, tval)
                if isinstance(res, list):
                    for vv in res:
                        self.setter(*vv)
                elif res:
                    self.setter(*res)

        if self.result:
            if not self.type_from_title:
                if self.template == 'keydescription' or self.template == 'template:keydescription':
                    self.type_from_title = 'Key'
                elif self.template == 'valuedescription' or self.template == 'template:valuedescription':
                    self.type_from_title = 'Tag'
                elif self.template == 'relationdescription' or self.template == 'template:relationdescription':
                    self.type_from_title = 'Relation'
                else:
                    return
            if not self.type_from_title:
                pass

            if 'lang' in self.result and self.lang != self.result['lang']:
                self.print(f'Title language {self.lang} does not match parameter lang={self.result["lang"]}')
                if self.lang == 'en':
                    self.lang = self.result['lang']
            return {
                'type': self.type_from_title,
                'str_id': self.id_extractor(),
                'lang': self.lang,
                'ns': self.ns,
                'full_title': self.title,
                'template': self.template,
                'params': self.result,
            }

    def parse_template_param(self, tkey, tval):
        if tkey in templ_param_map:
            tkey = templ_param_map[tkey]
        if tval.startswith('*'):
            tval = tval[1:].strip()

        if tkey in ['key', 'value', 'oldkey', 'oldvalue', 'newtext', 'type', 'label', 'nativekey', 'nativevalue',
                    'group', 'groups', 'category', 'description', 'osmcarto-rendering-size', 'image caption',
                    'website', 'displayname', 'proposal']:
            return tkey, tval
        elif tkey == 'lang':
            tval = tval.lower()
            if tval == 'pt-br':
                tval = 'pt'
            return tkey, tval
        elif tkey == 'wikidata':
            if re_wikidata.match(tval):
                return tkey, tval
            self.print(f'Bad wikidata {tval}')
        elif tkey == 'status':
            return tkey, tval.lower()
        elif tkey in ['onnode', 'onarea', 'onway', 'onrelation', 'onclosedway', 'onchangeset']:
            tval = tval.lower()
            if tval in ['yes', 'no']:
                return tkey, tval
            if tval != '?':
                self.print(f'Unrecognized {tkey}={tval}')
        elif tkey == 'statuslink':
            if tval.startswith('[[') and tval.endswith(']]'):
                tval = (tval[2:-2].split('|')[0]).strip()
            if tval:
                try:
                    return tkey, pb.Page(self.pwb_site, tval).full_url()
                except pb.exceptions.InvalidTitle as err:
                    self.print(f'Unparsable {tkey}={tval}')
        elif tkey in ['image', 'osmcarto-rendering']:
            if 'osm element key.svg' in tval.lower():
                self.print(f'image="{tval}" is not a valid image')
            else:
                try:
                    return tkey, self.image_cache.parse_image_title(tval)
                except:
                    self.print(f'image="{tval}" cannot be processed')
        elif tkey in ['combination', 'implies', 'seealso', 'requires']:
            tags = self.parse_combinations(tkey, tval)
            if len(tags) > 0:
                return [(tkey, tags), (tkey + '!text', tval)]
            self.info(f'No tags found in {tkey} -- {tval}')
        elif tkey in 'members':
            members = self.parse_members(tval)
            if len(members) > 0:
                return [('members', members), (tkey + '!text', tval)]
            self.info(f'No items found in {tkey} -- {tval}')
        elif tkey in ['languagelinks', 'image:desc', 'image_caption', 'float', 'debug', 'dir', 'rtl']:
            pass  # We know them, but they are not very useful at this point
        else:
            self.info(f'Unknown "{tkey}={tval}"')
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
                self.info(f'Parsed link in {tkey} is unrecognized: {typ}:{lnk} | {freetext}')
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
                        vals['value'] = params['1']
                    elif len(params.keys()) == 0:
                        vals['value'] = ''
                    else:
                        self.print(f"Unknown value param pattern in '{line}'")
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
                        self.print(f"Unknown value param pattern in '{line}'")
                else:
                    self.info(f"Unknown template {name} in '{line}'")
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
                        line2 = line.replace('<code>', '').replace('</code>', '')
                        m = re.match(r'^.* [-–] ([()A-Za-z:_0-9]+)($| .*$)', line2)
                        if m:
                            vals['value'] = m[1]
                        elif re.match(r'^.* - \((prázná|prázdná|空|prázdné)\)$', line2):
                            vals['value'] = ''
                        else:
                            self.info(f"Value not found in '{line}'")
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
                self.print(f'Bad Tag value "{prefix}:{name}" (unknown prefix)')
                return
        if name not in ['tag', 'key', 'tagkey', 'tagvalue']:
            if allow_key_only and name != 'english':
                self.info(f'Bad Tag value "{name}"')
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
                    self.info(f'Bad Tag value {value}')
            if not goodValue.match(key): continue
            yield key, value

    def id_extractor(self):
        item = self.result
        item_key = item['key'] if 'key' in item else item['oldkey'] if 'oldkey' in item else False
        item_id: Union[bool, str] = False

        if self.type_from_title == 'Relation':
            return item['type']

        if item_key:
            item_id = item_key
            item_value = item['value'] if 'value' in item else item['oldvalue'] if 'oldvalue' in item else False
            if item_value and self.type_from_title == 'Tag':
                item_id += '=' + item_value

        if self.id_from_title and item_id and item_id != self.id_from_title:
            if sitelink_normalizer(item_id) != sitelink_normalizer(self.id_from_title):
                self.print(f"Item keys don't match:   {item_id:30} { self.id_from_title :30} in {self.title}")
                return False
            return item_id

        return item_id if item_id else self.id_from_title if self.id_from_title else False

    def print(self, msg):
        self.messages.append(msg)

    def info(self, msg):
        if self.print_info:
            self.messages.append(msg)

    def print_messages(self):
        if self.messages:
            print('  ' + '\n  '.join(self.messages))
            # self.messages = []
