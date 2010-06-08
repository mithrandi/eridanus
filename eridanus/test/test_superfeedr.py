from twisted.trial import unittest
from twisted.internet.defer import succeed

from epsilon.structlike import record

from axiom.store import Store

from eridanus import superfeedr



class PubSubClientMock(superfeedr.SuperfeedrClient):
    """
    Mock PubSub client.
    """
    def __init__(self, *a, **kw):
        super(PubSubClientMock, self).__init__(*a, **kw)
        self.subscriptions = {}


    def subscribe(self, fromJID, url, toJID):
        self.subscriptions[url] = (fromJID, url, toJID)
        return succeed(None)


    def unsubscribe(self, fromJID, url, toJID):
        if url in self.subscriptions:
            del self.subscriptions[url]
        return succeed(None)



class EventMock(record('nodeIdentifier items')):
    """
    Mock PubSub event.
    """



class SuperfeedrServiceTests(unittest.TestCase):
    """
    Tests for L{eridanus.superfeedr.SuperfeedrService}.
    """
    def setUp(self):
        self.store = Store()
        self.service = superfeedr.SuperfeedrService(store=self.store)
        object.__setattr__(
            self.service, 'getCredentials', self.getCredentials)
        object.__setattr__(
            self.service, 'createXMPPClients', self.createXMPPClients)
        self.service.startService()


    def getCredentials(self):
        return (u'jid@domain', u'password')


    def createXMPPClients(self, jid, password):
        return None, PubSubClientMock(self.service)


    def test_subscribe(self):
        """
        L{eridanus.superfeedr.SuperfeedrService.subscribe} returns a
        C{Deferred} that fires immediately if the service is in a ready state.
        """
        self.service.clientConnected()
        self.service.subscribe(u'url', None)
        pubsubClient = self.service.pubsubClient
        self.assertIn(u'url', pubsubClient.subscriptions)


    def test_deferredSubscribe(self):
        """
        L{eridanus.superfeedr.SuperfeedrService.subscribe} returns a
        C{Deferred} that is fired once the service is in a ready state.
        """
        d = self.service.subscribe(u'url', None)

        @d.addCallback
        def clientConnected(dummy):
            pubsubClient = self.service.pubsubClient
            self.assertIn(u'url', pubsubClient.subscriptions)

        # This makes d callback.
        self.assertFalse(d.called)
        self.service.clientConnected()
        self.assertTrue(d.called)
        return d


    def test_itemsReceived(self):
        """
        L{eridanus.superfeedr.SuperfeedrService.itemsReceived} is called when
        PubSub notifications arrive.
        """
        called = []

        def cb(url, items):
            called.append((url, items))

        self.service.clientConnected()
        self.service.subscribe(u'url', cb)
        event = EventMock(
            nodeIdentifier=u'url',
            items=[1, 2])
        self.service.pubsubClient.itemsReceived(event)

        self.assertEquals(called, [(u'url', [1, 2])])


    def test_unsubscribe(self):
        """
        L{eridanus.superfeedr.SuperfeedrService.unsubscribe} only performs a
        PubSub unsubscribe if all C{ISuperfeedrService} subscribers have
        unsubscribed.
        """
        self.service.clientConnected()

        unsubscribers = []
        self.service.subscribe(u'url', 1
            ).addCallback(lambda fn: unsubscribers.append(fn))
        self.service.subscribe(u'url', 2
            ).addCallback(lambda fn: unsubscribers.append(fn))

        pubsubClient = self.service.pubsubClient
        self.assertIn(u'url', pubsubClient.subscriptions)

        unsubscribers.pop()()
        self.service.unsubscribe(u'url')
        self.assertIn(u'url', pubsubClient.subscriptions)

        unsubscribers.pop()()
        self.service.unsubscribe(u'url')
        self.assertNotIn(u'url', pubsubClient.subscriptions)


    def test_deferredUnsubscribe(self):
        """
        L{eridanus.superfeedr.SuperfeedrService.unsubscribe} returns a
        C{Deferred} that is fired once the service is in a ready state.
        """
        self.service.clientConnected()

        unsubscribers = []
        self.service.subscribe(u'url', 1
            ).addCallback(lambda fn: unsubscribers.append(fn))
        self.service.subscribe(u'url', 2
            ).addCallback(lambda fn: unsubscribers.append(fn))

        pubsubClient = self.service.pubsubClient
        self.assertIn(u'url', pubsubClient.subscriptions)

        # Cheap trick to return unfired Deferreds.
        self.service.running = False

        unsubscribers.pop()()
        d = self.service.unsubscribe(u'url')
        self.assertIn(u'url', pubsubClient.subscriptions)

        unsubscribers.pop()()
        d = self.service.unsubscribe(u'url')
        self.assertIn(u'url', pubsubClient.subscriptions)

        # Fire pending Deferreds.
        self.service.clientConnected()

        @d.addCallback
        def checkSubscriptions(dummy):
            self.assertNotIn(u'url', pubsubClient.subscriptions)

        return d
