import json
import requests

from telegram import Update, ParseMode
from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram.ext.callbackcontext import CallbackContext

import group_helper.modules.sql.antispam_sql as sql
from group_helper import CONFIG
from group_helper.modules.helper_funcs.chat_status import user_admin, is_user_admin

from group_helper.modules.tr_engine.strings import tld

GBAN_ENFORCE_GROUP = 6


def check_and_ban(update, user_id, should_message=True):
    chat = update.effective_chat
    message = update.effective_message
    try:
        if CONFIG.spamwatch_api is not None:
            headers = {'Authorization': f'Bearer {CONFIG.spamwatch_api}'}
            resp = requests.get("https://api.spamwat.ch/banlist/{user_id}",
                                headers=headers,
                                timeout=5)
            if resp.status_code == 200:
                sw_ban = json.loads(resp.content)
                reason = sw_ban['reason']
                chat.kick_member(user_id)
                if should_message:
                    message.reply_text(tld(
                        chat.id, "antispam_spamwatch_banned").format(reason),
                                       parse_mode=ParseMode.HTML)
                    return
                else:
                    return
        else:
            return
    except:
        pass


def enforce_gban(update: Update, context: CallbackContext):
    # Not using @restrict handler to avoid spamming - just ignore if cant gban.
    try:
        if sql.does_chat_gban(
                update.effective_chat.id) and update.effective_chat.get_member(
                    context.bot.id).can_restrict_members:
            user = update.effective_user
            chat = update.effective_chat
            msg = update.effective_message

            if user and not is_user_admin(chat, user.id):
                check_and_ban(update, user.id)
                return

            if msg.new_chat_members:
                new_members = update.effective_message.new_chat_members
                for mem in new_members:
                    check_and_ban(update, mem.id)
                    return

            if msg.reply_to_message:
                user = msg.reply_to_message.from_user
                if user and not is_user_admin(chat, user.id):
                    check_and_ban(update, user.id, should_message=False)
                    return
    except Exception:
        # Often timeout, bot kicked from chat, or bot is not in chat.
        return


@user_admin
def antispam(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    if len(args) > 0:
        if args[0].lower() in ["on", "yes"]:
            sql.enable_antispam(chat.id)
            update.effective_message.reply_text(tld(chat.id, "antispam_on"))
        elif args[0].lower() in ["off", "no"]:
            sql.disable_antispam(chat.id)
            update.effective_message.reply_text(tld(chat.id, "antispam_off"))
    else:
        update.effective_message.reply_text(
            tld(chat.id,
                "antispam_err_wrong_arg").format(sql.does_chat_gban(chat.id)))


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


__help__ = True

ANTISPAM_STATUS = CommandHandler("antispam",
                                 antispam,
                                 pass_args=True,
                                 run_async=True,
                                 filters=Filters.chat_type.groups)

GBAN_ENFORCER = MessageHandler(Filters.all & Filters.chat_type.groups,
                               enforce_gban,
                               run_async=True)

CONFIG.dispatcher.add_handler(ANTISPAM_STATUS)

if CONFIG.strict_antispam:  # enforce GBANS if this is set
    CONFIG.dispatcher.add_handler(GBAN_ENFORCER, GBAN_ENFORCE_GROUP)
