from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

from eridanusstd import weather

class WeatherPlugin(Item, Plugin):
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_weatherplugin'

    name = u'weather'
    pluginName = u'Weather'

    dummy = integer()

    @usage(u'current <location>')
    def cmd_current(self, source, location):
        """
        Get the current weather conditions for <location>.
        """
        def gotWeather(cond):
            source.reply(cond.display)

        return weather.Wunderground.current(location).addCallback(gotWeather)
