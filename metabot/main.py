from pathlib import Path

from pywikibot import Site as PWB_Site
from pywikibot.data.api import LoginManager

from metabot.OsmFamily import OsmFamily
from metabot import Caches
from metabot.Processor import Processor
from metabot.Sorter import Sorter
from metabot.utils import get_osm_site

site = get_osm_site()
use_bot_limits = False
pb_site = PWB_Site(fam=OsmFamily(), user='Yurikbot')
caches = Caches(site, pb_site, use_bot_limits=False)

password = Path('./password').read_text().strip()
site.login(user='Yurikbot', password=password, on_demand=True)
# if not pb_site.logged_in():
#     LoginManager(site=pb_site, password=password).login()
#     print('Logged in!')
# else:
#     print('Already logged in')


# s=Sorter(site)
# s.run()
# s.run_page('Item:Q382')
# exit(1)

# unparsed = caches.description.get()
# for rel in caches.reldescription.get():
#     pages = filter(lambda v: v.title == rel.full_title, unparsed)
#     wiki_pages = caches.descriptionParsed.parse_manual(pages)
#     for page in pages:
#         if 'members' in page["params"]:
#             print(f'<<<<<<<<<<<<< {page["title"]}')
#             print(f'{page["params"]["members"]}')
#             print(f'>>>>>>>>>>>>>')
#
# exit(1)

#
# unparsed = caches.description.get_new_pages(['Relation:multipolygon'])
# wiki_pages = caches.descriptionParsed.parse_manual(unparsed)

#
# caches.data_items.regenerate()
# caches.description.regenerate()
# caches.descriptionParsed.regenerate()
# caches.taginfo.regenerate()
# exit(1)

# caches.relroledescriptions.get()
# exit(1)

opts = {
    'throw': False
}
proc = Processor(opts, caches, site)

# proc.run('new')
# proc.run('REL|waterway')
# proc.run('relations')
# proc.run('relroles')
proc.run('items')
# proc.run([caches.itemByQid.get_item('Q16185')])
# proc.run('old')
# proc.run('taginfo_keys')
# proc.run('religion')
# proc.run([caches.itemByQid.get_item('Q6994')])

print('done!')
