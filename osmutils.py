import json


def format_date(datetime):
    # https://phabricator.wikimedia.org/T173974
    return '"' + datetime.isoformat().replace('+00:00', 'Z') + '"^^xsd:dateTime'

def stringify(val):
    return json.dumps(val, ensure_ascii=False)
