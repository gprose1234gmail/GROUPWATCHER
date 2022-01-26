import threading

from sqlalchemy import Column, UnicodeText, BigInteger, String, Boolean

from group_helper.modules.sql import BASE, SESSION


class GloballyBannedUsers(BASE):
    __tablename__ = "gbans"
    user_id = Column(BigInteger, primary_key=True)
    name = Column(UnicodeText, nullable=False)
    reason = Column(UnicodeText)

    def __init__(self, user_id, name, reason=None):
        self.user_id = user_id
        self.name = name
        self.reason = reason

    def __repr__(self):
        return "<GBanned User {} ({})>".format(self.name, self.user_id)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "name": self.name,
            "reason": self.reason
        }


class AntispamSettings(BASE):
    __tablename__ = "antispam_settings"
    chat_id = Column(String(14), primary_key=True)
    setting = Column(Boolean, default=True, nullable=False)

    def __init__(self, chat_id, enabled):
        self.chat_id = str(chat_id)
        self.setting = enabled

    def __repr__(self):
        return "<Gban setting {} ({})>".format(self.chat_id, self.setting)


AntispamSettings.__table__.create(checkfirst=True)

GBANSTAT_LIST = set()
ASPAM_SETTING_LOCK = threading.RLock()
ANTISPAMSETTING = set()


def enable_antispam(chat_id):
    with ASPAM_SETTING_LOCK:
        chat = SESSION.query(AntispamSettings).get(str(chat_id))
        if not chat:
            chat = AntispamSettings(chat_id, True)

        chat.setting = True
        SESSION.add(chat)
        SESSION.commit()
        if str(chat_id) in GBANSTAT_LIST:
            GBANSTAT_LIST.remove(str(chat_id))


def disable_antispam(chat_id):
    with ASPAM_SETTING_LOCK:
        chat = SESSION.query(AntispamSettings).get(str(chat_id))
        if not chat:
            chat = AntispamSettings(chat_id, False)

        chat.setting = False
        SESSION.add(chat)
        SESSION.commit()
        GBANSTAT_LIST.add(str(chat_id))


def does_chat_gban(chat_id):
    return str(chat_id) not in GBANSTAT_LIST


def __load_gban_stat_list():
    global GBANSTAT_LIST
    try:
        GBANSTAT_LIST = {
            x.chat_id
            for x in SESSION.query(AntispamSettings).all() if not x.setting
        }
    finally:
        SESSION.close()


def migrate_chat(old_chat_id, new_chat_id):
    with ASPAM_SETTING_LOCK:
        gban = SESSION.query(AntispamSettings).get(str(old_chat_id))
        if gban:
            gban.chat_id = new_chat_id
            SESSION.add(gban)

        SESSION.commit()


# Create in memory userid to avoid disk access
__load_gban_stat_list()
