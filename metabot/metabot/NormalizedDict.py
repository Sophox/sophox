from .utils import sitelink_normalizer


# See also
# https://stackoverflow.com/questions/2390827/how-to-properly-subclass-dict-and-override-getitem-setitem/2390997
class NormalizedDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.update(*args, **kwargs)

    def __getitem__(self, key):
        val = dict.__getitem__(self, sitelink_normalizer(key))
        return val

    def __setitem__(self, key, val):
        dict.__setitem__(self, sitelink_normalizer(key), val)

    def update(self, *args, **kwargs):
        for k, v in dict(*args, **kwargs).items():
            self[k] = v
