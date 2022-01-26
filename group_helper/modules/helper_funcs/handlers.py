import telegram.ext as tg
from telegram import Update
import group_helper.modules.sql.antispam_sql as sql

CMD_STARTERS = ('/', '!')


class CustomCommandHandler(tg.CommandHandler):
    def __init__(self, command, callback, run_async=False, **kwargs):
        if "admin_ok" in kwargs:
            del kwargs["admin_ok"]
        kwargs["filters"] = kwargs.get(
            "filters",
            tg.Filters.update.message) & ~tg.Filters.update.edited_message
        super().__init__(command, callback, run_async=run_async, **kwargs)

    def check_update(self, update):
        if isinstance(update, Update) and update.effective_message:
            message = update.effective_message

            if message.text and len(message.text) > 1:
                fst_word = message.text_html.split(None, 1)[0]
                if len(fst_word) > 1 and any(
                        fst_word.startswith(start) for start in CMD_STARTERS):
                    args = message.text.split()[1:]
                    command = fst_word[1:].split('@')
                    command.append(
                        message.bot.username
                    )  # in case the command was sent without a username

                    if not (command[0].lower() in self.command
                            and command[1].lower()
                            == message.bot.username.lower()):
                        return None

                    filter_result = self.filters(update)
                    if filter_result:
                        return args, filter_result
                    return False

        return False


class CustomMessageHandler(tg.MessageHandler):
    def __init__(self, filters, callback, run_async=False, **kwargs):
        filters = (filters
                   or tg.Filters.update) & ~tg.Filters.update.edited_message
        super().__init__(filters, callback, run_async=run_async, **kwargs)


class GbanLockHandler(tg.CommandHandler):
    def __init__(self, command, callback, **kwargs):
        super().__init__(command, callback, **kwargs)

    def check_update(self, update):
        if isinstance(update, Update) and update.effective_message:
            message = update.effective_message
            if sql.is_user_gbanned(update.effective_user.id):
                return False
            if message.text and message.text.startswith('/') and len(
                    message.text) > 1:
                first_word = message.text_html.split(None, 1)[0]
                if len(first_word) > 1 and first_word.startswith('/'):
                    command = first_word[1:].split('@')
                    command.append(
                        message.bot.username
                    )  # in case the command was sent without a username
                    if not (command[0].lower() in self.command
                            and command[1].lower()
                            == message.bot.username.lower()):
                        return False
                    if self.filters is None:
                        res = True
                    elif isinstance(self.filters, list):
                        res = any(func(message) for func in self.filters)
                    else:
                        res = self.filters(message)
                    return res
            return False
