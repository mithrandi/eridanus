from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

from eridanusstd import qdb

class QDB(Item, Plugin):
    """
    Retrieve quotes from various quote databases.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_qdb'

    dummy = integer()

    def getQuote(self, source, quoteID, func):
        def gotQuote(lines):
            map(source.say, lines)

        return func(quoteID).addCallback(gotQuote)

    @usage(u'qdbus <quoteID>')
    def cmd_qdbus(self, source, quoteID):
        """
        Retrieve <quoteID> from qdb.us.
        """
        return self.getQuote(source, quoteID, qdb.qdbUS)

    @usage(u'bash <quoteID>')
    def cmd_bash(self, source, quoteID):
        """
        Retrieve <quoteID> from bash.org.
        """
        return self.getQuote(source, quoteID, qdb.bash)

    @usage(u'slipgate <quoteID>')
    def cmd_slipgate(self, source, quoteID):
        return self.getQuote(source, quoteID, qdb.slipgate)

