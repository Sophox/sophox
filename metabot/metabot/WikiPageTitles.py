from pywikiapi import Site
from collections import defaultdict

from .consts import LANG_NS
from .Cache import CacheJsonl
from .utils import to_json, parse_wiki_page_title, id_to_sitelink, list_to_dict_of_lists, batches


class WikiPageTitles(CacheJsonl):
    def __init__(self, filename: str, site: Site):
        super().__init__(filename)
        self.site = site

    def generate(self):
        with open(self.filename, "w+") as file:
            print(to_json(self.get_all_relevant_pages()), file=file)

    def get_all_relevant_pages(self):
        titles = defaultdict(list)
        redirect_titles = {}
        for ns in LANG_NS.values():
            for redirects in [True, False]:
                for res in self.site.query(generator='allpages', gapnamespace=ns, gaplimit='max',
                                           gapfilterredir='redirects' if redirects else 'nonredirects'):
                    for p in res.pages:
                        type_from_title, lang, id_from_title, has_suspect_lang = parse_wiki_page_title(ns, p.title)
                        if not id_from_title:
                            if has_suspect_lang:
                                print(f'Possible language: {p.title}')
                            continue
                        good_title = f'{type_from_title}:{id_from_title}'
                        if lang != 'en':
                            good_title = (lang if ns == 0 else lang.upper()) + ':' + good_title
                        good_title = good_title[0].upper() + good_title[1:]
                        if not redirects and p.title != good_title:
                            print(f'Suspicious page, might need to be renamed {p.title} -> {good_title}')
                        titles[id_to_sitelink(type_from_title, id_from_title)].append((lang, p.title, redirects, good_title))

        result = {}
        for k, itms in titles.items():
            res = {}
            for lng, itms in list_to_dict_of_lists(itms, lambda v: v[0]).items():
                item = False
                if len(itms) == 1:
                    item = itms[0]
                elif lng == 'en':
                    print(f'Multiple English pages: {itms}')
                else:
                    nonredirs = [v for v in itms if not v[2]]
                    if len(nonredirs) == 1:
                        item = nonredirs[0]
                    elif len(nonredirs) > 1:
                        print(f'Multiple content pages found: {itms}')
                    else:
                        good_titles = [v for v in itms if v[3] == v[1]]
                        if len(good_titles) == 1:
                            item = good_titles[0]
                        else:
                            print(f'Multiple pages found: {itms}')
                if item:
                    res[lng] = item[1]
                    if item[2]:
                        redirect_titles[item[1]] = []
            if len(res) > 0:
                result[k] = res

        for batch in batches(redirect_titles.keys(), 100):
            for res in self.site.query(titles=batch, redirects=True):
                pages = {v.title: 'missing' in v for v in res.pages}
                redirs = {v['from']: (v.to, v.tofragment if 'tofragment' in v else None, v.to in pages) for v in res.redirects}
                redir_hop = True
                while redir_hop:
                    redir_hop = False
                    for v in batch:
                        lst = redirect_titles[v]
                        if lst == []:
                            nxt = v
                        elif type(lst) == list:
                            nxt = lst[-1][0]
                        else:
                            continue
                        if nxt in redirs:
                            nxt = redirs[nxt]
                            if nxt[2]:
                                redirect_titles[v] = nxt[0] + (f'#{nxt[1]}' if nxt[1] else '')
                                if pages[nxt[0]]:
                                    print(f'MISSING REDIR TARGET: {v}')
                            elif nxt not in lst:
                                lst.append(nxt)
                                redir_hop = True
                            else:
                                print(f'CIRCULAR REDIRECTS: {v}')
                                redirect_titles[v] = False
                        else:
                            print(f'REDIRECT TARGET NOT FOUND: {v}')
                            redirect_titles[v] = False

        for k, vals in result.items():
            for l, title in vals.items():
                if title in redirect_titles:
                    target = redirect_titles[title]
                    vals[l] = (vals[l], target if type(target) == str else None)

        return result
