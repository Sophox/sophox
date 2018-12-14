from typing import Union, List
from pywikibot import textlib
from pywikiapi import Site

from .consts import NS_USER, NS_USER_TALK, NS_TEMPLATE, NS_TEMPLATE_TALK, LANG_NS
from .Cache import CacheJsonl
from .utils import to_json, parse_wiki_page_title, batches


class WikiPagesWithTemplate(CacheJsonl):
    def __init__(self, filename: str, site: Site, template: List[str],
                 template_filters: List[str]):
        super().__init__(filename)
        self.site = site
        self.template = set(template)
        self.template.update(['Template:' + flt for flt in template_filters])
        self.filters = set(template_filters)
        self.ignore = set()
        for flt in self.filters:
            self.ignore.add('Template:' + flt)
        self.filters.update(self.ignore)
        self.ignore.update({template} if isinstance(template, str) else set(template))
        self.filters = set([v.lower() for v in self.filters])

    def generate(self):
        titles = set()
        with open(self.filename, "w+") as file:
            for batch in batches(self.get_all_relevant_pages(), 50):
                for page in self.site.query_pages(
                        prop=['revisions', 'info'],
                        rvprop='content',
                        inprop='redirect',
                        titles=batch,
                ):
                    if page.title in titles:
                        print(f'Duplicate title {page.title}')
                        continue
                    else:
                        titles.add(page.title)
                    for res in self.parse_page(page):
                        print(to_json(res), file=file)

    def get_new_pages(self, titles):
        result = []
        for page in self.site.query_pages(
                prop='revisions',
                rvprop='content',
                titles=titles,
        ):
            for item in self.parse_page(page):
                result.append(item)
        return result

    def get_all_relevant_pages(self):
        titles = set()
        for ns in LANG_NS.values():
            for res in self.site.query(list='allpages', apnamespace=ns, aplimit='max'):
                for p in res.allpages:
                    type_from_title, lang, id_from_title, has_suspect_lang = parse_wiki_page_title(ns, p.title)
                    if not id_from_title:
                        if has_suspect_lang:
                            print(f'Possible language: {p.title}')
                        continue
                    titles.add(p.title)
        for page in self.site.query_pages(prop='transcludedin', tilimit='max', titles=self.template):
            for p in page.transcludedin:
                titles.add(p.title)
        return titles

    def parse_page(self, page):
        if self.ignore_title(page.ns, page.title):
            return
        if 'revisions' in page and len(page.revisions) == 1 and 'content' in page.revisions[0]:
            found = False
            for (t, p) in textlib.extract_templates_and_params(page.revisions[0].content, True, True):
                if t.lower() in self.filters:
                    found = True
                    yield {
                        'ns': page.ns,
                        'title': page.title,
                        'template': t,
                        'params': p,
                    }
            if not found:
                print(f'Unable to find relevant templates in {page.title}')

    def ignore_title(self, ns, title):
        if ns % 2 == 1:
            return True  # Ignore talk pages
        if ns == NS_USER:
            return True  # User pages
        if ns == NS_TEMPLATE:
            for f in self.ignore:
                if f == title or title.startswith(f + '/'):
                    return True  # Template pages whose title is the same as the filtered templates
        return False
