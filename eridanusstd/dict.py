import enchant, dictclient

from eridanusstd import errors


def getDicts(host=None):
    """
    Return an iterable of C{(dbName, description)} pairs.
    """
    if host is None:
        host = 'localhost'
    conn = dictclient.Connection(host)
    return ((unicode(name, 'ascii'), unicode(desc, 'ascii'))
            for name, desc in conn.getdbdescs().iteritems())


def define(word, database=None, host=None):
    """
    Attempt to look up the dictionary definition of C{word}.

    @type word: C{unicode} or C{str}
    @param word: The word to find the definition for.

    @type database: C{unicode} or C{str}
    @param database: The dictionary database name to consult, C{*} means
        retrieve results from all available dictionaries and C{!} means
        retrieve only the first result

    @type host: C{unicode} or C{str}
    @param host: The dictd host to connect to, defaults to C{localhost}

    @raise errors.InvalidDictionary: If C{database} is not a valid name
    @raise errors.NoDefinitions: If C{word} has no definitions

    @rtype: C{iterable} of C{(unicode, unicode)}
    @return: An iterable of C{(dbName, definition)} pairs
    """
    if database is None:
        database = '*'
    if host is None:
        host = 'localhost'

    conn = dictclient.Connection(host)
    try:
        definitions = conn.define(database, word)
    except:
        raise errors.InvalidDictionary(u'No such dictionary database "%s"' % (database,))

    if not definitions:
        raise errors.NoDefinitions(u'No definitions for "%s" in "%s"' % (word, database))

    for d in definitions:
        defLines = (unicode(line, 'ascii')
                    for line in d.getdefstr().splitlines()
                    if line)
        yield unicode(d.getdb().getname(), 'ascii'), u' '.join(defLines)


_enchantBroker = enchant.Broker()
# XXX: there should probably be some way to specify this
_enchantBroker.set_ordering('*', 'aspell,ispell,myspell')

def spell(word, language):
    """
    Check the spelling of C{word} in C{language}

    @type word: C{unicode}

    @type language: C{unicode}

    @raise errors.InvalidLanguage: If no dictionary for C{language} could be
        found

    @rtype: C{list} or C{None}
    @return: A list of suggestions if C{word} is spelt incorrectly or C{None}
        if it is not
    """
    global _enchantBroker
    try:
        d = _enchantBroker.request_dict(language)
    except enchant.DictNotFoundError:
        raise errors.InvalidLanguage(u'No dictionary for language "%s"' % (language,))

    if not d.check(word):
        return d.suggest(word)

    return None
