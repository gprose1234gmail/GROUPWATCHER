
import html
import wikipedia
import re
from datetime import datetime
from typing import Optional
from covid import Covid

import requests
from telegram import Message, Chat, Update, MessageEntity
from telegram import ParseMode, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, Filters
from telegram.ext.callbackcontext import CallbackContext
from telegram.utils.helpers import escape_markdown, mention_html
from telegram.error import BadRequest

from group_helper import CONFIG
from group_helper.__main__ import GDPR
from group_helper.__main__ import STATS, USER_INFO
from group_helper.modules.disable import DisableAbleCommandHandler
from group_helper.modules.helper_funcs.extraction import extract_user

from group_helper.modules.tr_engine.strings import tld

from requests import get

cvid = Covid(source="worldometers")


def get_id(update: Update, context: CallbackContext):
    args = context.args
    user_id = extract_user(update.effective_message, args)
    chat = update.effective_chat  # type: Optional[Chat]
    if user_id:
        if update.effective_message.reply_to_message and update.effective_message.reply_to_message.forward_from:
            user1 = update.effective_message.reply_to_message.from_user
            user2 = update.effective_message.reply_to_message.forward_from
            update.effective_message.reply_markdown(
                tld(chat.id,
                    "misc_get_id_1").format(escape_markdown(user2.first_name),
                                            user2.id,
                                            escape_markdown(user1.first_name),
                                            user1.id))
        else:
            user = context.bot.get_chat(user_id)
            update.effective_message.reply_markdown(
                tld(chat.id,
                    "misc_get_id_2").format(escape_markdown(user.first_name),
                                            user.id))
    else:
        chat = update.effective_chat  # type: Optional[Chat]
        if chat.type == "private":
            update.effective_message.reply_markdown(
                tld(chat.id, "misc_id_1").format(chat.id))

        else:
            update.effective_message.reply_markdown(
                tld(chat.id, "misc_id_2").format(chat.id))


def info(update: Update, context: CallbackContext):
    args = context.args
    msg = update.effective_message  # type: Optional[Message]
    user_id = extract_user(update.effective_message, args)
    chat = update.effective_chat  # type: Optional[Chat]

    if user_id:
        user = context.bot.get_chat(user_id)

    elif not msg.reply_to_message and not args:
        user = msg.from_user

    elif not msg.reply_to_message and (
            not args or
        (len(args) >= 1 and not args[0].startswith("@")
         and not args[0].isdigit()
         and not msg.parse_entities([MessageEntity.TEXT_MENTION]))):
        msg.reply_text(tld(chat.id, "I can't extract a user from this."))
        return

    else:
        return

    text = tld(chat.id, "misc_info_1")
    text += tld(chat.id, "misc_info_id").format(user.id)
    text += tld(chat.id,
                "misc_info_first").format(html.escape(user.first_name))

    if user.last_name:
        text += tld(chat.id,
                    "misc_info_name").format(html.escape(user.last_name))

    if user.username:
        text += tld(chat.id,
                    "misc_info_username").format(html.escape(user.username))

    text += tld(chat.id,
                "misc_info_user_link").format(mention_html(user.id, "link"))

    if user.id == CONFIG.owner_id:
        text += tld(chat.id, "misc_info_is_owner")
    else:
        if user.id == int(254318997):
            text += tld(chat.id, "misc_info_is_original_owner")

        if user.id in CONFIG.sudo_users:
            text += tld(chat.id, "misc_info_is_sudo")
        else:
            if user.id in CONFIG.whitelist_users:
                text += tld(chat.id, "misc_info_is_whitelisted")

    for mod in USER_INFO:
        mod_info = mod.__user_info__(user.id, chat.id).strip()
        if mod_info:
            text += "\n\n" + mod_info

    update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


def reply_keyboard_remove(update: Update, context: CallbackContext):
    reply_keyboard = []
    reply_keyboard.append([ReplyKeyboardRemove(remove_keyboard=True)])
    reply_markup = ReplyKeyboardRemove(remove_keyboard=True)
    old_message = context.bot.send_message(
        chat_id=update.message.chat_id,
        text='trying',  # This text will not get translated
        reply_markup=reply_markup,
        reply_to_message_id=update.message.message_id)
    context.bot.delete_message(chat_id=update.message.chat_id,
                               message_id=old_message.message_id)


def gdpr(update: Update, context: CallbackContext):
    update.effective_message.reply_text(
        tld(update.effective_chat.id, "misc_gdpr"))
    for mod in GDPR:
        mod.__gdpr__(update.effective_user.id)

    update.effective_message.reply_text("GDPR is done",
                                        parse_mode=ParseMode.MARKDOWN)


def markdown_help(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    update.effective_message.reply_text(tld(chat.id, "misc_md_list"),
                                        parse_mode=ParseMode.HTML)
    update.effective_message.reply_text(tld(chat.id, "misc_md_try"))
    update.effective_message.reply_text(tld(chat.id, "misc_md_help"))


def stats(update: Update, context: CallbackContext):
    update.effective_message.reply_text(
        # This text doesn't get translated as it is internal message.
        "*Current Stats:*\n" + "\n".join([mod.__stats__() for mod in STATS]),
        parse_mode=ParseMode.MARKDOWN)


def github(update: Update, context: CallbackContext):
    message = update.effective_message
    text = message.text[len('/git '):]
    usr = get(f'https://api.github.com/users/{text}').json()
    if usr.get('login'):
        text = f"*Username:* [{usr['login']}](https://github.com/{usr['login']})"

        whitelist = [
            'name', 'id', 'type', 'location', 'blog', 'bio', 'followers',
            'following', 'hireable', 'public_gists', 'public_repos', 'email',
            'company', 'updated_at', 'created_at'
        ]

        difnames = {
            'id': 'Account ID',
            'type': 'Account type',
            'created_at': 'Account created at',
            'updated_at': 'Last updated',
            'public_repos': 'Public Repos',
            'public_gists': 'Public Gists'
        }

        goaway = [None, 0, 'null', '']

        for x, y in usr.items():
            if x in whitelist:
                if x in difnames:
                    x = difnames[x]
                else:
                    x = x.title()

                if x == 'Account created at' or x == 'Last updated':
                    y = datetime.strptime(y, "%Y-%m-%dT%H:%M:%SZ")

                if y not in goaway:
                    if x == 'Blog':
                        x = "Website"
                        y = f"[Here!]({y})"
                        text += ("\n*{}:* {}".format(x, y))
                    else:
                        text += ("\n*{}:* `{}`".format(x, y))
        reply_text = text
    else:
        reply_text = "User not found. Make sure you entered valid username!"
    message.reply_text(reply_text,
                       parse_mode=ParseMode.MARKDOWN,
                       disable_web_page_preview=True)


def repo(update: Update, context: CallbackContext):
    message = update.effective_message
    text = message.text[len('/repo '):]
    usr = get(f'https://api.github.com/users/{text}/repos?per_page=40').json()
    reply_text = "*Repo*\n"
    for i in range(len(usr)):
        reply_text += f"[{usr[i]['name']}]({usr[i]['html_url']})\n"
    message.reply_text(reply_text,
                       parse_mode=ParseMode.MARKDOWN,
                       disable_web_page_preview=True)


def paste(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat  # type: Optional[Chat]
    BURL = 'https://del.dog'
    message = update.effective_message
    if message.reply_to_message:
        data = message.reply_to_message.text
    elif len(args) >= 1:
        data = message.text.split(None, 1)[1]
    else:
        message.reply_text(tld(chat.id, "misc_paste_invalid"))
        return

    r = requests.post(f'{BURL}/documents', data=data.encode('utf-8'))

    if r.status_code == 404:
        update.effective_message.reply_text(tld(chat.id, "misc_paste_404"))
        r.raise_for_status()

    res = r.json()

    if r.status_code != 200:
        update.effective_message.reply_text(res['message'])
        r.raise_for_status()

    key = res['key']
    if res['isUrl']:
        reply = tld(chat.id, "misc_paste_success").format(BURL, key, BURL, key)
    else:
        reply = f'{BURL}/{key}'
    update.effective_message.reply_text(reply,
                                        parse_mode=ParseMode.MARKDOWN,
                                        disable_web_page_preview=True)


def get_paste_content(update: Update, context: CallbackContext):
    args = context.args
    BURL = 'https://del.dog'
    message = update.effective_message
    chat = update.effective_chat  # type: Optional[Chat]

    if len(args) >= 1:
        key = args[0]
    else:
        message.reply_text(tld(chat.id, "misc_get_pasted_invalid"))
        return

    format_normal = f'{BURL}/'
    format_view = f'{BURL}/v/'

    if key.startswith(format_view):
        key = key[len(format_view):]
    elif key.startswith(format_normal):
        key = key[len(format_normal):]

    r = requests.get(f'{BURL}/raw/{key}')

    if r.status_code != 200:
        try:
            res = r.json()
            update.effective_message.reply_text(res['message'])
        except Exception:
            if r.status_code == 404:
                update.effective_message.reply_text(
                    tld(chat.id, "misc_paste_404"))
            else:
                update.effective_message.reply_text(
                    tld(chat.id, "misc_get_pasted_unknown"))
        r.raise_for_status()

    update.effective_message.reply_text('```' + escape_markdown(r.text) +
                                        '```',
                                        parse_mode=ParseMode.MARKDOWN)


def get_paste_stats(update: Update, context: CallbackContext):
    args = context.args
    BURL = 'https://del.dog'
    message = update.effective_message
    chat = update.effective_chat  # type: Optional[Chat]

    if len(args) >= 1:
        key = args[0]
    else:
        message.reply_text(tld(chat.id, "misc_get_pasted_invalid"))
        return

    format_normal = f'{BURL}/'
    format_view = f'{BURL}/v/'

    if key.startswith(format_view):
        key = key[len(format_view):]
    elif key.startswith(format_normal):
        key = key[len(format_normal):]

    r = requests.get(f'{BURL}/documents/{key}')

    if r.status_code != 200:
        try:
            res = r.json()
            update.effective_message.reply_text(res['message'])
        except Exception:
            if r.status_code == 404:
                update.effective_message.reply_text(
                    tld(chat.id, "misc_paste_404"))
            else:
                update.effective_message.reply_text(
                    tld(chat.id, "misc_get_pasted_unknown"))
        r.raise_for_status()

    document = r.json()['document']
    key = document['_id']
    views = document['viewCount']
    reply = f'Stats for **[/{key}]({BURL}/{key})**:\nViews: `{views}`'
    update.effective_message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)


def ud(update: Update, context: CallbackContext):
    message = update.effective_message
    text = message.text[len('/ud '):]
    if text == '':
        text = "Cockblocked By Steve Jobs"
    results = get(
        f'http://api.urbandictionary.com/v0/define?term={text}').json()
    reply_text = f'Word: {text}\nDefinition: {results["list"][0]["definition"]}'
    message.reply_text(reply_text)


def wiki(update: Update, context: CallbackContext):
    kueri = re.split(pattern="wiki", string=update.effective_message.text)
    wikipedia.set_lang("en")
    if len(str(kueri[1])) == 0:
        update.effective_message.reply_text("Enter keywords!")
    else:
        try:
            pertama = update.effective_message.reply_text("🔄 Loading...")
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(text="🔧 More Info...",
                                     url=wikipedia.page(kueri).url)
            ]])
            context.bot.editMessageText(chat_id=update.effective_chat.id,
                                        message_id=pertama.message_id,
                                        text=wikipedia.summary(kueri,
                                                               sentences=10),
                                        reply_markup=keyboard)
        except wikipedia.PageError as e:
            update.effective_message.reply_text("⚠ Error: {}".format(e))
        except BadRequest as et:
            update.effective_message.reply_text("⚠ Error: {}".format(et))
        except wikipedia.exceptions.DisambiguationError as eet:
            update.effective_message.reply_text(
                "⚠ Error\n There are too many query! Express it more!\nPossible query result:\n{}"
                .format(eet))


def covid(update: Update, context: CallbackContext):
    message = update.effective_message
    chat = update.effective_chat
    country = str(message.text[len('/covid '):])
    if country == '':
        country = "world"
    if country.lower() in ["south korea", "korea"]:
        country = "s. korea"
    try:
        c_case = cvid.get_status_by_country_name(country)
    except Exception:
        message.reply_text(tld(chat.id, "misc_covid_error"))
        return
    active = format_integer(c_case["active"])
    confirmed = format_integer(c_case["confirmed"])
    country = c_case["country"]
    critical = format_integer(c_case["critical"])
    deaths = format_integer(c_case["deaths"])
    new_cases = format_integer(c_case["new_cases"])
    new_deaths = format_integer(c_case["new_deaths"])
    recovered = format_integer(c_case["recovered"])
    total_tests = c_case["total_tests"]
    if total_tests == 0:
        total_tests = "N/A"
    else:
        total_tests = format_integer(c_case["total_tests"])
    reply = tld(chat.id,
                "misc_covid").format(country, confirmed, new_cases, active,
                                     critical, deaths, new_deaths, recovered,
                                     total_tests)
    message.reply_markdown(reply)


def format_integer(number, thousand_separator=','):
    def reverse(string):
        string = "".join(reversed(string))
        return string

    s = reverse(str(number))
    count = 0
    result = ''
    for char in s:
        count = count + 1
        if count % 3 == 0:
            if len(s) == count:
                result = char + result
            else:
                result = thousand_separator + char + result
        else:
            result = char + result
    return result


__help__ = True

ID_HANDLER = DisableAbleCommandHandler("id",
                                       get_id,
                                       pass_args=True,
                                       run_async=True,
                                       admin_ok=True)
INFO_HANDLER = DisableAbleCommandHandler("info",
                                         info,
                                         pass_args=True,
                                         run_async=True,
                                         admin_ok=True)
GITHUB_HANDLER = DisableAbleCommandHandler("git", github, admin_ok=True)
REPO_HANDLER = DisableAbleCommandHandler("repo",
                                         repo,
                                         pass_args=True,
                                         run_async=True,
                                         admin_ok=True)
MD_HELP_HANDLER = CommandHandler("markdownhelp",
                                 markdown_help,
                                 run_async=True,
                                 filters=Filters.chat_type.private)

STATS_HANDLER = CommandHandler("stats",
                               stats,
                               run_async=True,
                               filters=Filters.user(CONFIG.owner_id))
GDPR_HANDLER = CommandHandler("gdpr",
                              gdpr,
                              run_async=True,
                              filters=Filters.chat_type.private)
PASTE_HANDLER = DisableAbleCommandHandler("paste",
                                          paste,
                                          pass_args=True,
                                          run_async=True)
GET_PASTE_HANDLER = DisableAbleCommandHandler("getpaste",
                                              get_paste_content,
                                              pass_args=True,
                                              run_async=True)
PASTE_STATS_HANDLER = DisableAbleCommandHandler("pastestats",
                                                get_paste_stats,
                                                pass_args=True,
                                                run_async=True)
UD_HANDLER = DisableAbleCommandHandler("ud", ud, run_async=True)
WIKI_HANDLER = DisableAbleCommandHandler("wiki", wiki, run_async=True)
COVID_HANDLER = DisableAbleCommandHandler("covid",
                                          covid,
                                          run_async=True,
                                          admin_ok=True)

CONFIG.dispatcher.add_handler(UD_HANDLER)
CONFIG.dispatcher.add_handler(PASTE_HANDLER)
CONFIG.dispatcher.add_handler(GET_PASTE_HANDLER)
CONFIG.dispatcher.add_handler(PASTE_STATS_HANDLER)
CONFIG.dispatcher.add_handler(ID_HANDLER)
CONFIG.dispatcher.add_handler(INFO_HANDLER)
CONFIG.dispatcher.add_handler(MD_HELP_HANDLER)
CONFIG.dispatcher.add_handler(STATS_HANDLER)
CONFIG.dispatcher.add_handler(GDPR_HANDLER)
CONFIG.dispatcher.add_handler(GITHUB_HANDLER)
CONFIG.dispatcher.add_handler(REPO_HANDLER)
CONFIG.dispatcher.add_handler(
    DisableAbleCommandHandler("removebotkeyboard", reply_keyboard_remove))
CONFIG.dispatcher.add_handler(WIKI_HANDLER)
CONFIG.dispatcher.add_handler(COVID_HANDLER)
