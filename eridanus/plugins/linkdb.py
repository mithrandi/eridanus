from zope.interface import classProvides

from twisted.internet.defer import gatherResults
from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus import util
from eridanus.ieridanus import IEridanusPluginProvider, IAmbientEventObserver
from eridanus.plugin import AmbientEventObserver, Plugin, usage

from eridanusstd import linkdb


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


class LinkDBAdminPlugin(Item, Plugin, _LinkDBHelperMixin):
    """
    Provides functionality for managing the LinkDB plugin.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_linkdbadmin'

    name = u'url'
    pluginName = u'LinkDBAdmin'

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


class LinkDBPlugin(Item, Plugin, AmbientEventObserver, _LinkDBHelperMixin):
    """
    LinkDB is designed to track HTTP URLs authored by users.  Each URL is
    stored along with information about the author, the web page's title or
    information about its content and timestamps.  Users can comment on
    LinkDB entries and can recall them by ID.  Entries are grouped by channel
    and access is restricted as such.
    """
    classProvides(IPlugin, IEridanusPluginProvider, IAmbientEventObserver)
    schemaVersion = 1
    typeName = 'eridanus_plugins_linkdb'

    name = u'url'
    pluginName = u'LinkDB'

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

    def find(self, linkManager, terms, limit=25):
        """
        Search for <terms> in entries on <linkManager> up to a maximum of <limit>.
        """
        # XXX: don't hardcode the limit
        entries = list(linkManager.search(terms, limit=limit))

        if not entries:
            msg = u'No results found for: %s.' % (u'; '.join(terms),)
        elif len(entries) == 1:
            msg = entries[0].completeHumanReadable
        else:
            msg = u'%d results. ' % (len(entries,))
            msg += u'  '.join([u'\002#%d\002: \037%s\037' % (e.eid, util.truncate(e.displayTitle, 30)) for e in entries])

        return msg

    @usage(u'find <term> [term ...]')
    def cmd_find(self, source, term, *terms):
        """
        Search for entries whose title, URL or comment contain any <term>.

        This search assumes the channel where the command was invoked, it can
        also not be used in private.  See the "findfor" command.
        """
        terms = [term] + list(terms)
        lm = self.getLinkManager(source)
        msg = self.find(lm, terms)
        source.reply(msg)

    @usage(u'findfor <channel> <term> [term ...]')
    def cmd_findfor(self, source, channel, term, *terms):
        """
        Search <channel> for entries whose title, URL or comment contain any <term>.
        """
        terms = [term] + list(terms)
        lm = self.getLinkManager(source, channel)
        msg = self.find(lm, terms)
        source.reply(msg)

    @usage(u'stats')
    def cmd_stats(self, source):
        """
        Show some interesting statistics for the current channel.
        """
        lm = self.getLinkManager(source)
        numEntries, numComments, numContributors, timespan = lm.stats()
        msg = '%d entries with %d comments from %d contributors over a total time period of %s.' % (numEntries, numComments, numContributors, util.prettyTimeDelta(timespan))
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

    ### IAmbientEventObserver

    def publicMessageReceived(self, source, message):
        return self.snarfURLs(source, message)
