from time import sleep

if __name__ != "__main__":
    raise Exception()

from os import environ
from pathlib import Path
from pywikibot import Site as PWB_Site
from metabot.OsmFamily import OsmFamily
from metabot import Caches
from metabot.Processor import Processor
from metabot.utils import get_osm_site, get_recently_changed_items
from datetime import datetime, timedelta

try:
    process_start = datetime.utcnow()
    last_change = process_start - timedelta(minutes=5)

    site = get_osm_site()
    use_bot_limits = False
    pwb_site = PWB_Site(fam=OsmFamily(), user='Yurikbot')
    password = environ.get('YURIKBOT_PASSWORD') or Path('./password').read_text().strip()
    site.login(user='Yurikbot', password=password, on_demand=True)

    caches = Caches(site, pwb_site, use_bot_limits=False)
    caches.data_items.regenerate()
    caches.description.regenerate()
    caches.descriptionParsed.regenerate()

    proc = Processor(dict(throw=False), caches, site)
    proc.run('new')
    proc.run('items')

    grace_period = 3 # minutes
    run_every = 1 # minutes

    proc = Processor(dict(throw=False, force_all=True), caches, site)
    while True:
        last_change, todo_items = get_recently_changed_items(site, last_change, grace_period, caches)
        if todo_items:
            proc.run(todo_items)

        if (datetime.utcnow() - process_start) > timedelta(hours=12):
            print('Have been running for a while, exiting')
            exit(-1)

        sleep(run_every*60)
except Exception as err:
    print(f'\n\n!!!!!  CRASH !!!!!\n\n{err}')
    exit(0)
