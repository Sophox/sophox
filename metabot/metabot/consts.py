import re

LANG_NS = {
    'en': 0,
    'de': 200,
    'fr': 202,
    'es': 204,
    'it': 206,
    'nl': 208,
    'ru': 210,
    'ja': 212,
}

elements = {
    'node': 'Q3',
    'way': 'Q4',
    'area': 'Q5',
    'relation': 'Q6',
    'closedway': 'Q4669',
    'changeset': 'Q4670',
}

Q_TAG = 'Q2'
Q_KEY = 'Q7'
Q_ENUM_KEY_TYPE = 'Q8'
Q_REL_MEMBER_ROLE = 'Q4667'
Q_GROUP = 'Q12'
Q_STATUS = 'Q11'
Q_REGION_INSTANCE = 'Q6999'
Q_IS_ALLOWED = 'Q8000'
Q_IS_PROHIBITED = 'Q8001'

languages = {'ace', 'kbd', 'ady', 'af', 'ak', 'als', 'am', 'ang', 'ab', 'ar',
             'an', 'arc', 'roa-rup', 'frp', 'as', 'ast', 'atj', 'gn', 'av',
             'ay', 'az', 'bm', 'bn', 'bjn', 'zh-min-nan', 'nan', 'map-bms',
             'ba', 'be', 'be-tarask', 'bh', 'bcl', 'bi', 'bg', 'bar', 'bo',
             'bs', 'br', 'bxr', 'ca', 'cv', 'ceb', 'cs', 'ch', 'cbk-zam', 'ny',
             'sn', 'tum', 'cho', 'co', 'cy', 'da', 'dk', 'pdc', 'de', 'dv',
             'nv', 'dsb', 'dty', 'dz', 'mh', 'et', 'el', 'eml', 'en', 'myv',
             'es', 'eo', 'ext', 'eu', 'ee', 'fa', 'hif', 'fo', 'fr', 'fy', 'ff',
             'fur', 'ga', 'gv', 'gag', 'gd', 'gl', 'gan', 'ki', 'glk', 'gu',
             'got', 'hak', 'xal', 'ko', 'ha', 'haw', 'hy', 'hi', 'ho', 'hsb',
             'hr', 'io', 'ig', 'ilo', 'bpy', 'id', 'ia', 'ie', 'iu', 'ik', 'os',
             'xh', 'zu', 'is', 'it', 'he', 'jv', 'kbp', 'kl', 'kn', 'kr', 'pam',
             'krc', 'ka', 'ks', 'csb', 'kk', 'kw', 'rw', 'rn', 'sw', 'kv', 'kg',
             'gom', 'ht', 'ku', 'kj', 'ky', 'mrj', 'lad', 'lbe', 'lez', 'lo',
             'ltg', 'la', 'lv', 'lb', 'lt', 'lij', 'li', 'ln', 'olo', 'jbo',
             'lg', 'lmo', 'lrc', 'hu', 'mai', 'mk', 'mg', 'ml', 'mt', 'mi',
             'mr', 'xmf', 'arz', 'mzn', 'ms', 'min', 'cdo', 'mwl', 'mdf', 'mo',
             'mn', 'mus', 'my', 'nah', 'na', 'fj', 'nl', 'nds-nl', 'cr', 'ne',
             'new', 'ja', 'nap', 'ce', 'frr', 'pih', 'no', 'nb', 'nn', 'nrm',
             'nov', 'ii', 'oc', 'mhr', 'or', 'om', 'ng', 'hz', 'uz', 'pa', 'pi',
             'pfl', 'pag', 'pnb', 'pap', 'ps', 'jam', 'koi', 'km', 'pcd', 'pms',
             'tpi', 'nds', 'pl', 'pnt', 'pt', 'aa', 'kaa', 'crh', 'ty', 'ksh',
             'ro', 'rmy', 'rm', 'qu', 'rue', 'ru', 'sah', 'se', 'sm', 'sa',
             'sg', 'sc', 'sco', 'stq', 'st', 'nso', 'tn', 'sq', 'scn', 'si',
             'simple', 'sd', 'ss', 'sk', 'sl', 'cu', 'szl', 'so', 'ckb', 'srn',
             'sr', 'sh', 'su', 'fi', 'sv', 'tl', 'ta', 'kab', 'roa-tara', 'tt',
             'te', 'tet', 'th', 'ti', 'tg', 'to', 'chr', 'chy', 've', 'tcy',
             'tr', 'azb', 'tk', 'tw', 'tyv', 'udm', 'bug', 'uk', 'ur', 'ug',
             'za', 'vec', 'vep', 'vi', 'vo', 'fiu-vro', 'wa', 'zh-classical',
             'vls', 'war', 'wo', 'wuu', 'ts', 'yi', 'yo', 'zh-yue', 'diq',
             'zea', 'bat-smg', 'zh', 'zh-tw', 'zh-cn',
             'yue', 'zh-hans', 'zh-hant', 'pt-br'}

ignoreLangSuspects = {'translation'}

reLanguagesClause = '(?:' + '|'.join([re.escape(l) for l in languages]) + ')'

NS_USER=2
NS_USER_TALK=3
NS_TEMPLATE=10
NS_TEMPLATE_TALK=11
