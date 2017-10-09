import time
import logging
import datetime as dt
from datetime import datetime

import osmutils
from RdfHandler import RdfHandler
from osmium.replication.server import ReplicationServer
from sparql import Sparql

log = logging.getLogger('osm2rdf')

class RdfUpdateHandler(RdfHandler):
    def __init__(self, options):
        super(RdfUpdateHandler, self).__init__(options)
        self.deleteIds = []
        self.insertStatements = []
        self.pendingCounter = 0
        self.rdf_server = Sparql(self.options.rdf_url, self.options.dry_run)

    def finalize_object(self, obj, statements, obj_type):
        super(RdfUpdateHandler, self).finalize_object(obj, statements, obj_type)

        prefixed_id = osmutils.types[obj_type] + str(obj.id)

        self.deleteIds.append(prefixed_id)
        self.pendingCounter += 1

        if statements:
            self.pendingCounter += len(statements)
            self.insertStatements.extend([prefixed_id + ' ' + s + '.' for s in osmutils.toStrings(statements)])

        if self.pendingCounter > 2000:
            self.flush()

    def flush(self, seqid=0):
        sparql = ''

        if self.deleteIds:
            # Remove all staetments with these subjects
            sparql += '''
    DELETE {{ ?s ?p ?o . }}
    WHERE {{
      VALUES ?s {{ {0} }}
      ?s ?p ?o .
    }};'''.format(' '.join(self.deleteIds))

        if self.insertStatements:
            sparql += 'INSERT {{ {0} }} WHERE {{}};\n'.format('\n'.join(self.insertStatements))

        if seqid > 0:
            sparql += self.set_osm_schema_ver(seqid)

        if sparql:
            sparql = '\n'.join(osmutils.prefixes) + '\n\n' + sparql
            self.rdf_server.run('update', sparql)
            self.pendingCounter = 0
            self.deleteIds = []
            self.insertStatements = []
        elif self.pendingCounter != 0:
            # Safety check
            raise Exception('pendingCounter={0}'.format(self.pendingCounter))

    def get_osm_schema_ver(self, repserv):
        sparql = '''
PREFIX osmroot: <https://www.openstreetmap.org>
SELECT ?dummy ?ver ?mod WHERE {
 BIND( "42" as ?dummy )
 OPTIONAL { osmroot: schema:version ?ver . }
 OPTIONAL { osmroot: schema:dateModified ?mod . }
}
'''

        result = self.rdf_server.run('query', sparql)[0]

        if result['dummy']['value'] != '42':
            raise Exception('Failed to get a dummy value from RDF DB')

        try:
            return int(result['ver']['value'])
        except KeyError:
            pass

        try:
            ts = result['mod']['value']
        except KeyError:
            log.error('Neither schema:version nor schema:dateModified are set for <https://www.openstreetmap.org>')
            return None

        mod_date = osmutils.parse_date(ts)

        log.info('schema:dateModified={0}, shifting back and getting sequence ID'.format(mod_date))

        mod_date -= dt.timedelta(minutes=60)
        return repserv.timestamp_to_sequence(mod_date)

    def set_osm_schema_ver(self, ver):
        if self.last_timestamp.year < 2000:  # Something majorly wrong
            raise Exception('last_timestamp was not updated')

        return '''
DELETE {{ osmroot: schema:version ?v . }} WHERE {{ osmroot: schema:version ?v . }};
DELETE {{ osmroot: schema:dateModified ?m . }} WHERE {{ osmroot: schema:dateModified ?m . }};
INSERT {{
  osmroot: schema:version {0} .
  osmroot: schema:dateModified {1} .
}} WHERE {{}};
'''.format(ver, osmutils.format_date(self.last_timestamp))

    def run(self):
        repserv = ReplicationServer(self.options.osm_updater_url)
        last_time = datetime.utcnow()
        if self.options.seqid:
            seqid = self.options.seqid
        else:
            seqid = self.get_osm_schema_ver(repserv)

        log.info('Initial sequence id: {0}'.format(seqid))
        state = None
        last_seqid = seqid

        while True:

            # must not read data newer than the published sequence id
            # or we might end up reading partial data

            sleep = True
            if state is None:
                state = repserv.get_state_info()
                if state is not None and seqid + 2 < state.sequence:
                    log.info('Replication server has data up to #{0}'.format(state.sequence))

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
                log.info('Processed {0}, todo {1};  {2}'.format(
                    seqid - last_seqid - 1,
                    (state.sequence - seqid + 1 if state else '???'),
                    self.format_stats()))
                last_seqid = seqid - 1
                last_time = datetime.utcnow()

            if state is not None and seqid > state.sequence:
                state = None  # Refresh state

            if sleep:
                time.sleep(60)
