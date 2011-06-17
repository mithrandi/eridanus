from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import text
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider, IAmbientEventObserver
from eridanus.plugin import AmbientEventObserver, Plugin, usage, rest

from eridanusstd import alias, errors



class Alias(Item, Plugin, AmbientEventObserver):
    """
    Manage command aliases.

    Aliases are a convenient way to write shortcuts for common commands. Any
    command, optionally including arguments, can be made into an alias.
    Additional arguments can be passed by the user invoking the alias.

    Alias names may NOT contain whitespace.

    Aliases are invoked by starting a line with the trigger (defaulting to '!')
    followed immediately by the alias name. Alias names and the trigger are
    case insensitive.
    """
    classProvides(IPlugin, IEridanusPluginProvider, IAmbientEventObserver)

    trigger = text(default=u'!')

    @rest
    @usage(u'define <name> <command>')
    def cmd_define(self, source, name, command):
        """
        Define a new alias.

        Any existing alias with the given name will be overwritten.
        """
        a = alias.defineAlias(self.store, name, command)
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


    def _isTrigger(self, message):
        """
        Does C{message} start with the alias trigger?
        """
        return message.lower().startswith(self.trigger.lower())


    def _expandAlias(self, message):
        """
        Expand an alias definition.

        Parameters appearing after the alias name are preserved.

        @rtype: C{unicode}
        @return: Expanded alias definition.
        """
        parts = message.split(u' ', 1)
        name = parts[0]
        if not name:
            return None

        a = alias.findAlias(self.store, name)
        message = a.command
        if len(parts) > 1:
            message += ' ' + parts[1]

        return message


    # IAmbientEventObserver

    def publicMessageReceived(self, source, message):
        if self._isTrigger(message):
            try:
                message = self._expandAlias(message[len(self.trigger):])
            except errors.InvalidIdentifier, e:
                source.privateNotice(u'%s: %s' % (type(e).__name__, e))
            else:
                if message:
                    # XXX: We really should not be touching the protocol.
                    return source.protocol.command(source, message)
