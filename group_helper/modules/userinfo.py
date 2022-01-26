
import html

from telegram import Update
from telegram import ParseMode, MAX_MESSAGE_LENGTH
from telegram.ext.callbackcontext import CallbackContext
from telegram.utils.helpers import escape_markdown

import group_helper.modules.sql.userinfo_sql as sql
from group_helper import CONFIG
from group_helper.modules.disable import DisableAbleCommandHandler
from group_helper.modules.helper_funcs.extraction import extract_user

from group_helper.modules.tr_engine.strings import tld


def about_me(update: Update, context: CallbackContext):
    args = context.args
    message = update.effective_message
    user_id = extract_user(message, args)
    chat = update.effective_chat

    if user_id:
        user = context.bot.get_chat(user_id)
    else:
        user = message.from_user

    info = sql.get_user_me_info(user.id)

    if info:
        update.effective_message.reply_text("*{}*:\n{}".format(
            user.first_name, escape_markdown(info)),
                                            parse_mode=ParseMode.MARKDOWN)
    elif message.reply_to_message:
        username = message.reply_to_message.from_user.first_name
        update.effective_message.reply_text(
            tld(chat.id, 'userinfo_about_not_set_they').format(username))
    else:
        update.effective_message.reply_text(
            tld(chat.id, 'userinfo_about_not_set_you'))


def set_about_me(update: Update, context: CallbackContext):
    chat = update.effective_chat
    message = update.effective_message
    user_id = message.from_user.id
    if user_id == 1087968824:
        message.reply_text(tld(chat.id, 'userinfo_anonymous_about'))
        return

    text = message.text
    info = text.split(
        None, 1
    )  # use python's maxsplit to only remove the cmd, hence keeping newlines.
    if len(info) == 2:
        if len(info[1]) < MAX_MESSAGE_LENGTH // 4:
            sql.set_user_me_info(user_id, info[1])
            message.reply_text(tld(chat.id, 'userinfo_about_set_success'))
        else:
            message.reply_text(
                tld(chat.id,
                    'userinfo_about_too_long').format(MAX_MESSAGE_LENGTH // 4,
                                                      len(info[1])))


def about_bio(update: Update, context: CallbackContext):
    args = context.args
    message = update.effective_message
    chat = update.effective_chat
    user_id = extract_user(message, args)
    if user_id:
        user = context.bot.get_chat(user_id)
    else:
        user = message.from_user

    info = sql.get_user_bio(user.id)

    if info:
        update.effective_message.reply_text("*{}*:\n{}".format(
            user.first_name, escape_markdown(info)),
                                            parse_mode=ParseMode.MARKDOWN)
    elif message.reply_to_message:
        username = user.first_name
        update.effective_message.reply_text(
            tld(chat.id, 'userinfo_bio_none_they').format(username))
    else:
        update.effective_message.reply_text(
            tld(chat.id, 'userinfo_bio_none_you'))


def set_about_bio(update: Update, context: CallbackContext):
    chat = update.effective_chat
    message = update.effective_message
    sender = update.effective_user
    if message.reply_to_message:
        repl_message = message.reply_to_message
        user_id = repl_message.from_user.id
        if user_id == 1087968824:
            message.reply_text(tld(chat.id, 'userinfo_anonymous_bio'))
            return
        if user_id == message.from_user.id:
            message.reply_text(tld(chat.id, 'userinfo_bio_you_cant_set'))
            return
        elif user_id == context.bot.id and sender.id not in CONFIG.sudo_users:
            message.reply_text(tld(chat.id, 'userinfo_bio_bot_sudo_only'))
            return
        elif user_id in CONFIG.sudo_users and sender.id not in CONFIG.sudo_users:
            message.reply_text(tld(chat.id, 'userinfo_bio_sudo_sudo_only'))
            return
        elif user_id == CONFIG.owner_id:
            message.reply_text(tld(chat.id, 'userinfo_bio_owner_nobio'))
            return

        text = message.text
        bio = text.split(
            None, 1
        )  # use python's maxsplit to only remove the cmd, hence keeping newlines.
        if len(bio) == 2:
            if len(bio[1]) < MAX_MESSAGE_LENGTH // 4:
                sql.set_user_bio(user_id, bio[1])
                message.reply_text("Updated {}'s bio!".format(
                    repl_message.from_user.first_name))
            else:
                message.reply_text(
                    tld(chat.id, 'userinfo_bio_too_long').format(
                        MAX_MESSAGE_LENGTH // 4, len(bio[1])))
    else:
        message.reply_text(tld(chat.id, 'userinfo_bio_set_no_reply'))


def __user_info__(user_id, chat_id):
    bio = html.escape(sql.get_user_bio(user_id) or "")
    me = html.escape(sql.get_user_me_info(user_id) or "")
    if bio and me:
        return tld(chat_id, "userinfo_what_i_and_other_say").format(me, bio)
    elif bio:
        return tld(chat_id, "userinfo_what_other_say").format(bio)
    elif me:
        return tld(chat_id, "userinfo_what_i_say").format(me)
    else:
        return ""


def __gdpr__(user_id):
    sql.clear_user_info(user_id)
    sql.clear_user_bio(user_id)


__help__ = True

SET_BIO_HANDLER = DisableAbleCommandHandler("setbio",
                                            set_about_bio,
                                            run_async=True)
GET_BIO_HANDLER = DisableAbleCommandHandler("bio",
                                            about_bio,
                                            pass_args=True,
                                            run_async=True)

SET_ABOUT_HANDLER = DisableAbleCommandHandler("setme",
                                              set_about_me,
                                              run_async=True)
GET_ABOUT_HANDLER = DisableAbleCommandHandler("me",
                                              about_me,
                                              pass_args=True,
                                              run_async=True)

CONFIG.dispatcher.add_handler(SET_BIO_HANDLER)
CONFIG.dispatcher.add_handler(GET_BIO_HANDLER)
CONFIG.dispatcher.add_handler(SET_ABOUT_HANDLER)
CONFIG.dispatcher.add_handler(GET_ABOUT_HANDLER)
