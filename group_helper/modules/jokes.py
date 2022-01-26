
import random

from telegram import Update, ParseMode
from telegram.ext import run_async
from telegram.ext.callbackcontext import CallbackContext

from group_helper.modules.disable import DisableAbleCommandHandler
from telegram.utils.helpers import escape_markdown
from group_helper.modules.helper_funcs.extraction import extract_user
from group_helper.modules.tr_engine.strings import tld, tld_list

from group_helper import CONFIG


@run_async
def runs(update: Update, context: CallbackContext):
    chat = update.effective_chat
    update.effective_message.reply_text(
        random.choice(tld_list(chat.id, "jokes_runs_list")))


@run_async
def slap(update: Update, context: CallbackContext):
    args = context.args

    chat = update.effective_chat
    msg = update.effective_message

    # reply to correct message
    reply_text = msg.reply_to_message.reply_text if msg.reply_to_message else msg.reply_text

    # get user who sent message
    if msg.from_user.username:
        curr_user = "@" + escape_markdown(msg.from_user.username)
    else:
        curr_user = "[{}](tg://user?id={})".format(msg.from_user.first_name,
                                                   msg.from_user.id)

    user_id = extract_user(update.effective_message, args)
    if user_id:
        slapped_user = context.bot.get_chat(user_id)
        user1 = curr_user
        if slapped_user.username == "squirrelCs":
            reply_text(tld(chat.id, "jokes_not_doing_that"))
            return
        if slapped_user.username:
            user2 = "@" + escape_markdown(slapped_user.username)
        else:
            user2 = "[{}](tg://user?id={})".format(slapped_user.first_name,
                                                   slapped_user.id)

    # if no target found, bot targets the sender
    else:
        user1 = "[{}](tg://user?id={})".format(context.bot.first_name,
                                               context.bot.id)
        user2 = curr_user

    temp = random.choice(tld_list(chat.id, "jokes_slaps_templates_list"))
    item = random.choice(tld_list(chat.id, "jokes_items_list"))
    hit = random.choice(tld_list(chat.id, "jokes_hit_list"))
    throw = random.choice(tld_list(chat.id, "jokes_throw_list"))
    itemp = random.choice(tld_list(chat.id, "jokes_items_list"))
    itemr = random.choice(tld_list(chat.id, "jokes_items_list"))

    repl = temp.format(user1=user1,
                       user2=user2,
                       item=item,
                       hits=hit,
                       throws=throw,
                       itemp=itemp,
                       itemr=itemr)

    reply_text(repl, parse_mode=ParseMode.MARKDOWN)


__help__ = True

RUNS_HANDLER = DisableAbleCommandHandler("runs", runs, admin_ok=True)
SLAP_HANDLER = DisableAbleCommandHandler("slap",
                                         slap,
                                         pass_args=True,
                                         admin_ok=True)

CONFIG.dispatcher.add_handler(RUNS_HANDLER)
CONFIG.dispatcher.add_handler(SLAP_HANDLER)
