import re, shlex
from textwrap import dedent

from zope.interface import implements

from axiom.item import Item
from axiom.attributes import integer, inmemory, reference, bytes, AND, text
from axiom.upgrade import registerUpgrader

from twisted.python import log
from twisted.internet import reactor
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet.defer import succeed
from twisted.words.protocols.irc import IRCClient
from twisted.application.service import IService, IServiceCollection

from eridanus import gchart
from eridanus.errors import CommandNotFound
from eridanus.entry import EntryManager
from eridanus.util import encode, decode, extractTitle, truncate, PerseverantDownloader, prettyTimeDelta
from eridanus.tinyurl import tinyurl


paramPattern = re.compile(r'([<[])(\w+)([>\]])')

def formatUsage(s):
    return paramPattern.sub(r'\1\002\2\002\3', s)


def usage(desc):
    def fact(f):
        f.usage = formatUsage(desc)
        f.help = f.__doc__
        return f
    return fact


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
    commentPattern = re.compile(ur'\s+(?:\[(.*)\]|<?--\s+(.*))')

    def __init__(self, config):
        self.config = config
        self.nickname = encode(config.nickname)
        self._entryManagers = dict((em.channel, em) for em in config.getEntryManagers())

    def noticed(self, user, channel, message):
        pass

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
        # XXX:                    _
        # XXX:   _   _ _   _  ___| | __
        # XXX:  | | | | | | |/ __| |/ /
        # XXX:  | |_| | |_| | (__|   <
        # XXX:   \__, |\__,_|\___|_|\_\
        # XXX:   |___/
        params = [decode(p) for p in shlex.split(encode(message))]

        try:
            handler = self.locateCommand(params)
            log.msg('DEBUG: Dispatching handler %r from %s in %s: %r (%s)' % (handler, user.nickname, channel, params, message))
            handler(user, channel, *params)
        except CommandNotFound, cmd:
            self.reply(user, channel, u'No such command: %s' % (cmd,))

    def createEntry(self, (channel, nick, url, comment, title)):
        em = self.getEntryManager(channel)
        return em.createEntry(channel=channel,
                              nick=nick,
                              url=url,
                              comment=comment,
                              title=title)

    def userText(self, user, channel, message):
        match = self.urlPattern.search(message)
        if match is None:
            return

        url = match.group(1)

        comment = self.commentPattern.search(message, match.start())
        if comment is not None:
            comment = filter(None, comment.groups())[0]

        nickname = decode(user.nickname)

        em = self.getEntryManager(channel)
        entry = em.entryByUrl(url)

        def logCreateError(f):
            log.msg('Creating a new entry failed:')
            log.err(f)
            return f

        if entry is None:
            # Only bother fetching the first 4096 bytes of the URL.
            d = PerseverantDownloader(str(url), headers=dict(range='bytes=0-4095')).go(
                ).addCallback(extractTitle).addErrback(lambda e: None
                ).addCallback(lambda title: (decode(channel), nickname, url, comment, title)
                ).addCallback(self.createEntry).addErrback(logCreateError)
        else:
            entry.occurences += 1
            if comment:
                entry.addComment(nickname, comment)
            d = succeed(entry)

        d.addCallback(lambda entry: self.notice(channel, encode(entry.humanReadable)))

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

    def locateCommand(self, params):
        cmd = params.pop(0).lower()
        handler = getattr(self, 'cmd_' + cmd, None)
        if handler is None:
            raise CommandNotFound(cmd)
        return handler

    ### Commands

    def cmd_help(self, user, channel, commandName=None):
        # XXX: implement this???
        if commandName is None:
            return

        handler = self.locateCommand([commandName])
        msg = u''

        if hasattr(handler, 'usage'):
            msg += handler.usage

        if hasattr(handler, 'help'):
            help = dedent(handler.help).splitlines()
            if not help[0]:
                help.pop(0)
            help = ' '.join(help)
            msg += u' -- %s' % (help,)

        if not msg:
            msg = u'No help for %s.' % (commandName,)

        self.reply(user, channel, msg)

    @usage('get <id> [channel]')
    def cmd_get(self, user, channel, eid, entryChannel=None):
        """
        Show entry <id> in [channel] or the current channel if not specified.
        """
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

    @usage('join <channel> [key]')
    def cmd_join(self, user, channel, channelName, key=None):
        """
        Joins <channel> with [key], if provided.
        """
        self.join(encode(channelName), key)

    @usage('part [channel]')
    def cmd_part(self, user, channel, channelName=None):
        """
        Leave [channel] or the current channel if not specified.
        """
        if channelName is None:
            channelName = channel
        self.part(encode(channelName))

    @usage('ignore <nick>')
    def cmd_ignore(self, user, channel, nick):
        """
        Ignore text from <nick>.
        """
        self.config.ignore(nick)

    @usage('stats [channel]')
    def cmd_stats(self, user, channel, channelName=None):
        """
        Show some interesting statistics for [channel] or the current channel
        if not specified.
        """
        if channelName is None:
            channelName = channel

        em = self.getEntryManager(channelName)
        numEntries, numComments, numContributors, timespan = em.stats()
        msg = '%d entries with %d comments from %d contributors over a total time period of %s.' % (numEntries, numComments, numContributors, prettyTimeDelta(timespan))
        self.reply(user, channel, msg)

    @usage('chart [channel]')
    def cmd_chart(self, user, channel, channelName=None):
        """
        Generate a chart of contributors for [channel] or the current channel
        if not specified.
        """
        if channelName is None:
            channelName = channel

        limit = 10

        em = self.getEntryManager(channelName)
        data = sorted(em.topContributors(limit=limit), key=lambda x: x[1])
        labels, data = zip(*data)

        title = 'Top %d URL contributors for %s' % (limit, channelName)
        chart = gchart.Pie(size=(900, 300), data=[data], labels=labels, title=title)

        def gotTiny(url):
            self.reply(user, channel, str(chart.url))

        tinyurl(str(chart.url)).addCallback(gotTiny)

    @usage('info <id> [channel]')
    def cmd_info(self, user, channel, eid, entryChannel=None):
        """
        Show information about entry <id> in [channel] or the current channel
        if not specified.
        """
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
            comments = ['<%s> %s' % (c.nick, c.comment) for c in entry.comments]
            msg = u'#%d: Mentioned \002%d\002 time(s). ' % (entry.eid, entry.occurences)
            if comments:
                msg += '  '.join(comments)
        else:
            msg = u'No such entry with that ID.'

        self.reply(user, channel, msg)

    @usage('find <text> [channel]')
    def cmd_find(self, user, channel, text, entryChannel=None):
        """
        Search for <text> in URLs, titles and comments in [channel] or the
        current channel if not specified.
        """
        if not text:
            self.reply(u'Invalid search criteria.')
            return

        if entryChannel is None:
            entryChannel = channel

        em = self.getEntryManager(entryChannel)
        entries = list(em.search(text))

        if not entries:
            msg = u'No results found for "%s".' % (text,)
        elif len(entries) == 1:
            msg = entries[0].completeHumanReadable
        else:
            msg = u'%d results. ' % (len(entries,))
            msg += '  '.join([u'\002#%d\002: \037%s\037' % (e.eid, truncate(e.displayTitle, 30)) for e in entries])

        self.reply(user, channel, msg)

    @usage('tinyurl <id> [channel]')
    def cmd_tinyurl(self, user, channel, eid, entryChannel=None):
        """
        Generate a TinyURL for entry <id> in [channel] or the current channel
        if not specified.
        """
        try:
            eid = int(eid)
        except ValueError:
            self.reply(user, channel, u'Invalid entry ID.')
            return

        if entryChannel is None:
            entryChannel = channel

        def gotTiny(url):
            self.reply(user, channel, url)

        em = self.getEntryManager(entryChannel)
        entry = em.entryById(eid)

        # XXX: yuck, this kind of code appears everwhere
        if entry is not None:
            tinyurl(entry.url).addCallback(gotTiny)
        else:
            self.reply(u'No such entry with that ID.')

    @usage('discard <id> [channel]')
    def cmd_discard(self, user, channel, eid, entryChannel=None):
        """
        Discards entry <id> in [channel] or the current channel if not
        specified. Discarded items are not considered for searching.
        """
        if user.nickname != 'k4y':
            self.reply(user, channel, u'You are not k4y. Lol.')
            return
        # XXX: this code is duplicated about 6 or 7 times, do something.
        try:
            eid = int(eid)
        except ValueError:
            self.reply(user, channel, u'Invalid entry ID.')
            return

        if entryChannel is None:
            entryChannel = channel

        em = self.getEntryManager(entryChannel)
        entry = em.entryById(eid)

        # XXX: yuck
        if entry is not None:
            entry.discarded = True
        else:
            self.reply(u'No such entry with that ID.')


class IRCBotFactory(ReconnectingClientFactory):
    protocol = IRCBot

    def __init__(self, config):
        self.bot = self.protocol(config)

    def buildProtocol(self, addr=None):
        return self.bot


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
