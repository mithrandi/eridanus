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

    def locateCommand(self, plugin, params):
        cmd = plugin
        while params:
            cmd, params = cmd.locateCommand(params)

        return cmd


class AnonymousAvatar(_AvatarMixin):
    """
    The avatar given to unauthenticated users.
    """
    def locatePlugins(self, protocol, name):
        yield protocol.locatePlugin(name)

    def getCommand(self, protocol, params):
        plugin = self.locatePlugins(protocol, params.pop(0)).next()
        return self.locateCommand(plugin, params)


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
    schemaVersion = 1

    dummy = integer()

    def locatePlugins(self, protocol, name):
        try:
            yield getPluginByName(self.store, name)
        except errors.PluginNotInstalled:
            pass
        try:
            yield protocol.locatePlugin(name)
        except errors.PluginNotInstalled:
            pass

    def getCommand(self, protocol, params):
        plugins = list(self.locatePlugins(protocol, params.pop(0)))

        while plugins:
            plugin = plugins.pop(0)
            try:
                return self.locateCommand(plugin, params[:])
            except:
                if not plugins:
                    # If there is no chance that this could work in some other
                    # plugin, then we let the exception go into the wild.
                    raise
