import sys

from axiom.store import Store

from eridanus.bot import IRCBotService


db = Store(sys.argv[1])
svc = db.findUnique(IRCBotService, IRCBotService.serviceID == sys.argv[2])
svc.config.name = sys.argv[3].decode('utf-8')
