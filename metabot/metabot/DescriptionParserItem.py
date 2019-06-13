from typing import Union

import re

from pywikibot import textlib

from .utils import remove_wikimarkup, re_wikidata, re_tag_link, goodValue, sitelink_normalizer, \
    parse_wiki_page_title, parse_members
from .consts import languages
import pywikibot as pb

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

# Lower-cased images that we should never add
bad_images = ['osm element key.svg', 'mf key.svg', 'none yet.jpg', 'fi none yet.jpg']


class ItemParser:

    def __init__(self, pwb_site: pb.Site, ns, title, template, template_params,
                 print_info=False):
        self.print_info = print_info
        self.pwb_site = pwb_site
        self.ns = ns
        self.title = title
        self.template = template.lower()
        self.template_params = template_params
        self.result = {}
        self.messages = []

        self.type_from_title, self.lang, self.id_from_title, has_suspect_lang = parse_wiki_page_title(ns, title)
        if has_suspect_lang:
            self.print(f'Suspected language code in {title}')

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
                    'group', 'groups', 'category', 'description', 'osmcarto-rendering-size', 'image_caption',
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
                except pb.exceptions.InvalidTitle:
                    self.print(f'Unparsable {tkey}={tval}')
        elif tkey in ['image', 'osmcarto-rendering']:
            tval2 = tval.lower()
            if [v for v in bad_images if v in tval2]:
                self.print(f'image="{tval}" is not a valid image')
            else:
                try:
                    if tval.startswith('Image:') or tval.startswith('image:'):
                        tval = 'File:' + tval[len('Image:'):]
                    elif tval.startswith('file:'):
                        tval = 'File:' + tval[len('file:'):]
                    return tkey, pb.FilePage(self.pwb_site, tval).titleWithoutNamespace()
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
        elif tkey in ['languagelinks', 'float', 'debug', 'dir', 'rtl']:
            pass  # We know them, but they are not very useful at this point
        else:
            self.info(f'Unknown "{tkey}={tval}"')
        return None

    def parse_combinations(self, tkey, tval):
        items = []
        for template in textlib.extract_templates_and_params(tval, True, True):
            for k, v in self.parse_tag(template):
                if v:
                    items.append(('Tag', f'{k}={v}'))
                else:
                    items.append(('Key', k))
        # Parse free text links like [[ (Key) : (lanes) | (lanes) ]]
        for link in re_tag_link.findall(tval):
            dummy, typ, lnk, freetext = link
            typ = typ.lower()
            if typ == 'relation':
                items.append(('Relation', lnk))
            else:
                self.info(f'Parsed link in {tkey} is unrecognized: {typ}:{lnk} | {freetext}')
        return items

    def parse_members(self, tval):
        members = []
        for line in re.split(r'(^ *\*|\n *\*)', tval.strip()):
            vals = parse_members(line, self.print, self.info)
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
        if ':' in name:
            prefix, name = name.split(':', 1)
            if prefix not in languages:
                self.print(f'Bad Tag value "{prefix}:{name}" (unknown prefix)')
                return
        if name not in ['tag', 'key', 'tagkey', 'tagvalue']:
            self.info(f'Bad tag value "{name}"')
            return
        key = ''
        if '1' in params:
            key = params['1'].strip()
            if 'subkey' in params: key += ':' + params['subkey'].strip()
            if ':' in params: key += ':' + params[':'].strip()
            if '::' in params: key += ':' + params['::'].strip()
            if ':::' in params: key += ':' + params[':::'].strip()
        value = ''
        if '2' in params:
            value = params['2'].strip()
        if value == '' and '3' in params:
            value2 = remove_wikimarkup(params['3'].strip())
            if value2 == 'yes':
                value = value2

        for val in re.split(r'[/;]+', value):
            val = val.strip()
            if not goodValue.match(val):
                if val not in ['']:
                    self.info(f'Bad Tag val {val}')
            if goodValue.match(key):
                yield key, val

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
                self.print(f"Item keys don't match:   {item_id:30} {self.id_from_title :30} in {self.title}")
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
