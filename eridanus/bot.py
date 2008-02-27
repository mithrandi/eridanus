import re

from zope.interface import implements

from axiom.item import Item
from axiom.attributes import integer, inmemory, reference, bytes, AND, text
from axiom.upgrade import registerUpgrader

from twisted.python import log
from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory
from twisted.internet.defer import succeed
from twisted.words.protocols.irc import IRCClient
from twisted.application.service import IService, IServiceCollection

from eridanus import gchart
from eridanus.entry import EntryManager
from eridanus.util import encode, decode, getPage, extractTitle


class User(object):
    def __init__(self, user):
        super(User, self).__init__()
        if '!' in user:
            nickname, realname = user.split('!', 1)
            realname, host = realname.split('@', 1)
        else:
            nickname = realname = None
            host = user

        self.nickname = nickname
        self.realname = realname
        self.host = host


class IRCBot(IRCClient):
    urlPattern = re.compile(ur'((?:(?:(?:https?|ftp):\/\/)|www\.)(?:(?:[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)|localhost|(?:[a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(?:com|net|org|info|biz|gov|name|edu|[a-zA-Z][a-zA-Z]))(?::[0-9]+)?(?:(?:\/|\?)[^ "]*[^ ,;\.:">)])?/?)')
    commentPattern = re.compile(ur'\s+(?:(?:\[(.*)\])|(?:<?-- (.*)))')

    def __init__(self, config):
        self.config = config
        self.nickname = encode(config.nickname)
        self._entryManagers = dict((em.channel, em) for em in config.getEntryManagers())

    def signedOn(self):
        for channel in self.config.channels:
            self.join(channel)

    def getEntryManager(self, channelName):
        em = self._entryManagers.get(decode(channelName))
        if em is None:
            em = self._entryManagers[channelName] = self.config.createEntryManager(channelName)
        return em

    def say(self, channel, message, length=None):
        return IRCClient.say(self, channel, encode(message), length)

    def reply(self, user, channel, message):
        nick = user.nickname
        self.say(channel, u'%s: %s' % (nick, message))

    def directedUserText(self, user, channel, message):
        params = message.split()
        cmd = params.pop(0).lower()

        handler = getattr(self, 'cmd_' + cmd, None)
        if handler is not None:
            handler(user, channel, *params)
        else:
            self.reply(user, channel, u'No such command: %s' % (cmd,))

    def userText(self, user, channel, message):
        match = self.urlPattern.search(message)
        if match is None:
            return

        url = match.group(1)

        comment = self.commentPattern.search(message, match.start())
        if comment is not None:
            comment = filter(None, comment.groups())[0]

        em = self.getEntryManager(channel)
        nickname = decode(user.nickname)

        def createEntry(title):
            return em.createEntry(channel=decode(channel),
                                  nick=nickname,
                                  url=url,
                                  comment=comment,
                                  title=title)

        entry = em.entryByUrl(url)

        if entry is None:
            # Only bother fetching the first 4096 bytes of the URL.
            d = getPage(str(url), headers=dict(range='bytes=0-4095')
                ).addCallbacks(extractTitle, lambda e: None
                ).addCallback(createEntry)
        else:
            entry.occurences += 1
            if comment is not None and entry.nick != nickname:
                print 'adding new comment by %s: %s to %s' % (nickname, comment, str(entry))
                entry.addComment(nickname, comment)
            d = succeed(entry)

        def noticeEntry(entry):
            self.notice(channel, encode(entry.humanReadable))

        d.addCallback(noticeEntry)

    def privmsg(self, user, channel, message):
        user = User(user)
        if channel == self.nickname or user.nickname in self.config.ignores:
            return

        message = decode(message)
        directed = self.nickname.lower() + u':'

        if message.lower().startswith(directed):
            message = message[len(directed):].strip()
            self.directedUserText(user, channel, message)
        else:
            self.userText(user, channel, message)

    ### Commands

    def cmd_get(self, user, channel, eid, entryChannel=None):
        try:
            eid = int(eid)
        except ValueError:
            self.reply(user, channel, u'Invalid entry ID.')
            return

        if entryChannel is None:
            entryChannel = channel

        em = self.getEntryManager(entryChannel)
        entry = em.entryById(eid)
        if entry is not None:
            msg = entry.completeHumanReadable
        else:
            msg = u'No such entry with that ID.'

        self.reply(user, channel, msg)

    def cmd_join(self, user, channel, channelName):
        self.join(channelName)

    def cmd_part(self, user, channel, channelName=None):
        if channelName is None:
            channelName = channel
        self.part(channelName)

    def cmd_ignore(self, user, channel, nick):
        self.config.ignore(nick)

    def cmd_stats(self, user, channel, channelName=None):
        if channelName is None:
            channelName = channel

        limit = 10

        em = self.getEntryManager(channelName)
        data = sorted(em.topContributors(limit=limit), key=lambda x: x[1])
        labels, data = zip(*data)

        title = 'Top %d URL contributors for %s' % (limit, channelName)
        chart = gchart.Pie(size=(900, 300), data=[data], labels=labels, title=title)
        self.reply(user, channel, str(chart.url))

    def cmd_info(self, user, channel, eid, entryChannel=None):
        try:
            eid = int(eid)
        except ValueError:
            self.reply(user, channel, u'Invalid entry ID.')
            return

        if entryChannel is None:
            entryChannel = channel

        em = self.getEntryManager(entryChannel)
        entry = em.entryById(eid)
        if entry is not None:
            comments = ['%s: %s' % (c.nick, c.comment) for c in entry.comments]
            msg = u'#%d: Mentioned %d time(s), first by \002%s\002.' % (entry.eid, entry.occurences, entry.nick)
            if comments:
                msg += u' Comments: ' + '  '.join(comments)
        else:
            msg = u'No such entry with that ID.'

        self.reply(user, channel, msg)


class IRCBotFactory(ClientFactory):
    protocol = IRCBot

    def __init__(self, config):
        self.bot = self.protocol(config)

    def buildProtocol(self, addr=None):
        return self.bot

    def clientConnectionLost(self, conn, reason):
        print 'clientConnectionLost', conn, reason


class IRCBotFactoryFactory(Item):
    schemaVersion = 1

    dummy = integer()

    def getFactory(self, config):
        return IRCBotFactory(config)


class IRCBotConfig(Item):
    typeName = 'eridanus_ircbotconfig'
    schemaVersion = 2

    hostname = bytes(doc="""
    The hostname of the IRC server to connect to.
    """)

    portNumber = integer(doc="""
    The port to connect to the IRC server on.
    """)

    nickname = text(doc="""
    The bot's nickname.
    """)

    _channels = text(doc="""
    Channels the bot should monitor.
    """)

    _ignores = text(default='')

    @property
    def channels(self):
        return encode(self._channels).split(',')

    @property
    def ignores(self):
        return encode(self._ignores).split(',')

    def getEntryManagers(self):
        return self.store.query(EntryManager, EntryManager.config == self)

    def getEntryManager(self, channel):
        return self.store.findFirst(EntryManager,
                                    AND(EntryManager.config == self,
                                        EntryManager.channel == channel))

    def createEntryManager(self, channel):
        return self.store.findOrCreate(EntryManager, config=self, channel=channel)

    def ignore(self, nick):
        self.ignores = ','.join(self.ignores.append(nick))

    def unignore(self, nick):
        raise NotImplementedError()

def ircbotconfig1to2(old):
    return old.upgradeVersion(
        IRCBotConfig.typeName, 1, 2,
        hostname=old.hostname,
        portNumber=old.portNumber,
        nickname=old.nickname.decode('utf-8'),
        _channels=old._channels.decode('utf-8'),
        _ignores=old._ignores.decode('utf-8'))

registerUpgrader(ircbotconfig1to2, IRCBotConfig.typeName, 1, 2)


class IRCBotService(Item):
    implements(IService)

    typeName = 'eridanus_ircbotservice'
    schemaVersion = 1

    powerupInterfaces = [IService]

    name = None

    serviceID = bytes(allowNone=False)

    config = reference()

    parent = inmemory(doc="""
    The parent of this service.
    """)

    factory = reference(doc="""
    An L{Item} with a C{getFactory} method which returns a Twisted protocol
    factory.
    """, whenDeleted=reference.CASCADE)

    connector = inmemory(doc="""
    The L{IConnector} returned by C{reactor.connectTCP}.
    """)

    def connect(self):
        assert self.config is not None, 'No configuration data'
        return reactor.connectTCP(self.config.hostname, self.config.portNumber, self.factory.getFactory(self.config))

    def activate(self):
        self.parent = None
        self.connector = None

    def installed(self):
        self.setServiceParent(self.store)

    def deleted(self):
        if self.parent is not None:
            self.disownServiceParent()

    ### IService
    def setServiceParent(self, parent):
        IServiceCollection(parent).addService(self)
        self.parent = parent

    def disownServiceParent(self):
        IServiceCollection(self.parent).removeService(self)
        self.parent = None

    def privilegedStartService(self):
        if self.config.portNumber < 1024:
            self.connector = self.connect()

    def startService(self):
        if self.connector is None:
            self.connector = self.connect()

    def stopService(self):
        self.connector.disconnect()
        return succeed(None)
