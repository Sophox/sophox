import json

import pywikibot as pb

from metabot.Cache import Cache


class ResolvedImageFiles(Cache):

    def __init__(self, filename: str, pwb_site: pb.Site):
        super().__init__(filename)
        self.pwb_site = pwb_site

    def load(self):
        with open(self.filename, "r") as file:
            return json.load(file)

    def generate(self):
        # Force the file to be non-empty
        self.save({'** dummy value **': 42})

    def save(self, data):
        with open(self.filename, "w+") as file:
            json.dump(data, file, ensure_ascii=False, indent=0, sort_keys=True)

    def append(self, title, img):
        self._data[title] = img
        self.save(self._data)

    def parse_image_title(self, file_title):
        if file_title.startswith('Image:') or file_title.startswith('image:'):
            file_title = 'File:' + file_title[len('Image:'):]
        elif file_title.startswith('file:'):
            file_title = 'File:' + file_title[len('file:'):]
        image_file_cache = self.get()
        if file_title in image_file_cache:
            return image_file_cache[file_title]

        try:
            img = pb.FilePage(self.pwb_site, file_title)
            if not img.fileIsShared():
                img = 'osm:' + img.titleWithoutNamespace()
            else:
                img = img.titleWithoutNamespace()
            self.append(file_title, img)
            return img
        except (pb.exceptions.NoPage, pb.exceptions.InvalidTitle):
            self.append(file_title, None)
            raise
