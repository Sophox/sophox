import re
from collections import defaultdict

import pywikibot as pb
from pywikiapi import AttrDict

from .Properties import P_USED_ON, P_NOT_USED_ON, P_OSM_IMAGE, P_IMAGE, P_GROUP, P_STATUS, P_INSTANCE_OF, \
    P_KEY_ID, P_TAG_ID, P_TAG_KEY, Property, P_KEY_TYPE
from .consts import elements, Q_KEY, Q_TAG, Q_ENUM_KEY_TYPE, reLanguagesClause
from .utils import get_sitelink, list_to_dict_of_lists, reTag_repl, remove_wikimarkup, sitelink_normalizer_key, \
    sitelink_normalizer_tag

reTag = re.compile(
    r'\{\{(?:(?:template:)?' + reLanguagesClause + r':)?' +
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

deprdescr = {
    'cs': 'Použití této značky se nedoporučuje. Použijte radši $1.',
    'de': 'Dieses Tag ist überholt, verwende stattdessen $1.',
    'en': 'Using this tag is discouraged, use $1 instead.',
    'es': 'El uso de esta etiqueta está desaconsejado, usa $1 en su lugar.',
    'fr': 'L’utilisation de cet attribut est découragée, utilisez plutôt $1.',
    'ja': 'このタグの使用は避けてください。代わりに $1 を使用してください。',
}


class ProcessorItem:

    def __init__(self, proc, item) -> None:
        self.proc = proc
        self.new_claims = defaultdict(dict)

        if type(item) is str and item in self.proc.all_items_by_strid:
            item = self.proc.all_items_by_strid[item]

        if type(item) is str:
            self.strid = item
            item = None
            if ' ' in self.strid:
                strid = self.strid.replace(' ', '_')
                if strid in self.proc.all_items_by_strid:
                    item = self.proc.all_items_by_strid[strid]
                    found = ', '.join(
                        [v.full_title for v in
                         (self.proc.wiki_items_by_id[self.strid] if self.strid in self.proc.wiki_items_by_id else [])])
                    print(
                        f"ID {self.strid} could be matched with {strid}, "
                        f"switching to existing mode{', found in ' + found if found else ''}")
            self.qid = None

        self.new_labels = {}
        self.new_descrs = {}
        self.has_unknown_group = False

        if not item:
            self.item = AttrDict()
            self.item.labels = {}
            self.item.descriptions = {}
        else:
            self.item = item
            self.strid = P_KEY_ID.get_claim_value(self.item)
            if not self.strid:
                self.strid = P_TAG_ID.get_claim_value(self.item)
            self.qid = self.item.id

    def run(self):
        if not self.strid:
            return
        if '*' in self.strid:
            print(f'WARNING: {self.strid} has a wildcard')
            # return

        if self.qid:
            self.validate_data_item()

        if self.strid in self.proc.wiki_items_by_id:
            self.process_wiki_pages()

        if self.qid:
            self.apply_all_claims()

    def process_wiki_pages(self):
        self.merge_wiki_items()
        if (not self.qid and 'en' not in self.new_labels) or (self.get_localized_value('labels', 'en') != self.strid):
            self.new_labels['en'] = self.strid
        if P_IMAGE.id in self.new_claims and P_OSM_IMAGE.id in self.new_claims:
            del self.new_claims[P_OSM_IMAGE.id]
        if self.has_unknown_group:
            status = ''
            old_group = P_GROUP.get_claim_value(self.item)
            if old_group:
                status += ' Currently set to ' + self.qitem(old_group)
            new_groups = self.new_claims[P_GROUP.id] if P_GROUP.id in self.new_claims else None
            if new_groups and {old_group} != set(new_groups):
                status += ' Trying to set to: ' + self.qitem(set(new_groups.values()))
            if status:
                print(status)
        if self.new_labels or self.new_descrs:
            status = f"{self.strid} - {self.qitem(self.qid)}"
            other_editors = self.get_nonbot_editors(self.qid)
            if not other_editors:
                status = ('Updating ' if self.qid else 'Creating ') + status
            else:
                status = f'Cannot update {status} because it was edited by {other_editors}'
            print('***************** ' + status)

            def lbls_to_status(name, old, new):
                results = []
                for k, v in new.items():
                    res = f"{k}="
                    prefixlen = len(res)
                    if old and k in old:
                        res += f"'{old[k]['value']}' -> "
                    if len(res) > 30:
                        res += '\n' + (' ' * (prefixlen + 2))
                    res += f"'{v}'"
                    results.append(res)

                return (name +
                        (': ' if len(results) == 1 else ':\n    ') +
                        '\n    '.join(results))

            if self.new_labels:
                print(lbls_to_status('  labels', self.item.labels, self.new_labels))
            if self.new_descrs:
                print(lbls_to_status('  descrs', self.item.descriptions, self.new_descrs))

            if not other_editors:
                if self.qid:
                    summary = 'Updating'
                else:
                    pbitem = pb.ItemPage(self.proc.pb_site)
                    summary = 'Creating'
                editData = {}
                if self.new_labels:
                    summary += ' labels ' + ', '.join([f"{k}:'{v}'" for k, v in self.new_labels.items()])
                    editData['labels'] = self.new_labels
                if self.new_descrs:
                    summary += ' descriptions ' + ', '.join([f"{k}:'{v}'" for k, v in self.new_descrs.items()])
                    editData['descriptions'] = self.new_descrs

                if not self.qid:
                    pt = next(iter(self.proc.wiki_items_by_id[self.strid]))
                    if pt.type == 'Key':
                        editData['sitelinks'] = [{'site': 'wiki', 'title': sitelink_normalizer_key(self.strid)}]
                        P_INSTANCE_OF.set_claim_on_new(editData, Q_KEY)
                        P_KEY_ID.set_claim_on_new(editData, self.strid)
                    elif pt.type == 'Tag':
                        editData['sitelinks'] = [{'site': 'wiki', 'title': sitelink_normalizer_tag(self.strid)}]
                        P_INSTANCE_OF.set_claim_on_new(editData, Q_TAG)
                        P_TAG_ID.set_claim_on_new(editData, self.strid)

                        ek = self.proc.cache.itemKeysByStrid.get()
                        ks = self.strid.split('=')[0]
                        if ks in ek:
                            P_TAG_KEY.set_claim_on_new(editData, ek[ks])
                        else:
                            print(f"Unable to find item '{ks}' for '{self.strid}', not setting {P_TAG_KEY}")
                    else:
                        print(f'Unknown type {pt}, skipping')
                        self.qid = None
                        return

                    self.apply_all_claims(editData)

                    print(f'  +++ creating {self.strid}')
                    pbitem.editEntity(editData, summary=summary)

    def apply_all_claims(self, editData=None):
        for prop, claims in self.new_claims.items():
            self.apply_claims(claims, Property.ALL[prop], editData)
        self.new_claims = None

    def merge_wiki_items(self):
        for lng, vv in list_to_dict_of_lists(self.proc.wiki_items_by_id[self.strid], lambda v: v.lang).items():

            # if 'oldkey' not in vv[0]: return  #DEBUG

            if len(vv) > 1 and len(set([v.ns for v in vv])) == 1:
                vv = [v for v in vv if
                      'Key:' in v.full_title or 'Tag:' in v.full_title]
            if len(vv) > 1:
                print(f'Multiple descriptions found {lng} : {self.strid} {self.qitem(self.qid)}')
                break
            params = vv[0].params

            if 'oldkey' in params:
                # deprecation support
                params.description = (deprdescr[lng] if lng in deprdescr else deprdescr['en']).replace('$1', params[
                    'newtext'] if 'newtext' in params else '')
                params.image = 'Ambox warning pn.svg'
                params.status = 'Deprecated'

            self.update_text_val('label', lng, self.new_labels, params)
            self.do_description(lng, params)
            self.do_used_on(lng, params)
            self.do_images(lng, params)
            self.do_groups(lng, params)
            self.do_status(lng, params)

    def do_description(self, lng, params):
        if 'description' in params:
            descr = params.description
            if descr == '???':
                del params.description
            else:
                if "[[" in descr:
                    print(f"Unable to fix description {descr}")
                descr = descr.replace('\n', ' ')
                if '{{' in descr:
                    pass
                descr = reTag.sub(reTag_repl, descr)
                params.description = remove_wikimarkup(descr)
            self.update_text_val('description', lng, self.new_descrs, params)


    def do_status(self, lng, params):
        if 'status' in params:
            statuses = self.proc.cache.statusesByName.get()
            st = params.status.lower()
            if st in statuses:
                self.new_claims[P_STATUS.id][lng] = statuses[st]
            elif st not in ['undefined', 'unspecified', 'unknown']:
                print(f"Unknown status {params.status} for {self.strid} ({lng})  {self.qitem(self.qid)}")

    def do_groups(self, lng, params):
        if 'group' in params:
            groups = self.proc.cache.groupsByName.get()
            grp = params.group.lower()
            if grp in groups:
                self.new_claims[P_GROUP.id][lng] = groups[grp]
            else:
                print(f"Unknown group {params.group} for {self.strid} ({lng})  {self.qitem(self.qid)}")
                self.has_unknown_group = True

    def do_images(self, lng, params):
        if 'image' in params:
            if params.image.startswith('osm:'):
                self.new_claims[P_OSM_IMAGE.id][lng] = params.image[len('osm:'):]
            else:
                self.new_claims[P_IMAGE.id][lng] = params.image

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
                    print(f'unknown usedon type {params[v]} for {self.strid} {self.qitem(self.qid)}')
        usedon.sort()
        notusedon.sort()
        if usedon: self.new_claims[P_USED_ON.id][lng] = usedon
        if notusedon: self.new_claims[P_NOT_USED_ON.id][lng] = notusedon

    def validate_data_item(self):
        instance_of = P_INSTANCE_OF.get_claim_value(self.item)
        key_strid = P_KEY_ID.get_claim_value(self.item)
        tag_strid = P_TAG_ID.get_claim_value(self.item)
        tag_key = P_TAG_KEY.get_claim_value(self.item)
        sl = get_sitelink(self.item)
        if instance_of == Q_KEY or key_strid or (sl and sl.startswith('Key:')):
            # Must be a key
            if instance_of != Q_KEY:
                print(f"{self.qitem(self.qid)} seems to be a key, but instance_of is {instance_of}")
            if not key_strid:
                print(f"{self.qitem(self.qid)} seems to be a key, but {P_KEY_ID} is not set")
            if tag_strid:
                print(f"{self.qitem(self.qid)} seems to be a key, but {P_TAG_ID} must not set")
            if tag_key:
                print(f"{self.qitem(self.qid)} seems to be a key, but {P_TAG_KEY} must not set")
            if not sl:
                print(f"{self.qitem(self.qid)} seems to be a key, but sitelink is not set")
            elif not sl.startswith('Key:') or (key_strid and sitelink_normalizer_key(key_strid) != sl):
                print(f"{self.qitem(self.qid)} seems to be a key, but sitelink equals to {sl}")

            related_tags = self.proc.tags_per_key[self.qid] if self.qid in self.proc.tags_per_key else []
            if len(related_tags) > 5:
                self.new_claims[P_KEY_TYPE.id]['en'] = Q_ENUM_KEY_TYPE
        if instance_of == Q_TAG or tag_strid or (sl and sl.startswith('Tag:')):
            # Must be a tag
            if instance_of != Q_TAG:
                print(f"{self.qitem(self.qid)} seems to be a tag, but instance_of is {instance_of}")
            if not tag_strid:
                print(f"{self.qitem(self.qid)} seems to be a tag, but {P_TAG_ID} is not set")
            if key_strid:
                print(f"{self.qitem(self.qid)} seems to be a tag, but {P_KEY_ID} must not be set")

            ek = self.proc.cache.itemKeysByStrid.get()
            ks = tag_strid.split('=')[0]
            expected_tag_key = ek[ks] if ks in ek else False

            if not tag_key:
                print(f"{self.qitem(self.qid)} seems to be a tag, but {P_TAG_KEY} is not set" +
                      (' to ' + self.qitem(
                          expected_tag_key) if expected_tag_key else ' (nor it could be found in the item cache)'))
                self.proc.autogenerated_keys.add(ks)
            else:
                if not expected_tag_key:
                    print(f"{self.qitem(self.qid)} {P_KEY_ID} = {self.qitem(tag_key)}, "
                          f"but the computed key '{ks}' does not exist in the item cache")
                elif expected_tag_key != tag_key:
                    print(f"{self.qitem(self.qid)} {P_KEY_ID} = {self.qitem(tag_key)}, "
                          f"which is different from expected {self.qitem(expected_tag_key)}")
            if tag_key in self.proc.cache.itemByQid.get():
                tag_key_item = self.proc.cache.itemByQid.get()[tag_key]
                if P_INSTANCE_OF.get_claim_value(tag_key_item) != Q_KEY:
                    print(f"{self.qitem(self.qid)} {P_KEY_ID} = {self.qitem(tag_key)}, which is not a key")
                if P_KEY_ID.get_claim_value(tag_key_item) != ks:
                    print(f"{self.qitem(self.qid)} {P_KEY_ID} = {self.qitem(tag_key)}, "
                          f"which does not have its key id set to {ks}")
            if not sl:
                print(f"{self.qitem(self.qid)} seems to be a tag, but sitelink is not set")
            elif not sl.startswith('Tag:') or (tag_strid and sitelink_normalizer_tag(tag_strid) != sl):
                print(f"{self.qitem(self.qid)} seems to be a tag, but sitelink equals to {sl}")

    def qitem(self, qid):
        if not qid: return '[New Item]'
        ids = self.proc.cache.itemDescByQid.get()
        if type(qid) == str: qid = [qid]
        return '[' + ', '.join([ids[v] if v in ids else '(' + v + ')' for v in qid]) + ']'

    def get_nonbot_editors(self, item):
        if not item or self.proc.opts.ignore_user_edits:
            return False
        resp = self.proc.site('query', {
            'prop': 'contributors',
            'pclimit': 'max',
            'titles': 'Item:' + item,
        })
        contributors = [v['name'] for v in resp['pages'][0]['contributors']]
        return ', '.join([c for c in contributors if c != 'Yurikbot']) if contributors != ['Yurikbot'] else False

    def apply_claims(self, new_claims_all, prop, data=False):
        if not prop.allow_multiple:
            new_claims_all = {k: [v] for k, v in new_claims_all.items()}
        self.new_claims = new_claims_all['en'] if 'en' in new_claims_all else False
        set_to_lang = list_to_dict_of_lists(
            [(k, tuple(v)) for k, v in new_claims_all.items()],
            lambda v: v[1], lambda v: v[0])
        if len(set_to_lang) == 1:
            self.new_claims = list([v for v in set_to_lang.keys()][0])
        else:
            status = f"  Claim mismatch: {self.qitem(self.qid)} - {self.strid} {prop}:"
            for q, lngs in set_to_lang.items():
                status += f"  ({','.join(lngs)}) = {self.qitem(q)}"
            print(status)
            if not self.new_claims:
                print('  Skipping...')
                return
        if self.new_claims:
            old_claims = prop.get_claim_value(self.item, allow_multiple=True)
            if old_claims == self.new_claims:
                return
        else:
            return

        if self.qid:
            pbitem = pb.ItemPage(self.proc.pb_site, self.qid)
            pbitem.get()
            old_claims2 = pbitem.claims[prop.id] if prop.id in pbitem.claims else []
        else:
            old_claims2 = []
        old_claims_ids = set([prop.value_from_claim(c) for c in old_claims2])
        self.new_claims = set(self.new_claims)
        addc = self.new_claims - old_claims_ids
        delc = old_claims_ids - self.new_claims
        if not addc and not delc:
            return

        other_editors = self.get_nonbot_editors(self.qid)

        status = f'  {prop}' if not self.qid else f"{self.qitem(self.qid)} {prop}"
        if addc:
            status += f" = {self.qitem(addc)}"
        if delc:
            status += f"   removing {self.qitem(delc)}"
        print(status)

        if other_editors:
            print(f'XXXXXXXXXXXXX  Cannot update {self.qitem(self.qid)} because it was edited by {other_editors}')
            return
        if not self.allow_edit(prop):
            return

        for v in addc:
            if self.qid:
                pbitem.addClaim(prop.create_claim(self.proc.pb_site, v))
            else:
                prop.set_claim_on_new(data, v)
        remove = [c for c in old_claims2 if prop.value_from_claim(c) not in self.new_claims]
        if remove:
            pbitem.removeClaims(remove)

    def allow_edit(self, prop):
        if (self.proc.opts.props and prop.id not in self.proc.opts.props) or \
                (self.proc.opts.ignore_qid and self.qid in self.proc.opts.ignore_qid):
            print(f'***********************  Skipping {self.qitem(self.qid)} prop {prop} due to parameter restrictions.')
            return False
        return True

    def update_text_val(self, typ, lng, newval, wikiinfo):
        typs = typ + 's'
        if typ in wikiinfo:
            old_value = self.get_localized_value(typs, lng)
            old_en_value = self.get_localized_value(typs, 'en')
            wikivalue = wikiinfo[typ][:250]
            if wikivalue != old_value:
                if lng != 'en':
                    if 'en' in newval and newval['en'] == wikivalue:
                        return
                    if old_en_value == wikivalue:
                        return
                newval[lng] = wikivalue
            elif lng != 'en' and old_en_value == wikivalue:
                # current value should be deleted
                newval[lng] = ''

    def get_localized_value(self, typ, lng, fallback_to_en=False):
        if typ in self.item:
            all = self.item[typ]
            if lng in all:
                return all[lng]['value']
            if fallback_to_en and 'en' in all:
                return all['en']['value']
        return None
