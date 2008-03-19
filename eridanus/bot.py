import re, shlex
from itertools import izip
from textwrap import dedent

from epsilon.extime import Time

from zope.interface import implements

from axiom.item import Item
from axiom.attributes import integer, inmemory, reference, bytes, AND, text, timestamp, textlist
from axiom.upgrade import registerUpgrader

from twisted.python import log
from twisted.internet import reactor, error as ineterror
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet.defer import succeed
from twisted.words.protocols.irc import IRCClient
from twisted.application.service import IService, IServiceCollection

from eridanus import gchart, const
from eridanus.errors import CommandError, InvalidEntry, CommandNotFound, ParameterError
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


class UserConfig(Item):
    typeName = 'eridanus_userconfig'
    schemaVersion = 1

    user = inmemory(doc="""
    An L{IRCUser} instance.
    """)

    created = timestamp(defaultFactory=lambda: Time(), doc=u"""
    Timestamp of when this comment was created.
    """)

    nickname = text(doc="""
    Nickname this configuration is bound to.
    """, allowNone=False)

    channel = text(doc="""
    Channel this configuration is bound to.
    """, allowNone=False)

    @property
    def displayCreated(self):
        return self.created.asHumanly(tzinfo=const.timezone)


class IRCUser(object):
    def __init__(self, user):
        super(IRCUser, self).__init__()
        if '!' in user:
            nickname, realname = user.split('!', 1)
            realname, host = realname.split('@', 1)
        else:
            nickname = realname = None
            host = user

        self.nickname = nickname
        self.realname = realname
        self.host = host


class _KeepAliveMixin(object):
    pingInterval = 120.0
    pingTimeoutInterval = 60.0

    pingTimeout = None

    def die(self):
        log.msg('PONG not received within %s seconds, asploding.' % (self.pingTimeoutInterval,))
        self.quit()
        self.factory.retry()

    def rawPing(self):
        self.sendLine('PING ' + self.config.hostname)
        self.pingTimeout = reactor.callLater(self.pingTimeoutInterval, self.die)

    def irc_PONG(self, *args):
        if self.pingTimeout is not None:
            self.pingTimeout.cancel()

        reactor.callLater(self.pingInterval, self.rawPing)


class IRCBot(IRCClient, _KeepAliveMixin):
    urlPattern = re.compile(ur'((?:(?:(?:https?|ftp):\/\/)|www\.)(?:(?:[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)|localhost|(?:[a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(?:com|net|org|info|biz|gov|name|edu|[a-zA-Z][a-zA-Z]))(?::[0-9]+)?(?:(?:\/|\?)[^ "]*[^ ,;\.:">])?/?)')
    commentPattern = re.compile(ur'\s+(?:\[(.*)\]|<?--\s+(.*))')

    def __init__(self, factory, config):
        self.factory = factory
        self.config = config
        # XXX
        self.store = config.store
        self.nickname = encode(config.nickname)
        self._entryManagers = dict((em.channel, em) for em in config.getEntryManagers())
        self.userConfigs = {}

    def noticed(self, user, channel, message):
        pass

    def signedOn(self):
        log.msg('Signed on.')
        self.rawPing()
        self.factory.resetDelay()
        for channel in self.config.channels:
            self.join(encode(channel))

    def userRenamed(self, old, new):
        userConfigs = self.userConfigs

        if old in userConfigs:
            userConfigs[new] = userConfigs.pop(old)

    def getEntryManager(self, channel):
        em = self._entryManagers.get(channel)
        if em is None:
            em = self._entryManagers[channel] = self.config.createEntryManager(channel)
        return em

    def reply(self, conf, message):
        message = u'%s: %s' % (conf.user.nickname, message)
        self.say(encode(conf.channel), encode(message))

    def directedUserText(self, conf, message):
        # XXX:                    _
        # XXX:   _   _ _   _  ___| | __
        # XXX:  | | | | | | |/ __| |/ /
        # XXX:  | |_| | |_| | (__|   <
        # XXX:   \__, |\__,_|\___|_|\_\
        # XXX:   |___/
        params = [decode(p) for p in shlex.split(encode(message))]

        try:
            handler = self.locateCommand(params)
            log.msg('DEBUG: Dispatching handler %r from %s in %s: %r (%s)' % (handler, conf.user.nickname, conf.channel, params, message))
            handler(conf, *params)
        except CommandError, e:
            self.reply(conf, u'%s: %s' % (e.__class__.__name__, e))

    def createEntry(self, (channel, nick, url, comment, title)):
        em = self.getEntryManager(channel)
        return em.createEntry(channel=channel,
                              nick=nick,
                              url=url,
                              comment=comment,
                              title=title)

    def snarfUrl(self, text):
        match = self.urlPattern.search(text)
        if match is None:
            return None

        url = match.group(1)

        comment = self.commentPattern.search(text, match.start())
        if comment is not None:
            comment = filter(None, comment.groups())[0]

        return url, comment, text[match.end():]

    def findUrls(self, text):
        while True:
            result = self.snarfUrl(text)
            if result is None:
                break
            url, comment, text = result
            yield url, comment

    def snarf(self, conf, text):
        def brokenUrl(f):
            log.msg('Error getting page data: %r' % (text,))
            log.err(f)
            return None

        def logCreateError(f):
            log.msg('Creating a new entry failed:')
            log.err(f)
            return f

        def spewParams(channel, nickname, url, comment):
            return lambda title: (channel, nickname, url, comment, title)

        def noticeEntry(entry):
            self.notice(encode(entry.channel), encode(entry.humanReadable))

        def noticeEntryUpdate((entry, comment)):
            noticeEntry(entry)
            if comment is not None:
                self.notice(encode(entry.channel), encode(comment.humanReadable))

        em = self.getEntryManager(conf.channel)
        nickname = conf.nickname

        for url, comment in self.findUrls(text):
            entry = em.entryByUrl(url)
            if entry is None:
                # Only bother fetching the first 4096 bytes of the URL.
                PerseverantDownloader(str(url), headers=dict(range='bytes=0-4095')).go(
                    ).addErrback(brokenUrl
                    ).addCallback(extractTitle
                    ).addCallback(spewParams(conf.channel, nickname, url, comment)
                    ).addCallback(self.createEntry).addErrback(logCreateError
                    ).addCallback(noticeEntry)
            else:
                entry.occurences += 1
                c = None
                if comment:
                    c = entry.addComment(nickname, comment)
                succeed((entry, c)).addCallback(noticeEntryUpdate)

    def userText(self, conf, message):
        self.snarf(conf, message)

    def privmsg(self, user, channel, message):
        user = IRCUser(user)
        if channel == self.nickname or decode(user.nickname) in self.config.ignores:
            return

        # XXX: this completely fails for private messages
        # XXX: FAIL FAIL FAIL
        conf = self.store.findOrCreate(UserConfig, nickname=decode(user.nickname), channel=decode(channel))
        conf.user = user

        message = decode(message)

        private = channel == self.nickname
        directedText = self.nickname.lower() + u':'
        directed = message.lower().startswith(directedText)

        if directed or private:
            if directed:
                message = message[len(directedText):].strip()
            self.directedUserText(conf, message)
        else:
            self.userText(conf, message)

    def locateCommand(self, params):
        cmd = params.pop(0).lower()
        handler = getattr(self, 'cmd_' + cmd, None)
        if handler is None:
            raise CommandNotFound(cmd)
        return handler

    def getEntry(self, channel, eid):
        if eid.startswith('#'):
            eid = eid[1:]

        try:
            eid = int(eid)
        except ValueError:
            raise InvalidEntry('Invalid entry ID')

        em = self.getEntryManager(channel)
        entry = em.entryById(eid)
        if entry is None:
            raise InvalidEntry('Entry #%d does not exist' % (eid,))

        return em, entry

    ### Commands

    @usage('help [command]')
    def cmd_help(self, conf, commandName=None):
        """
        Display help for [command] or a list of commands if not specified.
        """
        if commandName is None:
            commands = [name[4:] for name in sorted(self.__class__.__dict__.iterkeys()) if name.startswith('cmd_')]
            msg = u', '.join(commands)
        else:
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

        self.reply(conf, msg)

    @usage('get <id> [channel]')
    def cmd_get(self, conf, eid, entryChannel=None):
        """
        Show entry <id> in [channel] or the current channel if not specified.
        """
        em, entry = self.getEntry(entryChannel or conf.channel, eid)
        self.reply(conf, entry.completeHumanReadable)

    @usage('join <channel> [key]')
    def cmd_join(self, conf, channelName, key=None):
        """
        Joins <channel> with [key], if provided.
        """
        self.join(encode(channelName), key)

    @usage('part [channel]')
    def cmd_part(self, conf, channelName=None):
        """
        Leave [channel] or the current channel if not specified.
        """
        self.part(encode(channelName or conf.channel))

    @usage('ignore <nick>')
    def cmd_ignore(self, conf, nick):
        """
        Ignore text from <nick>.
        """
        # XXX: check privs
        self.config.ignore(nick)

    @usage('stats [channel]')
    def cmd_stats(self, conf, channelName=None):
        """
        Show some interesting statistics for [channel] or the current channel
        if not specified.
        """
        em = self.getEntryManager(channelName or conf.channel)
        numEntries, numComments, numContributors, timespan = em.stats()
        msg = '%d entries with %d comments from %d contributors over a total time period of %s.' % (numEntries, numComments, numContributors, prettyTimeDelta(timespan))
        self.reply(conf, msg)

    @usage('chart [channel]')
    def cmd_chart(self, conf, channelName=None):
        """
        Generate a chart of contributors for [channel] or the current channel
        if not specified.
        """
        limit = 10

        channel = channelName or conf.channel

        em = self.getEntryManager(channel)
        data = sorted(em.topContributors(limit=limit), key=lambda x: x[1])

        labels, data = zip(*data)
        labels = [u'%s (%d)' % (l, d) for l, d in izip(labels, data)]

        title = 'Top %d URL contributors for %s' % (limit, channel)
        chart = gchart.Pie(size=(900, 300), data=[data], labels=labels, title=title)

        def gotTiny(url):
            self.reply(conf, str(url))

        tinyurl(str(chart.url)).addCallback(gotTiny)

    @usage('info <id> [channel]')
    def cmd_info(self, conf, eid, entryChannel=None):
        """
        Show information about entry <id> in [channel] or the current channel
        if not specified.
        """
        em, entry = self.getEntry(entryChannel or conf.channel, eid)
        comments = ['<%s> %s' % (c.nick, c.comment) for c in entry.comments]
        msg = u'#%d: Mentioned \002%d\002 time(s). ' % (entry.eid, entry.occurences)
        if comments:
            msg = msg + '  '.join(comments)

        self.reply(conf, msg)

    # XXX: the channel argument can no longer be supported without kwargs now.
    # XXX: FIXME
    @usage('find <term> [term ...]')
    def cmd_find(self, conf, *terms):
        """
        Search entries for which every <term> matches the URL or title or
        any comment.
        """
        if not terms:
            raise ParameterError(u'Invalid search criteria.')

        em = self.getEntryManager(conf.channel)
        entries = list(em.search(terms))

        if not entries:
            msg = u'No results found for: %s.' % (u'; '.join(terms),)
        elif len(entries) == 1:
            msg = entries[0].completeHumanReadable
        else:
            msg = u'%d results. ' % (len(entries,))
            msg += '  '.join([u'\002#%d\002: \037%s\037' % (e.eid, truncate(e.displayTitle, 30)) for e in entries])

        self.reply(conf, msg)

    @usage('tinyurl <id> [channel]')
    def cmd_tinyurl(self, conf, eid, entryChannel=None):
        """
        Generate a TinyURL for entry <id> in [channel] or the current channel
        if not specified.
        """
        em, entry = self.getEntry(entryChannel or conf.channel, eid)

        def gotTiny(url):
            self.reply(conf, url)

        tinyurl(entry.url).addCallback(gotTiny)

    @usage('discard <id> [channel]')
    def cmd_discard(self, conf, eid, entryChannel=None):
        """
        Discards entry <id> in [channel] or the current channel if not
        specified. Discarded items are not considered for searching.
        """
        em, entry = self.getEntry(entryChannel or conf.channel, eid)

        # XXX: implement proper privs
        if entry.nick == conf.user.nickname or conf.user.nickname == u'k4y':
            entry.discarded = True
        else:
            self.reply(conf, u'You did not post this entry, ask %s to discard it.' % (entry.nick,))


class IRCBotFactory(ReconnectingClientFactory):
    protocol = IRCBot

    noisy = True

    def __init__(self, service, config):
        self.service = service
        self.bot = self.protocol(self, config)

    def buildProtocol(self, addr=None):
        # XXX: haev sum hax
        self.connector = self.service.connector
        return self.bot


class IRCBotFactoryFactory(Item):
    schemaVersion = 1

    dummy = integer()

    def getFactory(self, service, config):
        return IRCBotFactory(service, config)


class IRCBotConfig(Item):
    typeName = 'eridanus_ircbotconfig'
    schemaVersion = 3

    hostname = bytes(doc="""
    The hostname of the IRC server to connect to.
    """)

    portNumber = integer(doc="""
    The port to connect to the IRC server on.
    """)

    nickname = text(doc="""
    The bot's nickname.
    """)

    channels = textlist(doc="""
    Channels the bot should monitor.
    """, default=[])

    ignores = textlist(default=[])

    def join(self, channel):
        self.channels.append(channel)

    def ignore(self, nick):
        self.ignores.append(nick)

    def getEntryManagers(self):
        return self.store.query(EntryManager, EntryManager.config == self)

    def getEntryManager(self, channel):
        return self.store.findFirst(EntryManager,
                                    AND(EntryManager.config == self,
                                        EntryManager.channel == channel))

    def createEntryManager(self, channel):
        return self.store.findOrCreate(EntryManager, config=self, channel=channel)

def ircbotconfig1to2(old):
    return old.upgradeVersion(
        IRCBotConfig.typeName, 1, 2,
        hostname=old.hostname,
        portNumber=old.portNumber,
        nickname=old.nickname.decode('utf-8'),
        _channels=old._channels.decode('utf-8'),
        _ignores=old._ignores.decode('utf-8'))

registerUpgrader(ircbotconfig1to2, IRCBotConfig.typeName, 1, 2)

def ircbotconfig2to3(old):
    return old.upgradeVersion(
        IRCBotConfig.typeName, 2, 3,
        hostname=old.hostname,
        portNumber=old.portNumber,
        nickname=old.nickname,
        channels=old._channels.split(u','),
        ignores=old._ignores.split(u','))

registerUpgrader(ircbotconfig2to3, IRCBotConfig.typeName, 2, 3)


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
        return reactor.connectTCP(self.config.hostname, self.config.portNumber, self.factory.getFactory(self, self.config))

    def disconnect(self):
        self.connector.disconnect()

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
        self.disconnect()
        return succeed(None)
