# Copyright Yuri Astrakhan <YuriAstrakhan@gmail.com>
import argparse
import asyncio
import datetime as dt
import gzip
import logging
import time
from collections import defaultdict
from datetime import datetime

import aiohttp
# import async_timeout
import re
import shapely.speedups

import osmutils
from sparql import Sparql

if shapely.speedups.available:
    shapely.speedups.enable()

reWikiLanguage = re.compile(r'^[-a-z]+$')


class UpdatePageViewStats(object):
    def __init__(self):

        self.log = logging.getLogger('osm2rdf')
        self.log.setLevel(logging.INFO)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        self.log.addHandler(ch)

        # create the top-level parser
        parser = argparse.ArgumentParser(
            description='Download and update stats',
            usage='python3 %(prog)s [options]'
        )

        parser.add_argument('--host', action='store', dest='rdf_url',
                            default='http://localhost:9999/bigdata/namespace/wdq/sparql',
                            help='Host URL to upload data. Default: %(default)s')
        parser.add_argument('-n', '--dry-run', action='store_true', dest='dry_run', default=False,
                            help='Do not modify RDF database.')
        parser.add_argument('-b', '--go-backwards', action='store_true', dest='go_backwards', default=False,
                            help='Go back up to (maxfiles) and exit')
        parser.add_argument('-m', '--maxfiles', action='store', dest='max_files', default=1, type=int,
                            help='Maximum number of pageview stat files to process at once')
        opts = parser.parse_args()

        self.options = opts
        self.rdf_server = Sparql(opts.rdf_url, opts.dry_run)
        self.pvstat = '<https://dumps.wikimedia.org/other/pageviews/>'
        self.stats_url = 'https://dumps.wikimedia.org/other/pageviews/{0:%Y}/{0:%Y-%m}/pageviews-{0:%Y%m%d-%H}0000.gz'

        # oldest file is https://dumps.wikimedia.org/other/pageviews/2015/2015-05/pageviews-20150501-010000.gz
        self.minimum_data_ts = datetime(2015, 5, 1, tzinfo=dt.timezone.utc)

    async def run(self):
        backwards = self.options.go_backwards
        while True:
            ver = osmutils.query_status(self.rdf_server, f'{self.pvstat}')
            if ver is None:
                self.log.info(f'schema:dateModified is not set for {self.pvstat}')
                # Calculate last valid file
                ver = datetime.utcnow() + dt.timedelta(minutes=50)
                ver = datetime(ver.year, ver.month, ver.day, ver.hour, tzinfo=dt.timezone.utc)
            self.log.info(f'Processing {"backwards" if backwards else "forward"} from {ver}')
            stats, timestamp = await self.process_files(ver, backwards)
            if timestamp is not None and len(stats) > 0:
                self.log.info(f'Updating {len(stats)} stats')
                self.save_stats(stats, timestamp)
            if backwards:
                # Do a single iteration only
                return
            self.log.info('Pausing...')
            time.sleep(1000)

    async def process_files(self, last_processed, backwards):
        stats = defaultdict(int)
        new_last = None

        conn = aiohttp.TCPConnector(limit=3)
        timeout = aiohttp.ClientTimeout(total=None, connect=None, sock_read=60, sock_connect=60)
        async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
            futures = []
            for date in self.iterate_hours(last_processed, self.options.max_files, backwards):
                futures.append(self.process_file(session, date, stats))
            done, _ = await asyncio.wait(futures)

        for fut in done:
            date, ok = fut.result()
            # always find the latest possible timestamp even if going backwards
            if ok and (new_last is None or date > new_last):
                new_last = date

        return stats, new_last

    def iterate_hours(self, last_processed, max_count, backwards=True):
        delta = dt.timedelta(hours=(-1 if backwards else 1))
        done = 0
        current = last_processed
        if not backwards:
            # Inclusive when going backwards, exclusive when going forward
            current += delta
        while current > self.minimum_data_ts if backwards else current < datetime.now(dt.timezone.utc):
            if done >= max_count:
                break
            yield current
            done += 1
            current += delta

    async def process_file(self, session, date, stats):
        url = self.stats_url.format(date)
        async with session.get(url) as response:
            start = datetime.utcnow()
            if response.status != 200:
                self.log.warning(f'Url {url} returned {response.status}')
                return date, False
            for line in gzip.decompress(await response.read()).splitlines():
                try:
                    parts = line.decode('utf-8', 'strict').split(' ')
                    page_url = self.page_url(parts[0], parts[1])
                    if page_url:
                        stats[page_url] += int(parts[2])
                except:
                    self.log.error(f'Error parsing {url} line "{line}"')
            self.log.info(f'Finished processing {url} in {(datetime.utcnow() - start).total_seconds()} seconds')
        return date, True

    def page_url(self, prefix, title):
        parts = prefix.split('.', 1)

        if len(parts) == 1:
            site = '.wikipedia.org/wiki/'
        # elif parts[1] == 'b':
        #     site = '.wikibooks.org/wiki/'
        # elif parts[1] == 'd':
        #     site = '.wiktionary.org/wiki/'
        # elif parts[1] == 'n':
        #     site = '.wikinews.org/wiki/'
        # elif parts[1] == 'q':
        #     site = '.wikiquote.org/wiki/'
        # elif parts[1] == 's':
        #     site = '.wikisource.org/wiki/'
        # elif parts[1] == 'v':
        #     site = '.wikiversity.org/wiki/'
        # elif parts[1] == 'voy':
        #     site = '.wikivoyage.org/wiki/'
        else:
            return None

        if not reWikiLanguage.match(parts[0]):
            if parts[0] != 'test2':  # This is the only number-containing prefix so far
                self.log.error(f'Skipping unexpected language prefix "{parts[0]}"')
            return None

        return osmutils.make_wiki_url(parts[0], site, title)

    def save_stats(self, stats, timestamp):

        # From https://stackoverflow.com/questions/46030514/update-or-create-numeric-counters-in-sparql-upsert/46042692

        for keys in osmutils.chunks(stats.keys(), 2000):
            # (<...> 10) (<...> 15) ...
            values = ' '.join(['(' + k + ' ' + str(stats[k]) + ')' for k in keys])
            sparql = f'''
PREFIX pvstat: {self.pvstat}
DELETE {{ ?sitelink pvstat: ?outdated }}
INSERT {{ ?sitelink pvstat: ?updated }}
WHERE {{
    VALUES (?sitelink ?increment) {{ {values} }}
    OPTIONAL {{?sitelink pvstat: ?outdated}}
    BIND ((IF(BOUND(?outdated), ?outdated + ?increment, ?increment)) AS ?updated)
}}'''
            self.rdf_server.run('update', sparql)

        self.rdf_server.run('update', osmutils.set_status_query(f'{self.pvstat}', timestamp))


if __name__ == '__main__':
    updater = UpdatePageViewStats()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(updater.run())
    loop.close()
