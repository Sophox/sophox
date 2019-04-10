import os
from typing import Union, List

from metabot.TagInfoDb import TagInfoDb
from metabot.WikiFeatures import WikiFeatures
from .Properties import P_TAG_KEY, P_INSTANCE_OF
from .utils import list_to_dict_of_lists
from .DescriptionParser import DescriptionParser
from .consts import Q_GROUP, Q_STATUS, Q_TAG
from .CachedFilteredDescription import CachedFilteredDescription, RelationRolesDescription
from .DataItems import DataItems, DataItemsByQid, DataItemDescByQid, DataItemsKeysByStrid, DataItemsByName, \
    RegionByLangCode, DataItemBySitelink
from .WikiPagesWithTemplate import WikiPagesWithTemplate
from .DataItemContributors import DataItemContributors
from .WikiTagTemplateUsage import WikiTagTemplateUsage
from .TagInfo import TagInfoKeys
from pywikibot import Site as PWB_Site
from pywikiapi import Site


class Caches:
    def __init__(self, site: Site, pwb_site: PWB_Site, use_bot_limits):

        os.makedirs("_cache", exist_ok=True)

        self.taginfo = TagInfoKeys('_cache/taginfo.txt')
        self.tagusage = WikiTagTemplateUsage('_cache/tagusage.txt', site)

        self.contributed = DataItemContributors('_cache/contributed.json', site)

        # self.wikiPageTitles = WikiPageTitles('_cache/wiki_page_titles.json', site)

        self.mapfeatures = WikiFeatures('_cache/wiki_map_features.json', site, pwb_site)

        self.description = WikiPagesWithTemplate(
            '_cache/wiki_raw_descriptions.json', site,
            ['Template:Description'],
            ['KeyDescription', 'ValueDescription', 'RelationDescription', 'Deprecated', 'Pl:KeyDescription',
             'Pl:ValueDescription', 'Tag', 'Key', 'TagKey', 'TagValue'])

        self.descriptionParsed = DescriptionParser('_cache/wiki_parsed_descriptions.json', self.description, pwb_site)

        self.keydescription = CachedFilteredDescription(self.descriptionParsed, 'Key')
        self.tagdescription = CachedFilteredDescription(self.descriptionParsed, 'Tag')
        self.reldescription = CachedFilteredDescription(self.descriptionParsed, 'Relation')
        self.relroledescriptions = RelationRolesDescription(self.descriptionParsed)

        self.data_items = DataItems('_cache/data_items.json', site, use_bot_limits)

        self.itemByQid = DataItemsByQid(self.data_items)
        self.itemDescByQid = DataItemDescByQid(self.data_items)
        self.itemQidBySitelink = DataItemBySitelink(self.data_items)
        self.itemKeysByStrid = DataItemsKeysByStrid(self.data_items)
        self.regionByLangCode = RegionByLangCode(self.data_items)
        self.groupsByName = DataItemsByName(self.data_items, Q_GROUP)
        self.statusesByName = DataItemsByName(self.data_items, Q_STATUS)

        self.tags_per_key = list_to_dict_of_lists(
            self.data_items.get(),
            lambda v: P_TAG_KEY.get_claim_value(v) if P_INSTANCE_OF.get_claim_value(v) == Q_TAG else None)

        self.tagInfoDb = TagInfoDb('_cache/tag_info_db.json', '_cache/taginfo-db.db', self.data_items)

    def qitem(self, qid: Union[str, List[str]]):
        if not qid: return '[New Item]'
        ids = self.itemDescByQid.get()
        if type(qid) == str: qid = [qid]
        return '[' + ', '.join([ids[v] if v in ids else '(' + v + ')' for v in qid]) + ']'
