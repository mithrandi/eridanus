from twisted.trial.unittest import TestCase

from axiom.store import Store

from eridanus import errors, plugin
from eridanus.ieridanus import ICommand
from eridanus.avatar import _AvatarMixin
from eridanus.plugin import (IncrementalArguments, getPluginByName,
    installPlugin)

from eridanus.test import plugin_known



class MockAvatar(_AvatarMixin):
    """
    Mock avatar object.

    @type plugins: C{dict} mapping C{unicode} to C{IEridanusPlugin}
    @ivar plugins: Mapping of plugin names to plugin instances, used for plugin
        location.
    """
    def locatePlugins(self, protocol, name):
        yield protocol.locatePlugin(name)


    def getCommand(self, protocol, args):
        pluginName = args.next()
        p = self.locatePlugins(protocol, pluginName).next()
        return self.locateCommand(p, args)



class AvatarTests(TestCase):
    """
    Tests for L{eridanus.avatar}.
    """
    def setUp(self):
        self.store = Store()
        self.patch(plugin, 'getPlugins', self.getPlugins)
        installPlugin(self.store, u'Known')
        self.avatar = MockAvatar()


    def getPlugins(self, this, that):
        """
        Monkey patched version of C{twisted.plugin.getPlugins}.
        """
        yield plugin_known.Known


    def locatePlugin(self, name):
        """
        Locate a plugin by name.
        """
        return getPluginByName(self.store, name)


    def test_getCommand(self):
        """
        Getting a known command from a known plugin returns something that
        provides L{ICommand}.
        """
        cmd = self.avatar.getCommand(
            self, IncrementalArguments('known test a b'))
        self.assertTrue(ICommand.providedBy(cmd))


    def test_getUnknownPlugin(self):
        """
        Getting an unknown plugin raises L{errors.PluginNotInstalled}.
        """
        self.assertRaises(errors.PluginNotInstalled,
            self.avatar.getCommand,
            self, IncrementalArguments('chuck test a b'))


    def test_getUnknownCommand(self):
        """
        Getting an unknown command from a known plugin raises
        L{errors.UsageError}.
        """
        self.assertRaises(errors.UsageError,
            self.avatar.getCommand,
            self, IncrementalArguments('known hackthegibson a b'))
