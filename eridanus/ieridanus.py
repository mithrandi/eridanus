from zope.interface import Interface, Attribute


class INetwork(Interface):
    """
    """
    def managerByChannel(channel):
        """
        """


class IEntryManager(Interface):
    """
    """
    network = Attribute("""
    """)

    channel = Attribute("""
    """)

    def createEntry(nick, url, comment=None, title=None):
        """
        """

    def entryById(id):
        """
        """

    def entryByUrl(url):
        """
        """
