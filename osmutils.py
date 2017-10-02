import re
from urllib.parse import quote
import json

import datetime as dt
from datetime import datetime
import shapely.speedups
import sys
from shapely.wkb import loads


UTC_DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
UTC_DATE_FORMAT2 = '%Y-%m-%dT%H:%M:%S.%fZ'
XSD_DATE_TIME = '"{0:%Y-%m-%dT%H:%M:%S}Z"^^xsd:dateTime'


if shapely.speedups.available:
    shapely.speedups.enable()


# May contain letters, numbers anywhere, and -:_ symbols anywhere except first and last position
reSimpleLocalName = re.compile(r'^[0-9a-zA-Z_]([-:0-9a-zA-Z_]*[0-9a-zA-Z_])?$')
reWikidataKey = re.compile(r'(.:)?wikidata$')
reWikidataValue = re.compile(r'^Q[1-9][0-9]*$')
reWikidataMultiValue = re.compile(r'^Q[1-9][0-9]*(;Q[1-9][0-9]*)+$')
reWikipediaValue = re.compile(r'^([-a-z]+):(.+)$')


def format_date(datetime):
    # https://phabricator.wikimedia.org/T173974
    # 2015-05-01T01:00:00Z
    return XSD_DATE_TIME.format(datetime)


def parse_date(timestamp):
    # Try with and without the fraction of a second part
    try:
        result = datetime.strptime(timestamp, UTC_DATE_FORMAT)
    except ValueError:
        result = datetime.strptime(timestamp, UTC_DATE_FORMAT2)

    return result.replace(tzinfo=dt.timezone.utc)


def stringify(val):
    return json.dumps(val, ensure_ascii=False)


def chunks(values, max_count):
    """Yield successive n-sized chunks from l."""
    if hasattr(values, "__getitem__"):
        for index in range(0, len(values), max_count):
            yield values[index:index + max_count]
    else:
        result = []
        for v in values:
            result.append(v)
            if len(result) >= max_count:
                yield result
                result.clear()
        if len(result) > 0:
            yield result


def tagToStr(key, value):
    val = None
    if not reSimpleLocalName.match(key):
        # Record any unusual tag name in a "osmm:badkey" statement
        return 'osmm:badkey ' + stringify(key)

    if 'wikidata' in key:
        if reWikidataValue.match(value):
            val = 'wd:' + value
        elif reWikidataMultiValue.match(value):
            val = ','.join(['wd:' + v for v in value.split(';')])
    elif 'wikipedia' in key:
        match = reWikipediaValue.match(value)
        if match:
            val = make_wiki_url(match.group(1), '.wikipedia.org/wiki/', match.group(2))
    # elif 'website' in key or 'url' in key:
    # TODO: possibly convert all urls into the sparql <IRI> ?
    #     pass

    if val is None:
        return 'osmt:' + key + ' ' + stringify(value)
    else:
        return 'osmt:' + key + ' ' + val


def make_wiki_url(lang, site, title):
    # The "#" is also safe - used for anchoring
    return '<https://' + lang + site + quote(title.replace(' ', '_'), safe=';@$!*(),/~:#') + '>'


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

types = {
    'n': 'osmnode:',
    'w': 'osmway:',
    'r': 'osmrel:',
}

prefixes = [
    'prefix wd: <http://www.wikidata.org/entity/>',
    'prefix xsd: <http://www.w3.org/2001/XMLSchema#>',
    'prefix geo: <http://www.opengis.net/ont/geosparql#>',
    'prefix schema: <http://schema.org/>',

    'prefix osmroot: <https://www.openstreetmap.org>',
    'prefix osmnode: <https://www.openstreetmap.org/node/>',
    'prefix osmway: <https://www.openstreetmap.org/way/>',
    'prefix osmrel: <https://www.openstreetmap.org/relation/>',
    'prefix osmt: <https://wiki.openstreetmap.org/wiki/Key:>',
    'prefix osmm: <https://www.openstreetmap.org/meta/>',
]
