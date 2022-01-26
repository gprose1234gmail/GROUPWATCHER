
import html

from telegram import Update, ChatPermissions
from telegram.error import BadRequest
from telegram.ext import Filters, MessageHandler, CommandHandler
from telegram.ext.callbackcontext import CallbackContext
from telegram.utils.helpers import mention_html

from group_helper import CONFIG
from group_helper.modules.helper_funcs.chat_status import is_user_admin, user_admin, can_restrict
from group_helper.modules.log_channel import loggable
from group_helper.modules.sql import antiflood_sql as sql

from group_helper.modules.tr_engine.strings import tld

FLOOD_GROUP = 3


@loggable
def check_flood(update: Update, context: CallbackContext) -> str:
    user = update.effective_user
    chat = update.effective_chat
    msg = update.effective_message

    if not user:  # ignore channels
        return ""

    # ignore admins
    if is_user_admin(chat, user.id):
        sql.update_flood(chat.id, None)
        return ""

    should_ban = sql.update_flood(chat.id, user.id)
    if not should_ban:
        return ""

    try:
        context.bot.restrict_chat_member(
            chat.id, user.id, ChatPermissions(can_send_messages=False))
        msg.reply_text(tld(chat.id, "flood_mute"))

        return tld(chat.id, "flood_logger_success").format(
            html.escape(chat.title), mention_html(user.id, user.first_name))

    except BadRequest:
        msg.reply_text(tld(chat.id, "flood_err_no_perm"))
        sql.set_flood(chat.id, 0)
        return tld(chat.id, "flood_logger_fail").format(chat.title)


@user_admin
@can_restrict
@loggable
def set_flood(update: Update, context: CallbackContext) -> str:
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if len(args) >= 1:
        val = args[0].lower()
        if val == "off" or val == "no" or val == "0":
            sql.set_flood(chat.id, 0)
            message.reply_text(tld(chat.id, "flood_set_off"))

        elif val.isdigit():
            amount = int(val)
            if amount <= 0:
                sql.set_flood(chat.id, 0)
                message.reply_text(tld(chat.id, "flood_set_off"))
                return tld(chat.id, "flood_logger_set_off").format(
                    html.escape(chat.title),
                    mention_html(user.id, user.first_name))

            elif amount < 3:
                message.reply_text(tld(chat.id, "flood_err_num"))
                return ""

            else:
                sql.set_flood(chat.id, amount)
                message.reply_text(tld(chat.id, "flood_set").format(amount))
                return tld(chat.id, "flood_logger_set_on").format(
                    html.escape(chat.title),
                    mention_html(user.id, user.first_name), amount)

        else:
            message.reply_text(tld(chat.id, "flood_err_args"))

    return ""


def flood(update: Update, context: CallbackContext):
    chat = update.effective_chat

    limit = sql.get_flood_limit(chat.id)
    if limit == 0:
        update.effective_message.reply_text(tld(chat.id, "flood_status_off"))
    else:
        update.effective_message.reply_text(
            tld(chat.id, "flood_status_on").format(limit))


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


__help__ = True

# TODO: Add actions: ban/kick/mute/tban/tmute

FLOOD_BAN_HANDLER = MessageHandler(Filters.all & ~Filters.status_update
                                   & Filters.chat_type.groups,
                                   check_flood,
                                   run_async=True)
SET_FLOOD_HANDLER = CommandHandler("setflood",
                                   set_flood,
                                   pass_args=True,
                                   run_async=True,
                                   filters=Filters.chat_type.groups)
FLOOD_HANDLER = CommandHandler("flood",
                               flood,
                               run_async=True,
                               filters=Filters.chat_type.groups)

CONFIG.dispatcher.add_handler(FLOOD_BAN_HANDLER, FLOOD_GROUP)
CONFIG.dispatcher.add_handler(SET_FLOOD_HANDLER)
CONFIG.dispatcher.add_handler(FLOOD_HANDLER)
