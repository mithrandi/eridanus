"""
This is a module used in a test, not a test itself.
"""

from zope.interface import classProvides
from twisted.plugin import IPlugin

from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin

class SadPlugin(Plugin):
    """
    A plugin that does nothing.
    """
    classProvides(IPlugin, IEridanusPluginProvider)


# Here we import a mythical module to generate an ImportError.
import gyre_and_gimble_in_the_wabe
gyre_and_gimble_in_the_wabe
