import time
import requests
import logging
import datetime as dt
from datetime import datetime
from RdfHandler import RdfHandler
from osmium.replication.server import ReplicationServer

log = logging.getLogger('osm2rdf')

class RdfUpdateHandler(RdfHandler):
    def __init__(self, options):
        super(RdfUpdateHandler, self).__init__(options)
        self.deleteIds = []
        self.updatedIds = []
        self.insertStatements = []

    def finalize_object(self, obj, statements, obj_type):
        super(RdfUpdateHandler, self).finalize_object(obj, statements, obj_type)

        prefixed_id = self.types[obj_type] + str(obj.id)
        if obj.deleted:
            self.deleteIds.append(prefixed_id)
        else:
            self.deleteIds.append(prefixed_id)
        if statements:
            self.insertStatements.extend([prefixed_id + ' ' + s + '.' for s in statements])

        if len(self.deleteIds) > 1000 or len(self.updatedIds) > 1000 or len(self.insertStatements) > 2000:
            self.flush()

    def flush(self):
        if not self.deleteIds and not self.insertStatements:
            return

        sparql = '\n'.join(self.prefixes) + '\n\n'

        if not self.options.addWayLoc:
            # For updates, delete everything except the osmm:loc tag
            sparql += '''
DELETE {{ ?s ?p ?o . }}
WHERE {{
  VALUES ?s {{ {0} }}
  ?s ?p ?o .
  FILTER ( ?p != osmm:loc )
}};'''.format(' '.join(self.updatedIds))

        else:
            # Process updates and deletes the same
            self.deleteIds += self.updatedIds

        # Remove all staetments with these subjects
        sparql += '''
DELETE {{ ?s ?p ?o . }}
WHERE {{
  VALUES ?s {{ {0} }}
  ?s ?p ?o .
}};'''.format(' '.join(self.deleteIds))

        if self.insertStatements:
            sparql += 'INSERT { ' + '\n'.join(self.insertStatements) + ' } WHERE {};\n'
        self.update_rdf(sparql)
        self.deleteIds = []
        self.insertStatements = []

    def get_osm_schema_ver(self, repserv):
        sparql = '''
PREFIX osmroot: <https://www.openstreetmap.org>
SELECT ?dummy ?ver ?mod WHERE {
 BIND( "42" as ?dummy )
 OPTIONAL { osmroot: schema:version ?ver . }
 OPTIONAL { osmroot: schema:dateModified ?mod . }
}
'''

        r = requests.get(self.options.rdf_url,
                         {'query': sparql},
                         headers={'Accept': 'application/sparql-results+json'})
        if not r.ok:
            raise Exception(r.text)
        result = r.json()['results']['bindings'][0]
        if result['dummy']['value'] != '42':
            raise Exception('Failed to get a dummy value from RDF DB')

        try:
            return int(result['ver']['value'])
        except KeyError:
            pass

        try:
            mod_date = datetime.strptime(result['mod']['value'], "%Y-%m-%dT%H:%M:%S.%fZ") \
                .replace(tzinfo=dt.timezone.utc)
        except KeyError:
            log.error('Neither schema:version nor schema:dateModified are set for <https://www.openstreetmap.org>')
            return None

        log.info('schema:dateModified={0}, shifting back and getting sequence ID'.format(mod_date))

        mod_date -= dt.timedelta(minutes=60)
        return repserv.timestamp_to_sequence(mod_date)

    def set_osm_schema_ver(self, ver):
        if self.last_timestamp.year < 2000:  # Something majorly wrong
            raise Exception('last_timestamp was not updated')

        sparql = '''
PREFIX osmroot: <https://www.openstreetmap.org>
DELETE {{ osmroot: schema:version ?v . }} WHERE {{ osmroot: schema:version ?v . }};
DELETE {{ osmroot: schema:dateModified ?m . }} WHERE {{ osmroot: schema:dateModified ?m . }};
INSERT {{
  osmroot: schema:version {0} .
  osmroot: schema:dateModified {1} .
}} WHERE {{}};
'''.format(ver, self.format_date(self.last_timestamp))

        self.update_rdf(sparql)

    def update_rdf(self, sparql):
        if not self.options.dry_run:
            r = requests.post(self.options.rdf_url, data={'update': sparql})
            if not r.ok:
                raise Exception(r.text)

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

                    self.flush()
                    self.set_osm_schema_ver(seqid)

                    seqid += 1
                    sleep = False

            seconds_since_last = (datetime.utcnow() - last_time).total_seconds()
            if seconds_since_last > 60:
                log.info('Processed up to #{0} out of #{1}, {2:.2f}/s, {3}'.format(
                    seqid - 1, (state.sequence if state else '???'),
                    (seqid - last_seqid - 1) / seconds_since_last,
                    self.format_stats()))
                last_seqid = seqid - 1
                last_time = datetime.utcnow()

            if state is not None and seqid > state.sequence:
                state = None # Refresh state

            if sleep:
                time.sleep(60)
