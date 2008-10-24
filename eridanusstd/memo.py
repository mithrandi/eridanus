from epsilon.extime import Time

from axiom.attributes import AND, text, timestamp
from axiom.item import Item

from eridanus.util import humanReadableTimeDelta


class Memo(Item):
    typeName = 'eridanus_plugins_memo_memo'
    schemaVersion = 1

    created = timestamp(doc="""
    Creation time of this Factoid.
    """, defaultFactory=lambda: Time())

    channel = text(doc="""
    The channel where the memo should be recited.
    """, allowNone=False)

    sender = text(doc="""
    The nickname of the person who sent the memo.
    """, allowNone=False)

    recipient = text(doc="""
    The nicknames of the person to whom the memo is addressed.
    """, allowNone=False)

    message = text(doc="""
    The message to leave.
    """, allowNone=False)

    @property
    def displayAgo(self):
        delta = Time() - self.created
        return humanReadableTimeDelta(delta)

    @property
    def displayMessage(self):
        return u'Memo from \002%s\002 %s ago: %s (created %s)' % (
            self.sender,
            self.displayAgo,
            self.message,
            self.created.asHumanly())


class MemoManager(object):
    def __init__(self, store):
        self.store = store

    def leaveMemo(self, channel, sender, recipient, message):
        return Memo(store=self.store,
                    channel=channel,
                    sender=sender,
                    recipient=recipient,
                    message=message)

    def getMemosFor(self, channel, recipient):
        return self.store.query(Memo,
                                AND(Memo.recipient == recipient,
                                    Memo.channel == channel),
                                sort=Memo.created.ascending)
