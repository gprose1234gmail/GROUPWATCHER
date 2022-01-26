
import re
from time import sleep
import logging

from telegram import TelegramError, Update, ParseMode
from telegram.ext.callbackcontext import CallbackContext
from telegram.error import BadRequest
from telegram.ext import MessageHandler, Filters, CommandHandler

import group_helper.modules.sql.users_sql as sql
from group_helper import CONFIG
from telegram.utils.helpers import escape_markdown
from group_helper.modules.helper_funcs.filters import CustomFilters
from group_helper.modules.helper_funcs.chat_status import bot_admin

from group_helper.modules.tr_engine.strings import tld

USERS_GROUP = 4
CHAT_GROUP = 10


def get_user_id(username):
    # ensure valid userid
    if len(username) <= 5:
        return None

    if username.startswith('@'):
        username = username[1:]

    users = sql.get_userid_by_name(username)

    if not users:
        return None

    elif len(users) == 1:
        return users[0].user_id

    else:
        for user_obj in users:
            try:
                userdat = CONFIG.dispatcher.bot.get_chat(user_obj.user_id)
                if userdat.username == username:
                    return userdat.id

            except BadRequest as excp:
                if excp.message == 'Chat not found':
                    pass
                else:
                    logging.error("Error extracting user ID")

    return None


def broadcast(update: Update, context: CallbackContext):
    to_send = update.effective_message.text.split(None, 1)
    if len(to_send) >= 2:
        chats = sql.get_all_chats() or []
        failed = 0
        for chat in chats:
            try:
                context.bot.sendMessage(int(chat.chat_id), to_send[1])
                sleep(0.1)
            except TelegramError:
                failed += 1
                logging.warning("Couldn't send broadcast to %s, group name %s",
                                str(chat.chat_id), str(chat.chat_name))

        update.effective_message.reply_text(
            "Broadcast complete. {} groups failed to receive the message, probably "
            "due to being kicked.".format(failed))


def log_user(update: Update, context: CallbackContext):
    chat = update.effective_chat
    msg = update.effective_message

    sql.update_user(msg.from_user.id, msg.from_user.username, chat.id,
                    chat.title)

    if msg.reply_to_message:
        sql.update_user(msg.reply_to_message.from_user.id,
                        msg.reply_to_message.from_user.username, chat.id,
                        chat.title)

    if msg.forward_from:
        sql.update_user(msg.forward_from.id, msg.forward_from.username)


def snipe(update: Update, context: CallbackContext):
    args = context.args

    try:
        chat_id = str(args[0])
        del args[0]
    except TypeError as excp:
        update.effective_message.reply_text(
            "Please give me a chat to echo to!")
    to_send = " ".join(args)
    if len(to_send) >= 2:
        try:
            context.bot.sendMessage(int(chat_id), str(to_send))
        except TelegramError:
            logging.warning("Couldn't send to group %s", str(chat_id))
            update.effective_message.reply_text(
                "Couldn't send the message. Perhaps I'm not part of that group?"
            )


@bot_admin
def getlink(update: Update, context: CallbackContext):
    args = context.args
    message = update.effective_message

    if args:
        pattern = re.compile(r'-\d+')
    else:
        message.reply_text("You don't seem to be referring to any chats.")
    links = "Invite link(s):\n"
    for chat_id in pattern.findall(message.text):
        try:
            chat = context.bot.getChat(chat_id)
            bot_member = chat.get_member(context.bot.id)
            if bot_member.can_invite_users:
                invitelink = context.bot.exportChatInviteLink(chat_id)
                links += str(chat_id) + ":\n" + invitelink + "\n"
            else:
                links += str(
                    chat_id
                ) + ":\nI don't have access to the invite link." + "\n"
        except BadRequest as excp:
            links += str(chat_id) + ":\n" + excp.message + "\n"
        except TelegramError as excp:
            links += str(chat_id) + ":\n" + excp.message + "\n"

    message.reply_text(links)


def leavechat(update: Update, context: CallbackContext):
    args = context.args

    if args:
        chat_id = int(args[0])
    else:
        try:
            chat = update.effective_chat
            if chat.type == "private":
                update.effective_message.reply_text(
                    "You do not seem to be referring to a chat!")
                return
            chat_id = chat.id
            reply_text = "`I'll leave this group`"
            context.bot.send_message(chat_id,
                                     reply_text,
                                     parse_mode='Markdown',
                                     disable_web_page_preview=True)
            context.bot.leaveChat(chat_id)
        except BadRequest as excp:
            if excp.message == "Chat not found":
                update.effective_message.reply_text(
                    "It looks like I've been kicked out of the group :p")
            else:
                return

    try:
        chat = context.bot.getChat(chat_id)
        titlechat = context.bot.get_chat(chat_id).title
        reply_text = "`I'll Go Away!`"
        context.bot.send_message(chat_id,
                                 reply_text,
                                 parse_mode='Markdown',
                                 disable_web_page_preview=True)
        context.bot.leaveChat(chat_id)
        update.effective_message.reply_text(
            "I'll left group {}".format(titlechat))

    except BadRequest as excp:
        if excp.message == "Chat not found":
            update.effective_message.reply_text(
                "It looks like I've been kicked out of the group :p")
        else:
            return


def slist(update: Update, context: CallbackContext):
    message = update.effective_message
    text1 = "My sudo users are:"
    for user_id in CONFIG.sudo_users:
        try:
            user = context.bot.get_chat(user_id)
            name = "[{}](tg://user?id={})".format(
                user.first_name + (user.last_name or ""), user.id)
            if user.username:
                name = escape_markdown("@" + user.username)
            text1 += "\n - `{}`".format(name)
        except BadRequest as excp:
            if excp.message == 'Chat not found':
                text1 += "\n - ({}) - not found".format(user_id)

    message.reply_text(text1 + "\n", parse_mode=ParseMode.MARKDOWN)


def chat_checker(update: Update, context: CallbackContext):
    if update.effective_message.chat.get_member(
            context.bot.id).can_send_messages == False:
        context.bot.leaveChat(update.effective_message.chat.id)


def __user_info__(user_id, chat_id):
    if user_id == CONFIG.dispatcher.bot.id:
        return tld(chat_id, "users_seen_is_bot")
    num_chats = sql.get_user_num_chats(user_id)
    return tld(chat_id, "users_seen").format(num_chats)


def __stats__():
    return "• `{}` users, across `{}` chats".format(sql.num_users(),
                                                    sql.num_chats())


def __gdpr__(user_id):
    sql.del_user(user_id)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


BROADCAST_HANDLER = CommandHandler("broadcasts",
                                   broadcast,
                                   run_async=True,
                                   filters=Filters.user(CONFIG.owner_id))
USER_HANDLER = MessageHandler(Filters.all & Filters.chat_type.groups, log_user)
SNIPE_HANDLER = CommandHandler("snipe",
                               snipe,
                               pass_args=True,
                               run_async=True,
                               filters=Filters.user(CONFIG.owner_id))
GETLINK_HANDLER = CommandHandler("getlink",
                                 getlink,
                                 pass_args=True,
                                 run_async=True,
                                 filters=Filters.user(CONFIG.owner_id))
LEAVECHAT_HANDLER = CommandHandler("leavechat",
                                   leavechat,
                                   pass_args=True,
                                   run_async=True,
                                   filters=Filters.user(CONFIG.owner_id))
SLIST_HANDLER = CommandHandler("slist",
                               slist,
                               run_async=True,
                               filters=CustomFilters.sudo_filter)
CHAT_CHECKER_HANDLER = MessageHandler(Filters.all & Filters.chat_type.groups,
                                      chat_checker)

CONFIG.dispatcher.add_handler(SNIPE_HANDLER)
CONFIG.dispatcher.add_handler(GETLINK_HANDLER)
CONFIG.dispatcher.add_handler(LEAVECHAT_HANDLER)
CONFIG.dispatcher.add_handler(SLIST_HANDLER)
CONFIG.dispatcher.add_handler(USER_HANDLER, USERS_GROUP)
CONFIG.dispatcher.add_handler(BROADCAST_HANDLER)
CONFIG.dispatcher.add_handler(CHAT_CHECKER_HANDLER, CHAT_GROUP)
