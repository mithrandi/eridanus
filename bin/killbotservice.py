import sys

from axiom.store import Store
from axiom.dependency import uninstallFrom

from eridanus.bot import IRCBotService


db = Store(sys.argv[1])

for svc in db.query(IRCBotService):
    uninstallFrom(svc, db)
