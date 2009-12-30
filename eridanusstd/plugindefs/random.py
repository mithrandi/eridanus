import random

from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

class RandomPlugin(Item, Plugin):
    classProvides(IPlugin, IEridanusPluginProvider)

    name = u'random'
    pluginName = u'Random'

    dummy = integer()

    @usage(u'sample <count> <option1> [option2] [...]')
    def cmd_sample(self, source, count, option1, *options):
        count = int(count)
        options = [option1] + list(options)
        source.reply(u', '.join(random.sample(options, count)))
