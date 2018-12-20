import json
from urllib.parse import quote

import datetime as dt

from datetime import datetime

UTC_DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
UTC_DATE_FORMAT2 = '%Y-%m-%dT%H:%M:%S.%fZ'
XSD_DATE_TIME = '"{0:%Y-%m-%dT%H:%M:%S}Z"^^xsd:dateTime'


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


def query_status(rdf_server, uri, field=None):
    extra_cond = ''
    if field:
        extra_cond = f'OPTIONAL {{ {uri} schema:version ?{field} . }}'

    sparql = f'''
SELECT ?dummy ?dateModified {'?' + field if field else ''} WHERE {{
 BIND( "42" as ?dummy )
 OPTIONAL {{ {uri} schema:dateModified ?dateModified . }}
 {extra_cond if extra_cond else ''}
}}
'''

    result = rdf_server.run('query', sparql)[0]

    if result['dummy']['value'] != '42':
        raise Exception('Failed to get a dummy value from RDF DB')

    try:
        ts = parse_date(result['dateModified']['value'])
    except KeyError:
        ts = None

    if field:
        try:
            field_value = result[field]['value']
        except KeyError:
            field_value = None

        return {'dateModified': ts, field: field_value}
    else:
        return ts


def set_status_query(uri, timestamp, field=None, value=None):
    sparql = f'DELETE {{ {uri} schema:dateModified ?m . }} WHERE {{ {uri} schema:dateModified ?m . }};\n'
    if field:
        sparql += f'DELETE {{ {uri} schema:{field} ?v . }} WHERE {{ {uri} schema:{field} ?v . }};\n'
    sparql += 'INSERT {\n'
    sparql += f' {uri} schema:dateModified {format_date(timestamp)} .\n'
    if field:
        sparql += f' {uri} schema:{field} {value} .\n'
    sparql += '} WHERE {};'

    return sparql


def make_wiki_url(lang, site, title):
    # The "#" is also safe - used for anchoring
    return '<https://' + lang + site + quote(title.replace(' ', '_'), safe=';@$!*(),/~:#') + '>'


def format_date(datetime):
    # https://phabricator.wikimedia.org/T173974
    # 2015-05-01T01:00:00Z
    return XSD_DATE_TIME.format(datetime)


def parse_utc(ts):
    # TODO: In Python 3.7, use  datetime.fromisoformat(ts)  instead
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
