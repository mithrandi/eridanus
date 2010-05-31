from axiom.attributes import text
from axiom.item import Item

from eridanusstd import errors



class AliasDefinition(Item):
    """
    An aliased command definition.
    """
    name = text(doc="""
    Name.
    """, allowNone=False, indexed=True)

    command = text(doc="""
    Aliased command.
    """, allowNone=False)

    def displayValue(self):
        """
        Display-friendly representation of the alias.
        """
        return u'%s => %s' % (self.name, self.command)



def defineAlias(store, name, command):
    """
    Define a new alias overwriting existing aliases with the same name.

    @type name: C{unicode}

    @type command: C{unicode}

    @raise eridanusstd.errors.InvalidIdentifier: If C{name} contains whitespace.

    @rtype: L{eridanusstd.alias.AliasDefinition}
    """
    if u' ' in name:
        raise errors.InvalidIdentifier(
            u'%r is not a valid alias name' % (name,))

    # There can be only one.
    undefineAlias(store, name)

    return AliasDefinition(
        store=store,
        name=name,
        command=command)



def undefineAlias(store, name):
    """
    Undefine an alias.

    @type name: C{unicode}
    """
    store.query(AliasDefinition, AliasDefinition.name == name).deleteFromStore()



def findAlias(store, name):
    """
    Find an alias by name.

    @type name: C{unicode}

    @raise eridanusstd.errors.InvalidIdentifier: If C{name} does not refer to
        any known alias.

    @rtype: L{eridanusstd.alias.AliasDefinition}
    """
    a = store.findUnique(
        AliasDefinition, AliasDefinition.name == name, default=None)
    if a is None:
        raise errors.InvalidIdentifier(
            u'%r is not a valid alias name' % (name,))
    return a



def getAliases(store):
    """
    Get all L{eridanusstd.alias.AliasDefinition}s.
    """
    return store.query(AliasDefinition, sort=AliasDefinition.name.ascending)
