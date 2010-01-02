from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

from eridanusstd import xboxlive

class XboxLive(Item, Plugin):
    """
    XBOX Live related services.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_xboxliveplugin'

    name = u'xbl'

    dummy = integer()

    @usage(u'gamertag <gamertag>')
    def cmd_gamertag(self, source, gamertag):
        """
        Display a brief gamertag for <gamertag>.
        """
        def gotOverview(overview):
            def _getFields():
                yield u'Gamertag', overview['Gamertag']
                yield u'Gamerscore', overview['GamerScore']
                recentGames = overview['RecentGames']
                if recentGames:
                    game = recentGames[0]
                    yield u'Last played', u'%s (%s/%s gamerscore from %s/%s achievements)' % (
                        game['Name'], game['GamerScore'], game['TotalGamerScore'],
                        game['Achievements'], game['TotalAchievements'])

            msg = u'; '.join(u'\002%s\002: %s' % (key, value) for key, value in _getFields())
            source.reply(msg)

        return xboxlive.getGamertagOverview(gamertag
            ).addCallback(gotOverview)
