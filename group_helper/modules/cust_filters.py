import re

import telegram
from telegram import ParseMode, InlineKeyboardMarkup
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import MessageHandler, DispatcherHandlerStop
from telegram.ext.callbackcontext import CallbackContext
from telegram.utils.helpers import escape_markdown
from group_helper import CONFIG
from group_helper.modules.disable import DisableAbleCommandHandler
from group_helper.modules.helper_funcs.chat_status import user_admin
from group_helper.modules.helper_funcs.extraction import extract_text
from group_helper.modules.helper_funcs.filters import CustomFilters
from group_helper.modules.helper_funcs.misc import build_keyboard
from group_helper.modules.helper_funcs.string_handling import split_quotes, button_markdown_parser
from group_helper.modules.sql import cust_filters_sql as sql

from group_helper.modules.tr_engine.strings import tld

from group_helper.modules.connection import connected

HANDLER_GROUP = 15


def list_handlers(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user

    conn = connected(update, context, user.id, need_admin=False)
    if conn:
        chat_id = conn
        chat_name = context.bot.getChat(conn).title
        filter_list = tld(chat.id, "cust_filters_list")
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            chat_name = tld(chat.id, "cust_filters_local")
        else:
            chat_name = chat.title

        filter_list = tld(chat.id, "cust_filters_list")

    all_handlers = sql.get_chat_triggers(chat_id)

    if not all_handlers:
        update.effective_message.reply_text(
            tld(chat.id, "cust_filters_list_empty").format(chat_name))
        return

    for keyword in all_handlers:
        entry = " • `{}`\n".format(escape_markdown(keyword))
        if len(entry) + len(filter_list) > telegram.MAX_MESSAGE_LENGTH:
            update.effective_message.reply_text(
                filter_list.format(chat_name),
                parse_mode=telegram.ParseMode.MARKDOWN)
            filter_list = entry
        else:
            filter_list += entry

    update.effective_message.reply_text(filter_list.format(chat_name),
                                        parse_mode=telegram.ParseMode.MARKDOWN)


# NOT ASYNC BECAUSE DISPATCHER HANDLER RAISED
@user_admin
def filters(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = msg.text.split(
        None,
        1)  # use python's maxsplit to separate Cmd, keyword, and reply_text

    conn = connected(update, context, user.id)
    if conn:
        chat_id = conn
        chat_name = context.bot.getChat(conn).title
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            chat_name = tld(chat.id, "cust_filters_local")
        else:
            chat_name = chat.title

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])
    if len(extracted) < 1:
        return
    # set trigger -> lower, so as to avoid adding duplicate filters with different cases
    keyword = extracted[0].lower()

    is_sticker = False
    is_document = False
    is_image = False
    is_voice = False
    is_audio = False
    is_video = False
    buttons = []

    # determine what the contents of the filter are - text, image, sticker, etc
    if len(extracted) >= 2:
        offset = len(extracted[1]) - len(
            msg.text)  # set correct offset relative to command + notename
        content, buttons = button_markdown_parser(
            extracted[1], entities=msg.parse_entities(), offset=offset)
        content = content.strip()
        if not content:
            msg.reply_text(tld(chat.id, "cust_filters_err_btn_only"))
            return

    elif msg.reply_to_message and msg.reply_to_message.sticker:
        content = msg.reply_to_message.sticker.file_id
        is_sticker = True

    elif msg.reply_to_message and msg.reply_to_message.document:
        content = msg.reply_to_message.document.file_id
        is_document = True

    elif msg.reply_to_message and msg.reply_to_message.photo:
        content = msg.reply_to_message.photo[
            -1].file_id  # last elem = best quality
        is_image = True

    elif msg.reply_to_message and msg.reply_to_message.audio:
        content = msg.reply_to_message.audio.file_id
        is_audio = True

    elif msg.reply_to_message and msg.reply_to_message.voice:
        content = msg.reply_to_message.voice.file_id
        is_voice = True

    elif msg.reply_to_message and msg.reply_to_message.video:
        content = msg.reply_to_message.video.file_id
        is_video = True

    else:
        msg.reply_text(tld(chat.id, "cust_filters_err_empty"))
        return

    # Add the filter
    # Note: perhaps handlers can be removed somehow using sql.get_chat_filters
    for handler in CONFIG.dispatcher.handlers.get(HANDLER_GROUP, []):
        if handler.filters == (keyword, chat_id):
            CONFIG.dispatcher.remove_handler(handler, HANDLER_GROUP)

    sql.add_filter(chat_id, keyword, content, is_sticker, is_document,
                   is_image, is_audio, is_voice, is_video, buttons)

    msg.reply_text(tld(chat.id,
                       "cust_filters_add_success").format(keyword, chat_name),
                   parse_mode=telegram.ParseMode.MARKDOWN)
    raise DispatcherHandlerStop


# NOT ASYNC BECAUSE DISPATCHER HANDLER RAISED
@user_admin
def stop_filter(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    args = update.effective_message.text.split(None, 1)

    conn = connected(update, context, user.id)
    if conn:
        chat_id = conn
        chat_name = context.bot.getChat(conn).title
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            chat_name = tld(chat.id, "cust_filters_local")
        else:
            chat_name = chat.title

    if len(args) < 2:
        return

    chat_filters = sql.get_chat_triggers(chat_id)

    if not chat_filters:
        update.effective_message.reply_text(
            tld(chat.id, "cust_filters_list_empty").format(chat_name))
        return

    for keyword in chat_filters:
        if keyword == args[1].lower():
            sql.remove_filter(chat_id, args[1].lower())
            update.effective_message.reply_text(
                tld(chat.id, "cust_filters_stop_success").format(chat_name),
                parse_mode=telegram.ParseMode.MARKDOWN)
            raise DispatcherHandlerStop

    update.effective_message.reply_text(
        tld(chat.id, "cust_filters_err_wrong_filter"))


def reply_filter(update: Update, context: CallbackContext):
    chat = update.effective_chat
    message = update.effective_message

    to_match = extract_text(message)
    if not to_match:
        return

    chat_filters = sql.get_chat_triggers(chat.id)
    for keyword in chat_filters:
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            filt = sql.get_filter(chat.id, keyword)
            if filt.is_sticker:
                message.reply_sticker(filt.reply)
            elif filt.is_document:
                try:
                    message.reply_document(filt.reply)
                except Exception:
                    return
            elif filt.is_image:
                message.reply_photo(filt.reply)
            elif filt.is_audio:
                message.reply_audio(filt.reply)
            elif filt.is_voice:
                message.reply_voice(filt.reply)
            elif filt.is_video:
                try:
                    message.reply_video(filt.reply)
                except Exception:
                    return
            elif filt.has_markdown:
                buttons = sql.get_buttons(chat.id, filt.keyword)
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                try:
                    message.reply_text(filt.reply,
                                       parse_mode=ParseMode.MARKDOWN,
                                       disable_web_page_preview=True,
                                       reply_markup=keyboard)
                except BadRequest as excp:
                    if excp.message == "Unsupported url protocol":
                        message.reply_text(
                            tld(chat.id, "cust_filters_err_protocol"))
                    elif excp.message == "Reply message not found":
                        context.bot.send_message(chat.id,
                                                 filt.reply,
                                                 parse_mode=ParseMode.MARKDOWN,
                                                 disable_web_page_preview=True,
                                                 reply_markup=keyboard)
                    else:
                        try:
                            message.reply_text(
                                tld(chat.id, "cust_filters_err_badformat"))
                        except:
                            return

            else:
                # LEGACY - all new filters will have has_markdown set to True.
                message.reply_text(filt.reply)
            break


@user_admin
def stop_all_filters(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if chat.type == "private":
        chat.title = tld(chat.id, "cust_filters_local")
    else:
        owner = chat.get_member(user.id)
        chat.title = chat.title
        if owner.status != 'creator':
            message.reply_text(tld(chat.id, "notes_must_be_creator"))
            return

    x = 0
    flist = sql.get_chat_triggers(chat.id)

    if not flist:
        message.reply_text(
            tld(chat.id, "cust_filters_list_empty").format(chat.title))
        return

    f_flist = []
    for f in flist:
        x += 1
        f_flist.append(f)

    for fx in f_flist:
        sql.remove_filter(chat.id, fx)

    message.reply_text(tld(chat.id, "cust_filters_cleanup_success").format(x))


def __stats__():
    return "• `{}` filters, across `{}` chats.".format(sql.num_filters(),
                                                       sql.num_chats())


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


__help__ = True

FILTER_HANDLER = DisableAbleCommandHandler("filter", filters)
STOP_HANDLER = DisableAbleCommandHandler("stop", stop_filter)
STOPALL_HANDLER = DisableAbleCommandHandler("stopall",
                                            stop_all_filters,
                                            run_async=True)
LIST_HANDLER = DisableAbleCommandHandler("filters",
                                         list_handlers,
                                         run_async=True,
                                         admin_ok=True)
CUST_FILTER_HANDLER = MessageHandler(CustomFilters.has_text,
                                     reply_filter,
                                     run_async=True)

CONFIG.dispatcher.add_handler(FILTER_HANDLER)
CONFIG.dispatcher.add_handler(STOP_HANDLER)
CONFIG.dispatcher.add_handler(STOPALL_HANDLER)
CONFIG.dispatcher.add_handler(LIST_HANDLER)
CONFIG.dispatcher.add_handler(CUST_FILTER_HANDLER, HANDLER_GROUP)
