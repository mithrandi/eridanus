from itertools import islice, groupby

from epsilon.extime import Time

from axiom.item import Item
from axiom.attributes import AND, OR, timestamp, integer, reference, text
from axiom.upgrade import registerAttributeCopyingUpgrader, registerUpgrader

from eridanus import const


class Comment(Item):
    typeName = 'eridanus_comment'
    schemaVersion = 2

    created = timestamp(defaultFactory=lambda: Time(), doc=u"""
    Timestamp of when this comment was created.
    """)

    parent = reference(doc="""
    L{Entry} item this comment refers to.
    """, allowNone=False)

    nick = text(doc="""
    The nickname of the person who commented on L{parent}.
    """, allowNone=False)

    comment = text(doc="""
    The comment text that L{nick} made.
    """, allowNone=False)

registerAttributeCopyingUpgrader(Comment, 1, 2)


class Entry(Item):
    typeName = 'eridanus_entry'
    schemaVersion = 4

    eid = integer(allowNone=False)

    created = timestamp(defaultFactory=lambda: Time(), doc=u"""
    Timestamp of when this entry was created.
    """)

    channel = text(allowNone=False, doc=u"""
    The channel where this entry was first submitted.
    """)

    nick = text(allowNone=False, doc=u"""
    The nickname of the person who submitted this entry first.
    """)

    url = text(allowNone=False, doc=u"""
    Entry's URL.
    """)

    title = text(doc=u"""
    Optional title for this entry.
    """)

    occurences = integer(doc="""
    Number of times this entry has been mentioned.
    """, default=1)

    def addComment(self, nick, comment):
        return self.store.findOrCreate(Comment, parent=self, nick=nick, comment=comment)

    @property
    def comments(self):
        return self.store.query(Comment, Comment.parent == self)

    @property
    def creatorComments(self):
        return self.store.query(Comment,
                                AND(Comment.parent == self,
                                    Comment.nick == self.nick))

    @property
    def displayComment(self):
        comments = list(self.creatorComments)
        if not comments:
            return u''
        return u' [%s]' % ('; '.join(c.comment for c in comments),)

    @property
    def slug(self):
        return self.url.split('/')[-1]

    @property
    def displayTitle(self):
        return self.title or self.slug

    @property
    def completeHumanReadable(self):
        return u'#%d: \037%s\037%s @ %s posted %s by \002%s\002.' % (self.eid, self.displayTitle, self.displayComment, self.url, self.created.asHumanly(tzinfo=const.timezone), self.nick)

    @property
    def humanReadable(self):
        return u'#%d: \037%s\037%s posted %s by \002%s\002.' % (self.eid, self.displayTitle, self.displayComment, self.created.asHumanly(tzinfo=const.timezone), self.nick)

registerAttributeCopyingUpgrader(Entry, 1, 2)

def entry2to3(old):
    def decodeOrNone(v):
        if v is None:
            return None
        return v.decode('utf-8')

    return old.upgradeVersion(
        Entry.typeName, 2, 3,
        eid=old.eid,
        created=old.created,
        channel=decodeOrNone(old.channel),
        nick=decodeOrNone(old.nick),
        url=decodeOrNone(old.url),
        comment=decodeOrNone(old.comment),
        title=decodeOrNone(old.title))

registerUpgrader(entry2to3, Entry.typeName, 2, 3)

def entry3to4(old):
    comment = old.comment
    if comment is not None:
        comment = Comment(store=old.store,
                          parent=old,
                          nick=old.nick,
                          comment=comment)

    return old.upgradeVersion(
        Entry.typeName, 3, 4,
        eid=old.eid,
        created=old.created,
        channel=old.channel,
        nick=old.nick,
        url=old.url,
        title=old.title)

registerUpgrader(entry3to4, Entry.typeName, 3, 4)


class EntryManager(Item):
    typeName = 'eridanus_entrymanager'
    schemaVersion = 2

    config = reference()
    channel = text(allowNone=False)
    lastEid = integer(allowNone=False, default=0)

    def createEntry(self, channel, nick, url, comment=None, title=None):
        eid = self.lastEid
        self.lastEid += 1
        e = Entry(store=self.store,
                  eid=eid,
                  channel=channel,
                  nick=nick,
                  url=url,
                  title=title)
        if comment is not None:
            e.addComment(nick, comment)
        return e

    def entryById(self, eid):
        return self.store.findFirst(Entry,
                                    AND(Entry.channel == self.channel,
                                        Entry.eid == eid))

    def entryByUrl(self, url):
        return self.store.findFirst(Entry,
                                    AND(Entry.channel == self.channel,
                                        Entry.url == url))

    def topContributors(self, limit=None):
        query = self.store.query(Entry,
                                 Entry.channel == self.channel,
                                 sort=Entry.nick.descending)

        totalEntries = query.count()
        runningTotal = 0
        contributors = 0

        for nick, entries in islice(groupby(query, lambda e: e.nick), limit):
            count = len(list(entries))
            contributors += 1
            runningTotal += count
            yield nick, count

        if limit is not None and contributors > limit:
            yield 'Other', totalEntries - runningTotal

    def search(self, text, limit=None):
        searchTerm = '%%%s%%' % (text,)
        store = self.store

        return store.query(Entry,
            AND(Entry.channel == self.channel,
                OR(Entry.title.like(searchTerm),
                   Entry.url.like(searchTerm),
                   AND(Entry.storeID == Comment.parent,
                       Comment.comment.like(searchTerm)))),
            sort=Entry.occurences.descending,
            limit=limit).distinct()

def entrymanager1to2(old):
    return old.upgradeVersion(
        EntryManager.typeName, 1, 2,
        config=old.config,
        channel=old.channel.decode('utf-8'),
        lastEid=old.lastEid)

registerUpgrader(entrymanager1to2, EntryManager.typeName, 1, 2)
