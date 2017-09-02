from datetime import datetime, timezone

from osmutils import Bool, Date, Int, Str, Ref, Tag, Way, Point, loc_err, types
import osmium


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
        self.deleted_nodes = 0
        self.deleted_rels = 0
        self.deleted_ways = 0
        self.new_statements = 0

    def finalize_object(self, obj, statements, obj_type):
        if statements is not None and not obj.deleted:
            timestamp = obj.timestamp
            if timestamp > self.last_timestamp:
                self.last_timestamp = timestamp

            statements.append((Str, 'osmm:type', obj_type))
            statements.append((Int, 'osmm:version', obj.version))
            statements.append((Str, 'osmm:user', obj.user))
            statements.append((Date, 'osmm:timestamp', timestamp))
            statements.append((Int, 'osmm:changeset', obj.changeset))

            self.new_statements += len(statements)

    @staticmethod
    def parse_tags(tags):
        statements = []

        for tag in tags:
            key = tag.k
            if key == 'created_by':
                continue
            statements.append((Tag, key, tag.v))

        return statements

    def node(self, obj):
        statements = None
        if obj.deleted:
            self.deleted_nodes += 1
        else:
            tags = obj.tags
            if tags:
                statements = self.parse_tags(tags)
                if statements:
                    try:
                        geometry = self.wkbfab.create_point(obj)
                        statements.append((Point, 'osmm:loc', geometry))
                    except:
                        statements.append(loc_err())

            if statements:
                self.added_nodes += 1
            else:
                self.skipped_nodes += 1

        self.finalize_object(obj, statements, 'n')

    def way(self, obj):
        statements = None
        if obj.deleted:
            self.deleted_ways += 1
        else:
            statements = self.parse_tags(obj.tags)
            statements.append((Bool, 'osmm:isClosed', obj.is_closed()))
            if self.options.addWayLoc:
                try:
                    geometry = self.wkbfab.create_linestring(obj)
                    statements.append((Way, 'osmm:loc', geometry))
                except:
                    statements.append(loc_err())
            self.added_ways += 1

        self.finalize_object(obj, statements, 'w')

    def relation(self, obj):
        statements = None
        if obj.deleted:
            self.deleted_rels += 1
        else:
            statements = self.parse_tags(obj.tags)
            for mbr in obj.members:
                # Produce two statements - one to find all members of a relation,
                # and another to find the role of that relation
                #     osmrel:123  osmm:has    osmway:456
                #     osmrel:123  osmway:456  "inner"

                ref = types[mbr.type] + str(mbr.ref)
                statements.append((Ref, 'osmm:has', ref))
                statements.append((Str, ref, mbr.role))

            self.added_rels += 1

        self.finalize_object(obj, statements, 'r')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.flush()

    def flush(self):
        pass

    def format_stats(self):
        res = 'Statements: {0};  Added: {1}n {2}w {3}r;  Skipped: {4}n'.format(
            self.new_statements, self.added_nodes, self.added_ways, self.added_rels, self.skipped_nodes)

        if self.deleted_nodes or self.deleted_ways or self.deleted_rels:
            res += ';  Deleted: {0}n {1}w {2}r'.format(
                 self.deleted_nodes, self.deleted_ways, self.deleted_rels)

        if self.last_stats == res:
            res = ''
        else:
            self.last_stats = res
        return res

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
