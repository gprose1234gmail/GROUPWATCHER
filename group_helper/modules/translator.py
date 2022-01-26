
from typing import Optional

from telegram import Message, Update, ParseMode, Chat
from telegram.ext.callbackcontext import CallbackContext

from group_helper import CONFIG
from group_helper.modules.disable import DisableAbleCommandHandler
from group_helper.modules.helper_funcs.string_handling import remove_emoji
from group_helper.modules.tr_engine.strings import tld

from googletrans import LANGUAGES, Translator


def do_translate(update: Update, context: CallbackContext):
    args = context.args
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    if msg.reply_to_message:
        to_translate_text = remove_emoji(msg.reply_to_message.text)
    else:
        msg.reply_text(tld(chat.id, "translator_no_str"))
        return

    if not args:
        msg.reply_text(tld(chat.id, 'translator_no_args'))
        return
    lang = args[0]

    translator = Translator()
    try:
        translated = translator.translate(to_translate_text, dest=lang)
    except ValueError as e:
        msg.reply_text(tld(chat.id, 'translator_err').format(e))
        return

    src_lang = LANGUAGES[f'{translated.src.lower()}'].title()
    dest_lang = LANGUAGES[f'{translated.dest.lower()}'].title()
    translated_text = translated.text
    msg.reply_text(tld(chat.id,
                       'translator_translated').format(src_lang,
                                                       to_translate_text,
                                                       dest_lang,
                                                       translated_text),
                   parse_mode=ParseMode.MARKDOWN)


__help__ = True

CONFIG.dispatcher.add_handler(
    DisableAbleCommandHandler("tr",
                              do_translate,
                              pass_args=True,
                              run_async=True))
