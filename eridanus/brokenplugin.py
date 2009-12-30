import sys

from zope.interface import classProvides
from twisted.plugin import IPlugin

from eridanus.ieridanus import IEridanusPluginProvider

def brokenPlugin(name):
    einfo = sys.exc_info()
    class BrokenPlugin(object):
        classProvides(IPlugin, IEridanusPluginProvider)
        pluginName = name.split('Plugin')[0]
        exc_info = einfo
        def __init__(self, *args, **kw):
            etype, evalue, etrace = self.exc_info
            raise etype, evalue, etrace
    return BrokenPlugin
