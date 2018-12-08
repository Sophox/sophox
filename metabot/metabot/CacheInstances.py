from .DescriptionParser import DescriptionParser
from .consts import Q_GROUP, Q_STATUS
from .Cache2 import Cached_descriptionParsed, CachedFilteredDescription, Cached_items, Cached_itemByQid, \
    Cached_itemDescByQid, Cached_itemKeysByStrid, Cached_byname
from .WikiPagesWithTemplate import WikiPagesWithTemplate
from .ResolvedImageFiles import ResolvedImageFiles
from .WikiTagTemplateUsage import WikiTagTemplateUsage
# from .WikiAllPageTitles import WikiAllPageTitles
from .TagInfo import TagInfoKeys
from pywikibot import Site as PWB_Site
from pywikiapi import Site


class Caches:
    def __init__(self, site: Site, pwb_site: PWB_Site, use_bot_limits):
        # self.pages = WikiAllPageTitles('_cache/all_titles.txt', site)
        self.taginfo = TagInfoKeys('_cache/taginfo.txt')
        self.tagusage = WikiTagTemplateUsage('_cache/tagusage.txt', site)

        self.images = ResolvedImageFiles('_cache/images.txt')

        self.description = WikiPagesWithTemplate(
            '_cache/wiki_raw_descriptions.json', site,
            ['Template:Description', 'Template:Pl:KeyDescription', 'Template:Pl:ValueDescription'],
            ['KeyDescription', 'ValueDescription', 'RelationDescription', 'Deprecated', 'Pl:KeyDescription',
             'Pl:ValueDescription'])

        self.descriptionParsed = Cached_descriptionParsed(
            '_cache/wiki_parsed_descriptions.json', self.description, DescriptionParser(self.images, pwb_site))

        self.keydescription = CachedFilteredDescription(self.description, 'Key')
        self.tagdescription = CachedFilteredDescription(self.description, 'Tag')
        self.reldescription = CachedFilteredDescription(self.description, 'Relation')

        self.items = Cached_items('_cache/items.txt', site, use_bot_limits)
        self.itemByQid = Cached_itemByQid(self.items)
        self.itemDescByQid = Cached_itemDescByQid(self.items)
        self.itemKeysByStrid = Cached_itemKeysByStrid(self.items)
        self.groupsByName = Cached_byname(self.items, Q_GROUP)
        self.statusesByName = Cached_byname(self.items, Q_STATUS)
