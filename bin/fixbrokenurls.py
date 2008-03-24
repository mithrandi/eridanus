import sys

from axiom.store import Store

from eridanus.entry import Entry, saneURL


db = Store(sys.argv[1])

for e in db.query(Entry):
    o = e.url
    n = saneURL(e.url)
    print repr(o), '=>', repr(n)
    e.url = saneURL(e.url)
