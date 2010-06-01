from zope.interface import implements

from axiom.attributes import integer
from axiom.item import Item

from eridanus import errors
from eridanus.plugin import getPluginByName
from eridanus.ieridanus import IIRCAvatar


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


    def getAllCommands(self, protocol, args):
        pluginName = args.next()
        for plugin in self.locatePlugins(protocol, pluginName):
            yield self.locateCommand(plugin, args.copy())


class AnonymousAvatar(_AvatarMixin):
    """
    The avatar given to unauthenticated users.
    """
    def locatePlugins(self, protocol, name):
        yield protocol.locatePlugin(name)


    def getCommand(self, protocol, args):
        pluginName = args.next()
        plugin = self.locatePlugins(protocol, pluginName).next()
        return self.locateCommand(plugin, args)



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
