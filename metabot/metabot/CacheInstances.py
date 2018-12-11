from .DescriptionParser import DescriptionParser
from .consts import Q_GROUP, Q_STATUS
from .CachedFilteredDescription import CachedFilteredDescription
from .DataItems import DataItems, DataItemsByQid, DataItemDescByQid, DataItemsKeysByStrid, DataItemsByName
from .WikiPagesWithTemplate import WikiPagesWithTemplate
from .ResolvedImageFiles import ResolvedImageFiles
from .WikiTagTemplateUsage import WikiTagTemplateUsage
from .TagInfo import TagInfoKeys
from pywikibot import Site as PWB_Site
from pywikiapi import Site


class Caches:
    def __init__(self, site: Site, pwb_site: PWB_Site, use_bot_limits):
        self.taginfo = TagInfoKeys('_cache/taginfo.txt')
        self.tagusage = WikiTagTemplateUsage('_cache/tagusage.txt', site)

        self.images = ResolvedImageFiles('_cache/images.json', pwb_site)

        self.description = WikiPagesWithTemplate(
            '_cache/wiki_raw_descriptions.json', site,
            ['Template:Description', 'Template:Pl:ValueDescription'],
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
        self.groupsByName = DataItemsByName(self.data_items, Q_GROUP)
        self.statusesByName = DataItemsByName(self.data_items, Q_STATUS)
