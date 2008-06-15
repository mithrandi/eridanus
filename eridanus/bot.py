import shlex

from zope.interface import implements

from twisted.application.service import IService, IServiceCollection
from twisted.cred.checkers import AllowAnonymousAccess
from twisted.cred.credentials import UsernamePassword
from twisted.cred.portal import Portal
from twisted.internet import reactor
from twisted.internet.defer import succeed, maybeDeferred, Deferred
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.python import log
from twisted.words.protocols.irc import IRCClient

from axiom import errors as aerrors
from axiom.attributes import (integer, inmemory, reference, bytes, text,
    textlist)
from axiom.dependency import dependsOn
from axiom.item import Item
from axiom.upgrade import registerUpgrader, registerAttributeCopyingUpgrader
from axiom.userbase import LoginSystem

from eridanus import util, errors, plugin
from eridanus.avatar import AnonymousAvatar
from eridanus.irc import IRCSource, IRCUser
from eridanus.ieridanus import ICommand, IIRCAvatar
from eridanus.plugin import usage
from eridanus.util import encode, decode


class _IRCKeepAliveMixin(object):
    """
    Ping an IRC server periodically to determine the connection status.

    If there has been no response before the timeout interval has elapsed,
    C{self.factory.retry} is called in an attempt to reconnect.

    @type pingInterval: C{float}
    @cvar pingInterval: The interval, in seconds, between PING requests

    @type pingTimeoutInterval: C{float}
    @cvar pingTimeoutInterval: The number of seconds to wait for a response
        before attempting to reconnect

    @type pingTimeout: C{IDelayedCall}
    @cvar pingTimeout: The delayed call object that will trigger a reconnect
        unless a response is received
    """
    pingInterval = 120.0
    pingTimeoutInterval = 60.0

    pingTimeout = None

    def die(self):
        """
        It's over, reconnect.
        """
        log.msg('PONG not received within %s seconds, asploding.' % (self.pingTimeoutInterval,))
        self.quit()
        self.factory.retry()

    def rawPing(self):
        """
        Send a PING to the server.
        """
        # XXX: self.config.hostname is REALLY not great
        self.sendLine('PING ' + self.config.hostname)
        self.pingTimeout = reactor.callLater(self.pingTimeoutInterval, self.die)

    def irc_PONG(self, *args):
        """
        PING response handler for IRCClient.
        """
        if self.pingTimeout is not None:
            self.pingTimeout.cancel()

        reactor.callLater(self.pingInterval, self.rawPing)


# XXX: There should probably be a layer of indirection between this
# and the rest of the world.  Behaviour etc. is too muddied up here.
class IRCBot(IRCClient, _IRCKeepAliveMixin):
    isupportStrings = [
        'are available on this server',
        'are supported by this server']

    def __init__(self, appStore, serviceID, factory, portal, config):
        self.serviceID = serviceID
        self.factory = factory
        self.portal = portal
        self.config = config
        self.appStore = appStore
        self.nickname = encode(config.nickname)

        self.topicDeferreds = {}
        self.isupported = {}
        self.authenticatedUsers = {}

    def irc_RPL_BOUNCE(self, prefix, params):
        # 005 is doubly assigned.  Piece of crap dirty trash protocol.
        if params[-1] in self.isupportStrings:
            self.isupport(params[1:-1])
        else:
            c = None

        if metadata is not None:
            entry.updateMetadata(metadata)

        entry.touchEntry()
        return entry, c

    def findUrls(self, text):
        for url, pos in extractURLsWithPosition(text):
            comment = self.commentPattern.match(text, pos)
            if comment is not None:
                comment = filter(None, comment.groups())[0]

            yield url, comment

    def mentionError(self, f, conf):
        log.err(f)
        msg = '%s: %s' % (f.type.__name__, f.value)
        self.reply(conf, msg)

    def getPageData(self, url):
        def buildMetadata(data, headers):
            def getHeader(name):
                h = headers.get(name)
                if h is not None:
                    return decode(h[0])
                return None

            contentType = getHeader('content-type')
            if contentType is not None:
                yield u'contentType', contentType

                if contentType.startswith('image'):
                    try:
                        im = Image.open(StringIO(data))
                        dims = im.size
                    except IOError:
                        dims = None

                    if dims is not None:
                        yield u'dimensions', u'x'.join(map(unicode, dims))

            size = getHeader('content-range')
            if size is not None:
                if size.startswith('bytes'):
                    size = int(size.split(u'/')[-1])
                    yield u'size', humanReadableFileSize(size)

        def decodeTextData(data, encoding):
            def detectEncoding(data):
                info = chardet.detect(data)
                return info.get('encoding', 'ascii')

            if encoding is None:
                encoding = detectEncoding(data)

            try:
                return data.decode(encoding, 'replace')
            except LookupError:
                newEncoding = detectEncoding(data)
                log.msg('Decoding text with %r failed, detected data as %r.' % (encoding, newEncoding))
                return data.decode(newEncoding, 'replace')

        def decodeData(data, contentType, contentEncoding):
            # XXX: this should be done at a lower level, like util.getPage maybe
            if contentEncoding is not None:
                if contentEncoding in ('x-gzip', 'gzip'):
                    data = gzip.GzipFile(fileobj=StringIO(data)).read()
                else:
                    raise ValueError(u'Unsupported content encoding: %r' % (contentEncoding,))

            params = dict(p.lower().strip().split(u'=', 1) for p in contentType.split(u';')[1:] if u'=' in p)
            return decodeTextData(data, params.get('charset'))

        def gotData((data, headers)):
            metadata = dict(buildMetadata(data, headers))

            contentType = metadata.get('contentType', u'application/octet-stream')
            if contentType.startswith(u'text'):
                contentEncoding = headers.get('content-encoding', [None])[0]
                data = decodeData(data, contentType, contentEncoding)
                title = extractTitle(data)
            else:
                title = None

            return succeed((title, metadata))

        return PerseverantDownloader(str(url), headers=dict(range='bytes=0-4095')).go().addCallback(gotData)

    def snarf(self, conf, text):
        def entryCreated(entry):
            self.notice(encode(entry.channel), encode(entry.humanReadable))

        def entryUpdated((entry, comment)):
            self.notice(encode(entry.channel), encode(entry.humanReadable))
            if comment is not None:
                self.notice(encode(entry.channel), encode(comment.humanReadable))

    def join(self, channel, key=None):
        self.config.addChannel(channel)
        return IRCClient.join(encode(channel), key)

    def part(self, channel):
        self.config.removeChannel(channel)
        return IRCClient.part(encode(channel))

    def ignore(self, mask):
        self.config.addIgnore(mask)

    def unignore(self, mask):
        self.config.removeIgnore(mask)

    def noticed(self, user, channel, message):
        pass

    def privmsg(self, user, channel, message):
        user = IRCUser(user)
        if self.config.isIgnored(user.usermask):
            return

        source = IRCSource(self, decode(channel), user)
        message = decode(message)

        isPrivate = channel == self.nickname
        directedText = decode(self.nickname.lower() + ':')
        isDirected = message.lower().startswith(directedText)

        if isDirected:
            # Remove our nickname from the beginning of the addressed text.
            message = message[len(directedText):].strip()

        if isPrivate:
            self.privateMessage(source, message)
        elif isDirected:
            self.directedPublicMessage(source, message)
        else:
            self.publicMessage(source, message)

    def topic(self, channel, topic=None):
        channel = encode(channel)
        if topic is not None:
            topic = encode(topic)

        d = self.topicDeferreds.get(channel)
        if d is None:
            d = self.topicDeferreds[channel] = Deferred()
        IRCClient.topic(self, channel, topic)
        return d

    def topicUpdated(self, user, channel, topic):
        d = self.topicDeferreds.pop(channel, None)
        if d is not None:
            if topic is not None:
                topic = decode(topic)
            d.callback((user, channel, topic))

    def isupport(self, options):
        isupported = self.isupported
        for param in options:
            if '=' in param:
                key, value = param.split('=', 1)
                value = value.split(',')
            else:
                key = param
                value = True
            isupported[key] = value

    def signedOn(self):
        log.msg('Signed on.')

        self.rawPing()
        self.factory.resetDelay()
        channels = self.config.channels
        for channel in channels:
            self.join(encode(channel))

        log.msg('Joined channels: %r' % (channels,))

    # XXX: this method is a bit lame
    def locateBuiltinCommand(self, params):
        """
        Locate a built-in command.
        """
        cmd = params[0]
        method = getattr(self,
                         'cmd_%s' % cmd.lower(),
                         None)

        if method is not None:
            params.pop(0)

        return method

    def locatePlugin(self, name):
        """
        Get a C{IEridanusPlugin} provider by name.
        """
        return plugin.getPluginByName(self.appStore, name)

    def splitMessage(self, message):
        """
        Lexically split C{message}.

        @type message: C{str}

        @return: C{list} of C{unicode}
        """
        return map(decode, shlex.split(encode(message)))

    def command(self, source, message):
        """
        Find and invoke the C{ICommand} provider from C{message}.
        """
        params = self.splitMessage(message)
        cmd = self.locateBuiltinCommand(params)

        if cmd is not None:
            cmd(source, *params)
        else:
            avatar = self.getAvatar(source.user.nickname)
            cmd = avatar.getCommand(self, params)
            return cmd.invoke(source)

    def mentionFailure(self, f, source):
        log.err(f)
        msg = '%s: %s' % (f.type.__name__, f.getErrorMessage())
        source.reply(msg)

    def directedPublicMessage(self, source, message):
        d = maybeDeferred(self.command, source, message
            ).addErrback(self.mentionFailure, source)

    privateMessage = directedPublicMessage

    def publicMessage(self, source, message):
        for obs in plugin.getAmbientEventObservers(self.appStore):
            d = maybeDeferred(obs.publicMessageReceived, source, message
                ).addErrback(self.mentionFailure, source)

    def getUsername(self, nickname):
        # XXX: maybe check that nickname is sane?
        return '%s@%s' % (nickname, self.serviceID)

    def _getAvatar(self, nickname):
        username = self.getUsername(nickname)
        return self.authenticatedUsers.get(username, (None, None))

    def getAvatar(self, nickname):
        avatar, logout = self._getAvatar(nickname)
        if avatar is None:
            avatar = AnonymousAvatar()
        return avatar

    def getAuthenticatedAvatar(self, nickname):
        avatar, logout = self._getAvatar(nickname)
        if avatar is None:
            raise errors.AuthenticationError(u'No avatar available for "%s"' % (nickname,))
        return avatar

    def logout(self, nickname):
        avatar, logout = self._getAvatar(nickname)
        if logout is not None:
            logout()
            return True

        return False

    def login(self, nickname, password):
        username = self.getUsername(nickname)

        def failedLogin(f):
            f.trap(aerrors.UnauthorizedLogin)
            log.msg('Authentication for "%s" failed:' % (username,))
            log.err(f)
            raise errors.AuthenticationError(u'Unable to authenticate "%s"' % (username,))

        def wrapLogout(self, logout):
            def _logout():
                del self.authenticatedUsers[username]
                logout()
            return _logout

        def loginDone((interface, avatar, logout)):
            self.logout(username)
            logout = wrapLogout(self, logout)
            self.authenticatedUsers[username] = (avatar, logout)

        d = self.portal.login(
            UsernamePassword(username, password),
            None,
            IIRCAvatar)

        return d.addCallbacks(loginDone, failedLogin)

    def grantPlugin(self, nickname, pluginName):
        """
        Grant access to a plugin.

        @type nickname: C{unicode} or C{None}
        @param nickname: Nickname to grant access to, or C{None} if global
            access should be granted

        @type pluginName: C{unicode}
        @param pluginName: Plugin name to grant access to
        """
        if nickname is None:
            store = self.appStore
        else:
            store = self.getAuthenticatedAvatar(nickname).store
        plugin.installPlugin(store, pluginName)

    def revokePlugin(self, nickname, pluginName):
        """
        Revoke access to a plugin.

        @type nickname: C{unicode} or C{None}
        @param nickname: Nickname to revoke access from, or C{None} if global
            access should be revoked

        @type pluginName: C{unicode}
        @param pluginName: Plugin name to revoke access to
        """
        if nickname is None:
            store = self.appStore
        else:
            store = self.getAuthenticatedAvatar(nickname).store
        plugin.uninstallPlugin(store, pluginName)

    @usage(u'help <name>')
    def cmd_help(self, source, *params):
        """
        Retrieve help for a given command or plugin.
        """
        params = list(params)
        if params:
            avatar = self.getAvatar(source.user.nickname)
            cmd = avatar.getCommand(self, params)
        else:
            # XXX: kind of a hack
            cmd = ICommand(self.cmd_help)

        helps = [cmd.help]
        if cmd.usage is not None:
            helps.insert(0, cmd.usage)

        msg = u' -- '.join(helps)
        source.reply(msg)

    @usage(u'list <name>')
    def cmd_list(self, source, *params):
        params = list(params)
        if params:
            avatar = self.getAvatar(source.user.nickname)
            cmd = avatar.getCommand(self, params)
            names = type(cmd).__dict__.iterkeys()
        else:
            names = type(self).__dict__.iterkeys()

        # XXX: this won't always work like this, fix plox
        commands = [name[4:] for name in names if name.startswith('cmd_')]
        source.reply(u', '.join(commands))


class IRCBotFactory(ReconnectingClientFactory):
    protocol = IRCBot

    noisy = True

    def __init__(self, service, portal, config):
        # XXX: should this be here?
        appStore = service.loginSystem.accountByAddress(u'Eridanus', None).avatars.open()
        self.bot = self.protocol(appStore, service.serviceID, self, portal, config)

    def buildProtocol(self, addr=None):
        return self.bot


class IRCBotFactoryFactory(Item):
    schemaVersion = 1

    dummy = integer()

    def getFactory(self, service, portal, config):
        return IRCBotFactory(service, portal, config)


class IRCBotConfig(Item):
    typeName = 'eridanus_ircbotconfig'
    schemaVersion = 4

    name = text(doc="""
    The name of the network this config is for.
    """)

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
    A C{list} of channels the bot should join.
    """, default=[])

    ignores = textlist(doc="""
    A C{list} of masks to ignore.
    """, default=[])

    def addChannel(self, channel):
        if channel not in self.channels:
            self.channels = self.channels + [channel]

    def removeChannel(self, channel):
        channels = self.channels
        while channel in channels:
            channels.remove(channel)
        self.channels = channels

    def isIgnored(self, mask):
        mask = util.normalizeMask(mask)
        for ignore in self.ignores:
            if util.hostMatches(ignore, mask):
                return True

        return False

    def addIgnore(self, mask):
        mask = util.normalizeMask(mask)
        if mask not in self.ignores:
            self.ignores = self.ignores + [mask]

    def removeIgnore(self, mask):
        mask = util.normalizeMask(mask)
        ignores = self.ignores
        ignores.remove(mask)
        self.ignores = ignores

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
registerAttributeCopyingUpgrader(IRCBotConfig, 3, 4)


# XXX: technically this has no real ties to IRC anything, so the name sucks
class IRCBotService(Item):
    implements(IService)

    typeName = 'eridanus_ircbotservice'
    schemaVersion = 1

    powerupInterfaces = [IService]

    name = None

    serviceID = bytes(doc="""
    """, allowNone=False)

    config = reference(doc="""
    """)

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

    portal = inmemory(doc="""
    """)

    loginSystem = dependsOn(LoginSystem)

    def connect(self):
        config = self.config
        assert config is not None, 'No configuration data'

        hostname = config.hostname
        port = config.portNumber

        log.msg('Connecting to %s (%s:%s) as %r' % (config.name, hostname, port, config.nickname))
        return reactor.connectTCP(hostname, port, self.factory.getFactory(self, self.portal, config))

    def disconnect(self):
        self.connector.disconnect()

    def activate(self):
        self.parent = None
        self.connector = None
        if self.loginSystem:
            self.portal = Portal(self.loginSystem, [self.loginSystem, AllowAnonymousAccess()])

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
