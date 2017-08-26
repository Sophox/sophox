import re
from urllib.parse import quote
import json

# May contain letters, numbers anywhere, and -:_ symbols anywhere except first and last position
reSimpleLocalName = re.compile(r'^[0-9a-zA-Z_]([-:0-9a-zA-Z_]*[0-9a-zA-Z_])?$')
reWikidataKey = re.compile(r'(.:)?wikidata$')
reWikidataValue = re.compile(r'^Q[1-9][0-9]*$')
reWikipediaValue = re.compile(r'^([-a-z]+):(.+)$')


def format_date(datetime):
    # https://phabricator.wikimedia.org/T173974
    return '"' + datetime.isoformat().replace('+00:00', 'Z') + '"^^xsd:dateTime'


def stringify(val):
    return json.dumps(val, ensure_ascii=False)


def tagToStr(k, v):
    val = None
    if not reSimpleLocalName.match(k):
        # Record any unusual tag name in a "osmm:badkey" statement
        return 'osmm:badkey ' + stringify(k)

    if 'wikidata' in k:
        if reWikidataValue.match(v):
            val = 'wd:' + v
    elif 'wikipedia' in k:
        match = reWikipediaValue.match(v)
        if match:
            val = '<https://' + match.group(1) + '.wikipedia.org/wiki/' + \
                  quote(match.group(2).replace(' ', '_'), safe=';@$!*(),/~:') + '>'

    if val is None:
        return 'osmt:' + k + ' ' + stringify(v)
    else:
        return 'osmt:' + k + ' ' + val


Bool = 0
Date = 1
Geo = 2
Int = 3
Ref = 4
Str = 5
Tag = 6

statementToStr = [
    # Bool
    lambda k, v: k + ' "' + ('true' if v else 'false') + '"^^xsd:boolean',
    # Date
    lambda k, v: k + ' ' + format_date(v),
    # Geo
    lambda k, v: k + ' "Point(' + v + ')"^^geo:wktLiteral',
    # Int
    lambda k, v: k + ' "' + str(v) + '"^^xsd:integer',
    # Ref
    lambda k, v: k + ' ' + v,
    # Str
    lambda k, v: k + ' ' + stringify(v),
    # Tag
    tagToStr,
]


def toStrings(statements):
    return [statementToStr[s[0]](s[1], s[2]) for s in statements]
