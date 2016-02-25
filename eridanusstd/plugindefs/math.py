from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage, rest

from eridanusstd import calc



class Math(Item, Plugin):
    """
    Various mathematics related commands.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    typeName = 'eridanus_plugins_math'

    dummy = integer()

    @rest
    @usage(u'calc <expn>')
    def cmd_calc(self, source, expn):
        """
        Evaluate simple mathematical expressions.
        """
        source.reply(calc.evaluate(expn))


    @usage(u'base <number> <base>')
    def cmd_base(self, source, number, base):
        """
        Convert a base-10 number to another base.
        """
        source.reply(calc.base(int(number), int(base)))
