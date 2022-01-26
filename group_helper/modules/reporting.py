
import html
import logging
from typing import Optional
from telegram import Message, Chat, Update, User, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest, Unauthorized
from telegram.ext import CommandHandler, CallbackQueryHandler, Filters, MessageHandler
from telegram.ext.callbackcontext import CallbackContext
from telegram.utils.helpers import mention_html

from group_helper import CONFIG
from group_helper.modules.helper_funcs.chat_status import user_not_admin, user_admin
from group_helper.modules.log_channel import loggable
from group_helper.modules.sql import reporting_sql as sql
from group_helper.modules.tr_engine.strings import tld

REPORT_GROUP = 5


@user_admin
def report_setting(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    if chat.type == chat.PRIVATE:
        if len(args) >= 1:
            if args[0] in ("yes", "on"):
                sql.set_user_setting(chat.id, True)
                msg.reply_text(tld(chat.id, "reports_pm_on"))

            elif args[0] in ("no", "off"):
                sql.set_user_setting(chat.id, False)
                msg.reply_text(tld(chat.id, "reports_pm_off"))
        else:
            msg.reply_text(tld(chat.id, "reports_pm_pref").format(
                sql.user_should_report(chat.id)),
                           parse_mode=ParseMode.MARKDOWN)

    else:
        if len(args) >= 1:
            if args[0] in ("yes", "on"):
                sql.set_chat_setting(chat.id, True)
                msg.reply_text(tld(chat.id, "reports_chat_on"))

            elif args[0] in ("no", "off"):
                sql.set_chat_setting(chat.id, False)
                msg.reply_text(tld(chat.id, "reports_chat_off"))
        else:
            msg.reply_text(tld(chat.id, "reports_chat_pref").format(
                sql.chat_should_report(chat.id)),
                           parse_mode=ParseMode.MARKDOWN)


@user_not_admin
@loggable
def report(update: Update, context: CallbackContext) -> str:
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    if chat and message.reply_to_message and sql.chat_should_report(chat.id):
        reported_user = message.reply_to_message.from_user  # type: Optional[User]
        chat_name = chat.title or chat.first or chat.username
        admin_list = chat.get_administrators()

        if int(reported_user.id) == int(user.id):
            return

        if chat.username and chat.type == Chat.SUPERGROUP:
            msg = "<b>{}:</b>" \
                  "\n<b>Reported user:</b> {} (<code>{}</code>)" \
                  "\n<b>Reported by:</b> {} (<code>{}</code>)".format(html.escape(chat.title),
                                                                      mention_html(
                                                                          reported_user.id,
                                                                          reported_user.first_name),
                                                                      reported_user.id,
                                                                      mention_html(user.id,
                                                                                   user.first_name),
                                                                      user.id)
            link = "\n<b>Link:</b> " \
                   "<a href=\"http://telegram.me/{}/{}\">click here</a>".format(chat.username, message.message_id)

            should_forward = True
            keyboard = [[
                InlineKeyboardButton(
                    u"➡ Message",
                    url="https://t.me/{}/{}".format(
                        chat.username,
                        str(message.reply_to_message.message_id)))
            ],
                        [
                            InlineKeyboardButton(
                                u"⚠ Kick",
                                callback_data="report_{}=kick={}={}".format(
                                    chat.id, reported_user.id,
                                    reported_user.first_name)),
                            InlineKeyboardButton(
                                u"⛔️ Ban",
                                callback_data="report_{}=banned={}={}".format(
                                    chat.id, reported_user.id,
                                    reported_user.first_name))
                        ],
                        [
                            InlineKeyboardButton(
                                u"❎ Delete Message",
                                callback_data="report_{}=delete={}={}".format(
                                    chat.id, reported_user.id,
                                    message.reply_to_message.message_id))
                        ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

        else:
            msg = "{} is calling for admins in \"{}\"!".format(
                mention_html(user.id, user.first_name), html.escape(chat_name))
            link = ""
            should_forward = True

        for admin in admin_list:
            if admin.user.is_bot:  # can't message bots
                continue

            if sql.user_should_report(admin.user.id):
                try:
                    if not chat.type == Chat.SUPERGROUP:
                        context.bot.send_message(admin.user.id,
                                                 msg + link,
                                                 parse_mode=ParseMode.HTML,
                                                 disable_web_page_preview=True)

                        if should_forward:
                            message.reply_to_message.forward(admin.user.id)

                            if len(
                                    message.text.split()
                            ) > 1:  # If user is giving a reason, send his message too
                                message.forward(admin.user.id)

                    if not chat.username:
                        context.bot.send_message(admin.user.id,
                                                 msg + link,
                                                 parse_mode=ParseMode.HTML,
                                                 disable_web_page_preview=True)

                        if should_forward:
                            message.reply_to_message.forward(admin.user.id)

                            if len(
                                    message.text.split()
                            ) > 1:  # If user is giving a reason, send his message too
                                message.forward(admin.user.id)

                    if chat.username and chat.type == Chat.SUPERGROUP:
                        context.bot.send_message(admin.user.id,
                                                 msg + link,
                                                 parse_mode=ParseMode.HTML,
                                                 reply_markup=reply_markup,
                                                 disable_web_page_preview=True)

                        if should_forward:
                            message.reply_to_message.forward(admin.user.id)

                            if len(
                                    message.text.split()
                            ) > 1:  # If user is giving a reason, send his message too
                                message.forward(admin.user.id)

                except Unauthorized:
                    pass
                except BadRequest as excp:  # TODO: cleanup exceptions
                    logging.error(f"Exception while reporting user : {excp}")

        message.reply_to_message.reply_text(tld(
            chat.id,
            "reports_success").format(mention_html(user.id, user.first_name)),
                                            parse_mode=ParseMode.HTML,
                                            disable_web_page_preview=True)
        return msg

    return ""


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    splitter = query.data.replace("report_", "").split("=")
    if splitter[1] == "kick":
        try:
            context.bot.kickChatMember(splitter[0], splitter[2])
            context.bot.unbanChatMember(splitter[0], splitter[2])
            query.answer("✅ Succesfully kicked")
            return ""
        except Exception as err:
            query.answer("❎ Failed to kick")
            context.bot.sendMessage(text="Error: {}".format(err),
                                    chat_id=query.message.chat_id,
                                    parse_mode=ParseMode.HTML)
    elif splitter[1] == "banned":
        try:
            context.bot.kickChatMember(splitter[0], splitter[2])
            query.answer("✅  Succesfully Banned")
            return ""
        except Exception as err:
            context.bot.sendMessage(text="Error: {}".format(err),
                                    chat_id=query.message.chat_id,
                                    parse_mode=ParseMode.HTML)
            query.answer("❎ Failed to ban")
    elif splitter[1] == "delete":
        try:
            context.bot.deleteMessage(splitter[0], splitter[3])
            query.answer("✅ Message Deleted")
            return ""
        except Exception as err:
            context.bot.sendMessage(text="Error: {}".format(err),
                                    chat_id=query.message.chat_id,
                                    parse_mode=ParseMode.HTML)
            query.answer("❎ Failed to delete message!")


__help__ = True

REPORT_HANDLER = CommandHandler("report",
                                report,
                                run_async=True,
                                filters=Filters.chat_type.groups)
SETTING_HANDLER = CommandHandler("reports",
                                 report_setting,
                                 pass_args=True,
                                 run_async=True)
ADMIN_REPORT_HANDLER = MessageHandler(Filters.regex("(?i)@admin(s)?"),
                                      report,
                                      run_async=True)

report_button_user_handler = CallbackQueryHandler(buttons, pattern=r"report_")
CONFIG.dispatcher.add_handler(report_button_user_handler)

CONFIG.dispatcher.add_handler(REPORT_HANDLER, REPORT_GROUP)
CONFIG.dispatcher.add_handler(ADMIN_REPORT_HANDLER, REPORT_GROUP)
CONFIG.dispatcher.add_handler(SETTING_HANDLER)
