from zope.interface import classProvides
from functools import partial

from epsilon.extime import Time

from twisted.internet.defer import gatherResults
from twisted.plugin import IPlugin

from axiom.item import Item
from axiom.attributes import AND, integer
from axiom.dependency import requiresFromSite

from eridanus import const
from eridanus.ieridanus import (IEridanusPluginProvider, IAmbientEventObserver,
    ISuperfeedrService)
from eridanus.plugin import AmbientEventObserver, Plugin, usage

from eridanusstd import errors
from eridanusstd.feedupdates import SubscribedFeed



class FeedUpdates(Item, Plugin, AmbientEventObserver):
    """
    Receive notifications for web feed updates.
    """
    classProvides(IPlugin, IEridanusPluginProvider, IAmbientEventObserver)

    dummy = integer()

    superfeedrService = requiresFromSite(
        ISuperfeedrService)

    formatting = {
        u'title':         ['title'],
        u'summary':       ['summary'],
        u'content':       ['content'],
        u'title_summary': ['title', 'summary'],
        u'title_content': ['title', 'content']}

    def formatEntry(self, formatting, entry):
        """
        Format an Superfeedr entry element according to the formatting type.
        """
        parts = [
            getattr(entry, elemName, None) or u'<unknown>'
            for elemName in formatting]
        parts = u' -- '.join(map(str, parts))

        try:
            timestamp = Time.fromISO8601TimeAndDate(
                str(entry.published)).asHumanly(tzinfo=const.timezone)
            timestamp = u' (%s)' % (timestamp,)
        except ValueError:
            timestamp = u''

        return u'%s%s' % (parts, timestamp)


    def itemsReceived(self, sub, items):
        """
        Subscription item delivery callback.
        """
        for item in items:
            text = self.formatEntry(
                self.formatting[sub.formatting], item.entry)
            sub.source.notice(u'\002%s\002: %s' % (sub.id, text))


    def getSubscriptions(self, subscriber):
        """
        Get all L{SubscribedFeed} for C{subscriber}.
        """
        return self.store.query(
            SubscribedFeed,
            SubscribedFeed.subscriber == subscriber,
            sort=SubscribedFeed.id.ascending)


    def getSubscription(self, id, subscriber):
        """
        Get the L{SubscribedFeed} for C{id} and C{subscriber}.
        """
        return self.store.findUnique(
            SubscribedFeed,
            AND(SubscribedFeed.id == id,
                SubscribedFeed.subscriber == subscriber),
            default=None)


    def _subscribe(self, source, sub):
        """
        Subscribe a L{SubscribedFeed} and register the source to deliver
        notifications via.
        """
        def receiver(sub):
            def _innerReceiver(url, items):
                self.itemsReceived(sub, items)
            return _innerReceiver

        sub.source = source
        return sub.subscribe(self.superfeedrService, receiver(sub))


    def subscribe(self, source, id, url, formatting):
        """
        Create and subscribe a L{SubscribedFeed} and register the source to
        deliver notifications via.
        """
        sub = self.getSubscription(id, source.channel)
        if sub is not None:
            raise errors.InvalidIdentifier(
                u'A subscription with that identifier already exists')

        formatting = formatting.lower()
        if formatting not in self.formatting:
            raise ValueError(
                u'"%s" is not a valid format specifier' % (formatting,))

        sub = SubscribedFeed(
            store=self.store,
            id=id,
            url=url,
            subscriber=source.channel,
            formatting=formatting)
        return self._subscribe(source, sub)


    def unsubscribe(self, source, id):
        """
        Unsubscribe a L{SubscribedFeed}.
        """
        sub = self.getSubscription(id, source.channel)
        if sub is None:
            raise errors.InvalidIdentifier(
                u'No subscription with that identifier exists')

        return sub.unsubscribe(self.superfeedrService)


    @usage(u'subscribe <id> <url> <formatting>')
    def cmd_subscribe(self, source, id, url, formatting):
        """
        Subscribe to notifications for a feed.

        The `formatting` argument can be one of: "title", "summary", "content",
        "title_summary" or "title_content", indicating that the notification
        should contain the title, summary, content, title and summary, or title
        and content respectively.
        """
        def subscribed(dummy):
            source.reply(u'Subscribed to "%s" <%s>' % (id, url))

        d = self.subscribe(source, id, url, formatting)
        return d.addCallback(subscribed)


    @usage(u'unsubscribe <id>')
    def cmd_unsubscribe(self, source, id):
        """
        Unsubscribe from notifications for a feed.
        """
        def unsubscribed(dummy):
            source.reply(u'Unsubscribed from "%s"' % (id,))

        d = self.unsubscribe(source, id)
        return d.addCallback(unsubscribed)


    @usage(u'list')
    def cmd_list(self, source):
        """
        List subscriptions.
        """
        def subs():
            for sub in self.getSubscriptions(source.channel):
                yield u'\002%s\002: <%s>' % (sub.id, sub.url)

        msg = u'; '.join(subs())
        source.reply(msg)


    # IAmbientEventObserver

    def joinedChannel(self, source):
        subs = self.store.query(
            SubscribedFeed, SubscribedFeed.subscriber == source.channel)
        return gatherResults(map(partial(self._subscribe, source), subs))
