from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer, inmemory
from axiom.item import Item

from eridanus import util as eutil
from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage, rest

from eridanusstd import urbandict



class UrbanDict(Item, Plugin):
    """
    Urban Dictionary.

    An API key for `urbandict` is required in order for this plugin to work.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    typeName = 'eridanus_plugins_urbandict'

    dummy = integer()

    service = inmemory()

    def activate(self):
        apiKey = eutil.getAPIKey(self.store, u'urbandict')
        self.service = urbandict.UrbanDictService(apiKey)


    @rest
    @usage(u'define <term>')
    def cmd_define(self, source, term):
        """
        Get all definitions for <term> on Urban Dictionary.
        """
        def formatResults(results):
            for i, result in enumerate(results):
                word = result[u'word']
                # XXX: this should be a paginated/multiline output
                dfn = eutil.unescapeEntities(result[u'definition'])
                dfn = u' '.join(dfn.splitlines())
                yield u'\002%d. %s\002: %s;' % (i + 1, word, dfn)

        def displayResults(formattedResults):
            source.reply(u' '.join(formattedResults))

        return self.service.lookup(term
            ).addCallback(formatResults
            ).addCallback(displayResults)


    @usage(u'verifyKey')
    def cmd_verifykey(self, source):
        """
        Verify that the currently set API key is valid.
        """
        def gotResult(isValid):
            result = (u'is not', 'is')[isValid]
            msg = u'The API key %s valid.' % (result,)
            source.reply(msg)

        return self.service.verify_key().addCallback(gotResult)
