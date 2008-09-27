import csv
from datetime import datetime, date
from decimal import Decimal
from StringIO import StringIO

from epsilon.extime import Time

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

        print d, d.split('/', 3)
        month, day, year = map(int, d.split('/', 3))
        d = date(year, month, day)
        t = Time.fromHumanly(t).asDatetime().time()
        tradeTime = Time.fromDatetime(datetime.combine(d, t))

        return Decimal(lastTradeRate), tradeTime

    url = CURRENCY_URL.add('s', '%s%s=X' % (currencyFrom, currencyTo))
    return util.PerseverantDownloader(url).go(
        ).addCallback(gotCSV)
