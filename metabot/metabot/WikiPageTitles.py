from typing import List
from pywikibot import textlib
from pywikiapi import Site

from .consts import NS_USER, NS_TEMPLATE, LANG_NS, LANG_NS_REVERSE
from .Cache import CacheJsonl
from .utils import to_json, parse_wiki_page_title, batches


class WikiPagesWithTemplate(CacheJsonl):
    def __init__(self, filename: str, site: Site):
        super().__init__(filename)
        self.site = site

    def generate(self):
        titles = set()
        with open(self.filename, "w+") as file:
            for batch in batches(self.get_all_relevant_pages(), 50):
                print(to_json(res), file=file)

    def get_all_relevant_pages(self):
        titles = {}
        for ns in LANG_NS.values():
            for res in self.site.query(generator='allpages', gapnamespace=ns, gaplimit='max', prop='info'):
                for p in res.allpages:
                    type_from_title, lang, id_from_title, has_suspect_lang = parse_wiki_page_title(ns, p.title)
                    if not id_from_title:
                        if has_suspect_lang:
                            print(f'Possible language: {p.title}')
                        continue
                    titles.add(p.title)
        return titles
