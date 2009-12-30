from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

from eridanusstd import timeutil

class TimePlugin(Item, Plugin):
    """
    Time-related functions.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_time'

    name = u'time'
    pluginName = u'Time'

    dummy = integer()

    # XXX: should be a network config variables probably
    timeFormat = '%a, %Y-%m-%d %H:%M:%S %Z (%z)'
    defaultTimezoneName = u'Africa/Johannesburg'

    @usage(u'now [timezoneName]')
    def cmd_now(self, source, timezoneName=None):
        """
        Show the current time in the default timezone, or <timezoneName>.
        """
        if timezoneName is None:
            timezoneName = self.defaultTimezoneName

        dt = timeutil.now(timezoneName)
        source.reply(timeutil.format(dt, self.timeFormat))

    @usage(u'convert <timeString> [timezoneName]')
    def cmd_convert(self, source, timeString, timezoneName=None):
        """
        Convert <timeString> to the default timezone, or <timezoneName>.

        <timeString> should be a valid time string, the format of which is
        fairly flexible but care should be taken to quote <timeString> if it
        includes spaces. e.g. time convert "10:00 JST" Europe/Paris
        """
        if timezoneName is None:
            timezoneName = self.defaultTimezoneName

        dt = timeutil.convert(timeString, timezoneName, self.defaultTimezoneName)
        source.reply(timeutil.format(dt, self.timeFormat))
