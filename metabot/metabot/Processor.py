from time import sleep
import pywikibot as pb
import re
from collections import defaultdict

from pywikiapi import Site, AttrDict

from .consts import Q_LOCALE_INSTANCE, Q_GROUP
from .ItemFromConcept import ItemFromConcept
from .CacheInstances import Caches
from .ItemFromWiki import ItemFromWiki
from .UploadItem import UploadItem
from .Properties import P_KEY_ID, P_TAG_ID, P_INSTANCE_OF, P_SUBCLASS_OF, P_REL_ID
from .utils import get_entities, list_to_dict_of_lists, sitelink_normalizer, strid_from_item, id_to_sitelink

known_ignored_types = {
    Q_GROUP
}


class Processor:

    def __init__(self, opts, caches: Caches, site: Site) -> None:
        self.opts = AttrDict({
            'throw': True,
            'props': False,
            'ignore_qid': False,
            'overwrite_user_labels_en': True,
            'overwrite_user_labels': False,
            'overwrite_user_descriptions': False,
            'overwrite_user_claims': False,
            'print_user_edits': False,
            'force_all': False,
            **(opts or {})
        })
        self.caches = caches
        self.site = site

        wiki_items = (
            []
            + self.caches.keydescription.get()
            + self.caches.tagdescription.get()
            + self.caches.reldescription.get()
            # + self.caches.relroledescriptions.get()
        )

        # For each variant of str_id, count how many variants there are.
        # Ideally should be 1 for each, but if something defines two variants,
        # e.g. "Key:blah_blah" and "Key:blah blah",
        # each of the values will have 2 or more
        self.str_id_variants_count = defaultdict(int)
        for s in [
            set(lst)
            for k, lst in list_to_dict_of_lists(
                set([(v.type, v.str_id) for v in self.caches.descriptionParsed.get() if v.str_id] +
                [v for v in self.caches.itemKeysByStrid.get().keys() if v[1]]),
                lambda v: (v[0], sitelink_normalizer(v[1], v[0] + ':'))).items()
        ]:
            for v in s:
                self.str_id_variants_count[v] = len(s)
            if len(s) > 1:
                print('Ambiguous entries: "' + '", "'.join([str(v) for v in s]) + '"')

        self.existing_items_strids = set(self.caches.itemKeysByStrid.get().keys())
        self.wiki_items_by_norm_id = list_to_dict_of_lists(wiki_items, lambda v: id_to_sitelink(v.type, v.str_id) if v.str_id else None)
        wiki_items_by_id = list_to_dict_of_lists(wiki_items, lambda v: (v.type, v.str_id) if v.str_id else None)
        self.new_items_strids = {k:v for k,v in wiki_items_by_id.items() if k not in self.existing_items_strids}

        self.all_items_by_strid = {
            **self.items_by_strid(P_KEY_ID),
            **self.items_by_strid(P_TAG_ID),
            **self.items_by_strid(P_REL_ID),
        }

    def items_by_strid(self, prop, fix_multiple=False):
        result = {}
        for item in self.caches.data_items.get():
            qid = item.id
            try:
                values = prop.get_claim_value(item, allow_multiple=True)
                if not values or len(values) == 0:
                    continue
                if len(values) == 1:
                    result[values[0]] = item
                    continue
                if not fix_multiple:
                    raise ValueError('Found multiple key ids ')
                if len(set(values)) > 1:
                    raise ValueError('Found multiple different keys')

                print(f'Removing multiple duplicate keys from { self.caches.qitem(qid)}...')
                raise ValueError('Not implemented')
            except ValueError as err:
                print(f'Error parsing key id from { self.caches.qitem(qid)}: {err}')

        return result

    def run(self, mode):
        if mode == 'new':
            items = self.new_items_strids
        elif mode == 'old':
            items = self.caches.itemKeysByStrid.get()
        elif mode == 'taginfo_keys':
            items = self.get_taginfo_keys()
        elif mode == 'items':
            items = self.caches.data_items.get()
        elif mode == 'taginfo-tags':
            items = [('Tag', v.k+'='+v.v) for v in self.caches.tagInfoDb.get()]
        elif mode == 'relations':
            items = filter(lambda v: v and v.type == 'Relation', self.new_items_strids)
        elif mode == 'relroles':
            items = map(lambda v: v.str_id, self.caches.relroledescriptions.get())
        else:
            items = [mode] if type(mode) == tuple else mode
            mode = f'single object - {mode}'

        print(f'********** Running in {mode} mode')
        for obj in items:
            try:
                self.do_item(obj)
            except Exception as err:
                print(f'Crashed while processing "{obj}"\n{err}')
                if self.opts['throw']:
                    raise
                else:
                    sleep(15)

    def do_item(self, obj):
        if not obj:
            return
        item = None
        wiki_pages = None

        if type(obj) == tuple:
            strid = obj
        else:
            item = obj
            strid = strid_from_item(item)
        if strid:
            if strid[0] == 'Locale':
                print(f'Skipping "{strid}"')
                return
            if strid in self.str_id_variants_count and self.str_id_variants_count[strid] > 1 and not self.opts.force_all:
                print(f'Skipping ambiguous "{strid}"')
                return
            sl = id_to_sitelink(strid[0], strid[1])
            if sl in self.wiki_items_by_norm_id:
                wiki_pages = self.wiki_items_by_norm_id[sl]
            if strid in self.all_items_by_strid:
                item2 = self.all_items_by_strid[strid]
                if not item:
                    item = item2
                elif item2 and item != item2:
                    print(f'Skipping {strid} because it matched {item.id} and {item2.id}')
                    return
        change, sitelink = self.do_item_run(strid, item, wiki_pages, True)
        if change or self.opts.force_all:
            if wiki_pages and strid and strid[0] != 'Role':
                unparsed = self.caches.description.get_new_pages([p.full_title for p in wiki_pages])
                wiki_pages = self.caches.descriptionParsed.parse_manual(unparsed)
            if item:
                item = get_entities(self.site, ids=item.id)
            else:
                item = get_entities(self.site, titles=sitelink)
            if item:
                item = AttrDict(item)
            self.do_item_run(strid, item, wiki_pages, False)

    def do_item_run(self, strid, item, wiki_pages, dry_run):
        status_id = self.caches.qitem(item.id) if item else ''
        if item and P_SUBCLASS_OF.get_claim_value(item):
            return None, None
        if not strid:
            instance_of = P_INSTANCE_OF.get_claim_value(item)
            if instance_of == Q_LOCALE_INSTANCE:
                parsed_item = ItemFromConcept(item)
            else:
                if instance_of not in known_ignored_types:
                    print(f"Skipping {item.id} - don't know what to do with it")
                return None, None
        else:
            if item and 'id' in item and strid not in self.caches.itemKeysByStrid.get():
                self.caches.itemKeysByStrid.get()[strid] = item.id
            parsed_item = ItemFromWiki(self.caches, strid, wiki_pages, self.run)
            if not parsed_item.ok:
                parsed_item.print_messages()
                return None, None
            status_id = f'{strid[0]} {strid[1]} {status_id}'

        uploader = UploadItem(self.caches, self.site, strid, item, parsed_item.header,
                              parsed_item.claims, self.opts, dry_run, self.run)
        if dry_run:
            if not uploader.needs_changes:
                # Do not print messages if we will repeat the process anyway
                parsed_item.print_messages()
                uploader.print_messages()
        else:
            if uploader.needs_changes:
                print(f'==== Updating {status_id} ====')
                parsed_item.print_messages()
                uploader.print_messages()
                if strid[0] != 'Role':
                    # FIXME: !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                    uploader.upload_item_updates()
                uploader.print_messages()
                print(f'==== Done updating {status_id} ====')
            else:
                parsed_item.print_messages()
                uploader.print_messages()

        return uploader.needs_changes, parsed_item.sitelink

    def get_nonbot_editors(self, qid):
        resp = self.site('query', prop='contributors', pclimit='max', titles='Item:' + qid)
        contributors = [v.name for v in resp.query.pages[0].contributors]
        return ', '.join([c for c in contributors if c != 'Yurikbot']) if contributors != ['Yurikbot'] else False

    def get_taginfo_keys(self):
        re_key = re.compile(r'^[a-z0-9]+([-:_.][a-z0-9]+)*$')
        known_keys = self.caches.itemKeysByStrid.get()
        for item in self.caches.taginfo.get()['data']:
            key = item['key']
            count_all = item['count_all']
            if key in known_keys:
                continue
            if count_all > 5000 or (count_all > 50 and re_key.match(key)):
                yield key

    # def del_params(self):
    #     pwb_site = self.caches.descriptionParsed.pwb_site
    #     for wp in self.caches.descriptionParsed.get():
    #         if not wp.del_params:
    #             continue
    #         page = pb.Page(pwb_site, wp.full_title)
    #         text = page.get()
    #         re.sub()
    #         # page.raw_extracted_templates
    #         # pb.textlib.glue_template_and_params()
    #         # print(text)
    #
    #
