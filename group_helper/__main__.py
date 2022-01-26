import datetime
from sys import argv
import importlib
import re
from os.path import dirname, basename, isfile
import glob
import logging

from telegram import Update
from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import BadRequest, NetworkError, TelegramError
from telegram.ext import CommandHandler, Filters, MessageHandler, CallbackQueryHandler
from telegram.ext.dispatcher import DispatcherHandlerStop, Dispatcher
from telegram.ext.callbackcontext import CallbackContext
from telegram.utils.helpers import DEFAULT_FALSE

# Needed to dynamically load modules
# NOTE: Module order is not guaranteed, specify that in the config file!
from group_helper import CONFIG
from group_helper.modules import ALL_MODULES
from group_helper.modules.helper_funcs.misc import paginate_modules
from group_helper.modules.tr_engine.strings import tld

IMPORTED = {}
MIGRATEABLE = []
HELPABLE = {}
STATS = []
USER_INFO = []
DATA_IMPORT = []
DATA_EXPORT = []
GDPR = []

importlib.import_module("group_helper.modules.tr_engine.language")

for module_name in ALL_MODULES:
    imported_module = importlib.import_module("group_helper.modules." + module_name)
    modname = imported_module.__name__.split('.')[2]

    if not modname.lower() in IMPORTED:
        IMPORTED[modname.lower()] = imported_module
    else:
        raise Exception(
            "Can't have two modules with the same name! Please change one")

    if hasattr(imported_module, "__help__") and imported_module.__help__:
        HELPABLE[modname.lower()] = tld(0, "modname_" + modname).strip()

    # Chats to migrate on chat_migrated events
    if hasattr(imported_module, "__migrate__"):
        MIGRATEABLE.append(imported_module)

    if hasattr(imported_module, "__stats__"):
        STATS.append(imported_module)

    if hasattr(imported_module, "__gdpr__"):
        GDPR.append(imported_module)

    if hasattr(imported_module, "__user_info__"):
        USER_INFO.append(imported_module)


# Do NOT async this!
def send_help(chat_id, text, keyboard=None):
    """
    Sends the help message
    """

    if not keyboard:
        keyboard = InlineKeyboardMarkup(
            paginate_modules(chat_id, 0, HELPABLE, "help"))

    CONFIG.dispatcher.bot.send_message(chat_id=chat_id,
                                       text=text,
                                       parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=keyboard,
                                       disable_web_page_preview=True)


def start(update: Update, context: CallbackContext):
    """
    Handles /start
    """

    args = context.args
    chat = update.effective_chat
    if update.effective_chat.type == "private":
        if len(args) >= 1:
            if args[0].lower() == "help":
                send_help(
                    update.effective_chat.id,
                    tld(chat.id,
                        "send-help").format(context.bot.first_name,
                                            tld(chat.id, "cmd_multitrigger")))

            elif args[0][1:].isdigit() and "rules" in IMPORTED:
                IMPORTED["rules"].send_rules(update, args[0], from_pm=True)

        else:
            send_start(update, context)
    else:
        try:
            update.effective_message.reply_text(
                tld(chat.id, 'main_start_group'))
        except Exception as error:
            logging.error(
                f"An exception occurred, {type(error).__name__}: {error}")


def send_start(update: Update, context: CallbackContext):
    """
    Sends a properly formatted and translated
    start message to a given user
    """

    chat = update.effective_chat
    query = update.callback_query
    text = tld(chat.id, 'main_start_pm').format(context.bot.first_name)
    keyboard = [[
        InlineKeyboardButton(text=tld(chat.id, 'main_start_btn_lang'),
                             callback_data="set_lang_"),
        InlineKeyboardButton(text=tld(chat.id, 'btn_help'),
                             callback_data="help_back")
    ]]

    try:
        if query:
            context.bot.edit_message_text(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True)
        else:
            update.effective_message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True)
    except (TelegramError, NetworkError, AttributeError) as error:
        logging.error(
            f"An exception occurred, {type(error).__name__}: {error}")


def help_button(update: Update, context: CallbackContext):
    """
    Answers callback queries for the help button
    """

    query = update.callback_query
    chat = update.effective_chat
    back_match = re.match(r"help_back", query.data)
    mod_match = re.match(r"help_module\((.+?)\)", query.data)
    try:
        if mod_match:
            module = mod_match.group(1)
            mod_name = tld(chat.id, "modname_" + module).strip()
            help_txt = tld(
                chat.id, module +
                "_help")  # tld_help(chat.id, HELPABLE[module].__mod_name__)
            if not help_txt:
                logging.warning(f"Help string for {module} not found!")
            text = tld(chat.id, "here_is_help").format(mod_name, help_txt)
            context.bot.edit_message_text(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(text=tld(chat.id, "btn_go_back"),
                                         callback_data="help_back")
                ]]),
                disable_web_page_preview=True)

        elif back_match:
            context.bot.edit_message_text(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                text=tld(chat.id,
                         "send-help").format(context.bot.first_name,
                                             tld(chat.id, "cmd_multitrigger")),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(chat.id, 0, HELPABLE, "help")),
                disable_web_page_preview=True)

        context.bot.answer_callback_query(query.id)
    except BadRequest:
        pass


def get_help(update: Update, context: CallbackContext):
    # TODO -> Docstring
    chat = update.effective_chat
    args = update.effective_message.text.split(None, 1)
    if chat.type != chat.PRIVATE:
        update.effective_message.reply_text(
            tld(chat.id, 'help_pm_only'),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(text=tld(chat.id, 'btn_help'),
                                     url="t.me/{}?start=help".format(
                                         context.bot.username))
            ]]))
        return
    if len(args) >= 2:
        mod_name = None
        for module in HELPABLE:
            if args[1].lower() == HELPABLE[module].lower():
                mod_name = tld(chat.id, "modname_" + module).strip()
                break

        else:
            module = ""
        if module:
            help_txt = tld(chat.id, module + "_help")

            if not help_txt:
                logging.warning(f"Help string for {module} not found!")

            text = tld(chat.id, "here_is_help").format(mod_name, help_txt)
            send_help(
                chat.id, text,
                InlineKeyboardMarkup([[
                    InlineKeyboardButton(text=tld(chat.id, "btn_go_back"),
                                         callback_data="help_back")
                ]]))

            return

        update.effective_message.reply_text(tld(
            chat.id, "help_not_found").format(args[1]),
                                            parse_mode=ParseMode.HTML)
        return

    send_help(
        chat.id,
        tld(chat.id, "send-help").format(context.bot.first_name,
                                         tld(chat.id, "cmd_multitrigger")))


def migrate_chats(update: Update, context: CallbackContext):
    # TODO -> Docstring
    msg = update.effective_message
    if msg.migrate_to_chat_id:
        old_chat = update.effective_chat.id
        new_chat = msg.migrate_to_chat_id
    elif msg.migrate_from_chat_id:
        old_chat = msg.migrate_from_chat_id
        new_chat = update.effective_chat.id
    else:
        return
    for mod in MIGRATEABLE:
        mod.__dict__["__migrate__"](old_chat, new_chat)
    raise DispatcherHandlerStop


def main():
    """
    Starts group_helper
    """

    start_handler = CommandHandler("start",
                                   start,
                                   pass_args=True,
                                   run_async=True)
    help_handler = CommandHandler("help", get_help, run_async=True)
    help_callback_handler = CallbackQueryHandler(help_button,
                                                 pattern=r"help_",
                                                 run_async=True)
    start_callback_handler = CallbackQueryHandler(send_start,
                                                  pattern=r"bot_start")
    migrate_handler = MessageHandler(Filters.status_update.migrate,
                                     migrate_chats)

    CONFIG.dispatcher.add_handler(start_handler)
    CONFIG.dispatcher.add_handler(start_callback_handler)
    CONFIG.dispatcher.add_handler(help_handler)
    CONFIG.dispatcher.add_handler(help_callback_handler)
    CONFIG.dispatcher.add_handler(migrate_handler)

    # Add an antiflood processor
    Dispatcher.process_update = process_update

    logging.info("Using long polling.")
    CONFIG.updater.start_polling(timeout=2000,
                                 read_latency=4,
                                 drop_pending_updates=True)

    logging.info("Successfully loaded")
    if len(argv) not in (1, 3, 4):
        CONFIG.telethon_client.disconnect()
    else:
        CONFIG.telethon_client.run_until_disconnected()
    CONFIG.updater.idle()


CHATS_CNT = {}
CHATS_TIME = {}


def process_update(self, update):
    # An error happened while polling
    if isinstance(update, TelegramError):
        try:
            self.dispatch_error(None, update)
        except Exception as dispatch_error:
            self.logger.exception(
                f'An uncaught error was raised while handling the error -> {type(dispatch_error).__name__}: {dispatch_error}'
            )
        return

    if update.effective_chat:  # Checks if update contains chat object
        now = datetime.datetime.utcnow()
    try:
        if update.effective_chat:
            cnt = CHATS_CNT.get(update.effective_chat.id, 0)
        else:
            return
    except AttributeError:
        self.logger.exception(
            'An uncaught error was raised while updating process')
        return

    t = CHATS_TIME.get(update.effective_chat.id, datetime.datetime(1970, 1, 1))
    if t and now > t + datetime.timedelta(0, 1):
        CHATS_TIME[update.effective_chat.id] = now
        cnt = 0
    else:
        cnt += 1

    if cnt > 10:
        return

    CHATS_CNT[update.effective_chat.id] = cnt

    context = None
    handled = False
    sync_modes = []

    for group in self.groups:
        try:
            for handler in self.handlers[group]:
                check = handler.check_update(update)
                if check is not None and check is not False:
                    if not context and self.use_context:
                        context = CallbackContext.from_update(update, self)
                    handled = True
                    sync_modes.append(handler.run_async)
                    handler.handle_update(update, self, check, context)
                    break

        # Stop processing with any other handler.
        except DispatcherHandlerStop:
            self.logger.debug(
                'Stopping further handlers due to DispatcherHandlerStop')
            self.update_persistence(update=update)
            break

        # Dispatch any error.
        except Exception as exc:
            try:
                self.dispatch_error(update, exc)
            except DispatcherHandlerStop:
                self.logger.debug('Error handler stopped further handlers')
                break
            # Errors should not stop the thread.
            except Exception:
                self.logger.exception(
                    'An uncaught error was raised while handling the error.')

    # Update persistence, if handled
    handled_only_async = all(sync_modes)
    if handled:
        # Respect default settings
        if all(mode is DEFAULT_FALSE
               for mode in sync_modes) and self.bot.defaults:
            handled_only_async = self.bot.defaults.run_async
        # If update was only handled by async handlers, we don't need to update here
        if not handled_only_async:
            self.update_persistence(update=update)


def __list_all_modules():
    """
    Loads modules in the order set
    by the config file, making sure
    to exclude modules that have
    been set not to be loaded
    """

    # This generates a list of modules in this folder for the * in __main__ to work.
    paths = glob.glob(dirname(__file__) + "/modules/*.py")
    all_modules = [
        basename(f)[:-3] for f in paths if isfile(f) and f.endswith(".py")
        and not f.endswith('__init__.py') and not f.endswith('__main__.py')
    ]

    if CONFIG.load or CONFIG.no_load:
        to_load = CONFIG.load
        if to_load:
            if not all(
                    any(mod == module_name for module_name in all_modules)
                    for mod in to_load):
                logging.error("Invalid load order names. Quitting.")
                quit(1)
        else:
            to_load = all_modules

        if CONFIG.no_load:
            logging.info(f"Not loading: {CONFIG.no_load}")
            return list(
                filter(lambda m: m not in CONFIG.no_load,
                       [item for item in to_load]))

        return to_load

    return all_modules


if __name__ == "__main__":
    # TODO -> Make a proper startup function for this
    logging.info("Successfully loaded modules: " + str(ALL_MODULES))
    CONFIG.telethon_client.start(bot_token=CONFIG.bot_token)
    main()
