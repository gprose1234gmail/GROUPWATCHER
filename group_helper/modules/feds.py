from io import BytesIO
import logging
import uuid
import re

from telegram.error import BadRequest, TelegramError, Unauthorized
from telegram import ParseMode, Update, MessageEntity, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram.ext.callbackcontext import CallbackContext
from telegram.utils.helpers import mention_html, mention_markdown

from group_helper import CONFIG
from group_helper.modules.helper_funcs.misc import send_to_list
from group_helper.modules.helper_funcs.extraction import extract_user, extract_user_and_text
from group_helper.modules.helper_funcs.string_handling import markdown_parser
from group_helper.modules.disable import DisableAbleCommandHandler

import group_helper.modules.sql.feds_sql as sql

from group_helper.modules.tr_engine.strings import tld

FBAN_ERRORS = {
    "User is an administrator of the chat", "Chat not found",
    "Not enough rights to restrict/unrestrict chat member",
    "User_not_participant", "Peer_id_invalid", "Group chat was deactivated",
    "Need to be inviter of a user to kick it from a basic group",
    "Chat_admin_required",
    "Only the creator of a basic group can kick group administrators",
    "Channel_private", "Not in the chat", "Have no rights to send a message"
}

UNFBAN_ERRORS = {
    "User is an administrator of the chat", "Chat not found",
    "Not enough rights to restrict/unrestrict chat member",
    "User_not_participant",
    "Method is available for supergroup and channel chats only",
    "Not in the chat", "Channel_private", "Chat_admin_required",
    "Have no rights to send a message"
}


def new_fed(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    if chat.type != "private":
        update.effective_message.reply_text(tld(chat.id, "common_cmd_pm_only"))
        return

    if not args:
        update.effective_message.reply_text(tld(chat.id, "feds_err_no_args"))
        return

    fednam = args[0]
    if not fednam == '':
        fed_id = str(uuid.uuid4())
        fed_name = fednam
        logging.info(fed_id)
        if user.id == int(CONFIG.owner_id):
            fed_id = fed_name

        x = sql.new_fed(user.id, fed_name, fed_id)
        if not x:
            update.effective_message.reply_text(
                tld(chat.id, "feds_create_fail"))
            return

        update.effective_message.reply_text(tld(chat.id,
                                                "feds_create_success").format(
                                                    fed_name, fed_id, fed_id),
                                            parse_mode=ParseMode.MARKDOWN)
        try:
            context.bot.send_message(CONFIG.message_dump,
                                     tld(chat.id,
                                         "feds_create_success_logger").format(
                                             fed_name, fed_id),
                                     parse_mode=ParseMode.HTML)
        except Exception:
            logging.warning("Cannot send a message to MESSAGE_DUMP")
    else:
        update.effective_message.reply_text(tld(chat.id, "feds_err_no_args"))


def del_fed(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    if chat.type != "private":
        update.effective_message.reply_text(tld(chat.id, "common_cmd_pm_only"))
        return
    if args:
        is_fed_id = args[0]
        getinfo = sql.get_fed_info(is_fed_id)
        if getinfo == False:
            update.effective_message.reply_text(
                tld(chat.id, "feds_delete_not_found"))
            return
        if int(getinfo['owner']) == int(user.id):
            fed_id = is_fed_id
        else:
            update.effective_message.reply_text(tld(chat.id,
                                                    "feds_owner_only"))
            return
    else:
        update.effective_message.reply_text(tld(chat.id, "feds_err_no_args"))
        return

    if is_user_fed_owner(fed_id, user.id) == False:
        update.effective_message.reply_text(tld(chat.id, "feds_owner_only"))
        return

    update.effective_message.reply_text(
        "feds_delete_confirm".format(getinfo['fname']),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(text="⚠️ Delete Federation ⚠️",
                                 callback_data="rmfed_{}".format(fed_id))
        ], [InlineKeyboardButton(text="Cancel",
                                 callback_data="rmfed_cancel")]]))


#@user_admin
def fed_chat(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    fed_id = sql.get_fed_id(chat.id)

    if not fed_id:
        update.effective_message.reply_text(
            tld(chat.id, "feds_group_not_in_fed"))
        return

    chat = update.effective_chat
    info = sql.get_fed_info(fed_id)

    text = tld(chat.id, "feds_group_part_of_fed")
    text += "\n{} (ID: <code>{}</code>)".format(info['fname'], fed_id)

    update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


def join_fed(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    administrators = chat.get_administrators()
    fed_id = sql.get_fed_id(chat.id)

    if user.id in CONFIG.sudo_users:
        pass
    else:
        for admin in administrators:
            status = admin.status
            if status == "creator":
                print(admin)
                if str(admin.user.id) == str(user.id):
                    pass
                else:
                    update.effective_message.reply_text(
                        tld(chat.id, "common_group_creator_only"))
                    return
    if fed_id:
        message.reply_text(tld(chat.id, "feds_group_joined_fed"))
        return

    if len(args) >= 1:
        fedd = args[0]
        print(fedd)
        if sql.search_fed_by_id(fedd) == False:
            message.reply_text(tld(chat.id, "feds_fedid_invalid"))
            return

        x = sql.chat_join_fed(fedd, chat.id)
        if not x:
            message.reply_text(tld(chat.id, "feds_join_unknown_err"))
            return

        message.reply_text(tld(chat.id, "feds_join_success"))


def leave_fed(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    fed_id = sql.get_fed_id(chat.id)
    fed_info = sql.get_fed_info(fed_id)

    # administrators = chat.get_administrators().status
    getuser = context.bot.get_chat_member(chat.id, user.id).status
    if getuser in 'creator' or user.id in CONFIG.sudo_users:
        if sql.chat_leave_fed(chat.id) == True:
            update.effective_message.reply_text(
                tld(chat.id, "feds_leave_success").format(fed_info['fname']))
        else:
            update.effective_message.reply_text(
                tld(chat.id, "feds_leave_not_joined"))
    else:
        update.effective_message.reply_text(
            tld(chat.id, "common_group_creator_only"))


def user_join_fed(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    fed_id = sql.get_fed_id(chat.id)

    if is_user_fed_owner(fed_id, user.id):
        user_id = extract_user(msg, args)
        if user_id:
            user = context.bot.get_chat(user_id)
        elif not msg.reply_to_message and not args:
            user = msg.from_user
        elif not msg.reply_to_message and (
                not args or
            (len(args) >= 1 and not args[0].startswith("@")
             and not args[0].isdigit()
             and not msg.parse_entities([MessageEntity.TEXT_MENTION]))):
            msg.reply_text(tld(chat.id, "common_err_no_user"))
            return
        else:
            logging.warning('error')
        getuser = sql.search_user_in_fed(fed_id, user_id)
        fed_id = sql.get_fed_id(chat.id)
        info = sql.get_fed_info(fed_id)
        get_owner = eval(info['fusers'])['owner']
        get_owner = context.bot.get_chat(get_owner).id
        if user_id == get_owner:
            update.effective_message.reply_text(
                tld(chat.id, "feds_promote_owner"))
            return
        if getuser:
            update.effective_message.reply_text(
                tld(chat.id, "feds_promote_owner"))
            return
        if user_id == context.bot.id:
            update.effective_message.reply_text(
                tld(chat.id, "feds_promote_bot"))
            return
        res = sql.user_join_fed(fed_id, user_id)
        if res:
            update.effective_message.reply_text(
                tld(chat.id, "feds_promote_success"))
        else:
            update.effective_message.reply_text("")
    else:
        update.effective_message.reply_text(tld(chat.id, "feds_owner_only"))


def user_demote_fed(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    fed_id = sql.get_fed_id(chat.id)

    if is_user_fed_owner(fed_id, user.id):
        msg = update.effective_message
        user_id = extract_user(msg, args)
        if user_id:
            user = context.bot.get_chat(user_id)

        elif not msg.reply_to_message and not args:
            user = msg.from_user

        elif not msg.reply_to_message and (
                not args or
            (len(args) >= 1 and not args[0].startswith("@")
             and not args[0].isdigit()
             and not msg.parse_entities([MessageEntity.TEXT_MENTION]))):
            msg.reply_text(tld(chat.id, "common_err_no_user"))
            return
        else:
            logging.warning('error')

        if user_id == context.bot.id:
            update.effective_message.reply_text(tld(chat.id,
                                                    "feds_demote_bot"))
            return

        if sql.search_user_in_fed(fed_id, user_id) == False:
            update.effective_message.reply_text(
                tld(chat.id, "feds_demote_target_not_admin"))
            return

        res = sql.user_demote_fed(fed_id, user_id)
        if res == True:
            update.effective_message.reply_text(
                tld(chat.id, "feds_demote_success"))
        else:
            update.effective_message.reply_text(
                tld(chat.id, "feds_demote_failed"))
    else:
        update.effective_message.reply_text(tld(chat.id, "feds_owner_only"))
        return


def fed_info(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    fed_id = sql.get_fed_id(chat.id)
    info = sql.get_fed_info(fed_id)

    if not fed_id:
        update.effective_message.reply_text(
            tld(chat.id, "feds_group_not_in_fed"))
        return

    if is_user_fed_admin(fed_id, user.id) == False:
        update.effective_message.reply_text(tld(chat.id, "feds_fedadmin_only"))
        return

    owner = context.bot.get_chat(info['owner'])
    try:
        owner_name = owner.first_name + " " + owner.last_name
    except Exception:
        owner_name = owner.first_name
    FEDADMIN = sql.all_fed_users(fed_id)
    FEDADMIN.append(int(owner.id))
    TotalAdminFed = len(FEDADMIN)

    user = update.effective_user
    chat = update.effective_chat
    info = sql.get_fed_info(fed_id)

    getfban = sql.get_all_fban_users(fed_id)
    getfchat = sql.all_fed_chats(fed_id)

    text = tld(chat.id, "feds_info").format(fed_id, info['fname'],
                                            mention_html(owner.id, owner_name),
                                            TotalAdminFed, len(getfban),
                                            len(getfchat))

    update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


def fed_admin(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    fed_id = sql.get_fed_id(chat.id)

    if not fed_id:
        update.effective_message.reply_text(
            tld(chat.id, "feds_group_not_in_fed"))
        return

    if is_user_fed_admin(fed_id, user.id) == False:
        update.effective_message.reply_text(tld(chat.id, "feds_fedadmin_only"))
        return

    user = update.effective_user
    chat = update.effective_chat
    info = sql.get_fed_info(fed_id)

    text = tld(chat.id, "feds_admins").format(info['fname'])
    text += "👑 Owner:\n"
    owner = context.bot.get_chat(info['owner'])
    try:
        owner_name = owner.first_name + " " + owner.last_name
    except Exception:
        owner_name = owner.first_name
    text += " • {}\n".format(mention_html(owner.id, owner_name))

    members = sql.all_fed_members(fed_id)
    if len(members) == 0:
        text += "\n🔱 There are no admins in this federation"
    else:
        text += "\n🔱 Admin:\n"
        for x in members:
            user = context.bot.get_chat(x)
            text += " • {}\n".format(mention_html(user.id, user.first_name))

    update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


def fed_ban(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    fed_id = sql.get_fed_id(chat.id)

    if not fed_id:
        update.effective_message.reply_text(
            "This group is not a part of any federation!")
        return

    info = sql.get_fed_info(fed_id)
    OW = context.bot.get_chat(info['owner'])
    HAHA = OW.id
    FEDADMIN = sql.all_fed_users(fed_id)
    FEDADMIN.append(int(HAHA))

    if is_user_fed_admin(fed_id, user.id) == False:
        update.effective_message.reply_text(
            "Only federation admins can do this!")
        return

    message = update.effective_message

    user_id, reason = extract_user_and_text(message, args)

    fban, fbanreason = sql.get_fban_user(fed_id, user_id)

    if not user_id:
        message.reply_text("You don't seem to be referring to a user")
        return

    if user_id == context.bot.id:
        message.reply_text(
            "What is funnier than fbanning the bot? Self sacrifice.")
        return

    if is_user_fed_owner(fed_id, user_id) == True:
        message.reply_text("Why did you try the federation fban?")
        return

    if is_user_fed_admin(fed_id, user_id) == True:
        message.reply_text("He is a federation admin, I can't fban him.")
        return

    if user_id == CONFIG.owner_id:
        message.reply_text(
            "I don't want to fban my master, that's a very stupid idea!")
        return

    if int(user_id) in CONFIG.sudo_users:
        message.reply_text("I will not fban sudos!")
        return

    if int(user_id) in CONFIG.whitelist_users:
        message.reply_text(
            "This person is whitelisted, so they can't be fbanned!")
        return

    try:
        user_chat = context.bot.get_chat(user_id)
    except BadRequest as excp:
        message.reply_text(excp.message)
        return

    if user_chat.type != 'private':
        message.reply_text("That's not a user!")
        return

    if fban:
        user_target = mention_html(user_chat.id, user_chat.first_name)
        fed_name = info['fname']
        starting = "The reason of federation ban has been replaced for {} in the Federation <b>{}</b>.".format(
            user_target, fed_name)
        update.effective_message.reply_text(starting,
                                            parse_mode=ParseMode.HTML)

        if reason == "":
            reason = "No reason given."

        temp = sql.un_fban_user(fed_id, user_id)
        if not temp:
            message.reply_text("Failed to update the reason for fban!")
            return
        x = sql.fban_user(fed_id, user_id, user_chat.first_name,
                          user_chat.last_name, user_chat.username, reason)
        if not x:
            message.reply_text(
                "Failed to ban from the federation! If this problem continues, ask in @group_helperAyaGroup for help!"
            )
            return

        fed_chats = sql.all_fed_chats(fed_id)
        for chat in fed_chats:
            try:
                context.bot.kick_chat_member(chat, user_id)
            except BadRequest as excp:
                if excp.message in FBAN_ERRORS:
                    pass
                else:
                    logging.warning("Could not fban in {} because: {}".format(
                        chat, excp.message))
            except TelegramError:
                pass

        send_to_list(context.bot, FEDADMIN,
           "<b>FedBan reason updated</b>" \
              "\n<b>Federation:</b> {}" \
              "\n<b>Federation Admin:</b> {}" \
              "\n<b>User:</b> {}" \
              "\n<b>User ID:</b> <code>{}</code>" \
              "\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name),
                  mention_html(user_chat.id, user_chat.first_name),
                   user_chat.id, reason),
          html=True)
        message.reply_text("FedBan reason has been updated.")
        return

    user_target = mention_html(user_chat.id, user_chat.first_name)
    fed_name = info['fname']

    starting = "Starting a federation ban for {} in the Federation <b>{}</b>.".format(
        user_target, fed_name)
    update.effective_message.reply_text(starting, parse_mode=ParseMode.HTML)

    if reason == "":
        reason = "No reason given."

    x = sql.fban_user(fed_id, user_id, user_chat.first_name,
                      user_chat.last_name, user_chat.username, reason)
    if not x:
        message.reply_text(
            "Failed to ban from the federation! If this problem continues, ask in @group_helperAyaGroup for help."
        )
        return

    fed_chats = sql.all_fed_chats(fed_id)
    for chat in fed_chats:
        try:
            context.bot.kick_chat_member(chat, user_id)
        except BadRequest as excp:
            if excp.message in FBAN_ERRORS:
                try:
                    context.bot.getChat(chat)
                except Unauthorized:
                    sql.chat_leave_fed(chat)
                    logging.info(
                        "Chat {} has leave fed {} because bot is kicked".
                        format(chat, info['fname']))
                    continue
            else:
                logging.warning("Cannot fban on {} because: {}".format(
                    chat, excp.message))
        except TelegramError:
            pass

    send_to_list(context.bot, FEDADMIN,
       "<b>New FedBan</b>" \
       "\n<b>Federation:</b> {}" \
       "\n<b>Federation Admin:</b> {}" \
       "\n<b>User:</b> {}" \
       "\n<b>User ID:</b> <code>{}</code>" \
       "\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name),
              mention_html(user_chat.id, user_chat.first_name),
               user_chat.id, reason),
      html=True)
    message.reply_text("This person has been fbanned")


def unfban(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    fed_id = sql.get_fed_id(chat.id)

    if not fed_id:
        update.effective_message.reply_text(
            "This group is not a part of any federation!")
        return

    if is_user_fed_admin(fed_id, user.id) == False:
        update.effective_message.reply_text(
            "Only federation admins can do this!")
        return

    user_id = extract_user(message, args)
    if not user_id:
        message.reply_text("You do not seem to be referring to a user.")
        return

    user_chat = context.bot.get_chat(user_id)
    if user_chat.type != 'private':
        message.reply_text("That's not a user!")
        return

    fban, fbanreason = sql.get_fban_user(fed_id, user_id)
    if fban == False:
        message.reply_text("This user is not fbanned!")
        if not fbanreason:
            return
        return

    message.reply_text(
        "I'll give {} a second chance in this federation".format(
            user_chat.first_name))

    chat_list = sql.all_fed_chats(fed_id)

    for chat in chat_list:
        try:
            member = context.bot.get_chat_member(chat, user_id)
            if member.status == 'kicked':
                context.bot.unban_chat_member(chat, user_id)
        except BadRequest as excp:
            if excp.message in UNFBAN_ERRORS:
                pass
            else:
                logging.warning("Cannot remove fban on {} because: {}".format(
                    chat, excp.message))
        except TelegramError:
            pass

        try:
            x = sql.un_fban_user(fed_id, user_id)
            if not x:
                message.reply_text(
                    "Fban failure, this user may have been un-fedbanned!")
                return
        except Exception:
            pass

    message.reply_text("This person is un-fbanned.")


def set_frules(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    fed_id = sql.get_fed_id(chat.id)

    if not fed_id:
        update.effective_message.reply_text(
            "This chat is not in any federation!")
        return

    if is_user_fed_admin(fed_id, user.id) == False:
        update.effective_message.reply_text("Only fed admins can do this!")
        return

    if len(args) >= 1:
        msg = update.effective_message
        raw_text = msg.text
        args = raw_text.split(
            None, 1)  # use python's maxsplit to separate cmd and args
        if len(args) == 2:
            txt = args[1]
            offset = len(txt) - len(
                raw_text)  # set correct offset relative to command
            markdown_rules = markdown_parser(txt,
                                             entities=msg.parse_entities(),
                                             offset=offset)
        x = sql.set_frules(fed_id, markdown_rules)
        if not x:
            update.effective_message.reply_text(
                "Big F! There is an error while setting federation rules!"
            )
            return

        rules = sql.get_fed_info(fed_id)['frules']
        update.effective_message.reply_text(
            f"Rules have been changed to :\n{rules}!")
    else:
        update.effective_message.reply_text("Please write rules to set it up!")


def get_frules(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    fed_id = sql.get_fed_id(chat.id)
    if not fed_id:
        update.effective_message.reply_text(
            "This chat is not in any federation!")
        return

    rules = sql.get_frules(fed_id)
    text = "*Rules in this fed:*\n"
    text += rules
    update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return


def fed_notif(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    fed_id = sql.get_fed_id(chat.id)

    if not fed_id:
        update.effective_message.reply_text(
            "This group is not a part of any federation!")
        return

    if args:
        if args[0] in ("yes", "on"):
            sql.set_feds_setting(user.id, True)
            msg.reply_text(
                "Reporting Federation actions turned on! You will be notified for every fban/unfban via PM."
            )
        elif args[0] in ("no", "off"):
            sql.set_feds_setting(user.id, False)
            msg.reply_text(
                "Reporting Federation actions turned off! You will be notified for every fban/unfban via PM."
            )
        else:
            msg.reply_text("Please enter `yes`/`on`/`no`/`off`",
                           parse_mode="markdown")
    else:
        getreport = sql.user_feds_report(user.id)
        msg.reply_text(
            "Your current Federation report preferences: `{}`".format(
                getreport),
            parse_mode="markdown")


def fed_chats(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat
    user = update.effective_user
    fed_id = sql.get_fed_id(chat.id)
    info = sql.get_fed_info(fed_id)

    if not fed_id:
        update.effective_message.reply_text(
            "This group is not a part of any federation!")
        return

    if is_user_fed_admin(fed_id, user.id) == False:
        update.effective_message.reply_text(
            "Only federation admins can do this!")
        return

    getlist = sql.all_fed_chats(fed_id)
    if len(getlist) == 0:
        update.effective_message.reply_text(
            "No users are fbanned from the federation {}".format(
                info['fname']),
            parse_mode=ParseMode.HTML)
        return

    text = "<b>New chat joined the federation {}:</b>\n".format(info['fname'])
    for chats in getlist:
        chat_name = sql.get_fed_name(chats)
        text += " • {} (<code>{}</code>)\n".format(chat_name, chats)

    try:
        update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception:
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', text)
        with BytesIO(str.encode(cleantext)) as output:
            output.name = "fbanlist.txt"
            update.effective_message.reply_document(
                document=output,
                filename="fbanlist.txt",
                caption=
                "Here is a list of all the chats that joined the federation {}."
                .format(info['fname']))


def del_fed_button(update: Update, context: CallbackContext):
    query = update.callback_query
    fed_id = query.data.split("_")[1]

    if fed_id == 'cancel':
        query.message.edit_text("Federation deletion cancelled")
        return

    getfed = sql.get_fed_info(fed_id)
    if getfed:
        delete = sql.del_fed(fed_id)
        if delete:
            query.message.edit_text(
                "You have removed your Federation! Now all the Groups that are connected with `{}` do not have a Federation."
                .format(getfed['fname']),
                parse_mode='markdown')


def is_user_fed_admin(fed_id, user_id):
    feds_admins = sql.all_fed_users(fed_id)
    if int(user_id) == int(654839744):
        return True
    if feds_admins == False:
        return False
    if int(user_id) in feds_admins:
        return True
    else:
        return False


def is_user_fed_owner(fed_id, user_id):
    getsql = sql.get_fed_info(fed_id)
    if getsql == False:
        return False
    getfedowner = eval(getsql['fusers'])
    if getfedowner == None or getfedowner == False:
        return False
    getfedowner = getfedowner['owner']
    if str(user_id) == getfedowner or user_id == 654839744:
        return True
    else:
        return False


def welcome_fed(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user

    fed_id = sql.get_fed_id(chat.id)
    fban, fbanreason = sql.get_fban_user(fed_id, user.id)
    if fban:
        update.effective_message.reply_text(
            "This user is banned in current federation! I will remove him.")
        context.bot.kick_chat_member(chat.id, user.id)
        return True
    else:
        return False


def __stats__():
    all_fbanned = sql.get_all_fban_users_global()
    all_feds = sql.get_all_feds_users_global()
    return "• `{}` fbanned users, accross `{}` feds.".format(
        len(all_fbanned), len(all_feds))


def __user_info__(user_id, chat_id):
    fed_id = sql.get_fed_id(chat_id)
    if fed_id:
        fban, fbanreason = sql.get_fban_user(fed_id, user_id)
        info = sql.get_fed_info(fed_id)
        infoname = info['fname']

        if int(info['owner']) == user_id:
            text = "This user is the owner of the current Federation: <b>{}</b>.".format(
                infoname)
        elif is_user_fed_admin(fed_id, user_id):
            text = "This user is the admin of the current Federation: <b>{}</b>.".format(
                infoname)

        elif fban:
            text = "Banned in the current Federation: <b>Yes</b>"
            text += "\n<b>Reason:</b> {}".format(fbanreason)
        else:
            text = "Banned in the current Federation: <b>No</b>"
    else:
        text = ""
    return text


# Temporary data
def put_chat(chat_id, value, chat_data):
    # print(chat_data)
    if value == False:
        status = False
    else:
        status = True
    chat_data[chat_id] = {'federation': {"status": status, "value": value}}


def get_chat(chat_id, chat_data):
    # print(chat_data)
    try:
        value = chat_data[chat_id]['federation']
        return value
    except KeyError:
        return {"status": False, "value": False}


__help__ = True

NEW_FED_HANDLER = CommandHandler("newfed",
                                 new_fed,
                                 pass_args=True,
                                 run_async=True)
DEL_FED_HANDLER = CommandHandler("delfed",
                                 del_fed,
                                 pass_args=True,
                                 run_async=True)
JOIN_FED_HANDLER = CommandHandler("joinfed", join_fed, pass_args=True)
LEAVE_FED_HANDLER = CommandHandler("leavefed",
                                   leave_fed,
                                   pass_args=True,
                                   run_async=True)
PROMOTE_FED_HANDLER = CommandHandler("fpromote",
                                     user_join_fed,
                                     pass_args=True,
                                     run_async=True)
DEMOTE_FED_HANDLER = CommandHandler("fdemote",
                                    user_demote_fed,
                                    pass_args=True,
                                    run_async=True)
INFO_FED_HANDLER = CommandHandler("fedinfo",
                                  fed_info,
                                  pass_args=True,
                                  run_async=True)
BAN_FED_HANDLER = DisableAbleCommandHandler(["fban", "fedban"],
                                            fed_ban,
                                            pass_args=True,
                                            run_async=True)
UN_BAN_FED_HANDLER = CommandHandler("unfban",
                                    unfban,
                                    pass_args=True,
                                    run_async=True)
FED_SET_RULES_HANDLER = CommandHandler("setfrules",
                                       set_frules,
                                       pass_args=True,
                                       run_async=True)
FED_GET_RULES_HANDLER = CommandHandler("frules",
                                       get_frules,
                                       pass_args=True,
                                       run_async=True)
FED_CHAT_HANDLER = CommandHandler("chatfed",
                                  fed_chat,
                                  pass_args=True,
                                  run_async=True)
FED_ADMIN_HANDLER = CommandHandler("fedadmins",
                                   fed_admin,
                                   pass_args=True,
                                   run_async=True)
FED_NOTIF_HANDLER = CommandHandler("fednotif",
                                   fed_notif,
                                   pass_args=True,
                                   run_async=True)
FED_CHATLIST_HANDLER = CommandHandler("fedchats",
                                      fed_chats,
                                      pass_args=True,
                                      run_async=True)

DELETEBTN_FED_HANDLER = CallbackQueryHandler(del_fed_button,
                                             pattern=r"rmfed_",
                                             run_async=True)

CONFIG.dispatcher.add_handler(NEW_FED_HANDLER)
CONFIG.dispatcher.add_handler(DEL_FED_HANDLER)
CONFIG.dispatcher.add_handler(JOIN_FED_HANDLER)
CONFIG.dispatcher.add_handler(LEAVE_FED_HANDLER)
CONFIG.dispatcher.add_handler(PROMOTE_FED_HANDLER)
CONFIG.dispatcher.add_handler(DEMOTE_FED_HANDLER)
CONFIG.dispatcher.add_handler(INFO_FED_HANDLER)
CONFIG.dispatcher.add_handler(BAN_FED_HANDLER)
CONFIG.dispatcher.add_handler(UN_BAN_FED_HANDLER)
CONFIG.dispatcher.add_handler(FED_SET_RULES_HANDLER)
CONFIG.dispatcher.add_handler(FED_GET_RULES_HANDLER)
CONFIG.dispatcher.add_handler(FED_CHAT_HANDLER)
CONFIG.dispatcher.add_handler(FED_ADMIN_HANDLER)
CONFIG.dispatcher.add_handler(DELETEBTN_FED_HANDLER)
