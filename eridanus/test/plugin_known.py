"""
A known plugin, with some commands.
"""
from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.item import Item
from axiom.attributes import integer

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin



class Known(Item, Plugin):
    """
    A little plugin that does little things.
    """
    classProvides(IPlugin, IEridanusPluginProvider)

    dummy = integer()

    def cmd_test(self, source, foo, bar):
        return (foo, bar)
