import logging
import sys
import yaml
from pydantic import BaseModel, ValidationError
from typing import Optional, List, Set, Any
import os
from dotenv import dotenv_values

from telethon import TelegramClient
import telegram.ext as tg


class GroupHelperConfig(BaseModel):
    """
    group_helper configuration class
    """
    api_id: int
    api_hash: str
    bot_token: str
    database_url: str
    load: List[str]
    no_load: List[str]
    del_cmds: Optional[bool] = False
    strict_antispam: Optional[bool] = False
    workers: Optional[int] = 4
    owner_id: int
    sudo_users: Set[int]
    whitelist_users: Set[int]
    message_dump: Optional[int] = 0
    spamwatch_api: Optional[str] = ""
    spamwatch_client: Optional[Any] = None
    telethon_client: Optional[Any] = None
    updater: Optional[Any] = None
    dispatcher: Optional[Any] = None


logging.basicConfig(
    format=
    "[%(levelname)s %(asctime)s] Module '%(module)s', function '%(funcName)s' at line %(lineno)d -> %(message)s",
    level=logging.INFO)
logging.info("Starting group_helper...")

if sys.version_info < (3, 8, 0):
    logging.error(
        "Your Python version is too old for group_helper to run, please update to Python 3.8 or above"
    )
    exit(1)

try:
    config_file = dict(dotenv_values("config.env"))
    config_file['load'] = config_file['load'].split()
    config_file['no_load'] = config_file['no_load'].split()
    config_file['sudo_users'] = config_file['sudo_users'].split()
    config_file['whitelist_users'] = config_file['whitelist_users'].split()
except Exception as error:
    logging.error(
        f"Could not load config file due to a {type(error).__name__}: {error}")
    exit(1)

try:
    CONFIG = GroupHelperConfig(**config_file)
except ValidationError as validation_error:
    logging.error(
        f"Something went wrong when parsing config.yml: {validation_error}")
    exit(1)

CONFIG.sudo_users.add(CONFIG.owner_id)

try:
    CONFIG.updater = tg.Updater(CONFIG.bot_token, workers=CONFIG.workers)
    CONFIG.dispatcher = CONFIG.updater.dispatcher
    CONFIG.telethon_client = TelegramClient("group_helper", CONFIG.api_id,
                                            CONFIG.api_hash)

    # We import it now to ensure that all previous variables have been set
    from group_helper.modules.helper_funcs.handlers import CustomCommandHandler, CustomMessageHandler
    tg.CommandHandler = CustomCommandHandler
    tg.MessageHandler = CustomMessageHandler
except Exception as telegram_error:
    logging.error(
        f"Could not initialize Telegram client due to a {type(telegram_error).__name__}: {telegram_error}"
    )
    exit(1)
