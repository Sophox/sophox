import re
from typing import List
from pywikibot import textlib
from pywikiapi import Site

from .consts import NS_USER, NS_TEMPLATE, LANG_NS, LANG_NS_REVERSE
from .Cache import CacheJsonl
from .utils import to_json, parse_wiki_page_title, batches, parse_members

map_feature_pages = [
    'Ar:Map Features',
    'Ast:Map Features',
    'Az:Map Features',
    'Bg:Map Features',
    'Bs:Map Features',
    'Cs:Map Features',
    'Da:Map Features',
    'DE:Map Features',
    'El:Map Features',
    'Eo:Map Features',
    'Et:Map Features',
    'Fa:Map Features',
    'Fi:Map Features',
    'He:Map Features',
    'Hr:Map Features',
    'Hu:Map Features',
    'Id:Map Features',
    'Is:Map Features',
    'IT:Map Features',
    'JA:Map Features',
    'Ka:Map Features',
    'Ko:Map Features',
    'Lt:Map Features',
    'Lv:Map Features',
    'Map Features',
    'Mk:Map Features',
    'My:Map Features',
    'Ne:Map Features',
    'No:Map Features',
    'Pl:Map Features',
    'Pt:Map Features',
    'Ro:Map Features',
    'Sk:Map Features',
    'Sl:Map Features',
    'Sq:Map Features',
    'Sr:Map Features',
    'Sv:Map Features',
    'Ta:Map Features',
    'Tr:Map Features',
    'Vi:Map Features',
    'Zh-hans:Map Features',
    'Zh-hant:Map Features',
]


class WikiFeatures(CacheJsonl):
    def __init__(self, filename: str, site: Site, pwb_site):
        super().__init__(filename)
        self.site = site
        self.pwb_site = pwb_site

    def generate(self):
        titles = set()
        with open(self.filename, "w+") as file:
            for batch in batches(self.get_all_relevant_pages(), 50):
                for page in self.site.query_pages(
                        prop=['revisions', 'info'],
                        rvprop='content',
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
        # for batch in batches(map_feature_pages, 50):
        #     for res in self.site.query(prop='templates', tllimit='max', titles=batch):
        #         for p in res.pages:
        #             for t in p.templates:
        #                 titles.add(t.title)
        # for res in self.site.query(apprefix='Template:Map Features:')
        templates = set()
        for res in self.site.query(list='allpages', apprefix='Map Features:', apnamespace=10, aplimit='max'):
            templates.update([v.title for v in res.allpages if '/' not in v.title])

        for batch in batches(templates, 50):
            for page in self.site.query_pages(prop=['revisions'], rvprop='content', titles=batch):
                content = page.revisions[0].content
                tbl_start = [m.end() for m in re.finditer(r'^ *{\|', content, re.MULTILINE)]
                tbl_end = [m.end() for m in re.finditer(r'^ *\|} *$', content, re.MULTILINE)]
                if len(tbl_start) != len(tbl_end) or len(tbl_start) != 1:
                    print(f'Multiple tables in {page.title} - {len(tbl_start)} starts, {len(tbl_end)}')
                    continue
                content = content[tbl_start[0]:tbl_end[0]]
                for row in re.split(r'\n\|-.*\n', content):
                    cols = re.split(r'(?:^|\n)+\| *', row)
                    if len(cols) != 7:
                        print(f'Unable to parse {row}')
                        continue
                    try:
                        key_param, key_id = parse_kv(cols[1])
                        val_param, val_id = parse_kv(cols[2])
                        if not val_param:
                            print(f'Invalid {cols[2]}')
                            continue
                        members = parse_members(cols[3], print, print)
                        desc_param, desc_text = parse_param(cols[4])
                        render_param, render_text = self.parse_file(cols[5])
                        image_param, image_text = self.parse_file(cols[6])
                    except Exception as ex:
                        print(row, ex)
                        continue
                    print('---' + '\n---'.join([f'{k}={v}' for k,v in [(key_param, key_id), (val_param, val_id), ("", members), (desc_param, desc_text), (render_param, render_text), (image_param, image_text)]]))
                    print('parsed')

                #
                #
                # for res in self.parse_page(page):
                #     print(to_json(res), file=file)

        return titles

    def parse_file(self, val):
        param, file = parse_param(val)
        if param:
            m = textlib._get_regexes(['file'], self.pwb_site)[0].match(file)
            file = m.group(1) if m else None
        if not file:
            print(f'Unparsable {val}')
        return param, file

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
            if not found and 'redirect' in page and not page.redirect:
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


def parse_kv(val):
    m = re.match(r'(?:{{anchor[^}]*}})?(?:\[\[ *)?{{{([^|\]}]*)\| *(?:[^|\]}]*)}}}(?: *\| *(.*)\]\])?', val)
    if not m:
        m = re.match(r'^{{[^|}]*\|(?:lang={{{lang\|}}}\|)?{{{([^|}]+) *\|}}} *\| *([^|}]+(?: *\| *[^|}]*))}}', val)
    return m.groups() if m else (None, None)

def parse_param(val):
    m = re.match(r'{{{([^|\]}]*)(?:\| *((?:.|\n)*))?}}}', val)
    return m.groups() if m else (None, None)
