import time
import logging
import datetime as dt
from datetime import datetime

import osmutils
from utils import set_status_query, query_status
from RdfHandler import RdfHandler
from osmium.replication.server import ReplicationServer
from sparql import Sparql

log = logging.getLogger('osm2rdf')


class RdfUpdateHandler(RdfHandler):
    def __init__(self, options):
        super(RdfUpdateHandler, self).__init__(options)
        self.pending = {}
        self.pendingCounter = 0
        self.rdf_server = Sparql(self.options.rdf_url, self.options.dry_run)

    def finalize_object(self, obj, statements, obj_type):
        super(RdfUpdateHandler, self).finalize_object(obj, statements, obj_type)

        prefixed_id = osmutils.types[obj_type] + str(obj.id)

        if prefixed_id in self.pending:
            # Not very efficient, but if the same object is updated more than once within
            # the same batch, it does not get deleted because all deletes happen first
            self.flush()

        if statements:
            self.pending[prefixed_id] = [prefixed_id + ' ' + s + '.' for s in osmutils.toStrings(statements)]
            self.pendingCounter += len(statements)
        else:
            self.pending[prefixed_id] = False
            self.pendingCounter += 1

        if self.pendingCounter > 5000:
            self.flush()

    def flush(self, seqid=0):
        sparql = ''

        if self.pending:
            # Remove all statements with these subjects
            sparql += f'''
DELETE {{ ?s ?p ?o . }}
WHERE {{
  VALUES ?s {{ {' '.join(self.pending.keys())} }}
  ?s ?p ?o .
  FILTER (osmm:task != ?p)
}};'''
            # flatten list of lists, and if sublist is truthy, use it
            insert_sparql = '\n'.join([v for sublist in self.pending.values() if sublist for v in sublist])
            if insert_sparql:
                sparql += f'INSERT {{ {insert_sparql} }} WHERE {{}};\n'

        if seqid > 0:
            if self.last_timestamp.year < 2000:  # Something majorly wrong
                raise Exception('last_timestamp was not updated')
            sparql += set_status_query('osmroot:', self.last_timestamp, 'version', seqid)

        if sparql:
            sparql = '\n'.join(osmutils.prefixes) + '\n\n' + sparql
            self.rdf_server.run('update', sparql)
            self.pendingCounter = 0
            self.pending = {}
        elif self.pendingCounter != 0:
            # Safety check
            raise Exception(f'pendingCounter={self.pendingCounter}')

    def get_osm_schema_ver(self, repserv):
        result = query_status(self.rdf_server, '<https://www.openstreetmap.org>', 'version')

        ver = result['version']
        if ver is not None:
            log.info(f'schema:version={ver}')
            return int(ver)

        mod_date = result['dateModified']
        if mod_date is not None:
            log.info(f'schema:dateModified={mod_date}, shifting back and getting sequence ID')
            mod_date -= dt.timedelta(minutes=60)
            return repserv.timestamp_to_sequence(mod_date)

        log.error('Neither schema:version nor schema:dateModified are set for <https://www.openstreetmap.org>')
        return None

    def run(self):
        repserv = ReplicationServer(self.options.osm_updater_url)
        last_time = datetime.utcnow()
        if self.options.seqid:
            seqid = self.options.seqid
        else:
            seqid = self.get_osm_schema_ver(repserv)
            if seqid is None:
                raise Exception('Unable to determine sequence ID')

        log.info(f'Initial sequence id: {seqid}')
        state = None
        last_seqid = seqid

        while True:

            # must not read data newer than the published sequence id
            # or we might end up reading partial data

            sleep = True
            if state is None:
                state = repserv.get_state_info()
                if state is not None and seqid + 2 < state.sequence:
                    log.info(f'Replication server has data up to #{state.sequence}')

            if state is not None and seqid <= state.sequence:
                try:
                    diffdata = repserv.get_diff_block(seqid)
                except:
                    diffdata = ''

                # We assume there are no empty diff files
                if len(diffdata) > 0:
                    log.debug("Downloaded change %d. (size=%d)" % (seqid, len(diffdata)))

                    if self.options.addWayLoc:
                        self.apply_buffer(diffdata, repserv.diff_type, locations=True, idx=self.get_index_string())
                    else:
                        self.apply_buffer(diffdata, repserv.diff_type)

                    self.flush(seqid)

                    seqid += 1
                    sleep = False

            seconds_since_last = (datetime.utcnow() - last_time).total_seconds()
            if seconds_since_last > 60:
                log.info(f'Processed {seqid - last_seqid - 1}, ' +
                         f'todo {(state.sequence - seqid + 1 if state else "???")};  {self.format_stats()}')
                last_seqid = seqid - 1
                last_time = datetime.utcnow()

            if state is not None and seqid > state.sequence:
                state = None  # Refresh state

            if sleep:
                time.sleep(60)
