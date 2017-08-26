import gzip
import logging
import os
from multiprocessing import Process, JoinableQueue
from RdfHandler import RdfHandler
import osmutils

log = logging.getLogger('osm2rdf')


def writerThread(id, queue, options):
    fileId = True
    while fileId is not None:
        fileId, data, last_timestamp = queue.get()
        if fileId is not None:
            write_file(id, options, fileId, data, last_timestamp)
        queue.task_done()
    log.debug('Wrk #{0} complete'.format(id))


def write_file(workerId, options, fileId, data, last_timestamp):
    os.makedirs(options.output_dir, exist_ok=True)
    filename = os.path.join(options.output_dir, 'osm-{0:06}.ttl.gz'.format(fileId))

    # TODO switch to 'xt'
    log.info('Wrk #{0}: Exporting to {1}'.format(workerId, filename))
    output = gzip.open(filename, 'wt', compresslevel=5)

    output.write(options.file_header)
    for item in data:
        typ, id, statements = item
        text = typ + str(id) + '\n' + ';\n'.join(osmutils.toStrings(statements)) + '.\n\n'
        output.write(text)

    if last_timestamp.year > 2000:  # Not min-year
        output.write(
            '\nosmroot: schema:dateModified {0} .'.format(osmutils.format_date(last_timestamp)))

    output.flush()
    output.close()
    log.info('Wrk #{0}: {1} done'.format(workerId, filename))


class RdfFileHandler(RdfHandler):
    def __init__(self, options):
        super(RdfFileHandler, self).__init__(options)
        self.job_counter = 0
        self.length = None
        self.output = None
        self.maxStatementCount = self.options.maxStatementsPerFile * 1000
        self.pending = []
        self.pendingStatements = 0
        self.options.file_header = '\n'.join(['@' + p + ' .' for p in self.prefixes]) + '\n\n'

        worker_count = 4

        self.queue = JoinableQueue(worker_count*2)

        self.writers = []
        for id in range(worker_count):
            process = Process(target=writerThread, args=(id, self.queue, self.options))
            self.writers.append(process)
            process.start()

    def finalize_object(self, obj, statements, obj_type):
        super(RdfFileHandler, self).finalize_object(obj, statements, obj_type)

        if statements:
            self.pending.append((self.types[obj_type], obj.id, statements))
            self.pendingStatements += 2 + len(statements)

            if self.pendingStatements > self.maxStatementCount:
                self.flush()

    def flush(self):
        if self.pendingStatements == 0:
            return

        self.queue.put((self.job_counter, self.pending, self.last_timestamp))

        self.job_counter += 1
        self.pending = []
        self.pendingStatements = 0

    def run(self, input_file):
        if self.options.addWayLoc:
            self.apply_file(input_file, locations=True, idx=self.get_index_string())
        else:
            self.apply_file(input_file)

        self.flush()

        # Send stop signal to each worker, and wait for all to stop
        for p in self.writers:
            self.queue.put((None, None, None))
        self.queue.close()
        self.queue.join()
        for p in self.writers:
            p.join()
