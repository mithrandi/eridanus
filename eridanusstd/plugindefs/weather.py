from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage, rest

from eridanusstd import weather



class Weather(Item, Plugin):
    classProvides(IPlugin, IEridanusPluginProvider)
    typeName = 'eridanus_plugins_weatherplugin'

    dummy = integer()

    @rest
    @usage(u'current <location>')
    def cmd_current(self, source, location):
        """
        Get the current weather conditions for <location>.
        """
        def gotWeather(cond):
            source.reply(cond.display)

        return weather.Wunderground.current(location).addCallback(gotWeather)
