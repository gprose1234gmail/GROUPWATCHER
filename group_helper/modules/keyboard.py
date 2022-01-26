
from telegram import ReplyKeyboardMarkup, KeyboardButton

from group_helper import CONFIG
from group_helper.modules.tr_engine.strings import tld
from telegram import Update
from telegram.ext import CommandHandler
from telegram.ext.callbackcontext import CallbackContext

import group_helper.modules.sql.connection_sql as con_sql


def keyboard(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    conn_id = con_sql.get_connected_chat(user.id)
    if conn_id and not conn_id == False:
        btn1 = "/disconnect - {}".format(tld(chat.id, "keyboard_disconnect"))
        btn2 = ""
        btn3 = ""
    else:
        if con_sql.get_history(user.id):
            history = con_sql.get_history(user.id)
        try:
            chat_name1 = context.bot.getChat(history.chat_id1).title
        except Exception:
            chat_name1 = ""

        try:
            chat_name2 = context.bot.getChat(history.chat_id2).title
        except Exception:
            chat_name2 = ""

        try:
            chat_name3 = context.bot.getChat(history.chat_id3).title
        except Exception:
            chat_name3 = ""

        if chat_name1:
            btn1 = "/connect {} - {}".format(history.chat_id1, chat_name1)
        else:
            btn1 = "/connect - {}".format(tld(chat.id, "keyboard_connect"))
        if chat_name2:
            btn2 = "/connect {} - {}".format(history.chat_id2, chat_name2)
        else:
            btn2 = ""
        if chat_name3:
            btn3 = "/connect {} - {}".format(history.chat_id3, chat_name3)
        else:
            btn3 = ""

        #TODO: Remove except garbage

    update.effective_message.reply_text(
        tld(chat.id, "keyboard_updated"),
        reply_markup=ReplyKeyboardMarkup([[
            KeyboardButton("/help"),
            KeyboardButton("/notes - {}".format(tld(chat.id,
                                                    "keyboard_notes")))
        ], [KeyboardButton(btn1)], [KeyboardButton(btn2)],
                                          [KeyboardButton(btn3)]]))


KEYBOARD_HANDLER = CommandHandler(["keyboard"], keyboard)
CONFIG.dispatcher.add_handler(KEYBOARD_HANDLER)
