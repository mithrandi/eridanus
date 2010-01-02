"""
This is a module used in a test, not a test itself.
"""

from zope.interface import classProvides
from twisted.plugin import IPlugin

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin

class UselessPlugin(Plugin):
    """
    A plugin that does nothing.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
