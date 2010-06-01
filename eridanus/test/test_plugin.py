from twisted.trial import unittest

from eridanus import plugin
from eridanus.ieridanus import IEridanusPluginProvider, IEridanusBrokenPluginProvider
from eridanus.ieridanus import IEridanusPlugin, IEridanusBrokenPlugin


# Make pyflakes happy
UselessPlugin = None
SadPlugin = None


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



class IncrementalArgumentsTests(unittest.TestCase):
    """
    Tests for L{eridanus.plugin.IncrementalArguments}.
    """
    def test_iter(self):
        """
        C{IncrementalArguments} is iterable and produces a result for each word
        in the message.
        """
        args = plugin.IncrementalArguments(u'foo bar baz')
        self.assertEquals(list(args), [u'foo', u'bar', 'baz'])
        self.assertEquals(args.tail, u'')


    def test_incrementalSplit(self):
        """
        C{IncrementalArguments.next} produces the next word in the message and
        leaves the remainder of the message intact. Phrases in quotes are
        treated as a single word.
        """
        args = plugin.IncrementalArguments(u'foo bar baz')
        self.assertEquals(args.next(), u'foo')
        self.assertEquals(args.tail, u'bar baz')

        args = plugin.IncrementalArguments(u'"foo bar" baz')
        self.assertEquals(args.next(), u'foo bar')
        self.assertEquals(args.tail, u'baz')


    def test_quoting(self):
        """
        Quote characters (C{"} and C{'}) can be escaped with C{\} when they
        appear inside quote characters. Outside of quote characters C{\} has no
        no special meaning.
        """
        expected = [
            (u'"foo"', [u'foo']),
            (u"'foo'", [u'foo']),
            (u'foo "bar baz"', [u'foo', u'bar baz']),
            (u'foo "bar \\"quux\\" baz"', [u'foo', u'bar "quux" baz']),
            (u"foo 'bar \\'quux\\' baz'", [u'foo', u"bar 'quux' baz"]),
            (u"foo \\'bar baz\\'", [u'foo', u"\\'bar", u"baz\\'"])]

        for input, output in expected:
            args = plugin.IncrementalArguments(input)
            self.assertEquals(list(args), output)


    def test_copy(self):
        """
        C{IncrementalArguments.copy} produces a copy of a
        C{IncrementalArguments} instance that can be manipulated separately
        from the original.
        """
        args = plugin.IncrementalArguments(u'foo bar baz')
        argscopy = args.copy()
        list(args)
        self.assertEquals(list(args), [])
        self.assertEquals(list(argscopy), [u'foo', u'bar', u'baz'])


    def test_repr(self):
        """
        C{IncrementalArguments.__repr__} produces useful and accurate
        human-readable text.
        """
        args = plugin.IncrementalArguments(u'foo "bar" baz')
        self.assertEquals(
            repr(args),
            "<IncrementalArguments tail=u'foo \"bar\" baz'>")

        args.next()
        self.assertEquals(
            repr(args),
            "<IncrementalArguments tail=u'\"bar\" baz'>")
