import inspect, types, re
from textwrap import dedent
from zope.interface import implements

from twisted.plugin import getPlugins
from twisted.python.components import registerAdapter

from eridanus import plugins, errors
from eridanus.ieridanus import (ICommand, IEridanusPluginProvider,
    IEridanusPlugin, IAmbientEventObserver)


paramPattern = re.compile(r'([<[])(\w+)([>\]])')

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
    lines = [line for line in dedent(help).splitlines() if line]
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

    def locateCommand(self, params):
        cmd = params.pop(0).lower()
        method = getattr(self,
                         'cmd_%s' % cmd,
                         None)
        if method is None:
            msg = 'Unknown command "%s"' % (cmd,)
            raise errors.UsageError(msg)

        return ICommand(method), params

    def invoke(self, source):
        raise errors.UsageError('Not a command')


class SubCommand(CommandLookupMixin):
    def invoke(self, source):
        raise errors.UsageError('Too few parameters')


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
    defaultHelp = """No additional help."""

    def __init__(self, method):
        super(MethodCommand, self).__init__()

        usage = getattr(method, 'usage', None)
        if usage is None:
            usage = self.defaultUsage

        help = getattr(method, 'help', None)
        if help is None:
            help = self.defaultHelp

        self.method = method
        self.params = []
        self.name = method.__name__.strip('cmd_')
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
        minargs, maxargs = arglimits = getattr(self.method, 'arglimits', (None, None))

        args, vararg, varkw, defaults = inspect.getargspec(self.method)
        # Exclude self and source parameters.
        normArgCount = len(args) - 2

        if minargs is None:
            # Exclude default arguments from impacting the minimum number of
            # required arguments.
            minargs = normArgCount - len(defaults or [])

        if maxargs is None:
            if vararg is None:
                maxargs = normArgCount
            else:
                maxargs = None

        return minargs, maxargs

    ### ICommand

    def locateCommand(self, params):
        self.params = params
        return self, []

    def invoke(self, source):
        numargs = len(self.params)

        if numargs < self.minargs:
            raise errors.UsageError('Not enough arguments')
        if self.maxargs is not None and numargs > self.maxargs:
            raise errors.UsageError('Too many arguments')

        return self.method(source, *self.params)

registerAdapter(MethodCommand, types.MethodType, ICommand)


class Plugin(CommandLookupMixin):
    """
    Simple plugin mixin.
    """
    implements(IEridanusPlugin)

    name = None
    pluginName = None


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


def getPluginProvidersByName(pluginName):
    """
    Get all objects that provide C{IEridanusPluginProvider}.
    """
    for plugin in getPlugins(IEridanusPluginProvider, plugins):
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