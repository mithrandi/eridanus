from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus import util as eutil
from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage, SubCommand


class APICommand(SubCommand):
    """
    Manage API keys.
    """
    name = u'api'

    @usage(u'get <apiName>')
    def cmd_get(self, source, apiName):
        """
        Get the API key for <apiName>.
        """
        apiKey = eutil.getAPIKey(self.parent.store, apiName)
        source.reply(apiKey)

    @usage(u'set <apiName> <key>')
    def cmd_set(self, source, apiName, key):
        """
        Set the API key for <apiName>.
        """
        apiKey = eutil.setAPIKey(self.parent.store, apiName, key)
        source.reply(u'Set key for "%s".' % (apiName,))


class AdminPlugin(Item, Plugin):
    """
    Provides access to various admin functions.

    Which includes things such as installing/uninstalling plugins,
    joining/leaving channels and ignoring users.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_admin'

    name = u'admin'
    pluginName = u'Admin'

    dummy = integer()

    cmd_api = APICommand()

    @usage(u'install <pluginName>')
    def cmd_install(self, source, pluginName):
        """
        Globally install a plugin.
        """
        source.protocol.grantPlugin(None, pluginName)
        source.reply(u'Installed plugin "%s".' % (pluginName,))

    @usage(u'uninstall <pluginName>')
    def cmd_uninstall(self, source, pluginName):
        """
        Uninstall a globally installed plugin.
        """
        if pluginName == self.pluginName:
            msg = u'Can\'t uninstall "%s".' % (pluginName,)
        else:
            source.protocol.revokePlugin(None, pluginName)
            msg = u'Uninstalled plugin "%s".' % (pluginName,)
        source.reply(msg)

    @usage(u'grant <nickname> <pluginName>')
    def cmd_grant(self, source, nickname, pluginName):
        """
        Grant an authenticated <nickname> access to <pluginName>.
        """
        source.protocol.grantPlugin(nickname, pluginName)
        source.reply(u'Granted "%s" with access to "%s".' % (nickname, pluginName))

    @usage(u'revoke <nickname> <pluginName>')
    def cmd_revoke(self, source, nickname, pluginName):
        """
        Revoke <nickname>'s access to <pluginName>.
        """
        source.protocol.revokePlugin(nickname, pluginName)
        source.reply(u'Revoked access to "%s" from "%s".' % (pluginName, nickname))

    @usage(u'join <channel>')
    def cmd_join(self, source, name):
        """
        Join <channel>.
        """
        source.join(name)

    @usage(u'part [channel]')
    def cmd_part(self, source, name=None):
        """
        Part the current channel or <channel>.
        """
        source.part(name)

    @usage(u'ignores')
    def cmd_ignores(self, source):
        """
        Show the current ignore list.
        """
        # XXX: HACK: abstract this away
        ignores = source.protocol.config.ignores
        if ignores:
            msg = u', '.join(ignores)
        else:
            msg = u'Ignore list is empty.'
        source.reply(msg)

    @usage(u'ignore <usermask>')
    def cmd_ignore(self, source, usermask):
        """
        Ignore input from users matching <usermask>.

        If <usermask> is a partial mask then it will be normalized. e.g.
        "bob" becomes "bob!*@*".
        """
        mask = source.ignore(usermask)
        if mask is not None:
            msg = u'Ignoring "%s".' % (mask,)
        else:
            msg = u'Already ignoring "%s".' % (usermask,)
        source.reply(msg)

    @usage(u'unignore <usermask>')
    def cmd_unignore(self, source, usermask):
        """
        Stop ignoring input from <usermask>.

        If <usermask> is a partial mask then it will be normalized. e.g.
        "bob" becomes "bob!*@*".
        """
        removedIgnores = source.unignore(usermask)
        if removedIgnores is not None:
            msg = u'Stopped ignoring: ' + u', '.join(removedIgnores)
        else:
            msg = u'No ignores matched "%s".' % (usermask,)
        source.reply(msg)

    @usage(u'plugins')
    def cmd_plugins(self, source):
        """
        List plugins available to install.

        Not all plugins should be installed with the `install` command, plugins
        that end with the word `Admin` should be granted (`admin grant`) to a
        particular user instead of installed for the whole world.
        """
        msg = u', '.join(sorted(source.protocol.getAvailablePlugins(source.user.nickname)))
        if not msg:
            msg = u'No available plugins'
        source.reply(msg)
