from pathlib import Path

from pywikiapi import AttrDict
from pywikibot import Site as PWB_Site
from pywikibot.data.api import LoginManager

from metabot.OsmFamily import OsmFamily
from metabot.Properties import *
from metabot import Caches, Q_REGION_INSTANCE
from metabot.Processor import Processor
from metabot.utils import get_osm_site

site = get_osm_site()
use_bot_limits = False
pb_site = PWB_Site(fam=OsmFamily(), user='Yurikbot')
caches = Caches(site, pb_site, use_bot_limits=False)

# if not pb_site.logged_in():
#     password = Path('./password').read_text().strip()
#     LoginManager(site=pb_site, password=password).login()
#     print('Logged in!')
# else:
#     print('Already logged in')


# caches.data_items.regenerate()
# caches.description.regenerate()
# caches.descriptionParsed.regenerate()
# caches.taginfo.regenerate()
# exit(1)

opts = {
    # 'throw': False
}
proc = Processor(opts, caches, site, pb_site)

# proc.run('religion')
# proc.run('new')
# proc.run('items')
# proc.run('old')
# proc.run('taginfo_keys')
# proc.run('autogen_keys')
proc.run([caches.itemByQid.get_item('Q103')])

print('done!')
