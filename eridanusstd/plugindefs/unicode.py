import unicodedata

from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

class Unicode(Item, Plugin):
    """
    Basic Unicode related services.
    """
    classProvides(IPlugin, IEridanusPluginProvider)

    name = u'unicode'
    pluginName = u'Unicode'

    dummy = integer()

    @usage(u'name <unicodeCharacter>')
    def cmd_name(self, source, char):
        """
        Get the Unicode name for <unicodeCharacter>.
        """
        source.reply(unicodedata.name(char))

    @usage(u'lookup <unicodeName>')
    def cmd_lookup(self, source, name):
        """
        Get the Unicode character for <unicodeName>.
        """
        source.reply(unicodedata.lookup(name))

