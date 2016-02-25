from twisted.trial.unittest import TestCase

from eridanus.ieridanus import ICommand
from eridanus.plugin import getAllPlugins



class CommandTests(TestCase):
    """
    Tests for plugin commands.
    """
    def test_all(self):
        """
        Iterate all available commands on all available plugins in an attempt
        to find broken commands.
        """
        for plg in getAllPlugins():
            parent = ICommand(plg())
            for cmd in parent.getCommands():
                pass
