from datetime import datetime, timezone

from osmutils import Bool, Date, Int, Str, Ref, Tag, Way, Point, loc_err, types
import osmium


# def profile(func):
#     return func


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
        self.new_statements = 0

    # @profile
    def finalize_object(self, obj, statements, obj_type):
        if statements and not obj.deleted:
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
    # @profile
    def parse_tags(obj):
        tags = obj.tags
        if not tags or obj.deleted:
            return None

        statements = []

        for tag in tags:
            key = tag.k
            if key == 'created_by':
                continue
            statements.append((Tag, key, tag.v))

        return statements

    # @profile
    def node(self, obj):
        statements = self.parse_tags(obj)
        if statements:
            try:
                geometry = self.wkbfab.create_point(obj)
                statements.append((Point, 'osmm:loc', geometry))
            except:
                statements.append(loc_err())
            self.added_nodes += 1
        elif obj.deleted:
            self.deleted_nodes += 1
        else:
            self.skipped_nodes += 1

        self.finalize_object(obj, statements, 'n')

    # @profile
    def way(self, obj):
        statements = self.parse_tags(obj)
        if statements:
            statements.append((Bool, 'osmm:isClosed', obj.is_closed()))
            if self.options.addWayLoc:
                try:
                    geometry = self.wkbfab.create_linestring(obj)
                    statements.append((Way, 'osmm:loc', geometry))
                except:
                    statements.append(loc_err())
            self.added_ways += 1
        elif obj.deleted:
            self.deleted_ways += 1
        else:
            self.skipped_ways += 1
        self.finalize_object(obj, statements, 'w')

    # @profile
    def relation(self, obj):
        statements = self.parse_tags(obj)
        members = obj.members
        if members:
            statements = statements if statements else []
            for mbr in members:

                # Produce two statements - one to find all members of a relation,
                # and another to find the role of that relation
                #     osmrel:123  osmm:has    osmway:456
                #     osmrel:123  osmway:456  "inner"

                ref = types[mbr.type] + str(mbr.ref)
                statements.append((Ref, 'osmm:has', ref))
                statements.append((Str, ref, mbr.role))

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
        res = 'Statements: {6};  Added: {0}n {1}w {2}r;  Skipped: {3}n {4}w {5}r'.format(
            self.added_nodes, self.added_ways, self.added_rels,
            self.skipped_nodes, self.skipped_ways, self.skipped_rels,
            self.new_statements)

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
