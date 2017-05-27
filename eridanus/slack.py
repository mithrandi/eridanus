import json
from itertools import count

import treq
from autobahn.twisted.websocket import (
    WebSocketClientFactory, WebSocketClientProtocol)
from axiom.attributes import inmemory, reference, text
from axiom.item import Item
from eridanus import plugin
from twisted.application.internet import ClientService
from twisted.cred.portal import IRealm
from twisted.internet import reactor
from twisted.internet.defer import CancelledError, maybeDeferred
from twisted.internet.endpoints import clientFromString
from twisted.internet.task import deferLater, LoopingCall
from twisted.python import log
from twisted.python.url import URL
from xmantissa.port import PortMixin



class SlackUser(object):
    """
    Representation of a Slack user.
    """
    def __init__(self, protocol, user):
        self._protocol = protocol
        self._user = user


    @property
    def avatarId(self):
        return self._user[u'id']


    @property
    def name(self):
        return self._user[u'name']


    @property
    def mention(self):
        return u'<@{}>'.format(self._user[u'id'])



class SlackSource(object):
    """
    A Slack message source.
    """
    def __init__(self, protocol, channel, user):
        self._protocol = protocol
        self._channel = channel
        self.user = user


    def say(self, text):
        self._protocol.send(
            {u'type': u'message',
             u'channel': self._channel[u'id'],
             u'text': text})


    def reply(self, text):
        if self._channel.get(u'is_im', False):
            self.say(text)
        else:
            self.say(u'{}: {}'.format(self.user.mention, text))


    def logFailure(self, f, msg=None):
        log.err(f, msg)
        m = '%s: %s' % (f.type.__name__, f.getErrorMessage())
        self.reply(m)



class SlackProtocol(WebSocketClientProtocol):
    #def makeConnection(self, transport):
    #    self.transport = transport
    #    self.connectionMade()


    def send(self, message):
        message = dict(message, id=self.id())
        self.sendMessage(json.dumps(message))


    def onOpen(self):
        print "connected"
        self.bot = self.factory.bot
        self.id = count().next
        self.appStore = (
            IRealm(self.bot.store)
            .accountByAddress(u'Eridanus', None)
            .avatars
            .open())
        self.pingTimer = None
        self.pingCall = LoopingCall(self.ping)
        self.pingCall.start(30)


    def connectionLost(self, reason):
        super(SlackProtocol, self).connectionLost(reason)
        print "disconnected"
        self.pingCall.stop()


    def ping(self):
        """
        Send a Slack ping.
        """
        self.send({u'type': u'ping'})
        self.pingTimer = (
            deferLater(reactor, 30, self.transport.loseConnection)
            .addErrback(lambda f: f.trap(CancelledError))
            )


    def onMessage(self, payload, isBinary):
        if isBinary:
            print 'Unsupported binary message received:', repr(payload)
        message = json.loads(payload)
        mtype = message.get(u'type')
        if mtype is None:
            self.unhandled(message)
        else:
            getattr(
                self,
                'handle_' + mtype.encode('ascii'),
                self.unhandled)(message)


    def handle_pong(self, message):
        """
        We got a pong.
        """
        self.pingTimer.cancel()
        self.pingTimer = None


    def handle_message(self, message):
        if message.get(u'hidden', False):
            return
        u = message.get(u'user', None)
        if u is None:
            return
        user = SlackUser(self, self.bot.users[u])
        c = message[u'channel']
        try:
            channel = self.bot.channels[c]
        except KeyError:
            channel = self.bot.ims[c]
        except KeyError:
            print 'Unknown channel:', c
            return
        source = SlackSource(self, channel, user)
        m = message[u'text']
        isDirected = False
        mention = u'<@{}>'.format(self.bot.me[u'id'])
        if mention in m:
            m = m.replace(mention, u'').lstrip(u':')
            isDirected = True
        else:
            suffixes = [u' ', u':', u',']
            for suffix in suffixes:
                p = self.bot.me[u'name'] + suffix
                if m.startswith(p):
                    isDirected = True
                    m = m[len(p):].strip()

        if ((c in self.bot.channels and isDirected) or
            c in self.bot.ims):
            return (
                maybeDeferred(plugin.command, self.appStore, source, m)
                .addErrback(source.logFailure)
                )



    def unhandled(self, message):
        print message



class SlackBot(Item):
    token = text()
    me = inmemory()
    users = inmemory()
    channels = inmemory()
    ims = inmemory()

    def _makeEndpoint(self, url):
        netloc = u'{host}:{port}'.format(
            host=url.host, port=url.port or 443).encode('ascii')
        return clientFromString(reactor, b'tls:' + netloc)


    def connect(self, factory):
        #loginSystem = IRealm(self.store)
        #portal = Portal(loginSystem, [loginSystem, AllowAnonymousAccess()])
        d = treq.get(
            b'https://slack.com/api/rtm.start',
            params=[(b'token', self.token.encode('ascii'))])
        d.addCallback(treq.json_content)
        @d.addCallback
        def gotRTM(response):
            url = URL.fromText(response[u'url'])
            if url.scheme != u'wss':
                raise RuntimeError(url)
            factory.setSessionParameters(
                response[u'url'], useragent=factory.useragent)
            self.me = response[u'self']
            self.users = {u[u'id']: u for u in response[u'users']}
            self.channels = {c[u'id']: c for c in response[u'channels']}
            self.ims = {im[u'id']: im for im in response[u'ims']}
            print factory
            return self._makeEndpoint(url).connect(factory)
        d.addErrback(lambda f: (f, log.err(f))[0])
        return d



class SlackBotService(PortMixin, Item):
    bot = reference(doc="""
    An Item with a C{getFactory} method which returns a Twisted protocol
    factory.
    """, whenDeleted=reference.CASCADE)

    parent = inmemory(doc="""
    A reference to the parent service of this service, whenever there is a
    parent.
    """)

    _service = inmemory(doc="""
    A reference to the real endpoint L{IService}.
    """)

    def activate(self):
        self.parent = None


    def _makeService(self):
        """
        Construct a service for the endpoint as described.
        """
        factory = WebSocketClientFactory()
        factory.protocol = SlackProtocol
        factory.bot = self.bot
        return ClientService(self.bot, factory)


    def privilegedStartService(self):
        self._service = self._makeService()
        self._service.privilegedStartService()


    def startService(self):
        self._service = self._makeService()
        self._service.startService()


    def stopService(self):
        return self._service.stopService()
