if __name__ != "__main__":
    raise Exception()

from pathlib import Path
from pywikibot import Site as PWB_Site
from metabot.OsmFamily import OsmFamily
from metabot import Caches
from metabot.Processor import Processor
from metabot.utils import get_osm_site

site = get_osm_site()
use_bot_limits = False
pb_site = PWB_Site(fam=OsmFamily(), user='Yurikbot')
caches = Caches(site, pb_site, use_bot_limits=False)

password = Path('./password').read_text().strip()
site.login(user='Yurikbot', password=password, on_demand=True)

caches.data_items.regenerate()
caches.description.regenerate()
caches.descriptionParsed.regenerate()

proc = Processor({
    'throw': False,
}, caches, site)

proc.run('new')
proc.run('items')

print('done!')
