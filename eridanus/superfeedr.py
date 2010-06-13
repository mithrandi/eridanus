from zope.interface import implements

from twisted.words.protocols.jabber.jid import JID
from twisted.application.service import IService, IServiceCollection
from twisted.internet.defer import Deferred, succeed

from axiom.item import Item
from axiom.attributes import integer, inmemory

from wokkel.client import XMPPClient
from wokkel.xmppim import PresenceClientProtocol
from wokkel.pubsub import PubSubClient

from eridanus import errors
from eridanus.ieridanus import ISuperfeedrService
from eridanus.util import getAPIKey



class SuperfeedrClient(PubSubClient):
    """
    Superfeedr PubSub client.
    """
    def __init__(self, superfeedrService, **kw):
        super(SuperfeedrClient, self).__init__(**kw)
        self.superfeedrService = superfeedrService


    def connectionInitialized(self):
        super(SuperfeedrClient, self).connectionInitialized()
        self.superfeedrService.clientConnected()


    def itemsReceived(self, event):
        self.superfeedrService.itemsReceived(
            event.nodeIdentifier, event.items)



class SuperfeedrService(Item):
    implements(IService, ISuperfeedrService)

    powerupInterfaces = [IService, ISuperfeedrService]

    name = None

    apiKeyName = u'superfeedr'

    dummy = integer()

    _subscribers = inmemory(doc="""
    Mapping of C{unicode} URLs to a C{list} of callback functions.
    """)

    _callWhenReady = inmemory(doc="""
    C{list} of C{Deferred}s that are fired when the XMPP client has
    successfully connected.
    """)

    parent = inmemory(doc="""
    Parent of this service.
    """)

    running = inmemory(doc="""
    Flad indicating whether this service is running, the service is considered
    running if the XMPP client has successfully connected.
    """)

    jid = inmemory(doc="""
    Jabber ID of the service.
    """)

    xmppClient = inmemory(doc="""
    C{XMPPClient} instance.
    """)

    pubsubClient = inmemory(doc="""
    L{SuperfeedrClient} instance
    """)

    def activate(self):
        self._callWhenReady = []
        self._subscribers = {}
        self.running = False


    def clientConnected(self):
        """
        Called when the PubSub client connection has initialized.
        """
        self.running = True
        for d in self._callWhenReady:
            d.callback(None)


    def getCredentials(self):
        """
        Get XMPP credentials.

        @rtype: C{(unicode, unicode)}
        @return: C{(JID, password)}
        """
        creds = getAPIKey(self.store, self.apiKeyName).split(u':', 1)
        if len(creds) != 2:
            raise errors.MissingAPIKey(
                u'Superfeedr key must be of the form jid:password')
        return creds


    def createXMPPClients(self, jid, password):
        """
        Create XMPP clients.

        @return: C{(xmppClient, pubsubClient)}
        """
        xmppClient = XMPPClient(jid, password)
        xmppClient.startService()

        presence = PresenceClientProtocol()
        presence.setHandlerParent(xmppClient)
        presence.available(priority=127)

        pubsubClient = SuperfeedrClient(self)
        pubsubClient.setHandlerParent(xmppClient)

        return xmppClient, pubsubClient


    def itemsReceived(self, url, items):
        """
        A notification arrived for a subscribed feed.

        Subscribers to C{url} have their callbacks fired with C{url} and
        C{items}.

        @type  url: C{unicode}
        @param url: Feed URL.

        @type  items: C{list} of C{twisted.words.xish.domish.Element}
        @param items: Newly arrived feed items.
        """
        callbacks = self._subscribers.get(url, [])
        for callback in callbacks:
            callback(url, items)


    def _addFeed(self, url):
        # XXX: only subscribe if needed
        return self.pubsubClient.subscribe(
            JID('firehoser.superfeedr.com'), url, self.jid)


    def _maybeRemoveFeed(self, url):
        if not self._subscribers.get(url):
            return self.pubsubClient.unsubscribe(
                JID('firehoser.superfeedr.com'), url, self.jid)
        return succeed(None)


    # ISuperfeedrService

    def subscribe(self, url, callback):
        if self.running:
            d = succeed(None)
        else:
            d = Deferred()
            self._callWhenReady.append(d)

        def _subscribe(dummy):
            def subscribed(dummy):
                self._subscribers.setdefault(url, []).append(callback)
                return lambda: self._subscribers[url].remove(callback)
            return self._addFeed(url).addCallback(subscribed)

        return d.addCallback(_subscribe)


    def unsubscribe(self, url):
        if self.running:
            d = succeed(None)
        else:
            d = Deferred()
            self._callWhenReady.append(d)

        def _unsubscribe(dummy):
            return self._maybeRemoveFeed(url)

        return d.addCallback(_unsubscribe)


    # IService

    def setServiceParent(self, parent):
        IServiceCollection(parent).addService(self)
        self.parent = parent


    def disownServiceParent(self):
        IServiceCollection(self.parent).removeService(self)
        self.parent = None


    def privilegedStartService(self):
        pass


    def startService(self):
        jid, password = self.getCredentials()
        self.jid = JID(jid + '/eridanus')

        self.xmppClient, self.pubsubClient = self.createXMPPClients(
            self.jid, password)


    def stopService(self):
        self.running = False
        return self.xmppClient.stopService()
