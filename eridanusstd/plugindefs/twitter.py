from zope.interface import classProvides

from twisted.plugin import IPlugin
from twisted.internet.defer import gatherResults

from axiom.attributes import integer
from axiom.item import Item

from eridanus import iriparse
from eridanus.ieridanus import IEridanusPluginProvider, IAmbientEventObserver
from eridanus.plugin import Plugin, usage
from eridanus.util import truncate

from eridanusstd import twitter, timeutil



class Twitter(Item, Plugin):
    classProvides(IPlugin, IEridanusPluginProvider, IAmbientEventObserver)

    dummy = integer()

    def displayResults(self, results, source):
        source.reply(u'; '.join(results))


    def getStatusIDFromURL(self, url):
        """
        Attempt to retrieve a status ID from a URL.

        @return: A C{unicode} value of the status ID, or C{None} if there is
            none.
        """
        netloc = url.netloc
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        if netloc == 'twitter.com':
            segs = url.pathList()
            if segs >= 3:
                screenName, method, id = segs
                if method in ['status', 'statuses']:
                    try:
                        return unicode(int(id))
                    except (TypeError, ValueError):
                        pass
        return None


    def snarfURLs(self, source, text):
        """
        Find Twitter status URLs in a line of text and display information
        about the status.
        """
        for url in iriparse.parseURLs(text):
            id = self.getStatusIDFromURL(url)
            if id is not None:
                d = twitter.query('statuses/show', id)
                d.addCallback(self.formatStatus)
                d.addCallback(source.notice)
                d.addErrback(lambda f: None)
                yield d


    def formatStatus(self, status):
        """
        Format a status LXML C{ObjectifiedElement}.
        """
        parts = [
            u'\002%s\002' % status.user.screen_name]
        if status.in_reply_to_status_id:
            parts.append(
                u' (in reply to #%s)' % (status.in_reply_to_status_id,))
        timestamp = timeutil.parse(status.created_at.text)
        parts.extend([
            u': %s' % (status['text'],),
            u' (posted %s)' % (timestamp.asHumanly(),)])
        return u''.join(parts)


    def formatUserInfo(self, user):
        """
        Format a user info LXML C{ObjectifiedElement}.
        """
        def _fields():
            yield u'User', u'%s (%s)' % (user.name, user.screen_name)
            yield u'Statuses', user.statuses_count
            yield u'Website', user.url
            yield u'Followers', user.followers_count
            yield u'Friends', user.friends_count
            yield u'Location', user.location
            yield u'Description', user.description

        for key, value in _fields():
            if value:
                yield '\002%s\002: %s' % (key, value)


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


    @usage(u'search <term> [term ...]')
    def cmd_search(self, source, term, *terms):
        """
        Search Twitter.

        For more information about search operators see
        <http://search.twitter.com/operators>.
        """
        terms = [term] + list(terms)
        d = twitter.search(terms)
        d.addCallback(self.formatResults)
        d.addCallback(self.displayResults, source)
        return d


    # IAmbientEventObserver

    def publicMessageReceived(self, source, text):
        return gatherResults(list(self.snarfURLs(source, text)))
