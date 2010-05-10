import sys

from axiom.store import Store

from eridanus.bot import IRCBotService


db = Store(sys.argv[1])
for svc in db.query(IRCBotService):
    for manager in svc.config.allEntryManagers():
        if not manager.channel.startswith(u'#'):
            print manager
            manager.deleteFromStore()
