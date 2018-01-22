from zope.interface import classProvides

from twisted.python.filepath import FilePath
from twisted.internet.defer import gatherResults
from twisted.plugin import IPlugin

from epsilon.extime import Time

from axiom.attributes import integer
from axiom.item import Item
from axiom.scripts import axiomatic

from eridanus import util
from eridanus.ieridanus import IEridanusPluginProvider, IAmbientEventObserver
from eridanus.plugin import AmbientEventObserver, Plugin, usage, alias, rest
from eridanus.bot import IRCBotService, IRCBotConfig

from eridanusstd import linkdb


class ImportExportFile(object):
    encoding = 'utf-8'

    def __init__(self, fd, appStore):
        self.fd = fd
        self.appStore = appStore
        self.eof = False
        self.count = 0
        self._typeConverters = {'bytes':     (self.writeline, self.readline),
                                'text':      (self.writeText, self.readText),
                                'timestamp': (self.writeTimestamp, self.readTimestamp),
                                'integer':   (self.writeInteger, self.readInteger),
                                'textlist':  (self.writeTextList, self.readTextList),
                                'boolean':   (self.writeBoolean, self.readBoolean)}

    def write(self, s):
        self.fd.write(s)

    def writeline(self, s):
        self.write(s + '\n')

    def readline(self):
        self.count += 1
        line = self.fd.readline()
        if not line:
            self.eof = True

        return line.rstrip()

    def writeInteger(self, value):
        self.writeline(str(value))

    def readInteger(self):
        return int(self.readline())

    def writeTimestamp(self, value):
        self.writeline(str(value.asPOSIXTimestamp()))

    def readTimestamp(self):
        return Time.fromPOSIXTimestamp(float(self.readline()))

    def writeText(self, value):
        if value is None:
            data = ''
        else:
            data = value.encode(self.encoding)
        self.writeline(data)

    def readText(self):
        data = self.readline()
        if not data:
            return None
        return data.decode(self.encoding)

    def writeBoolean(self, value):
        return self.writeline(str(int(value)))

    def readBoolean(self):
        return bool(int(self.readline()))

    def writeTextList(self, value):
        data = '\1'.join(t.encode(self.encoding) for t in value)
        self.writeline(data)

    def readTextList(self):
        return [t.decode(self.encoding) for t in self.readline().split('\1')]

    def writeItem(self, item, attrs):
        for attrName in attrs:
             typeName = getattr(type(item), attrName).__class__.__name__
             writer = self._typeConverters[typeName][0]
             writer(getattr(item, attrName))

    def readItem(self, itemType, attrs):
        def _readAttributes():
            for attrName in attrs:
                typeName = getattr(itemType, attrName).__class__.__name__
                reader = self._typeConverters[typeName][1]
                yield attrName, reader()

        return dict(_readAttributes())

    serviceAttrs = ['serviceID']

    def writeService(self, service):
        self.writeline('service')
        self.writeItem(service, self.serviceAttrs)

        self.writeConfig(service.config)

        for manager in linkdb.getAllLinkManagers(self.appStore, service.serviceID):
            self.writeEntryManager(manager)

    def readService(self):
        return self.readItem(IRCBotService, self.serviceAttrs)

    configAttrs = ['name', 'hostname', 'portNumber', 'nickname', 'channels', 'ignores']

    def writeConfig(self, config):
        self.writeline('config')
        self.writeItem(config, self.configAttrs)

    def readConfig(self):
        return self.readItem(IRCBotConfig, self.configAttrs)

    entryManagerAttrs = ['channel', 'lastEid']

    def writeEntryManager(self, entryManager):
        self.writeline('entrymanager')
        self.writeItem(entryManager, self.entryManagerAttrs)

        for entry in entryManager.getEntries(discarded=None, deleted=None):
            self.writeEntry(entry)

    def readEntryManager(self):
        return self.readItem(linkdb.LinkManager, self.entryManagerAttrs)

    entryAttrs = ['eid', 'created', 'modified', 'channel', 'nick', 'url', 'title', 'occurences', 'isDiscarded', 'isDeleted']

    def writeEntry(self, entry):
        self.writeline('entry')
        self.writeItem(entry, self.entryAttrs)

        for comment in entry.getComments():
            self.writeComment(comment)

        for metadata in entry._getMetadata():
            self.writeMetadata(metadata)

    def readEntry(self):
        return self.readItem(linkdb.LinkEntry, self.entryAttrs)

    commentAttrs = ['created', 'nick', 'comment', 'initial']

    def writeComment(self, comment):
        self.writeline('comment')
        self.writeItem(comment, self.commentAttrs)

    def readComment(self):
        return self.readItem(linkdb.LinkEntryComment, self.commentAttrs)

    metadataAttrs = ['kind', 'data']

    def writeMetadata(self, metadata):
        self.writeline('metadata')
        self.writeItem(metadata, self.metadataAttrs)

    def readMetadata(self):
        return self.readItem(linkdb.LinkEntryMetadata, self.metadataAttrs)


class ExportEntries(axiomatic.AxiomaticSubCommand):
    longdesc = 'Export linkdb entries to disk'

    optParameters = [
        ('path', 'p', None, 'Path to output export data to'),
        ]

    def getStore(self):
        return self.parent.getStore()

    def getAppStore(self):
        return self.parent.getAppStore()

    def postOptions(self):
        appStore = self.getAppStore()
        store = self.getStore()

        outroot = FilePath(self['path'])
        if not outroot.exists():
            outroot.makedirs()

        for i, service in enumerate(store.query(IRCBotService)):
            print 'Processing service %r...' % (service.serviceID,)

            fd = outroot.child(str(i)).open('wb')
            ief = ImportExportFile(fd, appStore)
            ief.writeService(service)


class ImportEntries(axiomatic.AxiomaticSubCommand):
    longdesc = 'Import linkdb entries from an export'

    optFlags = [
        ('clear', None, 'Remove existing entries before performing the import'),
        ]

    optParameters = [
        ('path', 'p', None, 'Path to read export data from'),
        ]

    def getStore(self):
        return self.parent.getStore()

    def getAppStore(self):
        return self.parent.getAppStore()

    def postOptions(self):
        appStore = self.getAppStore()
        siteStore = self.getStore()

        inroot = FilePath(self['path'])

        availableModes = ['service', 'config', 'entrymanager', 'entry', 'comment', 'metadata']

        if self['clear']:
            appStore.query(linkdb.LinkEntryComment).deleteFromStore()
            appStore.query(linkdb.LinkEntryMetadata).deleteFromStore()
            appStore.query(linkdb.LinkEntry).deleteFromStore()
            appStore.query(linkdb.LinkManager).deleteFromStore()

        mode = None
        service = None
        entryManager = None
        entry = None

        for fp in inroot.globChildren('*'):
            fd = fp.open()
            ief = ImportExportFile(fd, appStore)

            while True:
                line = ief.readline()
                if ief.eof:
                    break

                if line in availableModes:
                    mode = line

                if mode == 'service':
                    # We assume the service already exists here.
                    kw = ief.readService()
                    sid = kw['serviceID']
                    print 'Assuming service "%s" exists and is configured.' % (sid,)
                    service = siteStore.findUnique(IRCBotService,
                                                   IRCBotService.serviceID == sid)
                elif mode == 'config':
                    # For legacy reasons, we must still read the service config.
                    kw = ief.readConfig()
                    #service.config = config = IRCBotConfig(store=siteStore, **kw)
                elif mode == 'entrymanager':
                    assert service is not None
                    kw = ief.readEntryManager()
                    print 'Creating entry manager for %(channel)s...' % kw
                    entryManager = linkdb.LinkManager(store=appStore, serviceID=service.serviceID, **kw)
                    if self['clear']:
                        entryManager.searchIndexer.reset()
                elif mode == 'entry':
                    assert entryManager is not None
                    kw = ief.readEntry()
                    #print 'Creating entry #%(eid)s for %(channel)s...' % kw
                    entry = linkdb.LinkEntry(store=appStore, **kw)
                elif mode == 'comment':
                    assert entry is not None
                    kw = ief.readComment()
                    linkdb.LinkEntryComment(store=appStore, parent=entry, **kw)
                elif mode == 'metadata':
                    assert entry is not None
                    kw = ief.readMetadata()
                    linkdb.LinkEntryMetadata(store=appStore, entry=entry, **kw)


class Hackery(axiomatic.AxiomaticSubCommand):
    longdesc = 'Beware, thar be hacks!'

    def postOptions(self):
        #from axiom.scheduler import Scheduler
        from xmantissa.fulltext import SQLiteIndexer
        from xmantissa.ixmantissa import IFulltextIndexer
        store = self.parent.getAppStore()

        #scheduler = Scheduler(store=store)
        #installOn(scheduler, store)

        print 'Deleting old indexers...'
        store.query(SQLiteIndexer).deleteFromStore()
        print 'Creating new indexer...'
        indexer = SQLiteIndexer(store=store)
        store.powerUp(indexer, IFulltextIndexer)

        entrySource = store.findOrCreate(linkdb.LinkEntrySource)
        indexer.addSource(entrySource)
        commentSource = store.findOrCreate(linkdb.LinkEntryCommentSource)
        indexer.addSource(commentSource)


class _LinkDBHelperMixin(object):
    def getLinkStore(self, source):
        """
        Get the C{axiom.store.Store} to find links in.
        """
        raise NotImplementedError()

    def getLinkManager(self, source, channel=None):
        """
        Get the link manager for C{source}.
        """
        if channel is None:
            channel=source.channel
        serviceID = source.protocol.serviceID
        return linkdb.getLinkManager(self.getLinkStore(source),
                                     serviceID,
                                     channel)

    def getEntryByID(self, source, entryID):
        """
        Get the entry for C{entryID} and C{source}.
        """
        serviceID = source.protocol.serviceID
        return linkdb.getEntryByID(self.getLinkStore(source),
                                   serviceID,
                                   entryID,
                                   source.channel)


class LinkDBAdmin(Item, Plugin, _LinkDBHelperMixin):
    """
    Provides functionality for managing the LinkDB plugin.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_linkdbadmin'

    name = u'url'

    dummy = integer()

    def getLinkStore(self, source):
        # XXX: mmm...
        return source.protocol.appStore

    @usage(u'discard <entryID>')
    def cmd_discard(self, source, entryID):
        """
        Discards entry <entryID>.
        """
        entry = self.getEntryByID(source, entryID)
        entry.isDiscarded = True
        source.reply(u'Discarded entry %s.' % (entry.canonical,))

    @usage(u'undiscard <entryID>')
    def cmd_undiscard(self, source, entryID):
        """
        Undiscard <entryID>.
        """
        entry = self.getEntryByID(source, entryID)
        entry.isDiscarded = False
        source.reply(u'Undiscarded entry %s.' % (entry.canonical,))

    @usage(u'delete <entryID>')
    def cmd_delete(self, source, entryID):
        """
        Deletes entry <entryID>.
        """
        entry = self.getEntryByID(source, entryID)
        entry.isDeleted = True
        source.reply(u'Deleted entry %s.' % (entry.canonical,))

    @usage(u'undelete <entryID>')
    def cmd_undelete(self, source, entryID):
        """
        Undelete <entryID>.
        """
        entry = self.getEntryByID(source, entryID, evenDeleted=True)
        entry.isDeleted = False
        source.reply(u'Undeleted entry %s.' % (entry.canonical,))



class LinkDB(Item, Plugin, AmbientEventObserver, _LinkDBHelperMixin):
    """
    LinkDB is designed to track HTTP URLs authored by users.  Each URL is
    stored along with information about the author, the web page's title or
    information about its content and timestamps.  Users can comment on
    LinkDB entries and can recall them by ID.  Entries are grouped by channel
    and access is restricted as such.
    """
    classProvides(IPlugin, IEridanusPluginProvider, IAmbientEventObserver)
    typeName = 'eridanus_plugins_linkdb'

    axiomCommands = [
        ('export',  None, ExportEntries,  'Export entries'),
        ('import',  None, ImportEntries,  'Import entries'),
        ('hackery', None, Hackery,        'Perform magic')]

    name = u'url'

    dummy = integer()

    def getLinkStore(self, source):
        return self.store


    def createEntry(self, (title, metadata), source, url, comment):
        """
        Create a new entry.
        """
        lm = self.getLinkManager(source)
        nick = source.user.nickname
        entry = lm.createEntry(nick=nick,
                               url=url,
                               title=title)

        if comment is not None:
            entry.addComment(nick, comment)
        if metadata is not None:
            entry.updateMetadata(metadata)

        return entry


    def updateEntry(self, (title, metadata), source, entry, comment=None):
        """
        Update C{entry}.
        """
        if title is not None:
            entry.title = title

        if comment:
            c = entry.addComment(source.user.nickname, comment)
        else:
            c = None

        if metadata is not None:
            entry.updateMetadata(metadata)

        entry.touchEntry()
        return entry, c


    def fetchFailed(self, f, source, url):
        # Log the failure but go ahead with creating/updating the entry.
        msg = 'Fetching %s failed:' % (url,)
        source.logFailure(f, msg)
        return None, {}


    def snarfURLs(self, source, text):
        """
        Extract URLs and create or update entries from C{text}.
        """
        def entryCreated(entry):
            source.notice(entry.humanReadable)

        def entryUpdated((entry, comment)):
            source.notice(entry.humanReadable)
            if comment is not None:
                source.notice(comment.humanReadable)

        def fetch():
            lm = self.getLinkManager(source)

            for url, comment in linkdb.extractURLs(text):
                entry = lm.entryByURL(url)

                # XXX: doesn't this mean we have to fetch in serial?
                d = linkdb.fetchPageData(url).addErrback(self.fetchFailed, source, url)
                if entry is None:
                    d.addCallback(self.createEntry, source, url, comment
                        ).addCallback(entryCreated)
                else:
                    d.addCallback(self.updateEntry, source, entry, comment
                        ).addCallback(entryUpdated)

                yield d

        return gatherResults(list(fetch()))


    @usage(u'get <entryID>')
    def cmd_get(self, source, entryID):
        """
        Retrieve the entry for <entryID>.
        """
        entry = self.getEntryByID(source, entryID)
        source.reply(entry.completeHumanReadable)


    def find(self, linkManager, term, limit=25):
        """
        Search C{linkManager} for entries that match C{term}, up to a maximum
        of C{limit}.
        """
        def processResults(entries):
            entries = list(entries)
            if not entries:
                yield u'No results found for: %s' % (term,)
            elif len(entries) <= 3:
                for e in entries:
                    yield e.completeHumanReadable
            else:
                msg = u'%d results. ' % (len(entries,))
                msg += u'  '.join([u'\002#%d\002: \037%s\037' % (e.eid, util.truncate(e.displayTitle, 30)) for e in entries])
                yield msg

        # XXX: don't hardcode the limit
        return linkManager.search(term, limit=limit
            ).addCallback(processResults)


    @usage(u'random')
    def cmd_random(self, source):
        lm = self.getLinkManager(source)
        result = lm.randomEntry()
        if result is not None:
            source.reply(result.completeHumanReadable)
        else:
            source.reply('No results found')


    @rest
    @usage(u'find <term>')
    def cmd_find(self, source, term):
        """
        Search for entries whose title, URL or comment match <term>.

        This search assumes the channel where the command was invoked, it can
        also not be used in private.  See the "findfor" command.
        """
        self.cmd_findfor(source, source.channel, term)

    cmd_search = alias(cmd_find, 'cmd_search')


    @rest
    @usage(u'findfor <channel> <term>')
    def cmd_findfor(self, source, channel, term):
        """
        Search <channel> for entries whose title, URL or comment match <term>.
        """
        lm = self.getLinkManager(source, channel)

        def gotResults(results):
            map(source.reply, results)

        return self.find(lm, term
            ).addCallback(gotResults)


    @usage(u'stats')
    def cmd_stats(self, source):
        """
        Show some interesting statistics for the current channel.
        """
        lm = self.getLinkManager(source)
        numEntries, numComments, numContributors, timespan = lm.stats()
        msg = '%d entries with %d comments from %d contributors over a total time period of %s.' % (numEntries, numComments, numContributors, util.humanReadableTimeDelta(timespan))
        source.reply(msg)


    @usage(u'discard <entryID>')
    def cmd_discard(self, source, entryID):
        """
        Discards entry <entryID>.

        Discarded entries are not considered for searching but can still be
        viewed directly by using the "get" command.  This operation can be
        reversed by the "undiscard" command in the LinkDBAdmin plugin.
        """
        entry = self.getEntryByID(source, entryID)
        if entry.nick == source.user.nickname:
            entry.isDiscarded = True
            msg = u'Discarded entry %s.' % (entry.canonical,)
        else:
            msg = u'You did not post this entry, ask %s to discard it.' % (entry.nick,)

        source.reply(msg)


    @usage(u'delete <entryID>')
    def cmd_delete(self, source, entryID):
        """
        Deletes entry <entryID>.

        Deleted entries will be unaccessible by regular users, in order to
        reverse this operation, someone granted the LinkDBAdmin plugin must
        perform the "undelete" command.
        """
        entry = self.getEntryByID(source, entryID)
        if entry.nick == source.user.nickname:
            entry.isDeleted = True
            msg = u'Deleted entry %s.' % (entry.canonical,)
        else:
            msg = u'You did not post this entry, ask %s to delete it.' % (entry.nick,)

        source.reply(msg)


    @usage(u'refresh <entryID>')
    def cmd_refresh(self, source, entryID):
        """
        Updates the title of <entryID>.
        """
        def entryUpdated(entry):
            source.notice(entry.humanReadable)

        entry = self.getEntryByID(source, entryID)
        return linkdb.fetchPageData(entry.url
            ).addCallback(self.updateEntry, source, entry
            ).addErrback(self.fetchFailed, source, entry.url
            # XXX: it might be nice if self.fetchFailed could return the right thing for us
            ).addCallback(lambda *a: entryUpdated(entry))


    @usage(u'recent [nickname]')
    def cmd_recent(self, source, nickname=None):
        """
        Get recent URL entries.
        """
        lm = self.getLinkManager(source)
        entries = list(lm.recent(3, nickname))
        if entries:
            for e in entries:
                source.notice(e.displayCompleteHumanReadable(modified=True))
        else:
            if nickname is None:
                msg = u'No recent entries.'
            else:
                msg = u'No recent entries for \002%s\002.' % (nickname,)
            source.reply(msg)


    # IAmbientEventObserver

    def publicMessageReceived(self, source, message):
        return self.snarfURLs(source, message)
