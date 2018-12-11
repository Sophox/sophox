from .Cache import CacheInMemory


class CachedFilteredDescription(CacheInMemory):

    def __init__(self, descriptions, filter):
        super().__init__()
        self.descriptions = descriptions
        self.filter = filter

    def generate(self):
        result = []
        for item in self.descriptions.get():
            # if 'amenity=bicycle' not in pt.full_title: continue
            if item.ns % 2 != 1 and item.ns != 2 and 'Proposed features/' not in item.full_title and item.type == self.filter:
                result.append(item)
        return result


