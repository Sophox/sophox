from .utils import ParsedTitle
from .consts import LANG_NS
from .Cache import Cache


class WikiAllPageTitles(Cache):

    def __init__(self, filename, site):
        super().__init__(filename)
        self.site = site

    def load(self):
        data = []
        with open(self.filename, "r") as file:
            for line in file.readlines():
                parts = line.rstrip().split('\t')
                if len(parts) != 5:
                    if len(parts) != 1 or parts[0] != '':
                        print(f"Error parsing {self.filename}: {line.rstrip()}")
                    continue
                parts[3] = int(parts[3])
                data.append(ParsedTitle(*parts))
        return data

    def generate(self):
        with open(self.filename, "w+") as file:
            for (lang, ns) in LANG_NS.items():
                for page in self.site.allpages(namespace=ns, filterredir=False):
                    r = parse_title(ns, page.title())
                    if r.type:
                        print(f'{r.type}\t{r.str_id}\t{r.lang}\t{r.ns}\t{r.full_title}', file=file)
