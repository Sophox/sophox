from typing import Union, List

from .Properties import P_TAG_KEY, P_INSTANCE_OF
from .utils import list_to_dict_of_lists
from .DescriptionParser import DescriptionParser
from .consts import Q_GROUP, Q_STATUS, Q_TAG
from .CachedFilteredDescription import CachedFilteredDescription
from .DataItems import DataItems, DataItemsByQid, DataItemDescByQid, DataItemsKeysByStrid, DataItemsByName, \
    RegionByLangCode
from .WikiPagesWithTemplate import WikiPagesWithTemplate
from .ResolvedImageFiles import ResolvedImageFiles
from .DataItemContributors import DataItemContributors
from .WikiTagTemplateUsage import WikiTagTemplateUsage
from .TagInfo import TagInfoKeys
from pywikibot import Site as PWB_Site
from pywikiapi import Site


class Caches:
    def __init__(self, site: Site, pwb_site: PWB_Site, use_bot_limits):
        self.taginfo = TagInfoKeys('_cache/taginfo.txt')
        self.tagusage = WikiTagTemplateUsage('_cache/tagusage.txt', site)

        self.images = ResolvedImageFiles('_cache/images.json', pwb_site)
        self.contributed = DataItemContributors('_cache/contributed.json', site)

        self.description = WikiPagesWithTemplate(
            '_cache/wiki_raw_descriptions.json', site,
            ['Template:Description'],
            ['KeyDescription', 'ValueDescription', 'RelationDescription', 'Deprecated', 'Pl:KeyDescription',
             'Pl:ValueDescription'])

        self.descriptionParsed = DescriptionParser(
            '_cache/wiki_parsed_descriptions.json', self.description, self.images, pwb_site)

        self.keydescription = CachedFilteredDescription(self.descriptionParsed, 'Key')
        self.tagdescription = CachedFilteredDescription(self.descriptionParsed, 'Tag')
        self.reldescription = CachedFilteredDescription(self.descriptionParsed, 'Relation')

        self.data_items = DataItems('_cache/data_items.json', site, use_bot_limits)

        self.itemByQid = DataItemsByQid(self.data_items)
        self.itemDescByQid = DataItemDescByQid(self.data_items)
        self.itemKeysByStrid = DataItemsKeysByStrid(self.data_items)
        self.regionByLangCode = RegionByLangCode(self.data_items)
        self.groupsByName = DataItemsByName(self.data_items, Q_GROUP)
        self.statusesByName = DataItemsByName(self.data_items, Q_STATUS)

        self.tags_per_key = list_to_dict_of_lists(
            self.data_items.get(),
            lambda v: P_TAG_KEY.get_claim_value(v) if P_INSTANCE_OF.get_claim_value(v) == Q_TAG else None)

    def qitem(self, qid: Union[str, List[str]]):
        if not qid: return '[New Item]'
        ids = self.itemDescByQid.get()
        if type(qid) == str: qid = [qid]
        return '[' + ', '.join([ids[v] if v in ids else '(' + v + ')' for v in qid]) + ']'
