from pywikibot import Site as PWB_Site

import metabot
from metabot.utils import get_osm_site

site = get_osm_site()

caches = metabot.Caches(site, PWB_Site(), use_bot_limits=False)

# caches.description.regenerate()
# caches.descriptionParsed.regenerate()

print('done!')
