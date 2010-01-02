from twisted.trial import unittest

from eridanus import plugin
from eridanus.ieridanus import IEridanusPluginProvider, IEridanusBrokenPluginProvider
from eridanus.ieridanus import IEridanusPlugin, IEridanusBrokenPlugin


class TestSafePluginImport(unittest.TestCase):
    """
    Tests for the broken plugin system.
    """

    def test_workingPlugin(self):
        """
        Non-broken plugins should be imported fine.
        """
        plugin.safePluginImport(globals(),
                                'eridanus.test.plugin_working.UselessPlugin')
        self.assertEqual('UselessPlugin', UselessPlugin.pluginName)
        self.assertTrue(IEridanusPlugin.implementedBy(UselessPlugin))
        self.assertTrue(IEridanusPluginProvider.providedBy(UselessPlugin))


    def test_brokenPlugin(self):
        """
        Broken plugins should be imported as BrokenPlugins.
        """
        plugin.safePluginImport(globals(),
                                'eridanus.test.plugin_broken.SadPlugin')
        self.assertEqual('SadPlugin', SadPlugin.pluginName)
        self.assertTrue(IEridanusBrokenPlugin.implementedBy(SadPlugin))
        self.assertTrue(IEridanusBrokenPluginProvider.providedBy(SadPlugin))
        self.assertFalse(IEridanusPlugin.implementedBy(SadPlugin))
        self.assertFalse(IEridanusPluginProvider.providedBy(SadPlugin))
        self.assertEqual(ImportError, SadPlugin.failure.type)
        self.assertEqual('No module named gyre_and_gimble_in_the_wabe',
                         SadPlugin.failure.getErrorMessage())
