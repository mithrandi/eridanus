from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import text
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider, IAmbientEventObserver
from eridanus.plugin import AmbientEventObserver, Plugin, usage

from eridanusstd import alias



class Alias(Item, Plugin, AmbientEventObserver):
    """
    Manage command aliases.

    Aliases are a convenient way to write shortcuts for common commands. Any
    command, optionally including arguments, can be made into an alias.
    Additional arguments can be passed by the user invoking the alias.

    Alias names may NOT contain whitespace.

    Aliases are invoked by starting a line with the trigger character
    (defaulting to '!') followed immediately by the alias name.
    """
    classProvides(IPlugin, IEridanusPluginProvider, IAmbientEventObserver)

    trigger = text(default=u'!')

    @usage(u'define <name> [param ...]')
    def cmd_define(self, source, name, *params):
        """
        Define a new alias.

        Any existing alias with the given name will be overwritten.
        """
        a = alias.defineAlias(self.store, name, params)
        source.reply(a.displayValue())


    @usage(u'undefine <name>')
    def cmd_undefine(self, source, name):
        """
        Undefine an existing alias.
        """
        alias.findAlias(self.store, name)
        alias.undefineAlias(self.store, name)


    @usage(u'display <name>')
    def cmd_display(self, source, name):
        """
        Display the command stored for an existing alias.
        """
        a = alias.findAlias(self.store, name)
        source.reply(a.displayValue())


    @usage(u'list')
    def cmd_list(self, source):
        """
        List all defined aliases.
        """
        aliasNames = (a.name for a in alias.getAliases(self.store))
        source.reply(u'; '.join(aliasNames))


    # IAmbientEventObserver

    def publicMessageReceived(self, source, message):
        if message.lower().startswith(self.trigger.lower()):
            # XXX: We really should not be touching the protocol.
            params = source.protocol.splitMessage(message[1:])
            if not params:
                return

            name = params.pop(0)
            a = alias.findAlias(self.store, name)
            params = a.params + params
            # XXX: We really should not be touching the protocol.
            source.protocol.command(source, params)
