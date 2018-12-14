from collections import defaultdict

from pywikiapi import Site
from pywikibot import textlib

from metabot.Cache import Cache


class WikiTagTemplateUsage(Cache):

    def __init__(self, filename: str, site: Site):
        super().__init__(filename)
        self.site = site

    def load(self):
        data = defaultdict(lambda: defaultdict(int))
        with open(self.filename, "r") as file:
            for line in file.readlines():
                parts = line.rstrip().split('\t', 3)
                if len(parts) != 3:
                    continue
                key, value, count = parts
                data[key][value] += int(count)
        return data

    def generate(self):
        with open(self.filename, "w+") as file:
            for resp in self.site.query(
                    prop='revisions',
                    rvprop='content',
                    redirects='no',
                    generator='transcludedin',
                    gtishow='!redirect',
                    gtilimit='50',
                    titles='Template:Tag',
            ):
                result = defaultdict(int)
                if 'pages' not in resp: continue
                for page in resp['pages']:
                    if 'revisions' in page and len(page['revisions']) == 1 and 'content' in page['revisions'][0]:
                        content = page['revisions'][0]['content']
                        for template in textlib.extract_templates_and_params(content, True, True):
                            for key, value in parse_tag(template, page['title']):
                                result[(key, value)] += 1
                for k, count in result.items():
                    print(f'{k[0]}\t{k[1]}\t{count}', file=file)
        # Consolidate duplicates
        data = self.load()
        with open(self.filename, "w+") as file:
            for key, vv in sorted(data.items(), key=lambda v: sum(v[1].values()), reverse=True):
                for value, count in sorted(vv.items(), key=lambda v: v[0]):
                    print(f'{key}\t{value}\t{count}', file=file)
