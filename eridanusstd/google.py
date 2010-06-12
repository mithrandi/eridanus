"""
Utilities for querying Google's APIs.

The following documentation may be useful::

    http://code.google.com/apis/ajaxsearch/documentation/#fonje
"""
import html5lib
from lxml import etree as letree
try:
    import simplejson as json
except ImportError:
    import json

from twisted.internet import defer

from nevow.url import URL

from eridanus import util
from eridanusstd import errors, defertools



HEADERS = {
    'Referrer': 'http://trac.slipgate.za.net/Eridanus'}

SEARCH_URL = URL.fromString('http://ajax.googleapis.com/ajax/services/search/')



class WebSearchQuery(object):
    """
    Encapsulate a Google web search query.

    Ideally this should be combined with the C{eridanusstd.defertools} module,
    to lazily pull results from C{self.queue}.  With this method, new pages
    will automatically be fetched when a result set runs dry.

    @type term: C{unicode}
    @ivar term: Search term.

    @type url: C{nevow.url.URL}
    @ivar url: Base search URL.

    @type pages: C{list} of C{dict}s
    @ivar pages: Remaining result pages that can be fetched.

    @type queue: C{defertools.LazyQueue}
    @ivar queue: Queue where results are lazily accumulated.
    """
    def __init__(self, term, apiKey=None):
        """
        Initialise a query.

        @type apiKey: C{unicode} or C{None}
        @param apiKey: A valid Google AJAX Search API key or C{None}.
        """
        self.term = term
        url = SEARCH_URL.child('web'
            ).add('v', '1.0'
            ).add('q', self.term.encode('utf-8'))

        if apiKey is not None:
            url = url.add('key', apiKey)

        self.url = url
        self.pages = None
        self.queue = defertools.LazyQueue(self.getMoreResults)


    def __repr__(self):
        return '<%s for: %r>' % (
            type(self).__name__,
            self.term)


    def parseResults(self, (data, headers)):
        """
        Parse Google's JSON response into results.

        @raise errors.NoSearchResults: If the response contains no results

        @rtype: C{iterable} of C{(unicode, unicode)}
        @return: An iterable of C{(title, url)} pairs
        """
        response = json.loads(data)[u'responseData']

        cursor = response.get(u'cursor')
        currentPageIndex = cursor.get(u'currentPageIndex')
        pages = cursor.get(u'pages')

        if self.pages is None:
            self.pages = pages
        if self.pages:
            self.pages.pop(0)

        results = response.get(u'results')
        if not results:
            raise errors.NoSearchResults(
                u'No results for the search term: ' + self.term)

        return (
            (util.unescapeEntities(result[u'titleNoFormatting']),
             result[u'url'])
            for result in results)


    def getMoreResults(self, start=None):
        """
        Retrieve and parse the next page of results.
        """
        if start is None:
            if self.pages is None:
                start = u'0'
            elif self.pages:
                start = self.pages[0][u'start']
            else:
                return defer.succeed([])

        url = self.url.add('start', start)
        return util.PerseverantDownloader(url, headers=HEADERS).go(
            ).addCallback(self.parseResults)



class Calculator(object):
    """
    Primitive screen-scraping interface to Google's calculator.
    """
    _resultFormatting = {
        'sup': u'^'}

    def _formatResult(self, elem):
        """
        Gracefully downgrade HTML markup in calculator results.
        """
        def _format():
            yield elem.text
            for child in elem.iterchildren():
                tag = child.tag.split('}')[-1]
                extra = self._resultFormatting.get(tag)
                if extra is not None:
                    yield extra
                yield child.text
                yield child.tail

        return filter(None, _format())


    def _extractResult(self, (data, headers), expn):
        """
        Extract the calculator result from a Google search.

        @rtype:  C{(unicode, unicode)}
        @return: A pair of C{(expn, result)}.
        """
        parser = html5lib.HTMLParser(
            tree=html5lib.treebuilders.getTreeBuilder('lxml', letree))
        tree = parser.parse(data)

        # At some point html5lib stopped sucking.
        if hasattr(html5lib, '__version__'):
            xpath = '//xhtml:h2[@class="r"]/xhtml:b'
        else:
            xpath = '//h2[@class="r"]/b'

        results = tree.xpath(
            xpath,
            namespaces={'xhtml': 'http://www.w3.org/1999/xhtml'})
        if results:
            return u''.join(self._formatResult(results[0]))
        raise errors.InvalidExpression(expn)


    def _fetch(self, url):
        """
        Fetch page data.
        """
        return util.PerseverantDownloader(url).go()


    def evaluate(self, expn):
        """
        Evaluate an expression.
        """
        url = URL.fromString('http://www.google.com/search?')
        url = url.add('q', expn + '=')
        url = url.add('num', '1')
        d = self._fetch(url)
        d.addCallback(self._extractResult, expn)
        return d
