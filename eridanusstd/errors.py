class InvalidEntry(ValueError):
    """
    An invalid LinkDB entry was specified.
    """


class InvalidDictionary(ValueError):
    """
    An invalid dictionary database was specified.
    """


class NoDefinitions(ValueError):
    """
    No dictionary definitions are available for the specified word.
    """


class InvalidLanguage(ValueError):
    """
    An invalid dictionary language was specified.
    """


class NoSearchResults(ValueError):
    """
    A search yielded zero results.
    """


class NoMoreItems(RuntimeError):
    """
    A deferred-iterator has no more items.
    """


class NoSuchFactoid(ValueError):
    """
    No factoid exists for the given key or number.
    """


class TooManyFactoids(ValueError):
    """
    Too many factoids were returned.
    """


class MissingBinary(ValueError):
    """
    An external process' binary was not found.
    """


class NoFortunes(ValueError):
    """
    No fortunes were found with the specified criteria.
    """


class InvalidGamertag(ValueError):
    """
    The specified Xbox Live gamertag is invalid.
    """


class InvalidCurrency(ValueError):
    """
    The specified currency code is invalid.
    """


class InvalidQuote(ValueError):
    """
    This specified quote ID is invalid.
    """



class InvalidExpression(ValueError):
    """
    An invalid calculator expression was specified.
    """



class RequestError(ValueError):
    """
    A bad request was made.
    """
    def __init__(self, request, error):
        self.request = request
        self.error = error
        super(RequestError, self).__init__(u'%s: %s' % (request, error))
