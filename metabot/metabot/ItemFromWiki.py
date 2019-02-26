from typing import List, Dict

import re
from collections import defaultdict

from pywikiapi import AttrDict

from .Properties import P_IMAGE_OSM, P_IMAGE, P_GROUP, P_STATUS, Property, P_INSTANCE_OF, \
    P_KEY_ID, P_TAG_ID, P_TAG_KEY, P_LIMIT_TO, ClaimValue, P_USE_ON_NODES, P_USE_ON_WAYS, P_USE_ON_AREAS, \
    P_USE_ON_RELATIONS, P_USE_ON_CHANGESETS, P_WIKIDATA_CONCEPT, P_REL_TAG, P_REL_ID, P_ROLE_ID, P_REL_FOR_ROLE, \
    P_REGEX, P_WIKI_PAGES
from .consts import reLanguagesClause, Q_TAG, Q_KEY, Q_IS_ALLOWED, Q_IS_PROHIBITED, Q_RELATION, Q_REL_MEMBER_ROLE
from .utils import list_to_dict_of_lists, reTag_repl, remove_wikimarkup, lang_pick, to_item_sitelink, id_to_sitelink

reTag = re.compile(
    r'{{(?:(?:template:)?' + reLanguagesClause + r':)?' +
    r'(?:tag|key)' +
    r'(?:\|[kv]l=' + reLanguagesClause + r')?' +
    r'(?:\|([a-z0-9_:]+))' +
    r'(?:\|[kv]l=' + reLanguagesClause + r')?' +
    r'(?:\|([a-z0-9_:]+))?' +
    r'(?:\|[kv]l=' + reLanguagesClause + r')?' +
    r'(?:\|([a-z0-9_:]+))?' +
    r'(?:\|[kv]l=' + reLanguagesClause + r')?' +
    r'\}\}',
    re.IGNORECASE)

reWikiLink = re.compile(r'\[\[(?:[^|\]\[]*\|)?([^|\]\[]*)\]\]')

deprecated_msg = {
    'cs': 'Použití této značky se nedoporučuje. Použijte radši $1.',
    'de': 'Dieses Tag ist überholt, verwende stattdessen $1.',
    'en': 'Using this tag is discouraged, use $1 instead.',
    'es': 'El uso de esta etiqueta está desaconsejado, usa $1 en su lugar.',
    'fr': 'L’utilisation de cet attribut est découragée, utilisez plutôt $1.',
    'ja': 'このタグの使用は避けてください。代わりに $1 を使用してください。',
}

on_elem_map = {
    'onnode': P_USE_ON_NODES,
    'onway': P_USE_ON_WAYS,
    'onarea': P_USE_ON_AREAS,
    'onrelation': P_USE_ON_RELATIONS,
    'onchangeset': P_USE_ON_CHANGESETS,
}


class ItemFromWiki:
    claim_per_lang: Dict[Property, Dict[str, List[str]]]
    claims: Dict[Property, List[ClaimValue]]

    def __init__(self, caches, strid, wiki_pages, create_new) -> None:
        self.ok = True
        self.caches = caches
        self.wiki_pages = wiki_pages
        self.messages = []
        self.claim_per_lang = defaultdict(dict)
        self.has_unknown_group = False
        self.typ = strid[0]
        self.strid = strid[1]
        self.claims = defaultdict(list)

        self.sitelink = id_to_sitelink(self.typ, self.strid)
        if self.typ == 'Relation':
            # Relation
            self.claims[P_INSTANCE_OF].append(ClaimValue(Q_RELATION))
            self.claims[P_REL_ID].append(ClaimValue(self.strid))
            type_strid = ('Tag', 'type=' + self.strid)
            tag_id = self.caches.itemKeysByStrid.get_strid(type_strid)
            if not tag_id:
                create_new(type_strid)
                tag_id = self.caches.itemKeysByStrid.get_strid(type_strid)
            self.claims[P_REL_TAG].append(ClaimValue(tag_id))
            label = self.strid + ' relation'
            self.strid = self.sitelink
        elif self.typ == 'Role':
            # Relation role
            is_number = False
            if self.strid.endswith('<number>'):
                self.strid = self.strid[:-len('<number>')]
                is_number = True
                print('number!')
            self.claims[P_INSTANCE_OF].append(ClaimValue(Q_REL_MEMBER_ROLE))
            self.claims[P_ROLE_ID].append(ClaimValue(self.strid))
            rel_name = self.strid[:self.strid.find('=')]
            role_name = self.strid[self.strid.find('=')+1:] or '<blank>'
            rel_sl = id_to_sitelink('Relation', rel_name)
            if rel_sl not in self.caches.itemQidBySitelink.get():
                raise ValueError(f"{rel_sl} does not exist")
            self.claims[P_REL_FOR_ROLE].append(ClaimValue(self.caches.itemQidBySitelink.get()[rel_sl]))
            if is_number:
                self.claims[P_REGEX].append(ClaimValue(re.escape(self.strid[self.strid.find('=') + 1:]) + r'[0-9]+'))
                role_name += '<number>'
            label = f'{rel_name} relation {role_name} role'
        elif self.typ == 'Tag':
            # TAG
            if '=' not in self.strid:
                 raise ValueError(f'{self.strid} does not contain "="')
            self.claims[P_INSTANCE_OF].append(ClaimValue(Q_TAG))
            self.claims[P_TAG_ID].append(ClaimValue(self.strid))
            key = ('Key', self.strid.split('=')[0])
            key_id = self.caches.itemKeysByStrid.get_strid(key)
            if key_id:
                self.claims[P_TAG_KEY].append(ClaimValue(key_id))
            label = self.strid
        elif self.typ == 'Key':
            # KEY
            if '=' in self.strid:
                raise ValueError(f'{self.strid} contains "="')
            self.claims[P_INSTANCE_OF].append(ClaimValue(Q_KEY))
            self.claims[P_KEY_ID].append(ClaimValue(self.strid))
            label = self.strid
        else:
            raise ValueError(f'Unknown type {self.typ} for {self.strid}')

        self.header = {
            'labels': {'en': label},
            'descriptions': {},
            'sitelinks': to_item_sitelink(self.sitelink),
        }

        if '*' in self.strid:
            self.print(f'WARNING: {self.strid} has a wildcard')

        if self.wiki_pages:
            new_wiki_pages = []
            for lng, vv in list_to_dict_of_lists(self.wiki_pages, lambda v: v.lang).items():
                if len(vv) > 1 and len(set([v.ns for v in vv])) == 1:
                    vv = [v for v in vv if 'Key:' in v.full_title or 'Tag:' in v.full_title or 'Relation:' in v.full_title]
                if len(vv) > 1:
                    vv = [v for v in vv if 'Proposed features/' not in v.full_title]
                if len(vv) > 1:
                    s = set([v.template for v in vv])
                    if s == {'deprecated', 'valuedescription'} or s == {'deprecated', 'keydescription'}:
                        vv = [v for v in vv if v.template != 'deprecated']
                    else:
                        self.print(f'Multiple descriptions found {lng} {self.strid}: '
                                   f'{", ".join([v.full_title for v in vv])}')
                        self.ok = False
                        break
                if len(vv) > 0:
                    new_wiki_pages.append(vv[0])
            self.wiki_pages = new_wiki_pages

            if self.ok:
                self.merge_wiki_languages()
                # if P_IMAGE in self.claim_per_lang and P_IMAGE_OSM in self.claim_per_lang:
                #     del self.claim_per_lang[P_IMAGE_OSM]
                for wp in self.wiki_pages:
                    self.claims[P_WIKI_PAGES].append(ClaimValue({'language': wp.lang, 'text': wp.full_title}))

        if self.claim_per_lang:
            for prop, claim in self.claim_per_lang.items():
                self.merge_claim(claim, prop)

        self.update_image_claims()

        self.ok = self.ok and (self.header or self.claim_per_lang)

    def print(self, msg):
        self.messages.append(msg)

    def print_messages(self):
        if self.messages:
            print(f'---- Merging wiki pages for {self.strid}')
            for msg in self.messages:
                print(msg)

    def merge_wiki_languages(self):
        for page in self.wiki_pages:
            params = page.params
            if type(params) == dict:
                params = AttrDict(params)

            if 'oldkey' in params:
                # deprecation support
                newtext = params.newtext if 'newtext' in params else ''
                params.description = lang_pick(deprecated_msg, page.lang).replace('$1', newtext)
                params.image = 'Ambox warning pn.svg'
                params.status = 'Deprecated'

            self.do_label(page.lang, params)
            self.do_description(page.lang, params)
            self.do_used_on(page.lang, params)
            self.do_images(page.lang, params)
            self.do_groups(page.lang, params)
            self.do_status(page.lang, params)
            self.do_wikidata(page.lang, params)

    def do_label(self, lng, params):
        if 'nativekey' not in params:
            return
        label = params.nativekey
        if 'nativevalue' in params:
            label += '=' + params.nativevalue
        if len(label) > 250:
            self.print(f'Label {self.strid} {lng} is longer than 250! {label}')
        self.header['labels'][lng] = label[:250].strip()

    def do_description(self, lng, params):
        if 'description' not in params:
            return
        desc = params.description
        if desc == '???':
            return
        if "[[" in desc:
            desc = reWikiLink.sub(r'\1', desc)
            if "[[" in desc:
                self.print(f"Unable to fix description {params.description}")
        desc = desc.replace('\n', ' ')
        # if '{{' in desc:
        #     pass
        desc = reTag.sub(reTag_repl, desc)
        desc = remove_wikimarkup(desc)
        if len(desc) > 250:
            self.print(f'Description {self.strid} {lng} is longer than 250! {desc}')
        self.header['descriptions'][lng] = desc[:250].strip()

    def do_status(self, lng, params):
        if 'status' not in params:
            return
        statuses = self.caches.statusesByName.get()
        st = params.status.lower()
        if st in statuses:
            self.claim_per_lang[P_STATUS][lng] = statuses[st]
        elif st not in ['undefined', 'unspecified', 'unknown']:
            self.print(f"Unknown status {params.status} for {self.strid} ({lng})")

    def do_groups(self, lng, params):
        if 'group' not in params:
            return
        groups = self.caches.groupsByName.get()
        grp = params.group.lower()
        if grp in groups:
            self.claim_per_lang[P_GROUP][lng] = groups[grp]
        else:
            # self.print(f"Unknown group {params.group} for {self.strid} ({lng})")
            self.has_unknown_group = True

    def do_images(self, lng, params):
        if 'image' not in params or not params.image:
            return
        self.claim_per_lang[P_IMAGE][lng] = params.image

    def update_image_claims(self):
        if P_IMAGE in self.claims:
            for img in list(self.claims[P_IMAGE]):
                if img.value.startswith('osm:'):
                    self.claims[P_IMAGE].remove(img)
                    self.claims[P_IMAGE_OSM].append(ClaimValue(img.value[len('osm:'):], img.qualifiers, img.rank))
            if len(self.claims[P_IMAGE]) == 0:
                del self.claims[P_IMAGE]


    def do_wikidata(self, lng, params):
        if 'wikidata' not in params or not params.wikidata:
            return
        self.claim_per_lang[P_WIKIDATA_CONCEPT][lng] = params.wikidata

    def do_used_on(self, lng, params):
        for key, prop in on_elem_map.items():
            if key in params:
                if params[key] == 'yes':
                    self.claim_per_lang[prop][lng] = Q_IS_ALLOWED
                elif params[key] == 'no':
                    self.claim_per_lang[prop][lng] = Q_IS_PROHIBITED
                else:
                    self.print(f'unknown {key} = {params[key]} for {self.strid}')

    def merge_claim(self, new_claims_all, prop):
        set_to_lang = list_to_dict_of_lists(
            [(k, v) for k, v in new_claims_all.items()],
            lambda v: v[1], lambda v: v[0])

        if len(set_to_lang) == 1:
            (new_claim,) = set_to_lang.keys()
            new_claims = [ClaimValue(new_claim, rank='preferred')]
        else:
            # status = f"  Claim mismatch: {prop}:"
            # for q, lngs in set_to_lang.items():
            #     status += f"  ({','.join(lngs)}) = { self.caches.qitem(q) }"
            # self.print(status)
            new_claims = {}
            default_value = None
            if 'en' in new_claims_all:
                default_value = new_claims_all['en']
                new_claims[default_value] = ClaimValue(default_value, rank='preferred')
            regions = self.caches.regionByLangCode.get()

            for lng in new_claims_all:
                if lng == 'en':
                    continue
                if lng not in regions:
                    self.print(f'Region language {lng} not found in the region codes')
                value = new_claims_all[lng]
                if value != default_value:
                    if value not in new_claims:
                        new_claims[value] = ClaimValue(value, {P_LIMIT_TO: set()})
                    new_claims[value].qualifiers[P_LIMIT_TO].add(regions[lng].id)

            new_claims = list(new_claims.values())

        self.claims[prop] = new_claims
