from typing import Union, List
from pywikibot import textlib
from pywikiapi import Site

from .consts import NS_USER, NS_USER_TALK, NS_TEMPLATE, NS_TEMPLATE_TALK
from .Cache import CacheJsonl
from .utils import to_json


class WikiPagesWithTemplate(CacheJsonl):
    def __init__(self, filename: str, site: Site, template: Union[str, List[str]],
                 template_filters: Union[str, List[str]]):
        super().__init__(filename)
        self.site = site
        self.template = template
        self.filters = {template_filters} if isinstance(template_filters, str) else set(template_filters)
        self.ignore = set()
        for flt in self.filters:
            self.ignore.add('Template:' + flt)
        self.filters.update(self.ignore)
        self.ignore.update({template} if isinstance(template, str) else set(template))

    def generate(self):
        with open(self.filename, "w+") as file:
            for page in self.site.query_pages(
                    prop='revisions',
                    rvprop='content',
                    redirects='no',
                    generator='transcludedin',
                    gtishow='!redirect',
                    gtilimit='200',
                    titles=self.template,
            ):
                if self.ignore_title(page.ns, page.title):
                    continue
                if 'revisions' in page and len(page.revisions) == 1 and 'content' in page.revisions[0]:
                    found = False
                    for (t, p) in textlib.extract_templates_and_params(page.revisions[0].content, True, True):
                        if t in self.filters:
                            found = True
                            print(to_json({
                                'ns': page.ns,
                                'title': page.title,
                                'template': t,
                                'params': p,
                            }), file=file)
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
