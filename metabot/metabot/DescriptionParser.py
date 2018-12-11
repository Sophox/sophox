import pywikibot as pb
from pywikiapi import AttrDict

from .Cache import CacheJsonl
from .DescriptionParserItem import ItemParser
from .ResolvedImageFiles import ResolvedImageFiles
from .utils import to_json


class DescriptionParser(CacheJsonl):

    def __init__(self, filename, descriptions, image_cache: ResolvedImageFiles, pwb_site: pb.Site):
        super().__init__(filename)
        self.descriptions = descriptions
        self.image_cache = image_cache
        self.pwb_site = pwb_site

    def generate(self):
        with open(self.filename, "w+") as file:
            for page in self.descriptions.iter():
                page = AttrDict(page)
                if page.template not in [
                    'KeyDescription', 'ValueDescription', 'Deprecated', 'Pl:KeyDescription', 'Pl:ValueDescription'
                ]:
                    # Ignore relations for now
                    continue

                item = ItemParser(self.image_cache, self.pwb_site, page.ns, page.title, page.template, page.params)
                result = item.parse()
                if item.messages:
                    print(f'#### {page.title}\n  ' + '\n  '.join(item.messages))
                if result:
                    print(to_json(result), file=file)
                else:
                    print(f'Skipping {page.title}')
