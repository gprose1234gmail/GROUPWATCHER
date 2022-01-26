
import html
import logging

import telegram.ext as tg
from telegram import ChatPermissions, MessageEntity, ParseMode, TelegramError, Update
from telegram.error import BadRequest
from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram.ext.callbackcontext import CallbackContext
from telegram.utils.helpers import mention_html

import group_helper.modules.sql.locks_sql as sql
from group_helper import CONFIG
from group_helper.modules.disable import DisableAbleCommandHandler
from group_helper.modules.helper_funcs.chat_status import can_delete, is_user_admin, user_not_admin, user_admin, \
    bot_can_delete, is_bot_admin
from group_helper.modules.log_channel import loggable

from group_helper.modules.tr_engine.strings import tld

LOCK_TYPES = {
    'sticker':
    Filters.sticker,
    'audio':
    Filters.audio,
    'voice':
    Filters.voice,
    'document':
    Filters.document & ~Filters.animation,
    'video':
    Filters.video,
    'videonote':
    Filters.video_note,
    'contact':
    Filters.contact,
    'photo':
    Filters.photo,
    'gif':
    Filters.animation,
    'url':
    Filters.entity(MessageEntity.URL)
    | Filters.caption_entity(MessageEntity.URL),
    'bots':
    Filters.status_update.new_chat_members,
    'forward':
    Filters.forwarded,
    'game':
    Filters.game,
    'location':
    Filters.location,
}

GIF = Filters.animation
OTHER = Filters.game | Filters.sticker | GIF
MEDIA = Filters.audio | Filters.document | Filters.video | Filters.voice | Filters.photo
MESSAGES = Filters.text | Filters.contact | Filters.location | Filters.venue | Filters.command | MEDIA | OTHER

RESTRICTION_TYPES = {
    'messages': MESSAGES,
    'media': MEDIA,
    'other': OTHER,
    'all': Filters.all
}

PERM_GROUP = 1
REST_GROUP = 2


class CustomCommandHandler(tg.CommandHandler):
    def __init__(self, command, callback, **kwargs):
        super().__init__(command, callback, **kwargs)

    def check_update(self, update):
        if super().check_update(update):
            args, filter_result = super().check_update(update)

            if not filter_result:
                return False

            return args, filter_result and not (sql.is_restr_locked(
                update.effective_chat.id, 'messages') and not is_user_admin(
                    update.effective_chat, update.effective_user.id))

        return False


tg.CommandHandler = CustomCommandHandler


# NOT ASYNC
def restr_members(bot,
                  chat_id,
                  members,
                  messages=False,
                  media=False,
                  other=False,
                  previews=False):
    for mem in members:
        if mem.user in CONFIG.sudo_users:
            pass
        try:
            bot.restrict_chat_member(
                chat_id, mem.user,
                ChatPermissions(can_send_messages=messages,
                                can_send_media_messages=media,
                                can_send_other_messages=other,
                                can_add_web_page_previews=previews))
        except TelegramError:
            pass


# NOT ASYNC
def unrestr_members(bot,
                    chat_id,
                    members,
                    messages=True,
                    media=True,
                    other=True,
                    previews=True):
    for mem in members:
        try:
            bot.restrict_chat_member(
                chat_id, mem.user,
                ChatPermissions(can_send_messages=messages,
                                can_send_media_messages=media,
                                can_send_other_messages=other,
                                can_add_web_page_previews=previews))
        except TelegramError:
            pass


def locktypes(update: Update, context: CallbackContext):
    chat = update.effective_chat
    update.effective_message.reply_text(
        "\n - ".join([tld(chat.id, "locks_list_title")] +
                     sorted(list(LOCK_TYPES) + list(RESTRICTION_TYPES))))


@user_admin
@bot_can_delete
@loggable
def lock(update: Update, context: CallbackContext) -> str:
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    if can_delete(chat, context.bot.id):
        if len(args) >= 1:
            if args[0] in LOCK_TYPES:
                sql.update_lock(chat.id, args[0], locked=True)
                message.reply_text(tld(chat.id,
                                       "locks_lock_success").format(args[0]),
                                   parse_mode=ParseMode.MARKDOWN)

                return "<b>{}:</b>" \
                       "\n#LOCK" \
                       "\n<b>Admin:</b> {}" \
                       "\nLocked <code>{}</code>.".format(html.escape(chat.title),
                                                          mention_html(user.id, user.first_name), args[0])

            elif args[0] in RESTRICTION_TYPES:
                sql.update_restriction(chat.id, args[0], locked=True)
                message.reply_text(tld(chat.id,
                                       "locks_lock_success").format(args[0]),
                                   parse_mode=ParseMode.MARKDOWN)
                return "<b>{}:</b>" \
                       "\n#LOCK" \
                       "\n<b>Admin:</b> {}" \
                       "\nLocked <code>{}</code>.".format(html.escape(chat.title),
                                                          mention_html(user.id, user.first_name), args[0])

            else:
                message.reply_text(tld(chat.id, "locks_type_invalid"))
        else:
            message.reply_text(tld(chat.id, "locks_lock_no_type"))

    else:
        message.reply_text(tld(chat.id, "locks_bot_not_admin"))

    return ""


@user_admin
@loggable
def unlock(update: Update, context: CallbackContext) -> str:
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    if is_user_admin(chat, message.from_user.id):
        if len(args) >= 1:
            if args[0] in LOCK_TYPES:
                sql.update_lock(chat.id, args[0], locked=False)
                message.reply_text(tld(chat.id,
                                       "locks_unlock_success").format(args[0]),
                                   parse_mode=ParseMode.MARKDOWN)
                return "<b>{}:</b>" \
                       "\n#UNLOCK" \
                       "\n<b>Admin:</b> {}" \
                       "\nUnlocked <code>{}</code>.".format(html.escape(chat.title),
                                                            mention_html(user.id, user.first_name), args[0])

            elif args[0] in RESTRICTION_TYPES:
                sql.update_restriction(chat.id, args[0], locked=False)

                # members = users_sql.get_chat_members(chat.id)
                # if args[0] == "messages":
                #     unrestr_members(bot, chat.id, members, media=False, other=False, previews=False)

                # elif args[0] == "media":
                #     unrestr_members(bot, chat.id, members, other=False, previews=False)

                # elif args[0] == "other":
                #     unrestr_members(bot, chat.id, members, previews=False)

                # elif args[0] == "previews":
                #     unrestr_members(bot, chat.id, members)

                # elif args[0] == "all":
                #     unrestr_members(bot, chat.id, members, True, True, True, True)

                message.reply_text(tld(chat.id,
                                       "locks_unlock_success").format(args[0]),
                                   parse_mode=ParseMode.MARKDOWN)

                return "<b>{}:</b>" \
                       "\n#UNLOCK" \
                       "\n<b>Admin:</b> {}" \
                       "\nUnlocked <code>{}</code>.".format(html.escape(chat.title),
                                                            mention_html(user.id, user.first_name), args[0])
            else:
                message.reply_text(tld(chat.id, "locks_type_invalid"))

        else:
            context.bot.sendMessage(chat.id,
                                    tld(chat.id, "locks_unlock_no_type"))

    return ""


@user_not_admin
def del_lockables(update: Update, context: CallbackContext):
    chat = update.effective_chat
    message = update.effective_message

    for lockable, filter in LOCK_TYPES.items():
        if filter(update) and sql.is_locked(chat.id, lockable) and can_delete(
                chat, context.bot.id):
            if lockable == "bots":
                new_members = update.effective_message.new_chat_members
                for new_mem in new_members:
                    if new_mem.is_bot:
                        if not is_bot_admin(chat, context.bot.id):
                            message.reply_text(
                                tld(chat.id, "locks_lock_bots_no_admin"))
                            return

                        chat.kick_member(new_mem.id)
                        message.reply_text(tld(chat.id,
                                               "locks_lock_bots_kick"))
            else:
                try:
                    message.delete()
                except BadRequest as excp:
                    if excp.message == "Message to delete not found":
                        pass
                    else:
                        logging.exception("ERROR in lockables")

            break


@user_not_admin
def rest_handler(update: Update, context: CallbackContext):
    msg = update.effective_message
    chat = update.effective_chat
    for restriction, filter in RESTRICTION_TYPES.items():
        if filter(update) and sql.is_restr_locked(
                chat.id, restriction) and can_delete(chat, context.bot.id):
            try:
                msg.delete()
            except BadRequest as excp:
                if excp.message == "Message to delete not found":
                    pass
                else:
                    logging.exception("ERROR in restrictions")
            break


def build_lock_message(chat, chatP, user, chatname):
    locks = sql.get_locks(chat.id)
    restr = sql.get_restr(chat.id)

    if not locks:
        sql.init_permissions(chat.id)
        locks = sql.get_locks(chat.id)
    if not restr:
        sql.init_restrictions(chat.id)
        restr = sql.get_restr(chat.id)

    res = tld(chatP.id, "locks_list").format(
        chatname, locks.sticker, locks.audio, locks.voice, locks.document,
        locks.video, locks.videonote, locks.contact, locks.photo, locks.gif,
        locks.url, locks.bots, locks.forward, locks.game, locks.location,
        restr.messages, restr.media, restr.other, restr.preview,
        all([restr.messages, restr.media, restr.other, restr.preview]))
    return res


@user_admin
def list_locks(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user

    chatname = chat.title
    res = build_lock_message(chat, chat, user, chatname)

    update.effective_message.reply_text(res, parse_mode=ParseMode.MARKDOWN)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


__help__ = True

LOCKTYPES_HANDLER = DisableAbleCommandHandler("locktypes",
                                              locktypes,
                                              run_async=True)
LOCK_HANDLER = CommandHandler("lock",
                              lock,
                              pass_args=True,
                              filters=Filters.chat_type.groups)
UNLOCK_HANDLER = CommandHandler("unlock",
                                unlock,
                                pass_args=True,
                                run_async=True,
                                filters=Filters.chat_type.groups)
LOCKED_HANDLER = CommandHandler("locks",
                                list_locks,
                                run_async=True,
                                filters=Filters.chat_type.groups)

CONFIG.dispatcher.add_handler(LOCK_HANDLER)
CONFIG.dispatcher.add_handler(UNLOCK_HANDLER)
CONFIG.dispatcher.add_handler(LOCKTYPES_HANDLER)
CONFIG.dispatcher.add_handler(LOCKED_HANDLER)

CONFIG.dispatcher.add_handler(
    MessageHandler(Filters.all & Filters.chat_type.groups,
                   del_lockables,
                   run_async=True), PERM_GROUP)
CONFIG.dispatcher.add_handler(
    MessageHandler(Filters.all & Filters.chat_type.groups,
                   rest_handler,
                   run_async=True), REST_GROUP)
