import html

from telegram import Update
from telegram import ParseMode
from telegram.error import BadRequest
from telegram.ext import CommandHandler, Filters
from telegram.utils.helpers import mention_html, escape_markdown
from telegram.ext.callbackcontext import CallbackContext

from group_helper import CONFIG
from group_helper.modules.disable import DisableAbleCommandHandler
from group_helper.modules.helper_funcs.chat_status import bot_admin, user_admin, can_pin
from group_helper.modules.helper_funcs.extraction import extract_user
from group_helper.modules.log_channel import loggable
from group_helper.modules.sql import admin_sql as sql
from group_helper.modules.tr_engine.strings import tld

from group_helper.modules.connection import connected


@bot_admin
@user_admin
@loggable
def promote(update: Update, context: CallbackContext) -> str:
    args = context.args
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    conn = connected(update, context, user.id)
    if conn:
        chatD = context.bot.getChat(conn)
    else:
        chatD = update.effective_chat
        if chat.type == "private":
            return ""

    if not chatD.get_member(context.bot.id).can_promote_members:
        update.effective_message.reply_text(tld(chat.id, "admin_err_no_perm"))
        return ""

    member = chatD.get_member(user.id)
    if not member.can_promote_members and member.status != 'creator':
        update.effective_message.reply_text(
            tld(chat.id, "admin_err_user_no_perm"))
        return ""

    user_id = extract_user(message, args)
    if not user_id:
        message.reply_text(tld(chat.id, "common_err_no_user"))
        return ""

    user_member = chatD.get_member(user_id)
    if user_member.status == 'administrator' or user_member.status == 'creator':
        message.reply_text(tld(chat.id, "admin_err_user_admin"))
        return ""

    if user_id == context.bot.id:
        message.reply_text(tld(chat.id, "admin_err_self_promote"))
        return ""

    # set same perms as bot - bot can't assign higher perms than itself!
    bot_member = chatD.get_member(context.bot.id)

    context.bot.promoteChatMember(
        chatD.id,
        user_id,
        can_change_info=bot_member.can_change_info,
        can_post_messages=bot_member.can_post_messages,
        can_edit_messages=bot_member.can_edit_messages,
        can_delete_messages=bot_member.can_delete_messages,
        can_invite_users=bot_member.can_invite_users,
        can_restrict_members=bot_member.can_restrict_members,
        can_pin_messages=bot_member.can_pin_messages,
        can_promote_members=bot_member.can_promote_members)

    message.reply_text(tld(chat.id, "admin_promote_success").format(
        mention_html(user.id, user.first_name),
        mention_html(user_member.user.id, user_member.user.first_name),
        html.escape(chatD.title)),
                       parse_mode=ParseMode.HTML)
    return f"<b>{html.escape(chatD.title)}:</b>" \
            "\n#PROMOTED" \
           f"\n<b>Admin:</b> {mention_html(user.id, user.first_name)}" \
           f"\n<b>User:</b> {mention_html(user_member.user.id, user_member.user.first_name)}"


@bot_admin
@user_admin
@loggable
def demote(update: Update, context: CallbackContext) -> str:
    args = context.args
    chat = update.effective_chat
    message = update.effective_message
    user = update.effective_user
    conn = connected(update, context, user.id)
    if conn:
        chatD = context.bot.getChat(conn)
    else:
        chatD = update.effective_chat
        if chat.type == "private":
            return ""

    if not chatD.get_member(context.bot.id).can_promote_members:
        update.effective_message.reply_text(tld(chat.id, "admin_err_no_perm"))
        return ""

    member = chatD.get_member(user.id)
    if not member.can_promote_members and member.status != 'creator':
        update.effective_message.reply_text(
            tld(chat.id, "admin_err_user_no_perm"))
        return ""

    user_id = extract_user(message, args)
    if not user_id:
        message.reply_text(tld(chat.id, "common_err_no_user"))
        return ""

    user_member = chatD.get_member(user_id)
    if user_member.status == 'creator':
        message.reply_text(tld(chat.id, "admin_err_demote_creator"))
        return ""

    if not user_member.status == 'administrator':
        message.reply_text(tld(chat.id, "admin_err_demote_noadmin"))
        return ""

    if user_id == context.bot.id:
        message.reply_text(tld(chat.id, "admin_err_self_demote"))
        return ""

    try:
        context.bot.promoteChatMember(int(chatD.id),
                                      int(user_id),
                                      can_change_info=False,
                                      can_post_messages=False,
                                      can_edit_messages=False,
                                      can_delete_messages=False,
                                      can_invite_users=False,
                                      can_restrict_members=False,
                                      can_pin_messages=False,
                                      can_promote_members=False)
        message.reply_text(tld(chat.id, "admin_demote_success").format(
            mention_html(user.id, user.first_name),
            mention_html(user_member.user.id, user_member.user.first_name),
            html.escape(chatD.title)),
                           parse_mode=ParseMode.HTML)
        return f"<b>{html.escape(chatD.title)}:</b>" \
                "\n#DEMOTED" \
               f"\n<b>Admin:</b> {mention_html(user.id, user.first_name)}" \
               f"\n<b>User:</b> {mention_html(user_member.user.id, user_member.user.first_name)}"

    except BadRequest:
        message.reply_text(tld(chat.id, "admin_err_cant_demote"))
        return ""


@bot_admin
@can_pin
@user_admin
@loggable
def pin(update: Update, context: CallbackContext) -> str:
    args = context.args
    user = update.effective_user
    chat = update.effective_chat

    is_group = chat.type != "private" and chat.type != "channel"

    prev_message = update.effective_message.reply_to_message

    is_silent = True
    if len(args) >= 1:
        is_silent = not (args[0].lower() == 'notify' or args[0].lower()
                         == 'loud' or args[0].lower() == 'violent')

    if prev_message and is_group:
        try:
            context.bot.pinChatMessage(chat.id,
                                       prev_message.message_id,
                                       disable_notification=is_silent)
        except BadRequest as excp:
            if excp.message == "Chat_not_modified":
                pass
            else:
                raise
        return f"<b>{html.escape(chat.title)}:</b>" \
                "\n#PINNED" \
               f"\n<b>Admin:</b> {mention_html(user.id, user.first_name)}"

    return ""


@bot_admin
@can_pin
@user_admin
@loggable
def unpin(update: Update, context: CallbackContext) -> str:
    chat = update.effective_chat
    user = update.effective_user

    try:
        context.bot.unpinChatMessage(chat.id)
    except BadRequest as excp:
        if excp.message == "Chat_not_modified":
            pass
        else:
            raise

    return f"<b>{html.escape(chat.title)}:</b>" \
           "\n#UNPINNED" \
           f"\n<b>Admin:</b> {mention_html(user.id, user.first_name)}"


@bot_admin
@user_admin
def invite(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    conn = connected(update, context, user.id, need_admin=False)
    if conn:
        chatP = context.bot.getChat(conn)
    else:
        chatP = update.effective_chat
        if chat.type == "private":
            return

    if chatP.username:
        update.effective_message.reply_text(chatP.username)
    elif chatP.type == chatP.SUPERGROUP or chatP.type == chatP.CHANNEL:
        bot_member = chatP.get_member(context.bot.id)
        if bot_member.can_invite_users:
            invitelink = chatP.invite_link
            #print(invitelink)
            if not invitelink:
                invitelink = context.bot.exportChatInviteLink(chatP.id)

            update.effective_message.reply_text(invitelink)
        else:
            update.effective_message.reply_text(
                tld(chat.id, "admin_err_no_perm_invitelink"))
    else:
        update.effective_message.reply_text(
            tld(chat.id, "admin_chat_no_invitelink"))


def adminlist(update: Update, context: CallbackContext):
    chat = update.effective_chat
    administrators = update.effective_chat.get_administrators()
    text = tld(chat.id, "admin_list").format(
        update.effective_chat.title
        or tld(chat.id, "common_this_chat").lower())
    for admin in administrators:
        user = admin.user
        name = "[{}](tg://user?id={})".format(user.first_name, user.id)
        if user.username:
            esc = escape_markdown("@" + user.username)
            name = "[{}](tg://user?id={})".format(esc, user.id)
        text += "\n - {}".format(name)

    update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# TODO: Finalize this command, add automatic message deleting
@user_admin
def reaction(update: Update, context: CallbackContext) -> str:
    args = context.args
    chat = update.effective_chat
    if len(args) >= 1:
        var = args[0]
        print(var)
        if var == "False":
            sql.set_command_reaction(chat.id, False)
            update.effective_message.reply_text(
                tld(chat.id, "admin_disable_reaction"))
        elif var == "True":
            sql.set_command_reaction(chat.id, True)
            update.effective_message.reply_text(
                tld(chat.id, "admin_enable_reaction"))
        else:
            update.effective_message.reply_text(tld(chat.id,
                                                    "admin_err_wrong_arg"),
                                                parse_mode=ParseMode.MARKDOWN)
    else:
        status = sql.command_reaction(chat.id)
        update.effective_message.reply_text(tld(
            chat.id, "admin_reaction_status").format('enabled' if status ==
                                                     True else 'disabled'),
                                            parse_mode=ParseMode.MARKDOWN)


__help__ = True

PIN_HANDLER = DisableAbleCommandHandler("pin",
                                        pin,
                                        pass_args=True,
                                        admin_ok=True,
                                        run_async=True,
                                        filters=Filters.chat_type.groups)
UNPIN_HANDLER = DisableAbleCommandHandler("unpin",
                                          unpin,
                                          admin_ok=True,
                                          run_async=True,
                                          filters=Filters.chat_type.groups)

INVITE_HANDLER = CommandHandler("invitelink",
                                invite,
                                admin_ok=True,
                                run_async=True)

PROMOTE_HANDLER = DisableAbleCommandHandler("promote",
                                            promote,
                                            admin_ok=True,
                                            pass_args=True,
                                            run_async=True)
DEMOTE_HANDLER = DisableAbleCommandHandler("demote",
                                           demote,
                                           pass_args=True,
                                           admin_ok=True,
                                           run_async=True)

REACT_HANDLER = DisableAbleCommandHandler("reaction",
                                          reaction,
                                          pass_args=True,
                                          admin_ok=True,
                                          run_async=True,
                                          filters=Filters.chat_type.groups)

ADMINLIST_HANDLER = DisableAbleCommandHandler(["adminlist", "admins"],
                                              adminlist,
                                              admin_ok=True,
                                              run_async=True)

CONFIG.dispatcher.add_handler(PIN_HANDLER)
CONFIG.dispatcher.add_handler(UNPIN_HANDLER)
CONFIG.dispatcher.add_handler(INVITE_HANDLER)
CONFIG.dispatcher.add_handler(PROMOTE_HANDLER)
CONFIG.dispatcher.add_handler(DEMOTE_HANDLER)
CONFIG.dispatcher.add_handler(ADMINLIST_HANDLER)
CONFIG.dispatcher.add_handler(REACT_HANDLER)
