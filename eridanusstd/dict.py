import enchant, dictclient

from twisted.internet import protocol, defer
from twisted.protocols import dict as tpdict
from twisted.python import failure

from eridanusstd import errors


class DictUsefulClient(tpdict.DictLookup):
    def defineFailed(self, reason):
        if reason == 'Invalid database':
            e = errors.InvalidDictionary(u'Invalid database "%s"' % (self.factory.args[0],))
        elif reason == 'No match':
            e = errors.NoDefinitions('No definitions for "%s" in "%s"' % (self.factory.args[1], self.factory.args[0]))
        else:
            # XXX: not great
            e = ValueError(reason)
        f = failure.Failure(e)
        self.failure(f)

    def dictConnected(self):
        _queries = {
            'define': self.sendDefine,
            'show':   self.sendShow,
            }

        f = _queries.get(self.factory.queryType)
        if f is not None:
            f(*self.factory.args, **self.factory.kwargs)

    def success(self, result):
        self.factory.d.callback(result)
        self.factory.clientDone()
        self.transport.loseConnection()

    def failure(self, f):
        self.factory.d.errback(f)
        self.factory.clientDone()
        self.transport.loseConnection()

    def sendShow(self, param):
        assert self.state == 'ready', 'DictClient.sendShow called when not in ready state'
        self.result = None  # these two are just in case. In "ready" state, result and data
        self.data = None    # should be None
        self.state = 'show'
        command = 'SHOW %s' % (param,)
        self.sendLine(command)

    def showDone(self, result):
        self.factory.d.callback(result)
        self.factory.clientDone()
        self.transport.loseConnection()

    def dictCode_110_show(self, line):
        self.mode = 'text'
        self.result = []

    def dictCode_text_show(self, line):
        if line == '.':
            self.mode = 'ready'
        else:
            name, desc = line.split(u' ', 1)
            desc = tpdict.parseParam(desc)[0]
            self.result.append((name, desc))

    def dictCode_250_show(self, line):
        self.success(self.result)


class DictFactory(protocol.ClientFactory):
    protocol = DictUsefulClient
    done = None

    def __init__(self, queryType, *a, **kw):
        self.queryType = queryType
        self.args = a
        self.kwargs = kw
        self.done = False
        self.d = defer.Deferred()

    def clientDone(self):
        self.done = True

    def clientConnectionFailed(self, connector, error):
        self.d.errback(error)

    def clientConnectionLost(self, connector, error):
        if not self.done:
            self.d.errback(error)

    def buildProtocol(self, addr):
        p = self.protocol()
        p.factory = self
        return p


def _dictDo(host, *a, **kw):
    factory = DictFactory(*a, **kw)
    from twisted.internet import reactor
    reactor.connectTCP(host, 2628, factory)
    return factory.d


def getDicts(host=None):
    """
    Return an iterable of C{(dbName, description)} pairs.
    """
    if host is None:
        host = 'localhost'

    return _dictDo(host, 'show', 'DB')


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

    def gotDefinition(definitions):
        if not definitions:
            raise errors.NoDefinitions(u'No definitions for "%s" in "%s"' % (word, database))

        for d in definitions:
            defLines = (line.strip() for line in d.text if line.strip())
            yield d.db, u' '.join(defLines)

    return _dictDo(host, 'define', database, word).addCallback(gotDefinition)


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
