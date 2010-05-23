from axiom.attributes import text, textlist
from axiom.item import Item

from eridanusstd import errors



class AliasDefinition(Item):
    name = text(doc="""
    Name.
    """, allowNone=False)
    params = textlist(doc="""
    Command parameters.
    """, allowNone=False)

    def displayValue(self):
        """
        Display-friendly representation of the alias.
        """
        command = u' '.join(map(repr, self.params))
        return u'%s => %s' % (self.name, command)



def defineAlias(store, name, params):
    """
    Define a new alias overwriting existing aliases with the same name.

    @type name: C{unicode}

    @type params: C{list} of C{unicode}

    @rtype: L{eridanusstd.alias.AliasDefinition}
    """
    # There can be only one.
    undefineAlias(store, name)

    return AliasDefinition(
        store=store,
        name=name,
        params=params)



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
    a = store.findFirst(AliasDefinition, AliasDefinition.name == name)
    if a is None:
        raise errors.InvalidIdentifier(
            u'%r is not a valid alias name' % (name,))
    return a
