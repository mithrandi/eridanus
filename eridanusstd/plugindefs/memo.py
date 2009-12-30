from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer, inmemory
from axiom.item import Item

from eridanus import errors, util as eutil
from eridanus.ieridanus import IEridanusPluginProvider, IAmbientEventObserver
from eridanus.plugin import Plugin, usage, AmbientEventObserver

from eridanusstd import memo

class Memo(Item, Plugin, AmbientEventObserver):
    """
    A simple memo service.

    Memos are left with the bot for a specific nickname, when the matching
    nickname becomes active all stored memos for that nickname are recited.
    """
    classProvides(IPlugin, IEridanusPluginProvider, IAmbientEventObserver)
    schemaVersion = 1
    typeName = 'eridanus_plugins_memoplugin'

    dummy = integer()

    manager = inmemory()

    def activate(self):
        self.manager = memo.MemoManager(self.store)

    @usage(u'leave <nickname> <message>')
    def cmd_leave(self, source, nickname, message):
        """
        Leave a memo for <nickname>.

        Memos will be given to <nickname> when they are next active in the
        channel where the memo was left.
        """
        # XXX: this probably breaks when source.channel is a private message
        self.manager.leaveMemo(source.channel,
                               source.user.nickname,
                               nickname,
                               message)

        source.reply(u'Memo left for \002%s\002.' % (nickname,))

    @usage(u'list <nickname>')
    def cmd_list(self, source, nickname):
        """
        List pending memos for <nickname>.
        """
        def getMemos():
            memos = list(self.manager.getMemosFor(source.channel, source.user.nickname))
            if not memos:
                yield u'No memos for %s.' % (nickname,)
            else:
                for i, memo in enumerate(memos):
                    yield u'\002%d\002 %s ago by \002%s\002: %s;' % (
                        i + 1,
                        memo.displayAgo,
                        memo.sender,
                        eutil.truncate(memo.message, 40))

        source.reply(u' '.join(getMemos()))

    ### IAmbientEventObserver

    def publicMessageReceived(self, source, message):
        memos = self.manager.getMemosFor(source.channel, source.user.nickname)
        for memo in memos:
            source.tell(source.user.nickname, memo.displayMessage)
            memo.deleteFromStore()
