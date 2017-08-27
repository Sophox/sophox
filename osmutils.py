import re
from urllib.parse import quote
import json

import shapely.speedups
import sys
from shapely.wkb import loads

if shapely.speedups.available:
    shapely.speedups.enable()


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


def loc_err():
    try:
        error = sys.exc_info()[1]
        return (Str, 'osmm:loc:error', str(error) + ' (' + type(error).__name__ + ')')
    except:
        return (Str, 'osmm:loc:error', 'Unable to parse location data')

def wayToStr(k, v):
    try:
        return formatPoint(k, loads(v, hex=True).representative_point())
    except:
        return tupleToStr(loc_err())


def pointToStr(k, v):
    try:
        return formatPoint(k, loads(v, hex=True))
    except:
        return tupleToStr(loc_err())


def formatPoint(tag, point):
    result = tag + ' "Point(' + str(point.x) + ' ' + str(point.y)
    if point.has_z:
        result += ' ' + str(point.z)
    result += ')"^^geo:wktLiteral'
    return result


Bool = 0
Date = 1
Int = 2
Ref = 3
Str = 4
Tag = 5
Way = 6
Point = 7

statementToStr = [
    # Bool
    lambda k, v: k + ' "' + ('true' if v else 'false') + '"^^xsd:boolean',
    # Date
    lambda k, v: k + ' ' + format_date(v),
    # Int
    lambda k, v: k + ' "' + str(v) + '"^^xsd:integer',
    # Ref
    lambda k, v: k + ' ' + v,
    # Str
    lambda k, v: k + ' ' + stringify(v),
    # Tag
    tagToStr,
    # Way
    wayToStr,
    # Point
    pointToStr,
]


def toStrings(statements):
    return [tupleToStr(s) for s in statements]


def tupleToStr(s):
    return statementToStr[s[0]](s[1], s[2])
