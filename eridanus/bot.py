import shlex, itertools

from zope.interface import implements

from twisted.application.service import IService, IServiceCollection
from twisted.cred.checkers import AllowAnonymousAccess
from twisted.cred.credentials import UsernamePassword
from twisted.cred.portal import Portal
from twisted.internet import reactor, error as ierror
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
from eridanus.plugin import usage, SubCommand
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
    pingTimeoutInterval = 240.0

    pingTimeout = None

    def die(self):
        """
        It's over, reconnect.
        """
        log.msg('PONG not received within %s seconds, asploding.' % (self.pingTimeoutInterval,))
        self.quit('No PING response')
        self.factory.connector.disconnect()


    def cancelTimeout(self):
        if self.pingTimeout is not None:
            try:
                self.pingTimeout.cancel()
            except ierror.AlreadyCalled:
                pass
            self.pingTimeout = None


    def rawPing(self):
        """
        Send a PING to the server.
        """
        # XXX: self.config.hostname is REALLY not great
        self.sendLine('PING ' + self.config.hostname)
        self.cancelTimeout()
        self.pingTimeout = reactor.callLater(self.pingTimeoutInterval, self.die)


    def irc_PONG(self, *args):
        """
        PING response handler for IRCClient.
        """
        self.cancelTimeout()
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


    def maxMessageLength(self):
        # XXX: This should probably take into account the prefix we are about
        # to use or something.
        return 500 - int(self.isupported['NICKLEN'][0]) - int(self.isupported['CHANNELLEN'][0])


    def irc_RPL_BOUNCE(self, prefix, params):
        # 005 is doubly assigned.  Piece of crap dirty trash protocol.
        if params[-1] in self.isupportStrings:
            self.isupport(params[1:-1])
        else:
            self.bounce(params[1])


    def join(self, channel, key=None):
        self.config.addChannel(channel)
        return IRCClient.join(self, encode(channel), key)


    def part(self, channel):
        self.config.removeChannel(channel)
        return IRCClient.part(self, encode(channel))


    def ignore(self, mask):
        return self.config.addIgnore(mask)


    def unignore(self, mask):
        return self.config.removeIgnore(mask)


    def noticed(self, user, channel, message):
        pass


    def broadcastAmbientEvent(self, eventName, source, *args, **kw):
        """
        Broadcast an ambient event to all L{IAmbientEventObserver}s.

        @type  eventName: C{str}
        @param eventName: Event to broadcast, this is assumed to be a callable
            attribute on the L{IAmbientEventObserver}.

        @type source: L{IRCSource}

        @param *args: Additional arguments to pass to the event observer.

        @param *kw: Additional keyword arguments to pass to the event observer.

        @rtype: C{Deferred}
        """
        for obs in plugin.getAmbientEventObservers(self.appStore):
            meth = getattr(obs, eventName, None)
            if meth is not None:
                d = maybeDeferred(meth, source, *args, **kw)
                d.addErrback(self.mentionFailure, source)


    def joined(self, channel):
        source = IRCSource(self, decode(channel), None)
        self.broadcastAmbientEvent('joinedChannel', source)


    def privmsg(self, user, channel, message):
        user = IRCUser(user)
        if self.config.isIgnored(user.usermask):
            return

        source = IRCSource(self, decode(channel), user)
        message = decode(message)

        directedTextSuffixes = (':', ',')
        isDirected = False
        for suffix in directedTextSuffixes:
            directedText = decode(self.nickname.lower()) + suffix
            if message.lower().startswith(directedText):
                isDirected = True
                break

        if isDirected:
            # Remove our nickname from the beginning of the addressed text.
            message = message[len(directedText):].strip()

        if source.isPrivate:
            self.privateMessage(source, message)
        else:
            if isDirected:
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


    def setModes(self):
        for mode in self.config.modes:
            self.mode(self.nickname, True, mode)


    def signedOn(self):
        log.msg('Signed on.')
        self.factory.resetDelay()

        self.setModes()

        self.rawPing()
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
        # XXX: this sucks, having to call the command two different ways is just stupid
        cmd = self.locateBuiltinCommand(params)

        if cmd is not None:
            cmd(source, *params)
        else:
            avatar = self.getAvatar(source.user.nickname)
            cmd = avatar.getCommand(self, params)
            return cmd.invoke(source)


    def mentionFailure(self, f, source, msg=None):
        if msg is not None:
            log.msg(msg)
        log.err(f)
        msg = '%s: %s' % (f.type.__name__, f.getErrorMessage())
        source.say(msg)


    def directedPublicMessage(self, source, message):
        maybeDeferred(self.command, source, message
            ).addErrback(self.mentionFailure, source)

    privateMessage = directedPublicMessage


    def publicMessage(self, source, message):
        self.broadcastAmbientEvent('publicMessageReceived', source, message)


    def getUsername(self, nickname):
        # XXX: maybe check that nickname is sane?
        return u'%s@%s' % (nickname, self.serviceID)


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
            raise errors.AuthenticationError(u'"%s" is not authenticated or has no avatar' % (nickname,))
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


    def diagnosePlugin(self, pluginName):
        """
        Diagnose a broken plugin.

        @type pluginName: C{unicode}
        @param pluginName: Plugin name to diagnose

        @returns: C{twisted.python.failure.Failure} instance from broken
            plugin.
        """
        return plugin.diagnoseBrokenPlugin(pluginName)


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


    def getAvailablePlugins(self, nickname):
        """
        Get an iterable of names of plugins that can still be installed.
        """
        def pluginTypes(it):
            return (type(p) for p in it)

        installedPlugins = set(pluginTypes(plugin.getInstalledPlugins(self.appStore)))
        avatar = self.getAvatar(nickname)
        # XXX: This is a crap way to tell the difference between authenticated
        # users and plebs.  Fix it!
        if hasattr(avatar, 'store'):
            installedPlugins.update(pluginTypes(plugin.getInstalledPlugins(avatar.store)))

        allPlugins = set(plugin.getAllPlugins())
        return (p.pluginName for p in allPlugins - installedPlugins)


    def getBrokenPlugins(self):
        """
        Get an iterable of names of plugins that cannot be installed.
        """
        brokenPlugins = set(plugin.getBrokenPlugins())
        return (p.pluginName for p in brokenPlugins)


    def getCommands(self):
        for name in dir(self):
            if name.startswith('cmd_'):
                yield ICommand(getattr(self, name))


    @usage(u'help <name>')
    def cmd_help(self, source, *params):
        """
        Retrieve help for a given command or plugin.

        Most commands will provide a reasonable description of what it is they
        do and how to use them.  Commands and subcommands can be listed with
        the "list" command.
        """
        params = list(params)
        if not params:
            params = [u'help']

        # XXX: blehblehbleh, locateBuiltinCommand is pure fail
        avatar = self.getAvatar(source.user.nickname)
        cmd = self.locateBuiltinCommand(params)
        if cmd is None:
            cmd = avatar.getCommand(self, params)

        cmd = ICommand(cmd)
        helps = [cmd.help]
        if cmd.usage is not None:
            helps.insert(0, cmd.usage)
        elif isinstance(cmd, plugin.Plugin):
            # XXX: argh, this is so horrible
            # XXX: as soon as multiline responses are implemented this must
            # be the first thing to get fixed
            helps.insert(0, u'\002%s\002' % (cmd.pluginName,))
            msg = u' -- '.join(helps)
            source.reply(msg)
            commands = self.listCommands(avatar, [cmd.name])
            helps = [u'\002%s\002' % (cmd.pluginName,),
                     u', '.join(commands)]

        msg = u' -- '.join(helps)
        source.reply(msg)


    def listCommands(self, avatar, params):
        """
        Retrieve a list of subcommands.
        """
        if params:
            parents = avatar.getAllCommands(self, params)
            commands = itertools.chain(*(p.getCommands() for p in parents))
            plugins = []
        else:
            # List top-level commands and plugins.
            commands = self.getCommands()
            avStore = getattr(avatar, 'store', None)

            # XXX: Can this really not be made any simpler?
            # XXX: Perhaps the solution here is making sure that plugins that
            #      are publically installed cannot be privately installed too.

            # Plugins that are private are marked with a *.  Plugins that are
            # public are not.  Plugins that are both private and public (?) are
            # treated as if there were only public.
            publicPlugins  = set((p.name, p.pluginName)
                                 for p in plugin.getInstalledPlugins(self.appStore))
            if avStore is not None:
                privatePlugins = set((p.name, p.pluginName)
                                     for p in plugin.getInstalledPlugins(avStore))
            else:
                privatePlugins = set()

            plugins = util.collate(itertools.chain(
                ((n, pn) for n, pn in publicPlugins),
                ((n, u'*' + pn) for n, pn in privatePlugins - publicPlugins)))

            plugins = sorted(u'%s (%s)' % (name, u', '.join(pluginNames))
                             for name, pluginNames in plugins.iteritems())

        def commandName(cmd):
            if isinstance(cmd, SubCommand):
                return u'@' + cmd.name
            return cmd.name

        commands = sorted(
            (commandName(cmd)
             for cmd in itertools.ifilter(lambda cmd: not cmd.alias, commands)))

        return commands + plugins


    @usage(u'list [name] [subname] [...]')
    def cmd_list(self, source, *params):
        """
        List commands and sub-commands.

        If no parameters are specified, top-level commands are listed along
        with installed plugins.

        Private plugins are marked with an *, subcommands are marked with an @.
        """
        avatar = self.getAvatar(source.user.nickname)
        commands = self.listCommands(avatar, list(params))
        source.reply(u', '.join(commands))



class IRCBotFactory(ReconnectingClientFactory):
    protocol = IRCBot

    noisy = True

    def __init__(self, service, portal, config):
        self.service = service

        # XXX: should this be here?
        appStore = service.loginSystem.accountByAddress(u'Eridanus', None).avatars.open()
        self.bot = self.protocol(appStore, service.serviceID, self, portal, config)


    @property
    def connector(self):
        return self.service.connector


    def buildProtocol(self, addr=None):
        return self.bot



class IRCBotFactoryFactory(Item):
    schemaVersion = 1

    dummy = integer()

    def getFactory(self, service, portal, config):
        return IRCBotFactory(service, portal, config)



class IRCBotConfig(Item):
    typeName = 'eridanus_ircbotconfig'
    schemaVersion = 5

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

    modes = bytes(doc="""
    A string of user modes to set after successfully connecting to C{hostname}.
    """, default='B')

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
            ignore = util.normalizeMask(ignore)
            if util.hostMatches(mask, ignore):
                return True

        return False


    def addIgnore(self, mask):
        mask = util.normalizeMask(mask)
        if mask not in self.ignores:
            self.ignores = self.ignores + [mask]
            return mask
        return None


    def removeIgnore(self, mask):
        def removeIgnores(mask):
            for ignore in self.ignores:
                normalizedIgnore = util.normalizeMask(ignore)
                if not util.hostMatches(normalizedIgnore, mask):
                    yield ignore

        mask = util.normalizeMask(mask)
        newIgnores = list(removeIgnores(mask))
        diff = set(self.ignores) - set(newIgnores)
        self.ignores = newIgnores
        return list(diff) or None


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
registerAttributeCopyingUpgrader(IRCBotConfig, 4, 5)



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
        pass


    def startService(self):
        if self.connector is None:
            self.connector = self.connect()


    def stopService(self):
        self.disconnect()
        return succeed(None)
