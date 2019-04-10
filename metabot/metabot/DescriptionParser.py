import pywikibot as pb
from pywikiapi import AttrDict

from .WikiPagesWithTemplate import WikiPagesWithTemplate
from .Cache import CacheJsonl
from .DescriptionParserItem import ItemParser
from .utils import to_json


class DescriptionParser(CacheJsonl):

    def __init__(self, filename: str, pages: WikiPagesWithTemplate, pwb_site: pb.Site):
        super().__init__(filename)
        self.pages = pages
        self.pwb_site = pwb_site

    def generate(self):
        with open(self.filename, "w+") as file:
            for page in self.pages.iter():
                res = self.parse_item(page)
                if res:
                    print(to_json(res), file=file)

    def parse_item(self, page):
        if page['ns'] % 2 != 1 and page['ns'] != 2: # and 'Proposed features/' not in page['title']:
            item = ItemParser(self.pwb_site, page['ns'], page['title'], page['template'], page['params'])
            result = item.parse()
            if item.messages:
                print(f'#### {page["title"]}')
                item.print_messages()
            if result:
                return result
        # print(f'Skipping {page["title"]}')
        return None

    def parse_manual(self, pages):
        return [AttrDict(v) for v in [self.parse_item(p) for p in pages] if v]
