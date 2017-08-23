# Copyright Yuri Astrakhan <YuriAstrakhan@gmail.com>
# Some ideas were taken from https://github.com/waymarkedtrails/osgende/blob/master/tools/osgende-import

import argparse
from datetime import datetime
import logging
import os
import time

from RdfFileHandler import RdfFileHandler
from RdfUpdateHandler import RdfUpdateHandler
from osmium.replication.server import ReplicationServer

logger = logging.getLogger('osm2rdf')


class Osm2rdf(object):
    def __init__(self):

        logger.setLevel(logging.INFO)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(ch)

        # create the top-level parser
        parser = argparse.ArgumentParser(
            description='Imports and updates OSM data in an RDF database',
            usage='python3 %(prog)s [global_arguments] <command> [command_specific_arguments]'
        )

        parser.add_argument('--skip-way-geo', action='store_false', dest='addWayLoc',
                            help='Calculate way centroids (osmm:loc). Use with --nodes-file during "parse" '
                                 'if it is needed later with "update". If not used, ')
        parser.add_argument('-c', '--nodes-file', action='store', dest='cacheFile',
                            default=None, help='File to store node cache.')
        parser.add_argument('--cache-strategy', action='store', dest='cacheType', choices=['sparse', 'dense'],
                            default='dense', help='Which node strategy to use (default: %(default)s)')
        parser.add_argument('-v', action='store_true', dest='verbose', default=False,
                            help='Enable verbose output.')

        subparsers = parser.add_subparsers(help='command', title='Commands', dest='command')

        parser_init = subparsers.add_parser('parse', help='Parses a PBF file into multiple .ttl.gz (Turtle files)')
        parser_init.add_argument('input_file', help='OSM input PBF file')
        parser_init.add_argument('output_dir', help='Output directory')
        parser_init.add_argument('--file-size', dest='maxFileSize', action='store', type=int, default=512,
                                 help='Maximum size of the output file in uncompressed MB. (default: %(default)s)')

        parser_update = subparsers.add_parser('update', help='Update RDF database from OSM minute update files')
        parser_update.add_argument('--update-url', action='store', dest='osm_updater_url',
                                   default='http://planet.openstreetmap.org/replication/minute',
                                   help='Source of the minute data. Default: %(default)s')
        parser_update.add_argument('--host', action='store', dest='rdf_url',
                                   default='http://localhost:9999/bigdata/sparql',
                                   help='Host URL to upload data. Default: %(default)s')
        parser_update.add_argument('-S', action='store', dest='change_size', default=50 * 1024,
                                   type=int,
                                   help='Maxium size in kB for changes to download at once (default: %(default)s)')

        opts = parser.parse_args()

        if not opts.command:
            self.parse_fail(parser, 'Missing command parameter')

        if opts.command == 'update' and opts.addWayLoc and not opts.cacheFile:
            self.parse_fail(parser, 'Node cache file must be specified when updating with way centroids')

        if opts.command == 'update' and opts.cacheFile and not os.path.isfile(opts.cacheFile):
            self.parse_fail(parser, 'Node cache file does not exist. Was it specified during the "parse" phase?')

        self.options = opts
        getattr(self, opts.command)()

    @staticmethod
    def parse_fail(parser, info):
        print(info)
        parser.print_help()
        exit(1)

    def get_index_string(self):
        if self.options.addWayLoc:
            if self.options.cacheType == 'sparse':
                if self.options.cacheFile:
                    return 'sparse_file_array,' + self.options.cacheFile
                else:
                    return 'sparse_mem_array'
            else:
                if self.options.cacheFile:
                    return 'dense_file_array,' + self.options.cacheFile
                else:
                    return 'dense_mmap_array'
        return None

    def parse(self):
        input_file = self.options.input_file
        with RdfFileHandler(self.options) as handler:
            handler.apply_file(input_file, locations=self.options.addWayLoc, idx=self.get_index_string())

        logger.info('done')

    def update(self):
        seqid = None
        last_seqid = None
        last_time = None
        cought_up = False

        repserv = ReplicationServer(self.options.osm_updater_url)

        while True:
            with RdfUpdateHandler(self.options) as handler:
                if not seqid:
                    seqid = handler.get_osm_schema_ver(repserv)
                if not last_time:
                    last_time = datetime.utcnow()
                    last_seqid = seqid
                    logger.info('Initial sequence id: {0}'.format(seqid))

                seqid = repserv.apply_diffs(handler, seqid, 50 * 1024)
                if seqid is None or seqid == last_seqid:
                    logger.info('Sequence {0} is not available, sleeping'.format(last_seqid))
                    if seqid == last_seqid:
                        cought_up = True
                    time.sleep(60)
                else:
                    handler.set_osm_schema_ver(seqid)
                    now = datetime.utcnow()
                    sleep = cought_up and (seqid - last_seqid) == 1
                    logger.info('Processed up to {0}, {2:.2f}/s{3} {4}'.format(
                        now, seqid,
                        (seqid - last_seqid) / (now - last_time).total_seconds(),
                        ', waiting 60s' if sleep else '',
                        handler.format_stats()))
                    if sleep:
                        time.sleep(60)
                last_time = datetime.utcnow()
                last_seqid = seqid


if __name__ == '__main__':
    Osm2rdf()
