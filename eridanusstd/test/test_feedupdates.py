from epsilon.structlike import record

from twisted.trial import unittest
from twisted.internet.defer import succeed
from twisted.python.filepath import FilePath
from twisted.words.xish import domish

from axiom.store import Store

from eridanusstd import feedupdates, errors
from eridanusstd.plugindefs import feedupdates as feedupdates_plugin



class MockSuperfeedrService(object):
    """
    Mock L{ISuperfeedrService}.
    """
    def subscribe(self, url, callback):
        return succeed(None)


    def unsubscribe(self, url):
        return succeed(None)



class MockSource(record('channel')):
    def __init__(self, *a, **kw):
        super(MockSource, self).__init__(*a, **kw)
        self.calls = {}


    def notice(self, msg):
        self.calls['notice'] = self.calls.setdefault('notice', 0) + 1



class FeedUpdatesTests(unittest.TestCase):
    """
    Tests for L{eridanusstd.feedupdates} and
    L{eridanusstd.plugindefs.feedupdates}.
    """
    def setUp(self):
        self.path = FilePath(__file__)
        self.store = Store()
        self.plugin = feedupdates_plugin.FeedUpdates(store=self.store)
        object.__setattr__(
            self.plugin, 'superfeedrService', MockSuperfeedrService())
        self.source = MockSource(u'#quux')


    def test_subscribe(self):
        self.assertRaises(ValueError,
            self.plugin.subscribe, self.source, u'wrong', u'url', u'not_valid')

        d = self.plugin.subscribe(self.source, u'foo', u'url', u'title')

        @d.addCallback
        def checkSubscription(sub):
            self.assertEquals(sub.id, u'foo')
            self.assertEquals(sub.url, u'url')
            self.assertEquals(sub.formatting, u'title')
            self.assertIdentical(sub.source, self.source)

        @d.addCallback
        def disallowDupes(dummy):
            self.assertRaises(errors.InvalidIdentifier,
                self.plugin.subscribe, self.source, u'foo', u'url', u'title')

        return d


    def test_unsubscribe(self):
        self.assertRaises(errors.InvalidIdentifier,
            self.plugin.unsubscribe, self.source, u'wrong')

        d = self.plugin.subscribe(self.source, u'foo', u'url', u'title')

        @d.addCallback
        def unsubscribeIt(sub):
            return self.plugin.unsubscribe(self.source, u'foo')

        @d.addCallback
        def unsubscibed(dummy):
            self.assertRaises(errors.InvalidIdentifier,
                self.plugin.unsubscribe, self.source, u'foo')

        return d


    def test_getSubscription(self):
        self.assertIdentical(
            self.plugin.getSubscription(u'notthere', self.source.channel),
            None)

        subs = []
        d = self.plugin.subscribe(self.source, u'foo', u'url', u'title')

        @d.addCallback
        def subscribed(sub):
            subs.append(sub)
            self.assertIdentical(
                self.plugin.getSubscription(u'foo', self.source.channel),
                sub)
            return self.plugin.subscribe(self.source, u'bar', u'url', u'title')


        @d.addCallback
        def subscribedAgain(sub):
            subs.append(sub)
            subs.sort(key=lambda s: s.id)
            self.assertEquals(
                list(self.plugin.getSubscriptions(self.source.channel)),
                subs)

        return d


    def parse(self, path):
        elements = []
        stream = domish.ExpatElementStream()
        stream.DocumentStartEvent = lambda root: None
        stream.DocumentEndEvent = lambda: None
        stream.ElementEvent = elements.append
        stream.parse(path.open().read())
        return elements


    def test_itemsReceived(self):
        elements = self.parse(self.path.sibling('feedupdates_1.xml'))
        items = elements[0].elements(
            uri=u'http://jabber.org/protocol/pubsub#event', name=u'items')
        items = list(items.next().elements(
            uri='http://jabber.org/protocol/pubsub#event', name='item'))

        d = self.plugin.subscribe(self.source, u'foo', u'url', u'title')

        @d.addCallback
        def subscribed(sub):
            self.plugin.itemsReceived(sub, items)
            self.assertEquals(self.source.calls['notice'], len(items))

        return d
