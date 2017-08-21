# Copyright Yuri Astrakhan <YuriAstrakhan@gmail.com>
# Some ideas were taken from https://github.com/waymarkedtrails/osgende/blob/master/tools/osgende-import

import argparse
import datetime as dt
import logging
import os
import time

from RdfFileHandler import RdfFileHandler
from RdfUpdateHandler import RdfUpdateHandler
from osmium import replication
from osmium.replication.server import ReplicationServer

class Osm2rdf(object):

    def __init__(self):

        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(levelname)s %(message)s')

        # create the top-level parser
        parser = argparse.ArgumentParser(
            description='Imports and updates OSM data in an RDF database',
            usage = 'python3 %(prog)s [global_arguments] <command> [command_specific_arguments]'
            )

        parser.add_argument('--skip-way-geo', action='store_false', dest='addWayLoc',
                            help='Calculate way centroids (osmm:loc). Use with --nodes-file during "parse" if it is needed later with "update". If not used, ')
        parser.add_argument('-c', '--nodes-file', action='store', dest='cacheFile',
                            default=None, help='File to store node cache.')
        parser.add_argument('--cache-strategy', action='store', dest='cacheType', choices=['sparse', 'dense'],
                            default='dense', help='Which node strategy to use (default: %(default)s)')
        parser.add_argument('-v', action='store_true', dest='verbose', default=False,
                            help='Enable verbose output.')
        parser.add_argument('--update-url', action='store', dest='osmUpdatesUrl',
                            default='http://planet.openstreetmap.org/replication/minute',
                            help='Source of the minute data. Default: %(default)s')

        subparsers = parser.add_subparsers(help='command', title='Commands', dest='command')

        parser_init = subparsers.add_parser('parse', help='Parses a PBF file into multiple .ttl.gz (Turtle files)')
        parser_init.add_argument('input_file', help='OSM input PBF file')
        parser_init.add_argument('output_dir', help='Output directory')
        parser_init.add_argument('--no-seqid', dest='getSeqId', action='store_false', help='Do not output sequence ID')
        parser_init.add_argument('--file-size', dest='maxFileSize', action='store', type=int, default=512,
                                 help='Maximum size of the output file in uncompressed MB. (default: %(default)s)')

        parser_update = subparsers.add_parser('update', help='Update RDF database from OSM minute update files')
        parser_update.add_argument('--host', action='store', dest='blazegraphUrl',
                                   default='http://localhost:9999/bigdata/sparql',
                                   help='Host URL to upload data. Default: %(default)s')
        parser_update.add_argument('-S', action='store', dest='change_size', default=50*1024,
                                   type=int, help='Maxium size in kB for changes to download at once (default: %(default)s)')

        opts = parser.parse_args()

        if not opts.command:
            self.parse_fail(parser, 'Missing command parameter')

        if opts.command == 'update' and opts.addWayLoc and not opts.cacheFile:
            self.parse_fail(parser, 'Node cache file must be specified when updating with way centroids')

        if opts.command == 'update' and opts.cacheFile and not os.path.isfile(opts.cacheFile):
            self.parse_fail(parser, 'Node cache file does not exist. Was it specified during the "parse" phase?')

        self.options = opts
        getattr(self, opts.command)()

    def parse_fail(self, parser, info):
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
        if self.options.getSeqId:
            repserv = ReplicationServer(self.options.osmUpdatesUrl)
            logging.info('Getting start date from {0}'.format(input_file))
            start_date = replication.newest_change_from_file(input_file)
            if start_date is None:
                raise ValueError("Cannot determine timestamp from the given pbf file")
            logging.info('Start date={0}, shifting back and getting sequence ID'.format(start_date))
            start_date -= dt.timedelta(minutes=60)
            seqid = repserv.timestamp_to_sequence(start_date)
            logging.info('Sequence ID={0}'.format(seqid, input_file))
        else:
            logging.info('Sequence ID is not calculated, and will not be stored in the output files')
            seqid = None

        with RdfFileHandler(seqid, self.options) as handler:
            handler.apply_file(input_file, locations=self.options.addWayLoc, idx=self.get_index_string())

        logging.info('done')

    def update(self):
        seqid = None
        lastSeqid = None
        lastTime = None
        isUpToDate = False

        # start_date = dt.datetime.strptime(sys.argv[1], '%y%m%d').replace(tzinfo=dt.timezone.utc)
        # start_date -= dt.timedelta(days=1)
        # seqid = repserv.timestamp_to_sequence(start_date)

        repserv = ReplicationServer(self.options.osmUpdatesUrl)

        while True:
            with RdfUpdateHandler(self.options) as handler:
                if not seqid:
                    seqid = handler.getOsmSchemaVer()
                if not lastTime:
                    lastTime = dt.datetime.now()
                    lastSeqid = seqid
                    logging.info('Initial sequence id: {0}'.format(lastTime, seqid))

                seqid = repserv.apply_diffs(handler, seqid, 50*1024)
                if seqid is None or seqid == lastSeqid:
                    lastTime = dt.datetime.now()
                    logging.info('Sequence {0} is not available, sleeping'.format(lastTime, lastSeqid))
                    if seqid == lastSeqid:
                        isUpToDate = True
                    time.sleep(60)
                else:
                    handler.setOsmSchemaVer(seqid)
                    now = dt.datetime.now()
                    sleep = isUpToDate and (seqid - lastSeqid) == 1
                    logging.info('Processed up to {0}, {2:.2f}/s{3} {4}'.format(
                        now, seqid,
                        (seqid-lastSeqid)/(now-lastTime).total_seconds(),
                        ', waiting 60s' if sleep else '',
                        handler.formatStats()))
                    if sleep:
                        time.sleep(60)
                lastTime = dt.datetime.now()
                lastSeqid = seqid


if __name__ == '__main__':
    Osm2rdf()

