import gzip
import logging
import os
from RdfHandler import RdfHandler


class RdfFileHandler(RdfHandler):
    def __init__(self, seqid, options):
        super(RdfFileHandler, self).__init__(options)
        self.file_counter = 0
        self.length = None
        self.output = None
        self.seqid = seqid
        self.maxFileSize = self.options.maxFileSize*1024*1024


    def finalizeObject(self, obj, statements, type):
        super(RdfFileHandler, self).finalizeObject(obj, statements, type)

        if statements:
            if self.length is None or self.length > self.maxFileSize:
                self.create_output_file()
                header = '\n'.join(['@' + p + ' .' for p in self.prefixes]) + '\n\n'
                self.output.write(header)
                self.length = len(header)

            text = self.types[type] + str(id) + '\n' + ';\n'.join(statements) + '.\n\n'
            self.output.write(text)
            self.length += len(text)


    def create_output_file(self):
        self.close()
        os.makedirs(self.options.output_dir, exist_ok=True)
        filename = os.path.join(self.options.output_dir, 'osm-{0:06}.ttl.gz'.format(self.file_counter))

        # TODO switch to 'xt'
        logging.info('Exporting to {0}'.format(filename))
        self.output = gzip.open(filename, 'wt', compresslevel=5)
        self.file_counter += 1


    def close(self):
        if self.output:
            if self.seqid:
                self.output.write('\nosmroot: schema:version {0} .'.format(self.seqid))
            self.output.close()
            self.output = None
            logging.info('{0}'.format(self.formatStats()))

