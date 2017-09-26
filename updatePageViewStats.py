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
                            default='http://localhost:9999/bigdata/sparql',
                            help='Host URL to upload data. Default: %(default)s')
        parser.add_argument('-n', '--dry-run', action='store_true', dest='dry_run', default=False,
                            help='Do not modify RDF database.')
        parser.add_argument('-b', '--go-backwards', action='store_true', dest='go_backwards', default=False,
                            help='At first, go back up to (maxfiles).')
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
            ver = self.get_pv_schema_ver()
            if ver is None:
                # Calculate last valid file
                ver = datetime.utcnow() + dt.timedelta(minutes=50)
                ver = datetime(ver.year, ver.month, ver.day, ver.hour, tzinfo=dt.timezone.utc)
            self.log.info('Processing {0} from {1}'.format(('backwards' if backwards else 'forward'), ver))
            stats, timestamp = await self.process_files(ver, backwards)
            backwards = False
            if timestamp is not None and len(stats) > 0:
                self.log.info('Updating {0} stats'.format(len(stats)))
                self.save_stats(stats, timestamp)
            self.log.info('Pausing...')
            time.sleep(1000)

    async def process_files(self, last_processed, backwards):
        stats = defaultdict(int)
        new_last = None

        conn = aiohttp.TCPConnector(limit=3)
        async with aiohttp.ClientSession(connector=conn) as session:
            futures = []
            for date in self.iterate_hours(last_processed, self.options.max_files, backwards):
                new_last = date
                url = self.stats_url.format(date)
                self.log.info('Processing {0}'.format(url))
                futures.append(self.process_file(session, url, stats))
            await asyncio.wait(futures)

        return stats, new_last

    def iterate_hours(self, last_processed, max_count, backwards=True):
        delta = dt.timedelta(hours=(-1 if backwards else 1))
        done = 0
        current = last_processed
        if not backwards:
            # Inclusive when going backwards, exclusive when going forward
            current += delta
        while (current > self.minimum_data_ts if backwards else current < datetime.now(dt.timezone.utc)):
            if done >= max_count:
                break
            yield current
            done += 1
            current += delta

    async def process_file(self, session, url, stats):
        # with async_timeout.timeout(30):
        async with session.get(url) as response:
            for line in gzip.decompress(await response.read()).splitlines():
                parts = line.decode('utf-8', 'strict').split(' ')
                page_url = self.page_url(parts[0], parts[1])
                if page_url:
                    stats[page_url] += int(parts[2])

    def get_pv_schema_ver(self):
        sparql = '''
PREFIX pvstat: {0}
SELECT ?dummy ?ver ?mod WHERE {{
 BIND( "42" as ?dummy )
 OPTIONAL {{ pvstat: schema:dateModified ?mod . }}
}}
'''.format(self.pvstat)

        result = self.rdf_server.run('query', sparql)[0]

        if result['dummy']['value'] != '42':
            raise Exception('Failed to get a dummy value from RDF DB')

        try:
            return osmutils.parse_date(result['mod']['value'])
        except KeyError:
            self.log.info('schema:dateModified is not set for {0}'.format(self.pvstat))
            return None

    def set_pv_schema_ver(self, timestamp):
        return '''
PREFIX pvstat: {0}
DELETE {{ pvstat: schema:dateModified ?m . }} WHERE {{ pvstat: schema:dateModified ?m . }};
INSERT {{ pvstat: schema:dateModified {1} . }} WHERE {{}};
'''.format(self.pvstat, osmutils.format_date(timestamp))

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
            if parts[0] != 'test2': # This is the only number-containing prefix so far
                self.log.error('Skipping unexpected language prefix "{0}"'.format(parts[0]))
            return None

        return osmutils.make_wiki_url(parts[0], site, title)

    def save_stats(self, stats, timestamp):

        # From https://stackoverflow.com/questions/46030514/update-or-create-numeric-counters-in-sparql-upsert/46042692

        unformatted_query = '''
PREFIX pvstat: {0}
DELETE {{ ?sitelink pvstat: ?outdated }}
INSERT {{ ?sitelink pvstat: ?updated }}
WHERE {{
    VALUES (?sitelink ?increment) {{ {1} }}
    OPTIONAL {{?sitelink pvstat: ?outdated}}
    BIND ((IF(BOUND(?outdated), ?outdated + ?increment, ?increment)) AS ?updated)
}}'''

        for keys in osmutils.chunks(stats.keys(), 2000):
            # (<...> 10) (<...> 15) ...
            values = ' '.join(['(' + k + ' ' + str(stats[k]) + ')' for k in keys])
            sparql = unformatted_query.format(self.pvstat, values)
            self.rdf_server.run('update', sparql)

        self.rdf_server.run('update', self.set_pv_schema_ver(timestamp))


if __name__ == '__main__':
    updater = UpdatePageViewStats()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(updater.run())
    loop.close()
