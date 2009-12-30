from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer, inmemory
from axiom.item import Item

from eridanus import util as eutil
from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

from eridanusstd import google

class Google(Item, Plugin):
    """
    Google services.

    It is recommended you set an API key for `googleAjaxSearch`.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_google'

    name = u'google'
    pluginName = u'Google'

    dummy = integer()

    apiKey = inmemory()

    def activate(self):
        self.apiKey = eutil.getAPIKey(self.store, u'googleAjaxSearch', default=None)

    def websearch(self, source, terms, count):
        """
        Perform a Google web search.
        """
        def formatResults(results):
            for title, url in results:
                yield u'\002%s\002: <%s>;' % (title, url)

        def displayResults(formattedResults):
            source.reply(u' '.join(formattedResults))

        q = google.WebSearchQuery(terms, apiKey=self.apiKey)
        return defertools.slice(q.queue, count
            ).addCallback(formatResults
            ).addCallback(displayResults)

    @usage(u'search <term> [term ...]')
    def cmd_search(self, source, term, *terms):
        """
        Perform a Google web search.
        """
        terms = [term] + list(terms)
        return self.websearch(source, terms, 4)

    @usage(u'lucky <term> [term ...]')
    def cmd_lucky(self, source, term, *terms):
        """
        Perform an "I'm feeling lucky" Google web search.
        """
        terms = [term] + list(terms)
        return self.websearch(source, terms, 1)
