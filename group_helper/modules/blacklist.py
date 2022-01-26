import html
import logging
import re

from telegram import Update, ParseMode
from telegram.error import BadRequest
from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram.ext.callbackcontext import CallbackContext

import group_helper.modules.sql.blacklist_sql as sql
from group_helper import CONFIG
from group_helper.modules.disable import DisableAbleCommandHandler
from group_helper.modules.helper_funcs.chat_status import user_admin, user_not_admin
from group_helper.modules.helper_funcs.extraction import extract_text
from group_helper.modules.helper_funcs.misc import split_message

from group_helper.modules.connection import connected

from group_helper.modules.tr_engine.strings import tld

BLACKLIST_GROUP = 11


def blacklist(update: Update, context: CallbackContext):
    args = context.args
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    conn = connected(update, context, user.id, need_admin=False)
    if conn:
        chat_id = conn
        chat_name = context.bot.getChat(conn).title
    else:
        if chat.type == "private":
            return
        else:
            chat_id = update.effective_chat.id
            chat_name = chat.title

    filter_list = tld(chat.id, "blacklist_active_list").format(chat_name)

    all_blacklisted = sql.get_chat_blacklist(chat_id)

    if len(args) > 0 and args[0].lower() == 'copy':
        for trigger in all_blacklisted:
            filter_list += "<code>{}</code>\n".format(html.escape(trigger))
    else:
        for trigger in all_blacklisted:
            filter_list += " • <code>{}</code>\n".format(html.escape(trigger))

    split_text = split_message(filter_list)
    for text in split_text:
        if filter_list == tld(chat.id, "blacklist_active_list").format(
                chat_name):  #We need to translate
            msg.reply_text(tld(chat.id, "blacklist_no_list").format(chat_name),
                           parse_mode=ParseMode.HTML)
            return
        msg.reply_text(text, parse_mode=ParseMode.HTML)


@user_admin
def add_blacklist(update: Update, context: CallbackContext):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    words = msg.text.split(None, 1)

    conn = connected(update, context, user.id)
    if conn:
        chat_id = conn
        chat_name = context.bot.getChat(conn).title
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            return
        else:
            chat_name = chat.title

    if len(words) > 1:
        text = words[1]
        to_blacklist = list(
            set(trigger.strip() for trigger in text.split("\n")
                if trigger.strip()))
        for trigger in to_blacklist:
            sql.add_to_blacklist(chat_id, trigger.lower())

        if len(to_blacklist) == 1:
            msg.reply_text(tld(chat.id, "blacklist_add").format(
                html.escape(to_blacklist[0]), chat_name),
                           parse_mode=ParseMode.HTML)

        else:
            msg.reply_text(tld(chat.id,
                               "blacklist_add").format(len(to_blacklist)),
                           chat_name,
                           parse_mode=ParseMode.HTML)

    else:
        msg.reply_text(tld(chat.id, "blacklist_err_add_no_args"))


@user_admin
def unblacklist(update: Update, context: CallbackContext):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    words = msg.text.split(None, 1)

    conn = connected(update, context, user.id)
    if conn:
        chat_id = conn
        chat_name = context.bot.getChat(conn).title
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            return
        else:
            chat_name = chat.title

    if len(words) > 1:
        text = words[1]
        to_unblacklist = list(
            set(trigger.strip() for trigger in text.split("\n")
                if trigger.strip()))
        successful = 0
        for trigger in to_unblacklist:
            success = sql.rm_from_blacklist(chat_id, trigger.lower())
            if success:
                successful += 1

        if len(to_unblacklist) == 1:
            if successful:
                msg.reply_text(tld(chat.id, "blacklist_del").format(
                    html.escape(to_unblacklist[0]), chat_name),
                               parse_mode=ParseMode.HTML)
            else:
                msg.reply_text(tld(chat.id, "blacklist_err_not_trigger"))

        elif successful == len(to_unblacklist):
            msg.reply_text(tld(chat.id, "blacklist_multi_del").format(
                successful, chat_name),
                           parse_mode=ParseMode.HTML)

        elif not successful:
            msg.reply_text(tld(chat.id,
                               "blacklist_err_multidel_no_trigger").format(
                                   successful,
                                   len(to_unblacklist) - successful),
                           parse_mode=ParseMode.HTML)

        else:
            msg.reply_text(tld(
                chat.id, "blacklist_err_multidel_some_no_trigger").format(
                    successful, chat_name,
                    len(to_unblacklist) - successful),
                           parse_mode=ParseMode.HTML)
    else:
        msg.reply_text(tld(chat.id, "blacklist_err_del_no_args"))


@user_not_admin
def del_blacklist(update: Update, context: CallbackContext):
    chat = update.effective_chat
    message = update.effective_message
    to_match = extract_text(message)
    if not to_match:
        return

    chat_filters = sql.get_chat_blacklist(chat.id)
    for trigger in chat_filters:
        pattern = r"( |^|[^\w])" + re.escape(trigger) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            try:
                message.delete()
            except BadRequest as excp:
                if excp.message == "Message to delete not found":
                    pass
                else:
                    logging.error("Error while deleting blacklist message.")
            break


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __stats__():
    return "• `{}` blacklist triggers, across `{}` chats.".format(
        sql.num_blacklist_filters(), sql.num_blacklist_filter_chats())


__help__ = True

#TODO: Add blacklist alternative modes: warn, ban, kick, or mute.

BLACKLIST_HANDLER = DisableAbleCommandHandler("blacklist",
                                              blacklist,
                                              pass_args=True,
                                              run_async=True,
                                              admin_ok=True)
ADD_BLACKLIST_HANDLER = CommandHandler("addblacklist",
                                       add_blacklist,
                                       run_async=True)
UNBLACKLIST_HANDLER = CommandHandler(["unblacklist", "rmblacklist"],
                                     unblacklist,
                                     run_async=True)
BLACKLIST_DEL_HANDLER = MessageHandler(
    (Filters.text | Filters.command | Filters.sticker | Filters.photo)
    & Filters.chat_type.groups,
    del_blacklist,
    run_async=True)

CONFIG.dispatcher.add_handler(BLACKLIST_HANDLER)
CONFIG.dispatcher.add_handler(ADD_BLACKLIST_HANDLER)
CONFIG.dispatcher.add_handler(UNBLACKLIST_HANDLER)
CONFIG.dispatcher.add_handler(BLACKLIST_DEL_HANDLER, group=BLACKLIST_GROUP)
