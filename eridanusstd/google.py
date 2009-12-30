"""
Utilities for querying Google's APIs.

The following documentation may be useful::

    http://code.google.com/apis/ajaxsearch/documentation/#fonje
"""
try:
    import simplejson as json
except ImportError:
    import json

from twisted.internet import defer

from nevow.url import URL

from eridanus import util
from eridanusstd import errors, defertools


HEADERS = {
    'Referrer': 'http://trac.slipgate.za.net/Eridanus'
    }

SEARCH_URL = URL.fromString('http://ajax.googleapis.com/ajax/services/search/')


class WebSearchQuery(object):
    """
    Encapsulate a Google web search query.

    Ideally this should be combined with the C{eridanusstd.defertools} module,
    to lazily pull results from C{self.queue}.  With this method, new pages
    will automatically be fetched when a result set runs dry.

    @type terms: C{list} of C{unicode}
    @ivar terms: The query's search terms

    @type url: C{nevow.url.URL}
    @ivar url: The base search URL

    @type pages: C{list} of C{dict}s
    @ivar pages: The remaining result pages that can be fetched

    @type queue: C{defertools.LazyQueue}
    @ivar queue: The queue where results are lazily accumulated
    """
    def __init__(self, terms, apiKey=None):
        """
        Initialise a query.

        @type terms: C{iterable} of C{unicode}
        @param terms: An iterable of search terms to query for, terms that
            contain a space will be quoted

        @type apiKey: C{unicode} or C{None}
        @param apiKey: A valid Google AJAX Search API key or C{None}
        """
        self.terms = list(self._quoteTerms(terms))
        url = SEARCH_URL.child('web'
            ).add('v', '1.0'
            ).add('q', u' '.join(self.terms))

        if apiKey is not None:
            url = url.add('key', apiKey)

        self.url = url
        self.pages = None
        self.queue = defertools.LazyQueue(self.getMoreResults)

    def __repr__(self):
        return '<%s for: %r>' % (
            type(self).__name__,
            self.terms)

    def _quoteTerms(self, terms):
        """
        Iterate C{terms} and quote any terms that need to be quoted.
        """
        for term in terms:
            if u' ' in term:
                yield u'"%s"' % (term,)
            else:
                yield term

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
                u'No results for the search terms: ' + u'; '.join(self.terms))

        return ((util.unescapeEntities(result[u'titleNoFormatting']), result[u'url'])
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
