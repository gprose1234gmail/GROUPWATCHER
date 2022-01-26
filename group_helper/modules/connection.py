from typing import Optional

from telegram import ParseMode
from telegram import Chat, Update, User
from telegram.ext import CommandHandler
from telegram.ext.callbackcontext import CallbackContext

import group_helper.modules.sql.connection_sql as sql
from group_helper import CONFIG
from group_helper.modules.helper_funcs.chat_status import user_admin

from group_helper.modules.tr_engine.strings import tld

from group_helper.modules.keyboard import keyboard


@user_admin
def allow_connections(update: Update, context: CallbackContext) -> str:
    args = context.args
    chat = update.effective_chat  # type: Optional[Chat]
    if chat.type != chat.PRIVATE:
        if len(args) >= 1:
            var = args[0]
            print(var)
            if var == "no" or var == "off":
                sql.set_allow_connect_to_chat(chat.id, False)
                update.effective_message.reply_text(
                    tld(chat.id, "connection_disable"))
            elif var == "yes" or var == "on":
                sql.set_allow_connect_to_chat(chat.id, True)
                update.effective_message.reply_text(
                    tld(chat.id, "connection_enable"))
            else:
                update.effective_message.reply_text(
                    tld(chat.id, "connection_err_wrong_arg"))
        else:
            update.effective_message.reply_text(
                tld(chat.id, "connection_err_wrong_arg"))
    else:
        update.effective_message.reply_text(
            tld(chat.id, "connection_err_wrong_arg"))


def connect_chat(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    if update.effective_chat.type == 'private':
        if len(args) >= 1:
            try:
                connect_chat = int(args[0])
            except ValueError:
                update.effective_message.reply_text(
                    tld(chat.id, "common_err_invalid_chatid"))
                return
            if (context.bot.get_chat_member(
                    connect_chat, update.effective_message.from_user.id).status
                    in ('administrator', 'creator') or
                (sql.allow_connect_to_chat(connect_chat) == True)
                    and context.bot.get_chat_member(
                        connect_chat,
                        update.effective_message.from_user.id).status in
                ('member')) or (user.id in CONFIG.sudo_users):

                connection_status = sql.connect(
                    update.effective_message.from_user.id, connect_chat)
                if connection_status:
                    chat_name = CONFIG.dispatcher.bot.getChat(
                        connected(update, context, user.id,
                                  need_admin=False)).title
                    update.effective_message.reply_text(
                        tld(chat.id, "connection_success").format(chat_name),
                        parse_mode=ParseMode.MARKDOWN)

                    # Add chat to connection history
                    history = sql.get_history(user.id)
                    if history:
                        # Vars
                        if history.chat_id1:
                            history1 = int(history.chat_id1)
                        if history.chat_id2:
                            history2 = int(history.chat_id2)
                        if history.chat_id3:
                            history3 = int(history.chat_id3)
                        if history.updated:
                            number = history.updated

                        if number == 1 and connect_chat != history2 and connect_chat != history3:
                            history1 = connect_chat
                            number = 2
                        elif number == 2 and connect_chat != history1 and connect_chat != history3:
                            history2 = connect_chat
                            number = 3
                        elif number >= 3 and connect_chat != history2 and connect_chat != history1:
                            history3 = connect_chat
                            number = 1
                        else:
                            print("Error")

                        print(history.updated)
                        print(number)

                        sql.add_history(user.id, history1, history2, history3,
                                        number)
                        # print(history.user_id, history.chat_id1, history.chat_id2, history.chat_id3, history.updated)
                    else:
                        sql.add_history(user.id, connect_chat, "0", "0", 2)
                    # Rebuild user's keyboard
                    keyboard(update, context)

                else:
                    update.effective_message.reply_text(
                        tld(chat.id, "connection_fail"))
            else:
                update.effective_message.reply_text(
                    tld(chat.id, "connection_err_not_allowed"))
        else:
            update.effective_message.reply_text(
                tld(chat.id, "connection_err_no_chatid"))
            history = sql.get_history(user.id)
            # print(history.user_id, history.chat_id1, history.chat_id2, history.chat_id3, history.updated)

    elif update.effective_chat.type == 'supergroup':
        connect_chat = chat.id
        if (context.bot.get_chat_member(
                connect_chat, update.effective_message.from_user.id).status
                in ('administrator', 'creator') or
            (sql.allow_connect_to_chat(connect_chat) == True)
                and context.bot.get_chat_member(
                    connect_chat, update.effective_message.from_user.id).status
                in 'member') or (user.id in CONFIG.sudo_users):

            connection_status = sql.connect(
                update.effective_message.from_user.id, connect_chat)
            if connection_status:
                update.effective_message.reply_text(
                    tld(chat.id, "connection_success").format(chat.id),
                    parse_mode=ParseMode.MARKDOWN)
            else:
                update.effective_message.reply_text(
                    tld(chat.id, "connection_fail"),
                    parse_mode=ParseMode.MARKDOWN)
        else:
            update.effective_message.reply_text(
                tld(chat.id, "common_err_no_admin"))

    else:
        update.effective_message.reply_text(tld(chat.id, "common_cmd_pm_only"))


def disconnect_chat(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    if update.effective_chat.type == 'private':
        disconnection_status = sql.disconnect(
            update.effective_message.from_user.id)
        if disconnection_status:
            sql.disconnected_chat = update.effective_message.reply_text(
                tld(chat.id, "connection_dis_success"))
            #Rebuild user's keyboard
            keyboard(update, context)
        else:
            update.effective_message.reply_text(
                tld(chat.id, "connection_dis_fail"))
    elif update.effective_chat.type == 'supergroup':
        update.effective_message.reply_text(tld(chat.id, 'common_cmd_pm_only'))
    else:
        update.effective_message.reply_text(tld(chat.id, "common_cmd_pm_only"))


def connected(update: Update,
              context: CallbackContext,
              user_id,
              need_admin=True):
    chat = update.effective_chat  # type: Optional[Chat]
    if chat.type == chat.PRIVATE and sql.get_connected_chat(user_id):
        conn_id = sql.get_connected_chat(user_id).chat_id
        if (context.bot.get_chat_member(
                conn_id, user_id).status in ('administrator', 'creator') or
            (sql.allow_connect_to_chat(connect_chat) == True)
                and context.bot.get_chat_member(
                    user_id, update.effective_message.from_user.id).status in
            ('member')) or (user_id in CONFIG.sudo_users):
            if need_admin:
                if context.bot.get_chat_member(
                        conn_id,
                        update.effective_message.from_user.id).status in (
                            'administrator',
                            'creator') or user_id in CONFIG.sudo_users:
                    return conn_id
                else:
                    update.effective_message.reply_text(
                        tld(chat.id, "connection_err_no_admin"))
                    return
            else:
                return conn_id
        else:
            update.effective_message.reply_text(
                tld(chat.id, "connection_err_unknown"))
            disconnect_chat(update, context)
            return
    else:
        return False


__help__ = True

CONNECT_CHAT_HANDLER = CommandHandler(["connect", "connection"],
                                      connect_chat,
                                      pass_args=True,
                                      run_async=True)
DISCONNECT_CHAT_HANDLER = CommandHandler("disconnect", disconnect_chat)
ALLOW_CONNECTIONS_HANDLER = CommandHandler("allowconnect",
                                           allow_connections,
                                           pass_args=True,
                                           run_async=True)

CONFIG.dispatcher.add_handler(CONNECT_CHAT_HANDLER)
CONFIG.dispatcher.add_handler(DISCONNECT_CHAT_HANDLER)
CONFIG.dispatcher.add_handler(ALLOW_CONNECTIONS_HANDLER)
