import json
import requests

from .utils import to_json
from .Cache import Cache


class TagInfoKeys(Cache):
    def load(self):
        with open(self.filename, "r") as file:
            return json.load(file)

    def generate(self):
        with open(self.filename, "w+") as file:
            r = requests.get('https://taginfo.openstreetmap.org/api/4/keys/all')
            data = r.json()
            file.write(to_json(data))
            return data
