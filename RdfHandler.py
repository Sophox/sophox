import re
import traceback
from urllib.parse import quote
from datetime import datetime, timezone

import osmutils
import osmium
import shapely.speedups
from shapely.wkb import loads

if shapely.speedups.available:
    shapely.speedups.enable()

# May contain letters, numbers anywhere, and -:_ symbols anywhere except first and last position
reSimpleLocalName = re.compile(r'^[0-9a-zA-Z_]([-:0-9a-zA-Z_]*[0-9a-zA-Z_])?$')
reWikidataKey = re.compile(r'(.:)?wikidata$')
reWikidataValue = re.compile(r'^Q[1-9][0-9]*$')
reWikipediaValue = re.compile(r'^([-a-z]+):(.+)$')


class RdfHandler(osmium.SimpleHandler):
    def __init__(self, options):
        osmium.SimpleHandler.__init__(self)
        self.options = options
        self.wkbfab = osmium.geom.WKBFactory()

        self.last_timestamp = datetime.fromtimestamp(0, timezone.utc)
        self.last_stats = ''
        self.added_nodes = 0
        self.added_rels = 0
        self.added_ways = 0
        self.skipped_nodes = 0
        self.skipped_rels = 0
        self.skipped_ways = 0
        self.deleted_nodes = 0
        self.deleted_rels = 0
        self.deleted_ways = 0

        self.types = {
            'n': 'osmnode:',
            'w': 'osmway:',
            'r': 'osmrel:',
        }

        self.prefixes = [
            'prefix wd: <http://www.wikidata.org/entity/>',
            'prefix xsd: <http://www.w3.org/2001/XMLSchema#>',
            'prefix geo: <http://www.opengis.net/ont/geosparql#>',
            'prefix schema: <http://schema.org/>',

            'prefix osmroot: <https://www.openstreetmap.org>',
            'prefix osmnode: <https://www.openstreetmap.org/node/>',
            'prefix osmway: <https://www.openstreetmap.org/way/>',
            'prefix osmrel: <https://www.openstreetmap.org/relation/>',
            'prefix osmt: <https://wiki.openstreetmap.org/wiki/Key:>',
            'prefix osmm: <https://www.openstreetmap.org/meta/>',
        ]

    def finalize_object(self, obj, statements, obj_type):
        if not obj.deleted and statements:
            timestamp = obj.timestamp
            if timestamp > self.last_timestamp:
                self.last_timestamp = timestamp

            statements.append('osmm:type "' + obj_type + '"')
            statements.append('osmm:version "' + str(obj.version) + '"^^xsd:integer')
            statements.append('osmm:user ' + osmutils.stringify(obj.user))
            statements.append('osmm:timestamp ' + osmutils.format_date(timestamp))
            statements.append('osmm:changeset "' + str(obj.changeset) + '"^^xsd:integer')

    @staticmethod
    def parse_tags(obj):
        if not obj.tags or obj.deleted:
            return None

        statements = []

        for tag in obj.tags:
            key = tag.k
            val = None
            if key == 'created_by':
                continue

            if not reSimpleLocalName.match(key):
                # Record any unusual tag name in a "osmm:badkey" statement
                statements.append('osmm:badkey ' + osmutils.stringify(key))
                continue

            if 'wikidata' in key:
                if reWikidataValue.match(tag.v):
                    val = 'wd:' + tag.v
            elif 'wikipedia' in key:
                match = reWikipediaValue.match(tag.v)
                if match:
                    # For some reason, sitelinks stored in Wikidata WDQS have spaces instead of '_'
                    # https://www.mediawiki.org/wiki/Wikibase/Indexing/RDF_Dump_Format#Sitelinks
                    val = '<https://' + match.group(1) + '.wikipedia.org/wiki/' + \
                          quote(match.group(2).replace(' ', '_'), safe=';@$!*(),/~:') + '>'

            if val is None:
                val = osmutils.stringify(tag.v)
            statements.append('osmt:' + key + ' ' + val)

        return statements

    def node(self, obj):
        statements = self.parse_tags(obj)
        if statements:
            self.parse_point(obj, statements)
            self.added_nodes += 1
        elif obj.deleted:
            self.deleted_nodes += 1
        else:
            self.skipped_nodes += 1

        self.finalize_object(obj, statements, 'n')

    def way(self, obj):
        statements = self.parse_tags(obj)
        if statements:
            statements.append('osmm:isClosed "' + ('true' if obj.is_closed() else 'false') + '"^^xsd:boolean')
            if self.options.addWayLoc:
                try:
                    wkb = self.wkbfab.create_linestring(obj)
                    point = loads(wkb, hex=True).representative_point()
                    self.add_location(point, statements)
                except:
                    if len(obj.nodes) == 1:
                        self.parse_point(obj, statements)
                    else:
                        self.add_error(statements, 'osmm:loc:error', "Unable to parse location data")
            self.added_ways += 1
        elif obj.deleted:
            self.deleted_ways += 1
        else:
            self.skipped_ways += 1
        self.finalize_object(obj, statements, 'w')

    def relation(self, obj):
        statements = self.parse_tags(obj)
        if obj.members:
            statements = statements if statements else []
            for mbr in obj.members:

                # Produce two statements - one to find all members of a relation,
                # and another to find the role of that relation
                #     osmrel:123  osmm:has    osmway:456
                #     osmrel:123  osmway:456  "inner"

                ref = self.types[mbr.type] + str(mbr.ref)
                statements.append('osmm:has ' + ref)
                statements.append(ref + ' ' + osmutils.stringify(mbr.role))

            self.added_rels += 1
        elif obj.deleted:
            self.deleted_rels += 1
        else:
            self.skipped_rels += 1

        self.finalize_object(obj, statements, 'r')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.flush()

    def flush(self):
        pass

    def format_stats(self):
        res = 'Added: {0}n {1}w {2}r;  Skipped: {3}n {4}w {5}r;  Deleted: {6}n {7}w {8}r'.format(
            self.added_nodes, self.added_ways, self.added_rels,
            self.skipped_nodes, self.skipped_ways, self.skipped_rels,
            self.deleted_nodes, self.deleted_ways, self.deleted_rels,
        )
        if self.last_stats == res:
            res = ''
        else:
            self.last_stats = res
        return res

    @staticmethod
    def format_date(datetime):
        # https://phabricator.wikimedia.org/T173974
        return '"' + datetime.isoformat().replace('+00:00', 'Z') + '"^^xsd:dateTime'

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

    def parse_point(self, obj, statements):
        try:
            wkb = self.wkbfab.create_point(obj)
            point = loads(wkb, hex=True)
            self.add_location(point, statements)
        except:
            self.add_error(statements, 'osmm:loc:error', "Unable to parse location data")

    @staticmethod
    def add_location(point, statements):
        spoint = str(point.x) + ' ' + str(point.y)
        if point.has_z:
            spoint += ' ' + str(point.z)
        statements.append('osmm:loc "Point(' + spoint + ')"^^geo:wktLiteral')

    @staticmethod
    def add_error(statements, tag, fallback_message):
        try:
            e = traceback.format_exc()
            statements.append(tag + ' ' + osmutils.stringify(e))
        except:
            statements.append(tag + ' ' + fallback_message)
