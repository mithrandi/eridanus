import random

from zope.interface import classProvides

from twisted.plugin import IPlugin

from axiom.attributes import integer
from axiom.item import Item

from eridanus import errors, util as eutil, reparse
from eridanus.ieridanus import IEridanusPluginProvider
from eridanus.plugin import Plugin, usage

from eridanusstd import factoid

class Factoid(Item, Plugin):
    classProvides(IPlugin, IEridanusPluginProvider)
    schemaVersion = 1
    typeName = 'eridanus_plugins_factoid'

    dummy = integer()

    @usage(u'list <key>')
    def cmd_list(self, source, key):
        """
        List all factoids for <key>.
        """
        def formatFactoid(fact, n):
            return u'\002%d\002: %s' % (n, fact.value)

        factoids = factoid.getFactoids(self.store, key)
        factoidText = (eutil.truncate(formatFactoid(fact, i), 40)
                       for i, fact in enumerate(factoids))
        msg = u'  '.join(factoidText)
        source.reply(msg)

    @usage(u'get <key> [index]')
    def cmd_get(self, source, key, index=None):
        """
        Retrieve a factoid for <key>.

        If <index> is omitted, a random factoid for <key> is retrieved.
        """
        if index is not None:
            fac = factoid.getFactoid(self.store, key, int(index))
        else:
            factoids = list(factoid.getFactoids(self.store, key))
            fac = random.sample(factoids, 1)[0]
        source.reply(u'%s \002is\002 %s' % (fac.key, fac.value))

    @usage(u'set <key> <value>')
    def cmd_set(self, source, key, value):
        """
        Replace all factoids for <key> with <value>.
        """
        factoid.setFactoid(self.store, source.user.nickname, key, value)
        source.reply(u'Set factoid for "%s".' % (key,))

    @usage(u'add <key> <value>')
    def cmd_add(self, source, key, value):
        """
        Add a new factoid for <key>.
        """
        factoid.createFactoid(self.store, source.user.nickname, key, value)
        source.reply(u'Added a factoid for "%s".' % (key,))

    @usage(u'delete <key> <index>')
    def cmd_delete(self, source, key, index):
        """
        Delete a factoid for <key>.

        If `*` is supplied for <index>, all factoids for <key> are deleted.
        """
        if index == u'*':
            index = None
            msg = u'Deleted all factoids for "%s".' % (key,)
        else:
            index = int(index)
            msg = u'Deleted %d for factoid "%s".' % (index, key)
        factoid.deleteFactoid(self.store, key, index)
        source.reply(msg)

    @usage(u'replace <key> <index> <value>')
    def cmd_replace(self, source, key, index, value):
        """
        Replace a specific factoid for <key>.
        """
        index = int(index)
        factoid.replaceFactoid(self.store,
                               source.user.nickname,
                               key,
                               index,
                               value)
        source.reply(u'Replaced %d for factoid "%s".' % (index, key))

    @usage(u'change <key> <regexp>')
    def cmd_change(self, source, key, regexp):
        """
        Change factoids for <key> based on a regular expression.

        <regexp> should be of the form `s/foo/bar/`, `g` and `i` flags are
        accepted.  If <regexp> matches multiple factoids for <key>, the global
        (`g`) flag must be specified.
        """
        subst = reparse.parseRegex(regexp)
        numChanged = factoid.changeFactoids(self.store,
                                            source.user.nickname,
                                            key,
                                            subst)
        source.reply(u'Changed %d factoid(s).' % (numChanged,))
