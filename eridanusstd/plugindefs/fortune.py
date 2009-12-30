from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

from eridanusstd import fortune

class Fortune(Item, Plugin):
    """
    Provides access to the system's `fortune` command.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_fortune'

    dummy = integer()

    def outputFortunes(self, fortunes, source):
        fortunes = (u'\002%s\002: %s' % (db, u' '.join(msg))
                    for db, msg in fortunes)
        source.reply(u' '.join(fortunes))

    def fortune(self, source, **kw):
        if kw.get('db') == u'*':
            kw['db'] = None

        return fortune.fortune(**kw).addCallback(self.outputFortunes, source)

    @usage(u'short [db] [match]')
    def cmd_short(self, source, db=u'*', match=None):
        """
        Retrieve a short fortune.

        <db> can be "*" to match all available fortune databases.
        """
        return self.fortune(source,
                            short=True,
                            db=db,
                            match=match)

    @usage(u'fortune [db]')
    def cmd_fortune(self, source, db=u'*'):
        """
        Retrieve a fortune.

        <db> defaults to "*" to match all available fortune databases.
        """
        return self.fortune(source,
                            db=db)

    @usage(u'match <match> [db]')
    def cmd_match(self, source, match, db=u'*'):
        """
        Match fortunes.

        <db> defaults to "*" to match all available fortune databases.
        """
        return self.fortune(source,
                            db=db,
                            match=match)

