from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer, inmemory
from axiom.item import Item

from eridanus import util as eutil
from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage, rest

from eridanusstd import google, defertools



class Google(Item, Plugin):
    """
    Google services.

    It is recommended you set an API key for `googleAjaxSearch`.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    typeName = 'eridanus_plugins_google'

    dummy = integer()

    apiKey = inmemory()

    def activate(self):
        self.apiKey = eutil.getAPIKey(
            self.store, u'googleAjaxSearch', default=None)


    def websearch(self, source, term, count):
        """
        Perform a Google web search.
        """
        def formatResults(results):
            for title, url in results:
                yield u'\002%s\002: <%s>;' % (title, url)

        def displayResults(formattedResults):
            source.reply(u' '.join(formattedResults))

        q = google.WebSearchQuery(term, apiKey=self.apiKey)
        return defertools.slice(q.queue, count
            ).addCallback(formatResults
            ).addCallback(displayResults)


    @rest
    @usage(u'search <term>')
    def cmd_search(self, source, term):
        """
        Perform a Google web search.
        """
        return self.websearch(source, term, 4)


    @rest
    @usage(u'lucky <term>')
    def cmd_lucky(self, source, term):
        """
        Perform an "I'm feeling lucky" Google web search.
        """
        return self.websearch(source, term, 1)


    @rest
    @usage(u'calc <expn>')
    def cmd_calc(self, source, expn):
        """
        Evaluate an expression with Google calculator.

        A guide to using the Google calculator can be found at
        <http://www.google.com/help/calculator.html>.
        """
        d = google.Calculator().evaluate(expn)
        d.addCallback(source.reply)
        return d
