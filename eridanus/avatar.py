from axiom.attributes import integer
from axiom.item import Item
from eridanus import errors, plugin
from eridanus.ieridanus import IIRCAvatar
from eridanus.plugin import getPluginByName
from zope.interface import implements



class _AvatarMixin(object):
    """
    A simple mixin to handle common avatar functions.
    """
    implements(IIRCAvatar)

    def locateCommand(self, plugin, args):
        cmd = plugin
        while args.tail:
            cmd, args = cmd.locateCommand(args)
        return cmd


    def getAllCommands(self, args):
        pluginName = args.next()
        cmd = getattr(self, 'cmd_' + pluginName, None)
        if cmd is not None:
            yield self.locateCommand(plugin.ICommand(cmd), args.copy())
        else:
            for p in self.locatePlugins(pluginName):
                yield self.locateCommand(p, args.copy())


    @plugin.rest
    @plugin.usage(u'help <name>')
    def cmd_help(self, source, name):
        """
        Retrieve help for a given command or plugin.

        Most commands will provide a reasonable description of what it is they
        do and how to use them.  Commands and subcommands can be listed with
        the "list" command.
        """
        if not name:
            name = u'help'
        args = plugin.IncrementalArguments(name)
        cmd = source.avatar.getCommand(args)
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
            commands = plugin.listCommands(source.avatar, cmd.name)
            helps = [u'\002%s\002' % (cmd.pluginName,),
                     u', '.join(commands)]

        msg = u' -- '.join(helps)
        source.reply(msg)


    @plugin.rest
    @plugin.usage(u'list [name]')
    def cmd_list(self, source, name):
        """
        List commands and sub-commands.

        If no parameters are specified, top-level commands are listed along
        with installed plugins.

        Private plugins are marked with an *, subcommands are marked with an @.
        """
        commands = plugin.listCommands(source.avatar, name)
        source.reply(u', '.join(commands))


    @plugin.usage(u'crash')
    def cmd_crash(self):
        1 / 0



class AnonymousAvatar(_AvatarMixin):
    """
    The avatar given to unauthenticated users.
    """
    def locatePlugins(self, name):
        yield plugin.getPluginByName(self.appStore, name)


    def getCommand(self, args):
        pluginName = args.next()
        cmd = getattr(self, 'cmd_' + pluginName, None)
        if cmd is not None:
            return self.locateCommand(plugin.ICommand(cmd), args.copy())
        else:
            p = self.locatePlugins(pluginName).next()
            return self.locateCommand(p, args)



class AuthenticatedAvatar(Item, _AvatarMixin):
    """
    The avatar used for authenticated users.

    The primary difference between this avatar and L{AnonymousAvatar} is the
    user-store plugin searching.  If a plugin cannot be found in the user-store
    then the regular plugin location method is used.  This allows plugins to be
    endowed on a single user, useful for things like a GodOfTheBot plugin that
    you probably don't want the rest of the world being able to use.
    """
    typeName = 'eridanus_avatar_authenticatedavatar'
    powerupInterfaces = [IIRCAvatar]

    dummy = integer()

    def locatePlugins(self, protocol, name):
        def _plugins():
            try:
                yield getPluginByName(self.store, name)
            except errors.PluginNotInstalled:
                pass
            try:
                yield protocol.locatePlugin(name)
            except errors.PluginNotInstalled:
                pass

        plugins = list(_plugins())
        if not plugins:
            raise errors.PluginNotInstalled(name)

        return plugins


    def getCommand(self, protocol, args):
        pluginName = args.next()
        plugins = list(self.locatePlugins(protocol, pluginName))

        while plugins:
            try:
                plugin = plugins.pop()
                return self.locateCommand(plugin, args.copy())
            except errors.UsageError:
                # XXX: this isn't great
                if not plugins:
                    raise
