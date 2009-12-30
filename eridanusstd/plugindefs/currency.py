from decimal import Decimal

from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus import errors
from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

from eridanusstd import currency

class Currency(Item, Plugin):
    """
    Simple currency services.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_currencyplugin'

    name = u'currency'
    pluginName = u'Currency'

    dummy = integer()

    @usage(u'convert <amount> <from> <to>')
    def cmd_convert(self, source, amount, currencyFrom, currencyTo):
        """
        Convert <amount> from currency <from> to currency <to>.

        Currencies should be specified using their 3-digit currency codes.
        """
        amount = Decimal(amount)
        currencyFrom = currencyFrom.upper()
        currencyTo = currencyTo.upper()

        def convert((rate, tradeTime)):
            convertedAmount = rate * amount
            source.reply(unicode(convertedAmount))

        return yahoo.currencyExchange(currencyFrom, currencyTo
            ).addCallback(convert)

    @usage(u'name <code>')
    def cmd_name(self, source, code):
        """
        Get the currency name from a currency code.
        """
        code = code.upper()
        name = currency.currencyNames.get(code)
        if name is None:
            raise errors.InvalidCurrency(u'%r is not a recognised currency code' % (code,))

        source.reply(name)
