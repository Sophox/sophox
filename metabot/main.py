from time import sleep

if __name__ != "__main__":
    raise Exception()

from pathlib import Path
from pywikibot import Site as PWB_Site
from metabot.OsmFamily import OsmFamily
from metabot import Caches, P_INSTANCE_OF, Q_KEY, P_KEY_TYPE, Q_ENUM_KEY_TYPE, P_KEY_ID
from metabot.Processor import Processor
from metabot.TagInfoDb import TagInfoDb
from metabot.utils import get_osm_site, parse_wiki_page_title, batches

site = get_osm_site()
use_bot_limits = False
pb_site = PWB_Site(fam=OsmFamily(), user='Yurikbot')
caches = Caches(site, pb_site, use_bot_limits=False)

password = Path('./password').read_text().strip()
site.login(user='Yurikbot', password=password, on_demand=True)


# caches.mapfeatures.regenerate()
# exit(1)

# caches.data_items.regenerate()
# caches.description.regenerate()
# caches.descriptionParsed.regenerate()
# caches.taginfo.regenerate()
# caches.tagInfoDb.regenerate()

opts = {
    # 'throw': False,
    'force_all': True,
}
proc = Processor(opts, caches, site)

# proc.run(('Tag', 'leisure=bleachers'))
# proc.run('taginfo-tags')
# proc.run('new')
# proc.run('items')
# proc.run('relations')
# proc.run('relroles')
proc.run([
    caches.itemByQid.get_item('Q7676'),
])
# proc.del_params()
# proc.run(('Key', 'yh:WIDTH_RANK'))
# proc.run(('Tag', 'highway=path'))

print('done!')
