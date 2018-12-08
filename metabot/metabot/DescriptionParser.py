from typing import Union

import pywikibot as pb
import re

from pywikibot import textlib

from . import ResolvedImageFiles
from .utils import getpt, ParsedTitle
from .consts import reLanguagesClause, LANG_NS, ignoreLangSuspects, languages

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
re_wikidata = re.compile(r'^Q[1-9][0-9]{0,11}$')
# links like [[Key:...|...]], with the optional language prefix??//
re_tag_link = re.compile(r'\[\[(?:(' + reLanguagesClause + r'):)?(Key|Tag|Relation):([^|\]]+)(?:\|([^|\]]+))?\]\]',
                         re.IGNORECASE)

re_lang_template = re.compile(r'^(?:' + reLanguagesClause + r':)?(?:Template:)?(.*)$', re.IGNORECASE)
goodValue = re.compile(r'^[a-zA-Z0-9]+([-: _.][a-zA-Z0-9]+)*:?$')

reBoldItalic = re.compile(r"'''''(.*)'''''")
reBold = re.compile(r"'''(.*)'''")
reItalic = re.compile(r"''(.*)''")


def remove_wikimarkup(text):
    if "''" in text:
        return reItalic.sub(
            r'\1', reBold.sub(
                r'\1', reBoldItalic.sub(
                    r'\1', text)))
    return text


def sitelink_normalizer(strid):
    return strid.replace('_', ' ').strip()


def id_extractor(item, messages=None):
    pt = getpt(item)
    item_key = item['key'] if 'key' in item else item['oldkey'] if 'oldkey' in item else False
    item_value = item['value'] if 'value' in item else item['oldvalue'] if 'oldvalue' in item else False
    item_id: Union[bool, str] = False
    if item_key:
        item_id = item_key
        if item_value and pt.type == 'Tag':
            item_id += '=' + item_value
    if pt.str_id and item_id and item_id != pt.str_id:
        if sitelink_normalizer(item_id) != sitelink_normalizer(pt.str_id):
            if messages:
                messages.append(f"Item keys don't match:   {item_id:30} { pt.str_id :30} in {pt.full_title}")
            return False
        return item_id
    return pt.str_id if pt.str_id else item_id if item_id else False


class DescriptionParser:

    def __init__(self, image_cache: ResolvedImageFiles, pwb_site: pb.Site):
        self.image_cache = image_cache
        self.pwb_site = pwb_site

    def parse(self, ns, title, template, template_params):
        item = ItemParser(self.image_cache, self.pwb_site, ns, title, template, template_params)
        item.parse()
        if item.messages:
            print(f'#### {title}\n  ' + '\n  '.join(item.messages))
        return item.result


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

        pt = ParsedTitle(page_type, page_title, lng, self.ns, self.title)

        if self.result:
            self.result['_parsed_title'] = pt
            strid = id_extractor(self.result, self.messages)
            if strid:
                if strid != pt.str_id:
                    self.result['_parsed_title'] = ParsedTitle(page_type, strid, lng, self.ns, self.title)
            else:
                self.messages.append(f'Unable to extract ID from { page_title }')

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
            if not re_wikidata.match(tval):
                self.messages.append(f'Bad wikidata {tval}')
            else:
                return tkey, tval
        elif tkey == 'status':
            return tkey, tval.lower()
        elif tkey in ['onnode', 'onarea', 'onway', 'onrelation', 'onclosedway', 'onchangeset']:
            tval = tval.lower()
            if tval not in ['yes', 'no']:
                if tval != '?':
                    self.messages.append(f'Unrecognized {tkey}={tval}')
            else:
                return tkey, tval
        elif tkey == 'statuslink':
            if tval.startswith('[[') and tval.endswith(']]'):
                tval = (tval[2:-2].split('|')[0]).strip()
            if tval:
                try:
                    return tkey, pb.Page(self.pwb_site, tval).full_url()
                except pb.exceptions.InvalidTitle as err:
                    self.messages.append(f'Unparsable {tkey}={tval}')
        elif tkey in ['image', 'osmcarto-rendering']:
            image = self.parse_image_title(tval)
            if image:
                return tkey, image
        elif tkey in ['combination', 'implies', 'seealso', 'requires']:
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
            if len(tags) == 0:
                self.messages.append(f'No tags found in {tkey} -- {tval}')
            else:
                return [(tkey, tags), (tkey + '!text', tval)]
        elif tkey in 'members':
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
            if len(members) == 0:
                self.messages.append(f'No items found in {tkey} -- {tval}')
            else:
                return [('members', members), (tkey + '!text', tval)]
        elif tkey in ['languagelinks', 'image:desc', 'image_caption', 'float', 'debug', 'dir', 'rtl']:
            pass  # We know them, but they are not very useful at this point
        else:
            self.messages.append(f'Unknown "{tkey}={tval}"')
        return None

    def parse_image_title(self, file_title):
        if file_title.startswith('Image:') or file_title.startswith('image:'):
            file_title = 'File:' + file_title[len('Image:'):]
        elif file_title.startswith('file:'):
            file_title = 'File:' + file_title[len('file:'):]
        image_file_cache = self.image_cache.get()
        if file_title in image_file_cache:
            return image_file_cache[file_title]
        try:
            img = pb.FilePage(self.pwb_site, file_title)
            if not img.fileIsShared():
                img = 'osm:' + img.titleWithoutNamespace()
            else:
                img = img.titleWithoutNamespace()
        except (pb.exceptions.NoPage, pb.exceptions.InvalidTitle):
            self.messages.append(f'image="{file_title}" cannot be processed')
            img = None

        self.image_cache.append(file_title, img)
        return img

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
