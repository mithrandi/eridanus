from twisted.trial import unittest

from axiom.store import Store

from eridanusstd import alias, errors
from eridanusstd.plugindefs import alias as alias_plugin



class AliasTests(unittest.TestCase):
    """
    Tests for L{eridanusstd.alias}.
    """
    def setUp(self):
        self.store = Store()
        self.anAlias = alias.AliasDefinition(
            store=self.store,
            name=u'foo',
            command=u'"hello world" quux')


    def test_displayValue(self):
        """
        L{eridanusstd.alias.AliasDefinition.displayValue} returns
        human-readable text accurately representing the alias.
        """
        self.assertEquals(
            self.anAlias.displayValue(),
            u'foo => "hello world" quux')


    def test_find(self):
        """
        Defining an alias creates a L{eridanusstd.alias.AliasDefinition} that
        can be located by L{eridanusstd.alias.findAlias}. Attempting to find an
        alias that does not exist results in
        L{eridanusstd.errors.InvalidIdentifier} being raised.
        """
        self.assertEquals(alias.findAlias(self.store, u'foo'), self.anAlias)
        self.assertRaises(errors.InvalidIdentifier,
            alias.findAlias, self.store, u'sonotanalias')


    def test_defineInvalid(self):
        """
        Alias names may not contain spaces.
        """
        self.assertRaises(errors.InvalidIdentifier,
            alias.defineAlias, self.store, u'hello world', u'cmd')


    def test_defineOverwrite(self):
        """
        Creating an alias with the same name as another alias will overwrite
        the previous alias.
        """
        b = alias.defineAlias(self.store, u'foo', u'cmd')
        self.assertEquals(alias.findAlias(self.store, u'foo'), b)
        self.assertNotEquals(alias.findAlias(self.store, u'foo'), self.anAlias)


    def test_undefine(self):
        """
        Undefining an alias causes it to stop existing.
        """
        alias.undefineAlias(self.store, u'foo')
        self.assertRaises(errors.InvalidIdentifier,
            alias.findAlias, self.store, u'foo')


    def test_getAliases(self):
        """
        L{eridanusstd.alias.getAliases} retrieves all defined aliases, sorted
        in alphabetic order.
        """
        self.assertEquals(
            list(alias.getAliases(self.store)),
            [self.anAlias])

        b = alias.defineAlias(self.store, u'b', u'cmd')
        z = alias.defineAlias(self.store, u'z', u'cmd')
        self.assertEquals(
            list(alias.getAliases(self.store)),
            [b, self.anAlias, z])



class AliasPluginTests(unittest.TestCase):
    """
    Tests for L{eridanusstd.plugindefs.alias.Alias}.
    """
    def setUp(self):
        self.store = Store()
        self.plugin = alias_plugin.Alias(store=self.store)
        self.anAlias = alias.AliasDefinition(
            store=self.store,
            name=u'foo',
            command=u'"hello world" quux')


    def test_isTrigger(self):
        """
        L{eridanusstd.plugindefs.alias.Alias._isTrigger} returns C{True} only
        if a message begins with the alias trigger.
        """
        self.assertTrue(self.plugin._isTrigger(u'!foo'))
        self.assertFalse(self.plugin._isTrigger(u' !foo'))
        self.assertFalse(self.plugin._isTrigger(u'@@foo'))
        self.assertFalse(self.plugin._isTrigger(u'foo'))

        self.plugin.trigger = u'@@'
        self.assertFalse(self.plugin._isTrigger(u'!foo'))
        self.assertFalse(self.plugin._isTrigger(u'@foo'))
        self.assertTrue(self.plugin._isTrigger(u'@@foo'))


    def test_expandAlias(self):
        """
        L{eridanusstd.plugindefs.alias.Alias._expandAlias} expands a valid
        alias identifier to the aliased command, any additional parameters
        specified when triggering the alias are added to the aliased command
        being executed.
        """
        self.assertEquals(
            self.plugin._expandAlias(u'foo'),
            u'"hello world" quux')

        self.assertEquals(
            self.plugin._expandAlias(u'foo bar'),
            u'"hello world" quux bar')

        self.assertIdentical(
            self.plugin._expandAlias(u''),
            None)

        self.assertRaises(errors.InvalidIdentifier,
            alias.findAlias, self.store, u'sonotanalias')
