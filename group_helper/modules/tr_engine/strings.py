
import yaml
from codecs import encode, decode
import logging
from group_helper.modules.sql.locales_sql import prev_locale

LANGUAGES = ['en-US']

strings = {}

for i in LANGUAGES:
    strings[i] = yaml.full_load(open("locales/" + i + ".yml", "r", encoding="utf-8"))


def tld(chat_id, t, show_none=True):
    language = prev_locale(chat_id)
    if language:
        locale = language.locale_name
        if locale == 'en-US' and t in strings['en-US']:
            result = decode(
                encode(strings['en-US'][t], 'latin-1', 'backslashreplace'),
                'unicode-escape')
            return result
        elif locale == 'id' and t in strings['id']:
            result = decode(
                encode(strings['id'][t], 'latin-1', 'backslashreplace'),
                'unicode-escape')
            return result
        elif locale == 'ru' and t in strings['ru']:
            result = decode(
                encode(strings['ru'][t], 'latin-1', 'backslashreplace'),
                'unicode-escape')
            return result
        elif locale == 'es' and t in strings['es']:
            result = decode(
                encode(strings['es'][t], 'latin-1', 'backslashreplace'),
                'unicode-escape')
            return result
    if t in strings['en-US']:
        result = decode(
            encode(strings['en-US'][t], 'latin-1', 'backslashreplace'),
            'unicode-escape')
        return result
    err = f"No string found for {t}."
    logging.warning(err)
    return err


def tld_list(chat_id, t):
    language = prev_locale(chat_id)
    if language:
        locale = language.locale_name
        if locale == 'en-US' and t in strings['en-US']:
            return strings['en-US'][t]
        elif locale == 'id' and t in strings['id']:
            return strings['id'][t]
        elif locale == 'ru' and t in strings['ru']:
            return strings['ru'][t]
        elif locale == 'es' and t in strings['es']:
            return strings['es'][t]
    if t in strings['en-US']:
        return strings['en-US'][t]
    logging.warning(f"#NOSTR No string found for {t}.")
    return f"No string found for {t}."
