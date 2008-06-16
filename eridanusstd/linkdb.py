import datetime, itertools, urllib, re, chardet, gzip, html5lib
from StringIO import StringIO
from PIL import Image

from epsilon.extime import Time

from twisted.internet.defer import succeed
from twisted.python import log

from axiom.item import Item
from axiom.attributes import (AND, OR, timestamp, integer, reference, text,
    boolean, bytes)

from eridanus import const, util
from eridanusstd import errors, iriparse, etree


def parseEntryID(eid):
    """
    Parse an entry ID into its parts.

    Entry IDs are of the form::

        [#]id[.[#]channel]

        Where C{#} and C{.} are literal. 

    @type eid: C{unicode}
    @param eid: Entry ID to parse

    @raise errors.InvalidEntry: If the C{id} part is not a valid number

    @rtype: C{(id, channel)}
    @return: The entry ID and channel, the channel may be C{None} if it was not
        specified
    """
    if eid.startswith(u'#'):
        eid = eid[1:]

    parts = eid.split(u'.')

    id = parts.pop(0)
    try:
        id = int(id)
    except ValueError:
        raise errors.InvalidEntry(u'Invalid entry ID: %s' % (id,))

    if parts:
        channel = parts.pop(0)
        # XXX: maybe support channels that don't start with # some day?
        if not channel.startswith(u'#'):
            channel = u'#' + channel
    else:
        channel = None

    return id, channel


def getAllLinkManagers(store, serviceID):
    """
    Get all managers for a given service.
    """
    return store.query(LinkManager, LinkManager.serviceID == serviceID)


_managerCache = {}

def getLinkManager(store, serviceID, channel):
    """
    Retrieve the manager item responsible for C{channel}

    If no manager exists for the given channel, a new one is created.

    @type store: C{axiom.store.Store}
    @param store: The store to find/create entry managers in, it is recommended
        that this be the app store

    @type serviceID: C{unicode}
    @param serviceID: The service under which the manager operates

    @type channel: C{unicode}
    @param channel: The channel to find the manager responsible for

    @rtype: C{LinkManager}
    """
    assert channel.startswith(u'#')
    global _managerCache
    em = _managerCache.get(channel)
    if em is None:
        em = store.findOrCreate(LinkManager,
                                serviceID=serviceID,
                                channel=channel)
        _managerCache[channel] = em

    return em


def getEntryByID(store, serviceID, entryID, defaultChannel):
    """
    Get the L{LinkEntry} item for C{entryID}.

    @type store: C{axiom.store.Store}
    @param store: The store to find/create entry managers in, it is recommended
        that this be the app store

    @type serviceID: C{unicode}
    @param serviceID: The service under which entry's manager operates

    @type entryID: C{unicode}

    @type defaultChannel: C{unicode}
    @param defaultChannel: If C{entryID} does not specify a channel, the
        channel name falls back to the this parameter

    @raise errors.InvalidEntry: If there is a problem with C{entryID}

    @return: The entry represented by C{entryID}
    @rtype: L{LinkEntry}
    """
    id, channel = parseEntryID(entryID)

    if channel is None:
        channel = defaultChannel

    lm = getLinkManager(store, serviceID, channel)
    entry = lm.entryByID(id)
    if entry is None:
        raise errors.InvalidEntry(u'Entry %s does not exist' % (entryID,))

    return entry


_commentPattern = re.compile(ur'\s+(?:\[(.*?)\]|<?--\s+(.*))')

def extractURLs(text):
    """
    Extract URLs and comments from C{text}

    @type text: C{unicode}

    @rtype: C{iterable} of C{(nevow.url.URL, unicode)}
    @return: An iterable of C{(url, comment)} pairs
    """
    for url, pos in iriparse.extractURLsWithPosition(text):
        comment = _commentPattern.match(text, pos)
        if comment is not None:
            comment = filter(None, comment.groups())[0]

        yield url, comment


def _decodeText(data, encoding):
    """
    Decode C{data} as text encoded as C{encoding}.

    @type data: C{str}

    @type encoding: C{str}

    @rtype: C{unicode}
    """
    def detectEncoding(data):
        info = chardet.detect(data)
        return info.get('encoding') or 'ascii'

    if encoding is None:
        encoding = detectEncoding(data)

    try:
        return data.decode(encoding, 'replace')
    except LookupError:
        newEncoding = detectEncoding(data)
        log.msg('Decoding text with %r failed, detected data as %r.' % (encoding, newEncoding))
        return data.decode(newEncoding, 'replace')


def _decodeData(data, contentType, contentEncoding):
    """
    Decode C{data} handling content encoding and content type.

    @type data: C{str}

    @type contentType: C{str}
    @param contentType: C{data} is decoded using any C{charset} directive found
        in the content type

    @type contentEncoding: C{str}
    @param contentEncoding: Content encoding to decode to obtain the intended
        data, only gzip is currently supported

    @raise ValueError: If C{contentEncoding} is not C{None} and not gzip

    @rtype: C{unicode}
    """
    # XXX: this should be done at a lower level, like util.getPage maybe
    if contentEncoding is not None:
        if contentEncoding in ('x-gzip', 'gzip'):
            data = gzip.GzipFile(fileobj=StringIO(data)).read()
        else:
            raise ValueError(u'Unsupported content encoding: %r' % (contentEncoding,))

    params = dict(p.lower().strip().split(u'=', 1) for p in contentType.split(u';')[1:] if u'=' in p)
    return _decodeText(data, params.get('charset'))


def _buildMetadata(data, headers):
    """
    Create entry metadata from C{data} and C{headers}.

    @rtype: C{iterable} of C{(unicode, unicode)}
    @return: Iterable of C{(key, value)} pairs
    """
    def getHeader(name):
        h = headers.get(name)
        if h is not None:
            return unicode(h[0], 'ascii')
        return None

    contentType = getHeader('content-type')
    if contentType is not None:
        yield u'contentType', contentType

        if contentType.startswith('image'):
            try:
                im = Image.open(StringIO(data))
                dims = im.size
            except IOError:
                dims = None

            if dims is not None:
                yield u'dimensions', u'x'.join(map(unicode, dims))

    size = getHeader('content-range')
    if size is not None:
        if size.startswith('bytes'):
            size = int(size.split(u'/')[-1])
            yield u'size', util.humanReadableFileSize(size)


_whitespace = re.compile(ur'\s+')

def _extractTitle(data):
    def sanitizeTitle(title):
        return _whitespace.sub(u' ', title.strip())

    if data:
        try:
            parser = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder('etree', etree))
            tree = etree.ElementTree(parser.parse(data))
            titleElem = tree.find('//title')
            if titleElem is not None and titleElem.text is not None:
                text = unicode(titleElem.text)
                return sanitizeTitle(text)
        except:
            log.msg('Extracting title failed:')
            log.err()

    return None


def fetchPageData(url):
    def gotData((data, headers)):
        metadata = dict(_buildMetadata(data, headers))

        contentType = metadata.get('contentType', u'application/octet-stream')
        if contentType.startswith(u'text'):
            contentEncoding = headers.get('content-encoding', [None])[0]
            data = _decodeData(data, contentType, contentEncoding)
            title = _extractTitle(data)
        else:
            title = None

        return succeed((title, metadata))

    headers = dict(range='bytes=0-4095')
    return util.PerseverantDownloader(url, headers=headers).go(
        ).addCallback(gotData)


class LinkManager(Item):
    typeName = 'eridanus_plugins_linkdb_linkmanager'
    schemaVersion = 1

    serviceID = bytes(doc="""
    The ID of the service this manager operates under.
    """)

    channel = text(doc="""
    The channel this manager is responsible for.
    """, allowNone=False)

    lastEid = integer(doc="""
    The previously allocated entry ID, starting at 0.
    """, allowNone=False, default=0)

    def __repr__(self):
        return '<%s %s>' % (type(self).__name__, self.channel)

    def createEntry(self, nick, url, title=None):
        """
        Create a new L{LinkEntry} item.

        @type nick: C{unicode}
        @param nick: Nickname of the person who authored the entry

        @type url: C{unicode}
        @param url: URL for the entry

        @type title: C{unicode} or C{None}
        @param title: The title of the entry or C{None} if there isn't one
        """
        eid = self.lastEid
        self.lastEid += 1
        
        return LinkEntry(store=self.store,
                         eid=eid,
                         channel=self.channel,
                         nick=nick,
                         url=url,
                         title=title)

    # XXX: this function needs work, it does way too many things
    def getEntries(self, limit=None, discarded=False, deleted=False):
        """
        Retrieve all L{Entry}s given certain criteria.

        @type limit: C{int} or C{None}
        @param limit: The maximum number of entries to retrieve

        @type discarded: C{boolean} or C{None}
        @param discarded: If this value is not C{None}, only items with the
            specified value will be queried

        @type deleted: C{boolean} or C{None}
        @param deleted: If this value is not C{None}, only items with the
            specified value will be queried

        @rtype: C{iterable}
        @return: Entries that matching the specified criteria
        """
        criteria = [LinkEntry.channel == self.channel]
        if discarded is not None:
            criteria.append(LinkEntry.isDiscarded == discarded)
        if deleted is not None:
            criteria.append(LinkEntry.isDeleted == deleted)

        return self.store.query(LinkEntry,
                                AND(*criteria),
                                limit=limit,
                                sort=LinkEntry.modified.descending)

    def _entryBy(self, eid=None, url=None, evenDeleted=False):
        """
        Retrieve an L{LinkEntry} by certain criteria.

        This is most useful when only specifying either C{eid} or C{url} but
        not both.

        @type eid: C{unicode}
        @param eid: ID (just the numeric part) of the entry to find

        @type url: C{url}
        @param url: URL of the entry to find

        @rtype: L{LinkEntry} or C{None}
        @return: Entry matching the given criteria or C{None} if there isn't
            one
        """
        criteria = [LinkEntry.channel == self.channel]
        if not evenDeleted:
            criteria.append(LinkEntry.isDeleted == False)

        if eid is not None:
            criteria.append(LinkEntry.eid == eid)
        if url is not None:
            criteria.append(LinkEntry.url == url)

        return self.store.findFirst(LinkEntry, AND(*criteria))

    def entryByID(self, eid, evenDeleted=False):
        """
        Get a L{LinkEntry} by ID.

        @type eid: C{unicode}

        @rtype: L{LinkEntry} or C{None}
        """
        return self._entryBy(eid=eid, evenDeleted=evenDeleted)

    def entryByURL(self, url):
        """
        Get a L{LinkEntry} by URL.

        @type url: C{unicode}

        @rtype: L{LinkEntry} or C{None}
        """
        return self._entryBy(url=url)

    def search(self, terms, limit=None):
        """
        Find L{LinkEntry}s with information that matches C{terms}.

        A search attempts to find any entry with any term occuring in the
        title, url or any of the comments.  More terms mean more specific
        results.

        @type terms: C{iterable}
        @param terms: The terms to include in the search

        @type limit: C{int} or C{None}
        @param limit: Maximum number of results to find

        @rtype: C{iterable}
        @return: All L{LinkEntry}s that matched the search terms
        """
        def makeCriteria():
            for term in terms:
                t = u'%%%s%%' % (term,)
                yield OR(LinkEntry.title.like(t),
                         LinkEntry.url.like(t),
                         AND(LinkEntryComment.parent == LinkEntry.storeID,
                             LinkEntryComment.comment.like(t)))

        # XXX: limit=limit).distinct() does this *ACTUALLY* limit the right
        # thing?
        return self.store.query(LinkEntry,
            AND(LinkEntry.channel == self.channel,
                LinkEntry.isDiscarded == False,
                LinkEntry.isDeleted == False,
                *makeCriteria()),
            sort=LinkEntry.modified.descending,
            limit=limit).distinct()

    # XXX: should this really be a method?
    def topContributors(self, limit=None):
        query = self.getEntries(sort=LinkEntry.nick.descending)

        totalEntries = query.count()
        runningTotal = 0
        contributors = 0

        # XXX: this doesn't seem optimal
        groups = ((nick, len(list(entries))) for nick, entries in itertools.groupby(query, lambda e: e.nick))
        groups = sorted(groups, reverse=True, key=lambda g: g[1])

        for nick, count in itertools.islice(groups, limit):
            contributors += 1
            runningTotal += count
            yield nick, count

        # XXX: other seems a bit of a pointless thing
        #if limit is not None and contributors > limit:
        #    yield 'Other', totalEntries - runningTotal

    # XXX: should this really be a method?
    def stats(self):
        store = self.store
        entries = store.query(LinkEntry,
                              LinkEntry.channel == self.channel,
                              sort=LinkEntry.created.ascending)
        numComments = store.query(LinkEntryComment,
                                  AND(LinkEntryComment.parent == LinkEntry.storeID,
                                      LinkEntry.channel == self.channel)).count()

        numEntries = entries.count()
        numContributors = len(list(entries.getColumn('nick').distinct()))
        if numEntries > 0:
            start = iter(entries).next().created
            age = Time() - start
        else:
            age = datetime.timedelta()

        return numEntries, numComments, numContributors, age


class LinkEntry(Item):
    typeName = 'eridanus_plugins_linkdb_linkentry'
    schemaVersion = 1

    eid = integer(doc="""
    The ID of this entry.
    """, allowNone=False)

    created = timestamp(doc="""
    Timestamp of when this entry was created.
    """, defaultFactory=lambda: Time())

    modified = timestamp(doc="""
    Timestamp of when this entry was last modified.
    """, defaultFactory=lambda: Time())

    channel = text(doc="""
    The channel where this entry was first submitted.
    """, allowNone=False)

    nick = text(doc=u"""
    The nickname of the person who submitted this entry first.
    """, allowNone=False)

    url = text(doc=u"""
    Entry's URL.
    """, allowNone=False)

    title = text(doc=u"""
    Optional title for this entry.
    """)

    occurences = integer(doc="""
    Number of times this entry has been mentioned.
    """, default=1)

    isDiscarded = boolean(doc="""
    Indicates whether this item is to be considered for searches and the like.
    """, default=False)

    isDeleted = boolean(doc="""
    Indicates whether this item is to be considered at all.
    """, default=False)

    def __repr__(self):
        return '<%s %s %s>' % (type(self).__name__, self.canonical, self.url)

    def getComments(self, initial=None):
        criteria = [LinkEntryComment.parent == self]
        if initial is not None:
            criteria.append(LinkEntryComment.initial == initial)

        return iter(self.store.query(LinkEntryComment,
                                     AND(*criteria),
                                     sort=LinkEntryComment.created.ascending))

    @property
    def comments(self):
        util.deprecation('This is legacy crap, use getComments rather')
        return self.getComments(initial=False)

    @property
    def initialComment(self):
        util.deprecation('This is legacy crap, use getInitialComment rather')
        return self.getInitialComment()

    @property
    def displayComment(self):
        comment = self.getInitialComment()
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
        def getMetadata():
            metadata = self.getMetadata()

            contentType = metadata.get(u'contentType')
            if contentType is not None:
                yield contentType

                if contentType.startswith('image'):
                    dims = metadata.get(u'dimensions')
                    if dims is not None:
                        yield dims

            size = metadata.get(u'size')
            if size is not None:
                yield size

        if self.title is not None:
            title = self.title
        else:
            comment = self.getInitialComment()
            if comment is not None:
                title = comment.comment
            else:
                title = self.slug

            md = list(getMetadata())
            if md:
                title = u'%s [%s]' % (title, u' '.join(md),)

        return title

    @property
    def displayTimestamp(self):
        return self.created.asHumanly(tzinfo=const.timezone)

    @property
    def displayModifiedTimestamp(self):
        return self.modified.asHumanly(tzinfo=const.timezone)

    @property
    def completeHumanReadable(self):
        return u'#%d: \037%s\037%s @ %s posted %s by \002%s\002.' % (self.eid, self.displayTitle, self.displayComment, self.url, self.displayTimestamp, self.nick)

    @property
    def humanReadable(self):
        return u'#%d: \037%s\037%s posted %s by \002%s\002.' % (self.eid, self.displayTitle, self.displayComment, self.displayTimestamp, self.nick)

    @property
    def canonical(self):
        return u'#%d.%s' % (self.eid, self.channel)

    def getInitialComment(self):
        try:
           return self.getComments(initial=True).next()
        except StopIteration:
            return None

    def _getMetadata(self):
        return self.store.query(LinkEntryMetadata,
                                LinkEntryMetadata.entry == self)

    def getMetadata(self):
        return dict((md.kind, md.data) for md in self._getMetadata())

    def addComment(self, nick, comment):
        """
        Add a comment to this entry.

        If this is the first comment made by the original author of the entry,
        it is specially marked as the initial comment.
        See L{self.getInitialComment}.

        @type nick: C{unicode}
        @param nick: Nickname of the person commenting on this entry

        @type comment: C{unicode}
        @param comment: Comment content

        @rtype: L{LinkEntryComment}
        @return: The newly created comment
        """
        initial = self.getInitialComment() is None and nick == self.nick
        return self.store.findOrCreate(LinkEntryComment, parent=self, nick=nick, comment=comment, initial=initial)

    def touchEntry(self):
        """
        Update the modification time and number of occurences of this entry.
        """
        self.modified = Time()
        self.occurences += 1

    # XXX: does anything use this?
    #def getMetadataByKind(self, kind):
    #    """
    #    Get all L{LinkEntryMetadata} items associated with this entry.
    #    """
    #    return self.store.query(LinkEntryMetadata,
    #                            AND(LinkEntryMetadata.entry == self,
    #                                LinkEntryMetadata.kind == kind))

    def updateMetadata(self, metadata):
        """
        Update this entry's metadata.

        @type metadata: C{dict}
        @param metadata: A mapping of metadata kinds to metadata data to use
            for updating this entry's metadata
        """
        store = self.store
        for kind, data in metadata.iteritems():
            md = store.findOrCreate(LinkEntryMetadata, entry=self, kind=kind)
            md.data = data


class LinkEntryComment(Item):
    typeName = 'eridanus_plugins_linkdb_linkentrycomment'
    schemaVersion = 1

    created = timestamp(doc="""
    Timestamp of when this comment was created.
    """, defaultFactory=lambda: Time())

    parent = reference(doc="""
    L{LinkEntry} item this comment refers to.
    """, allowNone=False, reftype=LinkEntry)

    nick = text(doc="""
    The nickname of the person who commented on L{parent}.
    """, allowNone=False)

    comment = text(doc="""
    The comment text that L{nick} made.
    """, allowNone=False)

    initial = boolean(doc="""
    Indicates whether this was the initial comment made when the entry was created.
    """, allowNone=False, default=False)

    def __repr__(self):
        return '<%s %s: %r>' % (type(self).__name__, self.nick, self.comment)

    @property
    def displayTimestamp(self):
        """
        Convert the C{self.created} timestamp into a human-readable string.
        """
        return self.created.asHumanly(tzinfo=const.timezone)

    @property
    def humanReadable(self):
        """
        Display this comment's information in a concise, human-readble string.
        """
        return u'#%d: %s -- \002%s\002 (%s)' % (self.parent.eid, self.comment, self.nick, self.displayTimestamp)


class LinkEntryMetadata(Item):
    typeName = 'eridanus_plugins_linkdb_linkentrymetadata'
    schemaVersion = 1

    entry = reference(doc="""
    L{LinkEntry} item this metadata is related to.
    """, reftype=LinkEntry)

    kind = text(doc="""
    The kind of metadata this is.  e.g. contentType, size, dimensions, etc.
    """)

    data = text(doc="""
    The actual metadata data.
    """)

    def __repr__(self):
        return '<%s %s: %r>' % (type(self).__name__, self.kind, self.data)
