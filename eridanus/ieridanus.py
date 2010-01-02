from zope.interface import Interface, Attribute


class ICommand(Interface):
    """
    Interface for representing objects that can locate sub-commands and invoke
    them.
    """

    name = Attribute("""
    A C{str} that is the command's name.
    """)

    usage = Attribute("""
    A single-line C{str} that details usage/syntax information for the command.
    """)

    help = Attribute("""
    A C{str}, optionally multi-line, that goes into detail about this command's
    behaviour and any related information.
    """)

    parent = Attribute("""
    The parent object of this command.
    """)

    def locateCommand(params):
        """
        Find the C{ICommand} handler responsible for a given command.

        The first parameter is popped from C{params} and is treated as the
        command handler name. If no handler is found L{UsageError} is raised.

        @param params: The parameters, including the command, for a command
        @type params: C{list}

        @return: The command handler for the command and the remaining parameters
        @rtype: C{(ICommand, list)}
        """


    def invoke(source):
        """
        Invoke the command.

        @param source: The source that the command originated from
        @type pseudo: L{Source} instance
        """



class IEridanusPlugin(Interface):
    """
    An object that is considered by Eridanus to be a usable plugin.
    """

    name = Attribute("""
    A C{unicode} value that specifies how the plugin is addressed in a command.
    Defaults to the name of the plugin class lowercased.
    """)

    pluginName = Attribute("""
    A C{unicode} value that specifies how the plugin is addressed outside
    of commands. Defaults to the name of the plugin class.
    """)

    axiomCommands = Attribute("""
    An C{iterable} that contains tuples suitable for use in the C{subCommands}
    attribute on a subclass of C{axiom.scripts.axiomatic.AxiomaticSubCommand}.
    Defaults to an empty tuple.
    """)



class IEridanusPluginProvider(Interface):
    """
    Interface for specifying that something can provide L{IEridanusPlugin}.
    """

    def __call__(store):
        pass



class IEridanusBrokenPlugin(Interface):
    """
    An object that is considered by Eridanus to be an unusable plugin.
    """

    pluginName = Attribute("""
    A C{unicode} value that names the broken plugin.
    """)

    failure = Attribute("""
    A C{twisted.python.failure.Failure} instance describing why the plugin is
    broken.
    """)



class IEridanusBrokenPluginProvider(Interface):
    """
    Interface for specifying that something can provide
    L{IEridanusBrokenPlugin}.
    """

    def __call__(store):
        pass



class IAmbientEventObserver(Interface):
    """
    An object that receives notifications about ambient events.
    """

    def publicMessageReceived(source, message):
        """
        A public message occured.

        @rtype: C{twisted.internet.Deferred}
        """



# XXX: this is too specific to be useful, but it's fine for now
class IIRCAvatar(Interface):
    """
    An IRC user's avatar.
    """

    def locatePlugins(protocol, name):
        """
        Find all installed plugins with C{name}.

        @type name: C{unicode}
        @param name: Plugin name

        @return: An iterable of objects implementing C{IEridanusPlugin}
        """


    def getCommand(protocol, params):
        """
        Get the C{ICommand} provider with the given parameters.

        The first parameter is used to determine the plugin to locate the
        command in.

        @raise eridanus.errors.PluginNotInstalled: If the plugin parameter
            specifies a plugin that is not installed

        @raise eridanus.errors.UsageError: If there is any problem locating
            the command

        @return: An object implementing C{ICommand}
        """


    def locateCommand(plugin, params):
        """
        Locate a plugin command.

        @param plugin: The plugin to locate the command in
        @type plugin: {IEridanusPlugin} provider

        @param params: The command parameters
        @type params: C{list}

        @raise eridanus.errors.UsageError: If there is a problem locating the
            command

        @return: The located command
        @rtype: C{ICommand} provider
        """
