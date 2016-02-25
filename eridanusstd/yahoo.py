import csv
from decimal import Decimal
from StringIO import StringIO

from nevow.url import URL

from eridanus import util
from eridanusstd import errors


CURRENCY_URL = URL.fromString('http://download.finance.yahoo.com/d/quotes.csv?f=l1d1t1ba&e=.csv')


def currencyExchange(currencyFrom, currencyTo):
    def gotCSV((data, headers)):
        row = csv.reader(StringIO(data)).next()
        lastTradeRate, d, t, bid, ask = row
        lastTradeRate = Decimal(lastTradeRate)

        if lastTradeRate == 0:
            raise errors.InvalidCurrency(u'One of the specified currency codes is invalid')

        tradeTime = u'%s %s' % (d, t)
        return Decimal(lastTradeRate), tradeTime

    url = CURRENCY_URL.add('s', '%s%s=X' % (currencyFrom, currencyTo))
    return util.PerseverantDownloader(url).go(
        ).addCallback(gotCSV)
