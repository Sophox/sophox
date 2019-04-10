import difflib

from json import loads, dumps
from pywikiapi import AttrDict
from typing import List

from metabot import known_non_enums
from metabot.utils import to_item_sitelink, id_to_sitelink
from .Sorter import Sorter, claim_order
from .Properties import *
from .consts import Q_KEY, Q_TAG, Q_ENUM_KEY_TYPE, Q_LOCALE_INSTANCE, Q_REL_MEMBER_ROLE
from .utils import get_sitelink, list_to_dict_of_lists, to_json


class UploadItem:
    claims: Dict[Property, List[ClaimValue]]

    def __init__(self, caches, site, strid, item, header,
                 claims: Dict[Property, List[ClaimValue]],
                 opts, dry_run, create_new) -> None:
        self.messages = []
        self.caches = caches
        self.opts = opts
        self.qitem = caches.qitem
        self.site = site
        self.type = strid[0]
        self.strid = strid[1]
        self.item = item
        self.header = header
        self.claims = claims
        self.dry_run = dry_run
        self.needs_changes = False
        # self.mod_claims = {}
        # self.duplicates = {}
        self.force_contribs = not dry_run
        self.rank_updated = False
        self.create_new = create_new
        self.sorter = Sorter(self.site)
        self.is_new = not item

        if self.is_new:
            self.item = AttrDict()
            self.item.labels = {}
            self.item.descriptions = {}
            self.item.sitelinks = header['sitelinks']
            self.item.claims = {}
            self.qid = None
            self.old_item = AttrDict()
        else:
            self.qid = self.item.id
            self.old_item = loads(dumps(item, ensure_ascii=False), object_hook=AttrDict)

        try:
            if not self.is_new:
                self.validate_data_item()
            self.update_i18n('labels', self.opts.overwrite_user_labels)
            self.update_i18n('descriptions', self.opts.overwrite_user_descriptions)
            self.update_claims()
            self.calc_changes()
        except:
            self.print_messages()
            self.needs_changes = False
            raise

    def prohibit(self, type, value):
        if self.is_new:
            return False
        if self.type == 'Role' and type == 'claims':
            # TODO!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            return True
        force = self.force_contribs
        contribs = self.caches.contributed(self.item.id, force=force)
        self.force_contribs = False
        return type in contribs and value in contribs[type]

    def upload_item_updates(self):
        self.print(('Updating ' if not self.is_new else 'Creating ') + \
                   (self.strid or '') + ' ' + self.qitem(self.qid))
        self.print_messages()

        id = self.edit_entity(
            self.item,
            'Auto-updating from Wiki pages',
            self.item['id'] if 'id' in self.item else None)

        self.print_messages()
        self.caches.itemKeysByStrid.get()[(self.type, self.strid)] = id
        self.print(f'+++ Data item {self.type} {self.strid} ({id}) updated!')

    def update_i18n(self, type, overwrite_user):
        if type not in self.header:
            return
        item_values = self.item[type]
        new_values = self.header[type]
        for lang in set(new_values.keys()).union(item_values.keys()):
            if lang in item_values and lang in new_values and item_values[lang].value == new_values[lang]:
                continue
            if not overwrite_user and self.prohibit(type[:-1], lang):
                if lang in item_values and lang in new_values:
                    msg = f'{type}:{lang} was modified by a user to "{item_values[lang].value}", cannot be set to "{new_values[lang]}"'
                elif lang in item_values:
                    msg = f'{type}:{lang} was modified by a user to "{item_values[lang].value}", cannot be deleted'
                else:
                    msg = f'{type}:{lang} was deleted by a user, cannot be set to "{new_values[lang]}"'
                if self.opts.print_user_edits:
                    self.print(msg)
                continue
            if lang in new_values:
                item_values[lang] = {'language': lang, 'value': new_values[lang]}
            else:
                del item_values[lang]

    def update_claims(self):
        for prop in set(c for c in self.claims.keys())\
                .union([Property.ALL[c] for c in self.item.claims.keys() if c in Property.ALL]):
            self.update_prop_claims(prop)

    @staticmethod
    def sort_claims(claims):
        claims.sort(key=lambda cv: claim_order(cv.rank == 'preferred', cv.value))
        return claims

    def update_prop_claims(self, prop):
        item_claims = self.sort_claims(prop.get_claim_value(self.item, True, True)) if prop.id in self.item.claims else None
        desired_claims = self.sort_claims(self.claims[prop]) if prop in self.claims else None
        if item_claims == desired_claims:
            return
        if not self.opts.overwrite_user_claims and self.prohibit('claims', prop.id):
            if item_claims and desired_claims:
                self.print(f'{prop} was modified by a user to "{item_claims}", cannot be set to "{desired_claims}"')
            elif item_claims:
                # self.print(f'{prop} was modified by a user to "{item_claims}", cannot be deleted')
                pass
            else:
                self.print(f'{prop} was deleted by a user, cannot be set to "{desired_claims}"')
            return
        if desired_claims:
            if item_claims:
                for val in item_claims:
                    for dv in list(desired_claims):
                        if dv.value == val.value:
                            item_claim_val, = (v for v in self.item.claims[prop.id] if prop.get_value(v) == dv.value)
                            item_claim_val.rank = dv.rank # just in case it has changed
                            desired_qs = [(p.id, q) for p, ql in dv.qualifiers.items() for q in ql]
                            item_qs = [q for ql in item_claim_val.qualifiers.values() for q in ql] if 'qualifiers' in item_claim_val else []
                            for itmq in item_qs:
                                try:
                                    desired_qs.remove((itmq.property, Property.ALL[itmq.property].get_value(itmq)))
                                except ValueError:
                                    item_claim_val.qualifiers[itmq.property].remove(itmq)
                                    if not item_claim_val.qualifiers[itmq.property]:
                                        del item_claim_val.qualifiers[itmq.property]
                                        item_claim_val['qualifiers-order'].remove(itmq.property)
                            for qpid, newq in desired_qs:
                                if 'qualifiers' not in item_claim_val:
                                    item_claim_val.qualifiers = {}
                                if qpid not in item_claim_val.qualifiers:
                                    item_claim_val.qualifiers[qpid] = []
                                    if 'qualifiers-order' not in item_claim_val:
                                        item_claim_val['qualifiers-order'] = [qpid]
                                    else:
                                        item_claim_val['qualifiers-order'].append(qpid)
                                item_claim_val.qualifiers[qpid].append(Property.ALL[qpid].create_snak(newq))

                            desired_claims.remove(dv)
                            break
                    else:
                        prop.remove_claim(self.item, val)
            for val in desired_claims:
                prop.set_claim_on_new(self.item, val)
        else:
            del self.item.claims[prop.id]

    def validate_data_item(self):
        item = self.item
        item_as_str = self.qitem(self.qid)
        instance_of = P_INSTANCE_OF.get_claim_value(item)
        key_strid = P_KEY_ID.get_claim_value(item)
        tag_strid = P_TAG_ID.get_claim_value(item)
        tag_key = P_TAG_KEY.get_claim_value(item)
        sitelink = get_sitelink(item)
        edit_sitelink = self.header['sitelinks']['wiki']['title']
        item_is_key = None
        item_is_tag = None

        if self.type == 'Locale' or instance_of == Q_LOCALE_INSTANCE:
            locale_id = P_LANG_CODE.get_claim_value(item)
            exp_sitelink = id_to_sitelink('Locale', locale_id.lower())
            if not sitelink or sitelink != exp_sitelink:
                item.sitelinks = to_item_sitelink(exp_sitelink)
                sitelink = exp_sitelink
                self.rank_updated = True
        elif self.type == 'Role' or instance_of == Q_REL_MEMBER_ROLE:
            pass
        if self.type == 'Key' or \
                instance_of == Q_KEY or key_strid or \
                (sitelink and sitelink.startswith('Key:')) or \
                (edit_sitelink and edit_sitelink.startswith('Key:')):
            # Must be a key
            item_is_key = True
            if not instance_of:
                self.print(f"{item_as_str} seems to be a key, but instance_of is not set")
                self.claims[P_INSTANCE_OF] = [ClaimValue(Q_KEY)]
            elif instance_of != Q_KEY:
                self.print(f"{item_as_str} seems to be a key, but instance_of is {instance_of}")
                item_is_key = False
            if not key_strid:
                self.print(f"{item_as_str} seems to be a key, but {P_KEY_ID} is not set")
                self.claims[P_KEY_ID] = [ClaimValue(self.strid)]
            elif '=' in key_strid:
                self.print(f"{item_as_str} seems to be a key, but {key_strid} has '=' in it")
                item_is_key = False
            if tag_strid:
                self.print(f"{item_as_str} seems to be a key, but {P_TAG_ID} must not set")
            if tag_key:
                self.print(f"{item_as_str} seems to be a key, but {P_TAG_KEY} must not set")
                item_is_key = False

            expected_sitelink = id_to_sitelink('Key', self.strid)
            if not sitelink:
                self.print(f"{item_as_str} seems to be a key, but sitelink is not set")
                item.sitelinks = to_item_sitelink(expected_sitelink)
            elif not sitelink.startswith('Key:') or (key_strid and expected_sitelink != sitelink):
                self.print(f"{item_as_str} seems to be a key, but sitelink equals to {sitelink}")
                if sitelink.startswith('Tag:') or '=' in sitelink:
                    item_is_key = False
            if expected_sitelink != edit_sitelink:
                raise ValueError(f'Expected sitelink {expected_sitelink} != {edit_sitelink}')

            related_tags = self.caches.tags_per_key[self.qid] if self.qid in self.caches.tags_per_key else []
            if len(related_tags) > 5 and key_strid not in known_non_enums:
                self.claims[P_KEY_TYPE] = [ClaimValue(Q_ENUM_KEY_TYPE)]

        if self.type == 'Tag' or \
                instance_of == Q_TAG or tag_strid or \
                (sitelink and sitelink.startswith('Tag:')) or \
                (edit_sitelink and edit_sitelink.startswith('Tag:')):
            # Must be a tag
            item_is_tag = True
            if not instance_of:
                self.print(f"{item_as_str} seems to be a tag, but instance_of is not set")
                self.claims[P_INSTANCE_OF] = [ClaimValue(Q_TAG)]
            elif instance_of != Q_TAG:
                self.print(f"{item_as_str} seems to be a tag, but instance_of is {instance_of}")
                item_is_tag = False
            if not tag_strid:
                self.print(f"{item_as_str} seems to be a tag, but {P_TAG_ID} is not set")
                self.claims[P_TAG_ID] = [ClaimValue(self.strid)]
            elif '=' not in tag_strid:
                self.print(f"{item_as_str} seems to be a tag, but {tag_strid} has no '=' in it")
                item_is_tag = False
            if key_strid:
                self.print(f"{item_as_str} seems to be a tag, but {P_KEY_ID} must not be set")
                item_is_tag = False

            ks = ('Key', (tag_strid or self.strid).split('=')[0])
            expected_tag_key = self.caches.itemKeysByStrid.get_strid(ks)

            if not tag_key:
                self.print(f"{item_as_str} seems to be a tag, but {P_TAG_KEY} is not set" +
                           (', setting to ' + self.qitem(
                               expected_tag_key) if expected_tag_key else ' (nor it could be found in the item cache)'))
                if expected_tag_key:
                    self.claims[P_TAG_KEY] = [ClaimValue(expected_tag_key)]
                else:
                    self.create_new(ks)
            else:
                if not expected_tag_key:
                    self.print(f"{item_as_str} {P_KEY_ID} = {self.qitem(tag_key)}, "
                               f"but the computed key '{ks}' does not exist in the item cache")
                elif expected_tag_key != tag_key:
                    self.print(f"{item_as_str} {P_KEY_ID} = {self.qitem(tag_key)}, "
                               f"which is different from expected {self.qitem(expected_tag_key)}")
            if tag_key in self.caches.itemByQid.get():
                tag_key_item = self.caches.itemByQid.get()[tag_key]
                if P_INSTANCE_OF.get_claim_value(tag_key_item) != Q_KEY:
                    self.print(f"{item_as_str} {P_KEY_ID} = {self.qitem(tag_key)}, "
                               f"which is not a key")
                if P_KEY_ID.get_claim_value(tag_key_item) != ks[1]:
                    self.print(f"{item_as_str} {P_KEY_ID} = {self.qitem(tag_key)}, "
                               f"which does not have its key id set to {ks}")

            expected_sitelink = id_to_sitelink('Tag', self.strid)
            if not sitelink:
                self.print(f"{item_as_str} seems to be a tag, but sitelink is not set")
                item.sitelinks = to_item_sitelink(expected_sitelink)
            elif not sitelink.startswith('Tag:') or (tag_strid and expected_sitelink != sitelink):
                self.print(f"{item_as_str} seems to be a tag, but sitelink equals to {sitelink}")
                if sitelink.startswith('Key:') or '=' not in sitelink:
                    item_is_tag = False
            if expected_sitelink != edit_sitelink:
                raise ValueError(f'Expected sitelink {expected_sitelink} != {edit_sitelink}')

        if item_is_key == False or item_is_tag == False:
            raise ValueError(f'{item_as_str} needs manual fixing')

        # Fix multiple values
        for prop in Property.ALL.values():
            if not prop.allow_multiple:
                vals = prop.get_claim_value(item, allow_multiple=True, allow_qualifiers=True)
                if vals:
                    vals = list_to_dict_of_lists(vals, lambda v: v.rank)
                    if 'preferred' in vals:
                        vals2 = vals['preferred']
                        if len(vals2) > 1:
                            self.print(f"{item_as_str} property {prop} has multiple preferred values:")
                            self.print('  ' + '\n  '.join([str(v) for v in vals2]))
                        with_lmt_qlf = [v for v in vals2 if v.qualifiers and P_LIMIT_TO in v.qualifiers]
                        if len(with_lmt_qlf) > 0:
                            self.print(f"{item_as_str} property {prop} has preferred values with qualifier:")
                            self.print('  ' + '\n  '.join([str(v) for v in with_lmt_qlf]))
                    if 'normal' in vals:
                        vals2 = vals['normal']
                        if len(vals2) > 1:
                            qualifiers = [v.qualifiers[P_LIMIT_TO]
                                          for v in vals2 if v.qualifiers and P_LIMIT_TO in v.qualifiers]
                            unique = set()
                            for qlf in qualifiers:
                                unique.update(qlf)
                            if sum([len(v) for v in qualifiers]) != len(unique):
                                self.print(f"{item_as_str} property {prop} has multiple normal values:")
                                self.print('  ' + '\n  '.join([str(v) for v in vals2]))

    def print(self, msg):
        self.messages.append(msg)

    def print_messages(self):
        if self.messages:
            print(f'---- {self.type} {self.strid}  {self.item["id"] if (self.item and "id" in self.item) else ""}')
            for msg in self.messages:
                print(msg)
            self.messages = []

    def fix_duplicates(self, prop):
        if prop.id in self.item.claims:
            vals = set()
            remove = []
            for c in self.item.claims[prop.id]:
                val = prop.value_from_claim(c)
                if val in vals:
                    remove.append(c)
                else:
                    vals.add(val)
            if remove:
                self.item.removeClaims(remove)

    def create_language_region(self, lang_code, label, description):
        data = {
            'labels': {'en': label},
            'descriptions': {'en': description},
            'sitelinks': to_item_sitelink(id_to_sitelink('Locale', lang_code)),
        }
        P_INSTANCE_OF.set_claim_on_new(data, Q_LOCALE_INSTANCE)
        P_LANG_CODE.set_claim_on_new(data, lang_code)
        self.edit_entity(data, label)

    def edit_entity(self, data, summary, qid=None):
        params = AttrDict()
        params.summary = summary
        params.token = self.site.token()
        params.data = to_json(data)
        params.bot = 1
        params.POST = 1
        if qid:
            params.id = qid
            params.clear = 1
        else:
            params.new = 'item'

        result = self.site('wbeditentity', **params)

        return result.entity.id if result.success else None

    def calc_changes(self):
        self.item = self.sorter.order(self.item)

        if self.old_item == self.item or \
                dumps(self.old_item, sort_keys=True, ensure_ascii=False) == \
                dumps(self.item, sort_keys=True, ensure_ascii=False):
            return None

        self.needs_changes = True

        if 'title' in self.item:
            self.print(f'Modified {self.item["title"]}')

        self.old_item = self.sorter.order(self.old_item)
        for group in ['labels', 'descriptions', 'sitelinks', 'claims']:
            old_vals = self.old_item[group] if group in self.old_item else {}
            new_vals = self.item[group] if group in self.item else {}
            if group == 'claims':
                pairs = []
                for k in set(old_vals.keys()).union(new_vals.keys()):
                    o = {k: old_vals[k]} if k in old_vals else {}
                    n = {k: new_vals[k]} if k in new_vals else {}
                    pairs.append((o, n))
            else:
                pairs = [(old_vals, new_vals)]
            for o,n in pairs:
                self.print_diff(o, n, group)
                group = None

    def print_diff(self, old_vals, new_vals, group):
        old_dict = old_vals.copy()
        new_dict = new_vals.copy()
        for key in set(old_vals.keys()) & set(new_vals.keys()):
            if old_dict[key] == new_dict[key]:
                del old_dict[key]
                del new_dict[key]
        if not old_dict and not new_dict:
            return
        old = to_json(old_dict, True).split('\n')[1:-1] if old_dict else []
        new = to_json(new_dict, True).split('\n')[1:-1] if new_dict else []
        if group:
            self.print(f'  ---{group}---')
        status = f'  ' + '\n  '.join([
            f"\x1b[{'32;107' if s.startswith('+') else '31;107' if s.startswith('-') else '0'}m{s}\x1b[0m"
            for s in difflib.ndiff(old, new) if not s.startswith('?')
        ])
        self.print(status)
