from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer, inmemory
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

from eridanusstd import calc

class Math(Item, Plugin):
    """
    Various mathematics related services.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_math'

    name = u'math'
    pluginName = u'Math'

    dummy = integer()

    _calculator = inmemory()

    @property
    def calculator(self):
        if self._calculator is None:
            self._calculator = calc.Calculator()
        return self._calculator

    @usage(u'calc <expression> [expression ...]')
    def cmd_calc(self, source, expr, *exprs):
        """
        Evaluate simple mathematical expressions.
        """
        expr = u' '.join((expr,) + exprs)
        return self.calculator.evaluate(expr
            ).addCallback(source.reply)

