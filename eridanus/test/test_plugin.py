from twisted.trial import unittest

from eridanus import errors
from eridanus.ieridanus import (ICommand, IEridanusPluginProvider,
    IEridanusPlugin, IAmbientEventObserver, IEridanusBrokenPlugin,
    IEridanusBrokenPluginProvider)
from eridanus.plugin import (safePluginImport, MethodCommand, rest,
    IncrementalArguments)


# Make pyflakes happy
UselessPlugin = None
SadPlugin = None


class SafePluginImportTests(unittest.TestCase):
    """
    Tests for the broken plugin system.
    """
    def test_workingPlugin(self):
        """
        Non-broken plugins should be imported fine.
        """
        safePluginImport(
            globals(), 'eridanus.test.plugin_working.UselessPlugin')
        self.assertEquals('UselessPlugin', UselessPlugin.pluginName)
        self.assertTrue(IEridanusPlugin.implementedBy(UselessPlugin))
        self.assertTrue(IEridanusPluginProvider.providedBy(UselessPlugin))


    def test_brokenPlugin(self):
        """
        Broken plugins should be imported as BrokenPlugins.
        """
        safePluginImport(globals(), 'eridanus.test.plugin_broken.SadPlugin')
        self.assertEquals('SadPlugin', SadPlugin.pluginName)
        self.assertTrue(IEridanusBrokenPlugin.implementedBy(SadPlugin))
        self.assertTrue(IEridanusBrokenPluginProvider.providedBy(SadPlugin))
        self.assertFalse(IEridanusPlugin.implementedBy(SadPlugin))
        self.assertFalse(IEridanusPluginProvider.providedBy(SadPlugin))
        self.assertEquals(ImportError, SadPlugin.failure.type)
        self.assertEquals(
            'No module named gyre_and_gimble_in_the_wabe',
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
        args = IncrementalArguments(u'foo bar baz')
        self.assertEquals(list(args), [u'foo', u'bar', 'baz'])
        self.assertEquals(args.tail, u'')


    def test_incrementalSplit(self):
        """
        C{IncrementalArguments.next} produces the next word in the message and
        leaves the remainder of the message intact. Phrases in quotes are
        treated as a single word.
        """
        args = IncrementalArguments(u'foo bar baz')
        self.assertEquals(args.next(), u'foo')
        self.assertEquals(args.tail, u'bar baz')

        args = IncrementalArguments(u'"foo bar" baz')
        self.assertEquals(args.next(), u'foo bar')
        self.assertEquals(args.tail, u'baz')


    def test_quoting(self):
        """
        The quote character (C{"} can be escaped with C{\} when it appears
        inside quote characters. Outside of quote characters C{\} has no no
        special meaning.
        """
        expected = [
            (u'"foo"', [u'foo']),
            (u"you're", [u"you're"]),
            (u'foo "bar baz"', [u'foo', u'bar baz']),
            (u'foo "bar \\"quux\\" baz"', [u'foo', u'bar "quux" baz']),
            (u'foo \\ bar', [u'foo', u'\\', u'bar'])]

        for input, output in expected:
            args = IncrementalArguments(input)
            self.assertEquals(list(args), output)


    def test_copy(self):
        """
        C{IncrementalArguments.copy} produces a copy of a
        C{IncrementalArguments} instance that can be manipulated separately
        from the original.
        """
        args = IncrementalArguments(u'foo bar baz')
        argscopy = args.copy()
        list(args)
        self.assertEquals(list(args), [])
        self.assertEquals(list(argscopy), [u'foo', u'bar', u'baz'])


    def test_repr(self):
        """
        C{IncrementalArguments.__repr__} produces useful and accurate
        human-readable text.
        """
        args = IncrementalArguments(u'foo "bar" baz')
        self.assertEquals(
            repr(args),
            "<IncrementalArguments tail=u'foo \"bar\" baz'>")

        args.next()
        self.assertEquals(
            repr(args),
            "<IncrementalArguments tail=u'\"bar\" baz'>")


    def test_rest(self):
        """
        L{eridanus.plugin.rest} decorates a function such that it will consume
        all arguments in a single parameter.
        """
        class LookAPlugin(object):
            @plugin.rest
            def cmd_test(self, source, foo, bar, rest):
                return [foo, bar, rest]

        aplugin = LookAPlugin()
        args = plugin.IncrementalArguments(u'foo bar baz quux oatmeal')
        cmd = ieridanus.ICommand(aplugin.cmd_test)
        cmd.locateCommand(args)
        self.assertEquals(
            cmd.invoke(None),
            [u'foo', u'bar', u'baz quux oatmeal'])
