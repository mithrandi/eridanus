from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

from eridanusstd import calc



class Math(Item, Plugin):
    """
    Various mathematics related commands.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_math'

    dummy = integer()

    @usage(u'calc <expression> [expression ...]')
    def cmd_calc(self, source, expr, *exprs):
        """
        Evaluate simple mathematical expressions.
        """
        expr = u' '.join((expr,) + exprs)
        source.reply(calc.evaluate(expr))

