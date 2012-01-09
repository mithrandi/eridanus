from zope.interface import classProvides

from functools import partial

from twisted.plugin import IPlugin
from twisted.internet.defer import gatherResults

from axiom.attributes import integer
from axiom.item import Item

from eridanus import iriparse
from eridanus.ieridanus import IEridanusPluginProvider, IAmbientEventObserver
from eridanus.plugin import Plugin, usage, rest, alias
from eridanus.util import truncate

from eridanusstd import twitter



class Twitter(Item, Plugin):
    classProvides(IPlugin, IEridanusPluginProvider, IAmbientEventObserver)

    dummy = integer()

    def displayResults(self, results, source):
        source.reply(u'; '.join(results))


    def snarfStatusIDs(self, text):
        """
        Find Twitter status URLs in a line of text extract the status IDs.
        """
        for url in iriparse.parseURLs(text):
            id = twitter.extractStatusIDFromURL(url)
            if id is not None:
                yield id


    def snarfURLs(self, source, text):
        """
        Find Twitter status URLs in a line of text and display information
        about the status.
        """
        for id in self.snarfStatusIDs(text):
            d = twitter.query('statuses/show', id)
            d.addCallback(self.formatStatus)
            d.addCallback(source.notice)
            d.addErrback(lambda f: None)
            yield d


    def formatUserInfo(self, user):
        """
        Format a user info LXML C{ObjectifiedElement}.
        """
        for key, value in twitter.formatUserInfo(user):
            yield '\002%s\002: %s' % (key, value)


    def formatStatus(self, *a, **kw):
        """
        Format a status LXML C{ObjectifiedElement}.
        """
        parts = twitter.formatStatus(*a, **kw)
        if parts['reply']:
            parts['reply'] = u' (in reply to #%(reply)s)' % parts
        return u'\002%(name)s\002%(reply)s: %(text)s (posted %(timestamp)s)' % parts


    def formatResults(self, results):
        """
        Format Twitter search results.
        """
        for entry in results.entry:
            link = entry.find(
                '{http://www.w3.org/2005/Atom}link[@type="text/html"]')
            yield u'\002%s\002 by \002%s\002: <%s>' % (
                truncate(entry.title.text, 30), entry.author.name, link.get('href'))


    @usage(u'status <id>')
    def cmd_status(self, source, id):
        """
        Retrieve a status by ID.
        """
        d = twitter.query('statuses/show', id)
        d.addCallback(self.formatStatus)
        return d.addCallback(source.reply)


    @usage(u'user <nameOrID>')
    def cmd_user(self, source, nameOrID):
        """
        Retrieve user information for a screen name or user ID.
        """
        d = twitter.query('users/show', nameOrID)
        d.addCallback(self.formatUserInfo)
        d.addCallback(self.displayResults, source)
        return d


    @rest
    @usage(u'search <term>')
    def cmd_search(self, source, term):
        """
        Search Twitter.

        For more information about search operators see
        <http://search.twitter.com/operators>.
        """
        d = twitter.search(term)
        d.addCallback(self.formatResults)
        d.addCallback(self.displayResults, source)
        return d


    @usage(u'recent <nameOrID> [limit]')
    def cmd_recent(self, source, nameOrID, limit=3):
        """
        Retrieve recent statuses (defaulting to 3) for a screen name or user ID.
        """
        d = twitter.query('statuses/user_timeline', nameOrID, count=limit)

        @d.addCallback
        def displayStatuses(timeline):
            map(source.reply, map(self.formatStatus, timeline.status))

        return d


    @usage(u'conversation <id_or_url> [limit]')
    def cmd_conversation(self, source, idOrURL, limit=None):
        """
        Retrieve a Twitter conversation.

        The ID or URL of the latest tweet in the thread should be used, the
        conversation is followed backwards until the beginning or <limit>.
        """
        def displayStatuses(statuses):
            formatStatus = partial(self.formatStatus, includeReplyTo=False)
            map(source.notice, map(formatStatus, reversed(statuses)))

        ids = list(self.snarfStatusIDs(idOrURL))
        if not ids:
            ids = [idOrURL]
        d = twitter.conversation(ids[0], limit)
        d.addCallback(displayStatuses)
        return d

    cmd_convo = alias(cmd_conversation, 'cmd_convo')


    # IAmbientEventObserver

    def publicMessageReceived(self, source, text):
        return gatherResults(list(self.snarfURLs(source, text)))
