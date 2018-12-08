import json

from metabot.Cache import Cache


class ResolvedImageFiles(Cache):
    def load(self):
        with open(self.filename, "r") as file:
            return json.load(file)

    def generate(self):
        # Force the file to be non-empty
        self.save({'** dummy value **': 42})

    def save(self, data):
        with open(self.filename, "w+") as file:
            json.dump(data, file, ensure_ascii=False)

    def append(self, title, img):
        self._data[title] = img
        self.save(self._data)
