from pathlib import Path

from pywikiapi import AttrDict
from pywikibot import Site as PWB_Site
from pywikibot.data.api import LoginManager

from metabot.OsmFamily import OsmFamily
from metabot.Properties import *
from metabot import Caches
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


caches.data_items.regenerate()
# caches.description.regenerate()
# caches.descriptionParsed.regenerate()
# exit(1)







# for qid in list(caches.contributed.data.keys()):
#     caches.contributed(qid, True)
# exit(1)







def fix_sitelinks_and_ids(opts=None):
    if not opts: opts = {}
    opts = {
        'throw': True,
        'props': False,
        'ignore_qid': False,
        'overwrite_user_labels_en': True,
        'overwrite_user_labels': False,
        'overwrite_user_descriptions': False,
        'overwrite_user_claims': True,
        **opts
    }

    proc = Processor(opts, caches, site, pb_site)
    # proc.run('cycle_network')
    proc.run('new')
    proc.run('items')
    proc.run('old')
    proc.run('autogen_keys')
    # proc.run([caches.itemByQid.get_item('Q7684')])


fix_sitelinks_and_ids({
    # 'throw': False,
    'props': {
        P_INSTANCE_OF.id,
        P_IMAGE.id,
        P_OSM_IMAGE.id,
        P_USED_ON.id,
        P_NOT_USED_ON.id,
        P_STATUS.id,
        P_KEY_TYPE.id,
        P_TAG_KEY.id,
        P_REF_URL.id,
        P_KEY_ID.id,
        P_TAG_ID.id,
        P_ROLE_ID.id,
        P_GROUP.id,
    },
    # 'ignore_qid': {
    #     'Q104',
    #     'Q108',
    #     'Q1191',
    #     'Q171',
    #     'Q3',
    #     'Q4',
    #     'Q4666',
    #     'Q501',
    #     'Q6',
    #     'Q890',
    #     'Q261',
    #     'Q7565',
    # }
})

print('done!')
