from collections import defaultdict

import re
import sqlite3

from .consts import Q_KEY, Q_ENUM_KEY_TYPE, known_non_enums
from .Properties import P_INSTANCE_OF, P_KEY_TYPE, P_KEY_ID
from .Cache import CacheJsonl
from .utils import to_json


class TagInfoDb(CacheJsonl):
    def __init__(self, filename, sqlite_db, data_items):
        super().__init__(filename)
        self.sqlite_db = sqlite_db
        self.data_items = data_items

    def generate(self):
        re_value = re.compile(r'^[a-z0-9]+([-:_.][a-z0-9]+)*$')
        keys = []
        for item in self.data_items.get():
            if P_INSTANCE_OF.get_claim_value(item) != Q_KEY:
                continue
            if P_KEY_TYPE.get_claim_value(item) == Q_ENUM_KEY_TYPE:
                key = P_KEY_ID.get_claim_value(item)
                if key not in known_non_enums:
                    keys.append(key)

        with open(self.filename, "w+") as file:
            with sqlite3.connect(self.sqlite_db) as conn:
                cur = conn.cursor()
                for key in keys:
                    values = defaultdict(int)
                    for item in cur.execute(
                            'select value, count_all '
                            'from tags '
                            'where key = ?',
                            (key,)).fetchall():
                        if ';' in item[0]:
                            for k in item[0].split(';'):
                                values[k] += item[1]
                        else:
                            values[item[0]] += item[1]
                    print('\n'.join([
                        to_json({'k': key, 'v': v, 'c': c})
                        for v, c in values.items()
                        if c > 5000 or (c > 50 and re_value.match(v))
                    ]), file=file)
