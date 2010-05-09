import sys

from axiom.store import Store

from eridanus.entry import Entry


db = Store(sys.argv[1])

for e in db.query(Entry):
    c = list(e.comments)
    if c:
        c = c[0]
        if c.nick == e.nick:
            c.initial = True
