import gzip
import logging
import os
from RdfHandler import RdfHandler

logger = logging.getLogger('osm2rdf')

class RdfFileHandler(RdfHandler):
    def __init__(self, options):
        super(RdfFileHandler, self).__init__(options)
        self.file_counter = 0
        self.length = None
        self.output = None
        self.maxFileSize = self.options.maxFileSize * 1024 * 1024

    def finalize_object(self, obj, statements, obj_type):
        super(RdfFileHandler, self).finalize_object(obj, statements, obj_type)

        if statements:
            if self.length is None or self.length > self.maxFileSize:
                self.create_output_file()
                header = '\n'.join(['@' + p + ' .' for p in self.prefixes]) + '\n\n'
                self.output.write(header)
                self.length = len(header)

            text = self.types[obj_type] + str(id) + '\n' + ';\n'.join(statements) + '.\n\n'
            self.output.write(text)
            self.length += len(text)

    def create_output_file(self):
        self.close()
        os.makedirs(self.options.output_dir, exist_ok=True)
        filename = os.path.join(self.options.output_dir, 'osm-{0:06}.ttl.gz'.format(self.file_counter))

        # TODO switch to 'xt'
        logger.info('Exporting to {0}'.format(filename))
        self.output = gzip.open(filename, 'wt', compresslevel=5)
        self.file_counter += 1

    def close(self):
        if self.output:
            if self.last_timestamp.year > 2000: # Not min-year
                self.output.write(
                    '\nosmroot: schema:dateModified "{0}"^^xsd:dateTime .' .format(self.last_timestamp.isoformat()))
            self.output.close()
            self.output = None
            logger.info('{0}'.format(self.format_stats()))
