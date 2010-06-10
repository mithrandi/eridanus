# -*- test-case-name: eridanus.test.test_plugin -*-

import inspect, types, re, itertools
from textwrap import dedent
from zope.interface import implements, classProvides

from twisted.plugin import getPlugins, IPlugin
from twisted.python.components import registerAdapter
from twisted.python.util import mergeFunctionMetadata
from twisted.python.failure import Failure

from eridanus import plugins, errors
from eridanus.ieridanus import (ICommand, IEridanusPluginProvider,
    IEridanusPlugin, IAmbientEventObserver, IEridanusBrokenPlugin,
    IEridanusBrokenPluginProvider)



def safePluginImport(globals, pluginpath):
    """
    Import a plugin class in a way that defers errors.

    Plugins that import without errors are added to the global
    namespace as if they had been imported normally. If an exception
    is raised during the import, the exception is captured and wrapped
    in an C{IBrokenPlugin} which can be listed and examined at
    runtime.

    In this way, all plugins are visible, if not installable, and the
    broken ones provide (hopefully) sufficient information to coax
    them into life. Usually this will involve installing whatever
    external libraries they depend on.

    @param globals: Namespace to import plugin into (usually globals())
    @type globals: C{dict}

    @param pluginpath: Full module path of the plugin to import
    @type pluginpath: C{str}
    """
    mod, pin = pluginpath.rsplit('.', 1)
    try:
        imported = __import__(mod, fromlist=[pin])
        plugin = getattr(imported, pin)
    except:

        class ThisBrokenPlugin(BrokenPlugin):
            classProvides(IPlugin, IEridanusBrokenPluginProvider)
            pluginName = pin
            failure = Failure()

        plugin = ThisBrokenPlugin
    globals[pin] = plugin



paramPattern = re.compile(r'([<[])(.*?)([>\]])')

def formatUsage(s):
    """
    Add some IRC formatting to defined parameters.

    Parameters are detected by being enclosed in C{<>} or C{[]}.

    @returns: Marked-up string
    """
    return paramPattern.sub(r'\1\002\2\002\3', s)



def formatHelp(help, sep=' '):
    """
    Dedent help text and strip blank lines.

    @returns: A "short help" and the complete help
    @rtype: C{(shortHelp, help)}
    """
    lines = [line.strip()
             for line in dedent(help).splitlines()
             if line.strip()]
    return lines[0], sep.join(lines)



def usage(desc):
    """
    Decorate a function with usage and help information.

    Help text is extracted from the function's doc string.

    @param desc: Usage description
    @type desc: C{str} or C{unicode}
    """
    def fact(f):
        f.usage = formatUsage(desc)
        f.help = f.__doc__
        return f
    return fact



def rest(f):
    """
    Decorate a function with a flag indicating that it should receive all
    remainder arguments in the last function argument.
    """
    f.rest = True
    return f



def alias(f, name=None):
    """
    Create an alias of another command.
    """
    newCmd = mergeFunctionMetadata(f, lambda *a, **kw: f(*a, **kw))
    newCmd.alias = True
    if name is not None:
        newCmd.func_name = name
    newCmd.arglimits = getCommandArgLimits(f)
    return newCmd



def getCommandArgLimits(method, minargs=None, maxargs=None):
    """
    Find the argument limits on an C{ICommand} method.
    """
    args, vararg, varkw, defaults = inspect.getargspec(method)
    # Exclude self and source parameters.
    normArgCount = len(args) - 2

    rest = getattr(method, 'rest', False)

    if minargs is None:
        # Exclude default arguments from impacting the minimum number of
        # required arguments.
        minargs = normArgCount - len(defaults or [])

    if maxargs is None:
        if vararg is None:
            maxargs = normArgCount
        else:
            maxargs = None

    if rest:
        if maxargs is None:
            raise TypeError(
                'Commands decorated with "rest" cannot use varargs')
        elif minargs != maxargs:
            raise TypeError(
                'Commands decorated with "rest" cannot use defaults')

    return minargs, maxargs



class IncrementalArguments(object):
    """
    Incrementally parse arguments from a message via the iteration protocol.

    Text quoted with C{"} is split as a single value.

    @type tail: C{unicode}
    @ivar tail: Current tail of the message.
    """
    def __init__(self, tail):
        self.tail = tail


    def __repr__(self):
        return '<%s tail=%r>' % (
            type(self).__name__,
            self.tail)


    def _splitArguments(self):
        """
        Split the next argument from C{tail}.

        @rtype: C{(unicode, unicode)}
        @return: C{(head, tail)}
        """
        def _readOne(s):
            one, sep, rest = s.partition(' ')
            return one, rest

        def _readQuoted(s):
            one = u''
            escaped = False
            it = iter(s)
            for c in it:
                if escaped:
                    one += c
                    escaped = False
                elif c == u'\\':
                    escaped = True
                elif c == u'"':
                    break
                else:
                    one += c
            return one, u''.join(it)

        s = self.tail.lstrip()
        if s == u'':
            raise ValueError('No arguments to split')

        if s[0] == u'"':
            head, tail = _readQuoted(s[1:])
        else:
            head, tail = _readOne(s)

        return head, tail.lstrip()


    def copy(self):
        return type(self)(self.tail)


    # Iterator protocol

    def __iter__(self):
        return self


    def next(self):
        if not self.tail:
            raise StopIteration()
        head, self.tail = self._splitArguments()
        return head



class CommandLookupMixin(object):
    """
    L{ICommand} implementation that locates methods suitable for invocation.

    Methods whose names begin with C{cmd_} are adapted to L{ICommand} when
    locating commands.
    """
    implements(ICommand)

    name = None
    usage = None

    @property
    def help(self):
        """
        Extract help text from C{__doc__}.
        """
        help = self.__doc__
        if help is None:
            return 'No additional help.'
        return formatHelp(help)[1]


    def getCommands(self):
        for name in dir(self):
            if name.startswith('cmd_'):
                yield ICommand(getattr(self, name))


    # ICommand

    def locateCommand(self, args):
        cmd = args.next().lower()
        method = getattr(self, 'cmd_%s' % cmd, None)
        if method is None:
            raise errors.UsageError('Unknown command "%s"' % (cmd,))

        cmd = ICommand(method)
        # XXX: This might not be the best route.  Primarily useful for making
        # SubCommand not quite so useless (access to the parent's store etc.)
        cmd.parent = self
        return cmd, args


    def invoke(self, source):
        raise errors.UsageError('Not a command')



class SubCommand(CommandLookupMixin):
    # XXX: maybe this could actually work?
    alias = False

    def invoke(self, source):
        raise errors.UsageError('Too few parameters -- ' + self.help)



class MethodCommand(object):
    """
    Wraps a method in something that implements L{ICommand}.

    This is most useful when combined with L{eridanus.plugin.usage} to generate
    (and format) the relevant help strings.

    @ivar method: The method being wrapped

    @ivar usage: The command's usage, extracted from C{method.usage}
                 or C{defaultUsage}
    @type usage: C{str} or C{unicode}

    @ivar help: The command's complete help, extracted from C{method.help}
                or C{defaultHelp}
    @type help: C{str} or C{unicode}

    @ivar shortHelp: The first line of C{help}, which should be a brief
                     description of the command's purpose
    """
    implements(ICommand)

    defaultUsage = 'No usage information'
    defaultHelp = 'No additional help.'

    def __init__(self, method):
        super(MethodCommand, self).__init__()

        usage = getattr(method, 'usage', None)
        if usage is None:
            usage = self.defaultUsage

        help = getattr(method, 'help', None)
        if help is None:
            help = self.defaultHelp

        self.method = method
        self.args = IncrementalArguments(u'')
        self.rest = getattr(method, 'rest', False)
        self.name = method.__name__[4:]
        self.usage = usage
        self.shortHelp, self.help = formatHelp(help)

        self.minargs, self.maxargs = self.getArgLimits()


    def __repr__(self):
        return '<%s wrapping %s>' % (type(self).__name__, self.method)


    def getArgLimits(self):
        """
        Find the minimum and maximum arguments for L{MethodCommand.method}.

        If the method has an C{arglimits} 2-tuple attribute, these values
        are used.  Otherwise the limits are calculated by inspecting the
        method.

        Implicit and default parameters are not taken into account when
        calculating the minimum number of arguments.

        The maximum number of arguments will be unbounded if the method accepts
        varargs.

        @returns: The minimum and maximum number of arguments that the method
                  will accept
        @rtype: C{(min, max)}
        """
        minargs, maxargs = getattr(self.method, 'arglimits', (None, None))
        return getCommandArgLimits(self.method, minargs, maxargs)


    @property
    def alias(self):
        return getattr(self.method, 'alias', False)


    # ICommand

    def locateCommand(self, args):
        self.args = args
        return self, IncrementalArguments(u'')


    def invoke(self, source):
        count = self.maxargs
        if self.rest:
            count -= 1

        if count is None:
            params = self.args
        else:
            params = itertools.islice(self.args, count)
        params = list(params)

        if self.rest:
            params.append(self.args.tail)
        elif self.args.tail:
            raise errors.UsageError('Too many arguments -- ' + self.usage)

        if len(params) < self.minargs:
            raise errors.UsageError('Not enough arguments -- ' + self.usage)

        return self.method(source, *params)

registerAdapter(MethodCommand, types.MethodType, ICommand)



class _PluginNameDescriptor(object):
    """
    A descriptor class to default pluginName to the plugin's class name.
    """
    def __get__(self, instance, owner):
        return owner.__name__



class _NameDescriptor(object):
    """
    A descriptor class to default name to the plugin's class name lowercased.
    """
    def __get__(self, instance, owner):
        return owner.__name__.lower()



class Plugin(CommandLookupMixin):
    """
    Simple plugin mixin.
    """
    implements(IEridanusPlugin)

    name = _NameDescriptor()
    pluginName = _PluginNameDescriptor()
    axiomCommands = () # A tuple, because mutable class attrs are ugh.



class BrokenPlugin(object):
    """
    Base class for broken plugins.
    """
    implements(IEridanusBrokenPlugin)

    pluginName = None
    failure = None



def getAllPlugins():
    """
    Get all plugins.
    """
    return getPlugins(IEridanusPluginProvider, plugins)



def getBrokenPlugins():
    """
    Get broken plugins.
    """
    return getPlugins(IEridanusBrokenPluginProvider, plugins)



def getPluginByName(store, name):
    """
    Get an C{IEridanusPlugin} provider by name.

    @type store: C{axiom.store.Store}

    @param name: Name of the plugin to find
    @type name: C{unicode}

    @raises PluginNotFound: If no plugin named C{name} could be found

    @returns: The plugin item
    @rtype: C{IEridanusPlugin}
    """
    for plugin in store.powerupsFor(IEridanusPlugin):
        if plugin.name == name:
            return plugin

    raise errors.PluginNotInstalled(name)



def getInstalledPlugins(store):
    """
    Get all plugins installed on C{store}.
    """
    return store.powerupsFor(IEridanusPlugin)



def getPluginProvidersByName(pluginName):
    """
    Get all objects that provide C{IEridanusPluginProvider}.
    """
    for plugin in getPlugins(IEridanusPluginProvider, plugins):
        if plugin.pluginName == pluginName:
            yield plugin

    raise errors.PluginNotFound(u'No plugin named "%s".' % (pluginName,))



def getBrokenPluginProvidersByName(pluginName):
    """
    Get all objects that provide C{IEridanusPluginProvider}.
    """
    for plugin in getPlugins(IEridanusBrokenPluginProvider, plugins):
        if plugin.pluginName == pluginName:
            yield plugin

    raise errors.PluginNotFound(u'No plugin named "%s".' % (pluginName,))



def getAmbientEventObservers(store):
    """
    Get all Items that provide C{IAmbientEventObserver}.
    """
    return store.powerupsFor(IAmbientEventObserver)



def installPlugin(store, pluginName):
    """
    Install a plugin on a store.

    @type store: C{axiom.store.Store}

    @param pluginName: Name of the plugin to install
    @type pluginName: C{unicode}

    @raises PluginNotFound: If no plugin named C{pluginName} could be found
    """
    for plugin in getPluginProvidersByName(pluginName):
        p = store.findOrCreate(plugin)
        store.powerUp(p, IEridanusPlugin)
        if IAmbientEventObserver.providedBy(plugin):
            store.powerUp(p, IAmbientEventObserver)
        return

    raise errors.PluginNotFound(u'No plugin named "%s".' % (pluginName,))



def diagnoseBrokenPlugin(pluginName):
    """
    Explain why a plugin is broken.

    @param pluginName: Name of the broken plugin to explain
    @type pluginName: C{unicode}

    @raises PluginNotFound: If no plugin named C{pluginName} could be found
    """
    for plugin in getBrokenPluginProvidersByName(pluginName):
        return plugin.failure

    raise errors.PluginNotFound(u'No plugin named "%s".' % (pluginName,))



def uninstallPlugin(store, pluginName):
    """
    Uninstall a plugin from a store.

    @type store: C{axiom.store.Store}

    @param pluginName: Name of the plugin to install
    @type pluginName: C{unicode}

    @raise errors.PluginNotInstalled: If C{pluginName} is not installed on
        C{store}
    """
    # XXX: this should probably use store.powerupsFor
    for plugin in getPluginProvidersByName(pluginName):
        p = store.findUnique(plugin, default=None)
        if p is None:
            raise errors.PluginNotInstalled(pluginName)

        store.powerDown(p, IEridanusPlugin)
        return



class AmbientEventObserver(object):
    """
    Abstract base class for L{IAmbientEventObserver}.
    """
    def publicMessageReceived(self, source, message):
        pass
