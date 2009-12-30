from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item
from axiom.userbase import getAccountNames

from eridanus import errors
from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

class Authenticate(Item, Plugin):
    """
    Authentication related commands.
    """
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_authenticate'

    name = u'auth'

    dummy = integer()

    @usage(u'login <password>')
    def cmd_login(self, source, password):
        """
        Authenticate yourself to the service.
        """
        def loginDone(dummy):
            source.reply(u'Successfully authenticated.')

        return source.protocol.login(source.user.nickname, password
            ).addCallbacks(loginDone)

    @usage(u'logout')
    def cmd_logout(self, source):
        """
        Unauthenticate yourself to the service.
        """
        if source.protocol.logout(source.user.nickname):
            source.reply(u'Unauthenticated.')

    @usage(u'whoami')
    def cmd_whoami(self, source):
        """
        Find out who you are authenticated as.
        """
        nickname = source.user.nickname
        try:
            avatar = source.protocol.getAuthenticatedAvatar(nickname)
            username, domain = getAccountNames(avatar.store).next()
            msg = u'Authenticated as "%s@%s".' % (username, domain)
        except errors.AuthenticationError:
            msg = u'Not authenticated.'
        source.reply(msg)

