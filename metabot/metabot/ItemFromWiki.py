import re
from collections import defaultdict

from pywikiapi import AttrDict

from .Properties import P_USED_ON, P_NOT_USED_ON, P_OSM_IMAGE, P_IMAGE, P_GROUP, P_STATUS, Property, P_INSTANCE_OF, \
    P_KEY_ID, P_TAG_ID, P_TAG_KEY
from .consts import elements, reLanguagesClause, Q_TAG, Q_KEY
from .utils import list_to_dict_of_lists, reTag_repl, remove_wikimarkup, lang_pick, sitelink_normalizer_tag, \
    sitelink_normalizer_key

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

deprdescr = {
    'cs': 'Použití této značky se nedoporučuje. Použijte radši $1.',
    'de': 'Dieses Tag ist überholt, verwende stattdessen $1.',
    'en': 'Using this tag is discouraged, use $1 instead.',
    'es': 'El uso de esta etiqueta está desaconsejado, usa $1 en su lugar.',
    'fr': 'L’utilisation de cet attribut est découragée, utilisez plutôt $1.',
    'ja': 'このタグの使用は避けてください。代わりに $1 を使用してください。',
}


class ItemFromWiki:

    def __init__(self, caches, strid, wiki_pages) -> None:
        self.ok = False
        self.caches = caches
        self.wiki_pages = wiki_pages
        self.messages = []
        self.claim_per_lang = defaultdict(dict)
        self.has_unknown_group = False
        self.strid = strid
        self.claims = defaultdict(list)

        if '=' in self.strid:
            # TAG
            self.sitelink = sitelink_normalizer_tag(strid)
            self.claims[P_INSTANCE_OF.id].append(Q_TAG)
            self.claims[P_TAG_ID.id].append(strid)
            key = strid.split('=')[0]
            key_id = self.caches.itemKeysByStrid.get_strid(key)
            if key_id:
                self.claims[P_TAG_KEY.id].append(key_id)
        else:
            # KEY
            self.sitelink = sitelink_normalizer_key(strid)
            self.claims[P_INSTANCE_OF.id].append(Q_KEY)
            self.claims[P_KEY_ID.id].append(strid)

        self.editData = {
            'labels': {'en': strid},
            'descriptions': {},
            'sitelinks': [{'site': 'wiki', 'title': self.sitelink}],
        }

    def print(self, msg):
        self.messages.append(msg)

    def print_messages(self):
        if self.messages:
            print(f'---- Merging wiki pages for {self.strid}')
            for msg in self.messages:
                print(msg)

    def run(self):
        if '*' in self.strid:
            self.print(f'WARNING: {self.strid} has a wildcard')

        if self.wiki_pages:
            self.merge_wiki_languages()
            if 'en' not in self.editData['labels']:
                self.editData['labels']['en'] = self.strid
            if P_IMAGE.id in self.claim_per_lang and P_OSM_IMAGE.id in self.claim_per_lang:
                del self.claim_per_lang[P_OSM_IMAGE.id]

        if self.claim_per_lang:
            for prop, claim in self.claim_per_lang.items():
                self.merge_claim(claim, Property.ALL[prop])

        self.ok = self.editData or self.claim_per_lang

    def merge_wiki_languages(self):
        for lng, vv in list_to_dict_of_lists(self.wiki_pages, lambda v: v.lang).items():
            if len(vv) > 1 and len(set([v.ns for v in vv])) == 1:
                vv = [v for v in vv if 'Key:' in v.full_title or 'Tag:' in v.full_title]
            if len(vv) > 1:
                s = set([v.template for v in vv])
                if s == {'Deprecated', 'ValueDescription'} or s == {'Deprecated', 'KeyDescription'}:
                    params = vv[0].params if vv[1].template == 'Deprecated' else vv[1].params
                else:
                    self.print(
                        f'Multiple descriptions found {lng} {self.strid}: {", ".join([v.full_title for v in vv])}')
                    break
            else:
                params = vv[0].params

            if type(params) == dict:
                params = AttrDict(params)

            if 'oldkey' in params:
                # deprecation support
                newtext = params.newtext if 'newtext' in params else ''
                params.description = lang_pick(deprdescr, lng).replace('$1', newtext)
                params.image = 'Ambox warning pn.svg'
                params.status = 'Deprecated'

            self.do_label(lng, params)
            self.do_description(lng, params)
            self.do_used_on(lng, params)
            self.do_images(lng, params)
            self.do_groups(lng, params)
            self.do_status(lng, params)

    def do_label(self, lng, params):
        if 'nativekey' not in params:
            return
        label = params.nativekey
        if 'nativevalue' in params:
            label += '=' + params.nativevalue
        if len(label) > 250:
            self.print(f'Label is longer than 250! {label}')
        self.editData['labels'][lng] = label[:250].strip()

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
            self.print(f'Description is longer than 250! {desc}')
        self.editData['descriptions'][lng] = desc[:250].strip()

    def do_status(self, lng, params):
        if 'status' not in params: return
        statuses = self.caches.statusesByName.get()
        st = params.status.lower()
        if st in statuses:
            self.claim_per_lang[P_STATUS.id][lng] = statuses[st]
        elif st not in ['undefined', 'unspecified', 'unknown']:
            self.print(f"Unknown status {params.status} for {self.strid} ({lng})")

    def do_groups(self, lng, params):
        if 'group' not in params: return
        groups = self.caches.groupsByName.get()
        grp = params.group.lower()
        if grp in groups:
            self.claim_per_lang[P_GROUP.id][lng] = groups[grp]
        else:
            # self.print(f"Unknown group {params.group} for {self.strid} ({lng})")
            self.has_unknown_group = True

    def do_images(self, lng, params):
        if 'image' not in params or not params.image: return
        if params.image.startswith('osm:'):
            self.claim_per_lang[P_OSM_IMAGE.id][lng] = params.image[len('osm:'):]
        else:
            self.claim_per_lang[P_IMAGE.id][lng] = params.image

    def do_used_on(self, lng, params):
        # Used/Not used on
        usedon = []
        notusedon = []
        for v in ['onnode', 'onarea', 'onway', 'onrelation', 'onclosedway', 'onchangeset']:
            if v in params:
                vv = elements[v[2:]]
                if params[v] == 'yes':
                    usedon.append(vv)
                elif params[v] == 'no':
                    notusedon.append(vv)
                else:
                    self.print(f'unknown usedon type {params[v]} for {self.strid}')
        usedon.sort()
        notusedon.sort()
        if usedon: self.claim_per_lang[P_USED_ON.id][lng] = usedon
        if notusedon: self.claim_per_lang[P_NOT_USED_ON.id][lng] = notusedon

    def merge_claim(self, new_claims_all, prop):
        if not prop.allow_multiple:
            new_claims_all = {k: [v] for k, v in new_claims_all.items()}
        new_claim = new_claims_all['en'] if 'en' in new_claims_all else False
        set_to_lang = list_to_dict_of_lists(
            [(k, tuple(v)) for k, v in new_claims_all.items()],
            lambda v: v[1], lambda v: v[0])
        if len(set_to_lang) == 1:
            new_claim = list([v for v in set_to_lang.keys()][0])
        else:
            status = f"  Claim mismatch: {prop}:"
            for q, lngs in set_to_lang.items():
                status += f"  ({','.join(lngs)}) = { self.caches.qitem(q) }"
            self.print(status)

        if not new_claim:
            self.print('  Skipping...')
        else:
            self.claims[prop.id] = new_claim
