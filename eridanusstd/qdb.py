from twisted.web import error as weberror, http

from nevow.url import URL

from eridanus import util
from eridanusstd import errors
from eridanusstd.util import parseHTML



def handleBadQuoteID(f, quoteID):
    f.trap(weberror.Error)
    if int(f.value.status) == http.NOT_FOUND:
        raise errors.InvalidQuote(quoteID)
    return f


QDB_US_URL = URL.fromString('http://qdb.us/')

def qdbUS(quoteID):
    url = QDB_US_URL.child(quoteID)

    def extractQuote(tree):
        quote = tree.find('//form/table/tbody')
        header = unicode(''.join(quote.find('tr/td').itertext())).strip()
        text = unicode(''.join(quote.find('tr/td/p').itertext())).strip()

        yield u'%s -- %s' % (header, url)
        for line in text.splitlines():
            yield line

    return util.PerseverantDownloader(url).go(
        ).addCallback(lambda (data, headers): parseHTML(data)
        ).addErrback(handleBadQuoteID, quoteID
        ).addCallback(extractQuote)


BASH_URL = URL.fromString('http://bash.org/')

def bash(quoteID):
    url = BASH_URL.add(quoteID)

    def extractQuote(tree):
        header = (t for t in tree.find('//p[@class="quote"]').itertext()
                  if t not in ('+', '-', '[X]'))
        header = unicode(''.join(header), 'ascii').strip()
        text = unicode(''.join(tree.find('//p[@class="qt"]').itertext())).strip()

        yield u'%s -- %s' % (header, url)
        for line in text.splitlines():
            yield line

    return util.PerseverantDownloader(url).go(
        ).addCallback(lambda (data, headers): parseHTML(data)
        ).addErrback(handleBadQuoteID, quoteID
        ).addCallback(extractQuote)


SLIPGATE_URL = URL.fromString('http://qdb.slipgate.za.net/FlyingCircus/')

def slipgate(quoteID):
    quoteURL = SLIPGATE_URL.child(quoteID)

    def extractQuote(lines):
        lines = iter(lines)
        yield '%s -- %s' % (lines.next(), quoteURL)
        for line in lines:
            yield line

    url = quoteURL.child('raw')
    return util.PerseverantDownloader(url).go(
        ).addCallback(lambda (data, headers): data.splitlines()
        ).addErrback(handleBadQuoteID, quoteID
        ).addCallback(extractQuote)
