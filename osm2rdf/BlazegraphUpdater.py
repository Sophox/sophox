# Copyright Yuri Astrakhan <YuriAstrakhan@gmail.com>
import logging
import os

import argparse
import time
from pathlib import Path

from sparql import Sparql


class BlazegraphUpdater(object):
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
        parser.add_argument('-d', '--queries-dir', action='store', dest='queries_dir',
                            default=str(Path(os.path.dirname(__file__)) / 'maintenance'),
                            help='Do not modify RDF database.')
        parser.add_argument('-n', '--dry-run', action='store_true', dest='dry_run', default=False,
                            help='Do not modify RDF database.')
        opts = parser.parse_args()

        self.options = opts
        self.rdf_server = Sparql(opts.rdf_url, opts.dry_run)

    def run(self):
        dir = Path(self.options.queries_dir)
        while True:
            queries = {}
            for file in dir.glob('*.sparql'):
                with file.open() as f:
                    queries[file.stem] = f.read()

            suffix = '-test'
            for filename in sorted(queries.keys()):
                if filename.endswith(suffix):
                    if filename[:-len(suffix)] not in queries:
                        self.log.warning(f'File {filename} has no matching query (without the "{suffix}" suffix)')
                    continue
                testfile = filename + suffix
                if testfile in queries:
                    if not self.rdf_server.run('query', queries[testfile]):
                        self.log.info(f'Skipping {filename} (test is negative)')
                        continue
                self.log.info(f'Executing {filename}')
                self.rdf_server.run('update', queries[filename])
                self.log.info(f'Done running {filename}')

            time.sleep(60)


if __name__ == '__main__':
    BlazegraphUpdater().run()
