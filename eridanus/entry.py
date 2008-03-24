import urllib
from itertools import islice, groupby

from epsilon.extime import Time

from axiom.item import Item
from axiom.attributes import AND, OR, timestamp, integer, reference, text, boolean
from axiom.upgrade import registerAttributeCopyingUpgrader, registerUpgrader

from eridanus import const
from eridanus.util import encode, decode



def saneURL(url):
    t, rest = urllib.splittype(encode(url))
    if t is None:
        if not rest.startswith('//'):
            rest = '//' + rest
        return u'http:' + decode(rest)

    return url


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
                  url=saneURL(url),
                  title=title)

        if comment is not None:
            e.addComment(nick, comment, initial=True)

        return e

    def allEntries(self, limit=None, recentFirst=True, discarded=False, sort=None):
        if sort is None:
            sort = [Entry.modified.ascending, Entry.modified.descending][recentFirst]

        return self.store.query(Entry,
                                AND(Entry.channel == self.channel,
                                    Entry.discarded == discarded,
                                    Entry.deleted == False),
                                limit=limit,
                                sort=sort)

    def entryBy(self, eid=None, url=None):
        criteria = [
            Entry.channel == self.channel,
            Entry.deleted == False]

        if eid is not None:
            criteria.append(Entry.eid == eid)
        if url is not None:
            criteria.append(Entry.url == url)

        return self.store.findFirst(Entry, AND(*criteria))

    def entryById(self, eid):
        return self.entryBy(eid=eid)

    def entryByUrl(self, url):
        return self.entryBy(url=url)

    def topContributors(self, limit=None):
        query = self.allEntries(sort=Entry.nick.descending)

        totalEntries = query.count()
        runningTotal = 0
        contributors = 0

        # XXX: this doesn't seem optimal
        groups = ((nick, len(list(entries))) for nick, entries in groupby(query, lambda e: e.nick))
        groups = sorted(groups, reverse=True, key=lambda g: g[1])

        for nick, count in islice(groups, limit):
            contributors += 1
            runningTotal += count
            yield nick, count

        # XXX: other seems a bit of a pointless thing
        #if limit is not None and contributors > limit:
        #    yield 'Other', totalEntries - runningTotal

    def search(self, terms, limit=None):
        def makeCriteria():
            for term in terms:
                t = u'%%%s%%' % (term,)
                yield OR(Entry.title.like(t),
                         Entry.url.like(t),
                         AND(Comment.parent == Entry.storeID,
                             Comment.comment.like(t)))

        return self.store.query(Entry,
            AND(Entry.channel == self.channel,
                Entry.discarded == False,
                Entry.deleted == False,
                *makeCriteria()),
            sort=Entry.modified.descending,
            limit=limit).distinct()

    def stats(self):
        store = self.store
        entries = store.query(Entry,
                              Entry.channel == self.channel,
                              sort=Entry.created.ascending)
        numComments = store.query(Comment,
                                  AND(Comment.parent == Entry.storeID,
                                      Entry.channel == self.channel)).count()

        numEntries = entries.count()
        numContributors = len(list(entries.getColumn('nick').distinct()))
        start = iter(entries).next()

        return numEntries, numComments, numContributors, Time() - start.created

def entrymanager1to2(old):
    return old.upgradeVersion(
        EntryManager.typeName, 1, 2,
        config=old.config,
        channel=old.channel.decode('utf-8'),
        lastEid=old.lastEid)

registerUpgrader(entrymanager1to2, EntryManager.typeName, 1, 2)


class Entry(Item):
    typeName = 'eridanus_entry'
    schemaVersion = 7

    eid = integer(allowNone=False)

    created = timestamp(defaultFactory=lambda: Time(), doc=u"""
    Timestamp of when this entry was created.
    """)

    modified = timestamp(defaultFactory=lambda: Time(), doc=u"""
    Timestamp of when this entry was last modified.
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

    discarded = boolean(doc="""
    Indicates whether this item is to be considered for searches and the like.
    """, default=False)

    deleted = boolean(doc="""
    Indicates whether this item is to be considered at all.
    """, default=False)

    def addComment(self, nick, comment, initial=False):
        return self.store.findOrCreate(Comment, parent=self, nick=nick, comment=comment, initial=initial)

    def touchEntry(self):
        self.modified = Time()
        self.occurences += 1

    @property
    def comments(self):
        return list(self.store.query(Comment,
                                     AND(Comment.parent == self,
                                         Comment.initial == False),
                                     sort=Comment.created.ascending))

    @property
    def initialComment(self):
        return self.store.findFirst(Comment,
                                    AND(Comment.parent == self,
                                        Comment.initial == True))

    @property
    def displayComment(self):
        comment = self.initialComment
        if comment is None:
            return u''
        return u' [%s]' % (comment.comment,)

    @property
    def slug(self):
        for slug in reversed(self.url.split('/')):
            if slug:
                return urllib.unquote(slug)

    @property
    def displayTitle(self):
        return self.title or self.slug

    @property
    def displayTimestamp(self):
        return self.created.asHumanly(tzinfo=const.timezone)

    @property
    def completeHumanReadable(self):
        return u'#%d: \037%s\037%s @ %s posted %s by \002%s\002.' % (self.eid, self.displayTitle, self.displayComment, self.url, self.displayTimestamp, self.nick)

    @property
    def humanReadable(self):
        return u'#%d: \037%s\037%s posted %s by \002%s\002.' % (self.eid, self.displayTitle, self.displayComment, self.displayTimestamp, self.nick)

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
registerAttributeCopyingUpgrader(Entry, 4, 5)
registerAttributeCopyingUpgrader(Entry, 5, 6)
registerAttributeCopyingUpgrader(Entry, 6, 7)


class Comment(Item):
    typeName = 'eridanus_comment'
    schemaVersion = 3

    created = timestamp(defaultFactory=lambda: Time(), doc=u"""
    Timestamp of when this comment was created.
    """)

    parent = reference(doc="""
    L{Entry} item this comment refers to.
    """, allowNone=False, reftype=Entry)

    nick = text(doc="""
    The nickname of the person who commented on L{parent}.
    """, allowNone=False)

    comment = text(doc="""
    The comment text that L{nick} made.
    """, allowNone=False)

    initial = boolean(doc="""
    Indicates whether this was the initial comment made when the entry was created.
    """, allowNone=False, default=False)

    @property
    def displayTimestamp(self):
        return self.created.asHumanly(tzinfo=const.timezone)

    @property
    def humanReadable(self):
        return u'#%d: %s -- \002%s\002 (%s)' % (self.parent.eid, self.comment, self.nick, self.displayTimestamp)

registerAttributeCopyingUpgrader(Comment, 1, 2)
registerAttributeCopyingUpgrader(Comment, 2, 3)
