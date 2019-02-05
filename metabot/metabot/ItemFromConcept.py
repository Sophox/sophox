from .Properties import P_INSTANCE_OF, \
    ClaimValue, P_LANG_CODE
from .consts import Q_LOCALE_INSTANCE
from .utils import sitelink_normalizer_locale, to_item_sitelink


class ItemFromConcept:

    def __init__(self, item, lang_code=None, lang_name=None) -> None:
        self.item = item
        self.lang_code = P_LANG_CODE.get_claim_value(item) if item else lang_code
        self.ok = True
        self.messages = []

        self.claims = {
            P_INSTANCE_OF: [ClaimValue(Q_LOCALE_INSTANCE)],
            P_LANG_CODE: [ClaimValue(self.lang_code)],
        }

        self.sitelink = sitelink_normalizer_locale(self.lang_code)

        self.header = {
            'labels': {},
            'descriptions': {},
            'sitelinks': to_item_sitelink(self.sitelink),
        }

        if item:
            self.header['labels'].update({k: v.value for k, v in item.labels.items()})
            self.header['descriptions'].update({k: v.value for k, v in item.descriptions.items()})
        else:
            self.header['labels']['en'] = f'{lang_name}-speaking region'
            self.header['descriptions']['en'] = f'This region includes {lang_name}-speaking countries ' \
                f'to document the difference in rules. Use it with P26 qualifier.'

    def print(self, msg):
        self.messages.append(msg)

    def print_messages(self):
        if self.messages:
            print(f'Creating item for {self.lang_code}')
            for msg in self.messages:
                print(msg)
