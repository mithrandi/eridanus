import unicodedata

from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage, rest



class Unicode(Item, Plugin):
    """
    Basic Unicode related services.
    """
    classProvides(IPlugin, IEridanusPluginProvider)

    typeName = 'eridanus_plugins_std_unicodeplugin'

    dummy = integer()

    @rest
    @usage(u'name <unicodeCharacters>')
    def cmd_name(self, source, chars):
        """
        Get the Unicode names for <unicodeCharacters>.
        """
        names = map(unicodedata.name, chars)
        source.reply(u'; '.join(names))


    @rest
    @usage(u'lookup <unicodeName>')
    def cmd_lookup(self, source, name):
        """
        Get the Unicode character for <unicodeName>.
        """
        source.reply(unicodedata.lookup(name))

