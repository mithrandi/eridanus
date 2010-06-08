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



class MethodCommandTests(unittest.TestCase):
    """
    Tests for L{eridanus.plugin.MethodCommand}.
    """
    def cmd_test(self, source, foo, bar):
        return (foo, bar)


    def cmd_defaults(self, source, foo, bar=None):
        return (foo, bar)


    def cmd_varargs(self, source, foo, *args):
        return (foo, args)


    @rest
    def cmd_rest(self, source, foo, bar):
        return (foo, bar)


    @rest
    def cmd_restDefaults(self, source, foo, bar=None):
        return (foo, bar)


    @rest
    def cmd_restVarargs(self, source, foo, *args):
        return (foo, args)


    def invokeCommand(self, meth, args):
        """
        Adapt C{meth} to L{ICommand}, checking the result is L{MethodCommand}
        and invoke it with C{args} as the arguments.
        """
        cmd = ICommand(meth)
        self.assertIdentical(type(cmd), MethodCommand)
        cmd.locateCommand(args)
        return cmd.invoke(None)


    def test_invoke(self):
        """
        Invoke a command with exactly the right number of arguments, each
        argument given is split and passed as individual function arguments.
        """
        res = self.invokeCommand(
            self.cmd_test, IncrementalArguments('foo bar'))
        self.assertEquals(res, (u'foo', u'bar'))


    def test_invokeDefaults(self):
        """
        Invoke a command, with defaults, allowing one of the defaults to be used.
        """
        res = self.invokeCommand(
            self.cmd_defaults, IncrementalArguments('foo'))
        self.assertEquals(res, (u'foo', None))


    def test_invokeVarargs(self):
        """
        Invoke a command, with varargs (C{*args}).
        """
        res = self.invokeCommand(
            self.cmd_varargs, IncrementalArguments('foo'))
        self.assertEquals(res, (u'foo', ()))

        res = self.invokeCommand(
            self.cmd_varargs, IncrementalArguments('foo baz  quux'))
        self.assertEquals(res, (u'foo', (u'baz', u'quux')))


    def test_invokeTooMany(self):
        """
        Invoke a command with too many arguments, resulting in
        L{eridanus.errors.UsageError}.
        """
        self.assertRaises(errors.UsageError,
            self.invokeCommand,
            self.cmd_test, IncrementalArguments('foo bar baz'))


    def test_invokeTooFew(self):
        """
        Invoke a command with too few arguments, resulting in
        L{eridanus.errors.UsageError}.
        """
        self.assertRaises(errors.UsageError,
            self.invokeCommand,
            self.cmd_test, IncrementalArguments('foo'))


    def test_invokeRest(self):
        """
        Invoke a command decorated with L{rest}, the final command argument
        will contain all remaining arguments intact. Omitting an argument to
        the "rest" (final) argument results in it being the empty string.
        """
        res = self.invokeCommand(self.cmd_rest, IncrementalArguments('foo'))
        self.assertEquals(res, (u'foo', u''))

        res = self.invokeCommand(self.cmd_rest, IncrementalArguments('foo bar'))
        self.assertEquals(res, (u'foo', u'bar'))

        res = self.invokeCommand(
            self.cmd_rest, IncrementalArguments('foo bar baz'))
        self.assertEquals(res, (u'foo', u'bar baz'))


    def test_invokeRestDefaults(self):
        """
        Commands decorated with L{rest} using defaults cause C{TypeError} to be
        raised.
        """
        self.assertRaises(TypeError,
            self.invokeCommand,
            self.cmd_restDefaults, IncrementalArguments('foo'))


    def test_invokeRestVarargs(self):
        """
        Commands decorated with L{rest} using varargs (C{*args}) cause C{TypeError} to be
        raised.
        """
        self.assertRaises(TypeError,
            self.invokeCommand,
            self.cmd_restVarargs, IncrementalArguments('foo'))


    def test_invokeRestTooFew(self):
        """
        Invoke a command with too few arguments, resulting in
        L{eridanus.errors.UsageError}.
        """
        self.assertRaises(errors.UsageError,
            self.invokeCommand,
            self.cmd_rest, IncrementalArguments(''))



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
