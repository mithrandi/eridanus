from twisted.trial import unittest

from axiom.store import Store

from eridanusstd import alias, errors



class AliasTests(unittest.TestCase):
    """
    Tests for L{eridanusstd.alias}.
    """
    def setUp(self):
        self.store = Store()
        self.anAlias = alias.AliasDefinition(
            store=self.store,
            name=u'foo',
            params=[u'hello world',
                    u'quux'])


    def test_displayValue(self):
        """
        L{eridanusstd.alias.AliasDefinition.displayValue} returns
        human-readable text accurately representing the alias.
        """
        self.assertEquals(
            self.anAlias.displayValue(),
            u"foo => u'hello world' u'quux'")


    def test_define(self):
        """
        Defining an alias creates a L{eridanusstd.alias.AliasDefinition} that
        can be located by L{eridanusstd.alias.findAlias}.
        """
        self.assertEquals(alias.findAlias(self.store, u'foo'), self.anAlias)


    def test_defineInvalid(self):
        """
        Alias names may not contain spaces.
        """
        self.assertRaises(errors.InvalidIdentifier,
            alias.defineAlias, self.store, u'hello world', [])


    def test_defineOverwrite(self):
        """
        Creating an alias with the same name as another alias will overwrite
        the previous alias.
        """
        b = alias.defineAlias(self.store, u'foo', [])
        self.assertEquals(alias.findAlias(self.store, u'foo'), b)
        self.assertNotEquals(alias.findAlias(self.store, u'foo'), self.anAlias)


    def test_undefine(self):
        """
        Undefining an alias causes it to stop existing.
        """
        alias.undefineAlias(self.store, u'foo')
        self.assertRaises(errors.InvalidIdentifier,
            alias.findAlias, self.store, u'foo')
