from epsilon.extime import Time

from axiom.item import Item
from axiom.attributes import AND, timestamp, text

from eridanusstd import errors


class Factoid(Item):
    """
    A factoid.

    The crux of this item is the key/value concept.  The goal is to have
    keys mapping to multiple values, which can be built up into a simple
    snippets of information tied to topics.
    """
    typeName = 'eridanus_plugins_factoid_factoid'
    schemaVersion = 1

    created = timestamp(doc="""
    Creation time of this Factoid.
    """, defaultFactory=lambda: Time())

    creator = text(doc="""
    The name of the original creator.
    """, allowNone=False)

    modified = timestamp(doc="""
    Modification time of this Factoid.
    """, defaultFactory=lambda: Time())

    editor = text(doc="""
    The name of the last person to modify this factoid.
    """, allowNone=False)

    key = text(doc="""
    The factoid key.
    """, indexed=True, allowNone=False)

    value = text(doc="""
    A factoid value.
    """, allowNone=False)

    def touchFactoid(self, editor):
        self.editor = editor
        self.modified = Time()


def createFactoid(appStore, creator, key, value):
    """
    Create a new factoid.

    If a factoid with the same key and value already exists, it is returned
    instead of creating a duplicate.

    @type appStore: C{axiom.store.Store}

    @type creator: C{unicode}
    @param creator: The name of the creator

    @type key: C{unicode}
    @param key: Factoid key

    @type value: C{unicode}
    @param value: Factoid value

    @rtype: L{Factoid}
    @return: The newly created factoid or the one that matches C{key} and
        C{value}
    """
    factoid = appStore.findFirst(Factoid, AND(Factoid.key == key,
                                              Factoid.value == value))

    if factoid is None:
        factoid = Factoid(store=appStore,
                          creator=creator,
                          editor=creator,
                          key=key,
                          value=value)

    return factoid


def deleteFactoid(appStore, key, number):
    """
    Delete a factoid.

    @type appStore: C{axiom.store.Store}

    @type key: C{unicode}
    @param key: Factoid key

    @type number: C{int} or C{None}
    @param number: The factoid index to delete or C{None} to delete all
        factoids associated with C{key}
    """
    factoids = getFactoids(appStore, key)
    if number is not None:
        factoids = list(factoids)[number]
    factoids.deleteFromStore()


def setFactoid(appStore, creator, key, value):
    """
    Replace all factoids for C{key} with C{value}.
    """
    appStore.query(Factoid, Factoid.key == key).deleteFromStore()
    createFactoid(appStore, creator, key, value)


def getFactoids(appStore, key):
    """
    Retrieve all factoids for C{key}.

    Results are sorted by their date of creation in ascending order.

    @rtype: C{iterable} of C{Factoid}s
    """
    # XXX: Everything that uses an index relies on this sorting order,
    # I'm not sure if this is sane or not.
    factoids = appStore.query(Factoid,
                              Factoid.key == key,
                              sort=Factoid.created.ascending)

    if factoids.count() == 0:
        raise errors.NoSuchFactoid(u'No factoids for "%s" were found.' % (key,))

    return factoids


def getFactoid(appStore, key, index):
    """
    Get a factoid for C{key} by index.
    """
    factoids = list(getFactoids(appStore, key))
    try:
        return factoids[index]
    except IndexError:
        raise errors.NoSuchFactoid(u'Invalid index "%d" for "%s".' % (index, key))


def getMatchingFactoids(appStore, key, pattern):
    """
    Find all factoids for C{key} that match C{pattern}.

    @type pattern: A compiled regular expression object
    @param pattern: The pattern to match factoids against

    @rtype: C{iterable} of C{Factoid}s
    """
    for factoid in getFactoids(appStore, key):
        if pattern.search(factoid.value) is not None:
            yield factoid


def replaceFactoid(appStore, editor, key, index, value):
    """
    Replace a single factoid's value.
    """
    factoid = getFactoid(appStore, key, index)
    factoid.value = value
    factoid.touchFactoid(editor)


def changeFactoids(appStore, editor, key, subst):
    """
    Change all factoids for C{key} that match a given pattern.

    @type subst: C{eridanus.reparse.Substitution}
    @param subst: A substitution object to match entries against and to
        perform the change

    @raise errors.TooManyFactoids: If multiple factoids match C{subst} and the
        global flag was not specified

    @rtype: C{int}
    @return: The number of factoids affected
    """
    factoids = list(getMatchingFactoids(appStore, key, subst.pattern))
    numFactoids = len(factoids)
    if numFactoids > 1 and not subst.globalFlag:
        raise errors.TooManyFactoids(u'Refusing to change multiple results (%d) without the global flag' % (numFactoids,))

    for factoid in factoids:
        factoid.value = subst.sub(factoid.value)
        factoid.touchFactoid(editor)

    return numFactoids
