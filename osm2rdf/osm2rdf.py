#!/usr/bin/env python3

# Copyright Yuri Astrakhan <YuriAstrakhan@gmail.com>
# Some ideas were taken from https://github.com/waymarkedtrails/osgende/blob/master/tools/osgende-import

import argparse
import logging
import os

from RdfFileHandler import RdfFileHandler
from RdfUpdateHandler import RdfUpdateHandler

class Osm2rdf(object):
    def __init__(self):

        self.log = logging.getLogger('osm2rdf')
        self.log.setLevel(logging.INFO)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        self.log.addHandler(ch)

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
        parser.add_argument('-s', '--cache-strategy', action='store', dest='cacheType', choices=['sparse', 'dense'],
                            default='dense', help='Which node strategy to use (default: %(default)s)')
        parser.add_argument('-v', action='store_true', dest='verbose', default=False,
                            help='Enable verbose output.')

        subparsers = parser.add_subparsers(help='command', title='Commands', dest='command')

        parser_init = subparsers.add_parser('parse', help='Parses a PBF file into multiple .ttl.gz (Turtle files)')
        parser_init.add_argument('input_file', help='OSM input PBF file')
        parser_init.add_argument('output_dir', help='Output directory')
        parser_init.add_argument('--max-statements', dest='maxStatementsPerFile', action='store', type=int, default=20000,
                                 help='Maximum number of statements, in thousands, per output file. (default: %(default)s)')
        parser_init.add_argument('--workers', action='store', dest='worker_count', default=4, type=int,
                                 help='Number of worker threads to run (default: %(default)s)')

        parser_update = subparsers.add_parser('update', help='Update RDF database from OSM minute update files')
        parser_update.add_argument('--seqid', action='store', dest='seqid',
                                   default=None, type=int,
                                   help='Start updating from this sequence ID. By default, gets it from RDF server')
        parser_update.add_argument('--update-url', action='store', dest='osm_updater_url',
                                   default='http://planet.openstreetmap.org/replication/minute',
                                   help='Source of the minute data. Default: %(default)s')
        parser_update.add_argument('--host', action='store', dest='rdf_url',
                                   default='http://localhost:9999/bigdata/sparql',
                                   help='Host URL to upload data. Default: %(default)s')
        parser_update.add_argument('--max-download', action='store', dest='change_size', default=5 * 1024, type=int,
                                   help='Maxium size in kB for changes to download at once (default: %(default)s)')
        parser_update.add_argument('-n', '--dry-run', action='store_true', dest='dry_run', default=False,
                                   help='Do not modify RDF database.')


        opts = parser.parse_args()

        if not opts.command:
            self.parse_fail(parser, 'Missing command parameter')

        if opts.command == 'update':
            # if opts.addWayLoc:
            #     self.parse_fail(parser, 'Updating osmm:loc is not yet implemented, use --skip-way-geo parameter right after osm2rdf.py')

            if opts.addWayLoc and not opts.cacheFile:
                self.parse_fail(parser, 'Node cache file must be specified when updating with way centroids')

            if opts.cacheFile and not os.path.isfile(opts.cacheFile):
                self.parse_fail(parser, 'Node cache file does not exist. Was it specified during the "parse" phase?')

        self.options = opts
        getattr(self, opts.command)()

    @staticmethod
    def parse_fail(parser, info):
        print(info)
        parser.print_help()
        exit(1)

    def parse(self):
        input_file = self.options.input_file
        with RdfFileHandler(self.options) as handler:
            handler.run(input_file)
        self.log.info('done')

    def update(self):
        with RdfUpdateHandler(self.options) as handler:
            handler.run()


if __name__ == '__main__':
    Osm2rdf()
