import sys

from axiom.item import Item
from axiom.attributes import integer
from zope.interface import classProvides

from twisted.plugin import IPlugin

from eridanus.ieridanus import IEridanusPluginProvider

def brokenPlugin(name):
    etype, evalue, etrace = sys.exc_info()
    class BrokenPlugin(Item):
        classProvides(IPlugin, IEridanusPluginProvider)
        pluginName = name.split('Plugin')[0]
        dummy = integer()
        def __init__(self, *args, **kw):
            raise etype, evalue, etrace
    return BrokenPlugin
