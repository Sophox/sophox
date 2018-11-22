import gzip
import logging
import os
from multiprocessing import Process, Queue
from datetime import datetime
import osmutils
from RdfHandler import RdfHandler

log = logging.getLogger('osm2rdf')


def writer_thread(worker_id, queue, options):
    while True:
        ts, file_id, data, last_timestamp, stats_str = queue.get()
        if ts is None:
            log.debug(f'Exiting worker #{worker_id}')
            return

        write_file(ts, worker_id, options, file_id, data, last_timestamp, stats_str)


def write_file(ts_enqueue, worker_id, options, file_id, data, last_timestamp, stats_str):
    start = datetime.now()

    os.makedirs(options.output_dir, exist_ok=True)
    filename = os.path.join(options.output_dir, f'osm-{file_id:06}.ttl.gz')
    output = gzip.open(filename, 'xt', compresslevel=3)

    output.write(options.file_header)
    for item in data:
        typ, qid, statements = item
        text = typ + str(qid) + '\n' + ';\n'.join(osmutils.toStrings(statements)) + '.\n\n'
        output.write(text)

    if last_timestamp.year > 2000:  # Not min-year
        output.write(f'\nosmroot: schema:dateModified {osmutils.format_date(last_timestamp)} .')

    output.flush()
    output.close()

    seconds = (datetime.now() - start).total_seconds()
    waited = (start - ts_enqueue).total_seconds()
    log.info(f'{filename} done in {seconds}s, {waited}s wait, by worker #{worker_id}: {stats_str}')


class RdfFileHandler(RdfHandler):
    def __init__(self, options):
        super(RdfFileHandler, self).__init__(options)
        self.job_counter = 1
        self.length = None
        self.output = None
        self.maxStatementCount = self.options.maxStatementsPerFile * 1000
        self.pending = []
        self.pendingStatements = 0
        self.options.file_header = '\n'.join(['@' + p + ' .' for p in osmutils.prefixes]) + '\n\n'

        # Queue should contain at most 1 item, making the total number of batches in memory to be
        # number_of_workers + one_in_query + one_being_assembled_by_main_thread
        self.queue = Queue(1)

        self.writers = []
        for worker_id in range(options.worker_count):
            process = Process(target=writer_thread, args=(worker_id, self.queue, self.options))
            self.writers.append(process)
            process.start()

    def finalize_object(self, obj, statements, obj_type):
        super(RdfFileHandler, self).finalize_object(obj, statements, obj_type)

        if statements:
            self.pending.append((osmutils.types[obj_type], obj.id, statements))
            self.pendingStatements += 2 + len(statements)

            if self.pendingStatements > self.maxStatementCount:
                self.flush()

    def flush(self):
        if self.pendingStatements == 0:
            return

        stats_str = self.format_stats()
        self.queue.put((datetime.now(), self.job_counter, self.pending, self.last_timestamp, stats_str))

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
        for _ in self.writers:
            self.queue.put((None, None, None, None, None))
        self.queue.close()
        for p in self.writers:
            p.join()
