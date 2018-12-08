import json
import os.path


class Cache:
    def __init__(self, filename):
        self.filename = filename
        self._data = None

    def get(self):
        if not self._data:
            self._reload()
        if not self._data:
            # generator could produce the same data, but it is better to round-trip to disk to ensure consistency
            self.regenerate()
            self._reload()
        if self._data is None:
            self._data = ValueError('Unable to generate data')
        if type(self._data) is ValueError:
            raise self._data
        return self._data

    def _reload(self):
        try:
            self._data = self.load()
        except IOError:
            self._data = None

    def regenerate(self):
        print(f'----------------  REGENERATING {self.filename}  ----------------')
        self._data = None
        self.generate()

    def load(self):
        raise Exception('Not implemented by derived class')

    def generate(self):
        raise Exception('Not implemented by derived class')


class CacheJsonl(Cache):
    def load(self):
        with open(self.filename, "r") as file:
            items = []
            for line in file.readlines():
                line = line.rstrip()
                if not line:
                    continue
                items.append(json.loads(line))
            return items

    def iter(self):
        if not os.path.isfile(self.filename):
            self.regenerate()

        with open(self.filename, "r") as file:
            for line in file:
                line = line.rstrip()
                if line:
                    yield json.loads(line)


class CacheInMemory:
    def __init__(self):
        self._is_loaded = False
        self._data = None

    def get(self):
        if self._is_loaded:
            return self._data
        self._data = self.generate()
        self._is_loaded = True
        return self._data

    def regenerate(self):
        self._is_loaded = False

    def generate(self):
        raise Exception('Not implemented by derived class')
