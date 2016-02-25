from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage, rest

from eridanusstd import imdb



class IMDB(Item, Plugin):
    classProvides(IPlugin, IEridanusPluginProvider)
    typeName = 'eridanus_plugins_imdb'

    dummy = integer()

    @rest
    @usage(u'search <title>')
    def cmd_search(self, source, title):
        """
        Search IMDB for artifacts whose titles match <title>.
        """
        def gotResults(results):
            for name, url, id in results:
                yield u'\002%s\002: <%s>;' % (name, url)

        def outputResults(results):
            source.reply(u' '.join(results))

        # XXX: Exact and the artifacts to search should maybe be configurable.
        # XXX: On the other hand, IMDB's search sucks badly, something more
        # useful should be written on top of the search.
        return imdb.searchByTitle(title, exact=False
            ).addCallback(gotResults
            ).addCallback(outputResults)


    @usage(u'plot <id>')
    def cmd_plot(self, source, id):
        """
        Retrieve the plot information for an IMDB title with <id>.
        """
        def gotInfo(info):
            source.reply(u'\002%(title)s (%(year)s)\002: %(summary)s' % info)

        return imdb.getInfoByID(id
            ).addCallback(gotInfo)

