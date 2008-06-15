from epsilon.extime import Time

from axiom.item import Item
from axiom.attributes import text, timestamp, inmemory

from eridanus import const


# XXX: remove this piece of junk
class UserConfig(Item):
    typeName = 'eridanus_userconfig'
    schemaVersion = 1

    user = inmemory(doc="""
    An L{IRCUser} instance.
    """)

    created = timestamp(defaultFactory=lambda: Time(), doc=u"""
    Timestamp of when this comment was created.
    """)

    nickname = text(doc="""
    Nickname this configuration is bound to.
    """, allowNone=False)

    channel = text(doc="""
    Channel this configuration is bound to.
    """, allowNone=False)

    @property
    def displayCreated(self):
        return self.created.asHumanly(tzinfo=const.timezone)


